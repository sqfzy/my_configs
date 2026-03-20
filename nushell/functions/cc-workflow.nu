#!/usr/bin/env nu
# cc-workflow.nu — Claude Code 工作流执行器（会话复用 + CLAUDE.md + Git 检查点）
#
# 默认行为：
#   - 方案 A：所有步骤共享同一 claude 会话（--resume）
#   - 方案 B：工作流开始前生成 CLAUDE.md，每步后追加进展
#   - 方案 C：每步执行前 git commit 一个检查点，支持回退
#
# 用法（直接运行）:
#   nu cc-workflow.nu workflow.md
#   nu cc-workflow.nu workflow.md --dry-run
#   nu cc-workflow.nu workflow.md --no-resume
#   nu cc-workflow.nu workflow.md --no-claudemd
#   nu cc-workflow.nu workflow.md --no-checkpoint
#   nu cc-workflow.nu workflow.md list-checkpoints
#   nu cc-workflow.nu workflow.md rollback 3
#
# 用法（作为模块导入）:
#   use cc-workflow.nu
#   cc-workflow workflow.md

const C_RST  = "\e[0m"
const C_BOLD = "\e[1m"
const C_DIM  = "\e[2m"
const C_GRN  = "\e[32m"
const C_YLW  = "\e[33m"
const C_CYN  = "\e[36m"
const C_RED  = "\e[31m"

const CLAUDEMD_INIT_PROMPT = "请分析当前项目，然后创建或完整覆盖写入 CLAUDE.md 文件。
CLAUDE.md 需包含以下内容（如信息暂不存在可留空）：
1. 项目概述：用途、技术栈、语言版本
2. 目录结构：关键目录和文件的职责
3. 架构决策：重要的设计选择和原因
4. 开发规范：代码风格、命名约定、日志规范等
5. 常用命令：构建、测试、运行等
6. 工作流进展：（初始为空，后续步骤会追加）
请直接写入文件，不要只是输出内容。"

const CLAUDEMD_UPDATE_PROMPT = "请将本步骤的执行摘要追加写入 CLAUDE.md 的「工作流进展」章节。
摘要应包含：做了什么、修改了哪些文件、当前状态、下一步需要注意的事项。
格式：### Step {IDX}: {TITLE}\n内容...\n
请直接追加写入文件，不要输出到终端。"

const CHECKPOINT_PREFIX = "cc-workflow checkpoint:"

# ── 安全工具函数 ──────────────────────────────────────────────────

# 安全截断字符串，不会因长度不足而 panic
def safe_truncate [max: int]: string -> string {
    let s = $in
    let len = ($s | str length)
    if $len <= $max { $s } else { $s | str substring 0..($max) }
}

# 安全取首行，空字符串返回 fallback
def first_line [fallback: string]: string -> string {
    let lines = ($in | str trim | lines)
    if ($lines | is-empty) { $fallback } else { $lines | first }
}

# 安全解析 JSON，失败返回 null
def try_from_json []: string -> any {
    let s = $in | str trim
    if ($s | str length) == 0 { return null }
    try { $s | from json } catch { null }
}

# 从 JSON 结果中提取 session_id（string），不存在或类型错误返回空字符串
def extract_session_id []: any -> string {
    let v = $in
    if $v == null { return "" }
    let cols = try { $v | columns } catch { return "" }
    if not ("session_id" in $cols) { return "" }
    let sid = $v.session_id
    if ($sid | describe) == "string" { $sid } else { "" }
}

# 从 JSON 结果中提取 result 文本，不存在返回 fallback
def extract_result [fallback: string]: any -> string {
    let v = $in
    if $v == null { return $fallback }
    let cols = try { $v | columns } catch { return $fallback }
    if not ("result" in $cols) { return $fallback }
    let r = $v.result
    if ($r | describe) == "string" { $r } else { $fallback }
}

# 计算耗时字符串，防止时钟跳变导致负值
def format_elapsed [t_start: datetime, t_end: datetime]: nothing -> string {
    let raw_ms = (($t_end - $t_start) | into int) / 1_000_000
    let ms = if $raw_ms < 0 { 0 } else { $raw_ms }
    $"($ms / 1000).($ms mod 1000 // 10)s"
}

# ── Git 工具函数 ──────────────────────────────────────────────────

def is_git_repo []: nothing -> bool {
    (do { ^git rev-parse --is-inside-work-tree } | complete).exit_code == 0
}

def checkpoint_tag [idx: int, title: string]: nothing -> string {
    let safe = ($title | str replace --regex '[^a-zA-Z0-9\u4e00-\u9fff]+' "-" | safe_truncate 30)
    $"($CHECKPOINT_PREFIX) step-($idx): ($safe)"
}

