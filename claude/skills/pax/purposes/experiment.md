# Purpose: experiment

设计并执行**受控实验**：对比 / 消融 / 超参搜索 / A/B / 效应测量 / 假设验证。核心是**统计严谨 + 可说服性**——任何审稿人 / 同行 / 未来的自己能挑出的漏洞都要提前堵上。

本文件只定义 experiment 目的**独有**的约束，通用维度（定位 / 现状 / 目标 / 影响 / 生产级 8 维度 / 图示 / 实施计划字段）由 SKILL.md 规定。

---

## 与 bench 的边界

| | bench | experiment |
|---|-------|-----------|
| 焦点 | 性能单维度测量（p99 / 吞吐 / profile） | 受控对比 + 假设检验 |
| 产物 | 基线曲线 / profile 报告 / 退化检测 | 预注册假设 → 统计结论 + 效应量 + CI |
| 适用 | "这个版本多快？" | "X 是否**真的**导致 Y？" / "A 是否**显著**优于 B？" |

**升级规则**：性能对比若需显著性检验（"这次优化真提升了 p99 吗"），归 experiment 不归 bench。

---

## 铁律（贯穿全流程）

1. **预注册**：假设 + 分析计划写在看数据之前，带时间戳。违反 = HARKing（Hypothesizing After Results are Known），学术界和工程界都判死刑。
2. **p-value 永不裸报**：每个结论必带 **p + 95% CI + effect size**（Cohen's d / Cliff's δ / η² / OR / relative risk），三件套缺一视同未证。
3. **Power 先于 n**：不做 power analysis 就跑实验 = 耍流氓。不够预算做足 n 的 → 降低 power 或换设计；不得边跑边看边停（sequential peeking 会膨胀 α）。
4. **偏离全程记录**：施工期任何改动（剔 run / 换种子 / 改度量 / 延长 n）入"偏离日志"，最终报告显式列出。
5. **所有变体全报**：失败条件 / 异常 run / 被拒绝的假设一并写入，不挑好看的（与 `/report` §2.10 覆盖完整一致）。

---

## experiment 独有的必展开章节（Phase 2）

### 1. 研究问题（RQ）

一句话。可证伪、指向具体对象、避免主观词（"更好" ❌；"在 workload W 下 p99 降低 ≥ 10%" ✓）。

### 2. 假设（预注册）

必须含时间戳，且明确：

```
预注册时间：<UTC ISO 8601>
（声明：以下假设与分析计划在看到数据之前写定。偏离必须进偏离日志。）

H0（null）: <X 与 Y 无差异 / 无效应>
H1（alternative）: <具体方向：单侧 / 双侧；预期 effect size 及出处>
```

禁 HARKing：看到数据后反推假设 = 不合格。

### 3. 变量清单

| 角色 | 变量 | 类型 | 取值域 / 水平 | 测量方式 |
|------|------|------|-------------|---------|
| IV（自变量）| 操纵什么 | 连续 / 离散 / 二分 | ... | ... |
| DV（因变量）| 测量什么 | 同上 | ... | 单位 / 采样频率 |
| 控制变量 | 固定什么 | ... | ... | hold |
| 混杂因子 | 可能共变的 | ... | ... | hold / randomize / stratify / block |

混杂因子未识别全 = 内部有效性威胁——Phase 3 自检拦截。

### 4. 实验设计

必须明确：
- **设计类型**：Between-subjects / Within-subjects / Factorial / RCBD（随机区组）/ Latin-square / Crossover / Split-plot / 纵向
- **分组方式**：完全随机 / 分层随机 / 配对 / 自身对照
- **重复次数**：每单元 n 次，说明为什么这个 n（承上功率分析）
- **顺序 / 位置效应控制**：随机化顺序 / 拉丁方 / 预热 run 丢弃
- **盲法**：双盲 / 单盲 / 实验者自动化（杜绝实验者预期偏差）
- **运行环境隔离**：独立机 / CPU 亲和 / isolated cgroup / 停止其他进程

### 5. 样本量 & 功率分析（硬要求）

```
预期 effect size : d = 0.5（来源：pilot n=10 的观察 / 文献 X / 保守估计）
目标 power       : 0.80
显著性水平 α     : 0.05（双侧）
计算工具         : G*Power 3.1 / R pwr 包 / 解析公式
→ 最小 n         : 64 per group（总 n = 128）
```

其它要求：
- 若预算不够 → 降低 power 或换设计，**不得**边跑边看
- Sequential / adaptive 设计需预注册 stopping rule（例如 O'Brien-Fleming / alpha-spending）
- effect size 出处必须可追溯（pilot 数据 commit / 文献 DOI / 参数推导式）

### 6. 分析计划（预注册）

**每个假设对应一个预选检验**：

