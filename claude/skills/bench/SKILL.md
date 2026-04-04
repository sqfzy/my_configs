---
name: bench
description: "Performance analysis and optimization — run benchmarks (baseline), identify hot paths (profile), compare before/after (compare), or run target-driven iterative optimization with correctness guarantees (optimize). Auto-saves reports to .artifacts/ TRIGGER when: user asks to profile, benchmark, optimize performance, investigate slowness/latency, compare before/after performance, or make code faster. DO NOT TRIGGER when: user mentions \"performance\" casually in feature requirements, or is writing benchmarks as part of /design or /test."
argument-hint: "<target or intent> [mode: profile|compare|optimize|baseline] [goal: <metric>] [max-rounds: N] [iterations: N] [no-commit] [auto]"
allowed-tools: Bash(find:*), Bash(cat:*), Bash(grep:*), Bash(head:*), Bash(wc:*), Bash(date:*), Bash(mkdir:*), Bash(git:*), Bash(cargo:*), Bash(xmake:*), Bash(uv:*), Bash(python:*), Bash(npm:*), Bash(go:*), Bash(perf:*), Bash(hyperfine:*), Bash(valgrind:*), Bash(flamegraph:*)
---

# /bench

当前时间：!`date '+%Y-%m-%d %H:%M:%S'`
当前目录：!`pwd`
当前分支：!`git branch --show-current 2>&1`
构建配置：!`find . -maxdepth 2 -name "xmake.lua" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "package.json" -o -name "go.mod" -o -name "CMakeLists.txt" 2>/dev/null | head -10`
现有 benchmark：!`find . -type f \( -path "*/benches/*" -o -name "bench_*.py" -o -name "*_bench.go" -o -name "*.bench.ts" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" 2>/dev/null | head -20`
现有测试：!`find . -type f \( -name "*_test.rs" -o -name "*_test.cpp" -o -name "test_*.py" -o -name "*.test.ts" -o -name "*_test.go" \) ! -path "*/target/*" ! -path "*/.git/*" ! -path "*/node_modules/*" | head -20`
性能工具可用性：!`command -v perf 2>/dev/null && echo "perf: yes" || echo "perf: no"; command -v hyperfine 2>/dev/null && echo "hyperfine: yes" || echo "hyperfine: no"; command -v valgrind 2>/dev/null && echo "valgrind: yes" || echo "valgrind: no"; command -v flamegraph 2>/dev/null && echo "flamegraph: yes" || echo "flamegraph: no"`

构建命令策略：!`cat ~/.claude/skills/shared/build-detect.md`
产物存储约定：!`cat ~/.claude/skills/shared/artifacts.md`
Plan 感知：!`cat ~/.claude/skills/shared/plan-aware.md`
现有计划：!`find .artifacts -name "plan-*.md" 2>/dev/null | head -10 || echo "(无)"`

目标：$ARGUMENTS

---

## 参数解析

- **目标**（必填）：要分析的文件、函数、模块，或性能意图描述
- `[mode]`：
  - `baseline`：运行 benchmark 并保存基线数据，不做分析
  - `profile`（默认）：运行 benchmark + 性能剖析，识别瓶颈
  - `compare`：对比两个状态（当前 vs 基线 / 当前 vs 指定 commit）
  - `optimize`：目标驱动的迭代优化——剖析、讨论、实施、验证，循环至达标或收敛
- `[iterations: N]`：benchmark 重复次数（覆盖默认值）
- 以下参数仅 `optimize` 模式：
  - `[goal: <metric condition>]`：性能目标，如 `goal: latency < 5ms`、`goal: throughput > 10000/s`、`goal: memory < 50MB`、`goal: 2x`（翻倍）。未指定则"尽可能优化直到收敛"
  - `[max-rounds: N]`：最大优化轮数上限，默认 **10**
  - `[no-commit]`：不自动提交每轮改动
  - `[auto]`：无人值守模式——跳过每轮确认，自动迭代

### 模式自动推断

若用户未显式指定模式参数，从 prompt 中推断：

| 关键词/意图 | 推断模式 |
|-------------|----------|
| "跑个 benchmark"、"测一下性能"、"保存基线" | baseline |
| "太慢了"、"性能瓶颈"、"为什么慢"、"profile" | profile |
| "对比"、"比较"、"退化了吗"、"和之前比" | compare |
| "优化"、"快一点"、"降到 X 以内"、"提升到 X" | optimize ⚠️ |

