---
name: discuss
description: Structured adversarial multi-role discussion that converges on a well-tested solution. Auto-saves results to .discuss/
TRIGGER when: user asks to weigh tradeoffs, compare approaches, debate a technical decision, or wants structured pros/cons analysis before choosing a direction.
DO NOT TRIGGER when: user wants discussion followed by implementation (use /design), or has already decided and wants to start coding.
argument-hint: <topic> [rounds: N] [roles: N]
allowed-tools: Bash(mkdir:*), Bash(date:*)
---

# /discuss

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`

议题：$ARGUMENTS

---

按以下流程执行，**全部完成后**再将结果写入文件。

---

## Step 0: 参数解析 & 复杂度评估

### 轮数

从议题中解析 `[rounds: N]` 或 `[轮数: N]`：

- **用户指定轮数**：严格执行，无上限，尽最大努力完成每一轮。
- **未指定**：以**收敛为目标**，不设固定上限。按复杂度确定最低轮数，之后持续讨论直到所有角色在最后一轮无新的实质性论点：

| 复杂度 | 特征                                                   | 最低轮数 | 终止条件 |
|--------|--------------------------------------------------------|----------|----------|
| 低     | 单一维度，有明显最优解，约束清晰                       | 2        | 连续 1 轮无新论点 |
| 中     | 多个合理方案，存在非显然权衡                           | 4        | 连续 1 轮无新论点 |
| 高     | 跨领域、约束模糊、利益方多、存在根本分歧               | 7        | 连续 2 轮无新论点 |
| 极高   | 开放性问题、无标准答案、需深度探索、或对抗性强         | 15       | 连续 2 轮无新论点 |

声明：`复杂度：X → 讨论轮数：N 轮`

记录开始时间，讨论结束后计算耗时。

### 角色数量

从议题中解析 `[roles: N]` 或 `[角色数: N]`，未指定则默认 **5 个角色**。

---

## Step 1: 角色选择与自定义

选出指定数量的角色：

!`cat ~/.claude/skills/shared/roles.md`

议题偏通用或模糊时，从预定义库中优先选 R5、R11、R12，其余用最相关的角色补足。

---

## Step 2: 结构化讨论

**轮次规则**：
- 第 1 轮：各角色独立提出核心论点和初步方案
- 中间轮：必须直接反驳其他角色的具体论点；允许临时联盟对抗第三方
- 最后一轮：每个角色声明立场修正情况——哪些反驳改变了自己的想法、哪些坚持不让及原因

---

## Step 3: 收敛输出

```markdown
## 最终方案

### 核心决策
[一句话]

### 方案细节
[具体内容]

### 已解决的分歧
- [分歧点] → [解决方式]

### 未解决的权衡（需用户决策）
- [冲突]：[角色A] vs [角色B]
  → 若 [条件X] 选前者；若 [条件Y] 选后者

## 会议摘要
- 参与角色：...
- 讨论轮数：...
- 主要争议：...
- 收敛路径：...
- 最终共识：...
```

---

## Step 4: 保存讨论记录

讨论全部完成后，执行：

1. 用 Bash 创建目录（若不存在）：`mkdir -p .discuss`
2. 生成文件名：`.discuss/discuss-YYYYMMDD-HHMMSS.md`（使用讨论开始时的时间戳）
3. 写入以下结构：

```markdown
# Discussion Record

## Context
- 时间：<讨论开始时间>
- 耗时：<X 分 Y 秒>
- 用户原始需求：<完整复现 $ARGUMENTS>
- 复杂度评估：<低/中/高/极高>
- 讨论轮数：<N 轮>
- 参与角色：<角色名列表，注明哪些是自定义角色>

## 内容摘要
<3–5 句话概述：争议焦点、各角色核心立场、收敛过程、最终结论>

---

<完整讨论内容，包含所有轮次发言和最终方案>
```

4. 写入完成后告知用户：`✓ 讨论已保存至 .discuss/discuss-YYYYMMDD-HHMMSS.md`

---

输出语言跟随用户输入语言。
