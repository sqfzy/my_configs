## 目的：ship（发布闸 —— 组合目的）

**适用**：准备发布 / release / 打 tag / 推到 remote。用户说"准备发布"、"ship 了"、"打个 tag"、"发布前检查"。

**ship 是组合目的** —— 它**内部依次调用其他 blueprint 目的**的核查与生成能力，组织成一条不可跳过的发布流水线。ship 的价值在于**纪律**：每一个 Gate 都必须跑，每一个失败都必须处理，直到全部通过才能真正提交 / tag / push。

**ship 必然修改代码**（commit / tag / CHANGELOG 更新 / 可能的文档更新），不默认只读。

本文件只定义 ship 目的**独有**的约束，通用维度由 SKILL.md 规定。

---

### ship 独有的必展开章节

#### 1. 发布范围声明

**必须明确**：
- **Diff 来源**：从哪个 ref 到哪个 ref（`HEAD` / `main..feature-X` / `v1.0.0..HEAD` / …）
- **目标版本**（若打 tag）：具体版本号（遵循 SemVer）
- **发布类型**：patch / minor / major / pre-release（影响 CHANGELOG 和 tag 格式）
- **目标远程**：push 到哪个 remote / branch
- **是否 no-push**：仅本地 tag + commit 不 push

#### 2. Gate 清单（核心章节，每个 Gate 都必须在计划中显式列出并标注 skip 理由若 skip）

ship 内部依次跑以下 Gate，每个 Gate 对应一个其他 blueprint 目的的能力：

```
Gate 1: Review（代码审查）
  - 功能：对本次 diff 做局部 review，找 Critical / Major 问题
  - 通过标准：无 Critical；Major 数量在可接受阈值内，或每个 Major 已有标注
  - 失败处理：发现 Critical 必须回 /blueprint --fix 修复后才能再跑 Gate 1

Gate 2: Test（测试覆盖）
  - 功能：对本次 diff 涉及的代码做 test 目的的覆盖盲区分析 + 生成
  - 通过标准：
    - 所有已修改 / 新增的公共函数有测试
    - 全量测试通过
    - 覆盖率相比上次 ship 不下降（若有覆盖率工具）
  - 失败处理：补齐缺口直到通过

Gate 3: Bench（性能回归）
  - 功能：若项目有 bench 基线，跑完整 bench 对比基线
  - 通过标准：无 bench 退化 ≥ 15%（或已解释的可接受退化）
  - 跳过条件：项目无 bench 基线 —— 必须在计划中明确标注"项目无 bench 覆盖，接受性能为盲区"
  - 失败处理：退化归因 + 决定是修复还是接受（接受必须有明确理由）

Gate 4: Doc（文档同步）
  - 功能：doc 目的的一致性核查 + 必要的生成
  - 通过标准：
    - CHANGELOG 有本次版本条目
    - 新增 / 变更的公共 API 有 doc comment
    - 若有 README 示例，示例仍可跑
    - 文档构建无警告
  - 失败处理：补齐直到通过

Gate 5: 提交与发布
  - 功能：生成 Conventional Commits message、提交、打 tag、push
  - 通过标准：提交成功、tag 创建成功、push 成功
  - 失败处理：排查 git / remote 问题
```

**每个 Gate 对应一段 plan 内容**，说明本次 ship 如何组织 Gate：

```
Gate 1 (Review):
  Diff 范围: <...>
  预期发现类型: <...>
  失败阈值: 任何 Critical 阻断

Gate 2 (Test):
  覆盖焦点: <本次 diff 的核心改动>
  新增测试预期: <...>

...
```

**陷阱**：不允许跳过 Gate，除非在计划中显式标注"跳过理由"并让用户（非 auto 模式）明确同意。

#### 3. 版本号策略

必须明确：
- 本次是 patch / minor / major
- 根据 SemVer：
  - patch：仅 bug 修复，无 API / 行为变化
  - minor：新增功能，向后兼容
  - major：breaking change
- 根据本次 diff 内容和 Gate 1 / Gate 4 的发现决定版本号

