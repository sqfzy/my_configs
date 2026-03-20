---
description: Generate a robust one-click launcher script for a project. Handles environment setup, dependency checks, build, and execution with verbose user-friendly output and actionable error messages. Run after completing a project that has complex environment or runtime requirements.
argument-hint: "[target: <path>] [lang: bash|nu|powershell] [name: <script-name>]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(head:*), Bash(uname:*), Bash(which:*), Bash(date:*)
---

# /run-script

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
操作系统：!`uname -s 2>/dev/null || echo "unknown"`
构建配置：!`find . -maxdepth 2 \( -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" -o -name "Makefile" \) 2>/dev/null | head -10`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -40`
现有脚本：!`find . -maxdepth 2 \( -name "*.sh" -o -name "*.nu" -o -name "*.ps1" -o -name "run*" -o -name "start*" -o -name "setup*" \) ! -path "*/.git/*" 2>/dev/null | head -10`

参数：$ARGUMENTS

---

## 参数解析

- `[target: <path>]`：项目根目录，未指定则使用当前目录
- `[lang: bash|nu|powershell]`：脚本语言；未指定则自动根据项目和 OS 判断
- `[name: <script-name>]`：输出脚本文件名（不含扩展名）；未指定则使用 `run`

---

## Step 0: 项目深度分析

在生成脚本之前，充分理解项目的运行需求。

### 0.1 项目类型识别

读取构建配置文件，识别：

| 线索 | 判断 |
|------|------|
| `Cargo.toml` | Rust，`cargo build/run` |
| `xmake.lua` | C++，`xmake build && xmake run` |
| `CMakeLists.txt` | C++，需判断 out-of-tree build 路径 |
| `pyproject.toml` / `uv.lock` | Python，`uv run` |
| `requirements.txt` | Python，virtualenv 模式 |
| `package.json` | Node.js，检查 `scripts.start` / `scripts.dev` |
| `go.mod` | Go，`go build && ./binary` |
| `Makefile` | 读取 `make help` 或 `all`/`run` target |

### 0.2 依赖与环境要求识别

读取以下文件，提取所有外部依赖：
- `Cargo.toml`：注意 `build-dependencies`、`[features]`、`[profile]`
- `xmake.lua`：注意 `add_requires`、平台条件
- `pyproject.toml`：注意 `[tool.uv]`、Python 版本约束、extras
- `README.md`：提取 Prerequisites / Requirements 章节
- `.env.example` / `.env.template`：环境变量列表
- `docker-compose.yml` / `Dockerfile`：容器依赖

识别结果分类：
- **必须的工具链**（cargo/xmake/uv/node/go/cmake 等）及最低版本
- **系统级依赖**（动态库、系统包，如 `libssl-dev`、`pkg-config`）
- **环境变量**（必填项 vs 有默认值的可选项）
- **外部服务**（数据库、消息队列、第三方 API）
- **数据文件 / 模型文件**（需预先下载的资产）

### 0.3 运行模式识别

分析项目支持哪些运行模式：
- 开发模式 vs 生产模式（不同的 build profile / 环境变量）
- CLI 参数（从 `clap`/`argparse`/`commander` 等推断）
- 后台服务 vs 前台进程
- 是否需要热重载

### 0.4 脚本语言选择

若用户未指定 `lang`，按以下优先级自动判断：

| 条件 | 选择 |
|------|------|
| 项目已有 `.nu` 脚本 / 用户在 Nushell 环境 | Nushell |
| Windows 唯一目标平台 | PowerShell |
| 跨平台 Unix 项目 | Bash |
| 默认 | Bash |

声明选择并说明理由。

---

## Step 1: 脚本设计

在生成代码前，明确脚本的完整结构：

```
脚本职责清单：
  [ ] 环境检测（工具链版本、系统依赖）
  [ ] 环境变量处理（加载 .env，填充默认值，验证必填项）
  [ ] 依赖安装（若适用：cargo fetch / uv sync / npm install 等）
  [ ] 构建（debug / release 模式）
  [ ] 预运行检查（端口占用、文件权限、外部服务可达性）
  [ ] 执行
  [ ] 清理（Ctrl+C 时的 trap 处理）

参数支持：
  [ ] --help         显示用法
  [ ] --release      生产构建（若适用）
  [ ] --clean        清理构建产物后重新构建
  [ ] --check-only   只做环境检查，不构建不运行
  [ ] <自定义参数，从项目 CLI 接口推断>