- 多个关键词匹配多个模式时，按合理顺序组合执行
- 无法推断时使用默认模式
- 推断结果输出一行声明：`▶ 推断模式：<mode>（从"<关键词>"推断）`
- 高风险模式（optimize）推断后需用户确认（auto 模式除外）

---

## 可复现原则

> **benchmark 产物必须包含足够信息让任何人能重新执行并得到可比较的结果。**

每次 benchmark 执行必须记录：
- **实际执行的完整命令**（构建命令 + benchmark 命令，可直接复制粘贴重跑）
- **编译器/工具链版本**（`rustc --version`、`g++ --version`、`go version` 等）
- **编译配置**（优化级别、关键标志、profile 设置如 LTO/codegen-units）
- **代码状态**（commit hash + 工作区是否干净）
- **运行环境**（OS、CPU 型号/核心数、内存）

这些信息必须同时出现在：
1. benchmark 报告的"环境与复现"部分
2. 原始数据文件（`bench-data-*.txt`）的头部注释

---

## Phase 0: 环境与 Benchmark 盘点

### 0.1 检测现有 Benchmark

搜索项目中已有的 benchmark 文件和入口点。根据语言使用对应的 benchmark 框架约定（Rust: criterion/bench、C++: Google Benchmark、Python: pytest-benchmark、Go: testing.B）。

- **若无 benchmark**：根据目标代码自动生成（见 0.3）
- **若有 benchmark**：列出所有入口及其覆盖的函数

### 0.2 检测性能工具

检查环境中可用的性能分析工具：

| 工具 | 用途 |
|------|------|
| `perf` | CPU 采样剖析、缓存命中分析 |
| `hyperfine` | CLI 命令级别的精确计时对比 |
| `valgrind` / `callgrind` | 调用图分析、缓存模拟 |
| `valgrind` / `massif` | 内存分配剖析 |
| `flamegraph` | 火焰图生成 |

记录可用工具列表，后续步骤据此选择分析方式。

### 0.3 生成缺失的 Benchmark（若需要）

若目标函数没有现有 benchmark，按项目语言和框架约定自动生成。

**关键原则**：
- 输入必须**有代表性**——过小的输入无法暴露真实瓶颈
- 使用 `black_box` / `DoNotOptimize` 等机制防止编译器优化掉被测代码
- 确认 benchmark 编译通过后再继续

### 0.4 正确性基线（仅 optimize 模式）

运行完整测试套件，建立正确性锚点：

```
根据构建命令获取策略（用户提供 > CLAUDE.md 声明 > 自动检测），确定并执行构建和测试命令。
```

- ✅ 全部通过 → 记录测试数量和用例名称作为正确性基线，继续
- ❌ 存在失败 → **终止**：
  ```
  ❌ 正确性基线未通过。请先修复现有测试失败，再开始优化。
  建议使用 /fix 修复后重试。
  ```

### 0.5 插桩（仅 optimize 模式，可选）

若需要函数内部各阶段耗时等细粒度数据，在关键路径上**临时**添加计时打点。

**关键原则**：
- 插桩使用项目已有的日志/追踪框架（Rust: tracing、C++: spdlog、等），不引入新依赖
- 记录每个插桩的**文件和行号**，Phase 5 必须全部移除
- 插桩不应改变代码逻辑，仅做观测

---

## Phase 1: 基线测量

### 1.1 运行 Benchmark

**必须在 release / 优化模式下运行**——debug 模式的数据无意义。根据构建命令获取策略确定并执行 benchmark 命令。**执行后立即按 bench-data 约定持久化**：原始输出写入 `.artifacts/bench-data-YYYYMMDD-HHMMSS.txt`，摘要追加到 `.artifacts/INDEX.md`。

### 1.2 解析结果

提取每个 benchmark 的关键指标：

```
## 基线数据

| Benchmark | 耗时 (mean) | 耗时 (median) | 标准差 | 吞吐量 | 内存分配 |
|-----------|------------|---------------|--------|--------|----------|
| <name>    | <X> ns     | <X> ns        | ±X%    | <X>/s  | <X> allocs |
```

**若 mode 为 `baseline`**：保存数据到 `.artifacts/bench-data-YYYYMMDD-HHMMSS.txt`，输出摘要后终止。

**若 mode 为 `optimize`**：额外记录目标确认：

