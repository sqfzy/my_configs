---
name: fix
description: "End-to-end bug fix workflow — traces root cause, implements fix, adds regression test, and commits with proper message. Combines /debug → /test → /git into a single disciplined pipeline where no step can be skipped. Auto-saves fix report to .artifacts/ TRIGGER when: user reports a bug, error, crash, panic, test failure, or unexpected behavior and wants it fixed; user pastes error output/stack trace and asks to resolve it. DO NOT TRIGGER when: user only asks what caused an error without wanting a fix, or is building new functionality (use /design)."
argument-hint: "[error text | file: <path> | run] [target: <file>] [no-commit] [auto]"
allowed-tools: Bash(mkdir:*), Bash(date:*), Bash(cat:*), Bash(find:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /fix

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`
现有测试文件：!`find . -type f \( -name "*_test.rs" -o -name "*_test.cpp" -o -name "test_*.py" -o -name "*.test.ts" -o -name "*_test.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -20`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`
Plan 感知：!`cat ~/.claude/skills/shared/plan-aware.md`
现有计划：!`find . -name "*.plan.md" 2>/dev/null | grep -v node_modules | grep -v target | grep -v .git | grep -v .artifacts | head -10 || echo "(无)"`

输入：$ARGUMENTS

---

## 核心理念

修 bug 不是改到不报错就完了。一个合格的 fix 必须：

1. **定位根因**——修根因，不修症状
2. **验证修复**——构建通过、测试通过
3. **补回归测试**——确保同样的 bug 不会再出现
4. **提交记录**——commit message 说清楚修了什么、为什么

跳过任何一步都是技术债。本命令强制执行完整流程。

---

## 参数解析

**错误来源**（与 `/debug` 一致）：

| 模式 | 格式 | 行为 |
|------|------|------|
| **直接粘贴** | 错误文本本身 | 直接使用 |
| **日志文件** | `file: <path>` | 读取指定文件内容 |
| **自动捕获** | `run` 或参数为空 | 自动检测项目类型并运行构建/测试，捕获输出 |

**可选参数**：

| 参数 | 说明 |
|------|------|
| `[target: <path>]` | 将根因分析聚焦到指定文件或模块 |
| `[no-commit]` | 完成后不自动提交 |
| `[auto]` | 无人值守模式——自动选择候选 1 的 commit message，不暂停询问 |

---

## 流程总览

```
┌──────────────────────────────────────────────────┐
│  Phase 1: 定位与修复（← /debug）                 │
│  错误捕获 → 分类 → 根因追踪 → 假设验证 → 修复   │
└──────────────────┬───────────────────────────────┘
                   │ 修复通过构建 + 现有测试
                   ▼
┌──────────────────────────────────────────────────┐
│  Phase 2: 回归测试（← /test edge）               │
│  设计测试用例 → 编写 → 运行 → 确认全量通过       │
└──────────────────┬───────────────────────────────┘
                   │ 新测试覆盖了触发条件
                   ▼
┌──────────────────────────────────────────────────┐
│  Phase 3: 提交（← /git）                         │
│  生成 commit message → 提交 → 更新 CHANGELOG     │
└──────────────────────────────────────────────────┘
```

每个 Phase 的进入条件是前一个 Phase 完全通过。任何一步失败都不跳过——修到通过为止。

---

## Phase 1: 定位与修复

### 1.0 错误捕获

解析 `$ARGUMENTS`，确定错误来源。

**自动捕获时**，按以下顺序检测并执行：
```
若用户提供了构建/测试命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建与测试命令（注意：此处用 ; 分隔以收集所有输出）；若项目无测试则跳过测试步骤。
```

若构建/测试**全部通过**：
```
✅ 构建和测试均通过，未发现错误。如需修复特定行为，请直接粘贴相关输出。
```
终止。

记录开始时间。

### 1.1 错误分类

| 类型 | 特征 | 后续策略 |
|------|------|----------|
| **编译错误** | 类型错误、未定义符号、语法错误 | 直接定位出错行 |
| **链接错误** | undefined reference、symbol not found | 检查依赖声明和构建配置 |
| **运行时 panic** | panic! / segfault / stack overflow / OOM | 追踪调用栈 |
| **测试失败** | assertion failed、expected/got | 比较预期与实际，追溯数据流 |
| **逻辑错误** | 输出不符合预期但无 crash | 追踪数据变换路径 |
| **间歇性错误** | flaky test、race condition | 识别并发/时序依赖 |

提取错误的**最深层 cause**（通常不是第一行），定位到具体文件、函数、行号。

声明：`错误类型：X | 直接位置：<file>:<line> | 疑似根因区域：<描述>`

### 1.2 根因追踪

从直接位置出发，向上追溯调用链，向下检查被调用的逻辑。

**追踪策略按错误类型选择**：

- **编译错误**：读取出错上下文（前后 20 行），追踪类型定义来源
- **运行时 panic**：逐帧分析调用栈，重点检查 `unwrap()`/`expect()`、数组越界、空指针
- **测试失败**：读取测试代码 → 追踪被测函数完整数据流 → 对比预期/实际差异
- **间歇性错误**：检查共享状态访问模式，识别缺失的同步原语

列出 1–3 个根因假设，按可能性排序：

```
假设 1（最可能）：<具体描述，指向代码位置>
  证据：<支持该假设的代码特征>

假设 2：<...>
```

### 1.3 假设验证

对每个假设，用最小代价验证，**不要还没验证就开始改代码**：

1. **静态分析**：重新阅读代码，逻辑推演
2. **添加临时日志**：关键路径插入 `eprintln!` / `stderr`，重新运行
3. **最小复现**：构造能稳定触发的最小输入
4. **注释隔离**：临时注释可疑代码块，确认错误消失

确认根因：
```
✅ 根因确认：<描述>
位置：<file>:<line> / <function>
触发条件：<什么情况下会触发>
影响范围：<仅此处 / 多处调用方受影响>
```

若所有假设均被排除 → 扩展检查构建配置、依赖版本、环境差异。

### 1.4 修复实施

**修复原则**：
- 修复根因，不修复症状
- 若根因影响多处调用方，一次性全部修复
- 若修复涉及接口变更，同步更新所有调用方
- 临时添加的调试日志**全部清除**
- 间歇性错误修复后添加注释说明并发语义

### 1.5 修复验证

```
若用户提供了构建/测试/benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与 benchmark 命令；若项目无测试或 benchmark 则跳过对应步骤。
```

**结果处理**：
- ✅ 全部通过 → 记录修复内容，进入 **Phase 2**
- ❌ 原错误仍存在 → 回到 1.2 重新审视根因假设
- ❌ 出现新错误 → 检查修复是否引入回归，优先回滚再重新分析
- ⚠️ 间歇性错误 → 运行 3 次以上，说明复现率变化

---

## Phase 2: 回归测试

> 修复没有测试保护的 bug，等于在同一个地方埋下第二次踩坑的可能。

### 2.1 测试用例设计

基于 Phase 1 确认的根因和触发条件，设计回归测试——**测试必须在修复前失败、修复后通过**：

```
回归测试清单：
  [ ] <函数名>_<触发条件描述>
      输入：<Phase 1 确认的触发输入>
      预期：<修复后的正确行为>
      验证：<该测试在修复前确实会失败>
```

**测试设计原则**：

1. **精确复现触发条件**：测试输入必须精确命中根因路径，不是泛泛的 happy path
2. **断言具体行为**：断言具体的返回值/错误类型，不只是 `is_ok()` / `is_err()`
3. **最小化依赖**：回归测试应尽可能是单元测试；若根因涉及集成场景则写集成测试
4. **补充相邻边界**：除了精确复现外，额外补 1–2 个相邻边界条件的测试

### 2.2 编写测试

按项目约定放置测试文件：

```
Rust：  同文件 #[cfg(test)] mod tests / tests/<module>_test.rs
C++：   tests/<module>_test.cpp
Python：tests/test_<module>.py
Go：    <module>_test.go
```

**命名规范**：测试名必须描述场景：
- ✅ `test_parse_empty_input_returns_error`
- ✅ `test_process_handles_u32_max_without_overflow`
- ❌ `test_fix_123`、`test_regression`

**结构**（Arrange-Act-Assert）：
```
// Arrange: 构造 Phase 1 确认的触发输入
// Act: 调用被修复的函数
// Assert: 验证修复后的正确行为
```

**语言特定**：

**Rust**：
- panic 路径用 `#[should_panic(expected = "...")]`
- 枚举变体用 `assert_matches!` 或 `matches!`
- 错误路径断言具体的错误变体，不只是 `is_err()`

**C++**：
- `EXPECT_*` 优于 `ASSERT_*`
- `std::expected` 错误路径用 `EXPECT_FALSE(result.has_value())` + `EXPECT_EQ(result.error(), ...)`

**Python**：
- 异常路径用 `pytest.raises(SpecificError)`
- 参数化用 `pytest.mark.parametrize`

### 2.3 编译验证

先确认测试能编译通过：

```
根据项目构建系统，验证测试代码能编译/收集通过（不实际运行）。
```

### 2.4 运行与全量回归

运行新增测试，再运行全量测试：

```
若用户提供了测试命令则优先使用；否则根据项目构建系统和配置，自行确定并执行测试命令。
```

**结果处理**：
- ✅ 全部通过 → 进入 **Phase 3**
- ❌ 新增测试失败 → 区分原因：
  - 测试本身写错（预期值不正确）→ 修正测试
  - 修复不完整（未覆盖所有路径）→ 回到 Phase 1.4 补充修复
- ❌ 已有测试失败 → 修复引入了回归，回到 Phase 1.4 修正

---

## Phase 3: 提交

若指定了 `no-commit`，跳过本 Phase，输出修复摘要后终止。

### 3.1 Diff 分析与 Commit Message 生成

分析暂存区变更，生成符合 [Conventional Commits](https://www.conventionalcommits.org/) 的 message。

**类型**：几乎总是 `fix`。若修复过程中附带了小范围重构，仍用 `fix`（主意图是修复）。

**格式**：
```
fix(<scope>): <subject，50 字符以内>

<body: 根因是什么，为什么这样修，而非只说改了什么>

<footer: Closes #N（若能从 branch 名或注释推断 issue 号）>
```

**scope** 从修复涉及的模块/文件路径自动推断。

生成 **2 个候选**：

```
── 候选 1（推荐）──────────────────────────────
fix(parser): handle empty input without panic

parse_input() called unwrap() on an empty string split, causing a
panic when the input contained no delimiters. Switch to
split().next().unwrap_or_default() and return ParseError::EmptyInput.

Adds regression test for empty and whitespace-only inputs.

── 候选 2（最简）──────────────────────────────
fix(parser): return error on empty input instead of panicking
```

询问用户：`使用候选 1？[1/2/e(自己输入)/回车默认1]`

**`auto` 模式**：直接使用候选 1，不询问。

### 3.2 执行提交

**禁止使用 `git add -A` 或 `git add .`——必须逐文件 add，避免暴露 .env、credentials 等敏感文件或意外的大文件。**

```bash
git add <本次改动的具体文件> && git commit -m "<confirmed message>"
```

输出：`✅ 已提交 <short-hash>: <subject>`

### 3.3 CHANGELOG 更新

若项目根目录存在 `CHANGELOG.md`，在 `[Unreleased]` 的 `### Fixed` 段落追加一条：

```markdown
### Fixed
- <面向用户的语言描述修复了什么，而非内部实现细节>
```

若不存在 `CHANGELOG.md`，跳过。

---

## Phase 4: 修复报告

按产物存储约定输出以下报告：

```markdown
# Fix Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 错误类型：<编译 / panic / 测试失败 / 逻辑错误 / 间歇性>
- 提交：<hash> / ⏭️ no-commit

## 原始错误
\```
<完整错误输出，截断至 50 行>
\```

## 根因分析

### 根因
<为什么会发生，不只是在哪里发生>

### 触发条件
<什么输入/状态/时序导致此错误>

### 排除的假设
- <假设 → 排除原因>

## 修复

### 改动摘要
| 文件 | 改动 |
|------|------|
| `<file>` | <描述> |

### 关键 Diff
\```diff
<核心 diff，10–30 行>
\```

### 修复逻辑
<为什么这样修，而不只是改了什么>

## 回归测试
| 测试 | 覆盖目标 | 结果 |
|------|----------|------|
| `test_<name>` | <触发条件> | ✅ |
| ... | ... | ... |

## 验证结果
- 构建：✅ / ❌
- 全量测试：✅ N 个通过 / ❌ N 个失败

## 后续建议
- <是否有类似模式在其他地方存在，可能存在同类 bug>
- <是否暴露了缺失的测试覆盖，建议 /test 补充>
- <是否暴露了设计缺陷，建议 /improve 跟进>
```

---

## 异常流程处理

### 根因无法在合理时间内确认

若经过充分分析仍无法确认根因：

```
⚠️ 根因未确认。当前最可能的假设：
  <假设描述>
  
建议：
  - 使用 /debug 进行更深入的独立调试
  - 使用 /discuss 对根因假设进行多角色对抗分析
```

终止，不进入 Phase 2。已有的分析记录仍保存到 `.artifacts/`。

### 修复引入了无法解决的回归

若修复后反复出现新的测试失败，且三次尝试无法同时满足旧测试和新修复：

```
⚠️ 修复与现有行为存在冲突，需要更大范围的重构。

已完成的分析：
  - 根因：<描述>
  - 修复方向：<描述>
  - 冲突点：<哪些现有测试与修复方向矛盾>

建议：
  - 使用 /discuss 讨论设计层面的解决方案
  - 使用 /refactor 进行必要的结构调整后再修复
```

回滚所有改动，保存分析报告后终止。

---

输出语言跟随用户输入语言。
