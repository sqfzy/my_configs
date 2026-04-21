## Target：wizard（交互式向导 / 配置助手）

**适用**：需要和用户对话引导完成某事的脚本。典型例子：项目脚手架生成器、配置初始化、注册流程、诊断向导、数据导入助手。

**与普通脚本的核心差异**：wizard 的**用户体验就是其生产级**——问得不清、回答没容错、中途退出数据丢失，都是 wizard 的严重 bug。

---

### 独有的必执行章节

#### 1. 欢迎信息 + 流程预告

第一屏告诉用户：
- 这个向导会做什么（一句话）
- 大约需要多久（"~2 分钟" / "5-10 问题"）
- 能否中途退出（Ctrl+C 行为）
- 能否稍后修改（所有选择是否可逆）

```
Welcome to <project> setup wizard.
This will guide you through 7 questions (~2 minutes)
to create your initial config at ~/.myapp/config.toml.

Press Ctrl+C at any time to cancel (nothing will be saved).
```

#### 2. 问题设计规范

每个问题必须包含：
- **清晰的问题**（避免术语，给非专家看）
- **默认值**（方括号展示，直接回车采用）
- **可选值**（若是枚举，列出所有）
- **帮助**（`?` 触发详细说明）
- **校验**（格式 / 范围 / 存在性，失败重问）

```
[3/7] Which database backend? [postgres]
      Options: postgres, sqlite, mysql
      Type ? for help, or press Enter to accept default.
>
```

#### 3. 输入校验 & 容错

- 格式错误 → 友好错误消息 + 重新问同一题（不把用户踢回头）
- 范围错 → 说明合法范围并重问
- 空输入 → 如有默认值使用默认；否则重问
- `?` → 显示帮助后重问
- 无效选项 → 列出合法选项 + 重问

**原则**：任何一题允许无限次重试。不能因为 3 次错就 exit（用户会哭）。

#### 4. 进度指示

每次问题显示 `[N/M]`，让用户知道还剩多少。

若过程有分支（某些答案会跳过某些问题），动态调整 M，但保持单调递增：

```
[1/5] ...
[2/5] ...
[3/5] ... （用户选了 sqlite，跳过 3 个后续题）
[4/5] ... （现在总数变 5）
```

#### 5. 最终确认

收集完所有答案后，**摘要展示 + 用户确认**，再真正写入：

```
Summary of your choices:

  Project name : myapp
  Backend      : postgres
  Port         : 8080
  Path         : ~/.myapp/

This will create:
  ~/.myapp/config.toml
  ~/.myapp/data/
  ~/.myapp/logs/

Proceed? [Y/n]
```

用户有最后一次反悔机会。

#### 6. 中途退出处理

捕获 SIGINT（Ctrl+C）：
- 显示"已取消，未做任何改动"
- 不留任何临时文件（`trap 'rm -f "$TMP"; exit 130' INT`）
- 退出码 130（SIGINT 标准）

#### 7. 答案持久化与断点续传（可选但推荐）

长向导（> 10 问题）应支持：
- 每回答一题持久化到 `.wizard-state.json`
- 重跑时检测到状态文件 → 问"从上次继续还是重新开始"
- 完成后清理状态文件

---

### 独有的维度权重

| 维度 | 权重 | 原因 |
|------|------|------|
| 输入校验 | **极高** | wizard 核心就是引导用户输对 |
| 用户引导 | **极高** | 问题必须清楚、有默认、可帮助 |
| 错误消息 | **极高** | 失败消息是 wizard 的"用户教程" |
| 进度 | **高** | 让用户知道还剩多少 |
| 中断清理 | **高** | Ctrl+C 不能留残骸 |
| 幂等 | **中** | 通常 wizard 只跑一次，但重跑不应崩 |

---

### 独有的 ASCII 图示要求

- **流程图**：展示向导的分支结构（"若选 A 则跳过 3、4 题"）
- **决策树**（若分支复杂）：在 `--help` 中展示

---

### 独有的反模式

- ❌ 一次性问完所有问题（像表单）—— 失去引导价值
- ❌ 问题不清晰（"Enter config?" —— 什么 config？什么格式？）
- ❌ 没有默认值 —— 用户不知道填什么
- ❌ 没有 `?` 帮助选项
- ❌ 输错一次就退出
- ❌ 没有最终确认就写入
- ❌ Ctrl+C 留下一半文件 / 临时目录
- ❌ 用 `read -s` 收敏感信息却不加确认（回车收到错密码）
- ❌ 非交互环境（CI / pipe）不工作（应检测 `[[ -t 0 ]]` 并提示或支持 `--non-interactive`）
- ❌ 问题顺序不合理（问完数据库类型才问项目名）

---

### wizard 脚本骨架模板

```bash
#!/usr/bin/env bash
# Interactive wizard for <project>
# Usage: ./wizard.sh [--non-interactive] [--resume]

set -euo pipefail

readonly STATE_FILE=".wizard-state"
readonly TOTAL_STEPS=7

# ───────────────────────── 工具 ─────────────────────────
ask() {
  local prompt="$1" default="${2:-}" validator="${3:-}"
  local answer
  while true; do
    if [[ -n "$default" ]]; then
      read -rp "$prompt [$default] > " answer
      answer="${answer:-$default}"
    else
      read -rp "$prompt > " answer
    fi

    [[ "$answer" == "?" ]] && { print_help; continue; }

    if [[ -n "$validator" ]] && ! $validator "$answer"; then
      echo "Invalid input. Try again."
      continue
    fi

    echo "$answer"
    return 0
  done
}

# ───────────────────────── 中断 ─────────────────────────
cleanup() {
  echo
  echo "Cancelled. No changes made."
  rm -f "$STATE_FILE.tmp"
  exit 130
}
trap cleanup INT TERM

# ───────────────────────── 主流程 ────────────────────────
welcome() {
  cat <<EOF
╔══════════════════════════════════════════╗
║  Welcome to <project> setup wizard       ║
║  ~2 minutes · $TOTAL_STEPS questions · Ctrl+C to cancel ║
╚══════════════════════════════════════════╝

EOF
}

main() {
  welcome

  # [1/7] 项目名
  name=$(ask "Project name" "myapp" validate_name)
  echo
  # [2/7] ...
  # ...

  # 最终确认
  cat <<EOF

Summary:
  Project : $name
  Backend : $backend
  ...

This will create:
  ~/.myapp/config.toml

EOF
  read -rp "Proceed? [Y/n] > " confirm
  [[ "${confirm,,}" =~ ^(y|yes|)$ ]] || { echo "Aborted."; exit 0; }

  # 真正执行
  write_config
  echo "✓ Done."
}

main "$@"
```
