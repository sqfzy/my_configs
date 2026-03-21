---
name: bench
description: Performance analysis and optimization — run benchmarks, identify hot paths, compare before/after, and guide targeted optimization. Auto-saves benchmark report to .discuss/
TRIGGER when: user asks to profile, benchmark, optimize performance, investigate slowness/latency, or compare before/after performance.
DO NOT TRIGGER when: user mentions "performance" casually in feature requirements, or is writing benchmarks as part of /feature or /test.
argument-hint: "<target or intent> [mode: profile|compare|optimize|baseline] [iterations: N]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*), Bash(perf:*), Bash(hyperfine:*), Bash(valgrind:*)
---

# /bench

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`
现有 benchmark：!`find . -type f \( -path "*/benches/*" -o -name "bench_*.py" -o -name "*_bench.go" -o -name "*.bench.ts" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" 2>/dev/null | head -20`
性能工具可用性：!`command -v perf 2>/dev/null && echo "perf: yes" || echo "perf: no"; command -v hyperfine 2>/dev/null && echo "hyperfine: yes" || echo "hyperfine: no"; command -v valgrind 2>/dev/null && echo "valgrind: yes" || echo "valgrind: no"; command -v flamegraph 2>/dev/null && echo "flamegraph: yes" || echo "flamegraph: no"`

目标：$ARGUMENTS

---

## 参数解析

- **目标**（必填）：要分析的文件、函数、模块，或性能意图描述（如 "解析器太慢"、"内存占用过高"）
- `[mode]`：
  - `baseline`：运行 benchmark 并保存基线数据，不做分析
  - `profile`（默认）：运行 benchmark + 性能剖析，识别瓶颈
  - `compare`：对比两个状态（当前 vs 基线 / 当前 vs 指定 commit）
  - `optimize`：完整流程——剖析、定位瓶颈、实施优化、验证结果
- `[iterations: N]`：benchmark 重复次数（覆盖默认值）

---

## Phase 0: 环境与 Benchmark 盘点

### 0.1 检测现有 Benchmark

```bash
# Rust (criterion / bench)
find . -path "*/benches/*.rs" 2>/dev/null
grep -rn "criterion_group\|#\[bench\]" . --include="*.rs" 2>/dev/null | head -20

# C++ (Google Benchmark / 自定义)
find . -name "*.cpp" -exec grep -l "BENCHMARK\|benchmark::" {} \; 2>/dev/null | head -20

# Python (pytest-benchmark / asv)
find . -name "bench_*.py" -o -name "*_benchmark.py" 2>/dev/null | head -20

# Go
find . -name "*_test.go" -exec grep -l "func Bench" {} \; 2>/dev/null | head -20
```

**若无 benchmark**：根据目标代码自动生成（见 Phase 0.3）。
**若有 benchmark**：列出所有 benchmark 入口及其覆盖的函数。

### 0.2 检测性能工具

根据环境检查可用的性能分析工具：

| 工具 | 用途 | 检测 |
|------|------|------|
| `perf` | CPU 采样剖析、缓存命中分析 | `command -v perf` |
| `hyperfine` | CLI 命令级别的精确计时对比 | `command -v hyperfine` |
| `valgrind` / `callgrind` | 调用图分析、缓存模拟 | `command -v valgrind` |
| `flamegraph` / `cargo-flamegraph` | 火焰图生成 | `command -v flamegraph` |
| `cargo-criterion` | Rust 统计 benchmark | Cargo.toml 中是否有 criterion |

记录可用工具列表，后续步骤据此选择分析方式。

### 0.3 生成缺失的 Benchmark（若需要）

若目标函数没有现有 benchmark，自动生成：

**Rust**（criterion）：
```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_target_function(c: &mut Criterion) {
    // 构造有代表性的输入
    let input = prepare_input();
    c.bench_function("target_function", |b| {
        b.iter(|| target_function(black_box(&input)))
    });
}

criterion_group!(benches, bench_target_function);
criterion_main!(benches);
```

**C++**（Google Benchmark）：
```cpp
#include <benchmark/benchmark.h>

static void BM_TargetFunction(benchmark::State& state) {
    auto input = prepare_input();
    for (auto _ : state) {
        benchmark::DoNotOptimize(target_function(input));
    }
}
BENCHMARK(BM_TargetFunction);
```

**Python**（pytest-benchmark）：
```python
def test_bench_target_function(benchmark):
    input_data = prepare_input()
    benchmark(target_function, input_data)
```

**Go**：
```go
func BenchmarkTargetFunction(b *testing.B) {
    input := prepareInput()
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        targetFunction(input)
    }
}
```

确认 benchmark 编译通过后继续。

---

## Phase 1: 基线测量

### 1.1 运行 Benchmark

**确保在 release / 优化模式下运行**（debug 模式的数据无意义）：

```
Rust：   cargo bench 2>&1 | tee .discuss/bench-run.txt
         # 或指定 target：cargo bench --bench <name> 2>&1
C++：    xmake build -m release -g bench 2>&1 && xmake run -g bench 2>&1 | tee .discuss/bench-run.txt
Python： uv run pytest --benchmark-only --benchmark-min-rounds=10 2>&1 | tee .discuss/bench-run.txt
Go：     go test -bench=. -benchmem -count=5 ./... 2>&1 | tee .discuss/bench-run.txt
```

### 1.2 解析结果

提取每个 benchmark 的关键指标：

```
## 基线数据

| Benchmark | 耗时 (mean) | 耗时 (median) | 标准差 | 吞吐量 | 内存分配 |
|-----------|------------|---------------|--------|--------|----------|
| <name>    | <X> ns     | <X> ns        | ±X%    | <X>/s  | <X> allocs |
```

**若 mode 为 `baseline`**：保存数据到 `.discuss/bench-baseline-YYYYMMDD-HHMMSS.txt`，输出摘要后终止。

---

## Phase 2: 性能剖析（mode: profile / optimize）

### 2.1 CPU 剖析

根据可用工具选择剖析方式：

**perf（首选，若可用）**：
```bash
# Rust
cargo build --release 2>&1
perf record -g --call-graph dwarf target/release/<binary> <args> 2>&1
perf report --stdio --sort=overhead 2>&1 | head -60

# C++
xmake build -m release 2>&1
perf record -g --call-graph dwarf ./build/<binary> <args> 2>&1
perf report --stdio --sort=overhead 2>&1 | head -60
```

**flamegraph（若可用）**：
```bash
cargo flamegraph --bench <name> -o .discuss/flamegraph.svg 2>&1
```

**valgrind / callgrind（若 perf 不可用）**：
```bash
valgrind --tool=callgrind --callgrind-out-file=.discuss/callgrind.out target/release/<binary> <args> 2>&1
```

### 2.2 内存剖析（若目标涉及内存）

```bash
# Rust: 使用 DHAT 或 jemalloc profiling
# C++: valgrind --tool=massif
valgrind --tool=massif --massif-out-file=.discuss/massif.out target/release/<binary> <args> 2>&1

# Go: pprof
go test -bench=. -memprofile=.discuss/mem.prof ./... 2>&1
```

### 2.3 瓶颈识别

从剖析结果中提取 Top 热点：

```
## 性能瓶颈分析

### CPU 热点（Top 5）
| 排名 | 函数 | 占比 | 文件:行号 | 说明 |
|------|------|------|-----------|------|
| 1 | `parse_token()` | 35% | `src/parser.rs:142` | 热循环内的字符串分配 |
| 2 | `validate()` | 22% | `src/validator.rs:87` | 重复的正则编译 |
| ... | ... | ... | ... | ... |

### 内存热点（若分析了内存）
| 函数 | 分配次数 | 总分配量 | 说明 |
|------|----------|----------|------|
| ... | ... | ... | ... |

### 瓶颈归因
<对每个热点，分析 WHY——不只是"这里慢"，而是为什么慢：
  - 算法复杂度？O(n²) 但输入 n 很大？
  - 不必要的内存分配？循环内 clone / to_string？
  - 缓存不友好？数据布局导致 cache miss？
  - I/O 阻塞？同步等待？
  - 锁竞争？>
```

**若 mode 为 `profile`**：输出瓶颈分析后终止，附优化建议但不实施。

---

## Phase 3: 优化实施（mode: optimize）

### 3.1 优化方案设计

对每个瓶颈设计优化方案，按预期收益排序：

```
## 优化方案

### 优化 1：<标题>
- 瓶颈：<哪个热点，占比多少>
- 方案：<具体怎么改>
- 预期收益：<估算>
- 风险：<可能的副作用>
- 复杂度：<改动量>

### 优化 2：...
```

**优化优先级**：
1. **低垂果实**：简单改动、高收益（如消除循环内不必要的分配）
2. **算法改进**：更换算法或数据结构
3. **缓存/批处理**：减少 I/O 或减少重复计算
4. **底层优化**：SIMD、内存布局优化、编译器 hints

**不做的优化**：
- 未经测量证实的"直觉优化"
- 牺牲可读性但收益不明确的 micro-optimization
- 影响正确性的 unsafe 优化（除非用户明确要求且性能收益显著）

### 3.2 逐一实施与验证

每个优化独立实施和验证：

```
for each 优化 in 方案:
    1. 实施改动
    2. 编译：cargo build --release / xmake build -m release
    3. 测试：cargo test / xmake test  （确认正确性未受损）
    4. 单点 benchmark：cargo bench --bench <name>  （确认该点确实变快了）
    5. 记录结果：
       - 改进幅度：<X>ns → <Y>ns（提升 Z%）
       - 若无改进或退化 → 回滚该优化，记录原因
    6. 提交（若有效）：
       git add -A && git commit -m "perf(<scope>): <描述>"
```

**关键纪律**：
- 一次只改一个优化点——否则无法归因收益
- 每步都跑 benchmark 确认——直觉不可靠
- 正确性测试失败 → 立即回滚，优化绝不能牺牲正确性

---

## Phase 4: 全量验证

所有优化完成后：

### 完整 Benchmark

```
Rust：   cargo bench 2>&1 | tee .discuss/bench-after.txt
C++：    xmake build -m release -g bench 2>&1 && xmake run -g bench 2>&1 | tee .discuss/bench-after.txt
Python： uv run pytest --benchmark-only 2>&1 | tee .discuss/bench-after.txt
Go：     go test -bench=. -benchmem -count=5 ./... 2>&1 | tee .discuss/bench-after.txt
```

### 正确性回归

```
Rust：   cargo test 2>&1
C++：    xmake test 2>&1
Python： uv run pytest 2>&1
Go：     go test ./... 2>&1
```

### 前后对比汇总

```
## 优化结果对比

| Benchmark | 基线 | 优化后 | 变化 | 提升 |
|-----------|------|--------|------|------|
| <name>    | <X>ns | <Y>ns | -<Z>ns | +<W>% |
| ... | ... | ... | ... | ... |

总体提升：<加权平均或最关键指标的变化>
```

---

## Phase 5: Benchmark 报告

```bash
mkdir -p .discuss
```

写入 `.discuss/bench-YYYYMMDD-HHMMSS.md`：

```markdown
# Benchmark Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 模式：<baseline / profile / compare / optimize>
- 目标：<描述>
- 分支：<branch>

## 环境
- OS：<uname>
- CPU：<model, cores>
- 可用工具：<perf / hyperfine / valgrind / flamegraph>

## 基线数据

| Benchmark | Mean | Median | Std Dev | Throughput | Allocs |
|-----------|------|--------|---------|------------|--------|
| ... | ... | ... | ... | ... | ... |

## 性能剖析结果（若执行了 profile/optimize）

### CPU 热点
| 排名 | 函数 | 占比 | 位置 | 归因 |
|------|------|------|------|------|
| ... | ... | ... | ... | ... |

### 火焰图
<若生成了火焰图：.discuss/flamegraph.svg>

## 优化记录（若执行了 optimize）

| 优化 | 描述 | 前 | 后 | 提升 | Commit |
|------|------|----|-----|------|--------|
| 1 | <描述> | <X>ns | <Y>ns | +Z% | <hash> |
| 2 | <描述> | ... | ... | ... | <hash> |
| ❌ | <回滚的优化> | — | — | 无效 | — |

## 最终对比

| Benchmark | 基线 | 最终 | 变化 |
|-----------|------|------|------|
| ... | ... | ... | ... |

### 正确性验证
- 测试：✅ 全部通过（N 个）
- Clippy / Lint：✅ 无新增警告

## 后续建议
- <还有哪些可优化的方向未探索>
- <是否建议补充更多 benchmark 覆盖>
- <是否有算法层面的优化需要更深度的 /discuss>
- <是否建议在 CI 中加入 benchmark 回归检测>
```

写入完成后输出：
`✓ Benchmark 报告已保存至 .discuss/bench-YYYYMMDD-HHMMSS.md`

---

## mode: compare — 对比模式

当 mode 为 `compare` 时，执行简化流程：

### 确定对比对象

| 输入 | 行为 |
|------|------|
| 无额外参数 | 对比最近保存的基线（`.discuss/bench-baseline-*.txt`）与当前 |
| `<commit-hash>` | checkout 该 commit 跑 benchmark，对比当前 |
| `<branch>` | checkout 该分支跑 benchmark，对比当前 |

### 执行对比

1. 在参照状态运行 benchmark，记录结果
2. 切回当前状态运行 benchmark，记录结果
3. 输出对比表：

```
## Benchmark 对比

参照：<commit/branch/baseline file>
当前：<HEAD>

| Benchmark | 参照 | 当前 | 变化 | 判定 |
|-----------|------|------|------|------|
| <name> | <X>ns | <Y>ns | -12% | ✅ 改善 |
| <name> | <X>ns | <Y>ns | +3% | ⚠️ 轻微退化 |
| <name> | <X>ns | <Y>ns | +15% | 🔴 显著退化 |

判定标准：
  ✅ 改善 > 5%
  ➡️ 持平 ±5%
  ⚠️ 轻微退化 5–15%
  🔴 显著退化 > 15%
```

---

输出语言跟随用户输入语言。