# git add -A && git commit，静默处理"nothing to commit"
def git_checkpoint [idx: int, title: string]: nothing -> nothing {
    let msg = checkpoint_tag $idx $title
    do { ^git add -A } | complete | ignore
    do { ^git commit --allow-empty -m $msg } | complete | ignore
}

# ── claude 调用封装 ───────────────────────────────────────────────
# 统一处理 resume/new-session 分支，返回 complete record
def run_claude [prompt: string, session_id: string, use_json: bool]: nothing -> record {
    let is_new = ($session_id | str length) == 0
    if $use_json {
        if $is_new {
            do { ^claude -p $prompt --output-format json } | complete
        } else {
            do { ^claude --resume $session_id -p $prompt --output-format json } | complete
        }
    } else {
        do { ^claude -p $prompt } | complete
    }
}

# ── Settings ──────────────────────────────────────────────────────

def setup_settings [settings_path: string]: nothing -> string {
    let dir = ($settings_path | path dirname)
    if not ($dir | path exists) {
        try { mkdir $dir } catch { |e|
            error make { msg: $"无法创建目录 ($dir): ($e.msg)" }
        }
    }

    let backup = if ($settings_path | path exists) {
        let b = $"($settings_path).bak"
        try { cp $settings_path $b } catch { |e|
            error make { msg: $"无法备份 settings.json: ($e.msg)" }
        }
        print $"($C_DIM)↳ 已备份 → ($b)($C_RST)"
        $b
    } else { "" }

    let settings = {
        defaultMode: "bypassPermissions"
        skipDangerousModePermissionPrompt: true
        permissions: {
            allow: [
                "Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "MultiEdit(*)",
                "Glob(*)", "Grep(*)", "WebFetch(*)",
                "TodoRead", "TodoWrite", "NotebookRead", "NotebookEdit"
            ]
            deny: []
        }
    }

    try {
        $settings | to json | save --force $settings_path
    } catch { |e|
        # 写入失败时还原备份，避免留下损坏的 settings
        if ($backup | str length) > 0 and ($backup | path exists) {
            mv --force $backup $settings_path
        }
        error make { msg: $"无法写入 settings.json ($settings_path): ($e.msg)" }
    }

    print $"($C_DIM)↳ 已写入无限制 settings.json → ($settings_path)($C_RST)"
    $backup
}

def restore_settings [settings_path: string, backup: string]: nothing -> nothing {
    if ($backup | str length) > 0 and ($backup | path exists) {
        try { mv --force $backup $settings_path } catch { |e|
            print $"($C_YLW)⚠ 无法还原 settings.json: ($e.msg)($C_RST)"
            print $"($C_DIM)  请手动执行: mv ($backup) ($settings_path)($C_RST)"
        }
    } else if ($settings_path | path exists) {
        try { rm $settings_path } catch {}
    }
}

# ── 主命令 ────────────────────────────────────────────────────────

