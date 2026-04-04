---
name: repeat
description: "Repeat a prompt or skill command until a termination condition is met (time limit, custom condition, or user stop). Uses subagents for context isolation — each subagent runs multiple rounds, main loop dispatches new subagents as needed. TRIGGER when: user wants to repeatedly execute a prompt or skill for a sustained period; user says \"keep running X for 30 minutes\", \"repeat X until 6pm\", \"repeat X until all tests pass\", \"loop X for 2 hours\". DO NOT TRIGGER when: user wants a one-shot execution of a skill (just run it directly); user wants a permanent cron schedule (use /schedule)."
argument-hint: "<prompt or /skill command> [until: <条件>] [batch-until: <条件>]"
allowed-tools: Bash(date:*), Bash(git:*), Bash(sleep:*), Bash(mkdir:*)
---

# /repeat

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`

产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`

命令：$ARGUMENTS

---

## 参数解析

- **prompt**（必填）：要重复执行的内容（skill 命令、组合命令、或自由文本）
- **`[until: <条件>]`**（必填）：主循环终止条件，用户自定义何时停止整个循环。如 `until: 18:00`、`until: 2h`、`until: 所有测试通过`、`until: 用户叫停`
  - 若未指定 → 提示用户指定，不默认无限循环
- **`[batch-until: <条件>]`**（可选）：启用 subagent 模式，控制每个 subagent 何时退出。如 `batch-until: 10轮`、`batch-until: 连续2轮无进展`
  - 未指定时 → **直接执行模式**：主循环自身直接执行 prompt，不派发 subagent
  - 指定时 → **subagent 模式**：派发 subagent 执行，subagent 退出后主循环检查 `until` 条件，未满足则派发新 subagent 继续
- 所有 skill 默认注入 `auto` 模式，无需手动追加

---

## 铁律

> **只有用户指定的结束条件才能终止循环。禁止以任何理由自行终止。此规则同时适用于主循环（`until`）和 subagent 循环（`batch-until`）。**

不得因为"觉得已经够好了"、"看起来没什么可做的"而擅自停止。**不得在轮次之间暂停等待用户确认**——未到终止条件时必须立即开始下一轮。主循环只在 `until` 条件满足或用户叫停时终止；subagent 只在 `batch-until` 条件满足、`until` 条件满足、或上下文耗尽时退出。

---

## 执行循环

### 直接执行模式（无 batch-until）

主循环自身直接执行 prompt，每轮结束后检查 `until` 条件。**不暂停、不询问、不等待确认——未到终止条件时自动进入下一轮**：

```
轮次 = 0
连续无效轮 = 0
cooldown = 30s

loop:
    轮次 += 1
    直接执行 prompt（auto 模式，不暂停等待确认）
    判断本轮是否有效（有 commit = 有效，无改动 = 无效）
    有效 → 连续无效轮 = 0，cooldown = 30s
    无效 → 连续无效轮 += 1，cooldown = min(cooldown × 2, 10m)
    记录本轮结果（commit hash、diff-stat、摘要）
    输出本轮报告给用户
    检查 until 条件 → 满足则进入结束总结
    → 不满足：
        输出 ⏳ 冷却 {cooldown} 后开始第 {轮次+1} 轮...
        sleep(cooldown)
        开始下一轮（禁止暂停等待确认）
```

### Subagent 模式（指定 batch-until）

派发 subagent 批量执行，subagent 退出后主循环检查条件：

```
批次 = 0
cooldown = 30s

loop:
    批次 += 1
    派发 subagent（description: "repeat 批次 N"）
    subagent 返回 →
      主循环将 subagent 的每轮报告原样输出给用户（subagent 结果对用户不可见，必须转发）
      DONE → 进入结束总结
      BATCH_DONE / CONTINUE → 检查主循环条件，未满足则：
          输出 ⏳ 冷却 {cooldown} 后派发下一批次...
          sleep(cooldown)
          派发新 subagent
```

### Cooldown 与退避策略

每轮结束后固定冷却，连续无效轮时指数退避：

