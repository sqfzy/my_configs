---
name: cleanup
description: "Radical project-wide cleanup — full code audit, aggressive architectural redesign discussion (\"design from scratch\" mindset), then breaking refactoring to bring the codebase to ideal state. Not incremental patching — holistic rethinking. TRIGGER when: user says \"big refactor\", \"clean up the whole project\", \"technical debt cleanup\", \"rethink the architecture\", \"redesign from scratch\", \"project overhaul\", or wants a periodic radical codebase cleanup. DO NOT TRIGGER when: user wants a small targeted refactor (use /refactor), incremental improvement (use /improve), or feature-driven evolution (use /evolve)."
argument-hint: "[target: <module or scope>] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /cleanup

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -80`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`
现有测试：!`find . -type f \( -name "*_test.rs" -o -name "*_test.cpp" -o -name "test_*.py" -o -name "*.test.ts" -o -name "*_test.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -30`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`

Bench 感知：!`cat ~/.claude/skills/shared/bench-aware.md`

目标：$ARGUMENTS

---

## 核心理念

> cleanup 不是修补——是**重新思考**。

渐进式修补（/improve、/evolve）适合日常维护。cleanup 适合另一个场景：项目积重难返，补丁叠补丁，需要退后一步问"如果今天从零开始，我会怎么设计？"

**思维模式差异**：

| | 渐进式修补 | cleanup（激进重设计） |
|---|---|---|
| 起点 | "现有代码哪里有问题" | "理想设计应该是什么" |
| 改动 | 逐个修复问题点 | 整体替换设计模式 |
| 保守性 | 尽量不动已有结构 | 主动打破不合理结构 |
| 适用 | 代码基本可用，有局部瑕疵 | 代码积重难返，需要重新思考 |

---

## 参数解析

- `[target: <module or scope>]`：聚焦特定模块或功能域；未指定则覆盖整个项目
- `[auto]`：无人值守模式——跳过所有确认，自动执行全流程

---

## Phase 0: 全量审计

调用 `/review audit auto`（或 `/review audit target: <module> auto`），产出完整的技术债清单。

审计覆盖 9 个维度：
- 正确性、安全性、性能、可观测性、测试覆盖、设计（现有 6 维度）
- 架构一致性、模式一致性、技术债识别（审计额外 3 维度）

**产出**：技术债清单（`.artifacts/review-audit-*.md`），按严重度排序，每项标注推荐 skill。

**检查点**：向用户展示审计结果摘要（Critical/Major/Minor 数量），确认继续。

**`auto` 模式**：不暂停。

---

## Phase 1: 激进设计讨论

这是 cleanup 的**核心差异点**——不受现有实现约束，以"从零设计"思维重新审视架构。

### 1.1 讨论引导

对审计报告中每个 Critical / Major 架构级问题，展开深度讨论。

**讨论引导原则**（必须遵守）：
- **忽略现有实现的约束**——不问"现有代码怎么修"，问"如果今天从零设计会怎样"
- **质疑所有现有抽象**——每个现有的模块划分、接口设计、数据结构选择都不是不可改变的
- **追求理想态**——先确定理想设计，再规划从当前到理想的迁移路径
- **敢于删除**——"这个模块应该存在吗？"是合法问题

### 1.2 讨论维度

按以下维度逐一重新审视：

**架构重新设计**：
- 当前模块划分是否合理？职责是否清晰？
- 依赖方向是否正确？应该反转哪些依赖？
- 哪些模块应该合并？哪些应该拆分？
- 核心抽象是否仍然合适？是否需要替换？

**模式统一**：
- 项目中有几种错误处理模式？应该统一为哪一种？
- 日志/tracing 的使用是否一致？
- 命名约定有哪些不统一？canonical 名字应该是什么？
- 并发/异步模式是否一致？

**接口简化**：
- 哪些公共接口过于复杂、应该简化？
- 哪些内部接口不应该是公共的？
- 接口的参数设计是否最优？

**技术债归零**：
- 所有 TODO/FIXME/HACK——是修复还是删除？
- 所有 deprecated 代码——是迁移还是删除？
- 所有已知的 workaround——根因是否可以现在修复？

### 1.3 多角色对抗讨论

选出 **5 个角色**进行深度对抗讨论：

!`cat ~/.claude/skills/shared/roles.md`

**推荐组合**：R8（激进创新者）+ R14（架构师）+ R6（维护性倡导者）+ R2（极简主义者）+ R1（风险卫士）

对每个架构级问题：
1. 描述当前状态和问题
2. 提出 2-3 个重新设计方案（含"从零设计"方案）
3. 多角色对抗评审
4. 收敛为目标设计 + 迁移路径

### 1.4 产出：重设计方案

```
## 重设计方案