```
## 优化目标

基线：<当前性能>
目标：<用户指定的目标 / "尽可能优化直到收敛">
差距：<需要提升 X% / 绝对差 Xms>
最大轮数：<N>

终止条件：
  1. 达到目标
  2. 连续 2 轮无有效改善（每轮提升 < 3%）
  3. 达到最大轮数
```

```bash
mkdir -p .artifacts
```

---

## Phase 2: 性能剖析（mode: profile / optimize）

### 2.1 CPU 剖析

根据可用工具选择剖析方式，优先级：perf > flamegraph > valgrind/callgrind > 手动打点。

- 以 release 模式编译后执行剖析
- 若可行，生成火焰图保存到 `.artifacts/flamegraph.svg`
- 剖析产物（callgrind.out、massif.out 等）保存到 `.artifacts/`

### 2.2 内存剖析（若目标涉及内存）

使用 valgrind/massif、Go pprof memprofile 等工具分析内存分配模式。关注：
- 分配次数和总分配量
- 分配热点函数
- 内存峰值和增长曲线

### 2.3 瓶颈识别

从剖析结果中提取 Top 5 热点，对每个热点分析**根因**——不只是"这里慢"，而是**为什么**慢：

```
## 性能瓶颈分析

### CPU 热点（Top 5）
| 排名 | 函数 | 占比 | 文件:行号 | 归因 |
|------|------|------|-----------|------|
| 1 | <name> | <X>% | <file>:<line> | <为什么慢> |
| ... | ... | ... | ... | ... |

### 内存热点（若分析了内存）
| 函数 | 分配次数 | 总分配量 | 说明 |
|------|----------|----------|------|
| ... | ... | ... | ... |

### 瓶颈归因
<对每个热点逐一分析：
  - 算法复杂度问题？O(n²) 但输入 n 很大？
  - 不必要的内存分配？循环内 clone / to_string / 临时容器？
  - 缓存不友好？数据布局导致 cache miss？
  - I/O 阻塞？同步等待？
  - 锁竞争？>
```

**若 mode 为 `profile`**：输出瓶颈分析后终止，附优化建议但不实施。

---

## Phase 3: 优化迭代（仅 mode: optimize）

### 核心原则

> **正确性不可牺牲**。任何优化改动后，现有测试必须全部通过。若优化不可避免地改变了某些外部可观测行为（如浮点精度、排序稳定性、错误消息措辞），必须在行为变更记录中声明。

- **测量驱动**——不凭直觉猜，用数据说话
- **一次一改**——每轮只改一个优化点，否则无法归因
- **无效即回滚**——无效的优化立即回滚，不留无用的复杂度

以下步骤循环执行，直到满足终止条件。

### 3.1 方案讨论（3 角色快速评审）

从角色库中选出 3 个角色进行 **2 轮快速评审**：

!`cat ~/.claude/skills/shared/roles.md`

**推荐组合**：R3（性能狂热者）+ R2（极简主义者）+ R1（风险卫士）

**聚焦问题**：
- 方案是否真的能解决已识别的瓶颈？
- 是否有更简单的替代方案能达到类似效果？
- 是否可能引入正确性问题或行为变化？
- 是否引入了不必要的复杂度？

每个角色须对具体方案给出明确支持或反对：

```
【角色名 | 立场】
论点：...（指向具体代码位置和性能数据）
风险评估：...
建议：...
```

**评审结论**：
```
## 第 N 轮评审结论
- 采纳方案：<描述>
- 预期收益：<估算>
- 风险：<注意事项>
- 否决的方案：<列表，附原因>
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

### 3.2 实施

实施评审通过的优化方案。**每轮只做一个优化改动**。

### 3.3 验证

验证分三步，顺序执行，任一步失败则阻断后续：

#### 3.3.1 正确性验证

运行完整测试套件，对比 Phase 0.4 的正确性基线。

- ✅ 全部通过 → 继续
- ❌ 测试失败 → 分析失败原因：
  - **实现 bug**（优化手误）→ 修复，最多重试 2 次
  - **行为变化**（优化不可避免地改变了外部行为）→ 记录到行为变更记录：
    ```
    ⚠️ 行为变更：<描述>
    旧行为：<...>
    新行为：<...>
    原因：<为什么优化导致了这个变化>
    影响：<谁会受影响>
    ```
    更新对应测试以反映新行为，**但此条目将出现在最终报告的行为变更清单中**。
  - **2 次修复后仍失败** → 回滚该轮优化，记录失败原因，跳过此优化方向，进入下一轮

#### 3.3.2 性能测量

以 release/优化模式运行 benchmark，**按 bench-data 约定持久化后**，对比上一轮结果：

```
## 第 N 轮结果

