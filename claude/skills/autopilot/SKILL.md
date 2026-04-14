---
name: autopilot
description: "Long-running unattended task orchestration — quick pre-flight + contract dialogue (≤5min), background task launch, periodic wakeup monitoring, autonomous exception handling within explicit authorization, final consolidated report. Self-healing within contract boundaries; escalates via artifact reports when encountering unauthorized situations. TRIGGER when: user wants to run a long task unattended and needs supervised autonomy (e.g. multi-hour builds, training jobs, data pipelines, benchmark sweeps); user says \"run this unattended\", \"watch this task\", \"无人值守\", \"跑完这个任务\" for long jobs. DO NOT TRIGGER when: task is short enough to watch directly; user wants simple cron scheduling (use /schedule); user wants to repeat a prompt N times (use /repeat)."
argument-hint: "<task description or command> [resume] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(head:*), Bash(tail:*), Bash(grep:*), Bash(mkdir:*), Bash(date:*), Bash(git:*), Bash(ls:*), Bash(pwd:*), Bash(df:*), Bash(which:*), Bash(ps:*), Bash(kill:*), Bash(test:*), Bash(wc:*), Bash(echo:*), Bash(stat:*), Bash(jq:*), Bash(awk:*), Bash(sed:*), Bash(tee:*), Bash(chmod:*), Bash(nohup:*), Bash(sh:*), Bash(bash:*)
---

# /autopilot

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
已有 autopilot 状态：!`ls .artifacts/autopilot-state-*.json 2>/dev/null || echo "(无)"`
可用磁盘：!`df -h . 2>/dev/null | tail -1 || echo "(未知)"`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`
Blueprint 感知：!`cat ~/.claude/skills/shared/blueprint-aware.md`

任务：$ARGUMENTS

---

## 核心理念

> **契约 + Checkpoint + 确定性分类器 = 跨 wakeup 连续性的三角支柱。**
>
> 长任务无人值守的关键不是让 Claude 更聪明，而是把 Claude 的判断权严格约束到书面契约（`INTENT.md`）+ 外部化状态（`state.json`）+ 确定性事件分类器 三者构成的三角之内。
>
> **每次 wakeup 进入的 Claude 是无记忆的新实例**——它只读 ~200 行上下文（intent 摘要 + 最新 state + 分类器输出 + 日志尾 50 行），就应该能做出正确决策。任何需要跨 wakeup 记忆才能决策的动作，都是设计失败。

**两条硬约束**（不可协商）：

- **硬约束 A**：成功判据必须是**可 shell 判定的表达式**。不可判定 → 预检不结束。
- **硬约束 B**：运行期间 Claude Code 主进程必须保持运行（最小化 OK，关闭不 OK）——预检必须明示用户。

**两层自主度**：

- **L1（可逆操作）**：读日志、重启子进程（符合授权条款）、切 wakeup 节奏、在 `.artifacts/` 内写文件 → 自动执行 + 记录
- **L2（其他全部）**：必须在 `INTENT.md` 授权清单里显式列出（条件 + 动作 + 次数上限），否则停下升级报人

**禁止**：跨 wakeup 的"同态推理"、类比历史 lesson 执行新策略、动态决定 wakeup 节奏。

---

## 参数解析

- **任务描述/命令**（必填）：要无人值守执行的任务。可以是自由描述（`"跑完整套集成测试"`）或具体命令
- `resume`：检测到已有同名 task state 时恢复运行（否则询问用户）
- `auto`：无人值守对话模式——预检对话中的不确定点按最保守理解处理，所有软停下默认继续观察

---

## Phase 0: 环境收集 & 重入保护

### 0.1 环境探测

```
[ ] 读取当前目录构建配置（按构建命令获取策略）
[ ] 确认 .artifacts/ 存在且可写
[ ] 确认磁盘剩余空间
[ ] 检查 git 状态（工作区是否干净，影响 rollback 可行性）
[ ] 若项目有 blueprint.md，按 Blueprint 感知约定读取约束
```

### 0.2 重入保护

若 `.artifacts/autopilot-state-*.json` 存在，按状态字段分类：

| state.status | 含义 | 行为 |
|--------------|------|------|
| `running` | 有正在运行的 autopilot | `ps -p <pid>` 确认进程——存活则询问"查看/介入/终止"，不存在则按 `crashed` 处理 |
| `crashed` | 上次意外中断 | 询问"从 checkpoint 恢复 / 重新预检 / 查看报告 / 放弃" |
| `escalated` | 软停下待用户处理 | 读取最新报告展示，询问"继续观察 / 介入修改 INTENT / 终止" |
| `finished` | 已完成 | 展示报告路径，询问是否归档后开始新任务 |

`auto` 模式：`running` 保持不动、`crashed` 自动恢复、`escalated` 继续观察、`finished` 归档后继续。

---

## Phase 1: 快速验证 + 契约对话（≤5 分钟硬上限）

**总预算**：5 分钟。超时未完成契约 → 暂停并告知用户是哪一节卡住，**拒绝进入 Phase 2**。

### 1.1 前 2 分钟：并行环境探测 + 可判定性预检

**并行项**（Claude 可一边对话一边跑）：

```
[ ] 任务启动命令的语法合法性（shellcheck / dry-run）
[ ] 任务依赖的命令/库是否存在（which / 版本）
[ ] 预估资源需求（内存、磁盘、网络）vs. 可用资源
[ ] 用户给出的成功判据是否可改写为 shell 表达式
```

**成功判据可判定性检查**：

| 用户表述 | shell 判定模板 | 可判定 |
|---------|----------------|--------|
| "进程正常退出" | `test $exit == 0` | ✅ |
| "文件 X 存在且非空" | `test -s <path>` | ✅ |
| "日志出现 DONE" | `grep -q '^DONE' <log>` | ✅ |
| "输出行数 ≥ N" | `test $(wc -l < <file>) -ge N` | ✅ |
| "指标 loss < 0.03" | `awk '/loss/{if($NF<0.03) exit 0}END{exit 1}' <log>` | ✅ |
| "结果看起来合理" | — | ❌ 需要弱化 |

若不可判定 → 询问用户：

```
⚠️ 成功判据无法 shell 判定。请选择：
  [A] 弱化为"进程正常退出 + 输出文件非空"
  [B] 提供一个手写验证脚本路径
  [C] 仅使用"任务退出码 == 0"（仅适用于简单任务）
  [D] 我来改写（用户重新描述判据）
