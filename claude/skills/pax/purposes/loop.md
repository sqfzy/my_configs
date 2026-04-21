# Purpose: loop

周期性重复执行 —— "跑一晚"、"自主演进"、"质量打磨"、"测试逼近"、"性能逼近"、"文档跟进" 等场景。loop 是**组合类元目的**：它不直接改代码，而是规划一份**循环契约**，契约里的循环体可以调任意 pax 子目的、`/report`、`/script`、shell 命令。审批后由 loop 执行层按契约反复执行，直到终止条件满足。

---

## 独有维度（Phase 2 必须展开）

### 1. BODY —— 循环体（伪代码 step-by-step）

每轮执行的步骤序列，可含：
- 子 pax 调用（`/pax --<p> --auto`）
- 其他 skill（`/report --auto`、`/script --auto`）
- shell 命令（`run: cargo test`）
- 条件分支（`if cond: ...`）
- 内置操作（`pick`、`filter`、`route`、`collect`）

**示例**：

```
BODY:
  step 1: /pax --review --auto (lens: {LENS})
          → tier_list
  step 2: pick = tier_list.tier1.first_unflagged()
          if none: ESCALATE       # 见 §6 梯队 L1/L2/L3/L4；绝不 signal UNTIL
  step 3: kind = classify(pick)
          route kind → /pax --{feat|fix|reshape|upgrade|test|bench|doc} --auto
          input: pick, lens: {LENS}
  step 4: collect commit_hashes; diff_stat; summary → STATE

# 只有当 UNTIL 原文就是"Tier 1 清完"之类时，step 2 才允许 signal UNTIL。
# UNTIL 为时间类（"到 9 点"）时，step 2 永远只能 ESCALATE，不得退出。
```

**硬约束**：BODY 至少有一个"产出 commit 或改变状态"的 step，否则判空转。

### 2. UNTIL —— 主终止条件（必填）

自然语言 + 结构化解析：

| 类 | 例子 | 检查方式 |
|---|------|---------|
| 时间 | "到 8 点"、"跑 2 小时" | 当前时间对比 |
| 项数 | "做 10 项"、"最多 5 轮" | 计数器 |
| 状态 | "cargo test 全绿"、"无 clippy warning" | 跑命令 |
| 清空 | "Tier 1 清完"、"无待修项" | 读 BODY 产物 |
| 外部 | "用户打断" | 系统信号 |
| 复合 | "8 点或 Tier 1 清完" | 任一满足即退（仅当用户文字里明写"或/and/任一/both"才算复合）|
| 空 | `""` | 永不满足（跑到被打断） |

**UNTIL 解读铁律**（Phase 0 假设列举必须列为最高优先级假设）：

1. **不得隐式合取 / 析取**。用户只给一个条件就是一个条件；不得施工期自作主张加 "OR 队列耗尽" / "OR 无新发现" / "OR 觉得差不多" 等附加门。**唯一**的复合 UNTIL 是用户文字里明写"或/且/任一/both"的。
2. **时间类 UNTIL 是硬墙**。到点前绝对不退出，任何其他信号（队列耗尽、无新发现、多轮无 commit）都不是 UNTIL 触发点，而是 ESCALATION 触发点（见 §6）——即扩大搜索面 / 换子目的 / 换镜头，**继续跑**直到时间到。
3. 歧义按**最保守**解读（"今晚"→24:00、"早上"→次日 08:00、"一会儿"→2h），解读写入"终止条件解读"章节并在 Phase 0.5 假设中显式列出供用户 confirm。
4. **BODY 不得 `signal UNTIL(...)` 除非该信号是 UNTIL 原文成分**。示例：UNTIL="Tier 1 清完" 时 BODY 可 signal；UNTIL="到 9 点" 时 BODY **严禁** signal 任何非时间信号。

### 3. BATCH_UNTIL —— subagent 级终止（subagent 模式必填）

subagent 内每轮检查的早退条件。典型值：`"10 轮"`、`"连续 2 轮无进展"`、`"subagent context 接近耗尽"`。

**触发判定**：
- 预估总轮数 > 30 **或** 预估总耗时 > 30 min → **强制 subagent 模式**（context 隔离必需）
- 否则可选；不选则走直接执行模式（主循环自跑）

### 4. LENS —— 聚焦镜头（可选）

每轮 review / 挑项步骤收窄到该维度。示例：`"代码风格"`、`"生产级"`、`"性能热路径"`、`"tracing 覆盖"`。

- 透传给 BODY 里每个 `/pax --<子目的>`
- 镜头为空 → 全景（Tier 按项目整体演进价值排）

### 5. STATE —— 跨轮流转字段

会话本地，loop 结束即丢失。必含字段：

