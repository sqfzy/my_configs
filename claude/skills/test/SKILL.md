---
name: test
description: "Analyze test coverage gaps and generate targeted tests — boundary conditions, error paths, property-based tests, and fuzzing. Auto-saves test report to .artifacts/ TRIGGER when: user asks to add/supplement tests, improve test coverage, find untested code paths, or generate edge-case/fuzz/property tests for existing code. DO NOT TRIGGER when: tests are being written as part of /design or /fix workflow, or user is running existing tests (just run them directly)."
argument-hint: "<target file or module> [mode: gaps|edge|fuzz|prop] [no-run]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*)
---

# /test

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
项目文件概览：!`find . -type f \( -name "*.rs" -o -name "*.cpp" -o -name "*.hpp" -o -name "*.h" -o -name "*.py" -o -name "*.ts" -o -name "*.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -60`
现有测试文件：!`find . -type f \( -name "*_test.rs" -o -name "*_test.cpp" -o -name "test_*.py" -o -name "*.test.ts" -o -name "*_test.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -30`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`

目标：$ARGUMENTS

---

## 核心理念

> **风险驱动，而非覆盖率驱动。**

Line coverage % 是欺骗性指标——一个项目可以做到 90% line coverage 但全是 getter/setter，而真正的危险代码（解析器、状态机、并发、边界条件）零覆盖。

test skill 的第一步是**扫描识别危险代码**，按风险分级生成测试。低风险代码（trivial getter/wrapper）只生成 1 个 smoke test，不详细测试。报告使用四指标（危险代码覆盖率、错误路径覆盖率、断言具体性、mutation score）替代 line coverage 作为主要判定。

---

## 参数解析

- **目标**（必填）：指定要补充测试的文件、模块、或函数
- `[mode]`：测试生成模式，可逗号分隔多个
  - `gaps`（默认）：风险扫描 + 按风险分级补充测试
  - `edge`：专注边界条件和错误路径
  - `fuzz`：生成模糊测试 / 随机输入测试
  - `prop`：生成基于属性的测试（property-based testing）
  - `mutation`：运行 mutation testing（需项目安装 `cargo-mutants`/`mutmut` 等）
  - `coverage-only`：传统 line coverage 模式（不推荐，仅在用户显式要求时使用）
- `[no-run]`：仅生成测试代码，不执行

### 模式自动推断

若用户未显式指定模式参数，从 prompt 中推断：

| 关键词/意图 | 推断模式 |
|-------------|----------|
| "覆盖率"、"缺少测试"、"补测试" | gaps |
| "边界条件"、"极端情况"、"edge case" | edge |
| "fuzz"、"模糊测试"、"随机输入" | fuzz |
| "属性测试"、"property"、"不变量" | prop |
| "mutation"、"变异测试" | mutation |

- 多个关键词匹配多个模式时，按合理顺序组合执行
- 无法推断时使用默认模式
- 推断结果输出一行声明：`▶ 推断模式：<mode>（从"<关键词>"推断）`

---

## Phase 0: 风险扫描 + 现状分析

### 0.1 理解目标代码

深入阅读目标文件/模块，提取：

- **所有公共函数/方法**：签名、参数类型、返回类型
- **所有代码路径**：条件分支、match/switch arms、early return
- **错误路径**：`Result::Err`、`Option::None`、异常抛出、panic 条件
- **外部依赖**：I/O 操作、网络调用、数据库访问、文件系统（影响测试策略）
- **不变量**：函数文档或注释中隐含的约束（"输入必须非空"、"返回值 ≥ 0"）

### 0.2 危险代码扫描（必需）

> **铁律**：必须先扫描识别危险代码，再基于清单生成测试。禁止按"完全无测试的函数"作为唯一标准。

用以下 9 类信号扫描目标代码，产出**危险代码清单**：

| 类别 | 识别信号 |
|------|----------|
| **解析器** | 函数名含 `parse/decode/deserialize/tokenize/lex`；接受 `&str`/`&[u8]`；内部有循环+分支；返回 `Result` |
| **状态机** | `enum` + `match` + 状态转换函数；字段名含 `state/status/phase`；显式状态转换表 |
| **边界条件** | 数值运算（加减乘除可能溢出）、索引访问、切片/字符串长度处理、空集合处理 |
| **并发** | `Arc<Mutex>`、`RwLock`、`atomic::*`、`async/await`、`tokio::spawn`、`thread::spawn`、channel |
| **错误恢复** | `Result` 链、`?` 密集（5+ 连续）、`catch_unwind`、retry/backoff 逻辑 |
| **外部输入** | 接受 `&str`/`&[u8]`/`Vec<u8>` 且直接处理外部数据（非内部调用链起点） |
| **资源管理** | 文件句柄、锁、网络连接、临时目录的获取/释放路径（尤其是错误路径的 cleanup） |
| **时间相关** | `Duration`、`Instant`、`SystemTime`、超时、过期、TTL、时钟相关逻辑 |
| **协议边界** | 函数从低层接收解密/解码后的数据并向上层 emit/callback/sink（decrypt→emit, decode→sink, process→callback）；签名含 Emit/Sink/Callback 模板参数或 `std::function`/闭包；代码从全栈库（OpenSSL、kernel TCP、std::io）提取状态后自己实现后续处理（"接管"模式） |

> **第 9 类"协议边界"说明**：前 8 类关注"这个函数本身会不会出错"，第 9 类关注"这个函数会不会把**不该交给上层的东西**交给上层"。典型 bug：TLS decrypt 后未检查 inner content type，把 NewSessionTicket 当 application data emit 给 codec。这类 bug 的特征是：函数本身正确执行了（解密成功），但语义过滤缺失。

扫描命令示例（Rust）：

```bash
grep -rEn "fn (parse|decode|deserialize|tokenize|lex)" <target> 2>/dev/null
grep -rn "Arc<Mutex\|RwLock\|atomic::" <target> 2>/dev/null
grep -rn "unsafe\|catch_unwind" <target> 2>/dev/null
# 协议边界：函数接收 emit/sink/callback 并在循环中转发数据
grep -rEn "emit\(|sink\(|callback\(|on_data\(|on_message\(" <target> 2>/dev/null
# C++: 模板参数含 Emit/Sink/Callback
grep -rEn "template.*Emit|template.*Sink|template.*Callback" <target> 2>/dev/null
# 接管模式：从全栈库提取状态后自己处理
grep -rEn "extract_.*state|hot_state|take_ownership|handoff" <target> 2>/dev/null
```

**危险代码清单**必须输出到报告，用户可审阅/修正：

```
## 🚨 危险代码清单

