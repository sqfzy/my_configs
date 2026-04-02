---
name: plan
description: "Interactive plan generation — co-creates a comprehensive plan.md through structured dialogue (AI asks questions with recommendations, user decides). Covers everything from tech stack to naming conventions. Supports hierarchical plans (project → module). Only plans, never implements. TRIGGER when: user wants to plan a project/feature before coding, says \"let's plan this first\", \"create a plan\", \"I want a blueprint before we start\", or wants a comprehensive design-before-code document. DO NOT TRIGGER when: user wants to immediately start coding (use /design), or wants a pure discussion without a plan document (use /discuss)."
argument-hint: "<project or feature description> [target: <path>] [parent: <plan.md path>] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(date:*), Bash(git:*), Bash(ls:*)
---

# /plan

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
现有计划：!`find . -name "*.plan.md" 2>/dev/null | grep -v node_modules | grep -v target | grep -v .git | grep -v .artifacts | head -10 || echo "(无)"`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -40`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`

目标：$ARGUMENTS

---

## 核心理念

> plan.md 是施工图，不是草稿。实施时严格遵循，不再做设计决策。

plan.md 的完成过程是**对话驱动**的——AI 提问并提供建议，用户决策，AI 记录。这不是 AI 单方面分析后产出的文档，而是双方共创的产物。

**与 /design 的区别**：
- `/plan`：只做计划，不实施。产出 plan.md 后停止。plan.md 是长期资产，可跨多个会话使用
- `/design`：设计 + 实施一体化。若项目中已有 plan.md，/design 读取它作为输入直接进入实现

**plan.md 的完成标准**：
- 实施时不需要额外的设计决策——所有"怎么做"的问题都已回答
- 用户和 AI 都认为没有遗漏和争议
- 每个关键决策有理由，可追溯

---

## 参数解析

- **描述**（必填）：要计划的项目或功能
- `[target: <path>]`：plan 文件的输出目录，默认为项目根目录
- `[related: <path1,path2,...>]`：关联计划路径——生成计划时读取这些 plan 作为约束和上下文。未指定则**自动搜索**项目中所有 `*.plan.md`
- `[auto]`：无人值守模式——AI 自行选推荐项，直接生成完整 plan，用户事后审阅

### 文件命名

plan 文件统一使用 `<项目名>-<YYYYMMDD>.plan.md` 格式，如 `auth-module-20260402.plan.md`。不再使用裸 `plan.md`。

---

## 流程

### Phase 0: 上下文理解

1. 若已有代码，阅读项目结构和关键文件，理解现状
2. **搜索关联计划**：自动搜索项目中所有 `*.plan.md`，加上 `[related]` 显式指定的路径。读取所有**活跃的**（状态非"已完成"）关联计划，提取已确定的决策作为约束和上下文
3. **归档已完成的 plan**：若搜索到状态为"已完成"的 plan，自动移入 `.artifacts/` 并追加 INDEX.md 记录
3. 根据项目规模和类型，确定本次计划需要覆盖的**决策维度**（已有关联计划中已确定的维度可跳过或直接继承）

### Phase 1: 逐维度对话

自顶向下逐层推进。AI 根据项目规模动态选择需要覆盖的维度——小项目跳过不相关的维度。

**推荐哲学**：追求设计最优，而非改动最小。在多个技术可行方案中，推荐长期设计质量最高的方案，即使短期迁移成本更大。迁移成本是执行阶段的问题，计划阶段只关注"应该是什么样"。

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

用户回答后 → AI 将决策写入 plan.md → 确认本维度是否完整 → 进入下一维度
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

所有维度完成后，AI 对 plan.md 做全局一致性检查：

- 决策之间是否矛盾？（如选了 async 框架但接口设计全是同步的）
- 是否有遗漏？（如定义了错误类型但没说谁负责转换）
- 命名约定是否与接口设计一致？
- 实施计划是否与架构设计匹配？

若发现不一致 → 向用户指出并讨论修正。

### Phase 3: 最终确认

输出完整 plan.md 的摘要，向用户确认：

