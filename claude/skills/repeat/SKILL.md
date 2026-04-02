---
name: repeat
description: "Repeat a prompt or skill command on an adaptive schedule — runs until a time limit expires, with exponential backoff when no progress is detected. Useful for iterative improvement loops, continuous monitoring, or sustained multi-skill workflows. TRIGGER when: user wants to repeatedly execute a prompt or skill for a sustained period; user says \"keep running X for 30 minutes\", \"repeat X until 6pm\", \"loop X for 2 hours\". DO NOT TRIGGER when: user wants a one-shot execution of a skill (just run it directly); user wants a permanent cron schedule (use /schedule)."
argument-hint: "<prompt or /skill command> [duration: <time>] [until: <HH:MM>] [cooldown: <seconds>]"
allowed-tools: Bash(date:*), Bash(git:*), Bash(sleep:*), Bash(mkdir:*)
---

# /repeat

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`

命令：$ARGUMENTS

---

## 参数解析

- **prompt**（必填）：要重复执行的内容。可以是：
  - 一个 skill 命令：`/review`、`/improve target: src/parser.rs`
  - 多个 skill 的组合：`/review && /test`
  - 自由文本 prompt：`检查代码中的 TODO 并尝试解决`
  - 带参数的组合：`/improve target: src/ iter: 1 auto`

- **结束条件**（必须指定至少一个，可组合）：
  - `[duration: <time>]`：持续时长，格式：`30m`、`2h`、`1h30m`
  - `[until: <HH:MM>]`：运行到指定时刻（当天），如 `until: 18:00`
  - 自定义条件：用户在 prompt 中用自然语言描述的结束条件，如"直到所有测试通过"、"直到 lint 零警告"、"直到覆盖率达到 80%"
  - 若未指定任何结束条件 → 提示用户指定，不默认无限循环
  - 多个条件同时存在时，**任一条件满足即终止**

- **冷却配置**（可选）：
  - `[cooldown: <seconds>]`：初始冷却间隔，默认 **30 秒**

---

## 铁律

> **只有用户指定的结束条件才能终止循环。禁止以任何理由自行终止。**

不得因为"觉得已经够好了"、"看起来没什么可做的"、"连续无进展太多轮"而擅自停止。无进展时执行退避和上下文重置，但**循环本身不终止**——除非用户指定的结束条件被满足或用户主动叫停。

---

## 核心机制

### 执行循环

> **核心机制**：通过 Agent tool 派发 subagent，subagent 在其独立上下文内**持续重复执行** prompt，直到终止条件满足或上下文接近耗尽。主循环只在 subagent 退出后介入——检查终止条件，若未满足则派发新的 subagent 继续。

```
开始时间 = now()
结束条件 = 解析用户指定的所有条件（时间限制 + 自定义条件）
批次 = 0

loop:
    批次 += 1

    1. 记录执行前状态：git rev-parse HEAD, git diff --stat
    2. 派发 subagent（见下方 subagent 派发规则）
       subagent 内部持续执行 prompt，直到：
       - 终止条件满足（subagent 返回 "DONE"）
       - 上下文接近耗尽（subagent 返回当前进度摘要）
    3. 记录执行后状态：git rev-parse HEAD, git diff --stat
    4. 主循环检查结束条件
       → subagent 报告 "DONE" 或时间到期 或用户叫停？break
       → 否则：派发新 subagent 继续
```

### Subagent 派发规则

每个 subagent 在其上下文内持续循环执行 prompt，prompt 格式：

```
你在 <当前目录> 下工作。

## 任务
持续重复执行以下操作（auto 模式，不暂停等待确认）：

<用户原始 prompt>

## 循环规则
- 每次执行完成后，冷却 <N> 秒，然后再次执行
- 若连续无进展（git 无变更且输出收敛），冷却时间翻倍（上限 600s）；有进展则重置为初始值
- 每次执行后检查终止条件：<终止条件描述>
  → 条件满足时立即停止，输出 "DONE: <最终摘要>"
  → 条件未满足时继续下一轮
- 若时间限制为 <截止时间>，到期时停止
- 每轮输出一行状态：`[第 N 轮 | HH:MM:SS] ✅/➡️ <摘要>`

## 退出时
输出表格摘要 + 状态标记：

终止条件满足时：
```
DONE
| 轮次 | 时间 | 状态 | 变更摘要 |
|------|------|------|----------|
| 1 | HH:MM | ✅ | <摘要> |
| 2 | HH:MM | ✅ | <摘要> |
| 3 | HH:MM | ➡️ | 无改动 |
累计：N 轮，M 次有效改动
```