```
检验选型
├── 数据类型：连续 / 计数 / 类别 / 时间-事件
├── 分布假设：正态 / 非正态 / 未知
├── 组间独立性：独立 / 配对
└── → 主检验：...
    选型理由：...

假设检查（violate 的回退方案）
├── 正态性：Shapiro-Wilk + Q-Q plot；违反 → Mann-Whitney / 非参
├── 方差齐性：Levene；违反 → Welch's t
├── 独立性：运行顺序残差自相关；违反 → 混合效应模型
└── 离群值：预先规定剔除准则（例 IQR×1.5、Grubbs）

决策规则
├── 采纳 H1：p < α 且 effect size ≥ 实质阈值 且 CI 不跨 0
├── 拒绝 H1：p ≥ α 或 effect size < 实质阈值
└── Inconclusive：power < 0.80 或 CI 跨决策边界 → 补样本 / 存疑

多重比较校正
├── 族系：主族（pre-specified）vs 探索族（exploratory）
├── 方法：Bonferroni / Holm / Benjamini-Hochberg（FDR）
└── 数量：k = ...（在预注册时锁定）

报告三件套（每结论必含）
├── p-value（精确值，不要 "p < 0.05"）
├── 95% 置信区间
└── effect size：Cohen's d / Cliff's δ / η² / OR / HR / RR（按数据类型选）
```

**铁律**：p-value 永不单独报。缺 CI 或 effect size 视同未证。

### 7. 随机化 & 种子

- **RNG 选型**：PCG / Mersenne Twister / 加密级（看需求）
- **种子策略**：主种子 + 每 trial 派生种子（splitmix / hash），全部落盘
- **非决定性源**：GPU 非决定性、时钟抖动、缓存状态、NIC 队列调度、OS 调度 —— 逐项说明如何缓解（`CUDA_DETERMINISTIC` / `taskset` / `PYTHONHASHSEED` / ...）

### 8. 复现包（硬要求）

他人能**一键复现**：

```
experiment-<id>/
├── README.md              ← 目的 + 如何跑
├── environment/
│   ├── Dockerfile / flake.nix / environment.yml
│   └── hw-snapshot.txt    ← lscpu / free / nvidia-smi / kernel / 编译器版本
├── scripts/
│   ├── 00_setup.sh
│   ├── 01_pilot.sh
│   ├── 02_main.sh        ← 随机顺序 + 分块内嵌
│   └── 03_analyze.R/.py
├── raw/                  ← 不覆盖；仅追加；每次 run 独立文件
├── processed/            ← 由 03 生成
├── analysis/             ← R/Python notebook + 锁定依赖版本（renv / poetry.lock）
├── seeds.log             ← 每 run 一行：timestamp + trial_id + seed + cmd
├── deviations.log        ← 偏离日志
└── report/               ← /report experiment --auto 产物
```

### 9. 对有效性的威胁（必须正面回应）

| 类别 | 问题 | 本实验的防线 |
|------|------|-------------|
| Internal validity（内部）| X 真的**因果**导致 Y 吗？混杂 / 选择偏差 / 时序? | 随机化 / 混杂控制 / 时序正确 / 盲法 |
| External validity（外部）| 结果能**推广**吗？样本 / 环境 / 时间段 | 样本代表性论证 / 环境多样性 / 明确限定适用域 |
| Construct validity（构念）| DV **真的测**到想测的吗？ | 度量定义明确 / 辅助度量交叉验证 |
| Statistical conclusion | 统计推断**可靠**吗？ | 功率 ≥ 0.80 / 假设检查 / 异常值规则 / 校正 |

**禁空栏**。确实无防线的要写"承认此威胁 + 结论适用域收窄到 XX"。

---

## experiment 必含 ASCII 图示（在通用要求之上追加）

- **实验设计图**：条件 × 复制 × 块的矩阵 / 流程图
- **数据流水线**：采集 → 质控 → 清洗 → 分析 → 报告
- **统计决策树**：数据分布检查 → 选哪个检验 → 结论分支
- **预期 effect 分布图**（计划阶段）：基于 power 分析画预期分布 + decision region；施工末改为"预期 vs 实际"对照

**样例（决策树）**：

```
[Shapiro-Wilk p > 0.05?]
    │
    ├─ yes ──▶ [Levene p > 0.05?]
    │            │
    │            ├─ yes ──▶ Student's t-test
    │            └─ no  ──▶ Welch's t-test
    │
    └─ no  ──▶ [n > 30 per group?]
                 │
                 ├─ yes ──▶ Welch's t-test（CLT robust）
                 └─ no  ──▶ Mann-Whitney U
```

---

## experiment 实施计划的特殊阶段（施工契约）

实验类施工按以下顺序推进，每阶段独立可回滚：

```
阶段 1  环境与基线捕获         锁定 hw/sw snapshot；commit environment/
阶段 2  Pilot（小 n）           验流水线 + 校准 effect size 初估 + 测单轮耗时
                               → 若 effect size 偏离预期 ±50%，回阶段 0 重算 n
阶段 3  主实验运行             随机顺序 + 分块；种子 + 元数据逐条落盘
阶段 4  质控                   诊断 + 异常标注（**不删不补**）
阶段 5  假设检查               分布 / 方差 / 独立性 / 离群值 → 决定主检验 or 回退
阶段 6  主分析                 严格按预注册执行；禁中间"看一眼"
阶段 7  稳健性检查             敏感性分析（去 outlier 前后）/ 分层分析 / 贝叶斯替代
阶段 8  报告生成               调 /report experiment --auto
```

