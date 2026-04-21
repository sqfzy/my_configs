## 生产级代码标准

> **铁律：任何修改/新增的代码，必须达到可直接上线运行的生产级别，而不是"能跑通的 demo"。**

"能编译、能跑通 happy path"只是起点，远不是终点。生产级代码必须假设它会在**不理想的环境**下运行：边界输入、并发、I/O 失败、恶意输入、长时间运行、维护者换人。编码时对以下每一维度都要主动考虑，不能依赖"以后再补"。

### 正确性与边界

- **边界条件全覆盖**：空输入 / 单元素 / 最大容量 / 整数溢出 / 越界索引 / 零除 / NaN / 负数 / 空指针 / 已关闭的 channel 或 socket
- **错误处理不得吞没**：禁止裸 `unwrap()` / `expect()`（除非有证明不会 panic 的不变量）；禁止空 `catch {}` 或 `except: pass`；禁止忽略 `Result` 而不加 `_ =`
- **错误类型要精确**：返回具体 error 类型让调用方能判别处理，不要一律 `Box<dyn Error>` / `anyhow::Error` 作为公共 API（内部可用）；不要用 `String` 当 error
- **错误信息可操作**：写清楚"发生了什么 + 相关上下文 + 对用户意味着什么"，而不是 `"error"` 或 `"failed"`
- **前置条件显式**：所有 invariant、契约、不变量用 `assert` / `debug_assert` / `static_assert` / 类型系统锁死，不要靠注释约定

### 并发与资源

- **并发安全显式**：共享状态必须标注 `Send + Sync` / 加锁 / 用 channel / 用原子；不要"默认单线程所以不管"
- **资源必释放**：文件/socket/锁/GPU 内存等所有获取都有对应释放路径（含错误路径）；Rust 用 RAII，C++ 用智能指针，Python 用 `with`
- **不泄漏 goroutine / task / 线程**：所有后台任务有明确的取消机制（cancellation token / context / drop guard）
- **超时与重试**：所有外部 I/O（网络、DB、子进程）必须有超时；幂等操作加指数退避重试；非幂等操作明确标注不可重试
- **背压**：无界 queue / channel 是 bug，必须有容量限制或丢弃策略

### 可观测性

- **结构化日志**：关键路径（函数入口/出口、错误分支、外部调用、状态转移）必须打日志；日志是**结构化字段**而非拼接字符串；级别准确（ERROR/WARN/INFO/DEBUG/TRACE）
- **日志内容可操作**：包含相关 ID、参数、状态、耗时；不要只写 `"something happened"`
- **Rust**：非 trivial 函数用 `#[instrument(err)]`；C++ 用 `spdlog` + `SPDLOG_ACTIVE_LEVEL` 控制
- **metrics/tracing**：热路径和关键业务操作应有耗时、QPS、错误率埋点（若项目已有观测体系）
- **Debuggability**：出问题时，通过日志 / dump / core 应能复现或定位

### 安全

- **所有外部输入视作不可信**：命令行参数、环境变量、HTTP body、文件内容、DB 读取——全部校验类型、长度、格式、范围
- **禁止命令注入**：拼接 shell 命令的 subprocess 调用必须用参数数组形式，不要 string concatenation
- **禁止路径穿越**：处理用户提供的文件名/路径时必须 canonicalize 并检查是否逃出白名单目录
- **敏感信息不落日志**：密码、token、session id、PII 必须 redact；错误信息不要泄漏内部路径 / 堆栈 / SQL 语句
- **依赖新增需审视**：不引入有已知 CVE 或长期无人维护的包；新依赖必须有清晰的用途说明

### 性能

- **复杂度有意识**：循环内的 O(n) 操作会变 O(n²)，要写出来意识到；大数据集上的 clone / collect 要问"必要吗"
- **热路径零分配**：能用 `&str` 就别 `String`；能用迭代器就别 intermediate `Vec`；C++ 能用 string_view 就别 string
- **I/O 批量化**：循环内 N 次查询是 bug，应改为一次批量查询
- **Cache 正确性**：引入缓存必须同时设计失效策略，否则就是在制造 bug
- **不过度优化**：没有 benchmark 证据就不做影响可读性的"优化"——但也不写明知低效的代码