| # | 函数 | 位置 | 危险类别 | 当前测试 |
|---|------|------|----------|----------|
| 1 | `parse_token()` | `lexer.rs:42` | 解析器 + 边界条件 | ❌ 无 |
| 2 | `State::transition()` | `fsm.rs:87` | 状态机 | ⚠️ 仅 happy path |
| 3 | `validate_input()` | `input.rs:120` | 外部输入 + 错误恢复 | ❌ 无 |
| 4 | `with_lock()` | `pool.rs:55` | 并发 + 资源管理 | ❌ 无 |
| ... | ... | ... | ... | ... |

## 🟢 低危代码（仅生成 smoke test）

| # | 函数 | 位置 | 类别 |
|---|------|------|------|
| 1 | `Config::name()` | `config.rs:15` | trivial getter |
| 2 | `Pair::new()` | `pair.rs:8` | trivial constructor |
| ... | ... | ... | ... |
```

### 0.3 现有测试盘点

扫描已有的测试：

```bash
# 查找目标模块的测试文件
grep -rn "#\[test\]" <target> 2>/dev/null          # Rust
grep -rn "TEST\|TEST_F\|TEST_P" <target> 2>/dev/null  # C++ (Google Test)
grep -rn "def test_" <target> 2>/dev/null           # Python
grep -rn "func Test" <target> 2>/dev/null           # Go
```

对每个已有测试，记录：
- 被测函数
- 测试的输入类别（正常 / 边界 / 错误）
- 是否验证了返回值和副作用
- **断言质量**（见 Phase 2.4）：是具体断言还是 `is_ok()` 类空洞断言

### 0.4 错误路径清点

静态扫描目标代码中所有错误返回路径：

```bash
# Rust
grep -nE "return Err\(|bail!|\.ok_or|Err\(|panic!\(" <target>
# Python
grep -nE "raise |throw " <target>
# Go
grep -nE "return .*err|return .*, err" <target>
```

记录每个错误路径的**位置和错误变体**，后续用于计算"错误路径覆盖率"。

### 0.5 接管清单（当检测到"接管"模式时）

> **触发条件**：Phase 0.2 扫描到"协议边界"类别中的"接管"模式 —— 代码从全功能库（OpenSSL、kernel TCP、std::io、libcurl 等）中提取状态/密钥/fd 后，自己实现后续处理。
>
> 这是最容易遗漏 bug 的场景：全栈库内部处理了 N 种消息类型，接管代码往往只想到了其中 1-2 种，其余的默默变成了上层的垃圾数据。

**执行步骤**：

1. 识别被接管的全栈库和接管点（如 `extract_hot_state()` 从 OpenSSL 接管 TLS record 处理）
2. 查阅该协议的 RFC/spec，列出全栈库在接管点之后可能收到的**全部消息类型**
3. 对每个消息类型，确认当前代码是：
   - ✅ **处理了** → 需要 happy-path 测试
   - 🔇 **有意跳过** → 需要"毒丸测试"验证它被正确过滤（不会泄漏到上层）
   - ❌ **遗漏了** → 🐛 这就是 bug，立即标记

**输出格式**：

```
## 🔄 接管清单

