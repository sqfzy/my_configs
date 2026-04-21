---
name: report
description: "Generate structured reports for stakeholders (managers, leads, executives) in markdown format. Principle-driven: conclusion-first, action-oriented, data-backed, anticipates questions. Auto-collects data from git history, .artifacts/, and code changes. TRIGGER when: user asks to write a report, summary for their boss/manager/lead, weekly/monthly report, status update, technical proposal, incident report, or achievement summary. DO NOT TRIGGER when: user wants code documentation (use /doc), project architecture overview (use /doc summary), or technical discussion records (use /discuss)."
argument-hint: "<topic> [to: <role>] [purpose: progress|decision|issue|achievement|tech-proposal|incident|experiment] [source: git|artifacts|<path>] [output: <path>] [auto]"
allowed-tools: Bash(git:*), Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*)
---

# /report

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
近期提交：!`git log --oneline -20 2>&1`
近期改动文件：!`git diff --stat HEAD~10 HEAD 2>&1`
现有产物：!`ls .artifacts/*.md 2>/dev/null | tail -10 || echo "(无)"`

主题：$ARGUMENTS

---

## 核心理念

> 报告的价值不在于篇幅，而在于**让读者能在 10 秒内找到他需要的信息**——结论、影响、或细节，各取所需。

不同报告服务于不同读者需求——进度周报里的日志流水可能本身就是信息，事故报告里的时间线就是证据。关键不是消灭过程记录，而是让**结构**替读者做分层：最重要的放最上面，详细内容放后面，读者用多少时间就能获取多少信息。

---

## 参数解析

- **主题**（必填）：报告关于什么
- `[to: <角色>]`：收件人角色（如"技术总监"、"产品经理"、"CTO"），影响用语、详细度和关注维度。未指定则默认"直属上司"
- `[purpose]`：报告目的，未指定则从主题自动推断
  - `progress`：汇报进展——进展如何？有风险吗？
  - `decision`：请求决策——该选什么方案？
  - `issue`：汇报问题——出了什么事？怎么解决？
  - `achievement`：分享成果——做了什么？效果如何？
  - `tech-proposal`：技术提案——该做什么新东西，方案是什么？
  - `incident`：事故报告——发生了什么，影响范围、根因、改进措施
  - `experiment`：实验报告——验证了什么假设，结果支持 / 否决？

### 目的自动推断

若用户未显式指定 purpose 参数，从 prompt 中推断：

| 关键词/意图 | 推断目的 |
|-------------|----------|
| "进展"、"周报"、"月报"、"状态" | progress |
| "方案"、"选 A 还是 B"、"审批" | decision |
| "问题"、"出了什么事"、"阻塞" | issue |
| "成果"、"做了什么"、"优化效果" | achievement |
| "技术提案"、"proposal"、"设计文档"、"RFC" | tech-proposal |
| "事故"、"故障"、"P0"、"postmortem"、"incident" | incident |
| "实验"、"验证"、"A/B"、"假设"、"spike"、"POC" | experiment |

- 多个关键词匹配多个目的时，按合理顺序组合执行
- 无法推断时使用默认目的（progress）
- 推断结果输出一行声明：`▶ 推断目的：<purpose>（从"<关键词>"推断）`

- `[source]`：数据来源，可逗号分隔多个。未指定则自动扫描
  - `git`：从 git log 提取工作内容和时间线
  - `artifacts`：从 `.artifacts/` 中的报告提取分析结论
  - `<path>`：从指定文件或目录提取
- `[output: <path>]`：输出路径，默认 `report-<主题摘要>.md`（当前目录）
- `[auto]`：跳过确认，直接输出

---

## 写作原则

以下 6 条原则是**强制的**。每条违反都会降低报告质量。

### 原则 1：结论先行

报告的第一段必须直接回答"所以呢"。读者不需要看完整篇才知道结论。

- 开头给结论，不给背景铺垫
- 若有多个结论，按重要性排序
- 详细论证放在后面，读者感兴趣时再深入

**反面示例**：先花 3 段描述背景和过程，最后一段才给出结论
**正面示例**：第一句就是"建议选方案 A，预计节省 40% 的延迟"，后面再解释为什么

### 原则 2：自包含

报告必须能让**不在现场的读者**独立看懂，不依赖对话上下文、不依赖读者的先验知识、不依赖外部链接里的信息。

强制要求：

- **首次出现的专有名词必须解释**：缩写、项目代号、内部系统名、非通用术语，第一次出现时用一句话说明（`XYZ 网关（负责 AB 流量的反向代理层）`）
- **关键数据必须自带语义**：不写 "QPS 从 5k 到 8k"，写 "QPS 从 5k 到 8k（+60%，超出目标值 7k）"——数字要带单位、对比基准、达标判断
- **引用必须内联要点**：引用 PR / issue / 之前的报告时，同时写一句话摘要，不能只丢链接
- **时间锚点绝对化**：不写"上周"、"最近"，写"2026-W15（4/7–4/13）"、"过去 30 天"
- **环境 / 版本必须标注**：涉及系统行为的论断要写清是哪个版本、什么配置、什么环境
- **报告结束时做一次"陌生读者测试"**：假设一个从未参与过的同事今天读这份报告，他需要的信息是否都在文档里

如果信息必须分层（10 秒 / 1 分钟 / 完整），分层展示，但**不可省略**。

