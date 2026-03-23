---
name: retro
description: Generate a structured retrospective after completing a coding session — extracts lessons learned, pitfalls, insights, and key decisions with enough context to be useful months later.
TRIGGER when: user asks for a retrospective, session review, lessons learned, or post-mortem after completing a feature/debug/refactor session.
DO NOT TRIGGER when: user is still actively working on a task, or asking for a code review (use /review).
argument-hint: "[scope: <path or description>] [since: <git-ref>] [depth: quick|full]"
allowed-tools: Bash(git:*), Bash(find:*), Bash(cat:*), Bash(date:*), Bash(mkdir:*)
---

# /retro

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
近期提交历史：!`git log --oneline -20 2>&1`
近期改动的文件：!`git diff --name-only HEAD~10 HEAD 2>&1`

参数：$ARGUMENTS

---

## 参数解析

- `[scope: <path|描述>]`：聚焦的模块、文件或功能域；未指定则覆盖近期所有改动
- `[since: <git-ref>]`：从指定的 commit / tag / 分支开始回溯；未指定则自动取最近一个有意义的起点（最近的 merge commit 或 10 个 commit 之前）
- `[depth: quick]`：只输出摘要和 Top 5 教训，适合快速记录；默认 `full`

记录开始时间，确定日志路径：
```bash
mkdir -p .discuss
```
输出文件：`.discuss/retro-YYYYMMDD-HHMMSS-<branch>.md`

---

## Step 0: 上下文重建

在提炼教训之前，先重建这段工作的完整上下文，确保复盘有据可查。

### 0.1 提交历史分析

```bash
git log --oneline <since>..HEAD      # 提交列表
git diff --stat <since>..HEAD        # 改动规模
git log --oneline <since>..HEAD --all -- "*.rs" "*.cpp" "*.h" "*.py"  # 按语言过滤
```

提取：
- 工作起止点
- 改动规模（文件数、行数增删）
- 提交数量和节奏（密集修复 vs 平稳推进）

### 0.2 关键文件精读

读取改动最集中的文件（按 diff 行数排序，取前 10），重点关注：
- 大块删除或重写（暗示走过弯路或重大重构）
- 多次反复修改同一段代码（暗示踩坑或需求变化）
- 错误处理路径的演变（暗示边界条件被逐步发现）
- 测试文件的变化（暗示对行为理解的修正过程）

### 0.3 调试日志扫描（若存在）

若 `.discuss/` 目录下有本次工作期间生成的 debug / evolution 日志，读取并提取：
- 出现过哪些错误
- 根因分析的结论
- 解决路径

---

## Step 1: 时间线重建

基于 git 历史，重建工作时间线，作为复盘的骨架：

```
## 工作时间线

<起点> — <描述：从哪里开始，初始状态是什么>
  │
  ├─ <commit/阶段> — <做了什么，当时的意图>
  │     └─ ⚠️ <若此处有明显弯路或回滚，标注>
  │
  ├─ <commit/阶段> — <...>
  │
  └─ <终点> — <最终状态>

总计：<N 个提交，M 个文件，+X/-Y 行>
```

时间线要求：
- 描述**意图**而非只列文件名（"尝试用 X 方案，后来发现不行"比"修改了 foo.rs"有价值）
- 明确标注回滚、重写、方向转变
- 若能从 commit message 或代码注释推断出当时的判断，显式写出来

---

## Step 2: 坑与教训提炼

这是复盘的核心。对每一个踩过的坑或值得记录的教训，用以下结构输出：

```
### 坑 N：<标题，一句话描述问题>

**背景**
<当时在做什么，代码/系统处于什么状态，为什么会走到这一步>

**现象**
<具体的错误信息、异常行为、或"感觉不对"的信号>

**当时的错误判断**
<第一反应是什么，为什么这个判断是错的>

**根因**
<真正的原因是什么，为什么一开始没发现>

**解决方式**
<最终怎么解决的>

**教训 / 正确思路**
<下次遇到类似情况，应该如何思考 / 先检查什么 / 避免什么>

**可复用的模式**（可选）
<这个教训是否能抽象成一个通用规律，适用于其他场景>

**相关代码位置**
`<file>:<line>` 或 `<function>`
```

