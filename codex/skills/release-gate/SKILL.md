---
name: release-gate
description: Resolve exact candidate project configuration and its TODO/ALLOW finding ledger, then enforce or explicitly bypass a fresh, ephemeral, read-only Codex review under no-verify, fast, balanced, or strict mode whenever an agent or Git hook is about to push, directly create or update a GitHub PR or GitLab MR by any route, or deploy to any environment. Use for the release action itself, not ordinary commits, local builds, local tests, or draft-only PR/MR text.
---

# Release Gate

Resolve the exact candidate at every release boundary. Start a separate read-only Codex process for
review modes, or record a bypass without starting Codex when the selected mode is `no-verify`.
This skill is the single source of truth for release-review execution and policy.

## File organization

```text
release-gate/
├── SKILL.md                         # Defines release boundaries, inputs, and blocking policy.
├── scripts/
│   ├── run_release_review.py        # Starts and evaluates the fresh read-only reviewer.
│   └── review-verdict.schema.json   # Constrains the reviewer's machine-readable report.
├── tests/
│   └── test_run_release_review.py   # Covers configuration, inputs, reports, and gate decisions.
└── agents/
    └── openai.yaml                  # Provides UI metadata and the default invocation prompt.
```

Participating repositories may add these root-level, version-controlled files:

```text
.codex/
├── release-gate.toml                # Selects the repository's default review mode.
└── release-gate.md                  # Tracks unresolved TODOs and approved ALLOW exceptions.
```

## Runtime contract

Configuration:

| Name | Type | Default | Valid values | Source | Why configurable |
|---|---|---|---|---|---|
| `CODEX_RELEASE_REVIEW_TIMEOUT_SECONDS` | integer | `900` | `30` through `3600` | environment | Repository size and machine performance change review latency. |
| `CODEX_RELEASE_REVIEW_CODEX_COMMAND` | string | `codex` | Non-empty executable name or absolute path | environment | Codex installation paths differ between machines and shells. |
| `CODEX_RELEASE_REVIEW_PYTHON_COMMAND` | string | `python3` | Non-empty executable name or absolute path | environment | The Git hook may run with a different executable search path. |
| `CODEX_RELEASE_REVIEW_MODEL` | string | `gpt-5.6-sol` | Non-empty model name | environment | Machines may use different available models or review cost policies. |
| `CODEX_RELEASE_REVIEW_REASONING_EFFORT` | enum | `medium` | `minimal`, `low`, `medium`, `high`, or `xhigh` | environment | Review quality, latency, and token budgets vary by environment. |
| `CODEX_RELEASE_REVIEW_MODE` | enum | unset | `no-verify`, `fast`, `balanced`, or `strict` | environment | A release task may explicitly override the candidate repository default. |

The defaults are explicit and do not inherit the main Codex session model. To override them for a
machine or one invocation, set the environment variables before the release action:

```bash
export CODEX_RELEASE_REVIEW_MODEL=gpt-5.6-terra
export CODEX_RELEASE_REVIEW_REASONING_EFFORT=high
```

Select a task-wide override only when the user explicitly requests one. Pass it to every release
boundary in the current task; do not persist it in shell startup files:

```bash
CODEX_RELEASE_REVIEW_MODE=fast git push
```

### Project mode configuration

The exact candidate commit may contain `.codex/release-gate.toml`:

```toml
version = 1
mode = "strict"
```

| Name | Type | Default | Valid values | Source | Why configurable |
|---|---|---|---|---|---|
| `version` | integer | required when the file exists | `1` | candidate `.codex/release-gate.toml` | Versions the tracked configuration contract. |
| `mode` | enum | required when the file exists | `no-verify`, `fast`, `balanced`, or `strict` | candidate `.codex/release-gate.toml` | A repository's release risk policy differs from another repository's policy. |

Reject an empty file, unknown field, missing field, wrong type, unsupported version, or invalid mode
with status `2`. Always read and validate this file from the exact candidate Git object, even when
the environment overrides its mode; never use the uncommitted working-tree copy.

Resolve the effective mode in this order:

1. A valid `CODEX_RELEASE_REVIEW_MODE` explicitly set for the current release task.
2. The exact candidate's project `mode`.
3. The built-in `no-verify` fallback.

For a push with several non-deletion candidates and no environment override, select the strictest
candidate mode using `no-verify < fast < balanced < strict`. A missing project file contributes
`no-verify`. Deletions-only pushes use the environment override or built-in fallback.

