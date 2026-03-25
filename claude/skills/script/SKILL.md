---
name: script
description: Generate robust, observable, fool-proof scripts for any purpose. Emphasizes error handling, user guidance, environment adaptability, and idempotent execution. No silent failures, no hardcoding, no surprises.
TRIGGER when: user asks to create/generate a script, automation, setup wizard, deployment script, or any standalone executable script.
DO NOT TRIGGER when: user is writing application code that happens to include shell commands, or writing a one-liner in the terminal.
argument-hint: "[target: <path>] [lang: bash|nu|python|powershell] [name: <script-name>] [purpose: <what the script does>]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(head:*), Bash(uname:*), Bash(which:*), Bash(date:*)
---

# /script

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
操作系统：!`uname -s 2>/dev/null || echo "unknown"`
构建配置：!`find . -maxdepth 2 \( -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" -o -name "Makefile" -o -name "docker-compose.yml" -o -name "Dockerfile" \) 2>/dev/null | head -10`
现有脚本：!`find . -maxdepth 2 \( -name "*.sh" -o -name "*.nu" -o -name "*.ps1" -o -name "*.py" \) ! -path "*/.git/*" ! -path "*/node_modules/*" ! -path "*/target/*" ! -path "*/__pycache__/*" 2>/dev/null | head -10`

参数：$ARGUMENTS

---

## 参数解析

- `[target: <path>]`：项目根目录，未指定则使用当前目录
- `[lang: bash|nu|python|powershell]`：脚本语言；未指定则自动判断
- `[name: <script-name>]`：输出文件名（不含扩展名）；未指定则根据用途推断
- `[purpose: <what the script does>]`：脚本用途描述；未指定则分析项目后推断

---

## Step 0: 理解需求

1. 判断脚本属于什么类型（项目启动器、环境搭建、部署、数据处理、维护、CI/CD、通用工具）
2. 读取构建配置文件，识别项目类型和依赖
3. 选择脚本语言（若未指定）：项目已有同类脚本则跟随 → 数据处理或跨平台选 Python → Unix 选 Bash → Windows 选 PowerShell
4. 明确脚本的输入、输出、依赖、目标环境

---

## Step 1: 编写脚本

遵守以下全部原则。**原则是强制的，不是建议**——每条原则的违反都会降低脚本质量。

---

### 原则 1：鲁棒性 — 错误是指引，不是死胡同

脚本的每一个可能失败的操作都必须被处理。错误消息必须告诉用户 **发生了什么 → 为什么 → 怎么解决**。

**规则：**

- 每个外部命令调用都必须检查返回值
- 错误消息必须包含三部分：**事实**（什么失败了）+ **原因**（可能为什么）+ **操作**（怎么修）
- 操作部分必须是用户可以直接复制粘贴执行的命令
- `die` / 致命退出的最后一行必须提示用户如何重新运行此脚本
- 区分致命错误（必须退出）和可恢复警告（提示后继续）
- 先做完所有前置检查（fail-fast），再执行主操作——不要在执行到一半时才发现缺依赖

```
✗  未找到 cargo — Rust 工具链未安装
   安装：curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   安装后重新运行：./run.sh
```

```
⚠  .env 文件不存在，使用默认配置继续
   创建配置：cp .env.example .env && ${EDITOR:-nano} .env
```

---

### 原则 2：可观测性 — 用户始终知道发生了什么

脚本绝不静默执行。用户应该能从输出中理解脚本在做什么、做到了哪里、结果是什么。

**规则：**

- 脚本启动时报告运行环境（OS、架构、关键工具版本、工作目录）
- 每个阶段开始时打印阶段名称
- 每个检查通过时打印通过确认（附关键信息如版本号）
- 长时间操作要有进度指示（至少有"正在执行…"）
- 脚本结束时打印结果摘要（成功产物路径、访问地址、后续操作建议）
- 使用统一的符号语言：

```
▶  阶段开始 / 正在执行
✓  成功（附关键结果）
⚠  警告（不阻断，附建议）
✗  错误（将退出，附修复命令）
ℹ  补充信息
💡 后续建议
```

- 颜色检测终端（`-t 1` / `isatty`），非终端或 CI 环境自动禁用颜色
- 支持 `--verbose` 模式：为每步操作补充**为什么做这个**和**背景知识**（面向不熟悉项目的新手）

---

### 原则 3：傻瓜式 — 符合直觉，无需阅读源码

用户拿到脚本后应该能"无脑运行"——不需要先看源码、不需要提前准备、不需要记住参数顺序。

**规则：**

- 无参数运行 = 最常见的用法（合理的默认值）
- `--help` 必须包含具体用法示例，而不只是选项列表
- 参数名自解释：`--check-only`、`--dry-run`、`--verbose`、`--clean`
- 缺少依赖时不报错退出了事——打印安装命令，让用户复制粘贴就能装
- 缺少配置文件（.env）时自动从模板创建或使用默认值继续，而不是直接失败
- `--verbose` 中的解释应包含日常类比（如"cargo 类似于 Python 的 pip"），面向完全不了解该技术栈的人

---

### 原则 3.5：防呆 — 破坏性操作必须保守

用户可能不理解脚本的每一步。任何不可逆操作都必须假设用户会误触，默认选择最安全的路径。

**规则：**

