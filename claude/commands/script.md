---
description: Generate robust, beginner-friendly scripts for any purpose — project launchers, automation, deployment, data processing, setup wizards, etc. Handles environment detection with transparent reporting, dependency checks, and produces scripts with actionable guidance at every step. Supports --verbose mode for beginners who want to understand what the script does and why.
argument-hint: "[target: <path>] [lang: bash|nu|powershell] [name: <script-name>] [purpose: <what the script does>]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(head:*), Bash(uname:*), Bash(which:*), Bash(date:*)
---

# /script

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
操作系统：!`uname -s 2>/dev/null || echo "unknown"`
构建配置：!`find . -maxdepth 2 \( -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" -o -name "Makefile" -o -name "docker-compose.yml" -o -name "Dockerfile" \) 2>/dev/null | head -10`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" -o -name "*.sh" -o -name "*.nu" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -40`
现有脚本：!`find . -maxdepth 2 \( -name "*.sh" -o -name "*.nu" -o -name "*.ps1" -o -name "run*" -o -name "start*" -o -name "setup*" -o -name "deploy*" -o -name "install*" \) ! -path "*/.git/*" 2>/dev/null | head -10`

参数：$ARGUMENTS

---

## 参数解析

- `[target: <path>]`：项目根目录，未指定则使用当前目录
- `[lang: bash|nu|powershell]`：脚本语言；未指定则自动判断
- `[name: <script-name>]`：输出脚本文件名（不含扩展名）；未指定则根据用途推断
- `[purpose: <what the script does>]`：脚本用途描述；未指定则分析项目后推断

---

## Step 0: 需求与环境深度分析

### 0.1 脚本用途分类

判断脚本属于以下哪种类型，并据此调整模板结构：

| 类型 | 特征 | 核心职责 |
|------|------|----------|
| **项目启动器** | 构建 + 运行项目 | 依赖检查 → 构建 → 运行 |
| **环境搭建** | 初始化开发环境 | 安装工具链 → 配置 → 验证 |
| **部署脚本** | 发布到服务器/云 | 构建 → 打包 → 推送 → 验证 |
| **数据处理** | ETL / 批处理 | 输入验证 → 处理 → 输出 → 报告 |
| **维护脚本** | 清理/备份/迁移 | 预检查 → 操作 → 验证 → 报告 |
| **自动化流水线** | CI/CD / 定时任务 | 阶段顺序执行 + 错误回滚 |
| **通用工具** | 其他自动化任务 | 按需组合 |

### 0.2 项目类型识别

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
| `docker-compose.yml` | 容器化部署 |

### 0.3 依赖与环境要求识别

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
脚本职责清单（根据脚本类型裁剪）：
  [ ] 环境检测 + 环境报告（必须）
  [ ] --verbose 详细模式支持（必须）
  [ ] 工具链版本检查
  [ ] 环境变量处理（加载 .env，填充默认值，验证必填项）
  [ ] 依赖安装（若适用）
  [ ] 构建（若适用）
  [ ] 预运行检查（端口占用、文件权限、外部服务可达性）
  [ ] 核心操作执行
  [ ] 结果报告 / 摘要
  [ ] 清理（Ctrl+C 时的 trap 处理）

参数支持（基础集，按类型扩充）：
  [ ] --help / -h      显示用法
  [ ] --verbose / -v    详细模式：解释每步做了什么、为什么做
  [ ] --check-only      只做环境检查，不执行主操作
  [ ] --dry-run         模拟运行，只显示会执行什么（若适用）
  [ ] <脚本类型特定参数>
```

---

## Step 2: 生成脚本

根据分析结果生成脚本，严格遵守以下设计原则。

---

### 核心设计原则

#### 原则 1：环境透明 — 检测后立即报告

脚本启动后，必须向用户完整报告检测到的运行环境，让用户清楚地知道脚本在什么环境下运行。

```bash
# ✅ 正确 — 环境检测后向用户报告全貌
separator
echo -e "${BOLD}环境报告${RESET}"
echo -e "  操作系统  ：$(uname -s) $(uname -r)"
echo -e "  架构      ：$(uname -m)"
echo -e "  Shell     ：$SHELL"
echo -e "  工作目录  ：$(pwd)"
echo -e "  用户      ：$(whoami)"
echo -e "  Rust 版本 ：$(rustc --version 2>/dev/null || echo '未安装')"
echo -e "  构建模式  ：$BUILD_MODE"
separator

