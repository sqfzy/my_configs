#!/usr/bin/env nu
# cc-workflow.nu — Claude Code 工作流执行器
#
# 用法:
#   nu cc-workflow.nu workflow.md
#   nu cc-workflow.nu workflow.md --dry-run
#   nu cc-workflow.nu workflow.md --restore-settings
#   nu cc-workflow.nu workflow.md --log-dir ./logs
#   nu cc-workflow.nu workflow.md --settings-scope user
#
# 工作流文件格式 (Markdown):
#   ## Step 1: 任意标题
#   这里写给 Claude 的提示词，可以多行。
#
#   ## Step 2: 另一个任务
#   继续写提示词...
#
#   任意 ## 二级标题都被视为一个步骤。
#   一级标题 (#) 和其他内容作为全局上下文，附加到每个步骤前。

# ANSI 颜色常量——在插值外赋值，避免 "Unknown ansi code" 错误
const C_RST  = "\e[0m"
const C_BOLD = "\e[1m"
const C_DIM  = "\e[2m"
const C_GRN  = "\e[32m"
const C_YLW  = "\e[33m"
const C_CYN  = "\e[36m"
const C_RED  = "\e[31m"

export def main [
    workflow_file: path                          # 工作流文件路径 (.md)
    --dry-run (-n)                               # 只打印步骤，不执行
    --restore-settings (-r)                      # 执行完毕后还原 settings.json
    --log-dir (-l): string = ""                  # 保存每步输出的目录（默认不保存）
    --settings-scope (-s): string = "project"    # project | user
] {
    # ── 检查依赖 ──────────────────────────────────────────────────
    if not (which claude | is-not-empty) {
        error make { msg: "找不到 claude 命令，请先安装 Claude Code: npm i -g @anthropic-ai/claude-code" }
    }

    let wf_path = ($workflow_file | path expand)
    if not ($wf_path | path exists) {
        error make { msg: $"工作流文件不存在: ($wf_path)" }
    }

    # ── 解析工作流文件 ─────────────────────────────────────────────
    let raw   = open $wf_path --raw
    let steps = parse_steps $raw

    if ($steps | is-empty) {
        error make { msg: "未解析到任何步骤。请确保工作流文件中有 '## ' 开头的二级标题。" }
    }

    let n = ($steps | length)
    print $"($C_GRN)✔($C_RST) 已解析 ($C_BOLD)($n)($C_RST) 个步骤，来自: ($C_CYN)($wf_path)($C_RST)"

    # ── Dry-run 预览 ───────────────────────────────────────────────
    if $dry_run {
        print $"\n($C_YLW)── DRY RUN 模式，仅预览步骤 ──($C_RST)"
        for step in $steps {
            print $"\n($C_BOLD)[Step ($step.index)] ($step.title)($C_RST)"
            print $"($C_DIM)($step.prompt | str trim)($C_RST)"
        }
        print $"\n($C_YLW)── 共 ($n) 步，dry-run 结束 ──($C_RST)"
        return
    }

    # ── 配置 settings.json ────────────────────────────────────────
    let settings_path = if $settings_scope == "user" {
        $"($env.HOME)/.claude/settings.json"
    } else {
        ".claude/settings.json"
    }

    let backup = setup_settings $settings_path

    # ── 日志目录 ──────────────────────────────────────────────────
    let log_dir_resolved = if $log_dir != "" {
        let d = ($log_dir | path expand)
        mkdir $d
        $d
    } else {
        ""
    }

    # ── 执行循环 ──────────────────────────────────────────────────
    print ""
    let total = ($steps | length)
    mut failed_steps: list<int> = []

    for step in $steps {
        let idx        = $step.index
        let title      = $step.title
        let prompt     = ($step.prompt | str trim)
        let first_line = ($prompt | lines | first)

        print $"($C_CYN)┌─ Step ($idx)/($total): ($title)($C_RST)"
        print $"($C_DIM)│ ($first_line)($C_RST)"
        print $"($C_CYN)└─ 执行中...($C_RST)"

        let t_start = (date now)
        let result  = (do { ^claude -p $prompt } | complete)
        let t_end   = (date now)

        let elapsed_ms  = (($t_end - $t_start) | into int) / 1_000_000
        let elapsed_sec = $elapsed_ms / 1000
        let elapsed_dec = ($elapsed_ms mod 1000) / 10
        let elapsed     = $"($elapsed_sec).($elapsed_dec)s"

        if $result.exit_code == 0 {
            print $"($C_GRN)✔ Step ($idx) 完成 [($C_DIM)($elapsed)($C_RST)($C_GRN)]($C_RST)\n"
        } else {
            let stderr_short = ($result.stderr | str trim)
            print $"($C_RED)✘ Step ($idx) 失败 (exit ($result.exit_code)) [($elapsed)]($C_RST)"
            print $"($C_RED)  stderr: ($stderr_short)($C_RST)\n"
            $failed_steps = ($failed_steps | append $idx)
        }

        # 保存日志
        if $log_dir_resolved != "" {
            let idx_str  = if $idx < 10 { $"0($idx)" } else { $"($idx)" }
            let log_file = $"($log_dir_resolved)/step_($idx_str).log"
            [
                $"=== Step ($idx)/($total): ($title) ===",
                $"=== 耗时: ($elapsed) | 退出码: ($result.exit_code) ===",
                "",
                "--- PROMPT ---",
                $prompt,
                "",
                "--- STDOUT ---",
                $result.stdout,
                "--- STDERR ---",
                $result.stderr,
            ] | str join "\n" | save --force $log_file
        }
    }

    # ── 还原 settings.json ────────────────────────────────────────
    if $restore_settings {
        restore_settings $settings_path $backup
        print $"($C_DIM)↩ settings.json 已还原($C_RST)"
    }

    # ── 最终摘要 ──────────────────────────────────────────────────
    let ok_count   = $total - ($failed_steps | length)
    let fail_count = ($failed_steps | length)

    print $"\n($C_BOLD)── 执行完毕 ──($C_RST)"
    print $"  总步骤:  ($total)"
    print $"  成功:    ($C_GRN)($ok_count)($C_RST)"
    if $fail_count > 0 {
        let fail_list = ($failed_steps | str join ", ")
        print $"  失败:    ($C_RED)($fail_count) → 步骤 ($fail_list)($C_RST)"
    }
    if $log_dir_resolved != "" {
        print $"  日志目录: ($C_CYN)($log_dir_resolved)($C_RST)"
    }

    if $fail_count > 0 {
        exit 1
    }
}