接管点：`extract_hot_state()` (tls_state.hpp:104)
被接管库：OpenSSL/aws-lc TLS 1.3 全栈
接管后职责：AEAD 解密 + 向 codec emit 明文

| 消息类型 (RFC 8446)   | inner_ct | 当前处理 | 毒丸测试 |
|-----------------------|----------|----------|----------|
| application_data      | 0x17     | ✅ emit  | —        |
| handshake (NST)       | 0x16     | 🔇 跳过  | test_nst_not_emitted |
| handshake (KeyUpdate) | 0x16     | 🔇 跳过  | test_keyupdate_not_emitted |
| alert                 | 0x15     | 🔇 跳过  | test_alert_not_emitted |
| change_cipher_spec    | 0x14     | ❌ 遗漏  | 🐛 需修复 |
```

对每个 🔇 行，Phase 1 必须生成一个**毒丸测试**：构造该类型的合法消息，验证它不会到达上层。
对每个 ❌ 行，立即报告为缺陷（参照 Phase 3.2 的 🐛 格式）。

---

## Phase 1: 测试用例设计

根据 mode 参数和缺口分析，设计测试用例。

### mode: gaps（默认）

基于 Phase 0.2 的**危险代码清单**和 Phase 0.4 的错误路径清点，按风险分级设计测试：

```
测试用例清单（按 Tier 分组）：

## Tier 1 — 危险代码的核心行为 + 错误路径（优先级最高）
  [ ] test_<函数名>_<场景描述>
      目标：<危险代码清单中的第 N 项>
      输入：<具体值>
      预期：<具体返回值 / 具体错误变体>
      理由：<对应哪个危险类别>

## Tier 2 — 边界条件
  [ ] test_<函数名>_<边界描述>
      输入：<边界值>
      预期：<具体行为>

## Tier 3 — Happy path 补齐（仅在 Tier 1/2 完成后）
  [ ] test_<函数名>_<正常场景>

## Smoke — 低危代码（仅生成 1 个 smoke test）
  [ ] smoke_<函数名>
      仅调用一次，断言不 panic
      名字前缀必须为 `smoke_`，方便统计时排除