# ❌ 错误 — 静默检测，用户不知道脚本在什么环境下运行
rustc --version > /dev/null
```

#### 原则 2：绝不静默

每一个有意义的操作都必须向用户报告：

```bash
# ✅ 正确
echo "▶ 正在检查 Rust 工具链..."
echo "✓ rustc 1.78.0（已满足最低版本要求 1.70）"

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
💡 建议（可选的改进方向）
```

#### 原则 3：一切提示皆可操作

不仅错误消息，**所有提示、建议、警告**都必须给出用户可以直接复制粘贴执行的命令或具体步骤：

```bash
# ✅ 正确 — 所有提示都可操作
ok "rustc 1.78.0（已满足最低版本要求 1.70）"
info "升级到最新版本：rustup update stable"

warn "检测到 .env.example 但没有 .env 文件"
info "创建配置：cp .env.example .env"
info "然后编辑：\${EDITOR:-nano} .env"

warn "构建产物目录占用 2.3 GB"
info "清理方式：$0 --clean"

die "端口 8080 已被占用" \
    "  查看占用进程：lsof -i :8080\n  终止占用进程：kill \$(lsof -t -i :8080)\n  或修改端口：编辑 .env 中的 PORT=<新端口>"

# ❌ 错误 — 提示不可操作
warn "建议升级 Rust"
warn "没有 .env 文件，建议创建"
die "端口被占用"
```

#### 原则 4：--verbose 小白友好模式

`--verbose` 模式为初学者提供每步操作的**原因解释**和**背景知识**：

```bash
VERBOSE=false

verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo -e "  ${CYAN}💬${RESET} $*"
    fi
}

# 使用示例
step "检查 Rust 工具链"
verbose "Rust 是这个项目的编程语言。cargo 是 Rust 的包管理器和构建工具，类似于 Python 的 pip + setuptools。"
verbose "我们需要确认 cargo 已安装，并且版本满足项目要求。"

if command -v cargo &>/dev/null; then
    CARGO_VERSION=$(cargo --version | grep -oP '\d+\.\d+\.\d+')
    ok "cargo $CARGO_VERSION"
    verbose "cargo 是 Rust 的构建工具。版本 $CARGO_VERSION 满足项目要求（最低 1.70）。"
else
    die "未找到 cargo（Rust 工具链）" \
        "  Rust 是这个项目使用的编程语言，cargo 是它的构建工具。\n\n  安装方式（一行命令，复制粘贴即可）：\n    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n\n  安装后需要做：\n    1. 关闭当前终端\n    2. 打开一个新终端\n    3. 重新运行此脚本：$0"
fi

step "加载 .env 配置"
verbose ".env 文件存放项目运行所需的环境变量（如数据库地址、API 密钥等）。"
verbose "这些配置不应提交到 Git，所以用 .env 文件在本地管理。"
```

`--verbose` 中的解释应包含：
- **这一步在做什么**（概念解释）
- **为什么需要做**（目的和原因）
- **类比说明**（用常见概念类比，如"类似于 Python 的 pip"）
- **如果出问题了怎么理解错误**（预防性提示）

#### 原则 5：失败快，失败明确

所有检查在执行任何主操作前完成（fail-fast）：

```bash
# 先做完所有检查
check_env
validate_inputs

# 全部通过后才开始主操作
execute_main_task
report_results
```

#### 原则 6：幂等且安全

- 重复运行不产生副作用
- `--clean` 才清理，默认不清理
- Ctrl+C 时通过 `trap` 优雅退出，清理临时文件和子进程
- `--dry-run` 只显示会做什么，不实际执行（若适用）

---

### Bash 脚本模板

```bash
#!/usr/bin/env bash
# <脚本名> — <用途描述>
# 生成时间：<timestamp>
# 用法：./<name>.sh [选项] [-- <额外参数>]

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