| 字段 | 维护方 | 用途 |
|------|-------|------|
| `skip_pool` | 失败策略 | 跨两轮失败 → 标"需人工介入"，永久跳过 |
| `commit_log` | 每轮末 | `git rev-parse HEAD` 前后对比累积 |
| `round_counter` | 每轮 | 总轮数 / 有效轮 / 无效轮 / 连续无效 |
| `elapsed` | 主循环 | 已运行时长 |
| `cooldown_current` | 每轮末 | 当前退避值 |
| `review_snapshot` | 可选 | 上轮 review 产物（BODY 若依赖增量则必需） |

subagent 模式下，主循环在派发新 subagent 时把 STATE 透传给它（prompt 里明示）。

### 6. FAILURE —— 失败分级策略

| 失败粒度 | 默认策略 |
|---------|---------|
| step 内失败 | 交给被调 purpose 的 `--auto` 规则（警告 + 自修复 + 回滚 + 继续剩余阶段） |
| 单轮整体失败 | 标记该轮 `⚠️`，继续下一轮 |
| 同一项跨两轮失败 | 加入 `skip_pool`，从待挑池永久移除 |
| 连续 3 轮无 commit | **触发 ESCALATION**（升一级搜索面 / 换子目的 / 换镜头），**不退出**。若 UNTIL 尚未到且 ESCALATION 全部耗尽，继续空转冷却等 UNTIL，不优雅退出 |
| 待挑池 / 队列耗尽 | **触发 ESCALATION**（Level 1 起），**不退出**。除非 UNTIL 原文就是"队列耗尽 / Tier 1 清完" |
| 被调 skill 不存在 / 参数错 | 警告 + 立刻退出（配置错误，非运行时问题；属"物理不可继续"） |
| subagent 返回 CONTINUE（context 耗尽） | 主循环派发新 subagent，传递 STATE |
| subagent 返回格式错误 / 无报告 | 该批次标记失败，主循环判断是否派发重试（最多 1 次） |

**ESCALATION 梯队**（UNTIL 未触发但手头活干完时的自适应升级）：

| Level | 触发 | 行为 |
|-------|------|------|
| L1 | 当前镜头 / Tier 无项可挑 | 去掉 LENS 过滤（全景 review）；Tier 1 空了降到 Tier 2 |
| L2 | L1 仍无项 | 换子目的：review → test（补盲区）→ bench（找热点）→ doc（补文档） |
| L3 | L2 仍无新改动 | 打磨类任务：改注释 / 补日志 / 提升可测性 / 收紧 static_assert / 收紧 lint |
| L4 | L3 仍无事可做（极端情况） | **空转冷却**（按指数退避但上限不变），定时重扫一遍整仓直到 UNTIL 触发 |

**铁律**：ESCALATION 全部耗尽仍没到 UNTIL 时，**继续空转等时间到，绝不提前退出**。时间类 UNTIL 只有时间本身能触发。

### 7. BOUNDS —— 资源边界

plan 必含数值：

```
最大轮数        : N      （安全阈；到达视同 UNTIL 触发）
最大耗时        : Xh     （到达视同 UNTIL 触发）
单轮超时        : 2h     （防 subagent 卡死；超时杀 subagent，走 CONTINUE 分支）
最大累计 commit : N      （防爆炸式 commit）
磁盘下限        : 1 GiB  （触发即退）
```

任一触发 → 优雅退出 + 在总汇报标注触发原因。

### 8. MODE —— 执行模式

Phase 3 自检时判定：

- 预估 > 30 轮 OR > 30 min → **subagent 模式**（BATCH_UNTIL 必填）
- 其他 → **直接执行模式**（主循环自跑）

用户显式指定可覆盖自动判定，但要给警告（如手动选直接模式跑 50 轮会爆 context）。

### 9. OUTPUTS —— 汇报格式

**每轮头部**（每轮开始前输出）：

```
╔══════════════════════════════════════════════════════╗
║  🔁 /pax --loop · 第 N 轮                      ║
╠══════════════════════════════════════════════════════╣
║  📝 BODY 摘要 ： <一句话>                            ║
║  🎯 镜头      ： <LENS / "无">                       ║
║  ⏰ 终止条件  ： <UNTIL>                             ║
║  ⚙️  模式     ： <直接执行 / subagent (batch: N/M)>  ║
║  🕐 当前时间  ： <HH:MM:SS>                          ║
║  ⏳ 已运行    ： <X 小时 Y 分>                       ║
║  📊 累计      ： 轮 N · 有效 M · 无效 K · 跳过 P     ║
║  ⏱️  冷却     ： <30s/1m/…>（退避：<原因> 或"正常"）│
╚══════════════════════════════════════════════════════╝
```

**每轮结果块**（diff-stat 风格）：

```
── 第 N 轮 ✅ abc1234 · 耗时 2m18s · (lens: 代码风格) ──
修复 Gateway::reconnect() 持锁死锁
 gateway.hpp  | 18 ++++++++++++---
 endpoint.hpp |  8 ++++++++
```