```
## plan.md 完成度检查

✅ 定位与边界：已确定
✅ 技术选型：已确定
✅ 架构设计：已确定（3 个模块，核心抽象 2 个）
✅ 接口设计：已确定（5 个公共 API）
✅ 编码规范：已确定
✅ 实施计划：已确定（3 个阶段）
✅ 一致性检查：通过

是否还有需要补充或修改的？
```

用户确认 → 写入文件。

**`auto` 模式**：不逐维度询问，AI 自行选推荐项生成完整 plan.md，最后输出给用户审阅。

---

## plan.md 格式

```markdown
# Plan: <项目/功能名>

> <一句话描述>

创建时间：<YYYY-MM-DD>
状态：草案 / 已确认 / 实施中 / 已完成

---

## 定位与边界

**目标**：<核心价值>
**用户**：<目标用户>
**In scope**：
- ...
**Out of scope**：
- ...

---

## 技术选型

| 类别 | 选择 | 理由 |
|------|------|------|
| 语言 | <X> | <理由> |
| 框架 | <X> | <理由> |
| 构建 | <X> | <理由> |
| 测试 | <X> | <理由> |

---

## 架构设计

### 模块划分

| 模块 | 职责 | 依赖 |
|------|------|------|
| <name> | <职责> | <依赖列表> |

### 核心抽象

<关键类型/trait/interface 的定义和设计意图>

### 数据流

<从输入到输出的主要数据路径>

---

## 接口设计

### 公共 API

<函数签名 + 行为描述>

### 错误体系

<错误类型定义 + 传播规则>

---

## 编码规范

| 维度 | 规范 |
|------|------|
| 命名 | <约定> |
| 错误处理 | <统一模式> |
| 日志 | <级别使用 + 格式> |
| 注释 | <风格> |

---

## 实施计划

### 阶段 1: <标题>
- 交付物：<...>
- 验收标准：<...>
- 推荐 skill：<如 /design, /refactor breaking, /test 等>
- 预估：<...>

### 阶段 2: <标题>
...

---

## 关键决策记录

> 仅记录有争议或高影响的决策，普通决策已在上方各节中体现。

### D-1: <决策标题>
- **问题**：<需要决策什么>
- **选项**：A / B / C
- **决策**：<选了什么>
- **理由**：<为什么>
- **验收标准**：<怎么判断实施正确>
```

---

## 关联计划联动

### 自动搜索

启动时自动搜索项目中所有已有的 plan 文件：

```bash
find . -name "*.plan.md" 2>/dev/null | grep -v node_modules | grep -v target | grep -v .git | grep -v .artifacts
```

所有搜索到的**活跃的** plan（状态非"已完成"）以及 `[related]` 显式指定的，都作为当前计划的**上下文和约束**。状态为"已完成"的 plan 自动移入 `.artifacts/` 归档。

### 联动规则

- **不矛盾**：新计划的决策不能与已有关联计划矛盾（如项目级 plan 选了 async，模块级 plan 不能用阻塞 I/O）
- **不重复**：已有 plan 中已确定的决策不需要重新讨论——直接继承，在新 plan 中引用
- **可细化**：已有 plan 中的粗粒度决策可以在新 plan 中细化（如项目级定了"用 thiserror"，模块级可以定义具体的错误类型枚举）
- **冲突处理**：若新计划的需求与已有 plan 存在冲突，必须显式指出并让用户决策——是修改已有 plan 还是在新 plan 中做例外

### 典型结构

```
myproject-20260401.plan.md       ← 项目级（技术选型、架构、全局规范）
auth-module-20260402.plan.md     ← 模块级（接口细化、内部设计）
parser-20260403.plan.md          ← 模块级
.artifacts/
  myold-project-20260301.plan.md ← 已完成，已归档
```

项目级和模块级之间是联动关系，不是严格的父子关系——模块级 plan 之间也可以互相约束（如 parser 的输出类型必须匹配 storage 的输入类型）。

---

## 与其他 skill 的衔接

- **`/design`**：启动时检测是否存在 plan.md。若存在，Phase 1（需求理解）直接从 plan.md 读取，跳过需求分析
- **`/design auto`**：可以读取 plan.md 后自动实施——`/design auto`（让 AI 按 plan 执行）
- **实施整个 plan**：逐阶段调用 `/design auto`，每阶段对应 plan 中的一个实施阶段

---

输出语言跟随用户输入语言。
