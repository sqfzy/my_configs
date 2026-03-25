---
name: migrate
description: Guided migration and upgrade — dependency major version bumps, API breaking change adaptation, language edition upgrades, and build system migrations. Preserves compatibility through incremental steps with rollback points. Auto-saves migration report to .discuss/
TRIGGER when: user asks to upgrade a dependency, bump a major version, migrate an API, switch build systems, or adapt to breaking changes from a library/framework update.
DO NOT TRIGGER when: user is adding a new dependency (use /feature), or making internal design changes unrelated to external API/version changes (use /refactor or /refactor breaking for destructive internal redesign).
argument-hint: "<migration target> [strategy: incremental|big-bang] [dry-run] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*), Bash(sed:*)
---

# /migrate

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`

目标：$ARGUMENTS

---

## 核心原则

迁移的关键不是"改完"，而是**每一步都可回滚、可验证**。

> 大爆炸式迁移（改完所有再测）是灾难之源。每一步改动后构建通过、测试通过，才推进到下一步。

---

## 参数解析

- **迁移目标**（必填）：描述要迁移的内容，支持以下类型：
  - 依赖升级：`upgrade tokio to 2.0`、`bump spdlog`
  - 语言版本：`rust edition 2024`、`C++23 to C++26`
  - 构建系统：`cmake to xmake`、`pip to uv`
  - 框架迁移：`actix-web to axum`、`unittest to pytest`
  - API 适配：`migrate from deprecated API X to Y`
- `[strategy]`：
  - `incremental`（默认）：逐模块迁移，每步提交，新旧可共存
  - `big-bang`：一次性全量替换（仅适用于无法增量迁移的场景）
- `[dry-run]`：仅输出迁移计划和影响分析，不执行
- `[auto]`：无人值守模式——跳过迁移计划确认，直接执行；迁移中遇到三次修复仍失败时自动终止并回滚（而非暂停等待）

---

## Phase 0: 迁移前分析

### 0.1 当前状态快照

记录迁移前的完整状态：

```bash
mkdir -p .discuss

# 依赖版本锁定
cat Cargo.lock 2>/dev/null | head -100       # Rust
cat uv.lock 2>/dev/null | head -100          # Python
cat package-lock.json 2>/dev/null | head -100 # Node

# 当前构建和测试基线
git rev-parse HEAD 2>&1
```

**运行完整构建和测试，建立基线**：

```
若用户提供了构建/测试/benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与 benchmark 命令；若项目无测试或 benchmark 则跳过对应步骤。
```

- ✅ 全部通过 → 记录基线，继续
- ❌ 基线失败 → 终止：
  ```
  ❌ 迁移前基线未通过。请先修复现有问题再开始迁移。
  ```

**若存在 benchmark**，运行并记录基线。

### 0.2 迁移目标研究

根据迁移类型，收集必要信息：

**依赖升级**：
```bash
# 当前版本
grep "<dep_name>" Cargo.toml xmake.lua pyproject.toml package.json 2>/dev/null

# 查找项目中所有使用该依赖的位置
grep -rn "<dep_name>" --include="*.rs" --include="*.cpp" --include="*.py" --include="*.ts" --include="*.go" . | grep -v "target/" | grep -v "node_modules/" | grep -v ".git/"
```

阅读目标版本的：
- CHANGELOG / Release Notes（识别 breaking changes）
- Migration Guide（若有）
- 废弃 API 列表和替代方案

**语言版本升级**：
- 阅读 edition/version 的官方迁移指南
- 识别废弃特性和新替代方案
- 检查编译器警告中的 deprecation 提示

**构建系统迁移**：
- 完整阅读现有构建配置
- 列出所有构建目标、编译选项、依赖声明、自定义规则
- 识别平台特定配置

### 0.3 影响范围评估

```
## 迁移影响评估

### 迁移类型
<依赖升级 / 语言版本 / 构建系统 / 框架 / API>