状态图标：`✅` 有效（有 commit） / `➡️` 无改动 / `⚠️` 部分失败 / `❌` 需人工介入

**冷却提示**：

```
⏳ 冷却 30s 后开始第 N+1 轮...
   下次执行预计时间：HH:MM:SS
```

退避时追加 `（退避：连续 M 轮无效）`。

**终止总汇报**（循环结束时）：

```
🔁 Loop 结束

触发退出：<UNTIL 满足 / BATCH_UNTIL（仅单批次触发的情况）/ BOUNDS 触发 / 用户打断 / 空转>
终止条件解读：<AI 对 UNTIL 的保守解读>
镜头：<LENS 或"无">

统计：
  总轮数：N（有效 M · 无效 K · 跳过 P）
  总耗时：X 小时 Y 分
  总 commit：Z
  累计 diff-stat：<git diff --stat 首 commit..末 commit>

完成列表（按时间序）：
  1. <第 N 轮> ✅ <hash> — <摘要>
  2. ...

需人工介入项（skip_pool）：
  1. <项> — <原因 / 卡在哪> — <建议>

后续建议：
  • 优先看：<skip_pool 最关键项>
  • 复盘：自动调 /report retro（除非契约 --report-on-exit=off）
```

### 10. 启动后的执行纪律（施工期）

**铁律**（借自旧 /repeat，必须写入契约）：

- 只有 UNTIL / BATCH_UNTIL / BOUNDS / 用户打断才能终止
- 禁以"觉得够好了"、"看起来没什么可做的"、"队列耗尽"、"无新发现"、"两轮无 commit" 等任何**非 UNTIL 原文成分**的理由自行停
- **时间类 UNTIL 是绝对硬墙**：即使 ESCALATION 4 级全部耗尽、即使 99% 时间在空转冷却，也必须跑到时间点
- 禁轮间暂停等待用户确认
- 禁合并多轮报告（每轮一块，即使空转也要出 `➡️` 块）

**Cooldown 与指数退避**：

```
初始 cooldown : 30s
退避          : 连续无效轮时 × 2
上限          : 10 分钟
重置          : 一旦出现有效轮 → 回 30s
```

**subagent 派发模板**（subagent 模式）：

```
你在 <cwd> 下工作。继承以下 STATE（来自上一批次）：
  skip_pool      : [...]
  commit_log     : [...]
  round_counter  : N
  elapsed        : Xh Ym
  review_snapshot: <可选>

## 任务
按以下 BODY 持续重复执行（auto 模式，不暂停等确认）：

<BODY 伪代码>

镜头（LENS）：<...>

## 循环规则
- 每轮结束后先检查 BATCH_UNTIL：<...> → 满足则返回 BATCH_DONE
- 再检查 UNTIL：<...> → 满足则返回 DONE
- 若 context 接近耗尽，停止并返回 CONTINUE + 完整 STATE 快照
- 禁以任何其他理由自行终止

## 退出协议（铁律）
首行：DONE | BATCH_DONE | CONTINUE，附 "已完成 N 轮"
接下来每轮一块（格式如 OUTPUTS 所定义，禁合并）
末行：累计 N 轮 · M 次有效改动 · K commits · STATE=<...>
```

主循环**原样转发** subagent 的每轮报告给用户（subagent 输出对用户本不可见）。

### 11. 产物去向

- **每轮报告**：只输出到终端，不落盘
- **终止总汇报**：只输出到终端
- **循环结束时**：默认自动调 `/report retro --auto`（复盘写入 `.artifacts/`，归 /report 负责）
- **契约内可关闭**：`--report-on-exit=off` 则不自动触发
- **loop 自身永不写 `.artifacts/`**（铁律：只有 /report 落盘）

---

## 预设模板（用户描述模糊时套用）

| 模板 | BODY 核心 | 典型 UNTIL |
|------|----------|-----------|
| `EVOLVE`     | review → pick tier1 → route → build | 到时间点 / Tier 清空 |
| `POLISH`     | review(lens=style) → fix → rerun lint | 无风格项 |
| `TEST_GREEN` | run tests → fix first fail → rerun | 测试全通过 |
| `PERF_HUNT`  | bench → optimize slowest → rerun bench | p99 低于阈值 |
| `DOC_SYNC`   | watch commit → /pax --doc --auto | 用户打断 |

用户 `/pax --loop EVOLVE "聚焦生产级"` 即可套模板；也可给完全自由描述让 AI 合成 BODY。

---

## 反模式（Phase 3 自检必拦）