```

---

## Step 2: 生成脚本

根据分析结果生成脚本，严格遵守以下设计原则。

---

### 核心设计原则

#### 原则 1：绝不静默

每一个有意义的操作都必须向用户报告：

```bash
# ✅ 正确
echo "▶ 正在检查 Rust 工具链..."
echo "✓ rustc 1.78.0 (已满足最低版本要求 1.70)"

# ❌ 错误
rustc --version > /dev/null
```

进度格式规范：
```
▶  正在进行某操作...
✓  操作成功（附关键结果）
⚠  警告信息（不阻断执行）
✗  错误信息（将要退出）
ℹ  提示信息（补充上下文）
```

#### 原则 2：错误必须可操作

每一个可能失败的步骤，失败时都必须告诉用户**怎么修**，而不只是报告失败：

```bash
# ✅ 正确
if ! command -v cargo &>/dev/null; then
    echo "✗ 未找到 cargo（Rust 工具链）"
    echo ""
    echo "  安装方式："
    echo "    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    echo "    安装后重新打开终端，再运行此脚本"
    echo ""
    echo "  若已安装但未找到，请检查 PATH 是否包含 ~/.cargo/bin"
    exit 1
fi

# ❌ 错误
cargo build || exit 1
```

#### 原则 3：失败快，失败明确

所有检查在执行任何构建操作前完成（fail-fast），不要构建到一半才发现缺少依赖：

```bash
# 先做完所有检查
check_toolchain
check_env_vars
check_system_deps
check_ports

# 全部通过后才开始构建
build_project
run_project
```

#### 原则 4：幂等且安全

- 重复运行不产生副作用
- `--clean` 才清理，默认不清理
- Ctrl+C 时通过 `trap` 优雅退出，清理临时文件和子进程

---

### Bash 脚本模板

```bash
#!/usr/bin/env bash
# <项目名> 一键启动脚本
# 生成时间：<timestamp>
# 用法：./run.sh [选项] [-- <传递给程序的参数>]

set -euo pipefail

# ──────────────────────────────────────────
# 颜色 & 格式
# ──────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
    BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
else
    RED=''; YELLOW=''; GREEN=''; BLUE=''; CYAN=''; BOLD=''; RESET=''
fi

step()  { echo -e "\n${BLUE}▶${RESET}  ${BOLD}$*${RESET}"; }
ok()    { echo -e "${GREEN}✓${RESET}  $*"; }
warn()  { echo -e "${YELLOW}⚠${RESET}  $*"; }
info()  { echo -e "${CYAN}ℹ${RESET}  $*"; }
error() { echo -e "${RED}✗${RESET}  ${BOLD}$*${RESET}" >&2; }
die()   {
    error "$1"
    [[ -n "${2:-}" ]] && echo -e "\n${2}" >&2
    exit 1
}
separator() { echo -e "\n${BOLD}────────────────────────────────────────${RESET}"; }

# ──────────────────────────────────────────
# 默认配置（可通过环境变量覆盖）
# ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_MODE="${BUILD_MODE:-debug}"         # debug | release
LOG_LEVEL="${LOG_LEVEL:-info}"
# <其他项目特定的配置变量>

# ──────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────
CLEAN=false
CHECK_ONLY=false
PASSTHROUGH_ARGS=()

usage() {
    cat <<EOF
${BOLD}用法${RESET}：$0 [选项] [-- 程序参数]

${BOLD}选项${RESET}：
  --release       使用 release 模式构建（更慢，但性能更好）
  --clean         清理构建产物后重新构建
  --check-only    只检查环境，不构建不运行
  -h, --help      显示此帮助

${BOLD}环境变量${RESET}：
  BUILD_MODE      构建模式（debug/release），默认 debug
  LOG_LEVEL       日志级别（trace/debug/info/warn/error），默认 info

${BOLD}示例${RESET}：
  $0                         # 默认启动
  $0 --release               # release 构建后启动
  $0 -- --port 8080          # 向程序传递参数
  $0 --check-only            # 只检查环境
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --release)    BUILD_MODE=release; shift ;;
        --clean)      CLEAN=true; shift ;;
        --check-only) CHECK_ONLY=true; shift ;;
        -h|--help)    usage; exit 0 ;;
        --)           shift; PASSTHROUGH_ARGS=("$@"); break ;;
        *)            die "未知选项：$1" "运行 $0 --help 查看用法" ;;
    esac
done

