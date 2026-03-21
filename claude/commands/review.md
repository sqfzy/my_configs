---
description: Structured code review — analyzes a diff, PR, branch, or specific files and produces actionable review feedback organized by severity. Read-only by default; does not modify code unless explicitly asked. Auto-saves review report to .discuss/
argument-hint: "<diff source> [severity: critical|all] [focus: security|perf|correctness|style|all]"
allowed-tools: Bash(git:*), Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /review

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
最近 5 次提交：!`git log --oneline -5 2>&1`

输入：$ARGUMENTS

---

## 核心原则

Review 是**只读操作**——输出的是给人看的反馈，不是直接改代码。

目标不是挑刺，而是：
1. 拦截真正的缺陷（逻辑错误、安全漏洞、资源泄漏）
2. 识别隐患（缺失的错误处理、未覆盖的边界条件）
3. 提出可操作的改进建议（附具体代码位置和修改方向）

**不做的事**：
- 不纠结纯风格偏好（除非违反项目已有约定）
- 不建议"为了抽象而抽象"的重构
- 不输出"looks good"之类的空泛评价——每条反馈都必须指向具体代码

---

## 参数解析

### Diff 来源（必填，从 `$ARGUMENTS` 推断）

| 模式 | 格式 | 行为 |
|------|------|------|
| **分支对比** | `branch: <name>` 或分支名 | `git diff main...<branch>` |
| **最近 N 次提交** | `last: N` 或 `last N` | `git diff HEAD~N..HEAD` |
| **暂存区** | `staged` | `git diff --cached` |
| **工作区** | `working` 或 `wip` | `git diff` |
| **两个 ref 之间** | `<ref1>..<ref2>` | `git diff <ref1>..<ref2>` |
| **指定文件** | `file: <path>` 或文件路径 | 对该文件做全量审查（非 diff 模式） |
| **无参数** | 空 | 自动选择：暂存区有内容则 review 暂存区，否则 review 工作区变更 |

### 可选参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `severity: critical` | 仅输出 critical 和 major 级别 | `all` |
| `focus: <领域>` | 聚焦特定审查维度（可逗号分隔多个） | `all` |

---

## Step 0: 获取 Diff 与上下文

### 0.1 获取变更

根据参数确定 diff 来源，获取完整 diff：

```bash
# 示例：分支对比
git diff main...<branch> 2>&1
git log main...<branch> --oneline 2>&1
```

**若 diff 为空**：
```
✅ 无变更可审查。请确认 diff 来源是否正确。
```
终止。

### 0.2 变更概览

生成变更统计：

```bash
git diff <source> --stat 2>&1
git diff <source> --numstat 2>&1
```

记录：
- 变更文件数
- 总增删行数
- 变更最集中的文件（按 diff 行数排序）

### 0.3 上下文加载

对每个变更文件，读取**周边上下文**——不只看 diff 行，还要理解：

- 被修改函数的完整实现（diff 前后各扩展 30 行）
- 被修改类型/结构体的完整定义
- 相关的测试文件（若存在）
- 该模块的公共接口声明

这一步至关重要：脱离上下文的 diff 审查会产生大量误判。

---

## Step 1: 逐文件审查

对每个变更文件，按以下维度逐一审查。根据 `focus` 参数决定审查维度——未指定则全部执行。

### 1.1 正确性 (Correctness)

- **逻辑错误**：条件判断是否正确？off-by-one？短路求值顺序？
- **边界条件**：空输入、零值、最大值、溢出、空集合
- **错误处理**：
  - 新增的 `unwrap()` / `expect()` / 裸 `.get()` 是否合理？是否应改为 `?` 或 `match`？
  - `Result` / `Option` 是否被静默忽略（`let _ = ...`）？
  - C++：`std::expected` 是否被正确传播？异常安全性？
- **并发安全**：新增的共享状态是否有正确的同步？`Send` / `Sync` 约束？
- **资源管理**：文件句柄、锁、网络连接是否在所有路径（含错误路径）上正确释放？

### 1.2 安全性 (Security)

- **输入验证**：来自外部的输入是否被校验（长度、格式、范围）？
- **注入风险**：字符串拼接是否可能引入 SQL / 命令 / 路径注入？
- **敏感数据**：日志中是否泄漏密钥、令牌、密码、PII？
- **unsafe 块**（Rust）：是否有 safety 注释？不变量是否真正成立？
- **未定义行为**（C++）：悬垂引用、use-after-move、有符号溢出？
- **依赖安全**：新引入的依赖是否已知存在漏洞？

### 1.3 性能 (Performance)

- **热路径影响**：改动是否在关键路径上引入了不必要的开销？
- **内存分配**：循环内是否有可避免的堆分配？`clone()` 是否可以用引用替代？
- **算法复杂度**：是否将 O(n) 变成了 O(n²)？集合类型选择是否合理？
- **I/O 模式**：是否引入了不必要的同步阻塞？批量操作是否可行？
- **编译期计算**（C++）：可以 `constexpr` / `consteval` 的是否遗漏了？

### 1.4 可观测性 (Observability)

基于项目约定检查：
- **Rust**：非平凡函数是否添加了 `#[instrument(err)]`？关键路径是否有 `tracing` 日志？
- **C++**：是否使用 `spdlog` 记录了 ERROR 分支和关键入口/出口？`SPDLOG_ACTIVE_LEVEL` 是否正确？
- **通用**：错误日志是否包含足够上下文（变量值、参数、状态），而非仅 "error occurred"？

### 1.5 测试覆盖 (Test Coverage)