```

### 1.2 后 3 分钟：预填 → 审核模式的契约对话

**Claude 根据任务类型预填 80% 的 `INTENT.md`**，用户只补最关键的三节：

1. **结果敏感参数**（skill 绝对不得自主调整的参数 —— 训练类的 `seed/lr/batch_size`、测试类的 `test-threads`、数据处理类可能为空）
2. **红线特例**（本项目/本环境的额外禁止，例如"不得碰 `/var/lib/prod`"）
3. **授权清单细化**（Claude 预填通用条款，用户填具体的次数上限和允许修改的配置字段）

### 1.3 `INTENT.md` 定稿 & 分裂存储

定稿后拆分为两份文件（存到 `.artifacts/`）：

- `autopilot-intent-<task>-summary.md` ≤ 100 行，**wakeup 必读**，包含：一句话目标、成功判据（shell 表达式）、红线摘要、当前阶段
- `autopilot-intent-<task>-full.md` 完整条款，**按需 grep**，包含所有授权细节和软停下规则

**`INTENT.md` 完整骨架**：

```markdown
# INTENT: <task-name>

## 1. 任务本体
- **一句话目标**：<...>
- **启动命令**：`<command>`
- **预计耗时**：<...>
- **成功判据**（必须可 shell 判定）：
  - 判据 A：`<shell-expression>`
  - 判据 B：`<shell-expression>`