step()    { echo -e "\n${BLUE}▶${RESET}  ${BOLD}$*${RESET}"; }
ok()      { echo -e "${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
info()    { echo -e "${CYAN}ℹ${RESET}  $*"; }
suggest() { echo -e "${CYAN}💡${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET}  ${BOLD}$*${RESET}" >&2; }
verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo -e "  ${CYAN}💬${RESET} $*"
    fi
}
die() {
    error "$1"
    [[ -n "${2:-}" ]] && echo -e "\n${2}" >&2
    exit 1
}
separator() { echo -e "\n${BOLD}────────────────────────────────────────${RESET}"; }

# ──────────────────────────────────────────
# 默认配置（可通过环境变量覆盖）
# ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# <其他项目特定的配置变量>

# ──────────────────────────────────────────
# 参数解析
# ──────────────────────────────────────────
VERBOSE=false
CHECK_ONLY=false
DRY_RUN=false
PASSTHROUGH_ARGS=()

usage() {
    cat <<EOF
${BOLD}用法${RESET}：$0 [选项] [-- 额外参数]

${BOLD}<脚本用途一句话描述>${RESET}

${BOLD}选项${RESET}：
  -v, --verbose     详细模式：解释每步操作的原因和背景
  --check-only      只检查环境，不执行主操作
  --dry-run         模拟运行：显示会执行什么，但不实际执行
  -h, --help        显示此帮助

${BOLD}环境变量${RESET}：
  <按实际需要列出>

${BOLD}示例${RESET}：
  $0                         # 默认运行
  $0 --verbose               # 详细模式（推荐初次使用）
  $0 --check-only            # 只检查环境是否满足
  $0 --dry-run               # 查看脚本会做什么，但不实际执行
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)   VERBOSE=true; shift ;;
        --check-only)   CHECK_ONLY=true; shift ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)      usage; exit 0 ;;
        --)             shift; PASSTHROUGH_ARGS=("$@"); break ;;
        *)              die "未知选项：$1" "  查看帮助：$0 --help" ;;
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
# 环境检测与报告
# ──────────────────────────────────────────
report_env() {
    separator
    step "检测运行环境"
    verbose "脚本需要先了解当前系统环境，确保所有必需的工具和依赖都已就绪。"

    local os_name kernel_version arch shell_name user_name
    os_name="$(uname -s)"
    kernel_version="$(uname -r)"
    arch="$(uname -m)"
    shell_name="${SHELL:-unknown}"
    user_name="$(whoami)"

    separator
    echo -e "${BOLD}📋 环境报告${RESET}"
    echo -e "  操作系统  ：$os_name $kernel_version"
    echo -e "  架构      ：$arch"
    echo -e "  Shell     ：$shell_name"
    echo -e "  工作目录  ：$(pwd)"
    echo -e "  用户      ：$user_name"
    echo -e "  脚本目录  ：$SCRIPT_DIR"

    # <按项目类型追加工具链版本检测>
    # 例：
    # echo -e "  Rust      ：$(rustc --version 2>/dev/null || echo '未安装')"
    # echo -e "  Node.js   ：$(node --version 2>/dev/null || echo '未安装')"

    separator

    verbose "以上是脚本检测到的运行环境。如果有信息不符合预期，请在继续前解决。"
}

# ──────────────────────────────────────────
# 依赖检查
# ──────────────────────────────────────────
check_deps() {
    step "检查依赖"
    verbose "确保所有必需的工具已安装且版本满足要求。"

    local all_ok=true

    # <按项目需求填充实际的工具链检查>
    # 模式示例：
    # if command -v <tool> &>/dev/null; then
    #     local ver=$(<tool> --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    #     ok "<tool> $ver"
    #     verbose "<tool> 是 <解释>。版本 $ver 满足最低要求 <min>。"
    # else
    #     error "未找到 <tool>"
    #     info "安装方式（复制粘贴即可）："
    #     info "  <具体安装命令>"
    #     info "安装后验证："
    #     info "  <tool> --version"
    #     all_ok=false
    # fi

    if [[ "$all_ok" == false ]]; then
        die "部分依赖缺失，请按上方提示安装后重新运行" \
            "  重新运行此脚本：$0 --check-only"
    fi

    ok "所有依赖满足"
}