**陷阱**：凭感觉选版本号是最常见错误。必须根据 diff 内容决定。

#### 4. CHANGELOG 更新

本次 ship 对应的 CHANGELOG 条目必须包含：
- 版本号 + 日期
- 按分类（Added / Changed / Deprecated / Removed / Fixed / Security）列改动
- 每条一句话摘要 + 必要上下文
- Breaking change 单独标红

#### 5. Commit 组织策略

- 若 Gate 2 / Gate 4 引入了新代码（测试 / 文档），这些改动**独立 commit**：
  - `test(<scope>): add coverage for X`
  - `docs(<scope>): update CHANGELOG for vX.Y.Z`
- 若 Gate 1 引入了修复，也独立 commit：
  - `fix(<scope>): <subject>`
- **本次发布的 tag 基于最后一个 commit**

#### 6. 回滚策略（强制）

ship 风险高，必须有回滚计划：
- 每个 Gate 的失败回滚点（回到该 Gate 开始前）
- push 失败时的回滚（删除本地 tag、reset 到 push 前的 HEAD）
- tag 已 push 后发现问题 → 按项目约定处理（通常不允许删 tag，而是发 patch）

---

### ship 必含 ASCII 图示

- **Gate 流水线图**：Gate 1 → Gate 2 → Gate 3 → Gate 4 → Gate 5 + 每个 Gate 的输入输出
- **diff 影响范围图**：本次 diff 触及的模块 / 公共 API / 调用方
- 若有 breaking change → **breaking 影响图**（哪些调用方 / 外部协议 / 持久化格式受影响）

---

### ship 实施计划的特殊约束（施工契约）

**ship 是施工类目的** —— 产出明确阶段骨架，每阶段对应一个 Gate。

**阶段骨架（强制，每个 Gate 一个阶段）**：

```
阶段 0: 发布前准备
  - 具体动作：
    1. 确认工作区干净（无未 commit 改动，除非是本次 ship 的工作分支）
    2. 确认基线：当前全量测试通过、bench 基线存档、文档构建通过
    3. 捕获 pre-ship 状态（commit hash / branch）作为回滚点
  - 验收：基线与回滚点清晰

阶段 1 (Gate 1: Review):
  - 具体动作：
    1. 按 review 目的的扫描维度对 diff 做审查
    2. 列出 Critical / Major / Minor
  - 交付物：Review 报告
  - 验收：无 Critical；Major 有处理方案

阶段 2 (Gate 2: Test):
  - 具体动作：
    1. 按 test 目的分析 diff 的覆盖盲区
    2. 生成缺口测试（必然生成，不是可选）
    3. 运行全量测试确认通过
    4. 若有覆盖率工具，对比上次 ship
  - 交付物：新测试 commit
  - 验收：全量测试通过；覆盖率不下降

阶段 3 (Gate 3: Bench):
  - 具体动作：
    1. 跑完整 bench 套件
    2. 对比基线
    3. 退化分析（若有）
  - 交付物：bench 对比报告（若项目有 bench）；或"无 bench 覆盖"的明确声明
  - 验收：无退化 ≥ 15% 或有明确接受理由

阶段 4 (Gate 4: Doc):
  - 具体动作：
    1. 核查公共 API 的 doc comment 完整性
    2. 生成 / 更新本次版本的 CHANGELOG 条目
    3. 运行文档构建确认无警告
  - 交付物：文档 commit
  - 验收：所有 Doc 标准通过

阶段 5 (Gate 5: 提交与发布):
  - 具体动作：
    1. 生成 Conventional Commits message
    2. 最终 commit（若还有未提交的改动）
    3. 打 tag（若指定版本号）
    4. push commit + tag（除非 --no-push）
  - 验收：tag 创建成功、remote 同步

阶段 6: 发布后确认
  - 具体动作：
    1. 确认 remote 收到 commit 和 tag
    2. 若项目有 CI，确认 CI 对新 tag 触发的构建通过
    3. 输出本次 ship 的汇报
  - 交付物：ship 完成汇报
  - 验收：remote 正常，CI 通过（或按约定异步等待）
```

