---
name: blueprint
description: "Interactive planning via Claude Code plan mode — co-creates a comprehensive plan through structured multi-dimension dialogue (AI asks questions with recommendations, user decides). Plans are presented via ExitPlanMode for user approval and are session-local (NOT persisted to disk). Use immediately before implementing in the same session. TRIGGER when: user wants to plan a project/feature through a structured dimension-by-dimension dialogue before coding in the current session; user says \"let's plan this first\", \"plan this out\", \"walk me through planning X\". DO NOT TRIGGER when: user wants to immediately start coding (use /design); user wants a persistent design document (plans here are ephemeral — there is no file artifact); user wants pure discussion without producing a plan (use /discuss)."
argument-hint: "<project or feature description>"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(date:*), Bash(git:*), Bash(ls:*)
---

# /blueprint

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -40`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`

目标：$ARGUMENTS

---

## 核心理念

> **Plan 是共创产物，不是 AI 独白；是会话内的合约，不是磁盘资产。**

本 skill 利用 Claude Code 的 **plan mode** 作为呈现与审批层：AI 通过结构化的**逐维度对话**引出用户决策，最后用 `ExitPlanMode` 将完整计划呈给用户审批。整个过程**不写任何文件**——计划是会话本地的、一次性的。

**为什么不写文件**：
- 跨会话的持久化契约（过去的 blueprint-aware）会让 AI 和用户都误以为"写过就是确定"，结果 plan 与真实代码长期漂移
- Plan mode 的天然语义就是"read-only 规划 → 审批 → 立即执行或丢弃"，和"长期资产"互相抵触
- 需要长期文档 → 那是 `/doc summary`（从实际代码生成）的职责，不是 plan 的职责

**使用时机**：你**马上**就要在同一会话内实施，只是想先把所有设计决策聊清楚。

**与 /design 的区别**：
- `/blueprint`：plan mode 驱动的**结构化决策对话**，产出是 plan mode 里的最终计划；不做实施
- `/design`：设计 + 实施一体化；如果 `/blueprint` 的 plan 被用户批准，下一步应该直接在同一会话内调用 `/design` 继续推进

**与直接切 plan mode 的区别**：
- 直接切 plan mode = 给 AI 自由发挥的空间
- `/blueprint` = 强制走维度清单，逐项给选项 + 推荐 + 理由，避免 AI 跳着回答或漏掉维度

---

## 参数解析

- **描述**（必填）：要规划的项目或功能
- 无 `[auto]` 参数——plan mode 的核心就是用户审批，auto 与其语义矛盾

---

## 流程

### Phase 0: 进入 plan mode + 上下文理解

1. **第一件事**：调用 `EnterPlanMode` 工具进入 plan mode。从此点开始直到 `ExitPlanMode`，只能做读取和分析，不可修改任何文件。
2. 若已有代码，阅读项目结构和关键文件，理解现状
3. 根据项目规模和类型，确定本次计划需要覆盖的**决策维度**

### Phase 1: 逐维度对话

自顶向下逐层推进。AI 根据项目规模动态选择需要覆盖的维度——小项目跳过不相关的维度。

**推荐哲学**：追求设计最优，一步到位，而非改动最小或渐进迁移。在多个技术可行方案中，推荐长期设计质量最高的方案，即使短期迁移成本更大。不要因为"当前代码是 X 风格"就推荐在 X 上修补——如果 Y 是更好的设计，就直接推荐 Y。迁移成本是执行阶段的问题，计划阶段只关注"最终应该是什么样"。

**每个维度的对话模式**：

```
AI 输出：
  ## <维度名称>

  以下问题需要确定：

  ### Q1: <问题>
  选项：
    A. <选项> — <优劣简述>
    B. <选项> — <优劣简述>
    C. <选项> — <优劣简述>
  推荐：<X>，因为 <理由>

  ### Q2: <问题>
  ...

  请逐一回答，或直接说"按推荐"采纳全部推荐项。

用户回答后 → AI 在本轮对话里记录决策（写入内部 plan 草稿，不落盘）→ 确认本维度是否完整 → 进入下一维度
```

**可选决策维度**（AI 根据项目动态选取）：

**定位与边界**（大型项目/新项目）：
- 目标用户和核心价值
- 功能边界（in scope / out of scope）
- 与现有系统的关系

**技术选型**（新项目/涉及新技术）：
- 语言、框架、核心依赖
- 构建工具、包管理
- 测试框架、CI 方案