export def main [
    workflow_file: path
    --dry-run (-n)
    --no-resume
    --no-claudemd
    --no-checkpoint
    --restore-settings (-r)
    --log-dir (-l): string = ""
    --settings-scope (-s): string = "project"
] {
    # 校验 settings-scope
    if $settings_scope not-in ["project", "user"] {
        error make { msg: $"--settings-scope 只接受 'project' 或 'user'，得到: '($settings_scope)'" }
    }

    if not (which claude | is-not-empty) {
        error make { msg: "找不到 claude，请先安装: npm i -g @anthropic-ai/claude-code" }
    }

    let wf_path = ($workflow_file | path expand)
    if not ($wf_path | path exists) {
        error make { msg: $"工作流文件不存在: ($wf_path)" }
    }

    let steps = parse_steps (open $wf_path --raw)
    if ($steps | is-empty) {
        error make { msg: "未找到步骤，请确保文件中有 '## ' 开头的二级标题" }
    }

    let n             = ($steps | length)
    let resume_mode   = not $no_resume
    let claudemd      = not $no_claudemd
    let do_checkpoint = not $no_checkpoint

    # 检查 git，非仓库时询问是否继续
    let checkpoint_ok = if $do_checkpoint and not (is_git_repo) {
        print $"($C_YLW)⚠ 当前目录不是 git 仓库，无法创建检查点($C_RST)"
        print $"($C_DIM)  如需检查点，请先执行: git init && git add -A && git commit -m 'init'($C_RST)"
        print $"  是否仍要继续执行工作流（不含检查点）？输入 ($C_BOLD)yes($C_RST) 继续，其他任意键退出："
        let ans = (input "")
        if $ans != "yes" {
            print "已取消"
            exit 0
        }
        false
    } else {
        $do_checkpoint and (is_git_repo)
    }

    let modes = (
        [ (if $resume_mode   { "A:会话复用" }  else { "" })
          (if $claudemd      { "B:CLAUDE.md" } else { "" })
          (if $checkpoint_ok { "C:Git检查点" } else { "" }) ]
        | where { |x| ($x | str length) > 0 }
        | str join " + "
    )
    print $"($C_GRN)✔($C_RST) 已解析 ($C_BOLD)($n)($C_RST) 个步骤 | ($C_BOLD)($modes)($C_RST)"
    print $"($C_DIM)  工作流: ($wf_path)($C_RST)"

    # ── Dry-run ───────────────────────────────────────────────────
    if $dry_run {
        print $"\n($C_YLW)── DRY RUN ──($C_RST)"
        for step in $steps {
            print $"\n($C_BOLD)[Step ($step.index)] ($step.title)($C_RST)"
            print $"($C_DIM)($step.prompt | str trim)($C_RST)"
        }
        if $checkpoint_ok {
            print $"\n($C_DIM)[方案 C] 每步前会创建 git 检查点($C_RST)"
        }
        print $"\n($C_YLW)── 共 ($n) 步，dry-run 结束 ──($C_RST)"
        return
    }

    # ── Settings ──────────────────────────────────────────────────
    let settings_path = if $settings_scope == "user" {
        $"($env.HOME)/.claude/settings.json"
    } else {
        ".claude/settings.json"
    }
    # setup_settings 内部出错时会还原备份再 error，此处无需额外处理
    let backup = setup_settings $settings_path

    # ── 日志目录 ──────────────────────────────────────────────────
    let log_dir_resolved = if $log_dir != "" {
        let d = ($log_dir | path expand)
        try { mkdir $d } catch { |e|
            error make { msg: $"无法创建日志目录 ($d): ($e.msg)" }
        }
        $d
    } else { "" }

    # ── 方案 B：初始化 CLAUDE.md ──────────────────────────────────
    mut session_id = ""

    if $claudemd {
        print $"\n($C_YLW)── 方案 B：初始化 CLAUDE.md ──($C_RST)"
        let r = run_claude $CLAUDEMD_INIT_PROMPT "" $resume_mode
        if $r.exit_code == 0 {
            let parsed = ($r.stdout | try_from_json)
            if $resume_mode {
                let sid = ($parsed | extract_session_id)
                if ($sid | str length) > 0 {
                    $session_id = $sid
                    print $"($C_GRN)✔ CLAUDE.md 已生成，会话已建立($C_RST)"
                    print $"($C_DIM)  session: ($session_id | safe_truncate 16)...($C_RST)"
                } else {
                    print $"($C_GRN)✔ CLAUDE.md 已生成（未获取 session_id，后续步骤将新建会话）($C_RST)"
                }
            } else {
                print $"($C_GRN)✔ CLAUDE.md 已生成($C_RST)"
            }
        } else {
            let err = ($r.stderr | first_line "（无错误信息）")
            print $"($C_YLW)⚠ CLAUDE.md 初始化失败，继续执行工作流($C_RST)"
            print $"($C_DIM)  ($err)($C_RST)"
        }
    }

    # ── 方案 C：基础检查点 ────────────────────────────────────────
    if $checkpoint_ok {
        print $"\n($C_YLW)── 方案 C：创建基础检查点 ──($C_RST)"
        git_checkpoint 0 "workflow-start"
        print $"($C_DIM)  检查点已创建: step-0 (workflow-start)($C_RST)"
    }

    # ── 执行循环 ──────────────────────────────────────────────────
    print ""
    let total = ($steps | length)
    mut failed_steps: list<int> = []

    for step in $steps {
        let idx        = $step.index
        let title      = $step.title
        let prompt     = ($step.prompt | str trim)
        let first_line = ($prompt | first_line "（空提示词）")

        # 方案 C：步骤前打检查点
        if $checkpoint_ok {
            git_checkpoint $idx $title
            let tag = (checkpoint_tag $idx $title)
            print $"($C_DIM)  [C] ($tag)($C_RST)"
        }

        print $"($C_CYN)┌─ Step ($idx)/($total): ($title)($C_RST)"
        print $"($C_DIM)│ ($first_line)($C_RST)"
        if $resume_mode {
            let label = if ($session_id | str length) > 0 {
                $"resume:($session_id | safe_truncate 8)..."
            } else { "new session" }
            print $"($C_DIM)│ [($label)]($C_RST)"
        }
        print $"($C_CYN)└─ 执行中...($C_RST)"

        let t_start        = (date now)
        let cur_session_id = $session_id   # 快照 mut，避免闭包捕获 mut 变量报错

        let result = run_claude $prompt $cur_session_id $resume_mode

        let t_end      = (date now)
        let elapsed    = format_elapsed $t_start $t_end

        # 解析输出，更新 session_id
        let stdout_text = if $resume_mode and $result.exit_code == 0 {
            let parsed = ($result.stdout | try_from_json)
            let sid    = ($parsed | extract_session_id)
            if ($sid | str length) > 0 { $session_id = $sid }
            $parsed | extract_result $result.stdout
        } else {
            $result.stdout
        }

        if $result.exit_code == 0 {
            print $"($C_GRN)✔ Step ($idx) 完成 [($C_DIM)($elapsed)($C_RST)($C_GRN)]($C_RST)"

            # 方案 B：追加进展
            if $claudemd {
                let update_prompt = (
                    $CLAUDEMD_UPDATE_PROMPT
                    | str replace "{IDX}"   ($idx | into string)
                    | str replace "{TITLE}" $title
                )
                let cur_sid = $session_id
                let upd     = run_claude $update_prompt $cur_sid $resume_mode
                if $upd.exit_code == 0 {
                    if $resume_mode {
                        let parsed = ($upd.stdout | try_from_json)
                        let sid    = ($parsed | extract_session_id)
                        if ($sid | str length) > 0 { $session_id = $sid }
                    }
                    print $"($C_DIM)  [B] CLAUDE.md 已更新($C_RST)"
                } else {
                    let err = ($upd.stderr | first_line "（无错误信息）")
                    print $"($C_YLW)  [B] CLAUDE.md 更新失败（不影响工作流）: ($err)($C_RST)"
                }
            }
            print ""

        } else {
            let err = ($result.stderr | first_line "（无错误信息）")
            print $"($C_RED)✘ Step ($idx) 失败 (exit ($result.exit_code)) [($elapsed)]($C_RST)"
            print $"($C_RED)  ($err)($C_RST)"
            if $checkpoint_ok {
                print $"($C_YLW)  回退命令: nu cc-workflow.nu ($wf_path) rollback ($idx)($C_RST)"
            }
            print ""
            $failed_steps = ($failed_steps | append $idx)
        }

        # 保存日志
        if $log_dir_resolved != "" {
            let idx_str  = if $idx < 10 { $"0($idx)" } else { $"($idx)" }
            let log_file = $"($log_dir_resolved)/step_($idx_str).log"
            let log_content = [
                $"=== Step ($idx)/($total): ($title) ===",
                $"=== 耗时: ($elapsed) | 退出码: ($result.exit_code) | session: ($session_id) ===",
                "", "--- PROMPT ---", $prompt,
                "", "--- OUTPUT ---", $stdout_text,
                "--- STDERR ---", $result.stderr,
            ] | str join "\n"
            try {
                $log_content | save --force $log_file
            } catch { |e|
                print $"($C_YLW)  ⚠ 日志保存失败 ($log_file): ($e.msg)($C_RST)"
            }
        }
    }

    # ── 还原 settings（无论成功失败都执行）────────────────────────
    if $restore_settings {
        restore_settings $settings_path $backup
        print $"($C_DIM)↩ settings.json 已还原($C_RST)"
    }

    # ── 摘要 ──────────────────────────────────────────────────────
    let fail_count = ($failed_steps | length)
    let ok_count   = $total - $fail_count

    print $"\n($C_BOLD)── 执行完毕 ──($C_RST)"
    print $"  总步骤:  ($total)"
    print $"  成功:    ($C_GRN)($ok_count)($C_RST)"
    if $fail_count > 0 {
        print $"  失败:    ($C_RED)($fail_count) → 步骤 ($failed_steps | str join ', ')($C_RST)"
    }
    if $claudemd {
        print $"  CLAUDE.md: ($C_GRN)已维护($C_RST)"
    }
    if $resume_mode and ($session_id | str length) > 0 {
        print $"  会话 ID:  ($C_DIM)($session_id | safe_truncate 20)...($C_RST)"
        print $"  ($C_DIM)可用 'claude --resume ($session_id)' 手动继续($C_RST)"
    }
    if $checkpoint_ok {
        print $"  检查点:   ($C_GRN)已保存($C_RST) ($C_DIM)（rollback N 可回退）($C_RST)"
    }
    if $log_dir_resolved != "" {
        print $"  日志目录: ($C_CYN)($log_dir_resolved)($C_RST)"
    }

    if $fail_count > 0 { exit 1 }
}