### Breaking Changes 清单
| 序号 | 变更 | 影响范围 | 代码位置 | 适配方式 |
|------|------|----------|----------|----------|
| 1 | `foo()` 签名变更 | 12 处调用 | `src/*.rs` | 更新参数 |
| 2 | `Bar` 类型移至新模块 | 8 处 import | `src/*.rs` | 更新路径 |
| ... | ... | ... | ... | ... |

### 废弃 API 使用情况
| 废弃 API | 使用次数 | 替代方案 |
|----------|----------|----------|
| `old_fn()` | 5 | `new_fn()` |
| ... | ... | ... |

### 风险评估
- 总影响文件数：N
- Breaking change 数量：N
- 预估工作量：<小 / 中 / 大>
- 策略建议：<incremental / big-bang，附理由>
```

---

## Phase 1: 迁移计划

### 1.1 步骤拆解

将迁移拆分为**可独立验证的原子步骤**：

```
## 迁移计划

### 步骤概览
1. [准备] <创建迁移分支，添加兼容层 / feature flag>
2. [适配] <逐模块适配 breaking change #1>
3. [适配] <逐模块适配 breaking change #2>
4. [切换] <更新依赖版本 / 构建配置>
5. [清理] <移除兼容层、废弃代码、旧配置>
6. [验证] <全量测试 + benchmark>

### 每步详细计划

#### Step 1: <标题>
- 改动：<具体操作>
- 验证：<该步骤后的验证命令>
- 回滚：<若失败如何回滚>
- 提交信息：<预设的 commit message>
```

**增量策略（默认）**的关键技巧：

- **兼容层 / Adapter**：在旧接口和新接口之间加一层适配，让新旧代码可共存
  ```rust
  // 兼容层：旧签名委托到新实现
  #[deprecated(note = "Use new_fn() instead")]
  pub fn old_fn(x: i32) -> i32 {
      new_fn(x as i64) as i32
  }
  ```
- **Feature Flag**：用编译时 feature 控制新旧路径，逐模块切换
  ```toml
  [features]
  new-parser = []  # 启用新解析器
  ```
- **逐模块迁移**：按依赖图的叶子节点到根节点顺序迁移——先迁没人依赖的模块，最后迁核心模块

**大爆炸策略**（仅当无法增量时）：
- 在单独分支上一次性完成所有改动
- 必须有完整的测试覆盖作为安全网
- 在计划中标记回滚方案

### 1.2 用户确认

```
✋ 迁移计划已就绪，共 N 步。
   回复「继续」开始执行。
   回复「dry-run」仅查看计划。
   回复并修改具体步骤。
```

**在此处暂停，等待用户确认。**

**`auto` 模式**：不暂停，直接按计划执行。若迁移失败则自动回滚到迁移前状态并终止。

若指定 `dry-run`，输出完整计划后终止。

---

## Phase 2: 分步执行

### 创建迁移分支

```bash
git checkout -b migrate/<简短描述> 2>&1
```

### 逐步执行

```
for each step in 迁移计划:
    1. 执行改动
    2. 构建验证：根据项目构建系统执行编译/导入验证（若用户提供了命令则优先使用）
    3. 若构建失败 → 分析错误，修复，重试
    4. 运行测试：根据项目配置执行测试（若用户提供了命令则优先使用）
    5. 测试结果：
       ✅ 通过 → 提交该步骤，继续下一步
       ❌ 失败 → 区分原因：
          - 迁移适配遗漏 → 修复，重试
          - 新版本行为变化（预期中的） → 更新测试，记录
          - 新版本 bug → 记录，评估是否继续
          - 三次修复仍失败 → 暂停，告知用户（`auto` 模式：自动回滚到上一个成功的 commit 并终止）
    6. 提交：
       git add -A && git commit -m "<预设的 commit message>"
