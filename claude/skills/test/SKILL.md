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

## 参数解析

- **目标**（必填）：指定要补充测试的文件、模块、或函数
- `[mode]`：测试生成模式，可逗号分隔多个
  - `gaps`（默认）：分析覆盖盲区，补充缺失的测试
  - `edge`：专注边界条件和错误路径
  - `fuzz`：生成模糊测试 / 随机输入测试
  - `prop`：生成基于属性的测试（property-based testing）
- `[no-run]`：仅生成测试代码，不执行

### 模式自动推断

若用户未显式指定模式参数，从 prompt 中推断：

| 关键词/意图 | 推断模式 |
|-------------|----------|
| "覆盖率"、"缺少测试"、"补测试" | gaps |
| "边界条件"、"极端情况"、"edge case" | edge |
| "fuzz"、"模糊测试"、"随机输入" | fuzz |
| "属性测试"、"property"、"不变量" | prop |

- 多个关键词匹配多个模式时，按合理顺序组合执行
- 无法推断时使用默认模式
- 推断结果输出一行声明：`▶ 推断模式：<mode>（从"<关键词>"推断）`

---

## Phase 0: 现状分析

### 0.1 理解目标代码

深入阅读目标文件/模块，提取：

- **所有公共函数/方法**：签名、参数类型、返回类型
- **所有代码路径**：条件分支、match/switch arms、early return
- **错误路径**：`Result::Err`、`Option::None`、异常抛出、panic 条件
- **外部依赖**：I/O 操作、网络调用、数据库访问、文件系统（影响测试策略）
- **不变量**：函数文档或注释中隐含的约束（"输入必须非空"、"返回值 ≥ 0"）

### 0.2 现有测试盘点

扫描已有的测试：

```bash
# 查找目标模块的测试文件
grep -rn "#\[test\]" <target> 2>/dev/null          # Rust
grep -rn "TEST\|TEST_F\|TEST_P" <target> 2>/dev/null  # C++ (Google Test)
grep -rn "def test_" <target> 2>/dev/null           # Python
grep -rn "func Test" <target> 2>/dev/null           # Go
```

对每个已有测试，记录它覆盖了什么：
- 被测函数
- 测试的输入类别（正常 / 边界 / 错误）
- 是否验证了返回值和副作用

### 0.3 覆盖缺口识别

将目标代码的所有路径与已有测试交叉对比，输出缺口报告：

```
## 测试覆盖分析

### 已覆盖
| 函数 | 正常路径 | 边界条件 | 错误路径 |
|------|----------|----------|----------|
| `parse_input()` | ✅ | ❌ | ✅ |
| `process_data()` | ✅ | ❌ | ❌ |

### 未覆盖的函数
- `validate_config()` — 完全没有测试
- `handle_timeout()` — 完全没有测试

### 识别的测试盲区
1. `parse_input()` 未测试空字符串输入
2. `process_data()` 未测试数据量超过 u32::MAX 的情况
3. `process_data()` 的错误分支（第 87 行的 Err 路径）无覆盖
4. ...
```

---

## Phase 1: 测试用例设计

根据 mode 参数和缺口分析，设计测试用例。

### mode: gaps（默认）

为每个缺口设计测试：

```
测试用例清单：
  [ ] <函数名>_<场景描述>
      输入：<具体值>
      预期：<返回值 / 副作用 / 错误类型>
      理由：<为什么需要这个测试>
```

**优先级排序**：
1. 完全无测试的公共函数
2. 错误路径无覆盖的函数
3. 边界条件缺失
4. 正常路径的补充场景

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

对每个公共函数，从上表中选取适用的边界值生成测试。

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

## Phase 4: 测试报告

按产物存储约定输出以下报告：

```markdown
# Test Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 目标：<文件/模块>
- 模式：<gaps / edge / fuzz / prop>

## 覆盖分析（改进前）

| 函数 | 正常路径 | 边界条件 | 错误路径 |
|------|----------|----------|----------|
| ... | ... | ... | ... |

## 新增测试

| 测试名 | 类型 | 覆盖目标 | 结果 |
|--------|------|----------|------|
| `test_parse_empty_input_returns_error` | 边界 | `parse_input()` 空输入 | ✅ |
| ... | ... | ... | ... |

## 覆盖分析（改进后）

| 函数 | 正常路径 | 边界条件 | 错误路径 |
|------|----------|----------|----------|
| ... | ... | ... | ... |

## 发现的缺陷
- 🐛 <描述>（建议 /debug 跟进）

## 待确认的行为
- ❓ <描述>

## 统计
- 新增测试：N 个
- 通过：N 个
- 发现缺陷：N 个
- 待确认：N 个
- 全量回归：✅ 通过

## 后续建议
- <哪些函数仍需更多覆盖>
- <是否建议增加 fuzz / prop 测试>
- <是否建议用 /improve 进行更深度的质量改善>
```

---

输出语言跟随用户输入语言。