# ──────────────────────────────────────────
# Ctrl+C 优雅退出
# ──────────────────────────────────────────
CHILD_PID=""
cleanup() {
    echo ""
    warn "收到中断信号，正在退出..."
    [[ -n "$CHILD_PID" ]] && kill "$CHILD_PID" 2>/dev/null && ok "子进程已终止"
    # <清理临时文件>
    exit 0
}
trap cleanup INT TERM

# ──────────────────────────────────────────
# Step 1: 环境检测
# ──────────────────────────────────────────
check_env() {
    separator
    step "检查运行环境"

    # 工具链检查（按项目类型填充）
    # --- Rust 示例 ---
    # if ! command -v cargo &>/dev/null; then
    #     die "未找到 cargo（Rust 工具链）" \
    #         "  安装：curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n  安装后重新打开终端"
    # fi
    # RUST_VERSION=$(rustc --version | grep -oP '\d+\.\d+\.\d+')
    # RUST_MIN="1.70.0"
    # if ! version_gte "$RUST_VERSION" "$RUST_MIN"; then
    #     die "Rust 版本过低：$RUST_VERSION（需要 >= $RUST_MIN）" \
    #         "  升级：rustup update stable"
    # fi
    # ok "rustc $RUST_VERSION"

    # 环境变量检查
    # MISSING_VARS=()
    # for var in REQUIRED_VAR_1 REQUIRED_VAR_2; do
    #     [[ -z "${!var:-}" ]] && MISSING_VARS+=("$var")
    # done
    # if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    #     die "缺少必要的环境变量：${MISSING_VARS[*]}" \
    #         "  请复制 .env.example 为 .env 并填写对应值"
    # fi

    ok "环境检查通过"
}

# ──────────────────────────────────────────
# Step 2: 加载 .env
# ──────────────────────────────────────────
load_dotenv() {
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        step "加载 .env 配置"
        set -a
        # shellcheck disable=SC1091
        source "$SCRIPT_DIR/.env"
        set +a
        ok ".env 已加载"
    elif [[ -f "$SCRIPT_DIR/.env.example" ]]; then
        warn "未找到 .env 文件"
        info "请执行：cp .env.example .env  并填写配置"
        info "使用内置默认值继续..."
    fi
}

# ──────────────────────────────────────────
# Step 3: 清理（可选）
# ──────────────────────────────────────────
clean_build() {
    if [[ "$CLEAN" == true ]]; then
        step "清理构建产物"
        # <按项目类型填充：cargo clean / xmake clean / rm -rf build/ 等>
        ok "清理完成"
    fi
}

# ──────────────────────────────────────────
# Step 4: 构建
# ──────────────────────────────────────────
build_project() {
    separator
    step "构建项目（模式：${BUILD_MODE}）"

    # <按项目类型填充构建命令>
    # Rust 示例：
    # local cargo_flags=()
    # [[ "$BUILD_MODE" == "release" ]] && cargo_flags+=(--release)
    # if ! cargo build "${cargo_flags[@]}"; then
    #     die "构建失败" \
    #         "  查看上方错误信息\n  常见原因：依赖未安装、Rust 版本不符\n  尝试：cargo clean && ./run.sh --clean"
    # fi

    ok "构建成功"
}

# ──────────────────────────────────────────
# Step 5: 预运行检查
# ──────────────────────────────────────────
prerun_checks() {
    step "预运行检查"

    # 端口占用检查示例：
    # local port="${PORT:-8080}"
    # if lsof -i ":$port" &>/dev/null; then
    #     die "端口 $port 已被占用" \
    #         "  查看占用进程：lsof -i :$port\n  或修改 .env 中的 PORT 配置"
    # fi
    # ok "端口 $port 可用"

    ok "预运行检查通过"
}