## 2. 事实前提（预检已确认，若运行时失效需重新预检）
- [x] 依赖 X 已安装（`<which-output>`）
- [x] 磁盘空间 > <N> GB
- [x] **Claude Code 主进程将保持运行**（wakeup 前提）
- [x] 任务输出路径可写：<path>

## 3. 授权清单（L2 操作，每条必须含条件 + 动作 + 次数上限）
- [ ] **重启挂掉的子进程**
      条件：exit code ∉ {0, 130, 143}，且 restart_count < 3
      动作：以原命令重启，记录到 state.restart_history
      上限：3 次
- [ ] **清理临时文件以释放磁盘**
      条件：df 可用空间 < 1GB
      动作：rm `<tmp-dir>/*`（不得出此路径）
      上限：无
- [ ] **<其他条款>**

## 3.5 结果敏感参数（skill 不得自主调整）
- <参数 1>：<为什么敏感>
- <参数 2>：...

## 4. 红线（命中立即终止任务 + 写报告 + 升级报人）
- `git push` / `git reset --hard` / `git push --force`
- `rm` 任何 `.artifacts/` 之外的文件
- 修改 `INTENT.md` 自身
- 对外部系统的写操作（数据库、云 API、消息发送）
- <项目特有红线>

## 5. 软停下（升级报人但不强制终止任务）
- 同一类错误连续 3 次无法自愈
- 进度 30 分钟无推进
- 磁盘 / 内存 / CPU 异常持续 5 分钟
- 任何 L2 操作到达次数上限

## 6. 汇报协议
- 最终报告：`.artifacts/autopilot-report-<task>-<timestamp>.md`
- 异常事件集中在报告顶部 `## ⚠️ 需要用户关注` 章节
- 软停下期间每次 wakeup 刷新报告
```

### 1.4 预检结束确认

```
┌─────────────────────────────────────────────┐
│  ✋ 契约已就绪，准备启动任务                  │
├─────────────────────────────────────────────┤
│  任务    ： <一句话>                          │
│  成功判据： <N 条，shell 可判定>               │
│  授权条款： <M 条>                            │
│  红线    ： <K 条>                            │
│  预计耗时： <...>                             │
│                                             │
│  ⚠️ 请勿关闭 Claude Code（可最小化）           │
│  ⚠️ wakeup 将持续触发至任务结束                │
│                                             │
│  回复「启动」开始，或提出修改                  │
└─────────────────────────────────────────────┘
```

**`auto` 模式**：不暂停，直接进入 Phase 2。

---

## Phase 2: 启动 + 初始化 state.json

### 2.1 初始化状态文件

写 `.artifacts/autopilot-state-<task>.json`：

```json
{
  "task": "<task-name>",
  "status": "starting",
  "intent_version": "<sha256 of intent-full.md>",
  "start_time": "<ISO-8601>",
  "command": "<启动命令>",
  "pid": null,
  "log_path": ".artifacts/autopilot-log-<task>.txt",
  "wakeup_phase": "startup_protection",
  "wakeup_count": 0,
  "progress": { "estimated_percent": 0, "last_advance_at": null },
  "events": [],
  "actions": [],
  "restart_history": [],
  "escalate": false,
  "escalate_reasons": []
}
```

### 2.2 启动任务

使用 `Bash(run_in_background=true)` 启动。PID 与日志路径写入 state。

### 2.3 切换 wakeup 循环

```
ScheduleWakeup(
  delaySeconds=60,
  prompt="<<autonomous-loop-dynamic>>",
  reason="autopilot <task>: startup protection (60s × first 5min)"
)
```

**复用 `<<autonomous-loop-dynamic>>` sentinel**。本轮主会话到此结束——**不继续观察，不多说一句话**，把上下文让给新的 wakeup Claude。

---

## Phase 3: Wakeup 监控循环

每次 wakeup 进入的 Claude **必须且只能**执行以下流程：

### 3.1 读取上下文（≤200 行）

```
[ ] .artifacts/autopilot-intent-<task>-summary.md        （~100 行）
[ ] .artifacts/autopilot-state-<task>.json               （JSON）
[ ] 分类器输出：bash shared/autopilot-classifier.sh <task>  （≤30 行）
[ ] 日志尾 50 行：tail -50 <log_path>
```

**不读** full intent、不读完整日志、不读历史 lessons——这些是爆 context 的源头。

### 3.2 确定性红线检查（grep-based，不依赖 Claude 判断）

```
红线命中 = 以下任何一条为真：
  - 日志尾包含 INTENT.md 红线关键字（预检时生成 grep 模式列表）
  - state.escalate_reasons 包含 "redline_*"
  - 分类器输出 severity=critical