### 原则 3：量化一切

**禁止**使用以下空话：
- "效果显著" → 用 "延迟从 142ns 降至 89ns（-37%）"
- "大幅提升" → 用 "吞吐量从 5,000/s 提升到 12,000/s（+140%）"
- "进展顺利" → 用 "12 个任务中已完成 9 个（75%），剩余 3 个预计下周五前完成"
- "存在一些问题" → 用 "发现 3 个 Critical 级别问题，已修复 2 个，剩余 1 个阻塞部署"

所有描述性结论必须附：**绝对值 + 变化量/百分比 + 对比基准**。

### 原则 4：Q&A

写完每个关键论断后，想象读者会问什么——然后在报告中先回答。

至少回答 **Top 3** 可能的 Q&A：
- 对进度报告："为什么延期了？" "风险怎么缓解？"
- 对方案报告："为什么不选 B？" "成本多少？" "时间线？"
- 对问题报告："影响范围多大？" "为什么没提前发现？" "怎么防止再次发生？"

以 "Q&A" 章节附在报告末尾，或在正文中自然融入。

### 原则 5：三层可读

报告必须支持三种阅读深度：

| 阅读时间 | 读什么 | 获得什么 |
|----------|--------|----------|
| **10 秒** | 标题 + 执行摘要 | 核心结论 |
| **1 分钟** | + 每节小标题 + 关键数据 | 论据是否充分、逻辑是否通 |
| **完整** | + 详细分析 + 附录 | 全部细节 |

实现方式：
- 执行摘要放在最前面（1-3 句结论 + 行动项）
- 每节有小标题，小标题本身传达信息（不用"分析"，用"方案 A 比 B 快 3 倍但成本高 20%"）
- 详细数据和过程放附录或折叠

### 原则 6：叙事节奏（SCQA 骨架）

报告的内部叙事遵循自然逻辑：
1. **背景**——读者已知的共识事实（简短，1-2 句）
2. **冲突/变化**——发生了什么新情况、出了什么问题、有什么机会
3. **核心问题**——由此引出什么问题需要回答
4. **答案**——你的结论/建议/方案

不需要在报告中标注"背景""冲突"等标签——自然写出即可。框架是指导节奏的，不是显式展示的。

---

## 目的分类与结构重心

根据推断或指定的 purpose，从对应模板读取结构骨架：

| purpose | 模板文件 |
|---------|---------|
| `progress` | `~/.claude/skills/report/templates/progress.md` |
| `decision` | `~/.claude/skills/report/templates/decision.md` |
| `issue` | `~/.claude/skills/report/templates/issue.md` |
| `achievement` | `~/.claude/skills/report/templates/achievement.md` |
| `tech-proposal` | `~/.claude/skills/report/templates/tech-proposal.md` |
| `incident` | `~/.claude/skills/report/templates/incident.md` |
| `experiment` | `~/.claude/skills/report/templates/experiment.md` |

模板是结构参考，不是填空题。严格遵守前面的写作原则；若某节对本次报告无意义，删掉即可。

---

## 流程

### Phase 0: 理解任务 + 素材收集

1. 分析主题，推断报告目的（若未指定）
2. 识别受众角色和关注维度
3. 自动扫描可用数据源：
   - `git log`：提取工作内容、时间线、变更统计
   - `.artifacts/`：提取已有的 review/bench/debug/improve 等报告中的结论和数据
   - 代码变更：`git diff --stat` 提取变更范围
   - benchmark 数据：`.artifacts/INDEX.md` 中的性能指标
4. 输出素材清单，确认是否有遗漏

**`auto` 模式**：不确认，直接使用收集到的素材。

### Phase 1: 撰写

按写作原则和目的分类撰写报告：

1. 根据 purpose，用 Read 工具读取对应模板文件（绝对路径见上表）作为结构骨架。**必须**使用绝对路径 `~/.claude/skills/report/templates/...`，避免与项目 CWD 内同名文件混淆
2. 先写执行摘要（结论先行）
3. 按模板骨架组织各节
4. 所有论断附数据支撑（量化一切）
5. 回答 Top 3 可能的 Q&A

**受众适配**：
- 技术上司：可以使用技术术语，但仍然结论先行
- 非技术上司：用业务语言替代技术术语，强调影响和价值而非实现细节
- 高管：极度精简，只保留结论和数据，详细内容放附录

### Phase 2: 质量自检 + 输出

撰写完成后，逐项检查：

```
## 质量自检

- [ ] 第一段是否直接给出结论（不是背景铺垫）
- [ ] **是否通过陌生读者测试**（不依赖对话上下文、缩写和专有名词首次出现有解释、引用有内联摘要、时间锚点绝对化、版本/环境已标注）
- [ ] 所有关键论断是否有数据支撑（无空话），数据是否自带语义（单位 + 对比基准 + 达标判断）
- [ ] 是否在正文或末尾以 Q&A 形式回答了可能的质疑
- [ ] 小标题是否传达信息（不是空泛的"分析""总结"）
- [ ] 篇幅是否匹配受众和目的（不冗长也不过简）
- [ ] 10 秒阅读（只看标题+摘要）是否能获取核心信息
```

任一项不通过 → 修改后重新检查。

全部通过 → 写入输出文件。

---

输出语言跟随用户输入语言。
