---
name: create-pr
description: Analyze the current Git branch's committed changes against a target branch, run relevant repository tests, write an evidence-backed Chinese pull request description, push the existing commits, and create or update a GitHub Draft PR. Use when the user asks to write, submit, open, refresh, or dry-run a PR for already committed work, especially when the PR must include commit history, behavior changes, root cause, reproduction, impact, prevention, test environment, test results, risk, rollback, and review guidance.
---

# Create PR

## Goal

Create an auditable Chinese PR from already committed work. Derive every claim from repository evidence or explicit user input, require relevant tests to pass before any push or PR mutation, and update an existing open PR for the same branch instead of creating a duplicate.

Do not stage, commit, amend, rebase, merge, reset, checkout another branch, or force-push.

## Runtime contract

Accept only explicit per-invocation overrides. Do not read persistent configuration or environment variables as Skill configuration.

| Name | Type | Default | Valid values |
|---|---|---|---|
| `base_branch` | string | `main` | Existing Git branch or ref |
| `remote_name` | string | `origin` | Existing Git remote |
| `test_commands` | list of strings | empty; auto-discover | Non-empty executable commands |
| `test_timeout_minutes` | integer | `30` | `1` through `240` |
| `include_ip_addresses` | boolean | `true` | `true` or `false` |
| `submission_mode` | enum | `draft` | `draft` or `dry-run` |

Keep these policies fixed:

- Write the PR title and body in Chinese; preserve commands, paths, identifiers, and quoted source text as-is.
- Analyze committed changes only.
- Require a clean working tree so tests cannot be contaminated by uncommitted files.
- Stop when tests fail, time out, cannot start, or cannot be discovered reliably.
- Create new PRs as Draft PRs. Preserve the Draft/Ready state when updating an existing PR.
- Include full active non-loopback IP addresses when `include_ip_addresses` is `true`.

## Workflow

### 1. Announce and time each phase

Report concise progress for preflight, evidence collection, test discovery, test execution, push, and PR creation or update. Record elapsed time for test commands and external Git/GitHub operations. On failure, report the failed command or operation, exit status when available, relevant context, and the next corrective action.

Never expose credentials, tokens, private keys, authorization headers, environment-variable values, or complete raw logs that may contain secrets.

### 2. Read repository instructions

Read every applicable `AGENTS.md` before acting. Look for repository PR templates in the standard root, `.github`, and `docs` locations, including `.github/PULL_REQUEST_TEMPLATE/`. Read build and test guidance from repository documentation and CI definitions.

Preserve the repository's required PR structure and checkboxes. Fill a checkbox only when evidence proves it. Populate matching template sections and append missing required analysis under an `自动分析` section instead of duplicating headings.

### 3. Run preflight before any remote write

Perform these checks in order:

1. Confirm the current directory belongs to a Git worktree.
2. Confirm the worktree is completely clean with `git status --porcelain=v1`. Treat tracked, staged, and untracked changes as dirty and stop.
3. Confirm `remote_name` exists and obtain its URL without printing embedded credentials.
4. Confirm `base_branch` exists on the selected remote. Fetch that branch without tags so the analysis uses the latest remote target.
5. Confirm `HEAD` is attached to a named branch and the current branch is not `base_branch`.
6. Resolve the fetched remote base, compute its merge-base with `HEAD`, and define the only analysis range as `merge_base..HEAD`.
7. Confirm the range contains at least one commit.
8. For `submission_mode=draft`, confirm the remote URL resolves to a GitHub repository and the GitHub connector can access that repository. For `submission_mode=dry-run`, skip connector validation and record the intended remote URL without writing to it.

Stop without pushing or mutating a PR when any check fails. Do not silently substitute a different remote, base branch, repository, or authentication mechanism.

### 4. Collect evidence

Inspect the complete range, not only the latest commit:

- Read commits in topological oldest-first order with full SHA, committer timestamp (`%cI`), author name, subject, and body.
- Inspect each commit's patch and file statistics so its row explains its actual change rather than repeating its subject.
- Inspect the aggregate diff with rename detection, changed-file statistics, relevant source, tests, schemas, configuration, documentation, and dependency manifests.
- Search branch names and commit messages for exact issue references or URLs. Link only references supported by evidence or user input.
- For `submission_mode=draft`, inspect recent repository PR titles through the connector when available and follow an established title convention. For `submission_mode=dry-run`, infer conventions only from local repository evidence. Otherwise write a concise Chinese verb-object title, normally no more than 72 characters.
- Classify the primary change as `bugfix`, `feature`, `refactor`, `performance`, or `docs/test`. Allow secondary types when the diff genuinely spans categories.

Treat the time range as commit history, not claimed development time. Show the earliest and latest committer timestamps in ISO 8601 with their original offsets.

Use the following evidence priority:

1. Observed command and test output.
2. Source code, tests, repository instructions, schemas, and CI definitions.
3. Commit messages and linked issues.
4. Explicit user statements.

Do not infer a root cause, discovery method, impact, benchmark, or test result without evidence. Write `未从现有证据确定` when a requested fact remains unknown. Unknown narrative facts do not block a Draft PR; missing or failed test evidence does.

### 5. Discover and run relevant tests

Use explicit `test_commands` when supplied. Otherwise derive the smallest defensible test set from applicable repository instructions, changed modules, build manifests, and CI workflows. Prefer repository-defined commands over invented commands. Include non-rewriting build, lint, format-check, unit, integration, and regression checks that cover the changed behavior.