```

**分层原则**：
- **Tier 1 是必需的**——危险代码清单中的每一项必须至少有一个核心行为测试和一个错误路径测试
- **Tier 2 补齐边界**——数值溢出、空集合、极端长度等
- **Tier 3 仅补齐缺失的 happy path**——不重复已有测试
- **低危代码不生成详细测试**——每个低危函数仅生成 1 个 `smoke_<name>` 测试（防止隐藏逻辑漏测），不计入危险代码覆盖率

**禁止**：
- 为 trivial getter/setter/wrapper 生成详细的 unit test（浪费且误导覆盖率）
- 生成只为"刷覆盖率"的测试（例如只调用不断言）

### mode: edge

专注边界条件和错误路径，系统性生成：

| 输入类型 | 边界值 |
|----------|--------|
| 数值 | 0, 1, -1, MAX, MIN, MAX+1（溢出） |
| 字符串 | `""`, 单字符, 超长字符串, Unicode, 含空字节 |
| 集合 | `[]`, 单元素, 重复元素, 极大集合 |
| Option/Nullable | `None` / `null` / `nil` |
| 文件路径 | 不存在, 无权限, 符号链接, 超长路径 |
| 并发 | 同时读写, 重入调用, 超时 |
| **协议消息类型** | 每个 RFC/spec 定义的合法消息类型，**而非只测预期类型**。构造"结构合法但语义错误"的输入（毒丸）验证过滤逻辑。例：TLS record inner_ct=0x16, TCP flags 全 0/全 1, HTTP method=CONNECT 对不支持代理的服务器 |

对每个公共函数，从上表中选取适用的边界值生成测试。

> **毒丸测试原则**：边界值测试关注"极端的值"，毒丸测试关注"错误的类型"。两者缺一不可。一个函数可能对 `len=0` 和 `len=MAX` 都正确处理了，却对 `type=handshake`（而非预期的 `type=appdata`）完全没有过滤。

### mode: fuzz

生成模糊测试骨架：

**Rust**（使用 `cargo-fuzz` / `arbitrary`）：
```rust
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    if let Ok(input) = std::str::from_utf8(data) {
        let _ = target_function(input);
    }
});
```

**C++**（使用 libFuzzer）：
```cpp
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    // ...
    return 0;
}
```

**Python**（使用 `hypothesis`）：
```python
from hypothesis import given, strategies as st

@given(st.binary())
def test_fuzz_target(data):
    target_function(data)
```

为每个适合模糊测试的函数（接受外部输入、解析器、序列化/反序列化）生成入口。

### mode: prop

识别代码中的不变量，生成属性测试：

**常见属性模式**：
- **往返性**（Roundtrip）：`decode(encode(x)) == x`
- **幂等性**（Idempotent）：`f(f(x)) == f(x)`
- **单调性**（Monotonic）：`x ≤ y → f(x) ≤ f(y)`
- **交换性**（Commutative）：`f(a, b) == f(b, a)`
- **不变量保持**：操作前后某条件始终成立

```
属性测试清单：
  [ ] <属性名>：<描述>
      生成器：<输入如何随机生成>
      属性断言：<什么条件必须始终成立>
```

---

## Phase 2: 测试实现

### 2.1 确定测试位置

按项目约定放置测试文件：

```
Rust：  同文件 #[cfg(test)] mod tests / tests/<module>_test.rs
C++：   tests/<module>_test.cpp（使用 Google Test 或项目已有框架）
Python：tests/test_<module>.py
Go：    <module>_test.go（同包）
```

若项目已有测试文件，将新测试追加到对应文件中，保持组织一致。

### 2.2 编写测试

**命名规范**：测试名描述场景，不用序号：
- ✅ `test_parse_empty_input_returns_error`
- ✅ `test_process_data_with_max_u32_does_not_overflow`
- ❌ `test1`, `test_parse_2`, `test_new`

**结构规范**（Arrange-Act-Assert）：
```
// Arrange: 构造输入和预期
// Act: 调用被测函数
// Assert: 验证结果
```

**测试质量要求**：
- 每个测试只验证一个行为，不做多件事
- 测试之间无状态依赖，可独立运行
- 错误路径测试要断言**具体的错误类型/消息**，不只是 `is_err()`
- I/O 密集型代码优先写集成测试；纯逻辑优先写单元测试

**语言特定**：

**Rust**：
- 使用 `#[should_panic(expected = "...")]` 测试 panic 路径
- 使用 `assert_matches!` 或 `matches!` 测试枚举变体
- 属性测试使用 `proptest` crate
- 模糊测试使用 `cargo-fuzz`

