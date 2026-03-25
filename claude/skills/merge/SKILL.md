---
name: merge
description: "Two modes: (1) sync — merge upstream into your branch, all conflicts favor upstream; (2) port — selectively transplant features from an independent library into a target codebase with adaptation. Full safety net: backup, preview, build verification, rollback."
TRIGGER when: user wants to sync with upstream, merge company code, port features from one codebase to another, or transplant code between independent repositories.
DO NOT TRIGGER when: user is merging their own feature branches (use git directly), or resolving a specific merge conflict (assist directly).
argument-hint: "<upstream-ref> [dry-run] [auto] | port <source-path> [files: <glob>] [dry-run] [auto]"
allowed-tools: Bash(git:*), Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(date:*), Bash(mkdir:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /merge

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
Remotes：!`git remote -v 2>&1`
工作区状态：!`git status --short 2>&1 | head -20`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`

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

## Sync Phase 3: 执行

```bash
git fetch <remote> 2>&1  # 确保最新
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

## Sync Phase 5: 报告

写入 `.discuss/merge-YYYYMMDD-HHMMSS.md`：
- 合并结果、被覆盖的个人改动、保留的个人改进、需手动审查的文件、验证结果、回滚命令

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

## Port Phase 5: 报告

写入 `.discuss/merge-port-YYYYMMDD-HHMMSS.md`：

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

## 后续操作
- 代码审查：建议使用 /review 审查 port 分支
- 合入主分支：git checkout main && git merge port/<name>
- 回滚：git checkout <原分支> && git branch -D port/<name>
```

输出：`✓ 移植完成，报告已保存至 .discuss/merge-port-YYYYMMDD-HHMMSS.md`

---

输出语言跟随用户输入语言。