上下文即将耗尽时：
```
CONTINUE | 已完成 N 轮 | 当前冷却 Xs
| 轮次 | 时间 | 状态 | 变更摘要 |
|------|------|------|----------|
| ... | ... | ... | ... |
```
```

**派发要求**：
- 使用 Agent tool 的 `description` 字段标注批次：`"repeat 批次 N"`
- subagent 内部自行管理轮次计数、冷却退避、进度检测
- 主循环仅在 subagent 退出后介入，根据返回的 `DONE` 或 `CONTINUE` 决定是否派发下一个 subagent
- 新 subagent 继承上一个的冷却状态和轮次计数（从 `CONTINUE` 消息中提取）

### 结束条件检查（subagent 内部 + 主循环双层）

**subagent 内部**（每轮执行后）：
1. **时间限制** → 到期则停止，返回 `DONE` 或 `CONTINUE`
2. **自定义条件** → 执行对应检查命令，条件满足则返回 `DONE`

**主循环**（subagent 退出后）：
1. **用户叫停** → 终止
2. **subagent 返回 `DONE`** → 终止
3. **时间到期** → 终止
4. **subagent 返回 `CONTINUE`** → 派发新 subagent

**自定义条件必须无条件遵守**——一旦检测到条件满足，即使还有剩余时间或用户未叫停，也必须立即终止。

### 进度检测（subagent 内部）

subagent 在每轮执行后自行判断进度，管理冷却退避：

**有进度的信号**：
- `git diff --stat` 显示有文件变更
- 有新的 git commit 产生
- skill 输出中包含明确的改动指示

**无进度的信号**：
- `git diff --stat` 为空且无新 commit
- skill 输出包含收敛/完成指示（如"无问题"、"全部通过"、"已收敛"）

**判断策略**：以 git 变更为主要信号，skill 输出为辅助。

### subagent 内部每轮输出

```
[第 N 轮 | HH:MM:SS] ✅ 有进度 — <变更摘要> | 冷却 30s
[第 N 轮 | HH:MM:SS] ➡️ 无进展 — <原因> | 冷却 60s（翻倍）
```

---

## 执行流程

### Step 1: 解析与确认

解析参数，计算截止时间，输出执行计划：

```
## 执行计划

命令：<prompt>
开始：<HH:MM:SS>
截止：<HH:MM:SS>（共 <duration>）
初始冷却：<N> 秒
退避策略：无进展时翻倍，上限 600 秒，有进展时重置

预估最大执行轮数：<duration / cooldown>（假设每轮有进度）
```

### Step 2: 执行循环

按核心机制派发 subagent。每个 subagent 内部持续执行多轮，主循环只在 subagent 退出后介入：

1. 派发 subagent（按 subagent 派发规则）
2. 等待 subagent 返回
3. 解析返回值：
   - `DONE: ...` → 终止条件已满足，进入 Step 3
   - `CONTINUE: ...` → 提取轮次和冷却状态，派发新 subagent 继续
4. 检查时间限制和用户叫停
5. 输出批次状态行

### Step 3: 结束总结

循环结束后，输出执行摘要：

```
## 执行摘要

总轮数：N
有效轮数（有进度）：M
无效轮数（无进展）：K
总耗时：X 分 Y 秒
终止原因：结束条件满足 / 时间到期 / 冷却超过剩余时间 / 用户叫停

### 各轮记录
| 轮次 | 时间 | 状态 | 变更摘要 | 冷却 |
|------|------|------|----------|------|
| 1 | HH:MM | ✅ | 修复了 3 个 lint 问题 | 30s |
| 2 | HH:MM | ✅ | 优化了 parse_token() | 30s |
| 3 | HH:MM | ➡️ | 无新问题 | 60s |
| 4 | HH:MM | ➡️ | 无新问题 | 120s |
| ... | ... | ... | ... | ... |

### 累计变更
- 新增/修改/删除文件数：<stat>
- 新增 commit 数：<N>
- 最终冷却间隔：<N> 秒
```

---

## 注意事项

- **必须有结束条件**：至少指定一个结束条件（时间限制或自定义条件），防止遗忘的无限循环
- **冷却上限**：最大 600 秒（10 分钟），防止退避到几乎不执行
- **冷却重置**：一旦检测到进度，立即重置到初始冷却——短暂的停滞不应永久拉高间隔
- **时间感知**：每轮开始前检查剩余时间，若冷却 > 剩余时间则提前终止而非空等
- **默认 auto**：prompt 中包含的所有 skill 默认以 `auto` 模式执行——重复执行场景下每轮暂停等待确认没有意义。用户无需手动追加 `auto` 参数，`/repeat` 会自动为每个 skill 注入 `auto`
- **上下文隔离**：subagent 在独立上下文内持续执行多轮，直到上下文耗尽或终止条件满足。主循环只在 subagent 退出后介入，上下文极简。这意味着：
  - subagent 内部可以利用完整上下文窗口执行尽可能多的轮次
  - 主循环的上下文几乎不增长（仅保留 `DONE`/`CONTINUE` 摘要）
  - subagent 之间的连续性通过代码变更（git）、产物（.artifacts/）和 `CONTINUE` 消息中的状态传递

---

输出语言跟随用户输入语言。
