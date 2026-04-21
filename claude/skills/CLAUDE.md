# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Personal Claude Code skill definitions. `~/.claude/skills` is a symlink to this directory, so edits here change live behavior for the user's Claude Code sessions. Files are Markdown with YAML frontmatter — there is no build / test / lint pipeline. Changes ship simply by committing.

## Architecture: three skills, one pattern

Three skills live at the top level (`pax/`, `report/`, `script/`). They share a common shape that must be preserved when editing:

```
<skill>/
├── SKILL.md              ← frontmatter + common skeleton (the shared flow,
│                           Phase 0..N, shared constraints, --auto semantics)
└── <variants>/           ← one file per variant; ONLY variant-specific content
    └── <name>.md
```

- `pax/purposes/` — 10 purposes: `feat, fix, reshape, upgrade, review, test, bench, doc, ship, loop`
- `report/modes/` — 7 modes: `decision, status, incident, issue, release, retro, experiment`
- `script/targets/` — 3 special targets: `setup, wizard, pipeline` (other script targets use only SKILL.md)

`shared/ascii-viz.md` is included by all three SKILL.md files via the frontmatter `!cat ~/.claude/skills/shared/ascii-viz.md` directive — treat it as a cross-skill contract.

### The skeleton/variant split is load-bearing

SKILL.md files define the **common skeleton**: flow phases, mandatory maneuvers (e.g. `EnterPlanMode` in pax Phase 0, `.artifacts/INDEX.md` update in report Phase 5), generic dimensions, `--auto` semantics, anti-patterns. Each variant file (`purposes/<p>.md`, `modes/<m>.md`, `targets/<t>.md`) contains **only what is unique** to that variant: extra mandatory sections, extra ASCII diagram requirements, extra traps, extra reporting fields.

When editing:
- **Do not duplicate skeleton content into variant files.** If you find yourself writing generic guidance inside a variant, it belongs in SKILL.md.
- **Do not weaken a variant by moving unique constraints into SKILL.md.** The whole point of the split is that, say, `fix` forces a root-cause section but `feat` does not.
- Each SKILL.md has an inference table (keywords → variant) and a dispatch step that reads the variant file. **Adding a new variant requires updating both the inference table and the dispatch comment in the parent SKILL.md.**

## Inter-skill boundaries (enforced, not stylistic)

```
/pax ── plans & constructs ──▶ in-session only, no disk writes
/report   ── persists artifacts ──▶ the ONLY skill that writes .artifacts/
/script   ── generates one file  ──▶ single-file programs; multi-file → /pax --feat
```

- `/pax` products (plans, construction logs, review findings) **never** auto-persist. Users must explicitly call `/report` to save anything.
- `.artifacts/INDEX.md` at repo root has a 5-column schema (`时间 | mode | 摘要 | Commit | 文件`) and must be appended on every `/report` write.
- When editing, do not add disk-write behavior to pax or script. Do not introduce a fourth persistence path — route everything through `/report`.

## The `--auto` contract (shared across all three skills)

`--auto` has identical semantics everywhere: full autonomy, never stop to ask the user, handle exceptions as "warn + continue", only stop on physical impossibility (cannot write disk, cannot compile, user interrupt). When modifying a SKILL.md, the `--auto` section must remain consistent with the other two — divergence here is a bug.

## Production-grade non-negotiables

Two skeletons enforce explicit production dimensions that must survive edits:

- **pax**: the "生产级 8 维度" (correctness & boundaries / concurrency & resources / observability / security / performance / maintainability / test strategy / docs). Every plan must address all 8; small topics may merge items but cannot skip any. Phase 3 self-check iterates them explicitly.
- **script**: the "8 条生产级原则" (error handling / logging / idempotency / dry-run / input validation / path & command safety / confirmation / progress). These are bottom-line rules; variants reweight but cannot drop them.

If an edit reduces either list, that is a semantic regression — flag it, don't make it silently.

## Writing style conventions (observable in all skill files)

- Primary language is Simplified Chinese; frontmatter `description` fields are also Chinese. Keep new content in Chinese unless the user writes in English.
- ASCII diagrams over prose for structure, flow, and comparison — `shared/ascii-viz.md` is the authority. "Can't draw it" is treated as "haven't thought hard enough."
- Tables for decision matrices and inference rules.
- Each SKILL.md ends with `输出语言跟随用户输入语言。` — preserve this line.

## Commit convention

History is currently flat (`update`, `update`, `update`). The user's global CLAUDE.md (`~/.claude/CLAUDE.md`) asks for meaningful messages and one-logical-change-per-commit, so prefer descriptive messages for new edits rather than matching the existing `update` pattern. The repo is part of a larger `my_configs` setup (remote `git@github.com:sqfzy/my_configs.git`) — treat the skills directory as one component of a personal config dotfiles repo.

## Things not to do here

- Do not create a README.md or top-level docs "for users" — this is a personal config, the SKILL.md files are the documentation.
- Do not add build tooling, package.json, test harnesses, or CI. The "test" for a skill edit is re-reading the SKILL.md end-to-end and verifying the flow is internally consistent.
- Do not copy content between SKILL.md files to "keep them in sync" — the similarity across the three skills is by design at the structural level, not the textual level.
