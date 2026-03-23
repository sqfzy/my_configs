## 构建/测试/Benchmark 命令获取策略

按以下优先级获取构建、测试、Benchmark 命令：

### 优先级 1：用户显式提供

若用户在参数或对话中直接提供了命令，使用该命令。

### 优先级 2：CLAUDE.md 声明

检查项目的 CLAUDE.md 或 ~/.claude/CLAUDE.md 中是否声明了构建工具（如 `Build tools: xmake (C++), uv (Python)`）。若有，据此推断命令。

### 优先级 3：自动检测构建文件

根据项目根目录的构建配置文件推断：

| 构建文件 | 语言/工具 | 构建命令 | 测试命令 | Benchmark 命令 |
|----------|-----------|----------|----------|----------------|
| `Cargo.toml` | Rust | `cargo build --release` | `cargo test` | `cargo bench` |
| `xmake.lua` | C++ (xmake) | `xmake build -y` | `xmake run -g test` | `xmake run -g bench`（若有） |
| `CMakeLists.txt` | C++ (CMake) | `cmake --build build --config Release` | `ctest --test-dir build` | 视项目而定 |
| `pyproject.toml` | Python (uv) | `uv sync` | `uv run pytest` | `uv run pytest --benchmark`（若有） |
| `requirements.txt` | Python (pip) | `pip install -r requirements.txt` | `pytest` | 视项目而定 |
| `package.json` | Node.js | `npm install && npm run build` | `npm test` | `npm run bench`（若有） |
| `go.mod` | Go | `go build ./...` | `go test ./...` | `go test -bench=. ./...` |
| `Makefile` | Make | `make` | `make test` | `make bench`（若有） |

### Lint / 静态检查命令

| 构建文件 | Lint 命令 |
|----------|-----------|
| `Cargo.toml` | `cargo clippy -- -D warnings` |
| `xmake.lua` | 视项目而定（clang-tidy 等） |
| `pyproject.toml` | `uv run ruff check .` |
| `package.json` | `npm run lint`（若有） |
| `go.mod` | `go vet ./...` |

### 使用方式

在 skill 中引用此模块的标准措辞：

```
根据构建命令获取策略（用户提供 > CLAUDE.md 声明 > 自动检测），确定并执行构建/测试/Benchmark 命令。若项目无测试或 Benchmark 则跳过对应步骤。
```

### 注意事项

- 始终以 release/优化模式运行 Benchmark（debug 模式数据无意义）
- 构建失败时输出完整错误信息，不静默吞掉
- 若检测到多个构建文件（如 Cargo.toml + Makefile），优先使用语言原生工具（cargo > make）
- 命令执行结果应 tee 到 `.discuss/` 中供后续引用（仅在需要对比时）
