---
name: merge
description: "Two modes: (1) sync — merge upstream into your branch, all conflicts favor upstream; (2) port — selectively transplant features from an independent library into a target codebase with adaptation. Full safety net: backup, preview, build verification, rollback. TRIGGER when: user wants to sync with upstream, merge company code, port features from one codebase to another, or transplant code between independent repositories. DO NOT TRIGGER when: user is merging their own feature branches (use git directly), or resolving a specific merge conflict (assist directly)."
argument-hint: "<upstream-ref> [dry-run] [auto] [review-conflicts] | port <source-path> [files: <glob>] [dry-run] [auto]"
allowed-tools: Bash(git:*), Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(date:*), Bash(mkdir:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /merge

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
Remotes：!`git remote -v 2>&1`
工作区状态：!`git status --short 2>&1 | head -20`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`

改动总结可视化原则：!`cat ~/.claude/skills/shared/change-summary.md`

生产级代码标准：!`cat ~/.claude/skills/shared/production-grade.md`

参数：$ARGUMENTS

---

## 模式分流

根据参数判断模式：

- 参数以 `port` 开头 → **Port 模式**（跨库功能移植）
- 其他 → **Sync 模式**（fork/分支同步）

---

# ═══════════════════════════════════════
# Sync 模式 — 将 upstream 合入当前分支
# ═══════════════════════════════════════

> 所有冲突以 upstream 为准。个人的非冲突改进自动保留。

## 参数

- `<upstream-ref>`（必填）：分支名、remote/分支、tag、commit hash
- `[dry-run]`：只预览，不实际合并
- `[auto]`：跳过确认
- `[review-conflicts]`：在冲突审查步骤暂停，允许用户选择性保留部分本地改动后再执行 theirs 合并。未设置时自动以 upstream 为准合并，但仍输出被覆盖改动的摘要

## Sync Phase 1: 准备

- 工作区必须干净——否则终止并提示 commit 或 stash
- 验证 upstream ref 可达——否则提示 `git remote add` / `git fetch`
- 创建备份分支：`git branch backup/merge-<timestamp>`
- 记录 HEAD hash 作为回滚点

## Sync Phase 2: 分析

在不改变任何东西的情况下预览合并影响：

```bash
git diff --stat HEAD...<upstream-ref>
git log --oneline HEAD...<upstream-ref> | head -30
```

输出分类：
- **冲突文件**：同时在两侧修改过的文件（个人改动将被 upstream 覆盖）
- **个人独有文件**：仅在个人分支存在（不受影响）
- **配置文件变更**：.gitignore, .env*, CI 配置等（建议手动审查）
- **锁文件/依赖变更**：Cargo.lock, uv.lock 等（合并后需依赖同步）

**暂停确认**（dry-run 则终止，auto 则跳过）。

## Sync Phase 3: 冲突审查

在执行最终合并之前，先探测哪些本地改动会被覆盖：

```bash
git fetch <remote> 2>&1  # 确保最新

# 3a. 尝试不带 -X theirs 的合并，探测冲突
git merge --no-commit --no-ff <upstream-ref> 2>&1
```

若合并无冲突 → 直接进入 Phase 3b 提交合并，无需审查。

若存在冲突：

1. **列出所有冲突文件**：

```bash
git diff --name-only --diff-filter=U
```

2. **逐文件展示本地将被覆盖的改动**：

对每个冲突文件，输出本地版本与 upstream 版本的差异摘要，明确标注哪些本地修改会丢失：

```bash
for f in $(git diff --name-only --diff-filter=U); do
    echo "=== $f ==="
    echo "--- 本地改动（将被覆盖）---"
    git diff HEAD -- "$f" | head -60
    echo ""
done
```

3. **`[review-conflicts]` 交互审查**（仅当设置了 `review-conflicts` 参数时）：

暂停并逐文件询问用户：
```
冲突文件：src/config.rs
  本地改动摘要：<改动描述>
  选择：
    [t] 使用 upstream 版本（theirs）
    [o] 保留本地版本（ours）
    [m] 手动编辑合并
```

对用户选择保留的文件，记录到保留列表；其余文件仍以 upstream 为准。

4. **无 `[review-conflicts]` 时的默认行为**：

输出被覆盖改动摘要后，自动继续——所有冲突以 upstream 为准。

5. **中止探测合并，执行最终合并**：

```bash
# 中止探测合并
git merge --abort 2>&1

# 执行最终合并
# 若有 review-conflicts 且用户选择保留了部分文件：
#   git merge --no-commit --no-ff -X theirs <upstream-ref>
#   git checkout HEAD -- <用户保留的文件列表>
#   git commit --no-edit
# 否则：
git merge -X theirs <upstream-ref> --no-edit 2>&1
```

失败处理：
- unrelated histories → 提示 `--allow-unrelated-histories`
- 残余冲突 → `git checkout --theirs <file>` 逐个解决
- 其他错误 → 输出回滚命令

## Sync Phase 4: 验证

- 依赖同步（若锁文件有变更）
- 构建验证
- 测试验证
- 失败时**不自动回滚**，输出选项：修复 / 回滚 / /debug
- **`auto` 模式**：失败时自动回滚到备份分支 `backup/merge-<timestamp>`，写明失败原因后终止。不自动尝试修复（避免在用户不知情下偏离意图）。

## Sync Phase 5: 报告

按产物存储约定输出以下报告：

```markdown
# Sync Report

## 概况
- 时间：<时间>
- Upstream ref：<upstream-ref>
- 当前分支：<branch>
- 合并 Commit：<merge-commit-hash>
- 备份分支：backup/merge-<timestamp>

## 冲突文件
| 文件 | 冲突类型 | 处理方式 |
|------|---------|---------|
| <file> | 双侧修改 | upstream 覆盖 / 保留本地（review-conflicts） |

## 被覆盖的本地改动
| 文件 | 本地改动摘要 | 影响行数 |
|------|-------------|---------|
| <file> | <改动描述> | +N / -M |

## 保留的个人改进
- 非冲突文件中的个人改动（自动保留）

## 验证结果
- 构建：✅ / ❌
- 测试：✅ / ❌ / ⏭️

## 改动总结
<按"改动总结可视化原则"输出 ASCII 化的：本次合并引入的文件清单（+/~/-/↻）/ 结构变化 / 接口变化 / 行为变化 / 故意保留的本地差异。
sync 模式下重点说明 upstream 覆盖了哪些本地内容、保留了哪些个人改进。Phase 4 验证通过后必须先打印给用户审阅，此处原样复刻。>

## 后续操作
- 审查被覆盖改动：若需恢复，参考备份分支 backup/merge-<timestamp>
- 回滚：git reset --hard <rollback-hash>
```

---

# ═══════════════════════════════════════
# Port 模式 — 从独立库移植功能到当前仓库
# ═══════════════════════════════════════

> 从源库选择性地移植功能到目标库（当前仓库）。源库和目标库无需有 git 历史关系。所有适配以目标库（公司代码）的风格、依赖、命名为准。

## 参数

- `port`（必填）：触发 port 模式的子命令
- `<source-path>`（必填）：源库的本地路径
- `[files: <glob or list>]`：要移植的文件或目录（如 `src/parser/**`、`src/utils.rs,src/config.rs`）；未指定则交互式列出源库结构让用户选择
- `[dry-run]`：只输出分析和移植计划，不执行
- `[auto]`：跳过确认

## Port Phase 1: 准备

- 验证源库路径存在且可读
- 验证当前仓库工作区干净
- 在目标仓库创建专用分支：`git checkout -b port/<source-name>-<timestamp>`
- 记录 HEAD hash 作为回滚点

若未指定 `files`，列出源库结构供用户选择：

```bash
find <source-path>/src -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.py" ... \) | head -50
```

暂停让用户指定要移植的文件。

## Port Phase 2: 分析

深入分析源文件和目标库，输出**适配矩阵**：

### 2.1 依赖链分析

读取要移植的文件，追踪其内部依赖——源库中被引用但不在移植列表中的文件：

```
⚠ parser.rs 依赖 utils.rs（不在移植列表中）
  [1] 一起移植 utils.rs
  [2] 用目标库中的等价模块替代
  [3] 忽略（移植后手动处理）
```

### 2.2 差异分析

对比源库和目标库的：
- **依赖/包管理**：源库有但目标库没有的依赖
- **命名约定**：模块命名、函数命名风格差异
- **错误处理模式**：源库的 error 类型 vs 目标库的 error 类型
- **目录结构**：源文件应放在目标库的什么位置

### 2.3 输出适配矩阵

```
## 移植计划

### 文件映射
| 源文件 | → 目标位置 | 适配事项 |
|--------|-----------|---------|
| src/parser.rs | src/core/parser.rs | import 路径、Error 类型适配 |
| src/utils.rs | src/common/utils.rs | 命名空间调整 |
| tests/test_parser.rs | tests/test_parser.rs | 测试路径更新 |

### 需要添加的依赖
| 依赖 | 源库版本 | 目标库当前 | 操作 |
|------|---------|-----------|------|
| serde | 1.0 | 未使用 | 添加 |
| tokio | 1.38 | 1.35 | 版本协调 |

### 构建配置变更
- Cargo.toml / xmake.lua：需添加新源文件和依赖
```

**暂停确认**（dry-run 则终止，auto 则跳过）。

## Port Phase 3: 执行

逐文件移植，每个逻辑功能单元独立提交：

```
for each 功能单元 in 移植计划:
    1. 复制源文件到目标位置
    2. 适配文件内容：
       - 修改 import/use/include 路径以匹配目标库结构
       - 适配错误类型、命名约定以匹配目标库风格
       - 替换源库特有的依赖调用为目标库等价物（若有）
    3. 更新构建配置（添加新文件、新依赖）
    4. 编译验证（确保每步可编译）
    5. 提交：git commit -m "port(<scope>): <描述>"
```

**关键纪律**：
- 每次提交必须可编译——不积累编译错误
- 适配以目标库风格为准——不把源库的风格带入目标库
- 配套的测试文件一起移植

## Port Phase 4: 验证

- 依赖安装/同步
- 全量构建验证
- 全量测试验证（包括移植的测试）
- 失败时**不自动回滚**，输出：
  ```
  ⚠ 移植后验证失败：
    <失败详情>

  选择：
    [1] 尝试修复后继续
    [2] 回滚到移植前：git checkout <原分支> && git branch -D port/<name>
    [3] 使用 /debug 定位失败原因
  ```
- **`auto` 模式**：失败时自动执行 [2] 回滚——切回原分支并删除 `port/<name>` 分支，写明失败原因后终止。Port 涉及跨库代码融合，自动修复风险过高，保守回滚更安全。

## Port Phase 5: 报告

按产物存储约定输出以下报告：

```markdown
# Port Report

## 概况
- 时间：<时间>
- 源库：<source-path>
- 目标分支：port/<name>
- 移植文件数：N

## 移植清单
| 源文件 | 目标位置 | 适配内容 | Commit |
|--------|---------|---------|--------|
| <src> | <dst> | <适配摘要> | <hash> |

## 添加的依赖
| 依赖 | 版本 |
|------|------|
| <dep> | <ver> |

## 验证结果
- 构建：✅ / ❌
- 测试：✅ / ❌ / ⏭️

## 改动总结
<按"改动总结可视化原则"输出 ASCII 化的：移植到目标库的文件清单（+/~/↻）/ 在目标库中的最终结构 / 新增公共接口 / 适配带来的行为差异 / 故意未移植的部分。
Phase 4 验证通过后必须先打印给用户审阅，此处原样复刻。>

## 后续操作
- 代码审查：建议使用 /review 审查 port 分支
- 合入主分支：git checkout main && git merge port/<name>
- 回滚：git checkout <原分支> && git branch -D port/<name>
```

---

## 关联 skill

- **`/review`**：sync 或 port 完成后，建议对合并后的代码做一轮 review，特别是 port 模式
- **`/debug`**：合并/移植后测试失败时调用 `/debug` 定位根因
- **`/improve`**：port 完成后的代码往往风格不齐，可用 `/improve` 做一轮打磨以贴近目标库
- **`/git`**：`merge` 不负责 commit message 的雕琢——若合并涉及复杂冲突取舍，后续可用 `/git` 整理 squash message

---

输出语言跟随用户输入语言。
