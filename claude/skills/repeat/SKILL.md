---
name: repeat
description: Repeat a prompt or skill command on an adaptive schedule — runs until a time limit expires, with exponential backoff when no progress is detected. Useful for iterative improvement loops, continuous monitoring, or sustained multi-skill workflows.
TRIGGER when: user wants to repeatedly execute a prompt or skill for a sustained period; user says "keep running X for 30 minutes", "repeat X until 6pm", "loop X for 2 hours".
DO NOT TRIGGER when: user wants a one-shot execution of a skill (just run it directly); user wants a permanent cron schedule (use /schedule).
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

```
开始时间 = now()
结束条件 = 解析用户指定的所有条件（时间限制 + 自定义条件）
当前冷却 = 初始冷却（默认 30s）
连续无进展次数 = 0
轮次 = 0

loop:
    轮次 += 1

    1. 记录执行前状态（git diff 快照）
    2. 执行 prompt
    3. 检测进度（见下方规则）
    4. 记录本轮结果
    5. 检查结束条件（见下方规则）
       → 任一条件满足？break

    if 有进度:
        当前冷却 = 初始冷却（重置）
        连续无进展次数 = 0
    else:
        连续无进展次数 += 1
        当前冷却 = min(当前冷却 * 2, 600)  # 翻倍，上限 10 分钟

    # 时间限制检查（若设置了 duration/until）
    if 有时间限制 and (冷却 > 剩余时间 or 剩余时间 ≤ 0):
        break

    # 冷却期间检查用户中断
    输出：「⏸ 冷却 <N>s… 按 Esc 完成本轮后停止」
    等待冷却（若用户在冷却期间发送任何消息或按 Esc，标记停止）
    if 用户已叫停:
        break
```

### 结束条件检查

每轮执行后，按以下顺序检查所有结束条件：

1. **用户叫停** → 立即终止
2. **时间限制**（若设置了 `duration` / `until`）→ 到期则终止
3. **自定义条件** → 每轮执行后评估用户描述的条件是否已满足：
   - 根据条件类型，执行对应的检查命令（如运行测试、检查 lint 输出、读取覆盖率报告）
   - 条件满足 → 终止
   - 条件未满足 → 继续

**自定义条件必须无条件遵守**——一旦检测到条件满足，即使还有剩余时间或用户未叫停，也必须立即终止。

### 进度检测

每轮执行后判断是否有进度。按以下信号综合判断：

**有进度的信号**：
- `git diff --stat` 显示有文件变更（新增、修改、删除）
- 有新的 git commit 产生
- skill 输出中包含明确的改动指示（如"已修复"、"已提交"、"已优化"、"已生成"）
- `.artifacts/` 中有新文件产生

**无进度的信号**：
- `git diff --stat` 为空且无新 commit
- skill 输出包含收敛/完成指示（如"无问题"、"全部通过"、"已收敛"、"nothing to do"、"no issues"）
- 与上一轮的输出实质相同

**判断策略**：以 git 变更为主要信号，skill 输出为辅助。有文件变更 = 有进度；无文件变更但 skill 报告有工作完成 = 有进度；两者都没有 = 无进度。

### 每轮输出

每轮执行完成后，输出简要状态行：

```
[第 N 轮 | HH:MM:SS] ✅ 有进度 — <变更摘要> | 冷却 30s | 剩余 25m
[第 N 轮 | HH:MM:SS] ➡️ 无进展 — <原因> | 冷却 60s（翻倍） | 剩余 20m

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

按核心机制中描述的循环执行。

**每轮执行时**：

1. 记录执行前的 git 状态：
   ```bash
   git rev-parse HEAD 2>&1
   git diff --stat 2>&1
   ```

2. 执行用户的 prompt（调用对应的 skill 或执行自由文本指令）

3. 记录执行后的 git 状态，对比检测进度：
   ```bash
   git rev-parse HEAD 2>&1
   git diff --stat 2>&1
   ```

4. 输出本轮状态行

5. 冷却等待（若未超时）：
   ```bash
   sleep <当前冷却秒数>
   ```

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

---

输出语言跟随用户输入语言。