| 指标 | 上轮 | 本轮 | 变化 |
|------|------|------|------|
| 耗时 (mean) | <X> | <Y> | <±Z%> |
| ... | ... | ... | ... |

优化内容：<本轮做了什么>
收益归因：<为什么变快了 / 为什么没效果>
```

- 有效改善（≥3%）→ 提交（除非 `no-commit`），进入下一轮
- 无效或退化 → 回滚该轮优化，记录原因，进入下一轮

#### 3.3.3 提交（若有效）

使用 `perf(<scope>): <描述优化内容>` 格式提交。

### 3.4 终止判断

每轮结束后检查终止条件：

```
## 第 N 轮终止检查

当前性能：<latest measurement>
目标：<goal>
已用轮数：N / max-rounds

□ 达到目标？→ 终止，进入 Phase 4
□ 连续 2 轮无有效改善（< 3%）？→ 终止（收敛），进入 Phase 4
□ 达到最大轮数？→ 终止，进入 Phase 4
□ 以上均不满足 → 回到 Phase 2（重新剖析，因为瓶颈分布可能已变化）
```

**重要**：每次回到 Phase 2 时必须**重新剖析**——优化可能改变了热点分布，旧的剖析数据不再准确。

### 3.5 迭代确认（非 auto 模式）

```
┌─────────────────────────────────────────────┐
│  📊 第 N 轮完成                               │
├─────────────────────────────────────────────┤
│                                             │
│  本轮优化 ： <描述>                          │
│  性能变化 ： <X>ns → <Y>ns（<±Z%>）          │
│                                             │
│  ── 累计进度 ──                              │
│  基线 ： <X>                                 │
│  当前 ： <Y>（总提升 <Z%>）                   │
│  目标 ： <goal>                              │
│  差距 ： <remaining>                         │
│                                             │
│  回复「继续」进入下一轮，或提出新方向         │
└─────────────────────────────────────────────┘
```

**在此处暂停，等待用户确认。**

**`auto` 模式**：不暂停，自动继续。

---

## Phase 4: 全量验证（仅 optimize 模式）

所有优化完成后：

### 完整 Benchmark

```
根据构建命令获取策略，确定并执行 benchmark 命令。**按 bench-data 约定持久化**到 `.artifacts/`。
```

### 正确性回归

```
根据构建命令获取策略，确定并执行测试命令。
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

## Phase 5: 清理（仅 optimize 模式）

### 5.1 清理插桩

移除 Phase 0.5 中添加的所有临时计时打点。按记录的位置逐一清理，搜索确认无遗留。

清理后运行构建 + 测试，确认清理未破坏代码。

若生成的 benchmark 文件对项目有长期价值，保留；若仅为本次优化临时创建，询问用户是否保留（`auto` 模式：保留）。

### 5.2 最终验证

确认清理后的性能数据与最后一轮优化结果一致（插桩移除不应影响性能）。

### 5.3 提交

```
chore: remove optimization instrumentation
```

---

## Phase 6: 报告

按产物存储约定输出报告。

### baseline / profile 模式报告

```markdown
# Benchmark Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 模式：<baseline / profile>
- 目标：<描述>
- 分支：<branch>

## 环境与复现

### 运行环境
- OS：<uname -sr>
- CPU：<model, cores/threads>
- 内存：<total RAM>
- 编译器：<rustc --version / g++ --version / go version>
- 可用工具：<perf / hyperfine / valgrind / flamegraph>

### 编译配置
<相关的 profile/编译标志，如 [profile.bench] 内容或 xmake 优化选项>

### 复现命令
\```bash
# Commit: <hash> (worktree: clean / dirty)
<实际执行的完整构建命令>
<实际执行的完整 benchmark 命令>
\```

## 基线数据

| Benchmark | Mean | Median | Std Dev | Throughput | Allocs |
|-----------|------|--------|---------|------------|--------|
| ... | ... | ... | ... | ... | ... |

## 性能剖析结果（若执行了 profile）

### CPU 热点
| 排名 | 函数 | 占比 | 位置 | 归因 |
|------|------|------|------|------|
| ... | ... | ... | ... | ... |

### 内存热点（若分析了内存）
| 函数 | 分配次数 | 总分配量 | 说明 |
|------|----------|----------|------|
| ... | ... | ... | ... |

### 火焰图
<若生成了火焰图：.artifacts/flamegraph.svg>

## 后续建议
- <优化建议但不实施>
- <是否建议用 /bench optimize 进行迭代优化>
```

