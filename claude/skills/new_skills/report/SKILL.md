---
name: report
description: "系统里唯一写入持久化产物的 skill。把会话中的决策 / 计划 / 发现 / 改动 / 复盘 / 实验落盘到 .artifacts/，并按读者定制：decision（决策记录）/ status（周报 / 绩效）/ incident（事故复盘）/ issue（问题报告）/ release（发布说明）/ retro（反思复盘）/ experiment（实验报告）。自动从会话 context + git log + .artifacts/ 收集素材。默认生成草稿供用户预览再落盘；--auto 直接落盘。TRIGGER when: 用户要记下决策 / 写周报 / 事故复盘 / 报 issue / 写 release notes / 做 retro / 写实验报告；说\"存一下\" / \"汇报\" / \"记录下来\" / \"告诉用户\"。DO NOT TRIGGER when: 用户要核查代码（用 /blueprint --review）；要做规划（用 /blueprint --<目的>）。"
argument-hint: "[<mode>] [<主题或补充素材>] [--auto] [--no-commit]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(ls:*)
---

# /report

ASCII 可视化原则：!`cat ~/.claude/skills/new_skills/shared/ascii-viz.md`

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
最近提交：!`git log --oneline -10 2>&1`
既有 INDEX：!`cat .artifacts/INDEX.md 2>&1 | head -30`

主题 / 补充素材：$ARGUMENTS

---

## 定位

`/report` 是 skill 系统里**唯一写入持久化产物**的 skill。其他所有 skill（包括 `/blueprint`）都不落盘——需要留存时用户**必须显式**调用 `/report`。

**铁律**：
- `/blueprint` 的 9 个目的产物（计划、施工日志、改动总结、审查发现、bench 数据…）**全部不自动落盘**
- 只有 `/report` 写 `.artifacts/`
- 一次会话可多次 `/report`，每次独立文件
- 每次落盘必须更新 `.artifacts/INDEX.md`

这个边界让产物归属清晰：**用户主动说"存下来"才存**，避免 `.artifacts/` 堆积失控。

---

## 核心职责

1. **留存**：把会话中已有的决策 / 计划 / 发现 / 改动 / 讨论持久化
2. **对外报告**：给人类读者（经理 / 团队 / 客户 / 用户）写正式报告
3. **复盘**：会话后的 retrospective、lessons learned
4. **索引与归档**：`.artifacts/` + `INDEX.md` 统一可检索
5. **读者适配**：不同 mode 对应不同读者，语气 / 侧重 / 深浅各不相同

---

## 输出形态

- 每次调用产出一个 Markdown 文件：`.artifacts/<mode>-YYYYMMDD-HHMMSS.md`
- 更新 `.artifacts/INDEX.md`：追加一行 5 列记录 `| 时间 | mode | 摘要 | Commit | 文件 |`
- 默认流程生成**草稿**供用户预览 → confirm / 修改 → 才真正落盘
- `--auto` 模式跳过预览直接落盘

---

## Mode 清单（7 种）

| mode | 时态 | 读者 | 关键差异点 |
|------|------|------|-----------|
| `decision`   | 已决 / 未决推销（都含） | 未来的自己 / 团队 / 决策者 | 记录"为什么选这个 + 否决了什么" |
| `status`     | 任意周期（周 / 月 / 季 / 绩效） | 上级 / 团队 | 做了什么 + 进度 + 量化指标 + 风险 |
| `incident`   | 已发生 | SRE / 客户 / 管理层 | 时间线 + 根因 + 影响 + 缓解 + 预防 |
| `issue`      | 发现中 | 协作者 / 自己 backlog | 现象 + 复现 + 上下文 + 建议调查方向 |
| `release`    | 已发布 | 终端用户 | 新能力 + break + 升级指引 |
| `retro`      | 事后 | 自己 / 团队 | 做对 / 做错 / 下次怎么改（反思性） |
| `experiment` | 验证后 | 自己 / 团队 | 假设 → 方法 → 数据 → 结论 |

