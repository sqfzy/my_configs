---
name: script
description: "生成生产级、可观察、幂等的独立脚本：一次性任务、部署、运维、数据管道、git hook、交互向导等。默认遵守 8 条生产级原则（错误处理 / 日志 / 幂等 / dry-run / 输入校验 / 路径安全 / 确认环节 / 进度提示）；按议题特征动态调整维度权重；必要时读取 targets/<name>.md 加载特殊目标的独有约束（setup / wizard / pipeline）。生成后自动语法检查 + dry-run 验证。--auto 全自动无需批准。TRIGGER when: 用户要创建 / 生成一个独立脚本、自动化、部署脚本、setup 向导、运维工具、batch 处理、git hook、一次性任务。DO NOT TRIGGER when: 用户在写应用代码中顺便用了 shell 命令、一行终端命令（直接执行即可）、需要用 /blueprint 规划的大型工程任务。"
argument-hint: "<脚本用途描述> [--auto] [--lang <bash|python|ruby|nu|...>] [--path <输出路径>]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(git:*), Bash(ls:*), Bash(which:*), Bash(uname:*), Bash(bash:*), Bash(python:*), Bash(python3:*), Bash(ruby:*), Bash(nu:*), Bash(shellcheck:*)
---

# /script

ASCII 可视化原则：!`cat ~/.claude/skills/new_skills/shared/ascii-viz.md`

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`

目的：$ARGUMENTS

---

## 定位

`/script` 生成**独立、生产级、可观察、幂等的脚本**。适用于所有"单文件可执行程序"的场景：自动化任务、部署 / setup、运维工具、数据处理管道、git hook、交互式向导、CI 小工具。

**核心价值**：AI 替你写出**能直接上线运行**的脚本，不是"demo 能跑但一上生产就挂"。

---

## 核心：8 条生产级原则（铁律）

任何脚本都必须满足这 8 条，不允许"简单脚本不用管"的偷懒：

### 1. 错误处理不容沉默

- **Shell**：脚本开头 `set -euo pipefail`（或等价）。任何外部命令失败必须被捕获或显式 `|| die` / `|| true`（后者需写明为何可以忽略）
- **Python**：不允许 `except: pass`；所有 I/O / subprocess 都要处理错误
- **Ruby / Nushell 等**：同等要求
- 任何 `exit` / `return` 非零路径必须打印**可操作**的错误消息（告诉用户"是什么挂了 + 下一步该做什么"）

### 2. 日志可观察

- 脚本开始：打印"开始做什么 + 关键参数"
- 关键步骤之间：打印进展（"Step 2/5: xxx"）
- 每个外部调用 / I/O：必要时 log（至少错误路径）
- 结束：打印"完成 + 做了什么 / 改了什么"
- 支持 verbose 级别（默认简洁 / `-v` 详细）
- 日志输出到 stderr 或 log 文件，不污染 stdout（stdout 留给机器可读输出）

### 3. 幂等执行

- 脚本重跑多次结果一致，不允许"第一次创建资源，第二次报错"
- 创建前检查存在（`mkdir -p` / `CREATE TABLE IF NOT EXISTS` / `idempotent` 模式）
- 删除前检查目标存在 + 引用关系
- 写入前（若破坏性）先备份（`file.bak-YYYYMMDD-HHMMSS`）

### 4. Dry-run 模式（破坏性操作必须）

- 任何会**创建 / 删除 / 修改**文件、数据库、远程资源的脚本必须支持 `--dry-run`
- Dry-run 模式：打印"若真实运行会做什么"，不真实执行
- 默认不进入 dry-run，用户显式指定才激活（避免"我以为在做，结果没做"）

### 5. 输入校验

- 所有用户输入（参数、环境变量、配置文件、stdin）必须校验：
  - 类型（数字 / 字符串 / 路径 / URL）
  - 范围（正数 / 非空 / 长度限制）
  - 格式（正则 / 枚举）
- 校验失败 → 清晰错误消息 + 退出，不带着脏数据继续
- 缺失必需参数时显示 `usage` / `--help` 引导

### 6. 路径与命令安全

- 处理路径 / 文件名时 **canonicalize + 白名单检查**，防路径穿越
- Subprocess / exec 用**参数数组**，不用字符串拼接（防命令注入）
- 敏感信息（密码、token）不出现在 `ps`、日志、错误消息
- 临时文件用 `mktemp` 风格，权限 600，用完删除

### 7. 确认环节（破坏性操作）

- 任何**删除 / 覆写 / 远程推送 / 费钱操作** 默认**需要用户确认**：
  - `This will delete N files under /path/to/X. Continue? [y/N]`
- `--yes` / `--force` / `--auto` 可跳过确认
- 确认消息要包含**具体影响**：多少文件、哪个目录、什么资源

### 8. 进度 / 超时 / 取消

- 长时间操作（> 3 秒）必须有进度提示（百分比 / 进度条 / "M / N"）
- 网络 / subprocess 调用必须有超时
- 支持 `Ctrl+C` 优雅中断，清理临时资源
- 不允许"程序卡住用户不知道发生什么"

---

## 维度权重（按议题动态调整）

上述 8 条是**底线**。不同目标的脚本对某些维度权重更高：

| 议题特征 | 高权重维度 |
|---------|-----------|
| 一次性清理 / 批处理 | 幂等 / dry-run / 确认 |
| 部署 / setup | 错误恢复 / 回滚 / 幂等 / 日志 |
| 运维诊断 | 日志 / 输出可读 / 退出码语义 |
| 数据处理管道 | dry-run / 幂等 / 进度 / 失败重试 |
| Git hook / CI 小工具 | 快速失败 / 退出码 / 静默成功 |
| 交互式向导 | 输入校验 / 用户引导 / 错误消息 |

**自主判断议题类型**，动态调整每条原则的展开深度。

若议题明确匹配特殊目标（setup / wizard / pipeline），读取对应 target 文件获取额外约束：

```
目标 setup     → Read ~/.claude/skills/new_skills/script/targets/setup.md
目标 wizard    → Read ~/.claude/skills/new_skills/script/targets/wizard.md
目标 pipeline  → Read ~/.claude/skills/new_skills/script/targets/pipeline.md
```

其他目标（一次性 task、ops、hook）由本 SKILL.md 的通用原则覆盖，不额外 Read。

---

## 语言选择

**原则：沿用项目 / 用户语境，不主动换语言**。

| 输入 | 选择 |
|------|------|
| 用户显式指定（`--lang bash` / "用 python"） | 用户指定 |
| 项目是 Rust / Python / TS / Go | 对应生态的脚本语言（或项目已用的 shell） |
| 用户在 nushell / zsh / fish 环境 | 对应 shell（注意 POSIX 兼容性） |
| OS：Linux / macOS + 简单任务 | bash（必要时 sh） |
| 复杂数据处理 / 跨平台 | python |
| 无法推断 | bash（兜底） |

若用户未明说但议题复杂度超出 shell 能力（循环嵌套 / 结构化数据 / 错误处理密集）→ 警告 + 推荐切换 python。

---

## 参数

```
/script <脚本用途描述>
  [--lang <bash|python|ruby|nu|zsh|fish|...>]   显式指定语言
  [--path <输出路径>]                            显式指定文件位置
  [--auto]                                       无人值守