### Finding ledger

In review modes, read `.codex/release-gate.md` from each exact candidate. A missing file means an
empty ledger. When present, require exactly one `## TODO` section and one `## ALLOW` section, each
with exactly one fenced block whose info string is `toml release-gate`. Prose outside the blocks is
allowed. Use `[[finding]]` entries inside each block:

````markdown
## TODO

```toml release-gate
[[finding]]
id = "RG-0123456789ab"
priority = "P2"
title = "Return the documented fallback value"
path = "src/service.py"
line = 42
explanation = "The changed fallback returns stale data on a supported timeout path."
first_seen_oid = "0123456789abcdef0123456789abcdef01234567"
```

## ALLOW

```toml release-gate
[[finding]]
id = "RG-fedcba987654"
priority = "P3"
title = "Keep the compatibility branch"
path = "src/compat.py"
explanation = "The branch remains intentionally reachable for legacy clients."
first_seen_oid = "0123456789abcdef0123456789abcdef01234567"
reason = "The published compatibility window is still active."
evidence = "The compatibility test and support policy require this path."
approved_by = "agent"
```
````

Common fields are `id`, `priority`, `title`, `path`, optional `line`, `explanation`, and
`first_seen_oid`. Require ALLOW entries to also contain non-empty `reason`, `evidence`, and
`approved_by`. An ID is `RG-` followed by exactly 12 lowercase hexadecimal characters and must be
unique across both sections. Require `P0` through `P3`, a normalized repository-relative POSIX
path, a positive line when present, and a 40- or 64-character hexadecimal first-seen object ID.
Reject unknown fields and malformed TOML.

`approved_by` is either `agent` or `user`. Only `user` may approve a P0 or P1 ALLOW. An agent may
approve P2 or P3 only with concrete code, test, or project-intent evidence; otherwise keep it as a
TODO. Do not add a DONE state. Delete verified fixes and stale exceptions before committing so Git
history remains the audit trail.

The child process also receives the fixed CLI override `project_doc_max_bytes=0`. This is not a
user configuration option: it prevents uncommitted working-tree instructions from entering the
review. The script supplies only review rules extracted from the exact candidate Git object.

Invocation inputs:

| Name | Type | Default | Valid values | Source |
|---|---|---|---|---|
| `event` | enum | required | `push`, `change-request`, `deploy` | `--event` |
| `repository` | path | current directory | Existing Git worktree | `--repository` |
| `target` | string | none | Exact review range or immutable target description | `--target` |
| `remote_name` | string | `origin` | Existing Git remote name | `--remote-name` |
| `push_updates` | Git pre-push records | standard input | One or more four-field ref update records | `--updates-file` |

Keep these policies fixed:

- In `fast`, `balanced`, and `strict`, run `codex exec` with `--ephemeral --sandbox read-only`.
- In review modes, pass the configured model with `--model` and reasoning effort with
  `--config model_reasoning_effort=<value>`; do not use `review_model`, which applies to `/review`.
- In review modes, explicitly invoke the system `$review-agent` inside the fresh process.
- In review modes, apply candidate project review rules as described below and disclose every rule hit that changes
  a potential finding into accepted behavior.
- In review modes, require the reviewer to return every actionable `P0` through `P3` finding, then let the script
  apply the configured review mode deterministically.
- In review modes, block when Codex is unavailable, times out, exits unsuccessfully, or returns an invalid report.
- Never add an unreported bypass, and never reuse a verdict from another release boundary.
- Bind a passing verdict to the reviewed target. If the target, `HEAD`, index, or relevant deployment
  contract changes, run a new review.

## Select the review mode

When the user does not select a task override, use the exact candidate project mode or the built-in
`no-verify` fallback. Select `fast` when the user requests review that blocks only `P0` and `P1`,
`balanced` when the user requests review that also blocks `P2`, and `strict` when the user requests
the most rigorous review. Do not infer a task override from urgency, elapsed time, review count,
token use, or an earlier review. Ask when an explicitly requested review strength is ambiguous.

| Mode | Codex review | Release behavior |
|---|---|---|
| `no-verify` | not started | resolve candidate, report `BYPASSED`, then permit |
| `fast` | started | block `P0`/`P1`; report `P2`/`P3` as advisories |
| `balanced` | started | block `P0`–`P2`; report `P3` as advisory |
| `strict` | started | block `P0`–`P3` |