每个 mode 在 `modes/<mode>.md` 中独立定义：**读者画像 / 必含章节 / 素材收集侧重 / 语气 / 禁忌 / ASCII 图示要求**。通用骨架由本 SKILL.md 统一规定。

---

## Mode 自动推断

若用户未显式指定：

| 关键词 / 语境 | 推断 mode |
|-------------|----------|
| "记下决策"、"ADR"、"留存设计记录"、"技术提案"、"推动这件事" | decision |
| "周报"、"status"、"本周进展"、"绩效"、"今年做了什么"、"汇报" | status |
| "事故"、"故障"、"出事了"、"post-mortem" | incident |
| "记个 issue"、"记下来这个问题"、"发给同事让他修"、"bug 报告" | issue |
| "release notes"、"发布说明"、"告知用户"、"v X.Y.Z 发布了" | release |
| "复盘"、"retro"、"lessons learned"、"总结经验教训" | retro |
| "实验报告"、"验证了 X"、"假设 vs 实际" | experiment |
| 无法推断 | 反问用户（默认模式）/ 按 context 最可能的选（auto 模式） |

推断后输出：`▶ Mode：<mode>（从"<证据>"推断）`

---

## 参数

```
/report [<mode>] [<主题或补充素材>]
  [--decision | --status | --incident | --issue | --release | --retro | --experiment]
  [--auto]          无人值守：跳过预览直接落盘
  [--no-commit]     生成报告后不自动 git add + commit .artifacts/ 改动（默认会）
```

### `--auto` 语义

和 blueprint 的 `--auto` 一致：全自动、无需批准、自动处理任何情况。

- 素材缺失 → 警告 + 用可得信息生成，缺失项在报告中标注 `[待补充]`
- mode 无法推断 → 警告 + 按 context 最可能的选
- 不反问用户，所有可推断的按保守解释继续
- 只有物理上无法继续（磁盘满、无法写入、用户中断）才停下

---

## 流程

```
Phase 0   Mode 分流 + 加载 mode 骨架
Phase 1   素材收集（从会话 context、git、.artifacts/、用户补充）
Phase 2   按 mode 骨架组织内容、适配读者
Phase 3   一致性自查
Phase 4   草稿预览（默认） / 直接落盘（auto）
Phase 5   落盘：写 .artifacts/<mode>-*.md + 更新 INDEX.md + （默认）git commit
Phase 6   输出确认
```

---

## Phase 0: Mode 分流 + 加载 mode 骨架

- 确认 mode（显式指定或自动推断）
- 读取对应骨架文件：

```
decision    → Read ~/.claude/skills/new_skills/report/modes/decision.md
status      → Read ~/.claude/skills/new_skills/report/modes/status.md
incident    → Read ~/.claude/skills/new_skills/report/modes/incident.md
issue       → Read ~/.claude/skills/new_skills/report/modes/issue.md
release     → Read ~/.claude/skills/new_skills/report/modes/release.md
retro       → Read ~/.claude/skills/new_skills/report/modes/retro.md
experiment  → Read ~/.claude/skills/new_skills/report/modes/experiment.md
```

骨架文件只写独有内容——通用骨架（结构、素材收集、共享约束、落盘流程）全部在本 SKILL.md。

---

## Phase 1: 素材收集（三级优先）

`/report` 的价值之一是**最大程度自己收集素材**，不把工作推给用户。**铁律**：遇到关键信息缺失时，按以下优先级处理：

```
1. 主动获取（首选）
2. 询问用户（默认模式）/ 警告留空（auto 模式）
```

### 1.1 主动获取（优先级最高）

在向用户要任何信息**之前**，必须先尝试自主获取：

**从会话上下文**：
- blueprint plan（ExitPlanMode 呈交过的内容）
- 讨论内容、用户意图、关键决策、否决的方案
- 会话中执行过的命令输出（测试结果、bench 数据、错误消息）
- 施工阶段的改动清单、commit message、每阶段完成汇报

**从 git**：
- `git log` 相关时间范围的 commit（按 Conventional Commits 类型分组）
- `git diff` 查看具体改动
- `git blame` 追溯某行变更历史
- `git show <hash>` 查看特定 commit 的详情
- `git tag` 查看发布历史

