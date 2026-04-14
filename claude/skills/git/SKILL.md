---
name: git
description: "Intelligent git workflow — stages changes, generates Conventional Commits messages, writes changelog entries, and optionally drafts a PR description. Auto-detects what needs to be done based on repo state. TRIGGER when: user asks to commit, stage changes, write a commit message, push, or create a PR description. DO NOT TRIGGER when: commit is part of another workflow like /fix, /design, or /ship (they handle git internally)."
argument-hint: "[msg: <hint>] [scope: <scope>] [pr] [push] [all] [auto]"
allowed-tools: Bash(git:*), Bash(date:*), Bash(mkdir:*)
---

# /git

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前 Git 状态：!`git status --short 2>&1`
当前分支：!`git branch --show-current 2>&1`
最近 5 次提交：!`git log --oneline -5 2>&1`
暂存区 diff：!`git diff --cached 2>&1 | head -200`
工作区 diff：!`git diff 2>&1 | head -200`

参数：$ARGUMENTS

---

## 核心理念

> **Commit 是写给未来的信，不是写给现在的日志。**

每个 commit 都会在三个月后被当证据读。届时人类记不住"为什么"——Conventional Commits 的 subject 说了"做了什么"，但 body 才是让未来读者理解"为什么做"的地方。`/git` 的任务是在用户还记得上下文的当下，把**动机**固化到 commit message 里，不让它随对话窗口一起丢失。

---

## Step 0: 参数解析 & 状态判断

解析可选参数：

| 参数 | 说明 |
|------|------|
| `msg: <hint>` | 提交信息的语义提示，Claude 据此生成完整 message |
| `scope: <scope>` | 手动指定 Conventional Commits 的 scope |
| `pr` | 额外生成 PR 描述（Markdown 格式，输出到终端） |
| `push` | commit 完成后自动执行 `git push` |
| `all` | 自动 `git add -A` 暂存所有变更，再提交 |
| `auto` | 无人值守模式——直接使用生成的 commit message，不暂停询问 |

**状态检查**：根据 `git status` 结果判断当前情况：

| 状态 | 行为 |
|------|------|
| 暂存区有内容 | 直接分析暂存区 diff |
| 仅工作区有变更（暂存区为空） | 若指定 `all` 或 `auto` 则 `git add -A`；否则询问用户确认后再暂存 |
| 工作区和暂存区均干净 | 输出 `✅ 工作区干净，无需提交` 后终止 |
| 存在 merge conflict 标记 | 输出 `❌ 存在未解决的冲突，请先解决后再提交` 后终止 |

---

## Step 1: Diff 分析

分析暂存区（或待提交）的变更内容，提取：

- **变更类型**：新增功能 / 修复 bug / 重构 / 测试 / 文档 / 配置 / 依赖更新
- **影响范围**：哪个模块、组件、或功能域
- **变更摘要**：用一句话描述做了什么，以及**为什么**（从代码意图推断，而非只描述改了什么文件）
- **破坏性变更检测**：是否有 API 签名变更、接口删除、行为变更，若有标记为 `BREAKING CHANGE`

若用户提供了 `msg: <hint>`，以该提示为主导，结合 diff 补充细节。

---

## Step 2: 生成 Commit Message

严格遵循 [Conventional Commits 1.0.0](https://www.conventionalcommits.org/) 规范。

### 类型映射

| 变更特征 | type |
|----------|------|
| 新增用户可见功能 | `feat` |
| 修复 bug | `fix` |
| 重构（不改变行为） | `refactor` |
| 性能优化 | `perf` |
| 测试新增或修改 | `test` |
| 文档变更 | `docs` |
| 构建配置、CI、工具链 | `chore` |
| 代码风格、格式化 | `style` |

### 格式规则

```
<type>(<scope>): <subject>

[body]

[footer]
```

- **subject**：50 字符以内，祈使句，首字母小写，不加句号
- **scope**：从变更的模块/文件路径推断，若用户指定 `scope:` 则直接使用
- **body**：说明**为什么**做这个改动，而非重复 subject；每行 72 字符以内；若 subject 已足够清晰可省略
- **footer**：
  - 破坏性变更：`BREAKING CHANGE: <描述>`
  - 关联 issue（若能从 branch 名或 diff 注释推断）：`Closes #N`

### 输出 commit message

直接生成**最合适的一个** commit message，展示给用户确认：

```
feat(parser): add incremental parsing for large inputs

Batch processing previously loaded entire input into memory before
parsing, causing OOM on files >1GB. Switch to streaming tokenizer
with configurable chunk size.
```

询问用户：`使用此 message？[y/e(自己输入)/回车默认y]`

**`auto` 模式**：直接使用，不询问。

---

## Step 3: 执行提交

用户确认后执行：

```bash
git commit -m "<confirmed message>"
```

若用户选择 `e`，打开编辑模式让用户直接输入完整 message，然后执行提交。

提交成功后输出提交 hash：`✅ 已提交 <short-hash>: <subject>`

---

## Step 4: Changelog 更新（自动判断）

若项目根目录存在 `CHANGELOG.md`，自动在对应版本段落下追加本次提交记录。

**格式遵循 [Keep a Changelog](https://keepachangelog.com/)**：

```markdown
## [Unreleased]

### Added
- Incremental parsing support for large inputs (>1GB) via streaming tokenizer

### Fixed
- ...
```

- `feat` → `Added`
- `fix` → `Fixed`
- `refactor` / `perf` → `Changed`
- `BREAKING CHANGE` → 在版本头部加 `⚠️ BREAKING` 标记

若不存在 `CHANGELOG.md`，跳过此步骤，不自动创建。

---

## Step 5: PR 描述生成（可选）

仅当用户指定 `pr` 参数时执行。

读取当前分支与 base 分支（`main` 或 `master`）的完整 diff：

```bash
git diff main...HEAD 2>&1 | head -500
git log main...HEAD --oneline 2>&1
```

生成 PR 描述（Markdown）：

```markdown
## Summary
<2–3 句话：这个 PR 做了什么，解决了什么问题>

## Changes
- <具体改动，按模块分组>

## Testing
- <如何验证这些改动：运行了哪些测试，手动验证了什么>

## Breaking Changes
<若有，详细描述；若无，写 None>

## Notes
<reviewer 需要特别注意的地方；若无可省略>
```

直接输出到终端，供用户复制到 GitHub / GitLab PR 界面。

---

## Step 6: Push（可选）

仅当用户指定 `push` 参数时执行：

```bash
git push 2>&1
```

若当前分支无远程追踪分支，自动补充 `--set-upstream origin <branch>`：

```bash
git push --set-upstream origin <branch> 2>&1
```

输出结果，若 push 失败（如需要 rebase），输出具体错误和建议操作。

---

输出语言跟随用户输入语言。