```

### `--auto` 语义

和 blueprint / report 一致：全自动、警告+继续、不停下问用户。

- 用户描述不清晰 → 警告 + 按最保守解读生成
- 参数缺失 → 警告 + 用最常见默认
- 目标路径已存在 → 警告 + 备份原文件（`.bak-<ts>`）+ 覆写
- 生成后语法检查失败 → 警告 + 尝试自动修复一轮；仍失败则在文件开头加警告注释并写入
- 生成后 dry-run 失败 → 警告 + 在文件开头加注释标明"需人工验证"
- 只有物理上无法继续（无法写文件、语言工具链不可用且无替代）才真正停下

---

## 流程

```
Phase 0   意图理解 + 语言选择 + 目标类型推断
Phase 1   [若 setup/wizard/pipeline] 加载 target 骨架
Phase 2   素材收集（环境、现有代码风格、相关工具）
Phase 3   8 原则逐项设计 + 按议题调整维度权重
Phase 4   生成脚本
Phase 5   语法检查 + dry-run 验证
Phase 6   输出汇报（脚本路径 + 使用说明 + 验证结果）
```

---

## Phase 0: 意图理解 + 语言选择 + 目标类型推断

- 解析用户描述，识别：
  - 脚本用途（做什么）
  - 触发方式（一次性 / 定时 / hook / 交互）
  - 破坏性（是否修改数据 / 远程资源）
  - 运行频次（一次性 / 每天 / 高频）
- 推断语言（见"语言选择"章节）
- 推断目标类型（task / setup / ops / pipeline / hook / wizard）

若任一推断不确定：
- **默认模式**：向用户确认关键项（只问真正必要的，不展开细节）
- **auto 模式**：按最保守 / 最常见默认继续

---

## Phase 1: [条件] 加载特殊目标骨架

仅当 Phase 0 推断为 **setup / wizard / pipeline** 时，Read 对应 target 文件获取额外约束。其他目标跳过此 Phase。

---

## Phase 2: 素材收集

**主动收集**（优先于问用户）：
- 检测语言工具链：`which bash python python3 ruby nu shellcheck`
- 检测 OS：`uname -a`
- 检测 shell：`$SHELL` / `echo $SHELL`
- 扫项目既有脚本的风格：`find . -name "*.sh" -o -name "*.py" | head -5` 读几个作为风格参考
- 读 `README.md` / `CLAUDE.md` 里的"how to run / setup"章节
- 若脚本涉及 git / docker / kubectl 等，检查工具是否已安装

**不足时询问**（默认）/ **警告继续**（auto）：参考 report 的三级优先逻辑。

---

## Phase 3: 8 原则逐项设计

对每一条原则，明确本脚本如何满足：

```
| # | 原则 | 本脚本实施 |
|---|------|-----------|
| 1 | 错误处理 | set -euo pipefail + 每个外部命令有 || die |
| 2 | 日志 | stderr 输出 Step N/M 进度，-v 详细 |
| 3 | 幂等 | 创建前 mkdir -p；写前 stat 检查 |
| 4 | Dry-run | 支持 --dry-run，打印"会做什么"不真做 |
| 5 | 输入校验 | $1 必须是路径，存在性检查；$2 数字范围 1-100 |
| 6 | 路径/命令安全 | 参数用数组；realpath canonicalize |
| 7 | 确认 | 删除前 prompt，--yes 跳过 |
| 8 | 进度/超时 | wget 加 --timeout；循环打印 i/N |
```

根据议题特征某些维度加强或弱化，但不能跳过。

---

## Phase 4: 生成脚本

按以下结构组织：

```
#!/usr/bin/env <interpreter>
# <脚本简述>
# Usage: <用法示例>
# Arguments:
#   <arg>  <description>
# Flags:
#   --dry-run   <...>
#   --verbose   <...>
#   --yes       <...>
# Exit codes:
#   0 - success
#   1 - usage error
#   2 - runtime error
#   ...