**每阶段独立可提交、可回滚**。禁止"几个 Gate 合并跑一次"。

**Gate 之间的依赖**：每个 Gate 失败必须解决才能进下一个。Gate 1 发现的 Critical 修复后，通常要**重新跑 Gate 1**（确认修复本身没引入新问题）。

---

### ship 的生产级重点（施工时必须贯穿）

ship 是**整个生产级标准的最终闸门**：
- 所有代码（包括本次发布引入的测试和文档）都必须达到生产级 8 维度
- 每个 Gate 的输出都是可复核的（不是"感觉 OK"）
- 不允许为了发布赶时间跳过 Gate
- 不允许在 Gate 中发现问题后标"下次处理"——每个发现要么修要么明确接受并记录

---

### ship 的施工纪律（写入计划的"施工纪律"字段）

- 每个 Gate 对应独立阶段、独立 commit（若有改动）
- 每个 commit message 遵循 Conventional Commits
- 不允许 `git add -A` —— 逐文件 add，避免敏感文件泄露
- Gate 失败时停下修复，不自作主张跳过（default 模式）
- auto 模式：Gate 失败按"警告 + 自主决策"处理（能修就修、能回滚就回滚、不能解决标红继续并汇报）
- tag 不允许 `--force` 覆盖已有 tag
- push 不允许 `--force` 到 main / master
- 发现敏感文件已进 commit 历史 → 停下，这是必须用户决策的情况

---

### ship 的反模式（计划里出现即不合格）

- ❌ 跳过任意 Gate 没有明确理由
- ❌ 没有 CHANGELOG 更新
- ❌ 凭感觉选版本号（不对照 SemVer）
- ❌ 发现 Critical 不修复直接发布
- ❌ Bench 显著退化直接接受，无解释
- ❌ 文档构建有警告直接发布
- ❌ `git add -A` 批量添加
- ❌ `--force push` 到受保护分支
- ❌ tag 已发布后意图"删了重做"（除非项目约定允许）
- ❌ ship 过程中夹带 feat / reshape 改动（应该先 feat / reshape 再 ship）

---

### ship 的风险与回滚

**回滚粒度**（从小到大）：
- 某 Gate 的修复 commit → 回退该 commit
- 整个 ship 过程（但还未 push）→ reset 到阶段 0 的回滚点
- 已 push 但 tag 未发布 → delete 本地 tag、push --delete 远程 tag
- tag 已发布、已被依赖方用 → **不回滚**，发 patch 版本修复

**预警信号**：
- Gate 1 发现大量 Critical → 本次改动成熟度不够，停下回 `/blueprint --fix` 批量修复
- Gate 2 发现测试盲区极多 → 说明 diff 本身就不完整，停下回 `/blueprint --test` 系统补齐
- Gate 3 发现大量 bench 退化 → 停下归因，可能需要 `/blueprint --bench --optimize`
- Gate 4 发现 breaking 未在 diff 中记录 → 说明设计时没意识到，停下补 BREAKING CHANGE 声明 + 升 major
- Push 失败 (权限 / 冲突 / hook) → 排查 remote 状态，不允许绕过 hook

---

### ship 完成后的输出

```
🎉 Ship 完成

版本: vX.Y.Z
Diff 范围: <...>
Commits: <数量> 个（含 <N> 个测试 commit、<M> 个文档 commit）

Gate 结果：
  ✅ Gate 1 Review:  0 Critical, N Major, M Minor
  ✅ Gate 2 Test:   +N 个测试，覆盖率 XX% → YY%
  ✅ Gate 3 Bench:  无退化 (或已解释)
  ✅ Gate 4 Doc:    CHANGELOG 已更新，公共 API doc 完整
  ✅ Gate 5 Push:   已推送到 <remote>/<branch>, tag <vX.Y.Z> 已创建

建议下一步：
  /report release     为本次发布留存决策记录
```
