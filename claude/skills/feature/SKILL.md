---
name: feature
description: "End-to-end feature development from scratch — clarifies requirements, designs architecture, implements with tests, verifies, and commits. TRIGGER when: user asks to implement a new feature, add a new module/component, or build non-trivial new functionality from scratch. DO NOT TRIGGER when: user is fixing a bug (use /fix), refactoring existing code (use /refactor), or requirements are highly ambiguous (use /design)."
argument-hint: "<feature description> [no-commit] [no-tests] [target: <path>] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(head:*), Bash(mkdir:*), Bash(date:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /feature

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`

需求：$ARGUMENTS

---

按以下流程执行。**Phase 1 和 Phase 2 必须经用户确认后才能推进到 Phase 3**。

---

## 参数解析

- `[no-commit]`：完成后不自动提交，仅实现代码
- `[no-tests]`：跳过测试编写（不推荐，仅用于 spike/探索性实现）
- `[target: <path>]`：新功能的目标模块或目录
- `[auto]`：无人值守模式——跳过所有交互确认，自动继续（需求不确定点按最保守理解处理，设计方案直接执行）

---

## Phase 1: 需求理解 & 边界澄清

### 1.1 理解现有代码库

在理解需求之前，先阅读项目关键文件，建立上下文：
- 构建配置（依赖、feature flags）
- 相关模块的现有接口
- 项目的代码风格约定（命名、错误处理模式、注释风格）

### 1.2 需求分析

对用户的需求描述进行拆解，明确以下内容并输出：

```
## 需求理解

### 核心目标
<一句话：这个功能要解决什么问题>

### 功能边界
**In scope（本次实现）**：
- ...

**Out of scope（明确不做）**：
- ...

### 输入 / 输出
- 输入：<数据类型、来源、约束>
- 输出：<数据类型、格式、副作用>

### 边界条件 & 错误情况
- <空输入 / 超大输入 / 并发访问 / 权限不足 / ...>

### 与现有代码的集成点
- <需要修改或扩展的现有接口>
- <需要新增的模块或文件>

### 不确定点（需用户确认）
- [ ] <问题1>
- [ ] <问题2>
```

若存在不确定点，**在此处暂停，等待用户回答**，再继续。

**`auto` 模式**：不暂停，对每个不确定点选择最保守的理解（功能范围最小、约束最严格的解读），并在输出中标注 `[auto: 保守假设]`。

---

## Phase 2: 设计方案

需求边界确认后，进行架构设计，并用 `/discuss` 的多角色对抗逻辑评审设计方案。

### 2.1 方案设计

输出设计文档：

```
## 设计方案

### 核心数据结构
\```<lang>
// 关键类型定义（伪代码或真实代码）
\```

### 模块结构
\```
新增 / 修改的文件：
  <path>  —  <职责>
  <path>  —  <职责>
\```

### 接口设计
\```<lang>
// 对外暴露的公共接口（函数签名、trait、类定义）
\```

### 实现策略
<分步骤描述实现顺序，说明为什么这样拆解>

### 关键设计决策
- 决策1：<选择了X而非Y，原因是...>
- 决策2：...
```

### 2.2 设计评审（多角色对抗）

针对上述设计，进行快速对抗评审。默认 **3 个角色，2 轮**，聚焦设计阶段的核心分歧，快速收敛。

#### 角色选择

从角色库中选出 3 个角色：

!`cat ~/.claude/skills/shared/roles.md`

每轮每个角色的发言中额外包含：
```
质疑 / 肯定：...（须指向具体设计决策，如数据结构选择、接口签名、模块划分）
建议改动：...
```

#### 评审结论

```
## 评审结论
- 采纳的建议：<列表，说明采纳理由>
- 拒绝的建议：<列表，说明拒绝原因>
- 设计修订：<若有，描述具体变更>
- 未解决的权衡：<若有，留待实现阶段决策>
```

### 2.3 用户确认

输出：
```
✋ 设计方案已就绪。确认后开始实现。
   回复「继续」开始编码，或直接提出修改意见。
```

**在此处暂停，等待用户确认。**

**`auto` 模式**：不暂停，直接采纳评审后的设计方案开始实现。

---

## Phase 3: 测试先行（TDD）

除非指定 `no-tests`，先写测试，再写实现。

### 3.0 Benchmark 基线（若存在）

在写任何实现代码之前，检测并记录现有 benchmark 基线：

```bash
find . -path "*/benches/*.rs" -o -name "*.cpp" -exec grep -l "BENCHMARK" {} \; -o -name "bench_*.py" 2>/dev/null | head -10
```

