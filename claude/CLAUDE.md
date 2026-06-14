## Environment
- OS: WSL Arch Linux
- Editor: Neovim
- Build tools: xmake (C++), uv (Python)
- Shell: Nushell
- Primary languages: Rust, C++23
## Code Style
### Function Design
- **「函数即目录」**：每个函数只在同一抽象层级上做一件事，由一串自解释的命名调用组成，让人能自顶向下逐层下钻——读函数名即懂意图，要细节再进下一层
- 综合 Compose Method（组合方法）+ SLAP（单一抽象层级原则）+ Clean Code 的 Do One Thing & Stepdown Rule + Extract Function / SRP：代码读起来应像一份能层层展开的提纲
- `main` 及上层入口应是几行命名调用，而非一大坨实现细节
### Observability
- All non-trivial functions must include leveled logging: ERROR / WARN / INFO / DEBUG / TRACE
- Log all error branches, external I/O, and key function entry/exit points (at DEBUG level)
- Log messages must be **actionable**: include relevant context — variable values, function arguments, system state — not just "error occurred"
- Rust: use the `tracing` crate; annotate non-trivial functions with `#[instrument(err)]`
- C++: use spdlog with `SPDLOG_ACTIVE_LEVEL` for compile-time log filtering
### Comments
- Comment non-obvious logic, especially complex algorithms and critical decision points
- Explain **why**, not just **what** — the code already shows what; comments should reveal intent
- Keep comments close to the relevant code and updated when logic changes
### Testing
- Write tests for boundary conditions and error-handling paths, not just the happy path
- Prefer integration tests for I/O-heavy code; unit tests for pure logic
- Test names should describe the scenario: `test_parse_empty_input_returns_error`, not `test1`
- **After any code change, run all tests that cover the modified code and ensure they pass before considering the task complete**
### Benchmarking
- **Before modifying any code that has associated benchmarks, run the benchmarks first to establish a baseline**
- **After the modification, re-run the benchmarks and verify there is no performance regression compared to the baseline**
- If a regression is detected, investigate and resolve it before finalizing the change
### General Principles
- **Simple is best** — favor the simplest solution that works; resist over-engineering
- Avoid unnecessary abstractions; prefer explicit over clever
- Commit frequently with meaningful messages; treat git history as documentation
- Each commit should represent one logical change and be buildable independently
- Prefer composition over inheritance
- Prefer modern C++ features (concepts, ranges, std::expected, std::format, structured bindings, etc.) over legacy patterns
- Prefer header-only code style for C++ libraries when feasible
- Prefer compile-time driven development in C++ (constant evaluation, generic programming) to catch errors early and improve performance
- Prefer scripts that are **robust, observable, and idempotent**: handle errors explicitly, emit clear progress/status output, and produce consistent results when run multiple times — avoid side effects that accumulate or break on re-execution
