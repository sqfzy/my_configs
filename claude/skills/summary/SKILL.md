---
name: summary
description: Analyze a codebase and produce a comprehensive, visually rich code_summary.md.
argument-hint: [target-path]
allowed-tools: Bash(find:*), Bash(cat:*), Bash(head:*), Bash(wc:*)
---

# /summary

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`

目标路径：$ARGUMENTS

---

按以下流程执行，**全部完成后**再将结果写入文件。

---

## Step 0: 参数解析 & 路径确定

- **若 `$ARGUMENTS` 非空**：以其作为项目根目录，输出文件写入 `<target>/code_summary.md`
- **若 `$ARGUMENTS` 为空**：以当前工作目录为项目根，输出写入 `./code_summary.md`

将目标路径解析为绝对路径，后续所有步骤均相对此根目录执行。

---

## Step 1: 项目身份识别

通过以下线索识别项目类型和主要语言：

- **构建文件**：`xmake.lua`、`CMakeLists.txt`、`Cargo.toml`、`pyproject.toml`、`package.json`、`go.mod`
- **语言启发**：`src/`、`lib/`、`include/` 下的主要扩展名分布
- **入口点**：`main.*`、`lib.*`、`mod.rs`、`__init__.py`、`index.*`

读取顶层 `README.md`（若存在）提取项目描述。

---

## Step 2: 目录结构映射

执行过滤后的文件扫描（跳过 `target/`、`build/`、`.git/`、`node_modules/`、`__pycache__/`、`.cache/`、`dist/`）：

```bash
find "$TARGET" -not \( -path '*/.git*' -o -path '*/target*' -o -path '*/build*' \
  -o -path '*/node_modules*' -o -path '*/__pycache__*' \
  -o -path '*/.cache*' -o -path '*/dist*' \) \
  -type f | sort | head -200
```

按模块/组件对文件分组，识别：
- 公共 API 层（头文件、`pub` 项、导出符号）
- 内部模块及其职责
- 测试目录
- 配置/数据文件

---

## Step 3: 架构分析

对每个重要模块或文件，阅读足够内容以理解：

- **用途**：该模块解决什么问题？
- **核心类型**：关键数据结构是什么？
- **公共接口**：对外暴露什么？
- **依赖关系**：从其他模块引入了什么？

在分析过程中构建依赖图：

- Rust：关注 `mod` 声明、`use` 路径、trait impl
- C++：关注 `#include` 链、命名空间、模板边界
- Python：追踪 `import` 语句

---

## Step 4: 数据流与控制流识别

追踪主执行路径：

- 执行从哪里开始？
- 主要处理阶段有哪些？
- I/O 发生在哪里（文件、网络、IPC）？
- 关键数据变换有哪些？

---

## Step 5: 生成 `code_summary.md`

将以下结构写入目标文件：

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
┌─────────────┐
│ Entry Point │
└──────┬──────┘
       │
┌──────▼──────┐
│ Core Module │
└──┬──────┬───┘
   │      │
┌──▼───┐ ┌▼────────┐
│Store │ │ Network │
└──┬───┘ └─────────┘
   │
┌──▼──────────┐
│ Files / DB  │
└─────────────┘
```

---

## Module Map

| Module / File | Responsibility | Key Types | Depends On |
|---|---|---|---|
| `src/main.rs` | CLI entry, arg parsing | `Args`, `Config` | `core`, `config` |
| ... | ... | ... | ... |

---

## Data Flow

<Describe the main data path in prose.>

### Flow Diagram

```
  Input / CLI / Config
          │
          ▼
       Parser
          │
          ▼
      Validator
          │
       ┌──┴──────────┐
       │             │ error
       ▼             ▼
   Processor    ErrorHandler
       │
       ▼
 Output / File / Network
```

---

## Key Components

### `<ComponentName>`

**File**: `src/...`
**Purpose**: ...
**Interface**:
```rust
pub fn key_function(arg: Type) -> Result<Out, Error>
```
**Notes**: non-obvious design decisions, caveats, gotchas

_(Repeat for each significant component)_

---

## Entry Points & APIs

| Entrypoint | Type | Description |
|---|---|---|
| `fn main()` | Binary | CLI entry |
| `pub fn init()` | Library API | ... |

---

## Dependencies

### Internal (module graph)

```
main ──► core ──► storage ──► utils
              └──► net
```

### External

| Crate / Package | Version | Purpose |
|---|---|---|
| `tokio` | 1.x | Async runtime |
| ... | ... | ... |

---

## Testing

| Test Suite | Location | Coverage Focus |
|---|---|---|
| Unit tests | `src/**/*_test.rs` | Pure logic |
| Integration | `tests/` | I/O, end-to-end |

Key test scenarios:
- ...
````

---

## Quality Guidelines

- **具体性**：命名实际文件、类型、函数，不写泛泛描述
- **ASCII 图准确性**：只画代码中实际存在的边，不发明关系；宽度 ≤ 80 字符
- **覆盖范围**：Key Components 覆盖 5–10 个最重要的部分，而非每个文件
- **诚实的空白**：若模块不透明（生成代码、二进制、不可读），如实说明
- **语言特性**：Rust 注明 unsafe 块和 FFI 边界；C++ 注明模板实例化复杂度
- **可扫描性**：不熟悉项目的开发者应能在 5 分钟内理解整体结构

完成后输出：`✅ <target>/code_summary.md written — <N> modules documented, <N> ASCII diagrams generated`

---

输出语言跟随用户输入语言。