```

**命中红线** → 立即执行：
1. `kill <pid>`（若进程还在）
2. 更新 state: `status=terminated_by_redline`
3. 生成最终报告（跳到 Phase 4）
4. **不再 ScheduleWakeup**，循环终止

### 3.3 事件分类 → 决策

读取分类器输出的 `{severity, category, suggested_action, evidence}`：

| severity | category | 决策 |
|----------|----------|------|
| `ok` | `running` | 无异常 → 更新进度 → 按节奏模板定下次 wakeup |
| `ok` | `finished_success` | 跑成功判据验证脚本 → 成功则跳 Phase 4 |
| `ok` | `finished_failure` | 按授权条款看能否恢复 → 不能则升级 |
| `warning` | `*` | 切 warning 密检节奏（270s × 3） |
| `error` | `<type>` | **匹配授权条款**：grep full-intent 找对应条款 → 若匹配且未超上限 → 执行动作 → 写 action record → 密检节奏；若未匹配或超上限 → 升级 |
| `critical` | `*` | 红线处理（见 3.2） |

**策略选择排序**（仅在多条款同时匹配时用）：

```
保护已有进度 > 最小破坏 > 最保守
```

每条 action 写入 `state.actions[]`：

```json
{
  "timestamp": "...",
  "trigger_event": {...},
  "matched_clause": "3.授权清单.第2项",
  "action": "<具体命令>",
  "result": "success|failure|partial",
  "sequence": 1
}
```

### 3.4 升级（软停下）

升级 = `state.escalate = true` + 追加 `escalate_reasons` + 刷新报告，**不终止任务**，继续观察：

- 连续 3 次同类错误无法自愈
- 进度 30 分钟无推进
- 任何 L2 授权次数上限用尽
- 任何前提条件（Phase 2 的事实前提）失效

`auto` 模式：升级但不暂停；主会话恢复后用户看报告。

### 3.5 Wakeup 节奏模板（硬编码，禁止动态决定）

| 阶段 | `wakeup_phase` 字段 | 间隔 | 进入条件 |
|------|---------------------|------|----------|
| 启动保护期 | `startup_protection` | 60s | 任务启动后前 5 分钟 |
| 稳定期 | `stable` | 1500s | 启动保护期结束且无异常 |
| Warning 密检 | `warning_watch` | 270s × 3 次 | 检测到 warning |
| 错误密检 | `error_recovery` | 120s × 5 次 | 执行过 L2 动作后 |
| 收尾期 | `finishing` | 600s | 进度 > 90% |

**禁用 300s**——落在 `ScheduleWakeup` 的缓存 TTL 陷阱里（付 miss 成本又不摊薄）。

### 3.6 下次 wakeup

```
ScheduleWakeup(
  delaySeconds=<按表确定>,
  prompt="<<autonomous-loop-dynamic>>",
  reason="autopilot <task>: <phase> (progress: <X>%)"
)
```

然后**立即结束本轮**，不做任何其他事。

---

## Phase 4: 终止 & 最终汇报

触发条件：
- 成功判据命中（分类器报告 `finished_success` 并验证脚本通过）
- 任务退出且无法恢复
- 红线命中
- 用户手动介入终止

### 4.1 收尾动作

```
[ ] 更新 state.status = "finished" | "terminated_by_redline" | "failed"
[ ] state.end_time 写入
[ ] 若 pid 还存活且需要终止 → kill <pid>
[ ] 跑成功判据验证脚本，结果写 state.success_verified
```

### 4.2 生成最终报告

按产物存储约定输出 `autopilot-<task>-<timestamp>.md`：

```markdown
# Autopilot Report: <task>