```

**每步提交**，确保每个 commit 都是可构建、可测试的状态。这样出问题时可以精确 `git bisect`。

### 语言特定注意事项

**Rust 依赖升级**：
- `cargo update -p <crate>` 更新单个依赖
- 检查 `cargo clippy` 是否有新的 lint 警告（新版 clippy 可能更严格）
- Edition 升级用 `cargo fix --edition` 自动迁移，再手动检查结果

**C++ 构建系统迁移**：
- 逐目标迁移：先迁库，再迁可执行文件，最后迁测试
- 确认编译选项完全等价（优化级别、warning 设置、sanitizer）
- 确认 `#include` 搜索路径和链接库路径正确

**Python 依赖升级**：
- `uv lock --upgrade-package <pkg>` 精确升级
- 检查类型标注兼容性（新版可能添加或修改类型）
- 检查运行时行为变化（默认参数、异常类型变更）

---

## Phase 3: 全量验证

所有步骤执行完毕后，运行完整验证：

### 构建 + 测试

```
若用户提供了构建/测试/lint 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与静态检查命令；若项目无测试或 linter 则跳过对应步骤。
```

### Benchmark 回归

若 Phase 0 记录了 benchmark 基线，重新运行并对比：

```
若用户提供了 benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行 benchmark 命令；若无 benchmark 则跳过。
```

- 无退化 → 继续
- 退化 ≥5% → 分析原因，告知用户：
  ```
  ⚠️ 迁移后 benchmark 退化：
  - <benchmark>：<基线> → <当前>（退化 X%）
  可能原因：<分析>
  ```

### 功能验证

若项目有可运行的 demo / example：
```bash
# 运行示例，确认功能正常
cargo run --example <name> 2>&1
python examples/<name>.py 2>&1
```

---

## Phase 4: 清理

### 移除迁移脚手架

- 删除兼容层 / adapter 代码
- 删除 feature flag（若已全量启用）
- 删除 `#[allow(deprecated)]` / `#pragma warning(disable: ...)` 等临时抑制
- 清理不再需要的旧依赖声明

### 最终验证

清理后再跑一轮完整构建 + 测试，确认清理未引入问题。

### 提交清理

```bash
git add -A
git commit -m "chore: remove migration scaffolding"
```

---

## Phase 5: 迁移报告

```bash
mkdir -p .discuss
```

写入 `.discuss/migrate-YYYYMMDD-HHMMSS.md`：

```markdown
# Migration Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 迁移类型：<依赖升级 / 语言版本 / 构建系统 / 框架 / API>
- 迁移目标：<描述>
- 策略：incremental / big-bang
- 迁移分支：<branch name>

## 迁移前后对比

| 维度 | 迁移前 | 迁移后 |
|------|--------|--------|
| <依赖/语言/构建系统> 版本 | <旧> | <新> |
| 构建状态 | ✅ | ✅ |
| 测试（通过/总数） | N/N | N/N |
| Benchmark | <基线> | <结果> |

## Breaking Changes 适配记录

| 变更 | 影响文件数 | 适配方式 | 备注 |
|------|------------|----------|------|
| <描述> | N | <如何改的> | <注意事项> |

## 执行步骤记录

| 步骤 | 描述 | Commit | 状态 |
|------|------|--------|------|
| 1 | <描述> | <hash> | ✅ |
| 2 | <描述> | <hash> | ✅ |

## 遇到的问题

### 问题 1：<标题>
- 现象：<描述>
- 原因：<分析>
- 解决：<如何处理>

## 后续建议
- <是否有废弃 API 警告需要后续处理>
- <是否需要更新文档（/doc）>
- <是否建议用 /improve 对迁移后的代码做深度打磨>
- <是否有其他依赖也需要升级>
```

写入完成后输出：
`✓ 迁移报告已保存至 .discuss/migrate-YYYYMMDD-HHMMSS.md`

---

输出语言跟随用户输入语言。