Always run `git diff --check` for the analysis range. Do not install missing dependencies or rewrite files to make checks pass. Stop before any push or PR mutation when:

- no reliable project validation command can be identified;
- a dependency or command is missing;
- a command exits non-zero;
- a command exceeds `test_timeout_minutes`;
- a formatter or test modifies the worktree.

For long-running commands, poll the process and send progress at least once per minute. Terminate the command at the configured timeout. After all checks, confirm the worktree is still clean.

Record for each command: exact command, covered scope, pass/fail state, elapsed time, and a concise evidence note. Never describe a check as passed unless it ran successfully in this invocation.

### 6. Collect the actual test environment

Collect environment facts on the host where the tests ran. Support macOS and Linux with available system commands such as `uname`, `sw_vers`, `sysctl`, `lscpu`, `/etc/os-release`, `/proc`, `ifconfig`, and `ip`.

Record:

- OS distribution/version and kernel;
- CPU architecture and model;
- physical and logical CPU counts when available;
- total memory;
- relevant compiler, build-tool, runtime, and package-manager versions used by the tests;
- full IPv4 and IPv6 addresses on active non-loopback interfaces when `include_ip_addresses` is `true`.

Do not query an external public-IP service. Do not include MAC addresses, hostnames, usernames, home-directory paths, environment variables, emails, or secrets. When a fact is unavailable, write `无法采集` and include the failed read-only command in the execution summary.

### 7. Compose the PR

Start with the repository template when one exists. Otherwise use the following common order, omitting sections that genuinely do not apply:

1. `摘要`
2. `变更元数据`
3. `Commit 明细`
4. Type-specific behavior analysis
5. `关键实现`
6. `影响范围与非目标`
7. `兼容性与迁移`
8. `风险、可观测性与回滚`
9. `测试环境`
10. `测试结果`
11. `评审重点`
12. `关联 Issue`

In `变更元数据`, include primary/secondary change types, base and head, merge-base, full head SHA, commit count, commit time range, changed-file statistics, and CI status as `待运行` unless a real status for the current head was retrieved.

Create exactly one Markdown table row per commit with these columns:

| Commit | 提交时间 | 作者 | 内容 | 主要影响 |
|---|---|---|---|---|

Use the first 12 hexadecimal characters for `Commit`. Use the commit subject/body plus inspected patch for `内容`; summarize the affected behavior or subsystem for `主要影响`. Escape Markdown table delimiters and line breaks.

Adapt the behavior section by type:

- `bugfix`: describe original behavior, problem, root cause, impact, reproduction, discovery, changed behavior, and prevention. Separate code-level safeguards, regression tests, and logs/metrics/alerts. State explicitly when no new prevention mechanism exists.
- `feature`: describe current state, goal, new behavior, usage, and impact.
- `refactor`: state the externally preserved behavior, internal structure change, and regression risk.
- `performance`: provide before/after values, sampling method, workload, variance, and resource impact. Never claim an improvement without measured data.
- `docs/test`: describe corrected or added knowledge/coverage and how it was validated.

For UI changes, include screenshots or visibly mark them as missing. For performance changes, require reproducible benchmark commands and measurements; otherwise stop because required validation is unavailable.

In common sections:

- State affected components, callers, users, deployments, and explicit non-goals.
- State API, configuration, schema, data, dependency, and backward-compatibility changes. Write `无` only after inspecting the relevant evidence.
- Assign a justified low/medium/high risk, describe rollout and concrete rollback steps, and list new or existing actionable logs, metrics, or alerts.
- Give reviewers focused files, behaviors, invariants, and trade-offs to inspect.
- Use exact issue links or `未提供`; do not invent associations.

Summarize test environments in a table and test commands in a separate result table. Keep raw logs out of the PR body; include only evidence needed for review and reproduction.

### 8. Dry-run or publish

For `submission_mode=dry-run`, do not push and do not call any GitHub read or mutation. Permit a local test remote, and return its URL with the proposed base, head, title, complete body, executed tests, and blockers or warnings.

For `submission_mode=draft`, continue only after every preflight and validation requirement passes:

1. Check the remote head branch. Push only the current `HEAD` using a normal fast-forward push; set upstream when the remote branch does not yet exist.
2. Stop on non-fast-forward rejection. Never force-push or rewrite commits.
3. Find an open PR in the target repository whose head branch and base branch exactly match the current request.
4. If found, update its title and body with the GitHub connector. Do not change its Draft/Ready state.
5. If none exists, create a Draft PR with the GitHub connector using the exact repository, head, base, title, and body.

Prefer the GitHub connector's PR read, create, and update operations. The local environment need not have `gh`. If the connector is unavailable or ambiguous, stop instead of falling back to an unverified repository or account.

Do not wait for newly triggered GitHub Actions. Report CI as pending unless a status for the exact head SHA was already observed. A later invocation may refresh the existing PR with current evidence.

### 9. Report the outcome

Return:

- repository and `base <- head`;
- analyzed commit range and count;
- tests and total validation duration;
- whether the branch was already current, newly pushed, or updated;
- whether a PR was created, updated, or only rendered;
- PR URL and number when available;
- CI state and any remaining unknown narrative facts.

If push succeeds but PR creation or update fails, state this partial result explicitly and provide the branch and corrective next step. Never claim atomic rollback of a successful push.
