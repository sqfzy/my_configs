## Target：setup（安装 / 部署 / 自举脚本）

**适用**：项目初始化、环境搭建、依赖安装、从零到可用的自动化。典型例子：`setup.sh`、`bootstrap.sh`、`install.sh`、`deploy.sh`。

**与普通 task 的核心差异**：setup 经常**部分成功部分失败** —— 装完 A 装 B 时挂了。必须具备**可恢复 + 幂等重跑 + 回滚**能力，这是 setup 脚本的生死线。

---

### 独有的必执行章节

#### 1. 前置检查（Preflight）

在真正做事之前，**先完整检查所有前置条件**，一次性展示给用户：

```
Preflight checks:
  ✓ bash >= 5.0          (found 5.2.15)
  ✓ git                  (found 2.43.0)
  ✓ python3 >= 3.11      (found 3.12.1)
  ✗ docker               (missing)
  ⚠ 2GB free disk space  (found 1.5GB)

Missing: docker
Please install and re-run.
```

**原则**：
- 一次性列出所有问题，不是"第一个缺什么就挂"
- 每项检查有版本要求时要校验
- 缺失项给出**可操作的安装建议**（如 `apt install docker.io` / `brew install docker`）
- 所有检查通过才进入实际安装

#### 2. 步骤清单（Plan）

在执行前打印"将要做什么"，让用户确认：

```
Setup plan:
  Step 1/7: Clone repo to /opt/myapp
  Step 2/7: Create config at /etc/myapp.conf
  Step 3/7: Install systemd service
  Step 4/7: Start service
  ...

This will write to /opt, /etc, and /var/log.
Continue? [y/N]
```

- 每步有编号（N/M 格式）
- 用户明确看到会写入哪些地方
- `--yes` / `--auto` 可跳过确认

#### 3. 检查点 / 状态追踪

setup 中途失败 → 重跑能跳过已完成步骤：

```
# 状态文件：.setup-state.json
{
  "steps_done": ["clone", "config"],
  "timestamp": "..."
}
```

重跑时：
- 读状态文件
- 已完成的步骤跳过（可 `--force` 重做）
- 从第一个未完成步骤开始

**幂等性铁律**：每个步骤必须幂等——即使状态文件丢失，重跑也不会"装两次"。

#### 4. 回滚 / Undo

setup **必须有对应的回滚脚本**（或同一脚本的 `--uninstall` 模式）：
- 列出创建 / 修改的所有资源
- 按逆序清理
- 不清理用户数据（除非明确 `--purge`）
- 回滚本身也要**幂等**（未装就别报错）

#### 5. 健康检查（Post-install verify）

安装完成后**主动验证**：
- 服务是否启动
- 端口是否监听
- 配置是否正确加载
- 关键命令是否可用

打印健康检查结果，失败明确说明"哪步失败 + 怎么排查"。

---

### 独有的维度权重

| 维度 | 权重 | 原因 |
|------|------|------|
| 幂等 | **极高** | setup 重跑是常态 |
| 回滚 | **高** | 装错能撤销 |
| 日志 | **高** | 出问题能排查 |
| Dry-run | **高** | 看清楚要装什么 |
| 进度 | **高** | setup 通常耗时长 |
| 确认 | **高** | 涉及系统级改动 |

---

### 独有的 ASCII 图示要求

- **setup 流程图**：在 `--help` 或脚本头部注释中画出步骤图
- **状态机图**：若步骤之间有依赖 / 分支，画状态机说明"从哪步到哪步、失败回到哪"
- **目录改动图**：列出脚本会创建 / 修改的路径树

---

### 独有的反模式

- ❌ 不做 preflight 就开始装（装到一半发现缺依赖）
- ❌ 无状态追踪，失败重跑从头开始
- ❌ 没有 uninstall / 回滚方案
- ❌ 改系统级配置不备份原文件
- ❌ 步骤之间无进度，用户不知道在哪
- ❌ 安装完不做验证就说"成功"
- ❌ 失败错误消息只写"failed"没说怎么办
- ❌ 强制要 root 但不提前检查（让用户输完 sudo 密码才报错）
- ❌ 静默覆盖用户已有配置（必须先备份并告知）

---

### setup 脚本骨架模板

```bash
#!/usr/bin/env bash
# Setup script for <project>
# Usage: ./setup.sh [--dry-run] [--yes] [--uninstall] [-v]

set -euo pipefail

readonly STATE_FILE=".setup-state"

# ───────────────────────── 工具 ─────────────────────────
log_info()  { echo "[INFO] $*" >&2; }
log_warn()  { echo "[WARN] $*" >&2; }
log_error() { echo "[ERROR] $*" >&2; }
die()       { log_error "$*"; exit 1; }

# ───────────────────────── 前置检查 ─────────────────────
preflight() {
  local missing=0
  log_info "Running preflight checks..."

  command -v bash >/dev/null || { log_error "bash missing"; ((missing++)); }
  command -v git  >/dev/null || { log_error "git missing"; ((missing++)); }
  # ...

  [[ $missing -eq 0 ]] || die "Preflight failed: $missing check(s) missing."
  log_info "✓ All preflight checks passed."
}

# ───────────────────────── 状态 ─────────────────────────
load_state() { ... }
save_state() { ... }
is_done()    { ... }
mark_done()  { ... }

# ───────────────────────── 步骤 ─────────────────────────
step_clone()   { is_done clone && return; ...; mark_done clone; }
step_config()  { is_done config && return; ...; mark_done config; }
# ...

# ───────────────────────── 回滚 ─────────────────────────
uninstall() {
  log_info "Rolling back..."
  # 按逆序清理
}

# ───────────────────────── 验证 ─────────────────────────
verify() {
  log_info "Post-install verification..."
  # ...
}

# ───────────────────────── main ─────────────────────────
main() {
  # 参数解析
  # ...

  if [[ "${UNINSTALL:-}" == "1" ]]; then
    uninstall
    exit 0
  fi

  preflight
  print_plan
  confirm_unless_yes

  step_clone
  step_config
  # ...

  verify
  log_info "✓ Setup complete."
}

main "$@"
```