**架构设计**：
- 模块划分和职责
- 依赖方向和层次
- 核心抽象和数据模型
- 并发/异步模型
- 对外接口形态（CLI / API / 库）

**接口设计**：
- 公共 API 签名
- 错误类型体系
- 关键数据结构定义

**编码规范**：
- 命名约定（模块、类型、函数、变量的命名风格）
- 错误处理模式（统一方式）
- 日志/tracing 规范
- 注释风格

**实施计划**（大型项目）：
- 实施顺序和阶段划分
- 每阶段的交付物和验收标准
- 依赖关系和关键路径

### Phase 2: 一致性检查

所有维度完成后，AI 对内部草稿做全局一致性检查：

- 决策之间是否矛盾？（如选了 async 框架但接口设计全是同步的）
- 是否有遗漏？（如定义了错误类型但没说谁负责转换）
- 命名约定是否与接口设计一致？
- 实施计划是否与架构设计匹配？

若发现不一致 → 在对话中向用户指出并讨论修正（仍在 plan mode 内）。

### Phase 3: 通过 ExitPlanMode 呈交最终计划

组装完整的 plan 文本，调用 `ExitPlanMode` 工具，`plan` 参数为 **Markdown 格式的完整计划**。建议遵循以下骨架：

```markdown
# Plan: <项目/功能名>

> <一句话描述>

## 定位与边界
<核心目标、in/out scope>

## 技术选型
| 类别 | 选择 | 理由 |
|------|------|------|

## 架构设计
### 模块划分
| 模块 | 职责 | 依赖 |
### 核心抽象
### 数据流

## 接口设计
### 公共 API
### 错误体系

## 编码规范
| 维度 | 规范 |

## 实施计划
### 阶段 1: <标题>
- 交付物：
- 验收标准：
- 推荐 skill：<如 /design、/refactor breaking、/test>
- 预估：

## 关键决策记录
### D-1: <决策标题>
- 问题：
- 选项：A / B / C
- 决策：
- 理由：
- 验收标准：
```

**用户审批后**：
- **同意** → Claude Code 自动退出 plan mode，计划进入会话上下文。建议立即说明"可以调用 `/design <下一步>` 进入实施"。不要主动执行任何动作——`/blueprint` 的职责到此结束。
- **拒绝或要求修改** → 留在 plan mode 内，按用户意见调整草稿，再次调用 `ExitPlanMode`。

---

## 异常流程

### 用户在中途要求直接开工

如果用户在 Phase 1/2 就说"够了，开始做吧"：
1. 询问是否接受当前草稿作为最终计划
2. 若接受 → 立即跳到 Phase 3，调用 `ExitPlanMode` 呈交现状
3. 若用户要的是不走 plan 直接动手 → 提示 `/blueprint` 不是正确的入口，建议切换到 `/design`

### 用户在 Phase 1 发现需求本身有问题

如果对话暴露出需求描述本身不清晰或不可行：
1. 停止维度推进
2. 在 plan mode 内向用户说明问题和选项
3. 用户修正需求后 → 重新从 Phase 0 开始，或直接中止 skill（用户主动退出 plan mode）

### 维度爆炸

如果项目规模巨大，维度清单超过 10 项，对话冗长：
1. 先在 Phase 0 与用户确认"本次 plan 只覆盖 <核心维度>，其余留到后续迭代"
2. 明确 out-of-scope 的维度，写入最终 plan 的"未覆盖项"章节
3. 避免一个 session 把所有事都定了——plan mode 是会话本地的，内容多了用户记不住

---

## 与其他 skill 的衔接

**`/blueprint` 的输出是会话内的 plan mode 契约，不跨会话。**

- **`/design`**：`/blueprint` 审批通过后，在**同一会话**内立即接力。由于 plan 已在 Claude 的 context 中，`/design` 无需重新澄清需求，可以直接从"设计方案（Phase 2）"开始
- **`/discuss`**：若某个维度出现方案分歧无法收敛，可以建议用户先退出 plan mode 跑一轮 `/discuss` 沉淀分歧，再回来继续 `/blueprint`
- **`/doc summary`**：**不是** `/blueprint` 的替代品。如果用户想要一份"项目永久文档"，应该先让代码实施完，然后用 `/doc summary` 从实际代码反向生成——这才是诚实的设计文档

---

输出语言跟随用户输入语言。
