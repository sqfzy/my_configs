# Mode: repro

**精确复现报告** —— 把一次现象 / 一次构建 / 一次性能数据 / 一次环境状态 / 一次故障情境**封装成可粘贴执行的配方**，让任何读者照着跑就能得到同一结果。

---

## 与相关 mode 的边界

| 你在做什么 | 去哪里 |
|-----------|-------|
| 描述发现了一个 bug，发给同事调查（粗粒度，含建议调查方向） | `issue` |
| 已发生的事故复盘，含时间线 + 根因 + 影响 | `incident` |
| 有假设的对照实验，要 p-value / CI / effect size | `experiment` |
| **把"怎么精确做到 X"封装成可执行清单**，任何读者照跑就重现 | **本 mode** |

**判据**：你的目标是不是"让一个不熟悉这件事的人，在不问你任何问题的前提下，照着这一份 md 跑出和你一样的结果"？是 → repro。

**铁律**：repro 是**一份配方**，不是**一份故事**。读者不需要知道你怎么发现的，只需要照着步骤跑。背景介绍多于半屏 = 跑偏到 incident / decision 去了。

---

## 必含章节

### 1. 复现目标（1-3 句）

复现**什么**？必须可一句话讲清，且与读者通过"验证"判定的产物**精确对应**。

- ✓ "在 commit abc1234 上跑 `cargo test poller` 时 `test_poller_collision` 偶发 panic（`thread 'tokio-runtime-worker' panicked at ...`）"
- ❌ "poller 有时候会出问题"

### 2. 环境锁定（精确到能让两台不同机器输出相同结果的最小集合）

```
OS                : <Ubuntu 22.04 / macOS 14.2 / Arch ...>
内核              : 6.6.x
工具链            : rustc 1.78.0 / cargo 1.78.0 / clang 17.0.6 / xmake 2.9.2
关键依赖版本      : tokio 1.36.0（来自 Cargo.lock）/ DPDK 24.11
硬件相关项（若依赖）: x86-64 / AVX2 / 8C16T / 16GB / NIC 型号
关键环境变量      : RUSTFLAGS=... / RUST_LOG=... / LD_LIBRARY_PATH=...
```

不依赖某项时**显式标 N/A** —— 帮读者省事。

### 3. 代码状态

- **Commit hash**：精确到 SHA（`abc1234567890`），不是 `main`
- **clean / dirty**：clean = 工作树干净；dirty = 列出未提交的关键 patch（`git diff` 内联粘贴）
- **私有依赖 / 子模块版本**：若涉及

### 4. 输入与数据

- 命令行参数 / stdin 内容 / 配置文件（**完整内容内联**或精确路径 + 哈希）
- 数据集：路径 + 大小 + sha256 + 来源（生成命令 / 下载 URL）
- 随机种子（若涉及）：列出每个种子值

### 5. 复现步骤（**编号 + 可粘贴执行**）

```
$ git checkout abc1234
$ export RUST_LOG=trace
$ cargo build --release
$ ./target/release/foo --bar 42 < input.txt 2>&1 | tee run.log
```

每步**附预期观察**：

```
$ cargo build --release
   Compiling foo v0.1.0
    Finished `release` profile [optimized] target(s) in 23s
# 预期: 0 warnings, 0 errors。若看到 deny(warnings) 触发 → 工具链版本不一致
```

### 6. 预期产物

- **命令输出**：关键行（精确文本或 grep pattern）+ 大小数量级（行数）
- **文件产物**：路径 + sha256（若可重现）
- **退出码**：明确给出（`echo $?` 应该是几）
- **现象**（如 panic / segfault）：完整 stack trace 关键帧

### 7. 验证（成功判据）

**精确的可观察判据**，不是"看起来对了":

```
✓ run.log 含 "panicked at 'reasm overflow'"
✓ 退出码 = 134（SIGABRT）
✓ /tmp/out.bin sha256 = e3b0c44...
```

### 8. 不需要相同的

帮读者省精力：**明确列出无关项**

- 用户名、机器名、工作目录路径
- OS minor 版本（22.04 ≈ 22.04.3）
- 屏幕 / 终端 / 编辑器
- shell（bash / zsh / fish 都行）

### 9. 已知干扰因素

需要避开 / 注意的：