| 反模式 | 后果 |
|-------|------|
| BODY 没有产出 commit 的 step | 必然空转，拒绝通过 |
| 长循环（预估 >30 轮）选直接模式 | context 必爆，强制 subagent 模式或警告 |
| UNTIL 为空且无 BOUNDS 上限 | 拒绝——必须至少有一项边界 |
| BODY 嵌套另一个 `--loop` | 拒绝（初版禁递归，避免失控） |
| 未加 `--auto` 就启动 loop | 每轮都卡 ExitPlanMode——警告 + 自动补 `--auto` + 告知用户 |
| BODY 包含交互式命令（如 `git rebase -i`） | 拒绝——破坏无人值守前提 |
| subagent 模式未定义 BATCH_UNTIL | 拒绝——等于永不退的 subagent |
| FAILURE 策略缺失（尤其跨轮失败） | 拒绝——会陷入死循环重试 |
| **时间类 UNTIL 与非时间信号合取 / 析取**（例 UNTIL="9点" 但 Phase 0.5 假设列作 "9点 或 队列耗尽"）| **拒绝**——时间类 UNTIL 必须原封不动，不允许加隐式出口 |
| **BODY 在非成分信号上 signal UNTIL**（例 UNTIL="9点" 但 BODY 写 `if tier_empty: signal UNTIL`）| **拒绝**——signal 的内容必须是 UNTIL 原文成分 |
| ESCALATION 梯队缺失（BODY 把"无项可挑"当退出路径而非升级路径） | **拒绝**——必须有 L1-L4 的自适应兜底 |

---

## 与其他目的 / skill 的集成约束

- **BODY 调 `/pax --<子目的>` 必须显式 `--auto`**（否则每轮都卡 ExitPlanMode）
- **BODY 调 `/report` 必须显式 `--auto`**（否则每轮都要等草稿确认）
- **BODY 不允许调 `/pax --loop`**（禁递归）
- **BODY 可调 `/script --auto`**（如每轮末跑部署健康检查脚本）
- **`--deep` 可与 `--loop` 叠加**，但会警告："每轮施工 deep 讨论会显著拖慢，请确认"

---

## Plan 独有章节（Phase 4 插入位置：紧跟"目标形态"之后）

```markdown
## 循环契约

### 镜头（LENS）
<聚焦维度 / "无">

### 循环体（BODY）
<伪代码 step-by-step>

### 终止条件（UNTIL）
<自然语言>

**解读**：<AI 的结构化理解，含类别 + 检查方式>

### 批次终止（BATCH_UNTIL，仅 subagent 模式）
<自然语言 + 解读>

### 状态流转（STATE）
<字段清单 + 谁维护>

### 失败策略（FAILURE）
<各粒度处理>

### 资源边界（BOUNDS）
- 最大轮数        : N
- 最大耗时        : Xh
- 单轮超时        : 2h
- 最大累计 commit : N
- 磁盘下限        : 1 GiB

### 执行模式（MODE）
<直接执行 / subagent —— 附理由（预估轮数、预估耗时）>

### 预期行为估算
- 预计每轮耗时：<>
- 预计总轮数：<>
- 预计总 commit：<>
- 预计磁盘增量：<>

### 汇报 / 产物
- 每轮终端输出（头部 + 结果块 + 冷却）
- 终止总汇报
- `--report-on-exit`：retro（默认）/ decision / off
```

实施计划章节退化为一个特殊阶段：

```
### 阶段 1: 启动并监督循环直到 UNTIL 触发
- 目标: 按契约执行循环，直到任一终止条件触发
- 具体动作:
  1. 初始化 STATE（空 skip_pool / commit_log 设为当前 HEAD / 计数器清零）
  2. 按 MODE 进入执行层（直接 / subagent dispatcher）
  3. 每轮严格按 OUTPUTS 输出格式；禁省略、禁合并
  4. 每轮末按 FAILURE / Cooldown 规则更新状态
  5. 每轮末检查 UNTIL / BOUNDS；subagent 模式另查 BATCH_UNTIL
  6. 触发退出 → 输出总汇报；如 --report-on-exit=retro 调 /report retro --auto
- 交付物: 总汇报（终端）+ 可选的 /report retro 产物
- 验收标准: 终止触发原因明确、每轮报告完整、STATE 一致
- 施工纪律: 上述铁律；不暂停、不省略、不合并、不自行停
- 风险等级: <中 / 高（按 UNTIL 宽度和 BOUNDS 估算）>
- 风险点 & 预警信号:
  - 连续 3 轮无 commit（空转）
  - subagent 连续 CONTINUE（context 不够，需减 BATCH_UNTIL 粒度）
  - skip_pool 持续膨胀（项质量差或 FAILURE 过严）
- 依赖的前置阶段: 无
- 回滚点: 无（循环是前进式；单轮回滚由被调 purpose 负责）
- 生产级自检要点: 每轮被调 purpose 的生产级考量由其自身负责；loop 只监督进度 / 资源 / 失败
```