# ── 解析 Markdown 步骤 ────────────────────────────────────────────
# 规则：
#   - ## 开头的行 → 新步骤标题
#   - 步骤之前的所有内容 → 全局上下文（附加到每步提示词前）
#   - 步骤正文 = 该 ## 标题到下一个 ## 之间的文本
def parse_steps [content: string] {
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

    # 保存最后一步
    if $in_step and ($cur_title | str length) > 0 {
        $idx   = $idx + 1
        let p  = build_prompt $global_ctx $cur_body
        $steps = ($steps | append { index: $idx, title: $cur_title, prompt: $p })
    }

    $steps
}

# 合并全局上下文与步骤正文
def build_prompt [global_ctx: list<string>, body: list<string>] {
    let ctx_str  = ($global_ctx | str join "\n" | str trim)
    let body_str = ($body      | str join "\n" | str trim)

    if ($ctx_str | str length) == 0 {
        $body_str
    } else {
        $"# 背景上下文\n($ctx_str)\n\n# 当前任务\n($body_str)"
    }
}

# ── 写入无限制 settings.json ──────────────────────────────────────
def setup_settings [settings_path: string] {
    let dir = ($settings_path | path dirname)
    if not ($dir | path exists) {
        mkdir $dir
    }

    let backup = if ($settings_path | path exists) {
        let b = $"($settings_path).bak"
        cp $settings_path $b
        print $"($C_DIM)↳ 已备份原 settings.json → ($b)($C_RST)"
        $b
    } else {
        ""
    }

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

    $settings | to json | save --force $settings_path
    print $"($C_DIM)↳ 已写入无限制 settings.json → ($settings_path)($C_RST)"

    $backup
}

# ── 还原 settings.json ────────────────────────────────────────────
def restore_settings [settings_path: string, backup: string] {
    if ($backup | str length) > 0 and ($backup | path exists) {
        mv --force $backup $settings_path
    } else if ($settings_path | path exists) {
        rm $settings_path
    }
}
