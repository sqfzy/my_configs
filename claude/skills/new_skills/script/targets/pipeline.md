## Target：pipeline（数据处理管道 / 批处理）

**适用**：处理数据集、ETL 任务、批量转换、定期作业。典型例子：日志分析、数据清洗、批量重命名、文件格式转换、从 API 抓数据。

**与普通 task 的核心差异**：pipeline **处理的是真实数据**——一旦错了可能损坏业务资产。必须具备**dry-run + 幂等 + 失败恢复 + 进度可见 + 原子切换**。

---

### 独有的必执行章节

#### 1. 输入 / 输出契约

脚本开头显式定义：

```
# Input:
#   - Source:  <文件 / 目录 / DB / API>
#   - Format:  <JSON / CSV / Parquet / ...>
#   - Schema:  <关键字段 + 约束>
#   - Size:    <预估量级，用于进度估计>
#
# Output:
#   - Target:  <目标位置>
#   - Format:  <...>
#   - Schema:  <...>
#   - Overwrite policy: <fail / skip / overwrite>
#
# Side effects:
#   - Creates: <...>
#   - Modifies: <...>
```

**原则**：读者不读代码也能知道"喂给它什么 / 它吐出什么"。

#### 2. Dry-run 模式（强制）

任何 pipeline 必须支持 `--dry-run`：
- 读取输入（或输入的样本）
- 模拟处理流程
- 打印"会产出什么"（记录数 / 文件名样本 / 变更摘要）
- **不写入任何目标**

Dry-run 输出必须**有代表性**——不只是"会写 N 条记录"，还要给几条样本的前后对比。

#### 3. 幂等 + 检查点

长 pipeline 必须支持**断点续传**：
- 处理单元化（每条记录 / 每个文件 / 每个批次独立可恢复）
- 记录已完成单元（到状态文件 / DB 表 / 文件系统标记）
- 失败重启时**跳过已完成**，只处理剩余

**幂等性铁律**：每个单元的处理必须幂等——同一条记录处理两次结果相同。

#### 4. 进度可见

pipeline 经常跑很久，必须有进度：

```
Processing records... 1,247 / 10,000 (12.47%) [ETA: 5m 32s]
```

要素：
- 已完成 / 总数
- 百分比
- 预估剩余时间（基于已处理速率）
- 当前正在处理的单元标识（文件名 / 记录 ID）
- 错误计数（"12 errors so far, see .pipeline-errors.log"）

长 pipeline 建议**每分钟心跳**，让监控 / 用户知道它没死。

#### 5. 错误路径隔离

单条记录失败**不中断整个 pipeline**（除非用户显式 `--strict`）：
- 失败记录写入单独的错误文件 / DLQ
- 继续处理剩余
- 结束时汇总错误统计
- 提供"重跑失败项"的子模式

```
Processing complete.
  Total:     10,000
  Success:   9,987
  Failed:    13 (see .pipeline-errors.log)

Re-run failed records: ./pipeline.sh --retry-failed
```

#### 6. 原子切换（若写入目标有一致性要求）

若 pipeline 输出是一个数据集（不是追加日志），应**原子切换**：
- 写到临时位置 / 临时表
- 全部完成后 atomic rename / switch
- 失败时临时位置可清理，目标位置不受影响

```
target/         # 旧数据
target.new/     # 正在写
↓ 完成后 ↓
target.old/     # 旧数据（备份）
target/         # 新数据（rename from target.new）
```

#### 7. 资源约束

- 内存：不允许全量加载大数据集，用 streaming / 分批
- 并发：显式 `--parallel N` 控制
- 速率：若访问外部 API / DB，限速（避免打挂下游）

---

### 独有的维度权重

| 维度 | 权重 | 原因 |
|------|------|------|
| Dry-run | **极高** | 数据错了很难恢复 |
| 幂等 | **极高** | pipeline 重跑是日常 |
| 进度 | **极高** | 长时运行必须可见 |
| 错误隔离 | **高** | 不能因一条错记录丢整个任务 |
| 资源约束 | **高** | 大数据集必须 streaming |
| 原子切换 | **高** | 输出一致性 |

---

### 独有的 ASCII 图示要求

- **数据流图**：Source → 处理阶段 → Target，标出每个阶段的转换
- **失败处理流**：错误记录往 DLQ 的路径

---

### 独有的反模式

- ❌ 没有 dry-run
- ❌ 全量加载到内存（`cat huge.csv | ...`）
- ❌ 一条错记录就 exit 1
- ❌ 没有进度输出
- ❌ 没有 ETA 预估
- ❌ 直接写目标位置（失败时脏数据半成品）
- ❌ 无限制并发打爆下游
- ❌ 失败不记录具体哪条记录错了
- ❌ 重跑时不跳过已完成
- ❌ 处理 PII / 敏感数据不 redact 日志

---

### pipeline 脚本骨架模板

```python
#!/usr/bin/env python3
"""
Pipeline: <source> → <target>

Input:
  Source:  s3://bucket/raw/
  Format:  JSON Lines
  Schema:  {id: str, value: int, ...}

Output:
  Target:  postgres://host/db.table
  Schema:  (id TEXT, normalized_value REAL, ...)
  Overwrite: atomic-switch via staging table

Usage:
  ./pipeline.py [--dry-run] [--parallel N] [--retry-failed] [-v]
"""

import argparse
import logging
import sys
from pathlib import Path

STATE_FILE = Path(".pipeline-state.json")
ERROR_FILE = Path(".pipeline-errors.log")

def main():
    args = parse_args()
    logging.basicConfig(...)

    if args.dry_run:
        log.info("DRY RUN — no writes will be performed")

    source = open_source(args.source)
    target = open_target(args.target, staging=not args.dry_run)

    state = load_state()
    total = count_records(source)

    log.info(f"Processing {total} records (resuming from {state.done})")

    success, failed = 0, 0
    for i, record in enumerate(stream(source)):
        if record.id in state.done:
            continue  # idempotent skip

        try:
            transformed = transform(record)
            if not args.dry_run:
                target.write(transformed)
            state.mark_done(record.id)
            success += 1
        except Exception as e:
            log_error(record, e)
            failed += 1
            if args.strict:
                raise

        if i % 1000 == 0:
            print_progress(i, total, success, failed)

    if not args.dry_run:
        target.atomic_switch()

    log.info(f"Done. Success: {success}, Failed: {failed}")
    if failed > 0:
        log.info(f"See {ERROR_FILE}. Retry: ./pipeline.py --retry-failed")

if __name__ == "__main__":
    sys.exit(main() or 0)
```
