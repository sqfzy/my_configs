---
name: ship
description: "Pre-release quality gate — runs structured code review, fills test coverage gaps, checks performance baselines, updates documentation, and commits/tags. A disciplined release checklist that blocks shipping until every step passes. Auto-saves ship report to .artifacts/ TRIGGER when: user says ready to ship/release/publish, asks for pre-release checks, or wants to tag a version. DO NOT TRIGGER when: user just wants a code review (use /review), or wants to commit without release ceremony (use /git)."
argument-hint: "<diff source> [skip: bench|doc] [no-push] [tag: <version>] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*), Bash(sed:*)
---

# /ship

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
最近 10 次提交：!`git log --oneline -10 2>&1`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`
现有文档：!`find . -maxdepth 3 \( -name "README*" -o -name "CHANGELOG*" -o -name "*.md" -o -name "docs" -type d \) ! -path "*/.git/*" ! -path "*/target/*" ! -path "*/node_modules/*" 2>/dev/null | head -20`
现有 benchmark：!`find . -type f \( -path "*/benches/*" -o -name "bench_*.py" -o -name "*_bench.go" -o -name "*.bench.ts" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" 2>/dev/null | head -10`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`
Blueprint 感知：!`cat ~/.claude/skills/shared/blueprint-aware.md`
现有计划：!`find .artifacts -name "blueprint-*.md" 2>/dev/null | head -10 || echo "(无)"`

Bench 感知：!`cat ~/.claude/skills/shared/bench-aware.md`

目标：$ARGUMENTS

---

## 核心理念

发版不是 `git push` 加祈祷。每次 ship 之前必须过五关：

1. **Review**——变更中有没有漏洞、遗漏、隐患
2. **Test**——测试覆盖是否充分，有没有盲区
3. **Bench**——性能有没有退化
4. **Doc**——文档是否跟上了代码变化
5. **Git**——commit 干净、CHANGELOG 更新、tag 打好

任何一关不过，不发版。这个清单的价值在于**不靠记忆靠流程**。

---

## 参数解析

### Diff 来源（必填）

与 `/review` 一致，从 `$ARGUMENTS` 推断：

| 模式 | 格式 | 行为 |
|------|------|------|
| **分支对比** | `branch: <name>` 或分支名 | `git diff main...<branch>` |
| **最近 N 次提交** | `last: N` 或 `last N` | `git diff HEAD~N..HEAD` |
| **两个 ref 之间** | `<ref1>..<ref2>` | `git diff <ref1>..<ref2>` |
| **无参数** | 空 | 自动取最近的 tag 到 HEAD；若无 tag 则 `last 10` |

### 可选参数

| 参数 | 说明 |
|------|------|
| `[skip: bench]` | 跳过 benchmark 检查（项目无 benchmark 时自动跳过） |
| `[skip: doc]` | 跳过文档更新（仅内部重构、无公共接口变更时可用） |
| `[no-push]` | 完成后不推送 |
| `[tag: <version>]` | 提交后打 tag（如 `v1.2.0`） |
| `[auto]` | 无人值守模式——Gate 1 阻断时自动终止（而非等待修复）；性能退化时自动终止；直接使用生成的 commit message |

---

## 流程总览

```
┌──────────────────────────────────────────────────┐
│  Gate 1: 代码审查（委托 /review auto）             │
│  调用 /review → 提取结论 → 判定通过/阻断          │
├────────────────────┬─────────────────────────────┤
│  无 Critical       │  有 Critical                │
│         ↓          │  → ❌ 阻断，必须先修复       │
│         ↓          └─────────────────────────────┘
│  Gate 2: 测试覆盖（← /test gaps）                 │
│  覆盖分析 → 补充缺失测试 → 全量通过               │
├────────────────────┬─────────────────────────────┤
│  全量通过          │  失败                        │
│         ↓          │  → ❌ 阻断，修到通过          │
│         ↓          └─────────────────────────────┘
│  Gate 3: 性能基线（← /bench baseline）            │
│  运行 benchmark → 对比基线 → 无显著退化            │
├────────────────────┬─────────────────────────────┤
│  无退化 / 跳过     │  退化 ≥5%                    │
│         ↓          │  → ⚠️ 暂停，用户决策          │
│         ↓          └─────────────────────────────┘
│  Gate 4: 文档同步（委托 /doc auto）         │
│  调用 /doc → 审计 + 更新 → 提取结果               │
├──────────────────────────────────────────────────┤
│  Gate 5: 提交与发布（← /git）                     │
│  commit → CHANGELOG → tag → push                 │
└──────────────────────────────────────────────────┘
```

---

## Gate 1: 代码审查（委托 /review）

**不在此处重复审查逻辑——委托给 `/review`，使用其完整方法论。**

### 1.1 执行审查

执行 `/review auto <diff source>`，对当前变更进行代码审查。

`/review` 将按其自身方法论完成：逐文件审查（正确性、安全性、性能、可观测性、测试覆盖、设计）→ 跨文件审查 → 构建与测试验证 → 生成审查报告。

### 1.2 Gate 通过判定

从 `/review` 的输出中提取结论（APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION）和问题统计（Critical / Major / Minor / Nit 数量），按以下标准判定：

- ✅ **通过**：结论为 APPROVE，或无 Critical 且无 Major → 继续 Gate 2。Minor 和 Nit 记录到最终 Ship 报告，不阻断。
- ❌ **阻断**：结论为 REQUEST_CHANGES 且存在 Critical 或 Major 问题 → 不继续后续 Gate。输出问题清单后暂停，等待用户修复后重新运行。

**`auto` 模式**：阻断时不暂停，直接终止并将审查报告保存到 `.artifacts/`。退出码非零，便于脚本检测失败。

```
## Gate 1 结果

（引用 /review 输出的问题统计和结论）

🔴 Critical：N | 🟡 Major：N | 🔵 Minor：N | 💬 Nit：N

<若阻断>：
❌ Gate 1 未通过。存在 N 个 Critical / Major 问题需修复。
建议使用 /fix 或 /debug 处理后重新执行 /ship。
```

---

## Gate 2: 测试覆盖

### 2.1 覆盖分析

聚焦 diff 范围内的变更代码，分析测试覆盖缺口：

- 对每个变更的公共函数，检查是否有对应测试
- 对新增的代码路径（条件分支、match arms、错误路径），检查测试是否覆盖
- 对修改的逻辑，检查现有测试是否仍然覆盖了修改后的行为

```
## 覆盖分析

| 变更函数 | 正常路径 | 边界条件 | 错误路径 | 缺口 |
|----------|----------|----------|----------|------|
| `foo()` | ✅ | ❌ | ✅ | 边界条件 |
| `bar()` | ✅ | ✅ | ❌ | 错误路径 |
| `new_fn()` | ❌ | ❌ | ❌ | 完全无测试 |
```

### 2.2 补充测试

对每个缺口编写测试：

- 命名描述场景：`test_<函数>_<条件>_<预期>`
- 结构遵循 Arrange-Act-Assert
- 错误路径断言具体错误类型，不只是 `is_err()`
- 边界条件从类型约束系统性推导（0、1、-1、MAX、空集合、超长输入等）

### 2.3 全量验证

若用户提供了构建/测试/lint 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与静态检查命令；若项目无测试或 linter 则跳过对应步骤。

**结果处理**：
- ✅ 全部通过 → 继续 Gate 3
- ❌ 失败 → 修复，不跳过。区分：
  - 新增测试发现了真实 bug → 记录 🐛，修复代码，重新验证
  - 测试本身写错 → 修正测试
  - 新增测试导致已有测试失败 → 分析回归原因，修复

```
## Gate 2 结果

- 覆盖缺口：N 个
- 新增测试：M 个
- 发现缺陷：K 个 🐛
- 全量测试：✅ P 个通过
```

---

## Gate 3: 性能基线

**自动跳过条件**：项目无 benchmark，或用户指定 `skip: bench`。跳过时在报告中注明 `ℹ️ 无 benchmark 覆盖，性能影响未验证`。

### 3.1 确定基线

```bash
# 查找最近的基线文件
ls -t .artifacts/bench-data-*.txt 2>/dev/null | head -1
```

- **有已保存的基线** → 使用该基线
- **无基线** → 在 diff 起点（tag / base commit）运行 benchmark 建立基线：
  ```bash
  git stash 2>&1
  git checkout <base-ref> 2>&1
  # 运行 benchmark，保存结果
  git checkout - 2>&1
  git stash pop 2>&1
  ```

### 3.2 运行当前 benchmark

若用户提供了 benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行 benchmark 命令，结果 tee 到 .artifacts/bench-data-ship.txt；若无 benchmark 则跳过。

### 3.3 对比

```
## Gate 3 结果

| Benchmark | 基线 | 当前 | 变化 | 判定 |
|-----------|------|------|------|------|
| <name> | <X>ns | <Y>ns | -8% | ✅ 改善 |
| <name> | <X>ns | <Y>ns | +2% | ➡️ 持平 |
| <name> | <X>ns | <Y>ns | +12% | ⚠️ 退化 |

判定标准：✅ 改善 >5% | ➡️ 持平 ±5% | ⚠️ 退化 5–15% | 🔴 严重退化 >15%
```

**结果处理**：
- 全部 ✅ 或 ➡️ → 继续 Gate 4
- 存在 ⚠️ 或 🔴 → 暂停，输出对比和可能的原因分析，由用户决策：
  ```
  ⚠️ 检测到性能退化：
  - <benchmark>：<基线> → <当前>（退化 X%）
  可能原因：<分析>
  
  [接受退化继续 / 优化后重新检查 / 终止]
  ```

**`auto` 模式**：性能退化时自动终止，在报告中记录退化详情。不自动接受退化——无人值守时宁可中断也不放过性能回归。

---

## Gate 4: 文档同步（委托 /doc）

**自动跳过条件**：用户指定 `skip: doc`。跳过时在报告中注明 `ℹ️ 文档更新已跳过`。

**不在此处重复文档生成逻辑——委托给 `/doc`，使用其完整方法论。**

### 4.1 执行文档更新

执行 `/doc auto`，对当前变更进行文档审计和更新。

`/doc` 将按其自身方法论完成：文档现状审计（README、CHANGELOG、API 注释覆盖率）→ 按需更新受变更影响的文档（CHANGELOG、API 文档注释、README）→ 文档测试验证 → 生成文档报告。

### 4.2 Gate 通过判定

从 `/doc` 的审计输出和文档报告中提取结果，确认文档已同步更新：

- CHANGELOG 是否已包含本次变更的条目
- 新增/修改的公共接口是否有文档注释
- README 是否反映了当前状态（若有相关变更）
- 文档测试是否通过

```
## Gate 4 结果

（引用 /doc 输出的变更摘要和验证结果）

- CHANGELOG：✅ 已更新 / ⏭️ 无需更新
- API 文档：✅ 已补充 N 处 / ⏭️ 无需更新
- README：✅ 已更新 / ⏭️ 无需更新
- 文档测试：✅ 通过
```

---

## Gate 5: 提交与发布

### 5.1 最终全量验证

在提交前做最后一轮完整验证（因为 Gate 2–4 可能引入了新改动）：

若用户提供了构建/测试/benchmark 命令则优先使用；否则根据项目构建系统和配置，自行确定并执行构建、测试与 benchmark 命令；若项目无测试或 benchmark 则跳过对应步骤。

- ✅ 通过 → 继续
- ❌ 失败 → 修复，重新验证

### 5.2 Commit

**禁止使用 `git add -A` 或 `git add .`——必须逐文件 add，避免暴露 .env、credentials 等敏感文件或意外的大文件。**

分析完整暂存区变更，生成 Conventional Commits message。

若 Gate 2–4 产生了多类改动（测试补充 + 文档更新 + 代码修复），拆为多个 commit：

```bash
# 若 Gate 1 审查导致了代码修复
git add <fixed files>
git commit -m "fix(<scope>): <subject>"

# Gate 2 的测试补充
git add <test files>
git commit -m "test(<scope>): <subject>"

# Gate 4 的文档更新
git add <doc files>
git commit -m "docs(<scope>): <subject>"
```

若改动内聚（只有一两个文件的小修小补），合为一个 commit 即可。

每次提交后输出：`✅ 已提交 <short-hash>: <subject>`

### 5.3 Tag（可选）

若用户指定了 `tag: <version>`：

```bash
git tag -a <version> -m "Release <version>"
```

同时将 CHANGELOG 的 `[Unreleased]` 替换为 `[<version>] - <date>`。

### 5.4 Push（默认执行）

除非指定 `no-push`：

```bash
git push 2>&1
git push --tags 2>&1  # 若打了 tag
```

若当前分支无远程追踪：
```bash
git push --set-upstream origin <branch> 2>&1
```

push 失败时输出具体错误和建议。

---

## Ship 报告

按产物存储约定输出以下报告：

```markdown
# Ship Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 分支：<branch>
- Diff 范围：<source>
- Tag：<version> / 无

## Gate 通过情况

| Gate | 状态 | 摘要 |
|------|------|------|
| 1. Review | ✅ | 0 Critical, 0 Major, N Minor |
| 2. Test | ✅ | 补充 N 个测试，发现 K 个缺陷 |
| 3. Bench | ✅ / ⏭️ | 无退化 / 跳过 |
| 4. Doc | ✅ / ⏭️ | 更新 CHANGELOG + N 处 API 注释 / 跳过 |
| 5. Git | ✅ | N 个 commit，已 push |

## Review 发现（Minor / Nit）
<引用 /review 报告中未阻断但值得记录的问题>

## 新增测试
| 测试 | 覆盖目标 |
|------|----------|
| ... | ... |

## Benchmark 对比
<Gate 3 的对比表，若执行了>

## 文档变更
<引用 /doc 报告的变更摘要，若执行了>

## 提交记录
| Commit | Message |
|--------|---------|
| <hash> | <subject> |

## 后续建议
- <Review 中记录的 Minor/Nit 问题，建议后续处理>
- <测试覆盖仍有盲区的模块>
- <性能值得进一步优化的 benchmark>
```

---

## 异常流程处理

### Gate 1 阻断

```
❌ Ship 被 Gate 1（代码审查）阻断。

发现 N 个 Critical / M 个 Major 问题：
<问题清单>

建议：
  - 使用 /fix 修复 Critical 问题
  - 修复完成后重新执行 /ship
```

暂停。已完成的审查保存到报告，下次重新执行时无需重复审查已修复的问题。

### Gate 2 发现真实缺陷

```
🐛 Gate 2（测试覆盖）发现 N 个代码缺陷：
<缺陷清单>

这些缺陷已在本轮中修复并验证。若缺陷复杂度超出当前流程：
  - 使用 /fix 进行独立的根因追踪和修复
  - 修复完成后重新执行 /ship
```

简单缺陷当场修复，复杂缺陷中断并建议走 `/fix` 流程。

### Benchmark 退化争议

用户选择"接受退化"后，在报告中明确标注：

```
⚠️ 已知退化（用户接受）：
  - <benchmark>：+X%（原因：<分析>）
```

确保退化有记录可查，不会变成"不知道什么时候变慢了"。

---

输出语言跟随用户输入语言。