# ──────────────────────────────────────────
# Step 6: 运行
# ──────────────────────────────────────────
run_project() {
    separator
    step "启动程序"
    info "构建模式：${BUILD_MODE} | 日志级别：${LOG_LEVEL}"
    [[ ${#PASSTHROUGH_ARGS[@]} -gt 0 ]] && info "传递参数：${PASSTHROUGH_ARGS[*]}"
    separator

    # <按项目类型填充运行命令>
    # Rust 示例：
    # local binary="target/${BUILD_MODE}/<binary-name>"
    # RUST_LOG="$LOG_LEVEL" "$binary" "${PASSTHROUGH_ARGS[@]}" &
    # CHILD_PID=$!
    # wait "$CHILD_PID"
}

# ──────────────────────────────────────────
# 版本比较工具函数
# ──────────────────────────────────────────
version_gte() {
    # 用法：version_gte "1.78.0" "1.70.0" → true if first >= second
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

# ──────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────
main() {
    separator
    echo -e "${BOLD}<项目名> 启动脚本${RESET}"
    info "运行于：$(uname -s) | 脚本目录：$SCRIPT_DIR"
    separator

    load_dotenv
    check_env

    if [[ "$CHECK_ONLY" == true ]]; then
        separator
        ok "环境检查完成，所有依赖满足。"
        exit 0
    fi

    clean_build
    build_project
    prerun_checks
    run_project
}

main "$@"
```

---

### Nushell 脚本模板

```nushell
#!/usr/bin/env nu
# <项目名> 一键启动脚本
# 生成时间：<timestamp>

# ──────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────
def step [msg: string] {
    print $"\n(ansi blue)▶(ansi reset)  (ansi bold)($msg)(ansi reset)"
}
def ok [msg: string] {
    print $"(ansi green)✓(ansi reset)  ($msg)"
}
def warn [msg: string] {
    print $"(ansi yellow)⚠(ansi reset)  ($msg)"
}
def info [msg: string] {
    print $"(ansi cyan)ℹ(ansi reset)  ($msg)"
}
def die [msg: string, hint: string = ""] {
    print $"(ansi red)✗(ansi reset)  (ansi bold)($msg)(ansi reset)"
    if ($hint | is-not-empty) { print $"\n($hint)" }
    exit 1
}
def separator [] {
    print $"\n(ansi bold)────────────────────────────────────────(ansi reset)"
}

# ──────────────────────────────────────────
# 主命令
# ──────────────────────────────────────────
def main [
    --release       # 使用 release 模式构建
    --clean         # 清理后重新构建
    --check-only    # 只检查环境
    ...args         # 传递给程序的参数
] {
    separator
    print $"(ansi bold)<项目名> 启动脚本(ansi reset)"
    info $"运行于：(sys host | get name)"
    separator

    # 加载 .env
    if (".env" | path exists) {
        step "加载 .env 配置"
        # nu 中通过 open 读取 .env 并 load-env
        open .env | lines
            | where { |l| ($l | str trim) != "" and not ($l | str starts-with "#") }
            | each { |l|
                let parts = ($l | split column "=" key value)
                load-env { ($parts.key.0): ($parts.value.0) }
            }
        ok ".env 已加载"
    }

    # 环境检测
    separator
    step "检查运行环境"
    # <按项目类型填充检查逻辑>
    ok "环境检查通过"

    if $check_only {
        separator
        ok "环境检查完成，所有依赖满足。"
        return
    }

    # 构建
    separator
    let mode = if $release { "release" } else { "debug" }
    step $"构建项目（模式：($mode)）"
    # <按项目类型填充构建命令>
    ok "构建成功"

    # 运行
    separator
    step "启动程序"
    separator
    # <按项目类型填充运行命令>
}
```

---

## Step 3: 填充项目特定逻辑

将 Step 0 分析出的所有项目信息填充进模板的占位区域，包括：

- `check_env()`：填充实际的工具链检查、版本约束、系统依赖检查
- `build_project()`：填充实际构建命令和 build profile 参数
- `prerun_checks()`：填充端口检查、文件权限、外部服务探活
- `run_project()`：填充实际的二进制路径、环境变量注入、启动命令
- `usage()`：填充项目实际支持的 CLI 参数
- `.env` 变量列表：从 `.env.example` 提取，附上每个变量的说明和默认值
- 错误提示：为每个可能失败的步骤写出具体的修复指引

**错误提示质量标准**：
- 说明**为什么**失败（不只是"失败了"）
- 给出**具体的修复命令**（不只是"请安装 X"）
- 说明**验证方式**（修复后如何确认解决了）

---

## Step 4: 验证与输出

生成完成后：

1. 检查脚本语法：
   ```bash
   bash -n run.sh          # Bash 语法检查
   nu --ide-check run.nu   # Nushell 语法检查（若适用）
   ```

2. 设置可执行权限（Bash/Nu）：
   ```bash
   chmod +x run.sh
   ```

3. 输出脚本到项目根目录（或 `target` 指定路径）

4. 生成使用说明摘要，直接输出到终端：

```
✅ 脚本已生成：./run.sh

用法：
  ./run.sh              # 默认启动
  ./run.sh --release    # release 构建
  ./run.sh --clean      # 清理后重新构建
  ./run.sh --check-only # 只检查环境

环境变量（可在 .env 中配置）：
  <从分析结果列出>
```

---

输出语言跟随用户输入语言。
