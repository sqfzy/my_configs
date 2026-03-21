#!/usr/bin/env nu

# cc-loop.nu — 循环调用 claude code command，每轮新开 context，定时结束
#
# 用法：
#   nu cc-loop.nu "/improve src/parser.rs auto"                       # 跑到收敛
#   nu cc-loop.nu "/improve src/ auto" --until "07:00"                # 跑到明早 7 点
#   nu cc-loop.nu "/improve src/ auto" --duration 2hr                 # 跑 2 小时
#   nu cc-loop.nu "/improve src/ auto" --max-runs 5                   # 最多 5 轮
#   nu cc-loop.nu "/review last 5" --max-runs 1                       # 单次执行（利用新 context）
#   nu cc-loop.nu "/fix run auto" --until "06:30" --cooldown 60
export def main [
    command: string                        # claude code command（如 "/improve src/ auto"）
    --until: string = ""                   # 结束时间，格式 "HH:MM"（若已过则视为明天）
    --duration: string = ""               # 运行时长，格式如 "2hr" "30min" "1hr30min"
    --max-runs: int = 0                    # 最大循环次数，0 = 不限
    --cooldown: int = 30                   # 每轮之间的冷却秒数
    --max-failures: int = 5               # 连续失败多少次后中止，0 = 不限
    --project: string = ""                 # claude code --project 参数
] {
    # ══════════════════════════════════════
    # Pre-flight checks
    # ══════════════════════════════════════

    # 参数互斥
    if ($until | is-not-empty) and ($duration | is-not-empty) {
        error make { msg: "--until 和 --duration 不能同时使用，请只传其中一个" }
    }

    if ($command | str trim | is-empty) {
        error make { msg: "command 不能为空字符串" }
    }

    # --until 格式校验
    if ($until | is-not-empty) {
        let valid = ($until =~ '^\d{1,2}:\d{2}$')
        if not $valid {
            error make { msg: $"--until 格式错误：'($until)'，应为 HH:MM（如 07:00）" }
        }
    }

    # Git 仓库检查
    let git_check = (try { ^git rev-parse --is-inside-work-tree | complete } catch { { stdout: "false", exit_code: 1 } })
    if $git_check.exit_code != 0 or ($git_check.stdout | str trim) != "true" {
        error make { msg: "当前目录不是 git 仓库" }
    }

    # 非 bare 仓库
    let bare_check = (^git rev-parse --is-bare-repository | str trim)
    if $bare_check == "true" {
        error make { msg: "当前是 bare 仓库，无法操作工作区" }
    }

    # claude 二进制可用
    let claude_exists = (try { which claude | length } catch { 0 })
    if $claude_exists == 0 {
        error make { msg: "找不到 claude 命令，请确认 claude code CLI 已安装并在 PATH 中" }
    }

    # 至少有一个 commit（否则 rev-parse HEAD 会失败）
    let has_commits = (try { ^git rev-parse HEAD | complete; true } catch { false })
    if not $has_commits {
        error make { msg: "仓库没有任何提交，请先手动做一次 initial commit" }
    }

    # ══════════════════════════════════════
    # Lock file — 防止并发运行
    # ══════════════════════════════════════

    let log_dir = ".discuss"
    mkdir $log_dir
    let lock_file = $"($log_dir)/cc-loop.lock"

    if ($lock_file | path exists) {
        let stale_pid = (try { open $lock_file | str trim } catch { "" })
        # 检查 PID 是否还活着（/proc 方式，Linux 通用）
        let pid_alive = if ($stale_pid | is-not-empty) {
            ($"/proc/($stale_pid)" | path exists)
        } else {
            false
        }
        if $pid_alive {
            error make { msg: $"另一个 cc-loop 正在运行（PID ($stale_pid)）。若确认已退出，请删除 ($lock_file)" }
        } else {
            print $"(ansi yellow)⚠ 发现残留 lock 文件（PID ($stale_pid) 已不存在），自动清理。(ansi reset)"
        }
    }

    # 写入当前 PID
    let my_pid = ($nu.pid | into string)
    $my_pid | save --force $lock_file

    # ══════════════════════════════════════
    # Idempotent: 确保启动时工作区干净
    # ══════════════════════════════════════

    let dirty_at_start = (^git status --porcelain | str trim)
    if ($dirty_at_start | is-not-empty) {
        let dirty_count = ($dirty_at_start | lines | length)
        print $"(ansi yellow)⚠ 工作区有 ($dirty_count) 个未提交变更（可能来自上次中断的运行）(ansi reset)"
        print $"  自动提交为 checkpoint ..."
        try {
            ^git add -A
            ^git commit -m "chore: checkpoint uncommitted changes from interrupted cc-loop"
            print $"  (ansi green)✓ checkpoint 已提交(ansi reset)"
        } catch { |e|
            print $"  (ansi red)✗ checkpoint 提交失败：($e)(ansi reset)"
            print $"  请手动处理后重新运行"
            rm -f $lock_file
            error make { msg: "启动中止：工作区不干净且无法自动提交" }
        }
    }

    # ══════════════════════════════════════
    # 初始化
    # ══════════════════════════════════════

    let start_time = (date now)
    let cmd_name = ($command | str trim | split row " " | get 0 | str replace --all "/" "")
    let ts = ($start_time | format date '%Y%m%d-%H%M%S')
    let run_log = $"($log_dir)/loop-($cmd_name)-($ts).log"
    let summary_json = $"($log_dir)/loop-($cmd_name)-($ts).json"

    let deadline = (resolve-deadline $until $duration)

    # ── 打印 & 记录启动信息 ──

    let sep = "════════════════════════════════════════════"
    let initial_hash = (^git rev-parse HEAD | str trim)
    let branch = (^git branch --show-current | str trim)

    let header_lines = [
        $sep
        "  cc-loop"
        $sep
        $"  命令：($command)"
        $"  分支：($branch)"
        $"  起始 commit：($initial_hash | str substring 0..8)"
        $"  开始：($start_time | format date '%Y-%m-%d %H:%M:%S')"
        (if $deadline != null {
            $"  截止：($deadline | format date '%Y-%m-%d %H:%M:%S')"
        } else if $max_runs > 0 {
            $"  截止：最多 ($max_runs) 轮"
        } else {
            "  截止：收敛为止"
        })
        $"  冷却：($cooldown) 秒/轮"
        (if $max_failures > 0 { $"  最大连续失败：($max_failures) 次" } else { null })
        (if ($project | is-not-empty) { $"  项目：($project)" } else { null })
        $"  日志：($run_log)"
        $sep
    ] | compact | str join "\n"

    print $"(ansi attr_bold)($header_lines)(ansi reset)\n"
    $"($header_lines)\n\n" | save --force $run_log

    # 记录循环开始前已有的报告，避免误读旧报告导致提前收敛
    let report_pattern = $"($log_dir)/($cmd_name)-*.md"
    let existing_reports = (try { glob $report_pattern | sort } catch { [] })

    # ══════════════════════════════════════
    # 主循环
    # ══════════════════════════════════════

    mut run_count = 0
    mut converged = false
    mut consecutive_no_change = 0
    mut consecutive_failures = 0
    mut termination_reason = "unknown"
    mut round_records = []
    mut current_cooldown = $cooldown           # 动态冷却，收敛时加倍
    mut convergence_hits = 0                   # 累计触发收敛信号次数（可观测性）
    let has_deadline = ($deadline != null)

    loop {
        $run_count = $run_count + 1

        # ── 终止条件检查 ──
        if $deadline != null and (date now) >= $deadline {
            print $"\n(ansi yellow)⏰ 已到截止时间，停止。(ansi reset)"
            $termination_reason = "deadline"
            break
        }

        if $max_runs > 0 and $run_count > $max_runs {
            print $"\n(ansi yellow)🔢 已达最大轮数 ($max_runs)，停止。(ansi reset)"
            $termination_reason = "max_runs"
            break
        }

        # ── 本轮初始状态 ──
        let before_hash = (^git rev-parse HEAD | str trim)
        let round_start = (date now)
        let round_ts = ($round_start | format date '%Y-%m-%d %H:%M:%S')

        print $"\n(ansi blue)▶(ansi reset)  (ansi attr_bold)第 ($run_count) 轮(ansi reset) — ($round_ts)"

        # 结构化日志 — 轮次开始
        let round_header = [
            ""
            $"══ Round ($run_count) ══════════════════════════════════"
            $"  started:     ($round_ts)"
            $"  before_hash: ($before_hash)"
        ] | str join "\n"
        $"($round_header)\n" | save --append $run_log

        # ── 执行 claude command ──
        let claude_args = if ($project | is-not-empty) {
            ["--project", $project, "-p", $command]
        } else {
            ["-p", $command]
        }

        let claude_ok = (try {
            let result = (^claude ...$claude_args | complete)
            # 原始输出附加到日志（带标记便于解析）
            $"[STDOUT]\n($result.stdout)\n" | save --append $run_log
            if ($result.stderr | str trim | is-not-empty) {
                $"[STDERR]\n($result.stderr)\n" | save --append $run_log
            }
            if $result.exit_code != 0 {
                print $"  (ansi yellow)⚠ claude 退出码 ($result.exit_code)(ansi reset)"
                $"[EXIT_CODE] ($result.exit_code)\n" | save --append $run_log
            }
            true
        } catch { |e|
            print $"  (ansi red)✗ claude 执行失败：($e)(ansi reset)"
            $"[ERROR] ($e)\n" | save --append $run_log
            false
        })

        if not $claude_ok {
            $consecutive_failures = $consecutive_failures + 1
            let round_dur = ((date now) - $round_start)
            print $"  连续失败次数：($consecutive_failures)"
            $"  status: FAILED (consecutive: ($consecutive_failures))\n  duration: ($round_dur)\n" | save --append $run_log

            # 记录本轮
            $round_records = ($round_records | append {
                round: $run_count
                status: "failed"
                before_hash: $before_hash
                after_hash: $before_hash
                commits: 0
                duration_sec: (($round_dur / 1sec) | math round)
                diff_stat: "n/a"
            })

            if $max_failures > 0 and $consecutive_failures >= $max_failures {
                print $"\n(ansi red)💥 连续失败 ($consecutive_failures) 次，中止。(ansi reset)"
                $termination_reason = "max_failures"
                break
            }
            print $"  等待 ($cooldown) 秒后重试..."
            sleep ($cooldown * 1sec)
            continue
        }

        # 执行成功，重置连续失败计数
        $consecutive_failures = 0

        # ── 自动提交所有变更（两级 fallback 保证幂等） ──
        commit-changes $project $run_log $run_count

        let round_duration = ((date now) - $round_start)
        print $"  耗时：($round_duration)"

        # ── 检查是否有实际改动 ──
        let after_hash = (^git rev-parse HEAD | str trim)
        let round_commits = if $after_hash == $before_hash {
            0
        } else {
            ^git log --oneline $"($before_hash)..($after_hash)" | lines | length
        }

        # Diff 统计（可观测性）
        let diff_stat = if $after_hash != $before_hash {
            ^git diff --stat $"($before_hash)..($after_hash)" | lines | last | str trim
        } else {
            "no changes"
        }

        if $round_commits == 0 {
            $consecutive_no_change = $consecutive_no_change + 1
            print $"  (ansi cyan)ℹ 本轮无代码改动（连续 ($consecutive_no_change) 轮）(ansi reset)"
        } else {
            $consecutive_no_change = 0
            $current_cooldown = $cooldown      # 有改动 → 重置冷却到基准值
            print $"  (ansi green)✓ ($round_commits) 个新提交(ansi reset)"
            print $"  (ansi attr_dimmed)($diff_stat)(ansi reset)"
        }

        # 结构化日志 — 轮次结束
        let round_footer = [
            $"  after_hash:  ($after_hash)"
            $"  commits:     ($round_commits)"
            $"  diff_stat:   ($diff_stat)"
            $"  duration:    ($round_duration)"
            $"  status:      OK"
            $"  no_change_streak: ($consecutive_no_change)"
        ] | str join "\n"
        $"($round_footer)\n" | save --append $run_log

        # 记录本轮结构化数据
        $round_records = ($round_records | append {
            round: $run_count
            status: "ok"
            before_hash: $before_hash
            after_hash: $after_hash
            commits: $round_commits
            duration_sec: (($round_duration / 1sec) | math round)
            diff_stat: $diff_stat
        })

        # ── 收敛判断：连续 3 轮无改动 ──
        if $consecutive_no_change >= 3 {
            $convergence_hits = $convergence_hits + 1
            if $has_deadline {
                # 有截止时间 → 不终止，加倍冷却继续（模型可能幻觉收敛）
                $current_cooldown = $current_cooldown * 2
                print $"\n(ansi cyan)🔄 连续 3 轮无改动（疑似收敛 #($convergence_hits)），但有截止时间，继续执行（冷却 → ($current_cooldown)s）(ansi reset)"
                $"  [CONVERGENCE] no_change streak=($consecutive_no_change), hit #($convergence_hits), cooldown→($current_cooldown)s, continuing -- has deadline\n" | save --append $run_log
                $consecutive_no_change = 0   # 重置计数，让下一个周期重新判断
            } else {
                print $"\n(ansi green)✅ 连续 3 轮无改动，判定为收敛。(ansi reset)"
                $converged = true
                $termination_reason = "converged_no_change"
                break
            }
        }

        # ── 检查报告中的收敛标记（只看本次循环新生成的报告）──
        let all_reports = (try { glob $report_pattern | sort } catch { [] })
        let new_reports = ($all_reports | where { |r| not ($existing_reports | any { |e| $e == $r }) })
        let report_converged = ($new_reports | any { |r|
            let content = (try { open $r } catch { "" })
            ($content | str contains "终止原因：收敛") or ($content | str contains "termination: converged")
        })
        if $report_converged {
            $convergence_hits = $convergence_hits + 1
            if $has_deadline {
                $current_cooldown = $current_cooldown * 2
                print $"\n(ansi cyan)🔄 报告标记收敛（疑似收敛 #($convergence_hits)），但有截止时间，继续执行（冷却 → ($current_cooldown)s）(ansi reset)"
                $"  [CONVERGENCE] report_signal, hit #($convergence_hits), cooldown→($current_cooldown)s, continuing -- has deadline\n" | save --append $run_log
            } else {
                print $"\n(ansi green)✅ 报告标记收敛，停止。(ansi reset)"
                $converged = true
                $termination_reason = "converged_report"
                break
            }
        }

        # ── 冷却（再次检查 deadline 避免空等） ──
        if $deadline != null and (date now) >= $deadline {
            print $"\n(ansi yellow)⏰ 已到截止时间，停止。(ansi reset)"
            $termination_reason = "deadline"
            break
        }
        print $"  冷却 ($current_cooldown) 秒..."
        sleep ($current_cooldown * 1sec)
    }

    # ══════════════════════════════════════
    # 汇总 & 清理
    # ══════════════════════════════════════

    let total_duration = ((date now) - $start_time)
    let current_hash = (^git rev-parse HEAD | str trim)
    let total_commits = if $initial_hash == $current_hash {
        0
    } else {
        ^git log --oneline $"($initial_hash)..HEAD" | lines | length
    }

    let final_diff_stat = if $initial_hash != $current_hash {
        ^git diff --stat $"($initial_hash)..HEAD" | lines | last | str trim
    } else {
        "no changes"
    }

    # 最终轮数（max_runs 边界修正：break 前 run_count 已 +1）
    let effective_rounds = if $termination_reason == "max_runs" {
        $max_runs
    } else {
        $run_count
    }

    let converged_str = if $converged { "✅ 是" } else { "❌ 否" }

    # 终端输出
    let footer_lines = [
        ""
        $sep
        "  完成"
        $sep
        $"  命令：($command)"
        $"  分支：($branch)"
        $"  总耗时：($total_duration)"
        $"  执行轮数：($effective_rounds)"
        $"  总提交数：($total_commits)"
        $"  变更统计：($final_diff_stat)"
        $"  收敛：($converged_str)"
        $"  收敛信号触发次数：($convergence_hits)"
        $"  终止原因：($termination_reason)"
        $"  commit 范围：($initial_hash | str substring 0..8)..($current_hash | str substring 0..8)"
        $"  日志：($run_log)"
        $"  摘要：($summary_json)"
        $sep
    ] | str join "\n"

    print $"(ansi attr_bold)($footer_lines)(ansi reset)"

    # 写入结构化文本日志
    $"($footer_lines)\n" | save --append $run_log

    # 写入 JSON 摘要（供外部工具消费）
    let summary_data = {
        command: $command
        branch: $branch
        project: $project
        initial_hash: $initial_hash
        final_hash: $current_hash
        start_time: ($start_time | format date '%Y-%m-%dT%H:%M:%S%z')
        end_time: (date now | format date '%Y-%m-%dT%H:%M:%S%z')
        duration_sec: (($total_duration / 1sec) | math round)
        rounds: $effective_rounds
        total_commits: $total_commits
        converged: $converged
        convergence_hits: $convergence_hits
        termination_reason: $termination_reason
        diff_stat: $final_diff_stat
        round_details: $round_records
    }
    $summary_data | to json --indent 2 | save --force $summary_json

    # 清理 lock 文件
    rm -f $lock_file
}