# ── 列出检查点 ────────────────────────────────────────────────────

export def "main list-checkpoints" [] {
    if not (is_git_repo) {
        error make { msg: "当前目录不是 git 仓库" }
    }
    let commits = (
        do { ^git log --format="%H %s" } | complete
    )
    if $commits.exit_code != 0 {
        error make { msg: $"git log 失败: ($commits.stderr | first_line '未知错误')" }
    }
    let checkpoints = (
        $commits.stdout
        | lines
        | where { |l| $l | str contains $CHECKPOINT_PREFIX }
    )
    if ($checkpoints | is-empty) {
        print "暂无检查点记录"
        return
    }
    print $"($C_BOLD)── 工作流检查点 ──($C_RST)"
    for line in $checkpoints {
        let parts = ($line | split row " ")
        let hash  = ($parts | first)
        let msg   = ($parts | skip 1 | str join " " | str replace $CHECKPOINT_PREFIX "" | str trim)
        print $"  ($C_CYN)($hash | safe_truncate 7)($C_RST)  ($msg)"
    }
    print $"\n($C_DIM)回退: nu cc-workflow.nu <file> rollback <step>($C_RST)"
}

# ── 回退到指定步骤执行前 ──────────────────────────────────────────

export def "main rollback" [
    step: int
] {
    if not (is_git_repo) {
        error make { msg: "当前目录不是 git 仓库" }
    }

    let log = (do { ^git log --format="%H %s" } | complete)
    if $log.exit_code != 0 {
        error make { msg: $"git log 失败: ($log.stderr | first_line '未知错误')" }
    }

    let pattern = $"($CHECKPOINT_PREFIX) step-($step):"
    let found = (
        $log.stdout
        | lines
        | where { |l| $l | str contains $pattern }
        | first 1
    )

    if ($found | is-empty) {
        error make { msg: $"找不到 Step ($step) 的检查点，请用 list-checkpoints 查看可用记录" }
    }

    let hash  = ($found | first | split row " " | first)
    let short = ($hash | safe_truncate 7)

    print $"($C_YLW)── 回退到 Step ($step) 执行前 ──($C_RST)"
    print $"  目标 commit: ($C_CYN)($short)($C_RST)"
    print $"($C_RED)  警告：这会丢弃该检查点之后的所有文件变更！($C_RST)"
    print $"  输入 ($C_BOLD)yes($C_RST) 确认，其他任意键取消："

    let confirm = (input "")
    if $confirm != "yes" {
        print "已取消"
        return
    }

    let reset = (do { ^git reset --hard $hash } | complete)
    if $reset.exit_code != 0 {
        error make { msg: $"git reset 失败: ($reset.stderr | first_line '未知错误')" }
    }

    print $"($C_GRN)✔ 已回退到 Step ($step) 执行前（($short)）($C_RST)"
    print $"($C_DIM)  ($short) 之后的 commit 仍在 reflog 中，可用 git reflog 恢复($C_RST)"
}

