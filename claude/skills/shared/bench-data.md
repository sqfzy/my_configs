## Benchmark 数据持久化约定

所有执行 benchmark 的 skill 必须遵守此约定，确保数据统一沉淀、可追溯、可对比。

### 存储位置

- 数据目录：`.bench/`（项目根目录下，与 `.discuss/` 分离）
- 首次执行时自动创建：`mkdir -p .bench`

### 文件结构

每次 benchmark 执行产生两个动作：

#### 1. 数据文件：`.bench/YYYYMMDD-HHMMSS.txt`

- 内容：benchmark 工具的**完整原始输出**（如 `cargo bench`、`go test -bench`、`pytest --benchmark` 的 stdout）
- 使用 `tee` 或重定向捕获，不做裁剪
- 文件名使用执行开始时的时间戳

#### 2. 追加历史记录：`.bench/HISTORY.md`

每次 benchmark 执行后，向 `HISTORY.md` **追加**一行或多行（每个 benchmark 入口一行）：

```markdown
| 时间 | 来源 | Benchmark | Mean | 变化 | Commit | 数据文件 |
```

字段说明：
- **时间**：`YYYY-MM-DD HH:MM` 格式
- **来源**：触发 benchmark 的 skill 和上下文（如 `/bench profile`、`/refactor 基线`、`/bench optimize R3`、`/ship 验证`）
- **Benchmark**：benchmark 入口名称
- **Mean**：平均耗时（含单位：ns/us/ms/s）
- **变化**：与上一次同名 benchmark 的对比（如 `-12.3%`、`+5.1%`、`—` 表示首次）
- **Commit**：当前 HEAD 的 short hash
- **数据文件**：对应的原始数据文件名（不含路径前缀）

若 `HISTORY.md` 不存在，先创建并写入表头：

```markdown
# Benchmark History

| 时间 | 来源 | Benchmark | Mean | 变化 | Commit | 数据文件 |
|------|------|-----------|------|------|--------|----------|
```

然后追加数据行。

### 变化百分比计算

从 `HISTORY.md` 中查找同名 benchmark 的最近一条记录，计算变化百分比：

```
变化 = (当前 - 上次) / 上次 × 100%
```

- 首次记录：显示 `—`
- 改善（变快）：显示负值如 `-12.3%`
- 退化（变慢）：显示正值如 `+5.1%`

### 适用场景

以下场景必须执行此约定：

| 场景 | 来源标注 |
|------|----------|
| `/bench baseline` | `/bench baseline` |
| `/bench profile` | `/bench profile` |
| `/bench compare`（当前状态的测量） | `/bench compare` |
| `/bench optimize` 基线 | `/bench optimize 基线` |
| `/bench optimize` 每轮测量 | `/bench optimize R<N>` |
| `/bench optimize` 最终验证 | `/bench optimize 最终` |
| `/refactor` Phase 0 基线 | `/refactor 基线` |
| `/refactor` Phase 4 回归检查 | `/refactor 验证` |
| `/improve` 迭代中的 benchmark | `/improve R<N>` |
| `/migrate` Phase 0 基线 | `/migrate 基线` |
| `/migrate` Phase 3 回归检查 | `/migrate 验证` |
| `/ship` 性能验证 | `/ship 验证` |

### 使用方式

在 skill 中引用此模块的标准措辞：

```
运行 benchmark 并按 benchmark 数据持久化约定（shared/bench-data.md）保存原始数据到 .bench/ 并追加 HISTORY.md 记录。
```

### .gitignore 建议

`.bench/` 中的数据文件通常不需要提交到版本控制（体积大、与环境相关）。但 `HISTORY.md` 有追踪价值。建议：

```gitignore
.bench/*.txt
!.bench/HISTORY.md
```
