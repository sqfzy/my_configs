---
name: ship
description: Pre-release quality gate — runs structured code review, fills test coverage gaps, checks performance baselines, updates documentation, and commits/tags. A disciplined release checklist that blocks shipping until every step passes. Auto-saves ship report to .discuss/
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
| `[auto]` | 无人值守模式——Gate 1 阻断时自动终止（而非等待修复）；性能退化时自动终止；commit message 自动选择候选 1 |

---

## 流程总览

```
┌──────────────────────────────────────────────────┐
│  Gate 1: 代码审查（← /review）                    │
│  逐文件审查 → 跨文件审查 → 问题清单               │
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
│  Gate 4: 文档同步（← /doc update）                │
│  审计 → 更新 README/CHANGELOG/API 注释            │
├──────────────────────────────────────────────────┤
│  Gate 5: 提交与发布（← /git）                     │
│  commit → CHANGELOG → tag → push                 │
└──────────────────────────────────────────────────┘
```

---

## Gate 1: 代码审查

对 diff 范围内的变更执行结构化审查。

### 1.1 获取变更与上下文

```bash
git diff <source> --stat 2>&1
git diff <source> --numstat 2>&1
```

对每个变更文件，读取周边上下文——不只看 diff 行，还要理解被修改函数的完整实现和相关类型定义。

### 1.2 逐文件审查

按以下维度审查每个变更文件：

- **正确性**：逻辑错误、边界条件、错误处理遗漏、并发安全、资源管理
- **安全性**：输入验证、注入风险、敏感数据泄漏、unsafe 块、未定义行为
- **性能**：热路径开销、循环内分配、算法复杂度退化
- **可观测性**：关键路径日志、错误上下文、`#[instrument]` / `spdlog` 覆盖
- **测试覆盖**：新逻辑是否有测试、错误路径是否被测试

### 1.3 跨文件审查

- 新代码与现有风格一致性
- 是否有应同步修改但遗漏的文件
- 是否引入循环依赖或模块职责模糊

### 1.4 审查结论

每条问题使用严重程度标签：

| 级别 | 含义 | 对 ship 的影响 |
|------|------|----------------|
| 🔴 **Critical** | 运行时错误、数据损坏、安全漏洞 | **阻断**——必须修复 |
| 🟡 **Major** | 缺失的错误处理、缺失的测试、性能退化风险 | **阻断**——强烈建议修复 |
| 🔵 **Minor** | 命名改进、日志补充、可选的结构优化 | 不阻断，记录 |
| 💬 **Nit** | 纯偏好 | 不阻断，记录 |

输出审查摘要：

```
## Gate 1 结果

🔴 Critical：N | 🟡 Major：N | 🔵 Minor：N | 💬 Nit：N

<若有 Critical 或 Major>：
❌ Gate 1 未通过。存在 N 个 Critical / Major 问题需修复。
建议使用 /fix 或 /debug 处理后重新执行 /ship。

<问题清单，按严重程度排序>
```

**Critical 或 Major 存在时阻断**——不继续后续 Gate。输出问题清单后暂停，等待用户修复后重新运行。

**`auto` 模式**：不暂停，直接终止并将审查报告保存到 `.discuss/`。退出码非零，便于脚本检测失败。

✅ 无 Critical 且无 Major → 继续 Gate 2。Minor 和 Nit 记录到最终报告，不阻断。

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

```
Rust：   cargo build 2>&1 && cargo test 2>&1 && cargo clippy 2>&1
C++：    xmake build 2>&1 && xmake test 2>&1
Python： uv run pytest 2>&1 && uv run ruff check . 2>&1
Node：   npm run build 2>&1 && npm test 2>&1
Go：     go build ./... 2>&1 && go test ./... 2>&1 && go vet ./... 2>&1
```

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
ls -t .discuss/bench-baseline-*.txt 2>/dev/null | head -1
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

```
Rust：   cargo bench 2>&1 | tee .discuss/bench-ship.txt
C++：    xmake build -m release -g bench 2>&1 && xmake run -g bench 2>&1 | tee .discuss/bench-ship.txt
Python： uv run pytest --benchmark-only 2>&1 | tee .discuss/bench-ship.txt
Go：     go test -bench=. -benchmem -count=5 ./... 2>&1 | tee .discuss/bench-ship.txt
```

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

## Gate 4: 文档同步

**自动跳过条件**：用户指定 `skip: doc`。跳过时在报告中注明 `ℹ️ 文档更新已跳过`。

### 4.1 文档审计

扫描变更是否影响文档：

```
## 文档影响分析

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 公共 API 变更 | ✅ 无 / ⚠️ 有 | <变更了哪些接口> |
| README 准确性 | ✅ 准确 / ⚠️ 过时 | <哪些段落过时> |
| CHANGELOG 更新 | ✅ 已更新 / ❌ 待更新 | <缺少哪些条目> |
| API 文档注释 | ✅ 已覆盖 / ⚠️ 缺失 | <N 个公共项缺注释> |
```

### 4.2 执行更新

按需执行（仅更新受变更影响的部分，不做全量重写）：

**CHANGELOG**（几乎每次都需要）：
- 从 diff 范围内的 commit 提取变更
- 遵循 [Keep a Changelog](https://keepachangelog.com/) 格式
- commit message 改写为面向用户的语言
- 合并相关 commit，`BREAKING CHANGE` 加 ⚠️ 标记
- 追加到 `[Unreleased]` 段落

**API 文档注释**（若公共接口有变更）：
- 对新增或修改签名的公共函数补充/更新 `///` / `/** */` / docstring
- 包含：一行摘要、参数说明、返回值说明、错误条件
- 文档描述必须基于实际代码，不可捏造

**README**（若安装步骤、项目结构、CLI 接口有变）：
- 仅更新受影响的段落，保留人工编写的内容

### 4.3 文档验证

```
Rust：   cargo test --doc 2>&1 && cargo doc --no-deps 2>&1
C++：    xmake build 2>&1
Python： uv run pytest --doctest-modules 2>&1
```

```
## Gate 4 结果

- CHANGELOG：✅ 已更新 / ⏭️ 无需更新
- API 文档：✅ 已补充 N 处 / ⏭️ 无需更新
- README：✅ 已更新 / ⏭️ 无需更新
- 文档测试：✅ 通过
```

---

## Gate 5: 提交与发布

### 5.1 最终全量验证

在提交前做最后一轮完整验证（因为 Gate 2–4 可能引入了新改动）：

```
Rust：   cargo build 2>&1 && cargo test 2>&1
C++：    xmake build 2>&1 && xmake test 2>&1
Python： uv run pytest 2>&1
Go：     go build ./... 2>&1 && go test ./... 2>&1
```

- ✅ 通过 → 继续
- ❌ 失败 → 修复，重新验证

### 5.2 Commit

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

```bash
mkdir -p .discuss
```

写入 `.discuss/ship-YYYYMMDD-HHMMSS.md`：

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
<Gate 1 中未阻断但值得记录的问题>

## 新增测试
| 测试 | 覆盖目标 |
|------|----------|
| ... | ... |

## Benchmark 对比
<Gate 3 的对比表，若执行了>

## 文档变更
<Gate 4 的变更列表，若执行了>

## 提交记录
| Commit | Message |
|--------|---------|
| <hash> | <subject> |

## 后续建议
- <Review 中记录的 Minor/Nit 问题，建议后续处理>
- <测试覆盖仍有盲区的模块>
- <性能值得进一步优化的 benchmark>
```

写入完成后输出：
`✓ Ship 报告已保存至 .discuss/ship-YYYYMMDD-HHMMSS.md`

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