set -euo pipefail    # 或语言对应的严格模式

# 常量
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_PREFIX="..."

# 工具函数
log_info()  { echo "[INFO] $*" >&2; }
log_error() { echo "[ERROR] $*" >&2; }
die()       { log_error "$*"; exit "${2:-1}"; }

usage() {
  cat <<EOF
...
EOF
}

# 参数解析
...

# 输入校验
...

# 前置检查（依赖的工具 / 环境）
...

# 主逻辑（每步可观察、幂等、失败可回滚）
...

# 成功退出
log_info "Done"
```

**生产级编码要求**（和 blueprint 的施工类目的一致）：
- 命名准确
- 注释讲 why 非 what
- 非 trivial 函数简短文档
- 外部命令的每次调用都有 error 处理
- 不硬编码路径 / 密钥 / 内部 IP
- 文件操作用 `mktemp` / `realpath` 等安全函数

---

## Phase 5: 语法检查 + dry-run 验证

生成后**必须**验证：

### 5.1 语法检查

| 语言 | 工具 |
|------|------|
| bash | `bash -n <file>`；若有 `shellcheck`，`shellcheck <file>` |
| python | `python3 -m py_compile <file>` |
| ruby | `ruby -c <file>` |
| nushell | `nu --ide-check <file>`（若支持） |

**失败处理**：
- **默认**：显示错误 → 修复后重试；连续 2 次失败 → 交给用户
- **auto**：警告 + 尝试修复一轮；仍失败 → 文件开头加注释警告，仍写入

### 5.2 Dry-run（若脚本支持）

调用生成的脚本 `--dry-run` 或 `--help`：
- 确认能正常启动
- 确认帮助消息展示正确
- 不真实运行破坏性操作

### 5.3 静态质量检查（shellcheck 等）

对 shell 脚本，若系统有 `shellcheck`，跑一遍：
- warning 级别以上的问题都修复
- info 级别按议题决定

---

## Phase 6: 输出汇报

```
✅ 脚本已生成