**从文件系统**：
- 读取 `.artifacts/INDEX.md` 获取历史上下文
- 读取相关 `.artifacts/*.md` 交叉引用
- 读取 `CHANGELOG.md`、`README.md`、配置文件
- grep 代码库确认某个符号 / 模式是否存在

**从工具推断**：
- 版本号 → 查 `Cargo.toml` / `package.json` / `pyproject.toml`
- 时间范围 → 若未指定，默认"上次同 mode 报告至今"（查 INDEX.md）
- 环境信息 → 查 OS / 工具链版本
- 复现命令 → 查 README / CLAUDE.md 的"how to build / test / bench"

**原则**：
- 对每一项缺失信息，**先问自己**："我能否通过读取文件 / 执行只读命令 / 查 context 获取？"
- 能获取的必须主动获取，不允许偷懒把工作推给用户
- 自主获取到的信息在报告中标明来源（如 "Commit 范围: a1b2c3d..HEAD（从 git log 获取）"）

### 1.2 询问用户（默认模式）/ 警告留空（auto 模式）

自主获取仍无法获得，且是**关键信息**（不填将导致报告不合格）：

**默认模式**：
- 向用户明确列出"已自主获取到的" + "仍需要补充的"
- 询问格式：

  ```
  📋 素材收集
  
  已自主获取：
    ✓ <信息 1>（来源：<来源>）
    ✓ <信息 2>（来源：<来源>）
    ...
  
  仍需你提供：
    ? <信息 A> —— 因为 <为什么必要>
    ? <信息 B> —— 因为 <为什么必要>
  
  请补充以上信息。无法提供的可以说"跳过" —— 该字段会被标为 [待补充]。
  ```
- 用户提供后继续；用户说"跳过"则按 auto 模式处理（警告 + 标 `[待补充]`）

**auto 模式**（不反问用户）：
- 在 stderr / 输出中警告缺失的关键信息
- 在报告中标注 `[待补充：<具体描述什么信息，为什么必要>]`
- 继续生成报告，不中断流程
- 最终确认输出中汇总所有"标 [待补充] 的字段"

### 1.3 非关键信息

对于"有更好，没有也行"的信息（如贡献者致谢、某些附加上下文），**不询问**，主动获取不到就省略。

### 1.4 关键信息判定（按 mode）

什么算"关键信息"由 mode 骨架定义——若缺失会让该 mode 报告失去价值的字段。各 mode 的关键信息示例：

- **decision**：决策内容、候选方案至少 1 个、理由
- **status**：时间范围、完成清单、量化指标
- **incident**：事故时间线、影响范围、根因
- **issue**：现象、复现步骤、环境信息
- **release**：版本号、Breaking changes（有则必须）、升级指引
- **retro**：做对 / 做错清单、教训
- **experiment**：假设、方法（环境 + 数据集 + 测量）、原始数据、结论

骨架文件的"必含章节"清单本身就是关键信息清单——缺失任一关键字段就必须先尝试主动获取，再询问 / 警告。

### 1.5 特殊素材

bench 基线数据、火焰图、profile 数据走 `experiment` mode 留存，带完整复现上下文注释：

```
# Reproduced: YYYY-MM-DD HH:MM
# Commit: <hash> (clean/dirty)
# Compiler: <version>
# Build: <完整构建命令>
# Bench: <完整 benchmark 命令>
# Profile: <编译配置摘要>
# ---
<工具原始输出>
```

大体积原始数据可以单独存 `bench-data-*.txt` / `callgrind-*.out` / `flamegraph-*.svg` 并在报告中引用。

### 1.6 反模式

- ❌ 不查 context 就问用户"你想报告什么"
- ❌ 不看 git log 就问用户"本周做了什么"
- ❌ 不读 .artifacts/ 就问用户"上次状态如何"
- ❌ auto 模式下反问用户
- ❌ 把可推断的信息（版本号、时间范围、commit 范围）当作要用户提供
- ❌ 默认模式下不列"已自主获取" —— 用户看不到你做了什么工作，会重复提供

---

## Phase 2: 按 mode 骨架组织 + 读者适配