# ── 解析 Markdown 步骤 ────────────────────────────────────────────

def parse_steps [content: string]: nothing -> list<record> {
    let lines = ($content | lines)
    mut global_ctx: list<string> = []
    mut steps:      list<record> = []
    mut cur_title = ""
    mut cur_body:  list<string> = []
    mut in_step = false
    mut idx = 0

    for line in $lines {
        if ($line | str starts-with "## ") {
            if $in_step {
                $idx   = $idx + 1
                let p  = build_prompt $global_ctx $cur_body
                $steps = ($steps | append { index: $idx, title: $cur_title, prompt: $p })
            }
            $cur_title = ($line | str replace --regex '^##\s+' '')
            $cur_body  = []
            $in_step   = true
        } else if $in_step {
            $cur_body = ($cur_body | append $line)
        } else {
            $global_ctx = ($global_ctx | append $line)
        }
    }

    if $in_step and ($cur_title | str length) > 0 {
        $idx   = $idx + 1
        let p  = build_prompt $global_ctx $cur_body
        $steps = ($steps | append { index: $idx, title: $cur_title, prompt: $p })
    }
    $steps
}

def build_prompt [global_ctx: list<string>, body: list<string>]: nothing -> string {
    let ctx_str  = ($global_ctx | str join "\n" | str trim)
    let body_str = ($body       | str join "\n" | str trim)
    if ($ctx_str | str length) == 0 {
        $body_str
    } else {
        $"# 背景上下文\n($ctx_str)\n\n# 当前任务\n($body_str)"
    }
}