**C++**：
- 使用 `EXPECT_*` 优于 `ASSERT_*`（允许同一测试中收集多个失败）
- 参数化测试使用 `TEST_P` + `INSTANTIATE_TEST_SUITE_P`
- `EXPECT_THROW` / `EXPECT_NO_THROW` 验证异常行为
- `std::expected` 错误路径用 `EXPECT_FALSE(result.has_value())` + `EXPECT_EQ(result.error(), ...)`

**Python**：
- 使用 `pytest.raises` 测试异常
- 使用 `pytest.mark.parametrize` 做参数化
- 属性测试使用 `hypothesis`

### 2.3 编译验证

测试编写完成后，先确认编译/导入通过（不运行）：

根据项目构建系统，验证测试代码能编译/收集通过（不实际运行）。

修复编译错误直到通过。

### 2.4 断言质量门（必需）

> **铁律**：生成的测试必须经过断言质量检查。空洞断言是"假测试"——能提升覆盖率却不保护正确性。

**空洞断言黑名单**（禁止作为唯一断言）：

| 模式 | 示例 | 问题 |
|------|------|------|
| 恒真 | `assert!(true)`, `assert!(1 == 1)` | 不测试任何东西 |
| 仅存在性 | `assert!(result.is_ok())` | 不验证 Ok 内部值 |
| 仅存在性 | `assert!(result.is_some())` | 不验证 Some 内部值 |
| 仅非空 | `assert!(!vec.is_empty())` | 不验证内容 |
| 仅不 panic | 只调用函数无 assert | 只保证不 panic |
| 仅 is_err | `assert!(result.is_err())` | 不验证具体错误变体 |

**合法替代**：

| 空洞断言 | 合法替代 |
|----------|----------|
| `result.is_ok()` | `assert_eq!(result.unwrap(), expected)` 或 配合另一个具体断言 |
| `result.is_err()` | `assert_matches!(result, Err(ParseError::Empty))` |
| `vec.is_empty()` | `assert_eq!(vec, expected_contents)` |

**例外**（合法的空洞断言）：
- **smoke test**：名字前缀 `smoke_` 的测试允许仅调用不断言（统计时单独归类）
- **属性测试的不变量**：`assert_eq!(decode(encode(x)), x)` 这类不变量断言合法（它区分了正确和错误行为）
- **`is_ok()` 配合另一个具体断言**：如先 `is_ok()` 再 `assert_eq!(result.unwrap().field, expected)`

**执行方式**：

对每个生成的测试做静态扫描，统计：
- 具体断言数量
- 空洞断言数量（分类：`is_ok`、`is_some`、`is_empty`、`true`/`false`、无断言）
- 属性断言数量（合法）

若存在空洞断言，必须修正或升级为具体断言后才能进入 Phase 3。

---

## Phase 3: 执行与修正

除非指定 `no-run`，运行所有新增的测试。

### 3.1 运行测试

若用户提供了测试命令则优先使用；否则根据项目构建系统和配置，自行确定并执行测试命令（可指定 filter 运行特定测试）。

### 3.2 结果分析

- ✅ **全部通过** → 进入 Phase 4
- ❌ **测试失败** → 区分原因：
  - **被测代码确实有 bug** → 🎯 测试发现了真实缺陷！记录该 bug，不修改测试使其"通过"：
    ```
    🐛 发现缺陷：<函数名> 在 <条件> 下 <错误行为>
    - 测试：<test_name>
    - 预期：<expected>
    - 实际：<actual>
    - 建议使用 /fix 修复（或 /debug 先定位根因）
    ```
  - **测试本身写错了**（预期值不正确）→ 修正测试，重新运行
  - **测试暴露了未文档化的行为**（代码"正常工作"但与直觉不符）→ 标记为需确认：
    ```
    ❓ 行为确认：<函数名> 在 <条件> 下返回 <值>
    这是预期行为还是 bug？请确认。
    ```

