---
name: doc
description: "Generate or update project documentation — API docs, README, CHANGELOG, inline doc comments, onboarding guides, and comprehensive project summaries. Reads actual code to produce accurate documentation rather than inventing descriptions. Auto-saves doc generation report to .artifacts/ TRIGGER when: user asks to write/update/generate documentation, README, CHANGELOG, API docs, inline doc comments, or project summary/overview/architecture overview; user asks \"what does this project do\". DO NOT TRIGGER when: user asks to write code comments as part of implementation (that's normal coding), or update CHANGELOG as part of /ship; user asks about a specific file or function (just read it directly)."
argument-hint: "<target> [type: api|readme|changelog|onboard|summary|all] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /doc

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`
现有文档：!`find . -maxdepth 3 \( -name "README*" -o -name "CHANGELOG*" -o -name "*.md" -o -name "docs" -type d \) ! -path "*/.git/*" ! -path "*/target/*" ! -path "*/node_modules/*" 2>/dev/null | head -20`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`

目标：$ARGUMENTS

---

## 核心原则

> 文档必须从代码中来，不可凭空捏造。

每一条描述都必须基于实际阅读的代码。若某个函数的行为不明确，文档中如实标注"行为待确认"，绝不编造。

---

## 参数解析

- **目标**（可选）：指定文件、模块或整个项目；未指定则覆盖整个项目
- `[type]`：文档类型，可逗号分隔多个
  - `api`：源文件注释——公共 API 的文档注释（`///`、`/** */`、docstring）+ 函数体内非显然逻辑的行内注释，一次扫描全覆盖
  - `readme`：生成或更新 README.md
  - `changelog`：从 git 历史生成 CHANGELOG 条目
  - `onboard`：新人上手指南（架构概览 + 开发环境搭建 + 常见任务指南）
  - `summary`：生成全面的项目概览文档 `summary.md`（架构、模块图、数据流、关键组件、依赖关系）
  - `all`：以上全部
- `[auto]`：无人值守模式——type 未指定时自动执行建议的优先项，不暂停询问

**始终从头生成**：不做增量更新。若目标文档已存在，直接删除后重新生成。这避免了过时内容残留——从代码重新生成的文档永远是准确的。

### 模式自动推断

若用户未显式指定 type 参数，从 prompt 中推断：

| 关键词/意图 | 推断类型 |
|-------------|----------|
| "API 文档"、"文档注释"、"补注释" | api |
| "README" | readme |
| "CHANGELOG"、"更新日志" | changelog |
| "上手指南"、"新人"、"onboarding" | onboard |
| "项目概览"、"架构概览"、"summary" | summary |
| 多个关键词同时出现 | 逗号组合 |

- 多个关键词匹配多个类型时，按合理顺序组合执行
- 无法推断时使用默认模式（自动检测项目缺什么并建议）
- 推断结果输出一行声明：`▶ 推断类型：<type>（从"<关键词>"推断）`

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
| 源文件注释（API + 行内） | 覆盖率约 X% | <无注释的公共函数数量、缺注释的非显然逻辑数量> |
| 上手指南 | ✅ / ❌ | <细节> |
| summary.md | ✅ 存在 / ❌ 缺失 / ⚠️ 过时 | <是否与当前代码结构匹配> |

建议优先补充：<type 列表>
```

若用户未指定 type，在此处暂停让用户选择，或执行建议的优先项。

**`auto` 模式**：不暂停，直接执行审计建议的优先项。

---

## Type: api — 源文件注释（文档注释 + 行内注释）

### 读取阶段

**文档注释扫描**——逐一阅读所有公共接口：

**Rust**：
- 所有 `pub fn`、`pub struct`、`pub enum`、`pub trait`、`pub type`
- 检查是否已有 `///` 或 `//!`

**C++**：
- `include/` 下所有头文件的公共函数、类、模板
- 检查是否已有 `/** */` 或 `///`

**Python**：
- 所有 `def`（非 `_` 前缀）和 `class`
- 检查是否已有 docstring（`"""`）

**行内注释扫描**——同时检查函数体内缺少注释的非显然逻辑：

