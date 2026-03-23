---
name: doc
description: Generate or update project documentation — API docs, README, CHANGELOG, inline doc comments, and onboarding guides. Reads actual code to produce accurate documentation rather than inventing descriptions. Auto-saves doc generation report to .discuss/
TRIGGER when: user asks to write/update/generate documentation, README, CHANGELOG, API docs, or inline doc comments.
DO NOT TRIGGER when: user asks to write code comments as part of implementation (that's normal coding), or update CHANGELOG as part of /ship.
argument-hint: "<target> [type: api|readme|changelog|onboard|inline|all] [update] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /doc

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`
现有文档：!`find . -maxdepth 3 \( -name "README*" -o -name "CHANGELOG*" -o -name "*.md" -o -name "docs" -type d \) ! -path "*/.git/*" ! -path "*/target/*" ! -path "*/node_modules/*" 2>/dev/null | head -20`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`

目标：$ARGUMENTS

---

## 核心原则

> 文档必须从代码中来，不可凭空捏造。

每一条描述都必须基于实际阅读的代码。若某个函数的行为不明确，文档中如实标注"行为待确认"，绝不编造。

---

## 参数解析

- **目标**（可选）：指定文件、模块或整个项目；未指定则覆盖整个项目
- `[type]`：文档类型，可逗号分隔多个
  - `api`：公共 API 的文档注释（`///`、`/** */`、docstring）
  - `readme`：生成或更新 README.md
  - `changelog`：从 git 历史生成 CHANGELOG 条目
  - `onboard`：新人上手指南（架构概览 + 开发环境搭建 + 常见任务指南）
  - `inline`：为代码中缺失注释的非显然逻辑补充 inline 注释
  - `all`：以上全部
- `[update]`：更新已有文档而非从头生成（保留人工编写的内容，仅补充/修正过时部分）
- `[auto]`：无人值守模式——type 未指定时自动执行建议的优先项，不暂停询问

未指定 type 时，自动检测项目缺什么并建议。

---

## Phase 0: 文档现状审计

### 0.1 扫描现有文档

```bash
# README
test -f README.md && echo "README.md exists" || echo "README.md missing"

# CHANGELOG
test -f CHANGELOG.md && echo "CHANGELOG.md exists" || echo "CHANGELOG.md missing"

# API 文档注释覆盖率（采样）
# Rust: 公共项是否有 ///
grep -rn "^pub " src/ --include="*.rs" 2>/dev/null | head -20
grep -c "///" src/**/*.rs 2>/dev/null

# C++: 公共函数是否有 /** */ 或 ///
grep -rn "^\s*\(template\|auto\|void\|int\|bool\|std::\)" include/ --include="*.hpp" 2>/dev/null | head -20

# Python: 公共函数是否有 docstring
grep -A1 "def " src/**/*.py 2>/dev/null | grep -c '"""' 2>/dev/null
```

### 0.2 输出审计结果

```
## 文档审计

| 文档类型 | 状态 | 说明 |
|----------|------|------|
| README.md | ✅ 存在 / ❌ 缺失 / ⚠️ 过时 | <细节> |
| CHANGELOG.md | ✅ / ❌ / ⚠️ | <细节> |
| API 文档注释 | 覆盖率约 X% | <无注释的公共函数数量> |
| Inline 注释 | <密度评估> | <复杂逻辑缺注释的位置> |
| 上手指南 | ✅ / ❌ | <细节> |

建议优先补充：<type 列表>
```

若用户未指定 type，在此处暂停让用户选择，或执行建议的优先项。

**`auto` 模式**：不暂停，直接执行审计建议的优先项。

---

## Type: api — API 文档注释

### 读取阶段

逐一阅读所有公共接口：

**Rust**：
- 所有 `pub fn`、`pub struct`、`pub enum`、`pub trait`、`pub type`
- 检查是否已有 `///` 或 `//!`

**C++**：
- `include/` 下所有头文件的公共函数、类、模板
- 检查是否已有 `/** */` 或 `///`

**Python**：
- 所有 `def`（非 `_` 前缀）和 `class`
- 检查是否已有 docstring（`"""`）

### 生成规则

**必须包含**：
- 一行摘要：这个函数/类型做什么
- 参数说明：每个参数的含义和约束
- 返回值说明：返回什么，何时返回 `Err` / `None`
- Panic / 异常条件（若有）

**可选包含**：
- 用法示例（`# Examples`）——仅对核心 API
- 安全性注释（`# Safety`）——Rust unsafe 函数必须有
- 性能说明——若存在非显然的性能特征

**风格**：

```rust
/// Parse the input string into a `Config`.
///
/// Returns `Err(ParseError::EmptyInput)` if `input` is empty.
/// Returns `Err(ParseError::InvalidFormat)` if the format is unrecognized.
///
/// # Examples
///
/// ```
/// let config = parse_config("key=value")?;
/// assert_eq!(config.key, "key");
/// ```
pub fn parse_config(input: &str) -> Result<Config, ParseError> {
```

```cpp
/// @brief Parse the input string into a Config.
/// @param input Non-empty configuration string in "key=value" format.
/// @return Config on success, or std::unexpected with ParseError.
/// @throws None (uses std::expected for error handling).
[[nodiscard]] auto parse_config(std::string_view input) -> std::expected<Config, ParseError>;
```

```python
def parse_config(input: str) -> Config:
    """Parse the input string into a Config.

    Args:
        input: Non-empty configuration string in "key=value" format.

    Returns:
        Parsed Config object.

    Raises:
        ValueError: If input is empty or format is unrecognized.
    """
```

**update 模式**：若已有文档注释，对比代码和注释——若签名或行为已变但注释未更新，修正注释；若注释准确则不碰。

### 验证

生成或更新后，运行文档测试（若支持）：

```
根据项目构建系统，执行文档测试（若用户提供了命令则优先使用）；若项目不支持文档测试则跳过。
```

---

## Type: readme — README.md

### 读取阶段

阅读以下内容构建 README 素材：
- 构建配置（`Cargo.toml` / `xmake.lua` / `pyproject.toml`）：项目名、版本、描述、依赖
- 入口点（`main.*` / `lib.*`）：项目做什么
- 现有 README（若有）：保留人工编写的内容
- 现有构建和运行脚本：实际的命令

### 生成结构

```markdown
# <项目名>

<一段描述：项目做什么，解决什么问题，面向谁>

## 功能特性

- <功能1>
- <功能2>

## 快速开始

### 前置要求

- <工具链及版本>
- <系统依赖>

### 安装

\```bash
<实际命令，从构建配置中提取>
\```

### 运行

\```bash
<实际命令>
\```

### 测试

\```bash
<实际命令>
\```

## 项目结构

\```
<关键目录说明，精简版，5-10 行>
\```

## 使用示例

<核心 API 或 CLI 的典型用法>

## 许可证

<从 LICENSE 文件或 Cargo.toml/pyproject.toml 提取>
```

**update 模式**：保留现有 README 的自定义段落（如 Contributing、Acknowledgments），仅更新技术性段落（安装步骤、项目结构、命令）。

---

## Type: changelog — CHANGELOG

### 读取阶段

```bash
# 确定范围：上次 tag 到 HEAD
git describe --tags --abbrev=0 2>/dev/null  # 最近的 tag
git log <last_tag>..HEAD --oneline 2>&1
git log <last_tag>..HEAD --format="%H %s" 2>&1
```

若无 tag，取最近 30 个 commit。

### 生成规则

遵循 [Keep a Changelog](https://keepachangelog.com/) 格式：

```markdown
## [Unreleased]

### Added
- <feat 类型的 commit，改写为面向用户的描述>

### Changed
- <refactor / perf 类型>

### Fixed
- <fix 类型>

### Removed
- <删除的功能或废弃的 API>
```

**原则**：
- 将 commit message 改写为**面向用户**的语言（用户不关心"重构了 parser 模块"，关心"解析大文件时不再 OOM"）
- 合并相关 commit（3 个关于同一功能的 commit 合为一条）
- `BREAKING CHANGE` 在条目前加 ⚠️ 标记

**update 模式**：追加到现有 CHANGELOG.md 的 `[Unreleased]` 段落，不修改已发布版本的条目。

---

## Type: onboard — 上手指南

### 读取阶段

全面阅读项目以构建新人视角的理解：
- 架构概览（可引用 `/code-summary` 的输出，若存在）
- 开发环境搭建步骤（从 README、CI 配置、Dockerfile 推断）
- 日常开发命令（构建、测试、lint、运行）
- 代码约定（从 CLAUDE.md、.editorconfig、lint 配置推断）

### 生成结构

输出文件：`docs/ONBOARDING.md`

```markdown
# 开发上手指南

## 开发环境搭建

### 前置要求
<具体工具和版本，含安装命令>

### 克隆与首次构建
\```bash
<从零开始到跑通的完整命令序列>
\```

### 验证环境
\```bash
<运行测试确认环境正常的命令>
\```

## 项目架构速览

<3-5 段描述：整体架构、核心模块、数据流>

### 目录结构
\```
<关键目录及其职责>
\```

### 关键入口点
- <入口1>：<做什么>
- <入口2>：<做什么>

## 日常开发

### 构建
\```bash
<命令>
\```

### 测试
\```bash
<命令>
\```

### 常见任务

#### 添加新功能
<简要流程>

#### 调试一个 bug
<简要流程，可引用 /debug 命令>

## 代码约定

### 命名规范
<从现有代码推断>

### 错误处理模式
<项目使用的错误处理惯例>

### 日志规范
<日志级别和格式约定>

### 提交规范
<Conventional Commits 或项目已有的约定>

## 常见问题

### Q: 构建失败 / 依赖问题
<从 README 或 CI 配置中提取的 troubleshooting>
```

---

## Type: inline — 行内注释

### 读取阶段

扫描目标代码，识别**缺少注释的非显然逻辑**：

- 复杂条件判断（3+ 个条件的 if/match）
- 非直觉的算法步骤
- Magic number / 硬编码常量
- Unsafe 块
- 绕过直觉的性能优化
- 错误处理中的非显然决策（为什么吞掉某个错误？为什么 retry？）

**不添加注释的地方**：
- 自解释的代码（`let count = items.len()`）
- 已有准确注释的代码
- 简单的 getter/setter

### 生成规则

注释解释 **why**，不解释 **what**：

```rust
// ✅ Good: 解释意图
// Retry up to 3 times because the upstream API occasionally returns
// transient 503 errors during deployment windows.
for _ in 0..3 {

// ❌ Bad: 重复代码
// Loop 3 times
for _ in 0..3 {
```

```cpp
// ✅ Good: 解释非显然决策
// Using relaxed ordering here because we only need eventual visibility
// of the counter value — no other memory operations depend on it.
counter.fetch_add(1, std::memory_order_relaxed);
```

---

## Phase 1: 生成 / 更新

根据选定的 type 执行生成。对每种 type：

1. 阅读相关代码
2. 生成/更新文档内容
3. 写入文件

**文件位置**：
- `api`：直接修改源文件（添加文档注释）
- `readme`：项目根 `README.md`
- `changelog`：项目根 `CHANGELOG.md`
- `onboard`：`docs/ONBOARDING.md`
- `inline`：直接修改源文件（添加注释）

---

## Phase 2: 验证

### 文档测试

```
根据项目构建系统，执行文档测试或编译验证（如 Rust 的 cargo test --doc、Python 的 doctest 等）；若无文档测试则仅做编译验证。
```

### 构建验证

确认文档注释和 inline 注释的添加未引入语法错误：

```
根据项目构建系统，执行编译或导入验证，确认文档注释的添加未引入语法错误。
```

### 链接检查（README / onboard）

检查文档中的文件路径引用是否指向实际存在的文件。

---

## Phase 3: 文档报告

```bash
mkdir -p .discuss
```

写入 `.discuss/doc-YYYYMMDD-HHMMSS.md`：

```markdown
# Documentation Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 类型：<api / readme / changelog / onboard / inline>
- 模式：<新建 / 更新>

## 变更摘要

### 新增/更新的文档
| 文件 | 类型 | 操作 | 说明 |
|------|------|------|------|
| `src/parser.rs` | API 注释 | 新增 12 处 | 覆盖所有 pub 函数 |
| `README.md` | README | 更新 | 更新了安装步骤和项目结构 |
| ... | ... | ... | ... |

### API 文档覆盖率变化
- 改进前：X%（N/M 个公共项有文档）
- 改进后：Y%（N'/M 个公共项有文档）

### 验证结果
- 文档测试：✅ / ❌ / ⏭️
- 构建验证：✅ / ❌

## 后续建议
- <仍缺文档的公共接口>
- <建议定期运行 /doc update 保持文档同步>
```

写入完成后输出：
`✓ 文档报告已保存至 .discuss/doc-YYYYMMDD-HHMMSS.md`

---

输出语言跟随用户输入语言。
