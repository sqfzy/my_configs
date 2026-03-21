---
name: debug
description: Systematically trace the root cause of an error, panic, or test failure and fix it. Accepts pasted error text, a log file path, or runs the build/test itself to capture output. Auto-saves debug report to .discuss/
argument-hint: "[error text | file: <path> | run] [target: <file>]"
allowed-tools: Bash(mkdir:*), Bash(date:*), Bash(cat:*), Bash(find:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /debug

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`

输入：$ARGUMENTS

---

## Step 0: 输入解析 & 错误捕获

解析 `$ARGUMENTS`，确定错误来源：

| 模式 | 格式 | 行为 |
|------|------|------|
| **直接粘贴** | 错误文本本身 | 直接使用，跳过运行步骤 |
| **日志文件** | `file: <path>` | 读取指定文件内容作为错误输入 |
| **自动捕获** | `run` 或参数为空 | 自动检测项目类型并运行构建/测试，捕获输出 |

**自动捕获时**，按以下顺序检测并执行：
```
Rust：   cargo build 2>&1; cargo test 2>&1
C++：    xmake build 2>&1; xmake test 2>&1
Python： uv run pytest 2>&1
Node：   npm run build 2>&1; npm test 2>&1
Go：     go build ./... 2>&1; go test ./... 2>&1
```

若构建/测试**全部通过**，输出：
```
✅ 构建和测试均通过，未发现错误。如需调试特定行为，请直接粘贴相关输出。
```
然后终止。

记录开始时间，创建日志目录：
```bash
mkdir -p .discuss
```
日志路径：`.discuss/debug-YYYYMMDD-HHMMSS.md`

**可选参数**：
- `[target: <path>]`：将根因分析聚焦到指定文件或模块

---

## Step 1: 错误分类 & 初步定位

拿到错误输出后，首先**分类**：

| 类型 | 特征 | 后续策略 |
|------|------|----------|
| **编译错误** | 类型错误、未定义符号、语法错误 | 直接定位出错行，通常根因明确 |
| **链接错误** | undefined reference、symbol not found | 检查依赖声明和构建配置 |
| **运行时 panic** | panic! / segfault / stack overflow / OOM | 追踪调用栈，定位触发条件 |
| **测试失败** | assertion failed、expected/got | 比较预期与实际，追溯数据流 |
| **逻辑错误** | 输出不符合预期但无 crash | 最难，需追踪数据变换路径 |
| **间歇性错误** | flaky test、race condition、超时 | 识别并发/时序依赖，重点标记 |

**初步定位**：
- 提取错误的**最关键一行**（通常不是第一行，而是最深的 cause）
- 定位到具体文件、函数、行号
- 区分**直接原因**（error message 所在位置）与**根因**（为什么会走到这里）

声明：`错误类型：X | 直接位置：<file>:<line> | 疑似根因区域：<描述>`

---

## Step 2: 根因追踪

从直接位置出发，向上追溯调用链，向下检查被调用的逻辑。

### 追踪策略（按错误类型选择）

**编译错误 / 类型错误**：
- 读取出错文件的相关上下文（前后 20 行）
- 追踪类型定义来源，检查是否有版本不匹配、feature flag 差异、条件编译分支

**运行时 panic**：
- 逐帧分析调用栈（若有）
- 重点检查：`unwrap()`/`expect()` 调用、数组越界、空指针解引用
- 追踪触发该路径的**输入条件**：什么样的输入会走到这里？

**测试失败**：
- 读取测试代码，理解预期行为
- 追踪被测函数的完整数据流：输入 → 变换 → 输出
- 对比预期值与实际值的差异，推断哪一步变换出错

**间歇性错误**：
- 标记为高风险，说明可能涉及 race condition 或时序依赖
- 检查共享状态的访问模式，识别缺失的同步原语

### 根因假设

列出 1–3 个根因假设，按可能性排序：

```
假设 1（最可能）：<具体描述，指向代码位置>
  证据：<支持该假设的代码特征>
  反驳：<可能排除该假设的因素>

假设 2：<...>
假设 3（兜底）：<...>
```

---

## Step 3: 假设验证

对每个假设，用最小代价验证其正确性，**不要还没验证就开始改代码**。

验证手段（按成本从低到高）：
1. **静态分析**：重新阅读相关代码，逻辑推演是否能复现错误
2. **添加临时日志**：在关键路径插入 `eprintln!` / `stderr` 输出，重新运行
3. **最小复现**：构造能稳定触发该错误的最小输入或测试用例
4. **注释隔离**：临时注释可疑代码块，确认错误是否消失

验证完成后，确认根因：
```
✅ 根因确认：<描述>
位置：<file>:<line> / <function>
触发条件：<什么情况下会触发>
影响范围：<仅此处 / 可能有其他调用方受影响>
```

若所有假设均被排除：
```
⚠️ 根因未确认，进入扩展分析...
```
扩展检查构建配置、依赖版本、环境变量、平台差异。

---

## Step 4: 修复实施

根因确认后，实施修复。

**修复原则**：
- 修复根因，不修复症状——不要只改让编译通过的那一行
- 若根因影响多处调用方，**一次性全部修复**，不留半修复状态
- 若修复涉及接口变更，同步更新所有调用方和相关测试
- 临时添加的调试日志**全部清除**

**对于间歇性错误**：修复后添加注释说明并发语义，并补充能稳定复现的回归测试。

---

## Step 5: 验证修复

运行构建和测试，确认修复有效：

```
Rust：   cargo build 2>&1 && cargo test 2>&1
C++：    xmake build 2>&1 && xmake test 2>&1
Python： uv run pytest 2>&1
Node：   npm run build 2>&1 && npm test 2>&1
Go：     go build ./... 2>&1 && go test ./... 2>&1
```

**结果处理**：

- ✅ 全部通过 → 进入 Step 6
- ❌ 原错误仍存在 → 回到 Step 2，重新审视根因假设
- ❌ 出现新错误 → 检查修复是否引入回归，优先回滚再重新分析
- ⚠️ 间歇性错误 → 运行 3 次以上，说明复现率变化

---

## Step 6: 调试报告 & 保存

将以下报告写入 `.discuss/debug-YYYYMMDD-HHMMSS.md`：

```markdown
# Debug Report

## Context
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 错误类型：<编译 / panic / 测试失败 / 逻辑错误 / 间歇性>
- 目标文件：<若指定>

## 原始错误
\```
<完整错误输出，截断至 100 行，超出部分注明"已截断">
\```

## 根因分析

### 直接位置
`<file>:<line>` — <错误描述>

### 根因
<具体描述：为什么会发生这个错误，而不只是在哪里发生>

### 触发条件
<什么样的输入/状态/时序会导致此错误>

### 排除的假设
- 假设 X：<描述> → 排除原因：<...>

## 修复方案

### 改动摘要
- `<file>`：<改动描述>

### 关键改动
\```diff
<核心 diff，10–30 行，聚焦最重要的改动>
\```

### 为何这样修复
<解释修复逻辑，而不只是"改了什么">

## 验证结果
- 构建：✅ / ❌
- 测试：✅ 全部通过 / ⚠️ N 个失败（说明）

## 后续建议
- <是否需要添加测试防止回归>
- <是否有类似模式在其他地方存在>
- <是否暴露了更深层的设计问题，建议 /self-evolution 跟进>
```

写入完成后输出：
`✓ 调试报告已保存至 .discuss/debug-YYYYMMDD-HHMMSS.md`

---

输出语言跟随用户输入语言。