```
初始 cooldown ： 30s
退避策略     ： 连续无效轮时 cooldown × 2
上限         ： 10 分钟
重置         ： 一旦出现有效轮，cooldown 回到 30s

示例：
  第 1 轮 有效 → cooldown 30s
  第 2 轮 无效 → cooldown 60s
  第 3 轮 无效 → cooldown 2m
  第 4 轮 无效 → cooldown 4m
  第 5 轮 无效 → cooldown 8m
  第 6 轮 无效 → cooldown 10m（触顶）
  第 7 轮 有效 → cooldown 30s（重置）
```

冷却期间输出提示：`⏳ 冷却 Xs 后开始第 N 轮...`（退避时额外标注：`⏳ 冷却 Xs（退避：连续 M 轮无效）后开始第 N 轮...`）

---

## Subagent 派发（仅 subagent 模式）

每个 subagent 收到的 prompt：

```
你在 <当前目录> 下工作。

## 任务
持续重复执行以下操作（auto 模式，不暂停等待确认）：

<用户原始 prompt>

## 循环规则
- 每次执行完成后，立即开始下一轮
- 每轮结束后检查 batch-until 条件：<batch-until 条件描述>
  → 条件满足时停止，返回 BATCH_DONE
- 每轮结束后检查 until 条件：<until 条件描述>
  → 条件满足时停止，返回 DONE
- 若上下文接近耗尽，停止并返回 CONTINUE
- 禁止以任何其他理由自行终止

## 退出时（铁律：必须输出报告）
退出前 **必须** 输出以下格式，缺少报告视为 subagent 失败。

**第一行**：状态标记
- `DONE | 已完成 N 轮`（主循环终止条件满足）
- `BATCH_DONE | 已完成 N 轮`（subagent 终止条件满足）
- `CONTINUE | 已完成 N 轮`（上下文耗尽）

**紧接每轮报告**（每轮一个块，严禁合并、省略）：

── 第 1 轮 ✅ abc1234 ──
修复 Gateway::reconnect() 持锁死锁
 gateway.hpp  | 18 ++++++++++++---
 endpoint.hpp |  8 ++++++++

── 第 2 轮 ✅ def5678 ──
提取 scan_string_literal()，消除重复
 lexer.rs | 109 +++++++++++++++++++++++++++-------------------------------------

── 第 3 轮 ➡️ ──
无改动（review 未发现新问题）

格式要求：
- 每轮标题行：`── 第 N 轮 ✅/➡️ <commit hash> ──`
- 标题下方第一行：摘要（一句话描述改了什么）
- 摘要下方：`git diff --stat` 的原始输出（每轮执行后用 `git diff --stat HEAD~1` 获取）；无改动时省略
- 严禁合并多轮为一个块（❌ "── 第 3-7 轮 ──"）

**末行**：累计：N 轮，M 次有效改动，K 个 commits
```

---

## 结束总结

循环结束后：

### 1. 输出汇总表格

将所有批次的每轮报告整合为一张表格输出给用户：

```
## repeat 执行摘要

总轮数：N | 有效：M | 无效：K | 耗时：X 分 Y 秒
终止原因：<条件满足 / 时间到期 / 用户叫停>

| 轮次 | 状态 | commit | 摘要 |
|------|------|--------|------|
| 1 | ✅ | abc1234 | 修复 Gateway::reconnect() 持锁死锁 |
| 2 | ✅ | def5678 | 提取 scan_string_literal()，消除重复 |
| 3 | ➡️ | — | 无改动 |
| ... | | | |
```

### 2. 保存报告到 .artifacts/

按产物存储约定，将完整报告写入 `.artifacts/repeat-YYYYMMDD-HHMMSS.md`，内容：

```markdown
# Repeat Report

## 概况
- 命令：<用户原始 prompt>
- 开始：<HH:MM:SS>
- 结束：<HH:MM:SS>
- 总轮数：N（有效 M，无效 K）
- 终止原因：<...>

## 各轮详情

（拼接所有批次的每轮报告，保留完整的 diff-stat 风格格式）

## 汇总表格

| 轮次 | 状态 | commit | 摘要 |
|------|------|--------|------|
| ... | | | |

## 累计变更
<git diff --stat 首轮起始commit..最终commit 的输出>
```

---

输出语言跟随用户输入语言。
