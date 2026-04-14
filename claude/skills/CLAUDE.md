# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A personal collection of Claude Code **custom skills** (slash commands). Each top-level directory is one skill; there is no build, no tests, no runtime. "Working on the codebase" means editing prompt/workflow definitions in Markdown — changes take effect the next time Claude Code loads the skill.

## Repository layout

```
<skill-name>/SKILL.md     # One directory per skill; SKILL.md is the whole skill
shared/                   # Reusable modules referenced by multiple skills via `!`cat`` in frontmatter
```

Current skills cluster around end-to-end workflows (`design`, `fix`, `ship`, `refactor`, `improve`, `evolve`, `migrate`, `cleanup`), analysis (`review`, `debug`, `test`, `bench`, `discuss`), planning (`blueprint`, `coach`), long-running orchestration (`autopilot`, `repeat`), and scaffolding (`git`, `doc`, `report`, `retro`, `merge`, `script`, `create-agent`).

## SKILL.md anatomy

Every skill is a single Markdown file with YAML frontmatter:

```yaml
---
name: <skill-name>                    # Must match directory name
description: "<trigger text>"         # Starts with a short purpose, then "TRIGGER when: ... DO NOT TRIGGER when: ..."
argument-hint: "<args> [flags]"       # Shown in the / menu
allowed-tools: Bash(cmd:*), ...       # Whitelist of tools; bash is restricted per-command
---
```

The body contains inline bash via `` !`command` `` in frontmatter-adjacent lines (used to inject live context like date, git branch, file listings, or the contents of shared modules at skill-load time), followed by the prompt that Claude executes. The body is a **prompt**, not code — edits are prose edits to Claude's instructions.

Conventions observed across skills:
- Body uses Chinese + English mix; final line is usually `输出语言跟随用户输入语言`
- Workflows are structured as `Phase 0..N` with explicit user-confirmation gates between phases
- Almost every skill has an `[auto]` mode that suppresses confirmations and picks conservative defaults
- Mode inference table: if the user doesn't pass a flag, the skill infers mode from keywords in the prompt and prints `▶ 推断模式：<mode>`

## Shared modules (the contract between skills)

Skills pull shared behavior by `cat`-ing files from `shared/` in their frontmatter. When editing these, every dependent skill picks up the change automatically — treat them as load-bearing APIs:

- **`shared/artifacts.md`** — The **"铁律"** for report output. All skills that produce reports MUST: (1) write to `.artifacts/<skill>-YYYYMMDD-HHMMSS.md`, (2) append one row to `.artifacts/INDEX.md` with a strict 5-column schema, (3) emit `✓ 报告已保存至 .artifacts/<filename>`. Skills reference this as "按产物存储约定输出" and do **not** redefine the mkdir/naming/index logic themselves.
- **`shared/build-detect.md`** — Priority chain for resolving build/test/bench/lint commands: user override → CLAUDE.md declaration → auto-detection from `Cargo.toml` / `xmake.lua` / `pyproject.toml` / `package.json` / `go.mod` / `Makefile`. Skills reference this as "按构建命令获取策略执行".
- **`shared/roles.md`** — The R1–R14 role library (风险卫士, 极简主义者, 性能狂热者, ...) used by any skill that does multi-role adversarial discussion. Also defines the `┌─ ... ─┐` box-drawing format for round-by-round debate output.
- **`shared/bench-aware.md`** — Baseline-check protocol. Any skill that modifies code first checks `.artifacts/INDEX.md` for a bench baseline, runs bench before edits if needed, then compares after. Defines regression thresholds (5% / 15%). Skills reference this as "按 Bench 感知约定执行".
- **`shared/blueprint-aware.md`** — Detection of active `blueprint-*.md` files in `.artifacts/`. If found, the skill treats the blueprint's decisions as **constraints** and skips re-discussing already-decided dimensions. This is how `/blueprint` (plan-only) hands off to `/design` (plan + implement).
- **`shared/autopilot-aware.md`** — Detection of running `/autopilot` sessions via `.artifacts/autopilot-state-*.json`. Any workspace-modifying skill should check this to avoid racing with an autopilot that's looking after a background task. Pure read-only skills can ignore it.
- **`shared/autopilot-classifier.sh`** — Deterministic event classifier consumed by `/autopilot`'s wakeup loop. Reads `.artifacts/autopilot-state-<task>.json` + log tail, emits a single JSON `{severity, category, suggested_action, evidence}`. **No LLM in the loop** — this is the load-bearing primitive that keeps per-wakeup context at ~200 lines. When editing, preserve the JSON schema since the skill's decision tree depends on it.

## Skill interaction graph

Skills call each other by design — when editing one, check what delegates to it:

- `/design` reads `blueprint.md` if present (via `blueprint-aware`); skips requirement re-clarification
- `/fix` is the orchestrator for `/debug` → `/test` → `/git` as a single pipeline
- `/ship` delegates Gate 1 to `/review auto` (expected, not a bug)
- `/refactor [breaking]` and `/cleanup` overlap in scope — `/cleanup` is the holistic "rethink from scratch" version, `/refactor` is targeted
- `/evolve` drives iterative `/discuss` → `/design` cycles autonomously

## When editing skills

- **Mirror existing phase structure.** All multi-phase skills follow `Phase 0 检测 → Phase 1 理解 → Phase 2 设计 → ... → Phase N 报告`. Keep new skills isomorphic for consistency.
- **Do not inline what a shared module already defines.** If you catch yourself writing `mkdir -p .artifacts` or redefining the INDEX.md schema in a skill, stop — reference `shared/artifacts.md` instead.
- **Keep `allowed-tools` minimal.** Each bash pattern must be justified; skills default to deny. Add only the exact subcommands the workflow runs.
- **Argument parsing is prose, not code.** Flags like `[auto]`, `[no-commit]`, `[deep]`, `[target: <path>]` are extracted by Claude reading the prompt, so describe them in a parameter table and let inference rules be explicit.
- **Every artifact-producing skill's `argument-hint` should list `[auto]`** if the workflow has user-confirmation gates — otherwise non-interactive use is impossible.
- `git status` currently shows untracked `blueprint/`, `coach/`, and `shared/blueprint-aware.md` — these are the newest additions and still in flight.

## Testing a skill change

There is no test harness. Validation is manual:
1. Reload Claude Code so the skill cache picks up edits
2. Invoke the skill with a representative prompt (include `[auto]` to exercise non-interactive paths)
3. Verify it produces `.artifacts/<skill>-*.md` and the INDEX.md row matches the shared schema

## Commit style

`git log` shows the commit history is uniformly `update` — the user commits frequently without ceremony on this repo. Don't invent Conventional Commit scopes here unless the user asks.