**若存在 benchmark**：运行并保存基线，Phase 5 用于回归对比。
**若不存在**：跳过，在最终报告中注明"无 benchmark 覆盖"。

### 3.1 测试用例设计

在写任何实现代码之前，列出测试场景：

```
测试用例清单：
  [ ] happy path: <描述>
  [ ] 边界条件: <空输入 / 最大值 / 临界值>
  [ ] 错误路径: <各类错误的触发和处理>
  [ ] 集成场景: <与现有模块的交互>（若适用）
```

### 3.2 编写测试骨架

创建测试文件，写出所有测试函数的骨架（编译通过但全部 `#[ignore]` 或 `todo!()`）：

```
Rust：  src/<module>/tests.rs 或 tests/<feature>_test.rs
C++：   tests/<feature>_test.cpp
Python：tests/test_<feature>.py
```

验证测试骨架能编译通过：
```
根据项目构建系统，验证测试代码能编译/收集通过（不实际运行）。
```

---

## Phase 4: 增量实现

按设计方案分步实现，每完成一个独立单元即运行相关测试验证。

### 实现顺序原则

1. **核心数据结构优先**：先定义类型，让编译器辅助验证设计
2. **由内向外**：先实现纯逻辑函数，再实现 I/O 和集成层
3. **每步可编译**：每次改动后立即验证编译通过，不积累编译错误
4. **逐步解除 `todo!()`**：每实现一个函数，同步取消对应测试的 ignore，确认测试通过

### 语言特定要求

**Rust**：
- 错误处理使用 `std::error::Error` 或项目已有的 error 类型，不使用裸 `unwrap()`（除非在测试或确定不会失败的位置）
- 添加 `#[instrument(err)]`（若项目使用 `tracing`）
- unsafe 块必须附有 safety 注释

**C++**：
- 遵循项目已有的内存管理约定（RAII / 智能指针）
- 模板边界使用 concepts（C++20）
- 使用 `spdlog` 记录关键路径日志（若项目已引入）

**通用**：
- 非显然逻辑必须有注释，说明**为什么**而非**是什么**
- 日志覆盖关键函数入口/出口（DEBUG 级别）和所有错误分支（ERROR/WARN 级别）

---

## Phase 5: 全量验证

实现完成后，运行完整测试套件：

```
若用户提供了构建/测试/lint 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与静态检查命令；若项目无测试或 linter 则跳过对应步骤。
```

**结果处理**：
- ✅ 全部通过 → 运行 Benchmark 回归检查（若 Phase 3.0 记录了基线），然后进入 Phase 6
  - 无退化 → 继续
  - 退化 ≥5% → 告知用户，分析原因，决定是否接受/优化/回滚
  - 无基线 → 跳过，报告中注明
- ❌ 失败 → 修复，不跳过，重新验证（参考 `/debug` 的根因追踪逻辑）
- ⚠️ Clippy / lint 警告 → 逐一处理，不允许 `#[allow(...)]` 压制警告（除非有充分理由且附注释）

---

## Phase 6: 收尾 & 提交

### 6.1 自查清单

在提交前逐项确认：

```
[ ] 所有测试通过（包括已有测试，无回归）
[ ] 没有遗留的 todo!() / unimplemented!() / fixme 注释（除非是设计上的占位）
[ ] 没有调试用的临时 println! / eprintln! / console.log
[ ] 公共接口有文档注释（/// 或 /** */）
[ ] 错误信息是可操作的（包含上下文，而非"error occurred"）
[ ] 新文件已加入构建系统（xmake.lua / Cargo.toml / CMakeLists.txt）
```

### 6.2 提交

除非指定 `no-commit`，执行提交：

生成符合 Conventional Commits 规范的 message：

```
feat(<scope>): <subject>

<body: 为什么做这个功能，关键设计决策摘要>

<footer: BREAKING CHANGE 若有>
```

```bash
git add -A
git commit -m "<generated message>"
```

输出：`✅ 已提交 <short-hash>: <subject>`

### 6.3 开发摘要

输出本次功能开发的完整摘要：

```markdown
## 功能开发完成

### 实现概况
- 功能：<一句话>
- 新增文件：<列表>
- 修改文件：<列表>
- 测试用例：<N 个，覆盖 happy path / 边界 / 错误路径>
- 提交：<hash>

### 关键设计决策
- <决策1>
- <决策2>

### 已知限制 & 后续建议
- <Out of scope 中的内容，若有优先级建议可注明>
- 建议后续用 `/improve` 对本模块做完整打磨
```

---

输出语言跟随用户输入语言。