# ══════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════

# 自动提交变更，两级 fallback 保证工作区在每轮结束时干净：
#   Level 1: claude /git all auto（生成 Conventional Commits message）
#   Level 2: 直接 git add -A && git commit（兜底，确保幂等）
def commit-changes [project: string, run_log: string, round: int] {
    let dirty = (^git status --porcelain | str trim)
    if ($dirty | is-empty) { return }

    let dirty_count = ($dirty | lines | length)
    print $"  (ansi blue)📦 ($dirty_count) 个文件待提交(ansi reset)"
    $"  [COMMIT] ($dirty_count) dirty files\n" | save --append $run_log

    # Level 1: claude /git all auto
    print $"  尝试 /git all auto ..."
    let git_args = if ($project | is-not-empty) {
        ["--project", $project, "-p", "/git all auto"]
    } else {
        ["-p", "/git all auto"]
    }

    let level1_ok = (try {
        let r = (^claude ...$git_args | complete)
        $"[GIT-L1 STDOUT]\n($r.stdout)\n" | save --append $run_log
        if $r.exit_code != 0 {
            $"[GIT-L1 STDERR]\n($r.stderr)\n" | save --append $run_log
            false
        } else {
            true
        }
    } catch { |e|
        $"[GIT-L1 ERROR] ($e)\n" | save --append $run_log
        false
    })

    # 验证 Level 1 是否真的提交了（claude 可能成功退出但没实际 commit）
    let still_dirty = (^git status --porcelain | str trim | is-not-empty)

    if $level1_ok and (not $still_dirty) {
        print $"  (ansi green)✓ /git 提交成功(ansi reset)"
        $"  [COMMIT] level1 OK\n" | save --append $run_log
        return
    }

    # Level 2: 直接 git commit 兜底
    if $still_dirty {
        print $"  (ansi yellow)⚠ /git 未完成提交，fallback 到直接 git commit(ansi reset)"
        $"  [COMMIT] level1 incomplete, falling back to level2\n" | save --append $run_log
    } else {
        # level1 失败但没有脏文件（可能 /improve 自己提交了）
        print $"  (ansi green)✓ 变更已提交(ansi reset)"
        $"  [COMMIT] clean -- committed externally\n" | save --append $run_log
        return
    }

    try {
        ^git add -A
        ^git commit -m $"chore: auto-commit changes from cc-loop round ($round)"
        print $"  (ansi green)✓ fallback 提交成功(ansi reset)"
        $"  [COMMIT] level2 OK\n" | save --append $run_log
    } catch { |e|
        print $"  (ansi red)✗ fallback 提交也失败：($e)(ansi reset)"
        print $"  (ansi red)  ⚠ 工作区仍有未提交变更，后续轮次结果可能受影响(ansi reset)"
        $"  [COMMIT] level2 FAILED: ($e)\n" | save --append $run_log
    }
}

# 解析 --until 和 --duration 为截止时间
def resolve-deadline [until: string, duration: string] {
    if ($until | is-not-empty) {
        let now = (date now)
        let today_str = ($now | format date '%Y-%m-%d')
        let tz_offset = ($now | format date '%z')  # 例如 +0800
        let target = ($"($today_str) ($until):00 ($tz_offset)" | into datetime)
        if $target <= $now {
            $target + 1day
        } else {
            $target
        }
    } else if ($duration | is-not-empty) {
        let dur = ($duration | into duration)
        (date now) + $dur
    } else {
        null
    }
}