踩坑的来源线索（从以下信号识别）：
- git 历史中出现 `fix`、`revert`、`hotfix`、`workaround`、`hack` 等词的提交
- 同一段代码被多次修改
- debug 日志中出现过的错误
- 大块删除后重写的代码（说明原始设计有缺陷）
- 测试从通过变为失败再变为通过的循环

---

## Step 3: 心得与洞察提炼

除了踩坑，也记录正向的收获——那些"原来如此"或"这个思路很好"的时刻：

```
### 心得 N：<标题>

**发现场景**
<在什么情况下意识到这个>

**核心洞察**
<具体是什么，越具体越好，避免泛泛的"要写好代码">

**为什么有价值**
<这个洞察解决了什么问题，或改变了什么思维方式>

**应用条件**
<什么情况下适用，什么情况下不适用>

**示例**（可选）
\```<lang>
// 能说明问题的最小代码片段
\```
```

心得来源线索：
- 设计方案中被评审采纳的建议
- 重构后代码变得明显简洁的地方
- 新引入的抽象或模式
- 性能优化中的关键发现
- 与预期不同但更好的解法

---

## Step 4: 关键决策记录

记录本次工作中做出的重要技术决策，包括**选择了什么**和**为什么没选另一个**：

```
### 决策 N：<标题>

**决策点**
<在什么时候面临什么选择>

**选项对比**
| 方案 | 优点 | 缺点 | 排除原因 |
|------|------|------|----------|
| 选择的方案 A | ... | ... | — （已选）|
| 放弃的方案 B | ... | ... | <为什么没选> |

**最终选择**：方案 A

**当时的信息状态**
<做决策时已知什么、不知道什么——这很重要，事后看决策要还原当时的认知>

**现在回看**
<这个决策是对的吗？有没有新的信息改变了判断？>
```

---

## Step 5: 遗留问题 & 后续建议

记录本次没有解决的问题和建议的跟进动作：

```
## 遗留问题

| 问题 | 严重程度 | 影响范围 | 建议跟进方式 |
|------|----------|----------|--------------|
| <描述> | critical/major/minor | <文件/模块> | `/debug` / `/improve` / 手动处理 |

## 后续建议
- <建议1：下次做类似工作时提前注意什么>
- <建议2：哪个模块还需要深度打磨>
- <建议3：哪个教训值得写成团队规范>
```

---

## Step 6: 生成复盘报告

将以上内容整合，写入 `.discuss/retro-YYYYMMDD-HHMMSS-<branch>.md`：

````markdown
# Retrospective: <功能/任务名称，从 git 历史推断>

## 元信息
- 时间范围：<开始> — <结束>
- 分支：<branch>
- 规模：<N commits, M files, +X/-Y lines>
- 复盘生成时间：<now>

---

## 一句话总结
<这段工作做了什么，最重要的收获是什么——给未来的自己看的 TL;DR>

---

## 工作时间线
<Step 1 的输出>

---

## 坑与教训
<Step 2 的所有条目>

---

## 心得与洞察
<Step 3 的所有条目>

---

## 关键决策记录
<Step 4 的所有条目>

---

## 遗留问题 & 后续建议
<Step 5 的输出>

---

## 索引标签
<自动生成，便于以后搜索>
标签：<语言> <涉及的技术领域，如 async/memory/parsing/concurrency> <错误类型，如 type-error/race-condition/oom> <关键词>
````

写入完成后输出：
`✓ 复盘报告已保存至 .discuss/retro-YYYYMMDD-HHMMSS-<branch>.md`

---

## depth: quick 模式

若指定 `depth: quick`，跳过 Step 0–1 的完整重建，直接输出：

```markdown
# Quick Retro: <branch> @ <date>

## TL;DR
<3 句话：做了什么，最大的坑，最重要的收获>

## Top 5 教训
1. <教训，附代码位置>
2. ...

## 遗留问题
- <列表>
```

同样保存到 `.discuss/`，文件名加 `-quick` 后缀。

---

输出语言跟随用户输入语言。