- 新增的逻辑是否有对应测试？
- 新增的错误路径是否有测试覆盖？
- 边界条件是否被测试？
- 测试命名是否描述了场景（`test_parse_empty_input_returns_error`，而非 `test1`）？
- **若新增代码完全没有测试**，标记为 major 问题

### 1.6 设计与可维护性 (Design)

- **接口设计**：新增的公共 API 是否符合最小暴露原则？参数是否合理？
- **抽象层级**：是否引入了不必要的抽象？是否有明显应提取但未提取的重复？
- **命名**：新增的名称是否准确传达意图？是否与项目约定一致？
- **注释**：非显然逻辑是否有注释解释 **why**？
- **Commit 粒度**：（若审查多个 commit）每个 commit 是否代表一个逻辑变更？

---

## Step 2: 跨文件审查

单文件审查完成后，从全局视角检查：

### 2.1 一致性

- 新代码与项目已有代码的风格是否一致？（错误处理模式、命名约定、日志风格）
- 是否在不同文件中对同一问题采用了不同的解决方式？

### 2.2 遗漏检测

- 是否有应该同步修改但未修改的文件？（调用方、配置文件、文档）
- 是否有新增的公共接口缺少文档注释？
- 构建配置是否需要更新？（新文件是否加入了 `xmake.lua` / `Cargo.toml` 等）

### 2.3 架构影响

- 本次变更是否改变了模块间的依赖方向？
- 是否引入了循环依赖？
- 变更是否让某个模块的职责变得模糊？

---

## Step 3: 构建与测试验证（若适用）

若审查的是本地分支或工作区变更（而非远程 PR），主动运行构建和测试：

```
Rust：   cargo build 2>&1 && cargo test 2>&1 && cargo clippy -- -W clippy::all 2>&1
C++：    xmake build 2>&1 && xmake test 2>&1
Python： uv run pytest 2>&1 && uv run ruff check . 2>&1
Node：   npm run build 2>&1 && npm test 2>&1
Go：     go build ./... 2>&1 && go test ./... 2>&1 && go vet ./... 2>&1
```

若存在与变更相关的 benchmark，运行并记录结果（供 review 意见参考，不做 pass/fail 判断）。

将构建/测试结果纳入审查报告——编译器和 linter 发现的问题直接归入对应的 review 条目。

---

## Step 4: 生成 Review 报告

### 4.1 问题分类与输出

每条 review 意见使用以下格式：

```
### [严重程度] 标题

**文件**：`<file>:<line>`
**类型**：正确性 / 安全性 / 性能 / 可观测性 / 测试 / 设计
**描述**：<具体问题是什么，为什么这是问题>
**建议**：<具体怎么改，给出修改方向或代码片段>
```

**严重程度定义**：

| 级别 | 含义 | 要求 |
|------|------|------|
| 🔴 **Critical** | 会导致运行时错误、数据损坏、安全漏洞 | 必须修复后才能合并 |
| 🟡 **Major** | 缺失的错误处理、缺失的测试、性能退化风险 | 强烈建议修复 |
| 🔵 **Minor** | 命名改进、日志补充、可选的结构优化 | 建议改进，不阻塞 |
| 💬 **Nit** | 纯偏好建议、微小的可读性改善 | 可忽略 |

**输出顺序**：Critical → Major → Minor → Nit。若指定了 `severity: critical`，省略 Minor 和 Nit。

### 4.2 Review 摘要

在所有条目之前，先输出全局摘要：

```
## Review 摘要

### 变更概况
- 文件数：<N>
- 增删：+<X> / -<Y>
- 主要变更：<一句话描述做了什么>

### 总体评价
<2–3 句话：变更的整体质量、设计方向是否正确、最需要关注的问题>

### 问题统计
- 🔴 Critical：N
- 🟡 Major：N
- 🔵 Minor：N
- 💬 Nit：N

### 结论
<APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION>
- APPROVE：无 Critical，Major ≤ 1 且不涉及正确性/安全性
- REQUEST_CHANGES：存在 Critical 或 Major 正确性/安全性问题
- NEEDS_DISCUSSION：存在需要作者澄清意图才能判断的设计决策
```

### 4.3 亮点（可选）

若变更中有值得肯定的做法——巧妙的错误处理、良好的抽象、充分的测试覆盖——简要提及。好的 review 不只找问题：

```
## 亮点
- `<file>:<line>`：<具体描述好在哪里>
```

---

## Step 5: 保存报告

```bash
mkdir -p .discuss
```

将完整报告写入 `.discuss/review-YYYYMMDD-HHMMSS.md`：

```markdown
# Code Review Report

## 元信息
- 时间：<review 开始时间>
- 耗时：<X 分 Y 秒>
- Diff 来源：<branch / last N / staged / file>
- 审查范围：<文件列表>
- 审查维度：<all / 指定的 focus>
- 构建状态：✅ 通过 / ❌ 失败 / ⏭️ 未执行
- 测试状态：✅ 全部通过 / ❌ N 个失败 / ⏭️ 未执行

---

<Review 摘要>

---

<所有 Review 条目，按严重程度排序>

---

<亮点（若有）>

---

## Diff 统计
\```
<git diff --stat 输出>
\```
```

写入完成后输出：
`✓ Review 报告已保存至 .discuss/review-YYYYMMDD-HHMMSS.md`

---

## 追加操作

Review 完成后，若用户希望直接修复 review 中发现的问题，告知：
```
如需自动修复 review 中的问题：
- Critical / Major 正确性问题 → 建议用 /debug 追踪修复
- 结构性建议 → 建议用 /refactor 执行
- 全面打磨 → 建议用 /self-evolution 迭代
```

---

输出语言跟随用户输入语言。