- 复杂条件判断（3+ 个条件的 if/match）
- 非直觉的算法步骤
- Magic number / 硬编码常量
- Unsafe 块
- 绕过直觉的性能优化
- 错误处理中的非显然决策（为什么吞掉某个错误？为什么 retry？）

**不添加行内注释的地方**：
- 自解释的代码（`let count = items.len()`）
- 已有准确注释的代码
- 简单的 getter/setter

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

**行内注释原则**——注释解释 **why**，不解释 **what**：
- ✅ "Retry up to 3 times because the upstream API occasionally returns transient 503 errors during deployment windows."
- ❌ "Loop 3 times"
- ✅ "Using relaxed ordering here because we only need eventual visibility of the counter value."
- ❌ "Fetch and add 1 to counter"

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

## Type: summary — 项目概览文档

### 输出文件

`<target>/summary.md`（项目根目录或 target 指定路径）。这是项目文档的一部分（和 README 同级），不是 `.artifacts/` 产物。

### 输出结构

````markdown
# Project: <name>

> <one-sentence description>

**Language**: ... | **Build**: ... | **License**: ... (if found)

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Module Map](#module-map)
4. [Data Flow](#data-flow)
5. [Key Components](#key-components)
6. [Entry Points & APIs](#entry-points--apis)
7. [Dependencies](#dependencies)
8. [Testing](#testing)

---

## Overview

<2–4 paragraphs: what the project does, who uses it, how it fits together at the highest level>

---

## Architecture

<Explain the architectural style: layered? pipeline? actor model? plugin-based?>

### Component Diagram

```
<ASCII diagram showing major components and their relationships, width ≤ 80 chars>
```

---

## Module Map

| Module / File | Responsibility | Key Types | Depends On |
|---|---|---|---|
| ... | ... | ... | ... |

---

## Data Flow

<Describe the main data path in prose.>

### Flow Diagram

```
<ASCII diagram showing data flow from input to output>
```

---

## Key Components

### `<ComponentName>`

**File**: `src/...`
**Purpose**: ...
**Interface**:
```
<key public function signatures>
```
**Notes**: non-obvious design decisions, caveats, gotchas

_(Repeat for 5–10 most important components)_

---

## Entry Points & APIs

| Entrypoint | Type | Description |
|---|---|---|
| ... | ... | ... |

---

## Dependencies

### Internal (module graph)

```
<ASCII dependency graph>
```

### External

| Crate / Package | Version | Purpose |
|---|---|---|
| ... | ... | ... |

---

## Testing

| Test Suite | Location | Coverage Focus |
|---|---|---|
| ... | ... | ... |

Key test scenarios:
- ...
````

### 质量准则

- **具体性**：命名实际文件、类型、函数，不写泛泛描述
- **ASCII 图准确性**：只画代码中实际存在的边，不发明关系；宽度 ≤ 80 字符
- **覆盖范围**：Key Components 覆盖 5–10 个最重要的部分，而非每个文件
- **诚实的空白**：若模块不透明（生成代码、二进制、不可读），如实说明
- **语言特性**：Rust 注明 unsafe 块和 FFI 边界；C++ 注明模板实例化复杂度
- **可扫描性**：不熟悉项目的开发者应能在 5 分钟内理解整体结构

### 注意事项

- 文件扫描时跳过 `target/`、`build/`、`.git/`、`node_modules/`、`__pycache__/`、`.cache/`、`dist/` 等生成目录
- 生成的 benchmark 使用有代表性的输入

---

## Phase 1: 生成 / 更新

根据选定的 type 执行生成。对每种 type：

1. 阅读相关代码
2. 生成/更新文档内容
3. 写入文件

**文件位置**：
- `api`：直接修改源文件（添加文档注释 + 行内注释）
- `readme`：项目根 `README.md`
- `changelog`：项目根 `CHANGELOG.md`
- `onboard`：`docs/ONBOARDING.md`
- `summary`：`<target>/summary.md`（项目根或指定路径）

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

按产物存储约定输出以下报告：

```markdown
# Documentation Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 类型：<api / readme / changelog / onboard / summary>
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
- <建议定期运行 /doc 保持文档同步>
```

---

输出语言跟随用户输入语言。
