# Rust 项目初始化工作流

这个工作流将创建一个新的 Rust 项目，配置好依赖和日志，并验证构建。
以下每个步骤会依次传给 Claude Code 执行。

## Step 1: 创建项目结构

使用 `cargo new my-app --bin` 创建一个新的 Rust 二进制项目。
然后进入目录，查看初始文件结构并输出给我看。

## Step 2: 添加依赖

编辑 `my-app/Cargo.toml`，在 `[dependencies]` 下添加以下依赖：
- tracing = "0.1"
- tracing-subscriber = { version = "0.3", features = ["env-filter"] }
- anyhow = "1"

## Step 3: 重写 main.rs

将 `my-app/src/main.rs` 改写为以下内容：
- 初始化 tracing-subscriber，支持 RUST_LOG 环境变量，默认 INFO
- 写一个带 `#[instrument(err)]` 的示例函数 `do_work(name: &str) -> anyhow::Result<()>`
  - 函数内用 tracing::info! 打印 "Processing {name}"
  - 函数内用 tracing::debug! 打印 "Detailed work for {name}"
  - 正常返回 Ok(())
- main 函数调用 do_work("hello")，处理错误并用 tracing::error! 打印

## Step 4: 验证构建

在 `my-app/` 目录下运行 `cargo build`。
如果失败，阅读错误信息并修复，然后重新构建直到成功。
最后输出构建成功的确认信息。