# ──────────────────────────────────────────
# 加载 .env
# ──────────────────────────────────────────
load_dotenv() {
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        step "加载 .env 配置"
        verbose ".env 文件存放项目运行所需的环境变量（如数据库地址、API 密钥）。"
        verbose "这些配置因环境而异且通常含敏感信息，所以不提交到 Git，而是用 .env 在本地管理。"
        set -a
        # shellcheck disable=SC1091
        source "$SCRIPT_DIR/.env"
        set +a
        ok ".env 已加载"
    elif [[ -f "$SCRIPT_DIR/.env.example" ]]; then
        warn "检测到 .env.example 但没有 .env 文件"
        info "创建配置文件（复制粘贴即可）："
        info "  cp $SCRIPT_DIR/.env.example $SCRIPT_DIR/.env"
        info "然后编辑配置："
        info "  \${EDITOR:-nano} $SCRIPT_DIR/.env"
        info "当前使用内置默认值继续..."
        verbose ".env.example 是配置模板，你需要复制一份为 .env 并填入你自己的配置值。"
    fi
}

# ──────────────────────────────────────────
# 主操作（按脚本用途填充）
# ──────────────────────────────────────────
execute_main() {
    separator
    step "<主操作描述>"
    verbose "<解释这一步在做什么以及为什么>"

    if [[ "$DRY_RUN" == true ]]; then
        info "[模拟运行] 将要执行："
        info "  <实际会运行的命令>"
        return
    fi

    # <实际执行逻辑>

    ok "<操作完成确认>"
}

# ──────────────────────────────────────────
# 结果报告
# ──────────────────────────────────────────
report_results() {
    separator
    echo -e "${BOLD}${GREEN}✅ 完成${RESET}"
    echo ""
    # <报告执行结果的关键信息>
    # 例：
    # echo -e "  产物路径：./target/release/my-app"
    # echo -e "  访问地址：http://localhost:8080"
    echo ""
    suggest "后续操作："
    # <根据脚本类型提供下一步建议>
    # 例：
    # info "  查看日志：tail -f logs/app.log"
    # info "  停止服务：kill \$(cat .pid)"
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
    echo -e "${BOLD}<脚本名> — <用途描述>${RESET}"
    [[ "$VERBOSE" == true ]] && info "详细模式已开启：将解释每步操作的原因和背景"
    [[ "$DRY_RUN" == true ]] && info "模拟运行模式：只显示会做什么，不实际执行"

    report_env
    load_dotenv
    check_deps

    if [[ "$CHECK_ONLY" == true ]]; then
        separator
        ok "环境检查完成，所有依赖满足。"
        suggest "一切就绪，可以正式运行："
        info "  $0"
        exit 0
    fi

    execute_main
    report_results
}