**施工纪律（严于通用）**：
- 阶段 1-3 的数据在阶段 4 前**不得预览**——预览 = 数据污染（即使是"就看一眼是否跑对了"也不行；用合成数据或 dry-run 验流水线）
- 意外发现开**新 RQ**（进后续实验），**不得**改原 H1 假装预测到了
- 任何中途决策（剔 run / 改 seed / 换度量 / 延 n）**立即**入 `deviations.log`，报告原样展示
- 单元测试 + 分析脚本的测试在阶段 1 写完（TDD 实验代码）

---

## 反模式（Phase 3 自检必拦）

| 反模式 | 后果 |
|-------|------|
| 缺 H0 / H1 | 拒绝 —— 无假设的"实验"归 review（探索），不归 experiment |
| 缺 RQ 的可证伪表述 | 拒绝 —— "让它变好"不是 RQ |
| 缺 power / n 推导 | 拒绝 —— 结果无意义 |
| effect size 来源不可追溯 | 拒绝 |
| p 裸报（缺 CI / effect size） | 拒绝 |
| 无预注册声明或无时间戳 | 拒绝（HARKing 风险） |
| n = 1 单次运行下结论 | 拒绝（无 variance） |
| α post-hoc 调整 / sequential peeking without spending | 拒绝 |
| outlier 无事先剔除规则 | 拒绝 |
| 多重比较未校正 | 拒绝 |
| 混杂因子未列全 / 无防线 | 拒绝 |
| "统计显著" ≡ "实质重要" | 语言自检；要区分 statistical vs practical significance |
| 只报赢的条件 / 隐藏失败 run | 拒绝（与 /report §2.10 一致） |
| 改 H1 迎合数据 | 拒绝 —— 新发现开新 RQ |
| 分析代码无锁依赖 | 拒绝 —— 不可复现 |

---

## 与其他 skill / 目的的集成

- **bench**：性能单维度测量归 bench；需统计显著性的性能对比升级 experiment
- **`/pax --review` (lens=statistics)**：审视已有实验的严谨性
- **`/report experiment --auto`**：阶段 8 **必调**，产出带 raw data 链接的正式报告
- **`/script --auto`**：分析脚本 / pilot 脚本 / 数据清洗脚本归 script；experiment 产出分析命令序列交给 script 固化
- **BODY 调 experiment 不建议在 loop 里**：loop 的快速迭代与 experiment 的预注册严谨性相冲（除非 UNTIL 明确是"跑够 K 个独立实验"且每个实验内部仍守铁律）

---

## Plan 独有章节（Phase 4 插入位置：紧跟"目标形态"之后）

```markdown
## 研究问题 (RQ)
<一句话，可证伪>

## 假设（预注册）
预注册时间：<UTC ISO 8601>
声明：以下内容在看到数据前写定。

- H0: <null>
- H1: <alternative + 方向 + 预期 effect size>

## 变量
| 角色 | 变量 | 类型 | 取值域 | 测量方式 |
|------|------|------|-------|---------|
| IV  | ... | ... | ... | ... |
| DV  | ... | ... | ... | ... |
| 控制 | ... | ... | ... | hold |
| 混杂 | ... | ... | ... | randomize / stratify |

## 实验设计
- 类型: <Between / Within / Factorial / RCBD / ...>
- 分组: ...
- 重复: n = ... per cell
- 顺序/位置效应控制: ...
- 盲法: ...
- 环境隔离: ...

## 样本量与功率分析
- 预期 effect size: ...（来源）
- 目标 power: 0.80
- α: 0.05（双/单侧）
- 工具: ...
- 最小 n: ...

## 分析计划（预注册）
- 主检验: ...（选型理由）
- 假设检查: ...
  - 违反 A → 回退 ...
  - 违反 B → 回退 ...
- 决策规则:
  - 采纳 H1: ...
  - 拒绝 H1: ...
  - Inconclusive: ...
- 多重比较: <族 / 方法 / k>
- 报告三件套: p + 95% CI + <effect size metric>

## 随机化 & 种子
- RNG: ...
- 种子策略: ...
- 非决定性源与缓解: ...

## 复现包
- env: ...
- hw/sw snapshot: ...
- 目录结构: raw/ processed/ analysis/ scripts/
- 一键命令: scripts/run_all.sh

## 对有效性的威胁
| 类别 | 问题 | 防线 |
|------|------|------|
| Internal | ... | ... |
| External | ... | ... |
| Construct | ... | ... |
| Statistical | ... | ... |

## 偏离日志（施工期填）
<每条：时间 / 什么决策 / 为什么 / 影响评估>
```

---

输出语言跟随用户输入语言。
