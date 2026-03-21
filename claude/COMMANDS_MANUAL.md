# Claude Code Command Suite — 使用手册

> 14 个命令覆盖从零开始到交付的完整开发生命周期。
> 所有命令放置于 `~/.claude/commands/`，全局生效。

---

## 目录

1. [命令全览](#命令全览)
2. [典型工作流](#典型工作流)
3. [命令详解](#命令详解)
4. [跨命令约定](#跨命令约定)
5. [输出目录结构](#输出目录结构)

---

## 命令全览

| 命令 | 一句话描述 | 输出位置 |
|------|------------|----------|
| `/feature` | 从零开发新功能（需求→设计→TDD→实现→提交） | 源码 |
| `/refactor` | 结构性重构，行为不变 | 源码 + `.discuss/` |
| `/migrate` | 依赖升级、语言版本、构建系统迁移 | 源码 + `.discuss/` |
| `/debug` | 根因追踪并修复错误/panic/测试失败 | `.discuss/` |
| `/self-evolution` | 多角色对抗迭代改进，直到无改进点 | `.discuss/` |
| `/test` | 分析覆盖盲区，补充测试 | 源码 + `.discuss/` |
| `/bench` | 性能分析、基线、优化、前后对比 | `.discuss/` |
| `/review` | 代码审查，输出按严重程度分级的反馈 | `.discuss/` |
| `/doc` | 生成/更新 API 注释、README、CHANGELOG 等 | 源码/文档 + `.discuss/` |
| `/discuss` | 多角色对抗讨论，收敛方案 | `.discuss/` |
| `/git` | 智能提交：生成 Conventional Commits message | 提交历史 |
| `/retro` | 事后复盘：提炼坑、心得、决策记录 | `.retro/` |
| `/code-summary` | 生成项目架构文档 | `code_summary.md` |
| `/run-script` | 生成一键启动脚本 | `run.sh` / `run.nu` |

---

## 典型工作流

### 新功能开发

```
/feature 实现基于 ring buffer 的无锁日志队列
    │
    ├── Phase 1: 需求澄清（有暂停点，等用户确认）
    ├── Phase 2: 设计方案 + 多角色评审（有暂停点）
    ├── Phase 3: TDD — 先写测试骨架
    ├── Phase 4: 增量实现
    ├── Phase 5: 全量验证（含 benchmark 回归）
    └── Phase 6: 提交
         │
         ▼
/test src/queue.rs mode: edge   ← 补充边界测试
         │
         ▼
/self-evolution [target: src/queue.rs]  ← 深度打磨
         │
         ▼
/git all push                   ← 提交推送
         │
         ▼
/retro                          ← 复盘记录
```

---

### Bug 修复

```
/debug <粘贴错误输出>
    │
    ├── 错误分类 → 根因假设 → 验证 → 修复 → 验证
    └── 保存调试报告
         │
         ▼
/test <出问题的模块> mode: edge  ← 补充回归测试
         │
         ▼
/git msg: fix <简述>
```

---

### 代码打磨（已有代码）

```
/review staged                  ← 提交前审查
    │
    ├── Critical/Major 问题 → /debug 或手动修复
    └── 结构性建议 → /refactor
         │
         ▼
/self-evolution                 ← 综合改进
         │
         ▼
/bench <模块> mode: profile     ← 确认无性能退化
```

---

### 依赖/语言升级

```
/discuss tokio 1.x 升级到 2.0 的策略  ← 先讨论方案
    │
    ▼
/migrate upgrade tokio to 2.0
    │
    ├── 影响分析 → 迁移计划（有暂停点）
    ├── 分步执行（每步提交）
    ├── 全量验证
    └── 迁移报告
         │
         ▼
/retro since: <迁移开始的 commit>
```

---

### 项目交付

```
/doc all                        ← 补全文档
    │
    ▼
/code-summary                   ← 生成架构文档
    │
    ▼
/run-script lang: nu            ← 生成一键启动脚本
    │
    ▼
/retro since: v1.0.0            ← 版本复盘
```

---

## 命令详解

---

### /feature — 功能开发

**场景**：从零开始实现一个新功能、模块或非平凡的改动。

```bash
/feature <需求描述> [no-commit] [no-tests] [target: <path>]
```

**参数**：
- `no-commit`：完成后不自动提交（适合需要人工检查的情况）
- `no-tests`：跳过测试（仅用于快速 spike，不推荐）
- `target: <path>`：新功能放置的目标目录

**流程中的暂停点**：
- Phase 1 结束后：确认需求理解和功能边界
- Phase 2 结束后：确认设计方案（含 3 角色 2 轮评审）

**示例**：
```bash
/feature 实现 CSV 批量导入，支持错误行跳过和进度回调 [target: src/import]
/feature 试验用 SIMD 加速字符串匹配 [no-tests] [no-commit]
```

---

### /refactor — 结构重构

**场景**：改变代码结构，不改变外部行为。

```bash
/refactor <重构意图> [target: <file>] [no-commit] [dry-run]
```

**铁律**：测试在重构前通过，重构后必须仍然通过，且测试本身不被修改。若测试需要修改，说明行为变化了——命令会暂停询问。

**支持的重构类型**：提取、内联、重命名、移动、拆分、合并、抽象变更、接口重塑

**示例**：
```bash
/refactor 将 parser.rs 中的 token 相关逻辑提取为独立模块
/refactor dry-run 重命名 handle_request 为 process_request 并更新所有调用方
```

---

### /migrate — 迁移升级

**场景**：依赖 major 版本升级、语言 edition 升级、构建系统迁移。

```bash
/migrate <迁移目标> [strategy: incremental|big-bang] [dry-run]
```

**默认策略**：`incremental`（逐模块、每步提交、新旧可共存）

**迁移前提**：运行基线测试，若基线失败则终止，要求先修复。

**示例**：
```bash
/migrate upgrade tokio to 2.0
/migrate rust edition 2024
/migrate cmake to xmake strategy: incremental
/migrate dry-run upgrade spdlog to 2.0   ← 只看计划不执行
```

---

### /debug — 调试修复

**场景**：遇到编译错误、运行时 panic、测试失败、逻辑错误时。

```bash
/debug [错误文本 | file: <path> | run] [target: <file>]
```

**三种输入模式**：
- 直接粘贴错误文本（最常用）
- `file: <path>`：从日志文件读取
- `run` 或无参数：自动运行构建/测试并捕获输出

**流程**：错误分类 → 根因假设（1-3个）→ 先验证，不改代码 → 修复根因 → 全量验证

**示例**：
```bash
/debug thread 'main' panicked at 'index out of bounds: the len is 3 but the index is 5'
/debug file: /tmp/build.log [target: src/parser.rs]
/debug run
```

---

### /self-evolution — 自我进化

**场景**：代码已基本可用，需要多轮迭代打磨到高质量状态。

```bash
/self-evolution [max-iterations: N] [target: <file or module>]
```

**默认迭代上限**：10 轮

**每轮流程**：代码审查 → 多角色讨论（5角色，2-6轮）→ 实施改动 → 编译+测试验证 → 评估是否继续

**终止条件**（按优先级）：
1. 达到最大迭代次数
2. 编译/测试无法通过
3. 所有角色无新的 critical/major 问题
4. 用户输入"停止"

每轮结束后询问用户是否继续。

**示例**：
```bash
/self-evolution
/self-evolution [max-iterations: 5] [target: src/parser.rs]
```

---

### /test — 测试补充

**场景**：为已有代码补充测试（新功能开发中的 TDD 用 `/feature`）。

```bash
/test <target> [mode: gaps|edge|fuzz|prop] [no-run]
```

**模式**：
- `gaps`（默认）：分析覆盖盲区，补充缺失测试
- `edge`：专注边界条件和错误路径
- `fuzz`：生成模糊测试（Rust: cargo-fuzz，Python: hypothesis）
- `prop`：生成属性测试（往返性、幂等性、单调性等）
- 可逗号组合：`edge,prop`

**发现缺陷时的处理**：测试失败若是被测代码的 bug，会标记 🐛 并建议 `/debug`，不会修改测试使其通过。

**示例**：
```bash
/test src/parser.rs
/test src/parser.rs mode: edge,fuzz
/test src/validator.rs mode: prop no-run
```

---

### /bench — 性能分析

**场景**：建立性能基线、定位瓶颈、验证优化效果、对比两个版本。

```bash
/bench <target or intent> [mode: profile|compare|optimize|baseline] [iterations: N]
```

**模式**：
- `baseline`：运行并保存基线数据
- `profile`（默认）：运行 + 剖析，识别瓶颈，不改代码
- `compare`：对比当前与基线/指定 commit/分支
- `optimize`：完整流程——剖析→定位→实施→验证

**优化纪律**：一次只改一个优化点；每步跑 benchmark 确认；正确性测试失败立即回滚。

**示例**：
```bash
/bench src/parser.rs                           ← 默认 profile
/bench 解析器太慢 mode: optimize
/bench mode: compare HEAD~5                    ← 对比5个commit前
/bench src/tokenizer.rs mode: baseline         ← 只建立基线
```

---

### /review — 代码审查

**场景**：提交前自查、PR 审查、专项安全/性能审查。

```bash
/review <diff source> [severity: critical|all] [focus: security|perf|correctness|style|all]
```

**Diff 来源**：
- `staged`：暂存区
- `last N`：最近 N 次提交
- `branch: <name>`：与 main 的对比
- `file: <path>`：全量审查指定文件
- 无参数：自动选择（暂存区优先）

**输出格式**：每条意见含文件位置、严重程度（Critical/Major/Minor/Nit）、具体描述和修改建议。

**示例**：
```bash
/review staged
/review last 3
/review branch: feature/async-refactor focus: correctness,security
/review severity: critical         ← 只看必须修复的问题
```

---

### /doc — 文档生成

**场景**：补充或更新项目文档。

```bash
/doc [target] [type: api|readme|changelog|onboard|inline|all] [update]
```

**文档类型**：
- `api`：公共接口的文档注释（`///`、`/** */`、docstring）
- `readme`：README.md
- `changelog`：从 git 历史生成 CHANGELOG 条目
- `onboard`：新人上手指南（`docs/ONBOARDING.md`）
- `inline`：为非显然逻辑补充行内注释（解释 why）
- `all`：全部

`update` 参数：保留人工编写的内容，只补充/修正过时部分。

**核心原则**：所有描述必须基于实际代码，不编造。

**示例**：
```bash
/doc type: api                     ← 补全所有公共接口注释
/doc type: readme,changelog update ← 更新 README 和 CHANGELOG
/doc src/parser.rs type: inline    ← 为复杂逻辑补注释
/doc type: onboard                 ← 生成上手指南
```

---

### /discuss — 多角色讨论

**场景**：面对复杂决策、方案评估、架构选型时，需要多视角检验。

```bash
/discuss <议题> [rounds: N] [roles: N]
```

**角色库**（12个预定义 + 支持自定义）：风险卫士、极简主义者、性能狂热者、实用主义者、第一性原理者、维护性倡导者、用户代言人、激进创新者、成本审计者、安全专家、怀疑论者、系统思维者

**轮数**：
- 用户指定（无上限，尽力执行）
- 未指定：自动判断（低: 2-3轮 / 中: 4-6轮 / 高: 7-15轮 / 极高: 16-100轮）

**自定义角色**：
```
【自定义】数值稳定性专家
核心偏好：浮点精度和模拟发散风险
立场预期：与性能狂热者在精度/速度上的冲突
```

**示例**：
```bash
/discuss 该用 Tokio 还是自己实现 async runtime
/discuss 新的错误处理策略是否值得引入 [rounds: 10] [roles: 7]
/discuss 数据库连接池的配置策略 [轮数: 5]
```

---

### /git — 智能提交

**场景**：日常提交，自动生成符合 Conventional Commits 规范的 message。

```bash
/git [msg: <hint>] [scope: <scope>] [pr] [push] [all]
```

**参数**：
- `msg: <hint>`：提交意图提示，Claude 据此生成完整 message
- `all`：自动 `git add -A`
- `push`：提交后自动推送
- `pr`：额外生成 PR 描述（Markdown 格式）
- `scope: <scope>`：手动指定 scope

**输出**：生成 2-3 个候选 message，供用户选择或直接编辑。

**示例**：
```bash
/git                                    ← 分析暂存区，生成候选
/git msg: 修复大文件解析 OOM
/git all push                           ← 暂存 + 提交 + 推送
/git all push pr scope: parser          ← 完整流程 + PR 描述
```

---

### /retro — 事后复盘

**场景**：完成一段工作后，提炼教训和心得以便日后回看。

```bash
/retro [scope: <path|描述>] [since: <git-ref>] [depth: quick|full]
```

**输出内容**：
- 工作时间线（基于 git 历史重建，不靠记忆）
- 坑与教训（含背景、现象、错误判断、根因、教训）
- 心得与洞察
- 关键决策记录（含"当时的信息状态"）
- 遗留问题与后续建议
- 索引标签（方便日后搜索）

`depth: quick`：只输出 TL;DR + Top 5 教训，适合快速记录。

**示例**：
```bash
/retro                                  ← 全量复盘近期工作
/retro since: v0.3.0                    ← 从指定版本开始
/retro scope: src/parser depth: quick   ← 快速记录
```

---

### /code-summary — 架构文档

**场景**：生成供新成员快速理解项目的架构文档。

```bash
/code-summary [target-path]
```

**输出内容**：概览、架构说明（含 ASCII 组件图）、模块映射表、数据流图、关键组件详解、依赖关系图、测试覆盖说明。

**示例**：
```bash
/code-summary                           ← 分析当前目录
/code-summary ./my-project
```

---

### /run-script — 一键启动脚本

**场景**：项目交付时，为用户生成无需手动操作的启动脚本。

```bash
/run-script [target: <path>] [lang: bash|nu|powershell] [name: <script-name>]
```

**生成内容**：
- 环境检测（工具链版本、系统依赖，失败时给出具体修复命令）
- `.env` 加载
- 构建（debug/release 模式）
- 预运行检查（端口占用、权限等）
- 执行（带彩色进度输出）
- Ctrl+C 优雅退出

**设计原则**：绝不静默；错误必须可操作（说明为什么 + 如何修复）；fail-fast（所有检查完成后才开始构建）。

**示例**：
```bash
/run-script                             ← 自动识别项目类型和语言
/run-script lang: nu                    ← 生成 Nushell 脚本
/run-script name: start lang: nu
```

---

## 跨命令约定

### 通用参数格式

| 约定 | 说明 |
|------|------|
| `[target: <path>]` | 指定目标文件或模块 |
| `[no-commit]` | 完成后不自动提交 |
| `[dry-run]` | 只输出计划，不执行 |

### 构建系统自动检测

所有命令自动检测项目类型：

| 语言 | 检测文件 | 构建命令 |
|------|----------|----------|
| Rust | `Cargo.toml` | `cargo build/test/bench/clippy` |
| C++ | `xmake.lua` | `xmake build/test` |
| C++ | `CMakeLists.txt` | `cmake --build && ctest` |
| Python | `pyproject.toml` | `uv run pytest / ruff` |
| Node | `package.json` | `npm run build && npm test` |
| Go | `go.mod` | `go build/test/vet` |

### 保存暂停点

以下命令有明确的暂停点，等待用户确认后再继续：

| 命令 | 暂停位置 |
|------|----------|
| `/feature` | 需求确认、设计确认 |
| `/refactor` | 方案确认 |
| `/migrate` | 迁移计划确认 |

---

## 输出目录结构

```
<project>/
├── .discuss/                    ← 大多数命令的日志输出
│   ├── YYYYMMDD-HHMMSS.md       ← /discuss 讨论记录
│   ├── debug-YYYYMMDD-HHMMSS.md ← /debug 调试报告
│   ├── evolution-YYYYMMDD-HHMMSS.md ← /self-evolution 进化日志
│   ├── test-YYYYMMDD-HHMMSS.md  ← /test 测试报告
│   ├── bench-YYYYMMDD-HHMMSS.md ← /bench 性能报告
│   ├── review-YYYYMMDD-HHMMSS.md ← /review 审查报告
│   ├── doc-YYYYMMDD-HHMMSS.md   ← /doc 文档报告
│   ├── migrate-YYYYMMDD-HHMMSS.md ← /migrate 迁移报告
│   └── refactor-YYYYMMDD-HHMMSS.md ← /refactor 重构报告
│
├── .retro/                      ← /retro 复盘报告（独立目录）
│   ├── YYYYMMDD-HHMMSS-<branch>.md
│   └── YYYYMMDD-HHMMSS-<branch>-quick.md
│
├── code_summary.md              ← /code-summary 输出
├── run.sh / run.nu              ← /run-script 输出
└── docs/
    └── ONBOARDING.md            ← /doc type: onboard 输出
```

`.discuss/` 和 `.retro/` 建议加入 `.gitignore` 或提交到 git，按团队偏好决定。

---

*输出语言始终跟随用户输入语言。*
