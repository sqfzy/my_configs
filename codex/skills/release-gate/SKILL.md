---
name: release-gate
description: Run a fresh, ephemeral, read-only Codex review and enforce its verdict before Git pushes, PR/MR creation or updates, and deployments. Use only when an agent is about to cross one of these release boundaries; do not use for ordinary commits, local builds, or local test runs.
---

# Release Gate

Start a separate Codex process for every release boundary so the reviewer has a clean context and
cannot modify the repository. Block the release action unless that reviewer returns no actionable
findings.

## File organization

```text
release-gate/
├── SKILL.md                         # Defines release boundaries, inputs, and blocking policy.
├── scripts/
│   ├── run_release_review.py        # Starts and evaluates the fresh read-only reviewer.
│   └── review-verdict.schema.json   # Constrains the reviewer's machine-readable verdict.
├── tests/
│   └── test_run_release_review.py   # Covers configuration, push inputs, and verdict invariants.
└── agents/
    └── openai.yaml                  # Provides UI metadata and the default invocation prompt.
```

## Runtime contract

Configuration:

| Name | Type | Default | Valid values | Source | Why configurable |
|---|---|---|---|---|---|
| `CODEX_RELEASE_REVIEW_TIMEOUT_SECONDS` | integer | `900` | `30` through `3600` | environment | Repository size and machine performance change review latency. |
| `CODEX_RELEASE_REVIEW_CODEX_COMMAND` | string | `codex` | Non-empty executable name or absolute path | environment | Codex installation paths differ between machines and shells. |
| `CODEX_RELEASE_REVIEW_PYTHON_COMMAND` | string | `python3` | Non-empty executable name or absolute path | environment | The Git hook may run with a different executable search path. |

Invocation inputs:

| Name | Type | Default | Valid values | Source |
|---|---|---|---|---|
| `event` | enum | required | `push`, `change-request`, `deploy` | `--event` |
| `repository` | path | current directory | Existing Git worktree | `--repository` |
| `target` | string | none | Exact review range or immutable target description | `--target` |
| `remote_name` | string | `origin` | Existing Git remote name | `--remote-name` |
| `push_updates` | Git pre-push records | standard input | One or more four-field ref update records | `--updates-file` |

Keep these policies fixed:

- Run `codex exec` with `--ephemeral --sandbox read-only`.
- Explicitly invoke the system `$review-agent` inside the fresh process.
- Block on every actionable `P0` through `P3` finding.
- Block when Codex is unavailable, times out, exits unsuccessfully, or returns an invalid verdict.
- Never add a silent bypass or reuse a verdict from another release boundary.
- Bind a passing verdict to the reviewed target. If the target, `HEAD`, index, or relevant deployment
  contract changes, run a new review.

## Select the exact target

- `push`: pass the unmodified ref-update records received by Git's `pre-push` hook. Review every
  non-deletion update. For an existing remote ref, use `remote_oid..local_oid`; for a new ref, use
  the merge base with the remote default branch when it can be resolved.
- `change-request`: review the complete merge range from the resolved merge base through the exact
  `HEAD` that will back the PR or MR. Run this review after any push and immediately before the
  provider create or update operation.
- `deploy`: review each frozen repository target against the commit currently deployed. For a new
  deployment with no current commit, compare the frozen target with the fetched remote default
  branch's merge base. Review every repository in a multi-repository deployment.

Do not substitute the latest commit, the last agent turn, or uncommitted changes when those are not
the release candidate.

## Run the gate

For PR/MR or deployment gates, run:

```bash
"${CODEX_RELEASE_REVIEW_PYTHON_COMMAND:-python3}" \
  <skill-root>/scripts/run_release_review.py \
  --event <change-request|deploy> \
  --repository <repository-root> \
  --target <exact-range-or-immutable-description>
```

The global Git `pre-push` hook supplies push records to the same script automatically. Do not start
another in-context self-review as a substitute.

Wait for the command to finish. Exit status `0` permits the requested release action, `1` means
actionable findings block it, and `2` means the review itself failed and also blocks it. Report all
findings and the exact reviewed target. Do not perform the release action after a non-zero status.