An explicitly selected task mode applies to push, change-request, and deployment gates within the
same release task. Propagate it with a one-command `CODEX_RELEASE_REVIEW_MODE` environment value at
every boundary. Without a task override, let each exact candidate select its project default. Each
boundary gets a fresh gate evaluation; review modes start a fresh review, while `no-verify`
independently resolves and records the candidate. A changed target still requires rerunning the
gate. Retries in the same task keep an explicit override; a separate release task returns to the
project mode or built-in fallback.

Print advisories before continuing, but do not request another confirmation. Advisories remain
real findings below the selected blocking threshold; they are not project-approved exceptions.
The three review modes do not change the review model, reasoning effort, exact target, read-only
sandbox, project-rule handling, output validation, or failure behavior. `fast` is not a bypass.

For `no-verify`, resolve and validate the repository, input records, base, candidate, immutable
object IDs, and candidate project configuration before allowing the release. Do not compute changed
paths, read the finding ledger or project review rules, resolve the Codex executable, build a
prompt, or start a reviewer. Print and log the event, exact candidate ranges, `mode=no-verify`, and
`verdict=bypassed`; do not fabricate a pass, finding, advisory, accepted exception, or residual
risk. Invalid targets or project configurations still fail closed.

## Classify findings

First decide whether an issue is a qualifying finding. It must be concrete, actionable, supported
by code evidence, and introduced, worsened, or activated by the candidate. Classify it by
demonstrated impact, realistic likelihood, blast radius, and recoverability. Do not classify by fix
effort or inflate severity from a theoretical worst case.

| Priority | Fixed definition |
|---|---|
| `P0` | A universal release blocker or catastrophic failure that occurs with almost no special assumptions, such as broadly preventing build or startup, irreversible widespread data damage, or a severe security compromise requiring no unusual input or configuration. |
| `P1` | An urgent high-impact defect reachable through a normal or common supported path, such as core functionality failure, serious incorrect or recoverably corrupted data, a security-boundary bypass, repeated crashes, or significant service interruption. It may require a realistic condition, but not a rare or speculative one. |
| `P2` | An ordinary, medium-impact defect limited to a feature, user group, configuration, or edge path, usually with a workaround or recovery path, such as localized wrong results, constrained reliability loss, or realistic but limited performance degradation. |
| `P3` | A low-impact defect or concrete quality debt introduced or worsened by the candidate. This includes narrow edge-case failures and actionable maintainability or testability problems with a clear maintenance cost or future-defect risk. A material missing test for changed behavior may qualify; formatting, naming preferences, unsupported refactoring suggestions, speculative future extensions, and untouched legacy debt do not. |

Use the lowest priority supported by the evidence when a higher priority depends on uncertainty.
Put uncertainty and non-finding test gaps in `residual_risks`. Every finding explanation must state
the realistic trigger and demonstrated impact that justify its priority. Apply this contract before
the script partitions findings by mode; review mode never changes classification or suppresses the
reviewer's output.

## Select the exact target

- `push`: pass the unmodified ref-update records received by Git's `pre-push` hook. Resolve every
  non-deletion update. For an existing remote ref, use `remote_oid..local_oid`; for a new ref, use
  the merge base with the remote default branch when it can be resolved.
- `change-request`: resolve the complete merge range from the merge base through the exact `HEAD`
  that will back the PR or MR. Run the gate after any push and immediately before the provider
  create or update operation.
- `deploy`: resolve each frozen repository target against the commit currently deployed. For a new
  deployment with no current commit, compare the frozen target with the fetched remote default
  branch's merge base. Process every repository in a multi-repository deployment.

Do not substitute the latest commit, the last agent turn, or uncommitted changes when those are not
the release candidate.

## Apply candidate project review rules

Projects may define review behavior under an exact `## Code Review Rules` heading in committed
`AGENTS.md` or `AGENTS.override.md` files. Keep release-gate mechanics out of project instructions;
project rules define only what behavior is or is not a finding.

The script resolves changed paths and reads policy only from each candidate Git object. For every
changed path, it walks from the repository root to the path's parent directory. At each level,
`AGENTS.override.md` replaces `AGENTS.md` when both exist. Applicable sources are ordered root first,
and a deeper source overrides a conflicting higher source. Rules from another path, uncommitted
files, headings other than `## Code Review Rules`, and user-configured fallback filenames do not
apply.

