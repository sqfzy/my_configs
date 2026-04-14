#!/usr/bin/env bash
# autopilot-classifier.sh — 通用事件分类器模板
#
# 用法：bash autopilot-classifier.sh <task-name>
#
# 从 .artifacts/autopilot-state-<task>.json 读取 log_path 和 pid，
# 扫描日志尾部 + 进程状态，输出一个 JSON 事件对象到 stdout：
#
#   {
#     "severity": "ok|warning|error|critical",
#     "category": "running|finished_success|finished_failure|oom|panic|disk_full|network|classifier_failure",
#     "suggested_action": "<matched authorization clause hint>",
#     "evidence": "<log line or ps output that triggered>",
#     "scanned_at": "<ISO-8601>"
#   }
#
# 分类器是确定性的：不调用任何 LLM，不依赖外部网络，不写任何文件。
# 所有判断基于 grep + ps + 退出码 + 磁盘状态。

set -eo pipefail

TASK="${1:?usage: autopilot-classifier.sh <task-name>}"
STATE_FILE=".artifacts/autopilot-state-${TASK}.json"
NOW="$(date -Iseconds)"

if [[ ! -f "$STATE_FILE" ]]; then
  printf '{"severity":"critical","category":"state_missing","suggested_action":"escalate","evidence":"state file %s not found","scanned_at":"%s"}\n' \
    "$STATE_FILE" "$NOW"
  exit 0
fi

LOG_PATH=$(jq -r '.log_path // ""' "$STATE_FILE")
PID=$(jq -r '.pid // ""' "$STATE_FILE")
STATUS=$(jq -r '.status // ""' "$STATE_FILE")

emit() {
  local sev="$1" cat="$2" action="$3" evidence="$4"
  # shellcheck disable=SC2016
  jq -n --arg s "$sev" --arg c "$cat" --arg a "$action" --arg e "$evidence" --arg t "$NOW" \
    '{severity:$s, category:$c, suggested_action:$a, evidence:$e, scanned_at:$t}'
  exit 0
}

# ─── Critical: 红线关键字命中 ──────────────────────────────────
if [[ -f "$LOG_PATH" ]]; then
  if tail -200 "$LOG_PATH" | grep -qE '(FATAL|SEGFAULT|data corruption|irrecoverable)'; then
    evidence=$(tail -200 "$LOG_PATH" | grep -E '(FATAL|SEGFAULT|data corruption|irrecoverable)' | tail -1)
    emit "critical" "fatal_log" "terminate" "$evidence"
  fi
fi

# ─── Error: 进程死亡 ───────────────────────────────────────────
if [[ -n "$PID" && "$PID" != "null" ]]; then
  if ! kill -0 "$PID" 2>/dev/null; then
    # 进程不存在了
    if [[ -f "$LOG_PATH" ]]; then
      # 成功判据命中？
      if tail -50 "$LOG_PATH" | grep -qE '^(DONE|FINISHED|SUCCESS|completed successfully)'; then
        emit "ok" "finished_success" "verify_and_report" "$(tail -50 "$LOG_PATH" | grep -E '^(DONE|FINISHED|SUCCESS)' | tail -1)"
      fi
      # OOM killer？
      if dmesg 2>/dev/null | tail -100 | grep -qE "Out of memory.*$PID"; then
        emit "error" "oom" "restart_with_adjusted_memory" "oom-killer dispatched to pid $PID"
      fi
      # Panic / unhandled exception
      if tail -100 "$LOG_PATH" | grep -qE '(panicked at|Traceback|Unhandled exception|thread .* panicked)'; then
        evidence=$(tail -100 "$LOG_PATH" | grep -E '(panicked|Traceback|Exception|panicked)' | tail -1)
        emit "error" "panic" "restart_if_authorized" "$evidence"
      fi
      # 一般退出
      emit "error" "finished_failure" "classify_exit_code" "process $PID gone, log tail: $(tail -1 "$LOG_PATH" 2>/dev/null || echo '')"
    fi
    emit "error" "process_gone" "restart_if_authorized" "pid $PID not found, no log to inspect"
  fi
fi

# ─── Warning: 磁盘紧张 ────────────────────────────────────────
if command -v df >/dev/null 2>&1; then
  avail_kb=$(df -k . 2>/dev/null | awk 'NR==2 {print $4}')
  if [[ -n "$avail_kb" && "$avail_kb" -lt 1048576 ]]; then  # < 1GB
    emit "warning" "disk_pressure" "cleanup_tmp_if_authorized" "available: ${avail_kb}KB"
  fi
fi

# ─── Warning: 日志中有 ERROR/WARN 但进程还在 ──────────────────
if [[ -f "$LOG_PATH" ]]; then
  recent_errors=$(tail -100 "$LOG_PATH" | grep -cE '(^ERROR|^\[ERROR\]|level=error)' || true)
  if [[ "${recent_errors:-0}" -gt 3 ]]; then
    evidence=$(tail -100 "$LOG_PATH" | grep -E '(^ERROR|level=error)' | tail -1)
    emit "warning" "error_log_cluster" "watch_closely" "$evidence"
  fi
fi

# ─── OK: 进程健康运行 ────────────────────────────────────────
if [[ -n "$PID" && "$PID" != "null" ]] && kill -0 "$PID" 2>/dev/null; then
  last_log_line=""
  if [[ -f "$LOG_PATH" ]]; then
    last_log_line=$(tail -1 "$LOG_PATH" 2>/dev/null | head -c 200)
  fi
  emit "ok" "running" "none" "pid $PID alive; log: $last_log_line"
fi

# ─── Fallback ─────────────────────────────────────────────────
emit "warning" "unknown_state" "watch_closely" "state=$STATUS pid=$PID log=$LOG_PATH"