### 3.3 回归验证

确认新增测试没有破坏现有测试：

若用户提供了测试命令则优先使用；否则根据项目构建系统和配置，自行确定并执行全量测试命令。

全部通过方可继续。

---

## Phase 4: 测试报告（四指标）

> **核心原则**：主要判定基于四指标（危险代码覆盖率、错误路径覆盖率、断言具体性、mutation score），line/branch coverage 保留但降级为参考指标。

按产物存储约定输出以下报告：

````markdown
# Test Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 目标：<文件/模块>
- 模式：<gaps / edge / fuzz / prop / mutation>

---

## 🎯 质量报告（主指标）

```
┌─────────────────────────────────────────────────┐
│  🎯 危险代码覆盖率 ：  12 / 15  (80%)            │
│     未覆盖：parser.rs:87, state.rs:42,          │
│              validator.rs:120                   │
├─────────────────────────────────────────────────┤
│  🔄 协议边界毒丸    ：  3 / 4  (75%)             │
│     未覆盖：1 个消息类型无毒丸测试               │
├─────────────────────────────────────────────────┤
│  ⚠️  错误路径覆盖率 ：  23 / 28  (82%)           │
│     未覆盖：5 个 Err 路径（见下方清单）           │
├─────────────────────────────────────────────────┤
│  📝 断言具体性     ：  34 / 37  (92%)           │
│     空洞断言：3 处（见下方清单）                 │
├─────────────────────────────────────────────────┤
│  🧬 Mutation score ：  ⏭️ 未运行                 │
│     （可用 /test mutation 运行）                 │
└─────────────────────────────────────────────────┘
```

### 🚨 Phase 0 识别的危险代码清单

<Phase 0.2 输出的完整清单，标注每项是否已被测试覆盖>

### ⚠️ 未覆盖的错误路径

| # | 位置 | 错误变体 | 建议测试 |
|---|------|----------|----------|
| 1 | `parser.rs:87` | `ParseError::EmptyInput` | `test_parse_empty_returns_err` |
| ... | ... | ... | ... |

### 📝 空洞断言清单

| 测试 | 问题 | 修复建议 |
|------|------|----------|
| `test_parse_ok` | 仅 `result.is_ok()` | 补充 `assert_eq!(result.unwrap(), expected)` |
| ... | ... | ... |

### 🔄 接管清单（若 Phase 0.5 触发）

<Phase 0.5 输出的完整接管清单，标注每个消息类型的处理状态和毒丸测试>

---

## ℹ️  参考指标（不作为主要判定）

> Line/branch coverage 无法反映测试质量——高数值可能全是 getter 和 smoke test。仅作为参考。

| 指标 | 数值 |
|------|------|
| Line coverage | 67% |
| Branch coverage | 54% |

---

## 新增测试

### Tier 1（危险代码 + 错误路径）

| 测试名 | 覆盖目标 | 断言类型 | 结果 |
|--------|----------|----------|------|
| `test_parse_empty_input_returns_error` | `parse_input()` 空输入 → `ParseError::Empty` | 具体错误变体 | ✅ |
| ... | ... | ... | ... |

### Tier 2（边界条件）

| 测试名 | 边界值 | 结果 |
|--------|--------|------|
| ... | ... | ... |

### Tier 3（Happy path）

| 测试名 | 场景 | 结果 |
|--------|------|------|
| ... | ... | ... |

### Smoke tests（低危代码）

> 单独统计，不计入危险代码覆盖率

| 测试名 | 目标 | 结果 |
|--------|------|------|
| `smoke_config_name` | `Config::name()` | ✅ |
| ... | ... | ... |

