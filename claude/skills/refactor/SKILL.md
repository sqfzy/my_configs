---
name: refactor
description: "Targeted structural refactoring — restructures code while preserving behavior by default. With [breaking] mode, supports destructive design-level refactoring (API reshape, architecture restructure, core abstraction replacement) with migration strategy and checkpoint commits. Auto-saves refactoring report to .artifacts/ TRIGGER when: user asks to refactor, extract function/module, inline, rename, split, merge, or move code; user wants to redesign internal architecture, reshape APIs, or replace core abstractions (use [breaking] mode). DO NOT TRIGGER when: user is upgrading dependencies, changing language editions, or switching frameworks (use /migrate); user wants broad quality improvement (use /improve); user is fixing a specific bug (use /fix)."
argument-hint: "<refactoring intent> [target: <file or module>] [breaking] [no-commit] [dry-run] [auto]"
allowed-tools: Bash(mkdir:*), Bash(date:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /refactor

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`

意图：$ARGUMENTS

---

## 核心原则

### 默认模式

重构的唯一目标是**改变代码结构，不改变外部行为**。整个流程围绕一条铁律：

> 测试在重构前通过，重构后必须仍然通过，且测试本身不被修改。

若重构过程中需要修改测试，说明行为发生了变化——此时应暂停并引导用户：
```
⚠️ 测试失败表明行为发生了变化。
若你确实需要改变代码设计（接口重塑、架构重组、核心抽象替换），请使用：
  /refactor breaking <意图>
```

### breaking 模式

当指定 `[breaking]` 时，切换到**破坏性重构**流程——允许改变外部行为，但每项行为变更必须被**显式声明和验证**。

铁律变为：

> 行为变更必须在迁移计划中预先声明。未声明的行为变化仍视为 bug，必须修复。

breaking 模式与默认模式的关键差异：

| 维度 | 默认模式 | breaking 模式 |
|------|----------|---------------|
| 行为约束 | 不可变 | 可变，但必须声明 |
| 分支策略 | 当前分支 | 自动创建 `refactor/<name>` 分支 |
| 测试策略 | 不修改测试 | 旧测试按计划更新，新测试覆盖新行为 |
| 迁移计划 | 无需 | 必须输出行为变更清单和分阶段迁移计划 |
| 提交策略 | 完成后一次提交 | 每个迁移检查点自动提交 |
| commit footer | 无 | 包含 `BREAKING CHANGE:` |

> **注意**：若变更是由外部依赖升级、语言版本变化、框架替换驱动的，应使用 `/migrate` 而非 `/refactor breaking`。`breaking` 模式用于**内部设计层面**的破坏性重构。

---

## 参数解析

- `[target: <path>]`：指定重构目标文件或模块；未指定则从意图描述中推断
- `[breaking]`：启用破坏性重构模式——允许改变外部行为，自动创建分支，检查点提交，要求声明行为变更清单
- `[no-commit]`：完成后不自动提交
- `[dry-run]`：仅输出重构计划和影响分析，不执行任何代码改动
- `[auto]`：无人值守模式——跳过方案确认直接执行；性能退化时自动回滚该改动并继续；默认模式下行为变化时自动回滚并终止；breaking 模式下未声明的行为变化自动回滚并终止

---

## Phase 0: 基线建立

在触碰任何代码之前，先建立安全基线。

### 0.1 运行现有测试

```
若用户提供了构建/测试/benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与 benchmark 命令；若项目无测试或 benchmark 则跳过对应步骤。
```

**结果处理**：
- ✅ 全部通过 → 记录测试数量和耗时作为基线，继续
- ❌ 存在失败 → **终止重构**，输出：
  ```
  ❌ 基线测试未通过，重构前必须先修复现有失败。
  建议使用 /debug 定位并修复这些失败，然后重新执行 /refactor。
  ```

### 0.2 Benchmark 基线

检测项目是否存在 benchmark：

```bash
# Rust
find . -path "*/benches/*.rs" -o -name "*.rs" -exec grep -l "#\[bench\]" {} \; 2>/dev/null | head -10
# C++
find . -name "*.cpp" -exec grep -l "BENCHMARK" {} \; 2>/dev/null | head -10
# Python
find . -name "bench_*.py" -o -name "*_bench.py" 2>/dev/null | head -10
```

**若存在与重构目标相关的 benchmark**：
```
若用户提供了 benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行 benchmark 命令。**按 bench-data 约定持久化**到 `.artifacts/`（来源标注：`/refactor 基线`）。若无 benchmark 则跳过。
```

记录基线数据，Phase 4 将用于对比。若无相关 benchmark 则跳过，注明"无 benchmark 覆盖"。

### 0.3 记录当前状态

```bash
mkdir -p .artifacts
git stash list 2>&1  # 确认没有未保存的 stash 干扰
```

记录基线信息：
- 测试通过数量
- Benchmark 基线数据（若有）
- 当前 HEAD commit hash
- 工作区是否干净（若有未提交改动，提示用户先提交或 stash）

### 0.4 创建重构分支（仅 breaking 模式）

```bash
# 从意图描述中生成简短分支名
git checkout -b refactor/<简短描述> 2>&1
```

声明：`▶ breaking 模式：已创建分支 refactor/<name>，所有改动将在此分支上执行。`

---

## Phase 1: 代码阅读与重构意图分析

### 1.1 理解目标代码

深入阅读 target 指定的文件（若未指定，从用户的意图描述中定位相关文件）。理解：

- 该模块的**职责**：它做什么，为谁服务
- **公共接口**：哪些函数/类型/trait 被外部依赖
- **内部结构**：数据流、控制流、核心抽象
- **调用方**：谁依赖这段代码（`grep` 搜索引用关系）

```bash
# 查找所有调用方
grep -rn "<函数名/模块名/类型名>" --include="*.rs" --include="*.py" --include="*.ts" --include="*.cpp" --include="*.go" . | grep -v "target/" | grep -v "node_modules/"
```

### 1.2 识别重构类型

从用户的意图描述中识别具体的重构操作，归类为以下一种或多种：

| 类型 | 描述 | 风险等级 |
|------|------|----------|
| **提取** (Extract) | 函数提取、模块拆分、接口提取（trait/interface） | 低 |
| **内联** (Inline) | 消除不必要的间接层、合并过度拆分的小函数 | 低 |
| **重命名** (Rename) | 变量/函数/类型/模块更名，贯穿所有引用 | 低 |
| **移动** (Move) | 将函数/类型移至更合适的模块 | 中 |
| **拆分** (Split) | 将一个大文件/模块拆为多个 | 中 |
| **合并** (Merge) | 将分散的相关代码合并到一处 | 中 |
| **抽象变更** (Restructure) | 替换数据结构、改变继承/组合关系、引入设计模式 | 高 |
| **接口重塑** (Reshape API) | 改变公共接口签名但保持语义等价 | 高 |

声明：`重构类型：<类型> | 风险等级：<低/中/高> | 目标范围：<文件列表>`

### 1.2.1 行为变更清单（仅 breaking 模式）

在 breaking 模式下，必须在此阶段声明所有预期的行为变更：

```
## 行为变更清单

| 序号 | 变更描述 | 影响范围 | 旧行为 | 新行为 | 调用方适配方式 |
|------|----------|----------|--------|--------|----------------|
| 1 | `process()` 签名变更 | 12 处调用 | 接受 `&str` | 接受 `Input` | 包装为 `Input::from()` |
| 2 | `Config` 拆为 `Config` + `Runtime` | 8 处引用 | 单一配置 | 编译期/运行期分离 | 按用途引用对应类型 |
```

**未在此清单中声明的行为变化仍视为 bug**——在 Phase 4 验证阶段如果出现未声明的测试失败，必须修复而非更新测试。

### 1.3 影响范围分析

列出本次重构将涉及的所有文件，分为：

```
## 影响范围

### 直接修改
- `<file>` — <改动描述>

### 间接受影响（调用方需同步更新）
- `<file>:<line>` — 引用了 <被重构的符号>

### 不受影响（已确认）
- `<module>` — 无依赖关系
```

**若影响范围超过 10 个文件**，提醒用户：
```
⚠️ 本次重构影响 N 个文件，建议分阶段执行。是否继续？
```

---

## Phase 2: 重构方案设计与评审

### 2.1 方案设计

输出重构方案：

```
## 重构方案

### 目标
<一句话：重构要达成什么结构改善>

### 当前结构
<简要描述现状的问题>

### 目标结构
<描述重构后的代码组织方式>

### 操作步骤
<按执行顺序列出每一步具体操作，粒度到函数/类型级别>
1. ...
2. ...

### 不变量
<明确列出重构前后必须保持不变的东西>
- 公共 API 签名：<不变 / 变更并同步调用方>
- 行为语义：不变
- 错误处理逻辑：不变
- 性能特征：不变（或注明预期变化）
```

### 2.2 快速对抗评审

针对重构方案，进行 **3 个角色、2 轮** 的快速评审。

从角色库中选出 3 个角色：

!`cat ~/.claude/skills/shared/roles.md`

**讨论聚焦**：
- 这个重构是否必要？是否存在更简单的替代方案？
- 步骤拆解是否足够原子化？每步之后代码是否仍可编译？
- 是否有遗漏的调用方或隐式依赖？

每轮每个角色的发言中额外包含：
```
质疑 / 肯定：...（指向具体的重构步骤或代码位置）
建议修改：...
```

**评审结论**：
```
## 评审结论
- 采纳的建议：<列表>
- 拒绝的建议：<列表，附原因>
- 方案修订：<若有>
- 风险提醒：<需要特别注意的点>
```

### 2.3 用户确认

输出：
```
✋ 重构方案已就绪，影响 N 个文件。
   回复「继续」开始执行，或提出修改意见。
   回复「dry-run」仅查看计划不执行。
```

**在此处暂停，等待用户确认。**

**`auto` 模式**：不暂停，直接按方案执行。

若指定了 `dry-run` 参数，在此处输出完整计划后终止，不进入 Phase 3。

---

## Phase 3: 分步执行

按 Phase 2 确定的步骤逐一执行。

### 执行原则

**原子化**：每一步完成后代码必须可编译。绝不批量改动后才验证。

**执行节奏**：

**默认模式**：
```
for each step in 重构步骤:
    1. 执行改动
    2. 编译验证（根据项目构建系统执行）
    3. 若编译失败 → 立即修复，不继续下一步
    4. 编译通过 → 记录该步完成，继续下一步
```

**breaking 模式**（每步提交作为检查点）：
```
for each step in 重构步骤:
    1. 执行改动
    2. 编译验证
    3. 若编译失败 → 修复，重试
    4. 运行测试：
       - 测试失败且在行为变更清单中 → 更新对应测试，记录
       - 测试失败但不在变更清单中 → 视为 bug，修复代码而非测试
       - 三次修复仍失败 → 暂停，告知用户（auto 模式：回滚到上一个检查点并终止）
    5. 编译+测试通过 → 提交检查点：
       git add <本次改动的具体文件> && git commit -m "refactor(<scope>): step N — <描述>"
```

**语言特定注意事项**：

**Rust**：
- `pub` 可见性变更需同步更新 `mod` 声明和 `use` 路径
- 移动类型时注意 trait impl 块和 `From`/`Into` 实现是否跟随
- `cfg` 条件编译块中的引用容易遗漏
- 移动带 `#[instrument(err)]` 的函数时，确认 `tracing` 的 `use` 声明跟随

**C++**：
- 头文件移动需更新所有 `#include` 路径
- 命名空间变更需检查 `using` 声明和 `friend` 声明
- 模板特化和 concept 约束可能分布在多处，移动时需全部同步
- 移动含 `spdlog` 日志的代码时，确认 `SPDLOG_ACTIVE_LEVEL` 宏和 logger 初始化仍可达
- header-only 模块的移动需检查是否引入循环 include

**Python**：
- 移动函数/类后检查 `__init__.py` 的 `__all__` 导出
- 相对导入和绝对导入需保持一致
- 装饰器和元类引用需同步更新

**通用**：
- 重命名时使用全词匹配搜索，避免误改子串（如 `get` 匹配到 `get_all`）
- 移动代码时保留原位置的 re-export（若有外部调用方），后续统一清理
- 字符串中的引用（日志消息、错误消息中的函数名）也要更新

---

## Phase 4: 全量验证

所有步骤执行完毕后，运行完整测试套件：

```
若用户提供了构建/测试/lint 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与静态检查命令；若项目无测试或 linter 则跳过对应步骤。
```

**结果处理**：

- ✅ 全部通过 → 与基线对比：
  - **默认模式**：测试数量一致（重构不应增减测试）
  - **breaking 模式**：测试数量可以变化，但每项变化必须对应行为变更清单中的条目
  - 无新增 warning / lint 错误
  - → 进入 Benchmark 回归检查

### Benchmark 回归检查

**若 Phase 0 记录了 benchmark 基线**，重新运行相同的 benchmark：

```
若用户提供了 benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行 benchmark 命令。**按 bench-data 约定持久化**到 `.artifacts/`（来源标注：`/refactor 验证`）。若无 benchmark 则跳过。
```

对比基线数据：
- **无显著退化（<5% 波动）** → 进入 Phase 5
- **性能退化 ≥5%** → ⚠️ 暂停，输出对比结果，分析原因：
  - 若退化源于新增的间接调用层 → 考虑内联优化或调整方案
  - 若退化源于内存布局变化 → 评估是否可接受
  - 告知用户：
    ```
    ⚠️ Benchmark 检测到性能退化：
    - <benchmark_name>：基线 <X>ns → 当前 <Y>ns（退化 Z%）
    是否接受此退化？[接受 / 优化后继续 / 回滚]
    ```

**`auto` 模式**：自动回滚引起退化的改动，在报告中记录，继续后续步骤。

**若 Phase 0 无 benchmark 基线**，跳过此检查，在报告中注明"无 benchmark 覆盖，性能影响未验证"。

→ 进入 Phase 5

- ❌ 测试失败 → 分析失败原因：
  - **引用路径未更新** → 修复遗漏的引用，重新验证
  - **行为变化** → ⚠️ 这说明重构改变了语义，必须定位原因：
    - 若是实现 bug（重构手误）→ 修复
    - 若是设计层面的行为变化 → 暂停，告知用户：
      ```
      ⚠️ 测试 <test_name> 失败，表明重构改变了行为：
      - 预期：<expected>
      - 实际：<actual>
      这超出了纯重构的范畴。是否继续（需同步更新测试）？还是回滚？
      ```
    **`auto` 模式**：自动回滚所有改动并终止，在报告中记录行为变化的详情。
  - **三次修复仍无法通过** → 回滚所有改动：
    ```bash
    git checkout -- .
    ```
    输出失败原因和建议，终止。

- ⚠️ Clippy / lint 警告 → 逐一处理

---

## Phase 5: 清理与提交

### 5.1 清理

- 移除重构过程中留下的临时 re-export（若调用方已全部迁移）
- 移除空文件、空模块
- 确认没有遗留的 `// TODO: refactor` 注释
- 确认 `use` / `import` 语句中没有未使用的引入

### 5.2 最终验证

再次运行完整测试，确认清理没有破坏任何东西。

### 5.3 提交

除非指定 `no-commit`，生成提交信息并执行：

**默认模式**：
```
refactor(<scope>): <subject>

<body: 重构了什么、为什么重构、关键结构变化>
```

**breaking 模式**（注意：分步检查点已在 Phase 3 中提交，此处为最终清理提交）：
```
refactor!(<scope>): <subject>

<body: 重构了什么、为什么重构、关键结构变化>

BREAKING CHANGE: <逐条列出行为变更清单中的每项变更及其影响>
```

**禁止使用 `git add -A` 或 `git add .`——必须逐文件 add，避免暴露 .env、credentials 等敏感文件或意外的大文件。**

```bash
git add <本次改动的具体文件> && git commit -m "<generated message>"
```

输出：`✅ 已提交 <short-hash>: <subject>`

---

## Phase 6: 重构报告

按产物存储约定输出以下报告：

```markdown
# Refactor Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 重构类型：<Extract / Rename / Split / ...>
- 风险等级：<低 / 中 / 高>
- 目标：<一句话>

## 重构前后对比

### 结构变化
\```
Before:
  <原始文件/模块结构>

After:
  <重构后文件/模块结构>
\```

### 影响统计
- 直接修改文件：N 个
- 间接更新（调用方）：N 个
- 新增文件：<列表>
- 删除文件：<列表>
- 净行数变化：+X / -Y

## 关键改动

### 改动 1：<描述>
\```diff
<核心 diff 片段>
\```
为什么这样改：<解释>

### 改动 2：...

## 验证结果
- 基线测试：<N> 个通过
- 重构后测试：<N> 个通过（数量一致 ✅ / 有差异 ⚠️）
- Lint / Clippy：✅ 无新增警告
- Benchmark：✅ 无退化 / ⚠️ <benchmark> 退化 X%（已接受/已优化） / ℹ️ 无 benchmark 覆盖

## 评审摘要
- 参与角色：<列表>
- 采纳的建议：<列表>
- 主要争议：<简述>

## 后续建议
- <是否有进一步可做的结构优化>
- <是否暴露了需要 /improve 跟进的质量问题>
- <重构是否揭示了缺失的测试场景>
```

---

输出语言跟随用户输入语言。
