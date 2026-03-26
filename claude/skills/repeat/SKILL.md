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

- **时间限制**（二选一，必须指定至少一个）：
  - `[duration: <time>]`：持续时长，格式：`30m`、`2h`、`1h30m`
  - `[until: <HH:MM>]`：运行到指定时刻（当天），如 `until: 18:00`
  - 若都未指定 → 提示用户指定，不默认无限循环

- **冷却配置**（可选）：
  - `[cooldown: <seconds>]`：初始冷却间隔，默认 **30 秒**

---

## 核心机制

### 执行循环

```
开始时间 = now()
截止时间 = 开始时间 + duration 或 until 指定的时刻
当前冷却 = 初始冷却（默认 30s）
连续无进展次数 = 0
轮次 = 0

while now() < 截止时间:
    轮次 += 1

    1. 记录执行前状态（git diff 快照）
    2. 执行 prompt
    3. 检测进度（见下方规则）
    4. 记录本轮结果

    if 有进度:
        当前冷却 = 初始冷却（重置）
        连续无进展次数 = 0
    else:
        连续无进展次数 += 1
        当前冷却 = min(当前冷却 * 2, 600)  # 翻倍，上限 10 分钟
        if 连续无进展次数 >= 2:
            执行 /clear  # 清空上下文，换个视角
            连续无进展次数 = 0  # 重置计数，给新上下文机会

    剩余时间 = 截止时间 - now()
    if 剩余时间 ≤ 0:
        break
    if 当前冷却 > 剩余时间:
        break  # 冷却时间已超过剩余时间，不值得再等

    # 冷却期间检查用户中断
    输出：「⏸ 冷却 <N>s… 按 Esc 完成本轮后停止」
    等待冷却（若用户在冷却期间发送任何消息或按 Esc，标记停止）
    if 用户已叫停:
        break
```

### 进度检测

每轮执行后判断是否有进度。按以下信号综合判断：

**有进度的信号**：
- `git diff --stat` 显示有文件变更（新增、修改、删除）
- 有新的 git commit 产生
- skill 输出中包含明确的改动指示（如"已修复"、"已提交"、"已优化"、"已生成"）
- `.discuss/` 中有新文件产生

**无进度的信号**：
- `git diff --stat` 为空且无新 commit
- skill 输出包含收敛/完成指示（如"无问题"、"全部通过"、"已收敛"、"nothing to do"、"no issues"）
- 与上一轮的输出实质相同

**判断策略**：以 git 变更为主要信号，skill 输出为辅助。有文件变更 = 有进度；无文件变更但 skill 报告有工作完成 = 有进度；两者都没有 = 无进度。

### 上下文重置（连续 2 轮无进展时触发）

当连续 2 轮无进展时，模型可能"卡在老路上"——上下文中堆满了之前的尝试，导致反复走同样的死路。

**触发条件**：`连续无进展次数 >= 2`

**执行方式**：执行 `/clear` 清空会话上下文，然后重新执行用户的 prompt。清空后模型会从零开始审视代码，可能发现之前被忽略的方向。

**重置后的行为**：
- 上下文已清空，但工作区（代码、git 历史）保持不变——之前的有效改动都在
- 冷却时间继续退避，不因重置而归零（重置解决的是视角问题，不是进度问题）
- 一旦重置后的轮次产生了进度，冷却重置到初始值

### 每轮输出

每轮执行完成后，输出简要状态行：

```
[第 N 轮 | HH:MM:SS] ✅ 有进度 — <变更摘要> | 冷却 30s | 剩余 25m
[第 N 轮 | HH:MM:SS] ➡️ 无进展 — <原因> | 冷却 60s（翻倍） | 剩余 20m
[第 N 轮 | HH:MM:SS] 🔄 上下文已重置 — /clear 后重新执行 | 冷却 120s | 剩余 15m
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
终止原因：时间到期 / 冷却超过剩余时间 / 用户叫停

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

- **不做无限循环**：必须指定 `duration` 或 `until`，防止遗忘的后台循环消耗资源
- **冷却上限**：最大 600 秒（10 分钟），防止退避到几乎不执行
- **冷却重置**：一旦检测到进度，立即重置到初始冷却——短暂的停滞不应永久拉高间隔
- **时间感知**：每轮开始前检查剩余时间，若冷却 > 剩余时间则提前终止而非空等
- **prompt 中的 auto 参数**：若用户的 prompt 包含需要交互确认的 skill（如 `/improve`），建议追加 `auto` 参数以避免每轮暂停。若检测到 prompt 中的 skill 可能暂停等待输入，提醒用户：
  ```
  💡 建议在 prompt 中追加 auto 参数以避免每轮暂停：
     /repeat /improve target: src/ auto [duration: 1h]
  ```

---

输出语言跟随用户输入语言。
