## Skill 产物统一存储约定

> **铁律：所有 skill 产生的报告、数据文件，必须存入 `.artifacts/` 并追加 INDEX.md 记录。没有例外。**

### 存储位置

- 统一目录：`.artifacts/`（项目根目录下）
- 首次使用时自动创建：`mkdir -p .artifacts`

### 文件命名规则

`<skill>-YYYYMMDD-HHMMSS.<ext>`

| 类型 | 命名示例 | 说明 |
|------|----------|------|
| 讨论记录 | `discuss-20260328-013000.md` | |
| 代码审查 | `review-20260328-020000.md` | |
| 重构报告 | `refactor-20260328-030000.md` | |
| 改进报告 | `improve-20260328-040000.md` | |
| 修复报告 | `fix-20260328-050000.md` | |
| 演进报告 | `evolve-20260328-060000.md` | |
| 迁移报告 | `migrate-20260328-070000.md` | |
| 发布报告 | `ship-20260328-080000.md` | |
| 调试报告 | `debug-20260328-090000.md` | |
| 测试报告 | `test-20260328-100000.md` | |
| 文档报告 | `doc-20260328-110000.md` | |
| 设计报告 | `design-20260328-120000.md` | |
| 复盘报告 | `retro-20260328-130000.md` | |
| 合并报告 | `merge-20260328-140000.md` | sync 或 port 模式的合并/移植报告 |
| Benchmark 报告 | `bench-20260328-140000.md` | |
| Benchmark 原始数据 | `bench-data-20260328-140000.txt` | benchmark 工具的完整原始输出 |
| 火焰图 | `flamegraph-20260328-140000.svg` | |
| 剖析数据 | `callgrind-20260328-140000.out` | valgrind/perf 等产物 |
| 重构跟踪 | `refactor-tracker-<name>.md` | 渐进式重构的跨会话迁移状态跟踪（持久化，非一次性产物） |

时间戳使用该 skill 执行开始时的时间。

### 索引文件：INDEX.md

每次产出文件后，**必须**向 `.artifacts/INDEX.md` 追加一行。

若 `INDEX.md` 不存在，先创建并写入表头：

```markdown
# Artifacts Index

| 时间 | Skill | 摘要 | Commit | 文件 |
|------|-------|------|--------|------|
```

然后追加数据行。

**字段说明**：

- **时间**：`YYYY-MM-DD HH:MM` 格式
- **Skill**：触发的 skill 和上下文（如 `/bench profile`、`/refactor 基线`、`/evolve R3`）
- **摘要**：一句话描述内容（如"讨论 optimize 与 bench 是否重合"、"parse_token 性能剖析"）
- **Commit**：当前 HEAD 的 short hash（若与 commit 无关则 `—`）
- **文件**：文件名（不含路径前缀）

### Benchmark 数据专项规则

除通用规则外，benchmark 数据有额外要求：

- 原始输出使用 `tee` 捕获，不做裁剪，保存为 `bench-data-YYYYMMDD-HHMMSS.txt`
- 原始数据文件**头部必须包含复现上下文注释**（`#` 开头），然后是工具原始输出：
  ```
  # Reproduced: YYYY-MM-DD HH:MM
  # Commit: <hash> (clean/dirty)
  # Compiler: <version>
  # Build: <完整构建命令>
  # Bench: <完整 benchmark 命令>
  # Profile: <编译配置摘要>
  # ---
  <benchmark tool raw output>
  ```
- INDEX.md 中 benchmark 行额外记录关键指标（Mean、变化百分比）：
  ```
  | 2026-03-28 14:00 | /bench optimize R3 | parse_token: 89ns (-35%) | b7c8d9e | bench-data-20260328-140000.txt |
  ```
- 变化百分比从 INDEX.md 历史中查找同名 benchmark 的最近一条计算

### 适用 Skill

所有产生报告或数据文件的 skill：`/discuss`、`/review`、`/refactor`、`/improve`、`/fix`、`/evolve`、`/migrate`、`/ship`、`/debug`、`/test`、`/doc`、`/design`、`/retro`、`/bench`、`/merge`

### 标准输出流程

每个 skill 完成后，按以下流程输出产物（skill 本身**不需要**重复描述这些步骤，只需声明"按产物存储约定输出"）：

1. `mkdir -p .artifacts`
2. 将报告写入 `.artifacts/<skill>-YYYYMMDD-HHMMSS.md`（时间戳为 skill 执行开始时间）
3. 向 `.artifacts/INDEX.md` 追加一行记录（若 INDEX.md 不存在则先创建表头）
4. 输出确认消息：`✓ 报告已保存至 .artifacts/<filename>`

**Skill 内不应重复定义**：
- 不写 `mkdir -p .artifacts`（约定已定义）
- 不写文件命名规则（约定已定义）
- 不写 INDEX.md 追加逻辑（约定已定义）
- 不写输出确认消息格式（约定已定义）

**Skill 应该定义的**：
- 报告的内容结构（各 skill 的报告模板不同，这是 skill 特有的）

### .gitignore 建议

```gitignore
# Benchmark 原始数据和剖析产物（体积大、环境相关）
.artifacts/bench-data-*.txt
.artifacts/callgrind-*.out
.artifacts/massif-*.out
# 保留所有报告和索引
!.artifacts/*.md
!.artifacts/*.svg
```