路径：<目标路径>
语言：<lang>
行数：~N
类型：<task / setup / ops / pipeline / hook / wizard>

8 原则实施摘要：
  1. 错误处理: ✓ <如何>
  2. 日志:    ✓ <如何>
  ...

使用方法：
  <command> [--dry-run] [-v] [--yes] [args...]

验证结果：
  语法检查：✓
  shellcheck：✓ / ⚠️ N warnings
  --help：✓
  --dry-run：✓ / N/A

建议下一步：
  • 手动跑一次 --dry-run 确认行为符合预期
  • 提交：/report decision 记录脚本设计决策（可选）
```

---

## 共享约束

**ASCII 可视化**：脚本的**使用说明**若有多步流程 / 决策分支，用 ASCII 图示展示（在脚本顶部注释或 `--help` 输出中）。

**生产级**：8 条原则是铁律，按议题调权重但不跳过。

**诚实**：不粉饰——若某维度由于议题特殊性无法完全满足（如 hook 脚本不方便 dry-run），在脚本头部注释明确标注**为什么** + **风险提示**。

---

## 反模式（生成即不合格）

- ❌ 没有 `set -euo pipefail` 或等价严格模式
- ❌ 外部命令不处理错误
- ❌ 破坏性操作无 dry-run / 无确认
- ❌ 硬编码路径 / 密钥 / 邮箱 / IP
- ❌ subprocess 字符串拼接（命令注入风险）
- ❌ "应该不会出错"作为不处理错误的理由
- ❌ 没有 `usage` / `--help`
- ❌ 无退出码语义
- ❌ 无日志或日志污染 stdout
- ❌ 长时间卡住无进度
- ❌ 失败时不清理临时资源
- ❌ 语法检查失败仍写入文件（除非 auto 模式且已标注）

---

## 与其他 skill 的衔接

- **`/blueprint`**：script 是"生成单文件"，不是"规划项目"。若用户议题涉及多文件 / 长期维护 / 跨模块 → 建议改用 `/blueprint --feat`。
- **`/report`**：脚本生成后若有决策值得留存（为何选某种实施策略、为何某维度弱化）→ `/report decision`。
- **`/autopilot`**：脚本运行时间长 / 需要无人值守 → 用 `/autopilot` 执行 script 生成的脚本。

---

输出语言跟随用户输入语言。