按 Phase 0 读入的 mode 骨架执行。骨架定义了：
- 该 mode 的读者画像（给谁看）
- 必含章节
- 语气 / 深度 / 禁忌
- ASCII 图示要求

**所有 mode 共用的组织原则**：

### 2.1 结论先行

第一屏（< 15 行）必须能回答读者最关心的问题。技术细节和证据放后面。

```
## TL;DR
<1-3 句话：最重要的结论 / 状态 / 发现>
```

### 2.2 数据驱动

不允许空话：
- ❌ "做了很多事"
- ✅ "本周完成 N 个 commit、关闭 M 个 issue、修复 K 个 bug"
- ❌ "性能提升了"
- ✅ "p99 从 120ms 降到 85ms（-29%）"
- ❌ "这个方案更好"
- ✅ "方案 A 在 X 维度优于方案 B（具体数据 / 对比）"

每个结论都要有锚点：commit hash、时间戳、文件位置、INDEX 条目、具体指标。

### 2.3 读者适配

**语言深浅**按 mode 不同：
- 对终端用户（release） → 避免术语、多用例子
- 对经理（status） → 结论 + 进度 + 风险 + 量化
- 对工程师（decision / retro / experiment / issue）→ 技术细节可以详
- 对客户（incident）→ 透明 + 避免推卸 + 明确补救

**侧重**按 mode 不同：
- status / achievement-flavored ： 完成了什么 + 量化贡献
- incident / retro：根因 + 教训 + 预防
- decision：权衡 + 理由
- release：用户视角的新能力 + break
- experiment：假设 + 数据 + 结论
- issue：现象 + 复现 + 上下文（让接手人有足够信息继续）

### 2.4 锚点清晰

每份报告必须有明确的"回溯信息"：
- 时间戳（报告生成时 + 覆盖的时间段）
- 相关 commit hash（最好是 short hash + 链接格式）
- 相关 .artifacts/ 文件（若交叉引用）
- 相关 issue / PR 号（若适用）

### 2.5 ASCII 可视化

按 shared/ascii-viz.md 原则使用。report 尤其适合：
- 时间线（incident / retro / status）
- 流程 / 因果图（incident 根因追踪）
- 对比表（experiment / decision 候选对比 / release break 前后）
- 进度 / 完成度（status）
- 改动分布（release / status）

### 2.6 自我一致

- 结论、数据、建议要对得上
- 不允许前文说"OK"后文说"有严重风险"
- 各章节不冲突

---

## Phase 3: 一致性自查

生成草稿后自检：

- **结论先行**：TL;DR 在第一屏？
- **数据充分**：每个结论都有锚点？
- **读者适配**：语气 / 深度符合该 mode 的读者画像？
- **自我一致**：前后不冲突？
- **锚点完整**：时间戳 / commit / 文件引用都有？
- **ASCII 图示**：关键比较 / 流程用图示而非长段文字？
- **无敏感信息**：不暴露密钥 / token / 内部路径 / PII（尤其是对客户 / 用户的报告）

任一不过 → 修正草稿。

---

## Phase 4: 草稿预览 / 直接落盘

### 默认模式

```
┌─────────────────────────────────────────┐
│  📝 草稿预览                             │
├─────────────────────────────────────────┤
│                                         │
│  mode     ： <mode>                       │
│  目标文件 ： .artifacts/<mode>-<ts>.md    │
│  长度     ： ~N 行                        │
│  锚点     ： <commit / 相关 .artifacts/>  │
│                                         │
│  <草稿全文>                              │
│                                         │
│  回复：                                  │
│  • "确认" / "落盘"  → 落盘              │
│  • "修改 X"         → 按意见修订         │
│  • "取消"           → 不落盘             │
└─────────────────────────────────────────┘
```

### `--auto` 模式

跳过预览，直接落盘。

---

## Phase 5: 落盘

1. `mkdir -p .artifacts`
2. 写入 `.artifacts/<mode>-YYYYMMDD-HHMMSS.md`（时间戳为 report 生成开始时间）
3. 更新 `.artifacts/INDEX.md`：
   - 若不存在，创建并写入表头
   - 追加一行数据