- 破坏性操作（删除文件/目录、覆盖已有内容、停止服务、重置状态、drop/truncate）必须在非 CI 环境下交互确认
- 确认提示默认为拒绝：`[y/N]`（大写 N = 回车即拒绝）。**绝不使用 `[Y/n]`**
- 确认提示超时（如 30 秒无输入）→ 按拒绝处理，不按接受处理
- 确认前必须**预览影响范围**：列出将被删除/覆盖的具体文件列表和数量，而不是只说"即将删除"
- 涉及多个目标时，显示数量摘要 + 前 10 项明细 + `--verbose` 查看完整列表
- 批量破坏性操作（删除 > 5 个文件、清空目录）需要二次确认：先预览 → 确认 → 输入目标名称（如 `输入目录名 "build" 以确认删除`）
- 提供 `--force` / `-f` 跳过确认（供 CI/自动化使用），但 `--force` **绝不是默认行为**
- 破坏性操作执行前自动创建备份（若可行）：`*.bak` / `.backup-YYYYMMDD-HHMMSS/`，并告知用户恢复命令
- `--dry-run` 对破坏性操作尤其重要——明确显示 `[DRY RUN] 将删除 X 个文件` 而非静默跳过

```bash
# 示例：删除构建产物
files=$(find build/ -type f 2>/dev/null)
count=$(echo "$files" | grep -c . 2>/dev/null || echo 0)
if [ "$count" -gt 0 ]; then
    echo "⚠  即将删除 build/ 下 ${count} 个文件："
    echo "$files" | head -10
    [ "$count" -gt 10 ] && echo "   ... 及其余 $((count - 10)) 个文件（--verbose 查看完整列表）"
    printf "确认删除？[y/N] "
    read -r -t 30 ans || ans=""
    case "$ans" in [yY]*) ;; *) echo "已取消。"; exit 0 ;; esac
fi
```

---

### 原则 4：兼容性 — 在哪都能跑

脚本不应假设用户的环境和作者的一样。

**Bash 脚本规则：**

- 不使用 `grep -P`（macOS BSD grep 不支持）→ 用 `grep -E`
- 不使用 `sort -V`（macOS/BusyBox 不支持）→ 纯 shell 版本比较
- 不使用 `readlink -f`（macOS 不支持）→ `cd "$(dirname "$0")" && pwd`
- 不使用 `sed -i` 无备份参数（macOS 需要 `-i ''`）→ 用临时文件
- 不使用 `source .env`（命令注入风险）→ 逐行 `read` + `export`
- 不使用 Bash 4+ 专有特性（关联数组 `declare -A`、`${var,,}`）——除非目标明确仅 Linux
- 解析版本号用 `grep -oE '[0-9]+\.[0-9]+\.[0-9]+'`

**Python 脚本规则：**

- 仅使用标准库，不引入 pip 依赖（no colorama, no dotenv, no click）
- `signal.SIGTERM` 用 `try/except` 保护（Windows 不支持）
- 路径操作用 `pathlib`，不硬编码路径分隔符

**跨语言规则：**

- 自动检测运行环境并适应：
  - **CI**（`CI=true` / `GITHUB_ACTIONS` / `GITLAB_CI`）：禁颜色、跳确认、输出适合日志
  - **WSL**（`/proc/version` 含 `microsoft`）：提示路径映射等已知问题
  - **Docker**（`/.dockerenv` 存在）：跳过用户权限检查
- 所有路径使用变量，不硬编码绝对路径
- 所有外部工具先 `command -v` / `which` 检测再调用

---

### 原则 5：普适性 — 配置化优于硬编码

脚本应该通过配置适应不同场景，而不是修改源码。

**规则：**

- 所有可变参数都应有环境变量覆盖机制（脚本内定义默认值，用户可通过环境变量或 .env 覆盖）
- 构建模式（debug/release）、端口号、路径等决不硬编码
- .env 加载逻辑：有 .env 则加载 → 无 .env 但有 .env.example 则提示创建 → 都没有则使用内置默认值
- 支持 `--` 透传额外参数给底层命令
- 脚本自身可配置的行为（如是否自动打开浏览器、是否启用 watch 模式）通过命令行参数或环境变量控制

---

### 原则 6：幂等与安全

重复运行不产生副作用，不导致意外。

**规则：**

- 重复运行同一脚本的结果与运行一次相同
- 创建文件/目录前检查是否已存在
- 下载资源前检查是否已缓存
- `--clean` 才清理，默认不清理
- Ctrl+C 时优雅退出：清理临时文件、终止子进程、不留残余
- `--dry-run` 只显示会做什么，不实际执行

---

### 提示语言

脚本中的用户可见文字（提示、错误消息、help 文本）跟随项目的主要语言。英文项目用英文提示，中文项目用中文。

---

## Step 2: 验证与输出

1. 检查脚本语法：
   ```bash
   bash -n <script>.sh          # Bash
   nu --ide-check <script>.nu   # Nushell
   python -m py_compile <script>.py  # Python
   ```

2. 设置可执行权限（Bash/Nu/Python）：
   ```bash
   chmod +x <script>
   ```

3. 输出脚本到项目根目录（或 `target` 指定路径）

4. 输出使用说明摘要：

```
✅ 脚本已生成：./<name>.sh

用法：
  ./<name>.sh                  # 默认运行
  ./<name>.sh --verbose        # 详细模式（推荐初次使用）
  ./<name>.sh --check-only     # 只检查环境
  ./<name>.sh --dry-run        # 查看会执行什么
  ./<name>.sh --help           # 查看完整帮助

💡 初次使用建议先运行 --verbose 模式了解脚本的每一步操作。
```

---

输出语言跟随用户输入语言。