### 可维护性

- **命名准确传意图**：`normalize_path` > `do_thing`；`user_id` > `uid` > `x`；名字骗不了人
- **函数职责单一**：一个函数超过 ~50 行或做了多件事，就该拆
- **抽象层级一致**：同一函数内不要混杂"业务概念"和"字节偏移"
- **注释解释 why 而非 what**：代码写什么自明；注释讲为什么这样写、为什么不用另一种、隐藏约束、历史坑
- **禁止复制粘贴**：两处一模一样的逻辑，抽成函数；三处还没抽就是技术债
- **禁止死代码**：注释掉的旧代码、永不调用的函数、永远 false 的 feature flag——删除，让 git 做记忆

### 测试

- **修改代码必须配测试**：新增功能有正向+反向测试；修 bug 必有回归测试锁定该 bug
- **测试覆盖边界和错误路径**，不只是 happy path
- **测试名称描述场景**：`parse_empty_input_returns_error` > `test1`
- **测试必须独立**：不依赖执行顺序、不依赖外部服务（除非是明确的集成测试）

### 文档

- **公共 API 必须有文档注释**：说明参数、返回值、错误条件、panic 条件、使用示例
- **非 trivial 函数需 doc comment**：调用方不看实现也能正确用
- **示例代码可运行**：Rust 的 doctest、Python 的 doctest、Go 的 Example 必须真的能跑

### 语言专项

**Rust**：
- 非 trivial 函数加 `#[instrument(err)]`（若用 `tracing`）
- 公共 API 考虑 `#[must_use]`、实现 `Debug`/`Clone` 等 derive 是否合理
- `unsafe` 块必须有 `// SAFETY:` 注释说明不变量
- 错误类型用 `thiserror` 定义；应用层用 `anyhow`
- clippy warning 必须处理，不能 `#[allow]` 了事（除非有明确理由）

**C++**：
- 用 RAII 而非手动 new/delete
- 模板边界用 C++20 concepts，不用 SFINAE
- 优先 `std::expected` / `std::optional` 而非 out-param + return code
- 用 `std::format` / `std::println` 而非 printf
- 生命周期不明确时用智能指针，不要裸 `T*` owner

**Python**：
- 类型注解必须加（非 trivial 函数）
- 用 `pathlib.Path` 而非 `os.path` 字符串拼接
- 禁止 `except Exception: pass`；捕获要具体
- 用 `dataclass` / `pydantic` / `attrs` 表达数据结构，不要裸 dict

### 反模式（必须拒绝）

- ❌ "TODO: 后面再处理错误" / "FIXME: 先这样" —— 不要提交这种代码
- ❌ "这里先假设输入合法" —— 假设会被现实打脸
- ❌ "panic/abort 算了反正不会发生" —— 会发生
- ❌ "打个 log 就好不用具体处理" —— log 不是处理
- ❌ "这段逻辑复杂我 copy-paste 一下" —— 抽函数
- ❌ "测试回头补" —— 不会补的

### 判定标准

写完一段代码后自问：
1. 如果这段代码明天就上生产，我敢睡觉吗？
2. 如果 6 个月后别人来改这段代码，他能看懂吗？
3. 如果 QA 拿着 fuzzer 来打，能撑住吗？
4. 如果 oncall 凌晨 3 点被这段代码叫醒，从日志能定位问题吗？

任何一个答案是"不能"，都没达到生产级别，必须继续打磨。

### 适用 skill

所有修改或新增代码的 skill：`/design`、`/fix`、`/refactor`、`/improve`、`/cleanup`、`/migrate`、`/evolve`、`/ship`、`/merge`（port 模式）。