4. 默认自动 `git add .artifacts/<新文件>` + `git add .artifacts/INDEX.md` + `git commit -m "docs(report): <mode> — <摘要>"`
   - 若 `--no-commit`，跳过 commit
5. 对于大体积原始数据（bench-data / flamegraph / callgrind），单独成文件并在报告中引用

### INDEX.md 格式（5 列）

若不存在：

```markdown
# Artifacts Index

| 时间 | mode | 摘要 | Commit | 文件 |
|------|------|------|--------|------|
```

追加行示例：

```
| 2026-04-22 15:30 | decision | 选 Tokio 作为 async runtime | a7b9c2d | decision-20260422-153000.md |
```

**字段说明**：
- **时间**：`YYYY-MM-DD HH:MM` 格式
- **mode**：7 种之一
- **摘要**：一句话（< 40 字）
- **Commit**：当前 HEAD 的 short hash；若与 commit 无关 `—`
- **文件**：文件名（不含路径前缀）

---

## Phase 6: 输出确认

```
✅ 报告已保存

文件：.artifacts/<mode>-<ts>.md
INDEX：已追加第 N 条记录
Commit：<hash>（若未 --no-commit）

摘要：<一句话内容概述>
```

**若报告中含 `[待补充]` 字段**（仅 auto 模式可能出现），额外输出：

```
⚠️ 以下字段在本次生成中缺失，已标注为 [待补充]：
  - <章节 / 字段名>: <具体缺什么，为什么必要>
  - ...

建议：后续补充信息后，`/report` 重新生成此报告；或直接编辑 .artifacts/<文件>。
```

---

## 共享约束总览

所有 mode 的产物都必须：

1. **结论先行**：TL;DR 在第一屏
2. **数据驱动**：每个结论有具体锚点（数字 / hash / 时间 / 文件）
3. **锚点清晰**：时间戳 + commit + 相关 .artifacts/ 交叉引用
4. **读者适配**：按 mode 读者画像调整语言和侧重
5. **ASCII 可视化**：关键对比 / 流程用图示
6. **自我一致**：结论、数据、建议对得上
7. **无敏感信息**：不暴露密钥 / token / 内部路径 / PII

---

## 异常处理

### 素材严重不足

**默认模式**：向用户询问具体缺什么；列出"已从 context 收集到的素材" + "需要补充的素材"

**auto 模式**：警告 + 用可得信息生成，缺失项标 `[待补充：<说明>]`

### Mode 无法推断

**默认模式**：列出候选 mode + 各自适用场景，请用户选

**auto 模式**：按 context 最可能的选，输出警告

### 草稿被用户拒绝

循环：按用户意见修改 → 再次预览 → 直到 confirm 或取消

### 敏感信息检测

落盘前扫描：若发现可疑敏感信息（疑似密钥 / token / AWS key 格式 / email / 内部 IP），**停下警告**（即使在 auto 模式下也停——这是"物理阻断"类情况）

---

## 与 blueprint 的衔接

**场景**：blueprint 刚完成（审批计划、施工完毕、review 完成等），用户想留存。

```
blueprint 完成 ──▶ /report <相关 mode> ──▶ .artifacts/<mode>-*.md
```

常见搭配：

| blueprint 目的完成后 | 推荐 /report mode |
|---------------------|------------------|
| `--feat` / `--fix` / `--reshape` / `--upgrade` 施工完 | `decision`（记录关键决策）+ `retro`（反思） |
| `--review`（局部或全局） | `decision`（把 Tier 分层 / 发现留存）/ `issue`（把 Critical 条目发给协作者） |
| `--test` | `experiment`（若是为验证某假设写的测试） |
| `--bench` | `experiment`（基线 / profile / 对比 / 优化轨迹） |
| `--doc` | 通常不需要单独 report（文档本身就是产物） |
| `--ship` | `release`（对用户）+ `status`（对团队 / 上级） |

`/report` 自动识别会话上下文中的 blueprint 产物并作为素材来源。

---

输出语言跟随用户输入语言。