### optimize 模式报告

```markdown
# Optimization Report

## 概况
- 时间：<开始时间>
- 耗时：<X 分 Y 秒>
- 模式：optimize
- 目标代码：<target>
- 性能目标：<goal / "尽可能优化">
- 目标达成：✅ 已达成 / ⚠️ 收敛但未达目标 / ❌ 达到轮数上限
- 优化轮数：N 轮（有效 M 轮，回滚 K 轮）
- 分支：<branch>

## 环境与复现

### 运行环境
- OS：<uname -sr>
- CPU：<model, cores/threads>
- 内存：<total RAM>
- 编译器：<rustc --version / g++ --version / go version>
- 可用工具：<perf / hyperfine / valgrind / flamegraph>

### 编译配置
<相关的 profile/编译标志，如 [profile.bench] 内容或 xmake 优化选项>

### 复现命令
\```bash
# Commit: <hash> (worktree: clean / dirty)
<实际执行的完整构建命令>
<实际执行的完整 benchmark 命令>
\```

## 性能对比

| 指标 | 基线 | 最终 | 变化 | 提升 |
|------|------|------|------|------|
| 耗时 (mean) | <X> | <Y> | <-Z> | <+W%> |
| 吞吐量 | <X>/s | <Y>/s | <+Z> | <+W%> |
| 内存分配 | <X> | <Y> | <-Z> | <-W%> |

## 优化历程

### 第 1 轮：<标题>
- 瓶颈：<识别的瓶颈，占比>
- 方案：<做了什么>
- 评审摘要：<采纳理由>
- 结果：<前> → <后>（提升 X%）
- Commit：<hash>

### 第 2 轮：<标题>
...

### 第 N 轮（回滚）：<标题>
- 方案：<尝试了什么>
- 失败原因：<为什么无效 / 为什么破坏正确性>

## 瓶颈演变

\```
基线热点：
  1. parse_token()   35%
  2. validate()      22%
  3. allocate()      15%

最终热点（优化后）：
  1. io_read()       28%  ← 原本占比小，优化其他后暴露
  2. parse_token()   18%  ← 从 35% 降至 18%
  3. serialize()     12%
\```

## 正确性验证
- 基线测试数量：N
- 最终测试数量：N（一致 ✅ / 有变化 ⚠️）
- 全部通过：✅ / ❌

## 行为变更记录

> 若优化过程中未产生任何行为变更，此节显示"无行为变更"。

| 轮次 | 变更描述 | 旧行为 | 新行为 | 原因 |
|------|----------|--------|--------|------|
| N | <描述> | <旧> | <新> | <为什么优化导致了变化> |

## 终止原因
<达成目标 / 连续 2 轮无有效改善（收敛） / 达到轮数上限>

<若未达成目标，分析原因：>
- 当前瓶颈在哪里？
- 为什么剩余瓶颈难以优化？（I/O bound？算法下界？硬件限制？）
- 是否有需要更大架构变更才能突破的优化方向？（建议 /refactor breaking）

## 后续建议
- <是否有未探索的优化方向>
- <是否建议在 CI 中加入 benchmark 回归检测>
- <是否建议用 /bench baseline 定期监控>
- <是否有架构层面的优化需要 /discuss 或 /refactor breaking>
```

---

## mode: compare — 对比模式

当 mode 为 `compare` 时，执行简化流程：

### 确定对比对象

| 输入 | 行为 |
|------|------|
| 无额外参数 | 对比最近保存的基线（`.artifacts/bench-data-*.txt`）与当前 |
| `<commit-hash>` | checkout 该 commit 跑 benchmark，对比当前 |
| `<branch>` | checkout 该分支跑 benchmark，对比当前 |

### 执行对比

1. 保护工作区（若有未提交改动则 stash）
2. 切到参照状态运行 benchmark，记录结果
3. 切回当前状态（恢复 stash）
4. 在当前状态运行 benchmark，记录结果
5. 输出对比表：

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