## ⚠️ 需要用户关注

<按严重度倒序列出：红线事件、升级事件、自主处置动作、未解决的告警>

## 概况
- 任务：<一句话>
- 开始：<时间>
- 结束：<时间>
- 总耗时：<X 小时 Y 分>
- 最终状态：✅ 成功 / 🔴 红线终止 / ⚠️ 升级 / ❌ 失败
- 成功判据验证：<pass / fail / n/a>

## 执行时间线
| 时间 | 阶段 | 事件 | 处置 |
|------|------|------|------|
| ... | startup | 任务启动 PID <pid> | - |
| ... | stable | warning: 磁盘使用率 85% | 清理 tmp（授权 #2） |
| ... | ... | ... | ... |

## 自主处置记录
<完整复现 state.actions[]，每条含：触发事件、匹配条款、执行动作、结果>

## 资源使用
<若可获取：CPU/内存/磁盘峰值、网络字节数>

## Lessons（供下次同类任务预检参考）
- 本次遇到但 INTENT.md 未覆盖的情况：<...>
- 建议下次预检追加的授权条款：<...>
- 建议下次预检追加的红线：<...>

## 最终产物
- 任务输出：<路径>
- 任务日志：<.artifacts/autopilot-log-<task>.txt>
- 状态文件：<.artifacts/autopilot-state-<task>.json>
```

### 4.3 归档

```
[ ] state.json 移到 .artifacts/archive/autopilot-state-<task>-<timestamp>.json
[ ] 不删除 log（供用户复盘）
[ ] INDEX.md 追加一行
```

---

## 异常流程

### 预检超时（>5 分钟未完成契约）

```
⚠️ 预检 5 分钟上限已到，仍有 N 项未完成：
  - <未完成项>

选择：
  [1] 延长 3 分钟重试
  [2] 弱化到最小可启动契约（仅成功判据 + 红线通用集）
  [3] 放弃本次预检
```

`auto` 模式：选 [2]。

### 分类器脚本异常（wakeup 内）

若 `shared/autopilot-classifier.sh` 执行失败（exit code 非 0）：
1. 视为 severity=warning，category=classifier_failure
2. 切 warning 密检
3. 连续 3 次失败 → 升级（`escalate_reason=classifier_broken`）

**不**让 Claude 手写现场分类器——那是 prompt 泄露路径。

### Context 耗尽（wakeup 内发现自己读了太多）

若本轮 wakeup 已经读了超过 400 行日志（意外情况），立即：
1. 放弃当前轮的决策
2. 在 state 追加 `context_overflow_at: <time>`
3. ScheduleWakeup 到下一个节奏点
4. 下次 wakeup 的 Claude 从干净 state 开始

### 任务成功判据脚本本身报错

当作"未完成 + 可能已完成"处理：
1. 升级 `escalate_reason=success_verifier_broken`
2. 不自动终止任务（任务可能在跑完成后的清理）
3. 用户必须手动判定

---

## 关联 skill

- **`/discuss`**：本 skill 的设计依据存在 `.artifacts/discuss-20260415-000000.md`
- **`/debug`**：升级后用户介入时可调用 `/debug` 诊断失败根因
- **`/loop`**（Claude Code 内建）：共享 `<<autonomous-loop-dynamic>>` sentinel 协议
- **`/repeat`**：不同语义——`/repeat` 是重复执行同一动作，`/autopilot` 是看护单一长任务
- **`/schedule`**：若用户需要"每天定时触发一次 autopilot"可组合使用

---

输出语言跟随用户输入语言。
