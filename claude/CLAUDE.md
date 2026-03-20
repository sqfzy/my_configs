## Environment
- OS: WSL Arch Linux
- Editor: Neovim
- Build tools: xmake (C++), uv (Python)
- Shell: Nushell
- Primary languages: Rust, C++23

## Code Style

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
- Avoid unnecessary abstractions; prefer explicit over clever
- Commit frequently with meaningful messages; treat git history as documentation
- Each commit should represent one logical change and be buildable independently
- Prefer composition over inheritance
- Prefer modern C++ features (concepts, ranges, std::expected, std::format, structured bindings, etc.) over legacy patterns
- Prefer header-only code style for C++ libraries when feasible
- Prefer compile-time driven development in C++ (constant evaluation, generic programming) to catch errors early and improve performance