An applicable project rule may add a finding or explicitly permit concrete behavior at any
priority. A permitted potential finding is omitted from `findings` and recorded in
`accepted_exceptions` with the candidate rule source, affected location, and reason. Project rules
cannot redefine the fixed priority contract or gate thresholds, change the exact target, request
writes or delegation, dictate the verdict, weaken schema validation or fail-closed behavior, or
authorize a release action.

## Reconcile the finding ledger

Send each candidate's TODO and ALLOW entries to the independent reviewer together with the scoped
project rules. Require `tracking_id` on every returned finding and accepted exception; it is the
matching ledger ID or `null` for a new finding or an AGENTS-based exception.

- Merge every registered TODO into the final report even when the reviewer omits it. Partition the
  merged TODO by the active mode exactly like any other finding.
- Accept a ledger ALLOW only when the reviewer reports that the concrete behavior actually matches
  it. Put the match in `accepted_exceptions`, never in findings.
- Keep AGENTS-based accepted exceptions at `tracking_id=null`; do not duplicate durable project
  rules in the ledger.
- Fail with status `2` for an unknown ID, a TODO returned as an accepted exception, an ALLOW
  returned as a finding, a duplicate ID or finding, changed tracked-finding content, or ambiguous
  candidate attribution.

For every new finding returned with `tracking_id=null`, generate a stable `RG-` ID from its
normalized priority, title, path, line, and explanation. Print a canonical `[[finding]]` entry with
the exact candidate OID as `first_seen_oid`. Any new finding requires ledger synchronization and
returns status `1`, including a P2 or P3 that would otherwise be advisory in the selected mode.
This prevents a real issue from disappearing between fresh reviewer runs.

The gate script and pre-push hook never modify tracked files. In an agent-driven release workflow:

1. Remove TODO entries whose fixes are verified and ALLOW entries whose exception no longer
   applies.
2. Put each new finding in TODO by default. Move P2/P3 to ALLOW only with concrete evidence. Move
   P0/P1 to ALLOW only after the user explicitly approves that exact issue.
3. Update `.codex/release-gate.md` and create a separate
   `chore(release-gate): sync findings` commit.
4. Resolve the new HEAD and run a fresh gate. Never reuse the pre-sync verdict.

When running from a Git hook, only print the canonical entries and block. Do not stage, edit, or
commit on the user's behalf.

## Distinguish Git's native push bypass

The default task-wide Codex review bypass uses a normal push, so repository-owned and other
pre-push hooks still run:

```bash
git push
```

Use `git push --no-verify` only when the user explicitly authorizes bypassing the current push. Do
not infer authorization because a similar target may have been reviewed before. Before executing,
warn that Git will skip every pre-push hook, including repository-owned hooks, not only this release
gate. Report the bypass in the outcome.

Treat native Git bypass authorization as single-use. A failed command, retry, changed target, or
later push requires new explicit authorization. It applies only to the Git push; it does not select
or propagate a Release Gate mode to change-request or deployment boundaries; those boundaries
independently use their explicit task override, candidate project mode, or built-in fallback. Do
not record a passing verdict for a natively bypassed push and do not add a persistent Git-hook
bypass setting.

## Run the gate

For PR/MR or deployment gates, run:

```bash
"${CODEX_RELEASE_REVIEW_PYTHON_COMMAND:-python3}" \
  <skill-root>/scripts/run_release_review.py \
  --event <change-request|deploy> \
  --repository <repository-root> \
  --target <exact-range-or-immutable-description>
```

Prefix the command with `CODEX_RELEASE_REVIEW_MODE=<no-verify|fast|balanced|strict>` only when
overriding the candidate project mode or built-in fallback for the current release task.

The global Git `pre-push` hook supplies push records to the same script automatically. Do not start
another in-context self-review as a substitute.

Wait for the command to finish. Exit status `0` permits the requested release action and may mean
`BYPASSED` or a reviewed result with registered advisories. Status `1` means the selected mode has
blocking findings or new findings require ledger synchronization. Status `2` means configuration,
target resolution, ledger validation, execution, or report reconciliation failed. Report the mode,
mode source, exact target, bypass state, blocking findings, advisories, accepted exceptions, and
ledger-sync entries as applicable. Do not perform the release action after a non-zero status.