---

## 🐛 发现的缺陷

| # | 描述 | 测试 | 预期 | 实际 | 建议 |
|---|------|------|------|------|------|
| 1 | <描述> | <测试名> | <预期> | <实际> | `/fix` |
| ... | ... | ... | ... | ... | ... |

## ❓ 待确认的行为

| # | 函数 | 条件 | 当前行为 | 问题 |
|---|------|------|----------|------|
| ... | ... | ... | ... | ... |

---

## 统计

| 项 | 数量 |
|----|------|
| Tier 1 新增测试 | N |
| Tier 2 新增测试 | M |
| Tier 3 新增测试 | K |
| Smoke tests | P |
| 通过 | Q |
| 发现缺陷 | R |
| 待确认 | S |
| 全量回归 | ✅ 通过 / ❌ 失败 |

---

## 后续建议

- <危险代码清单中仍未覆盖的项>
- <是否建议运行 `/test mutation` 验证断言强度>
- <是否建议 `/test fuzz` 对解析器增加模糊测试>
- <是否暴露了设计缺陷，建议 `/improve` 跟进>
````

---

## mode: mutation — 变异测试

当 mode 为 `mutation` 时，对目标模块运行 mutation testing，验证测试套件的实际保护强度。

### 前置条件

检查项目是否安装了 mutation 工具：

```bash
# Rust
command -v cargo-mutants 2>&1

# Python
command -v mutmut 2>&1

# Go
# go-mutesting
```

若未安装：
```
❌ mutation testing 需要安装对应工具：
  Rust:   cargo install cargo-mutants
  Python: pip install mutmut
  Go:     go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest

安装后重新运行 /test mutation <target>
```
终止。

### 执行

```bash
# Rust
cargo mutants --file <target> 2>&1

# Python
mutmut run --paths-to-mutate <target> 2>&1
```

运行结果会标识哪些 mutation 被测试捕获（killed）、哪些存活（survived，即测试没发现）。

### 报告

```markdown
## 🧬 Mutation Testing Report

- 工具：cargo-mutants / mutmut / go-mutesting
- 目标：<target>
- 总 mutation 数：N
- 被捕获（killed）：M
- 存活（survived）：K
- **Mutation score**：M / N (X%)

### 存活的 mutation（暴露测试不足）

| # | 位置 | 变异描述 | 存活原因分析 |
|---|------|----------|--------------|
| 1 | `parser.rs:87` | `>` → `>=` | 未测试边界相等情况 |
| 2 | `fsm.rs:42` | 删除 `state = State::Done` | 无测试验证最终状态 |
| ... | ... | ... | ... |

### 修复建议

对每个存活的 mutation，建议添加针对性测试。
```

**判定标准**：
- Mutation score ≥ 80% → 测试套件较强
- Mutation score 50–80% → 存在明显盲区，需补充
- Mutation score < 50% → 测试严重不足，大量"虚假覆盖"

---

## mode: coverage-only — 传统模式

仅当用户显式要求时使用。跳过风险扫描和四指标，仅输出 line/branch coverage。

**警告输出**：
```
⚠️  coverage-only 模式不推荐使用。
   Line coverage 无法反映真实测试质量——高覆盖率可能全是 getter 和 smoke test。
   建议改用默认的 gaps 模式（风险驱动 + 四指标）。
```

---

## 关联 skill

- **`/fix`**：发现危险代码无测试时，若配合 bug 修复，用 `/fix` 的全流程（它会调用 `/test` 补缺口）而非单独跑 `/test`
- **`/design`** / **`/design deep`**：新功能开发期间的测试应通过 `/design` 的 TDD 阶段产生，不需要事后补跑 `/test`
- **`/bench`**：测试覆盖和性能回归是两套指标，复杂模块两者都要跑
- **`/debug`**：测试暴露出来的失败先交给 `/debug` 定位根因再修复
- **`/improve`**：`/test` 补上缺口后，可用 `/improve` 对测试代码本身做质量提升

---

输出语言跟随用户输入语言。