main "$@"
```

---

### Nushell 脚本模板

```nushell
#!/usr/bin/env nu
# <脚本名> — <用途描述>
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
def suggest [msg: string] {
    print $"(ansi cyan)💡(ansi reset) ($msg)"
}
def verbose-msg [msg: string, is_verbose: bool] {
    if $is_verbose {
        print $"  (ansi cyan)💬(ansi reset) ($msg)"
    }
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
# 环境检测与报告
# ──────────────────────────────────────────
def report-env [is_verbose: bool] {
    separator
    step "检测运行环境"
    verbose-msg "脚本需要先了解当前系统环境，确保所有必需的工具和依赖都已就绪。" $is_verbose

    let host = (sys host)

    separator
    print $"(ansi bold)📋 环境报告(ansi reset)"
    print $"  操作系统  ：($host.name) ($host.kernel_version)"
    print $"  架构      ：($host.os_version)"
    print $"  工作目录  ：(pwd)"
    print $"  用户      ：(whoami)"

    # <按项目类型追加工具链版本>

    separator
    verbose-msg "以上是脚本检测到的运行环境。如果有信息不符合预期，请在继续前解决。" $is_verbose
}

# ──────────────────────────────────────────
# 主命令
# ──────────────────────────────────────────
def main [
    --verbose (-v)   # 详细模式：解释每步操作的原因和背景
    --check-only     # 只检查环境，不执行主操作
    --dry-run        # 模拟运行：显示会做什么，不实际执行
    ...args          # 传递给程序的额外参数
] {
    separator
    print $"(ansi bold)<脚本名> — <用途描述>(ansi reset)"
    if $verbose { info "详细模式已开启：将解释每步操作的原因和背景" }
    if $dry_run { info "模拟运行模式：只显示会做什么，不实际执行" }

    report-env $verbose

    # 加载 .env
    if (".env" | path exists) {
        step "加载 .env 配置"
        verbose-msg ".env 文件存放项目运行所需的环境变量。这些配置因环境而异，所以不提交到 Git。" $verbose
        open .env | lines
            | where { |l| ($l | str trim) != "" and not ($l | str starts-with "#") }
            | each { |l|
                let parts = ($l | split column "=" key value)
                load-env { ($parts.key.0): ($parts.value.0) }
            }
        ok ".env 已加载"
    } else if (".env.example" | path exists) {
        warn "检测到 .env.example 但没有 .env 文件"
        info "创建配置文件（复制粘贴即可）："
        info "  cp .env.example .env"
        info "然后编辑配置："
        info "  open .env"
        verbose-msg ".env.example 是配置模板，你需要复制一份为 .env 并填入你自己的配置值。" $verbose
    }

    # 依赖检查
    separator
    step "检查依赖"
    verbose-msg "确保所有必需的工具已安装且版本满足要求。" $verbose
    # <按项目需求填充检查逻辑>
    ok "所有依赖满足"

    if $check_only {
        separator
        ok "环境检查完成，所有依赖满足。"
        suggest "一切就绪，可以正式运行："
        info $"  ($env.CURRENT_FILE? | default '<script>')"
        return
    }

    # 主操作
    separator
    step "<主操作描述>"
    verbose-msg "<解释这一步在做什么以及为什么>" $verbose

    if $dry_run {
        info "[模拟运行] 将要执行："
        info "  <实际会运行的命令>"
        return
    }

    # <实际执行逻辑>

    # 结果报告
    separator
    print $"(ansi bold)(ansi green)✅ 完成(ansi reset)"
    suggest "后续操作："
    # <提供下一步建议>
}
```

---

## Step 3: 填充脚本逻辑

将 Step 0 分析出的所有信息填充进模板的占位区域，包括：

- `report_env()`：填充项目相关工具链的版本检测和报告
- `check_deps()`：填充实际的工具链检查、版本约束、系统依赖检查
- `execute_main()`：填充脚本的核心操作逻辑（构建/部署/处理/等）
- `report_results()`：填充执行结果报告和后续操作建议
- `usage()`：填充脚本实际支持的参数和示例
- 每个 `verbose()` 调用：填充对初学者友好的解释
- `.env` 变量列表：从 `.env.example` 提取，附上每个变量的说明和默认值

**所有提示质量标准**（不仅限于错误）：

| 提示类型 | 要求 |
|----------|------|
| **错误提示** | 说明为什么失败 + 给出具体修复命令 + 说明如何验证已修复 |
| **警告提示** | 说明潜在问题 + 给出预防/解决的具体命令 |
| **信息提示** | 附带可操作的下一步命令 |
| **建议提示** | 给出可直接复制粘贴执行的改进命令 |
| **verbose 解释** | 用日常类比解释概念 + 说明为什么需要这步 + 预防性提示 |

---

## Step 4: 验证与输出

生成完成后：

1. 检查脚本语法：
   ```bash
   bash -n <script>.sh          # Bash 语法检查
   nu --ide-check <script>.nu   # Nushell 语法检查（若适用）
   ```

2. 设置可执行权限（Bash/Nu）：
   ```bash
   chmod +x <script>.sh
   ```

3. 输出脚本到项目根目录（或 `target` 指定路径）

4. 生成使用说明摘要，直接输出到终端：

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
