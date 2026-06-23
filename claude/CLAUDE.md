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
- **行数是结果而非判据**：编排函数理想 ≤5 行，多数函数舒适上限 ≤15~20 行，>40 行基本确定违反 SLAP。但真正的拆分信号是"同一函数混入了两种抽象高度的词汇"或"做了多件事"——超行数只是去查这个病因的提示。反之也别为压行数硬拆出只能连在一起读、共享隐式状态的碎片
- **扁平化代码，不要过早抽象**：遵循 YAGNI + Rule of Three（三次法则）+ "宁可重复，勿要错误的抽象"（Sandi Metz）。错误抽象的代价（特例分支、flag 参数、被 N 处绑死）远高于重复（线性、显式、可逆）。需要泛型 / trait / 接口 / 配置驱动的"万能函数"时，等共性出现第三次、真正稳定后再抽；发现抽错了，先内联回重复再重新提炼
- **区分两种"抽"**：为"读得懂 / 压平抽象层级"而抽函数——单次调用也尽管抽（即"函数即目录"，本地、廉价、可逆）；为"将来复用 / 消除重复"而抽通用抽象——延后到共性稳定（YAGNI）。警惕把后者伪装成前者：看到两段相似代码就急着抽一个带多个 bool 参数的"共用函数"，那不是 DRY，是过早抽象
### Observability
- All non-trivial functions must include leveled logging: ERROR / WARN / INFO / DEBUG / TRACE
- Log all error branches, external I/O, and key function entry/exit points (at DEBUG level)
- Log messages must be **actionable**: include relevant context — variable values, function arguments, system state — not just "error occurred"
- Rust: use the `tracing` crate; annotate non-trivial functions with `#[instrument(err)]`
- C++: use spdlog with `SPDLOG_ACTIVE_LEVEL` for compile-time log filtering
### Naming
- **默认拼全名**：只允许领域内人人秒懂、无歧义的通用缩写（`id` / `url` / `ctx` / `cfg` / `req` / `db` 等），且一旦采用就全代码库一致——绝不自创只有自己当下懂的简写
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