### 架构变更清单
| 序号 | 变更 | 当前状态 | 目标状态 | 影响范围 | 迁移策略 |
|------|------|----------|----------|----------|----------|
| 1 | 模块 A/B 合并 | 两个独立模块 | 统一为模块 AB | 15 个调用方 | 渐进式 |
| 2 | 错误处理统一 | 6 种模式 | 统一为 Result<T, AppError> | 全项目 | 一次性 |
| ... | ... | ... | ... | ... | ... |

### 执行顺序
<按依赖关系排序——先改底层后改上层>
1. <第一步>
2. <第二步>
...

### 风险评估
<每项变更的风险和缓解措施>
```

**检查点**：向用户展示重设计方案，确认后进入执行。

**`auto` 模式**：不暂停，直接执行。

---

## Phase 2: 破坏性执行

按重设计方案的执行顺序，逐项调用 `/refactor breaking auto`。

**执行原则**：
- 每项架构变更独立执行和验证
- 大规模变更自动使用渐进式迁移跟踪
- 每项完成后运行全量测试确认无回归
- 行为变更必须在跟踪文件中声明

**每项完成后输出进度**：
```
┌─────────────────────────────────────────────┐
│  ✅ 变更 N / M 完成                          │
├─────────────────────────────────────────────┤
│                                             │
│  描述     ： <描述>                          │
│  影响文件 ： N 个                            │
│  测试     ： 全部通过                        │
│  Commit   ： <hash>                         │
│                                             │
│  ── 总进度 ──                                │
│  ████████████░░░░░░░░  N/M                  │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Phase 3: 统一规范

架构变更完成后，处理非架构级的规范统一：

- 调用 `/improve auto iter: 1` 统一代码风格和质量
- 命名规范统一（若有不一致）
- 清理所有已完成变更的残留物（旧注释、过时文档引用）

---

## Phase 4: 验证

重新调用 `/review audit auto`，对比 Phase 0 的审计结果：

```
## 清理前后对比

| 维度 | 清理前 | 清理后 | 变化 |
|------|--------|--------|------|
| 🔴 Critical | N | M | -K |
| 🟡 Major | N | M | -K |
| 🔵 Minor | N | M | -K |
| 架构一致性 | <评分/描述> | <评分/描述> | <变化> |
| 模式一致性 | <评分/描述> | <评分/描述> | <变化> |
```

若仍有 Critical 项，提示用户是否继续清理。

---

## Phase 5: 报告

按产物存储约定输出以下报告：

```markdown
# Cleanup Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 范围：<整个项目 / target 模块>
- 架构变更数：N 项
- 规范统一项：M 项

## 清理前审计摘要
<Phase 0 的 Critical/Major/Minor 统计>

## 重设计方案
<Phase 1.4 的架构变更清单>

## 执行记录
| 序号 | 变更 | 状态 | Commit | 影响文件 |
|------|------|------|--------|----------|
| 1 | <描述> | ✅ | <hash> | N 个 |
| ... | ... | ... | ... | ... |

## 清理后审计摘要
<Phase 4 的对比表>

## 架构变化
\```
清理前：
  <模块关系简图>

清理后：
  <模块关系简图>
\```

## 行为变更清单
> 若无行为变更，显示"无行为变更"。

| 变更 | 旧行为 | 新行为 | 原因 |
|------|--------|--------|------|
| ... | ... | ... | ... |

## 代码变化统计
- 新增文件：N
- 删除文件：M（✅ 实际删除了旧代码）
- 修改文件：K
- 净行数：+X / -Y

## 后续建议
- <是否有 Minor 项需要后续 /improve 处理>
- <建议下次 cleanup 的时间周期>
- <需要更新的文档（/doc）>
```

---

输出语言跟随用户输入语言。