- "另开 cargo 进程会让本测试因 IO 抖动 flake，跑前 `pkill cargo`"
- "首次跑前先 `cargo clean`，否则 incremental 缓存会跳过编译错误"
- "防止 OOM kill：`ulimit -m` 设 8GB+"
- 系统时间 / 时区 / locale 是否敏感

---

## 读者画像

- 工程师 / SRE / 维护者，**愿意动手照着跑**
- **不愿猜** —— 任何"按你的环境调整..."都是失败
- 假设读者**不熟悉项目背景**（自包含；该交代的环境/版本/数据都列全）

---

## 铁律

- **可粘贴可执行**：每条命令一行（必要时多行 here-doc），复制即跑。禁占位符 `<your-token>` 出现而不交代获取方式。
- **每步可验证**：每个关键步骤给"成功 / 失败"的具体观察，不是"应该可以"
- **环境前置**：环境锁定章节走在最前；不让读者跑到第 5 步才发现缺工具
- **一份配方一份报告**：不同复现目标分开存；不要把"跑测试" + "构建镜像" + "导出 profile" 三件事塞一份
- **决定性优先**：能用具体哈希 / 版本号就不写"latest" / "main" / "现在"

---

## ASCII / 可视化要求

- **命令序列**：`$ cmd` + 输出，模拟终端；输入 / 输出区分明确（不要 REPL 风格混淆）
- **diff 内联**（若有未提交 patch）：标准 unified diff
- **时序图**（若涉及多个进程 / 服务交互）：ASCII sequence diagram
- **状态机** / **流程**（若复现需要触发特定状态）：ASCII

---

## 反模式（任一命中即不合格）

- ❌ "在你的环境调整..." / "根据你的实际情况..." —— 推卸责任
- ❌ 占位符 `<your-token>` / `<your-path>` 而无获取说明
- ❌ 只给"总览"不给逐步命令（"安装依赖、构建、运行"）
- ❌ 没列 commit hash / 用 `main` / 用 "最新版"
- ❌ 验证语模糊：`"看看是不是这样"` / `"应该会输出..."`
- ❌ 假定读者已知项目（缺自包含上下文）
- ❌ 命令输出和命令未区分（混在一起读者分不清谁是谁）
- ❌ 把多个不相关 repro 塞同一份
- ❌ 包含主观叙述（"我当时尝试..."、"我觉得是..."）—— 那是 incident / decision 该有的
- ❌ 让读者去看 git log / 看 README / 看代码才能跑（违反§2.7 自包含）

---

## auto 模式

- 缺关键信息（commit hash / 工具链版本 / 数据集哈希）→ 先尽力主动获取（`git rev-parse HEAD` / `rustc --version` / `sha256sum`），仍缺则在对应字段标 `[待补充：<具体>]`
- 不需要相同的 / 已知干扰因素：无信息时省略整节，不强凑

---

## 报告骨架

```markdown
# Repro: <一句话目标>

Commit: <hash> · Captured at: <YYYY-MM-DD HH:MM Z>
Author: <谁记的>

## 复现目标
<1-3 句，含期望观察的具体现象>

## 环境锁定
<OS / 内核 / 工具链 / 依赖 lock / 硬件 / env vars>

## 代码状态
- Commit: <hash>
- 工作树: clean | dirty + diff
- 子模块 / 私有依赖: <若涉及>

## 输入与数据
<命令行 / stdin / 配置文件 / 数据集 + 哈希 + 种子>

## 复现步骤
1. `$ <cmd>` ← 预期: ...
2. `$ <cmd>` ← 预期: ...
...

## 预期产物
- 命令输出: ...
- 文件: <path> sha256=...
- 退出码: ...
- 关键现象: ...

## 验证
✓ <可观察判据 1>
✓ <可观察判据 2>

## 不需要相同的
- ...

## 已知干扰因素
- ...
```

---

## 集成

- **输入**：用户给一次现象 / 一次成功跑的命令 / 一次环境快照
- **输出衔接**：
  - 复现确认了一个 bug → 配 `/report issue` 发同事调查
  - 复现是一次实验跑数据 → 配 `/report experiment` 做完整实验报告
  - 复现是一次故障重演 → 配 `/report incident` 写完整事故报告
- repro 经常作为 issue / incident / experiment 的**附件**被引用：那些 mode 的"复现步骤"章节如果很长，单独存 repro 后引用文件名。
