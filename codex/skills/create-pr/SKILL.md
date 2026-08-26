---
name: create-pr
description: Analyze a Git branch's committed changes, apply the repository's own review template, run relevant tests, push existing commits, and create or update a ready-for-review GitHub pull request or GitLab merge request. Use when the user asks to write, submit, open, refresh, or dry-run a PR or MR with an English Conventional Commit title and evidence-backed Chinese body covering commit history, behavior, impact, reproduction, prevention, test environment, test results, risk, rollback, and review guidance.
---

# Create PR

## Goal

Create an auditable GitHub pull request or GitLab merge request from already committed work, using an English Conventional Commits title and a Chinese body. Treat the repository's template as the primary document contract, derive claims from evidence, require validation before remote writes and an independent release review before provider mutation, and update an existing open change request instead of creating a duplicate.

Do not stage, commit, amend, rebase, merge, reset, checkout another branch, or force-push, except
for the narrow `$release-gate` ledger-sync workflow below. That exception may edit and stage only
`.codex/release-gate.md` and must create the separate commit
`chore(release-gate): sync findings`.

## File organization

```text
create-pr/
├── SKILL.md           # Defines configuration, evidence, template, validation, and publishing workflows.
└── agents/
    └── openai.yaml    # Defines user-facing Skill metadata and the default invocation prompt.
```

## Runtime contract

Accept only explicit per-invocation overrides. Do not read persistent configuration or environment variables as Skill configuration.

| Name | Type | Default | Valid values |
|---|---|---|---|
| `provider` | enum | `auto` | `auto`, `github`, or `gitlab` |
| `template_path` | string or null | null; auto-discover | Provider-supported repository-relative template path |
| `base_branch` | string | `main` | Existing Git branch or ref |
| `remote_name` | string | `origin` | Existing Git remote |
| `test_commands` | list of strings | empty; auto-discover | Non-empty executable commands |
| `test_timeout_minutes` | integer | `30` | `1` through `240` |
| `include_ip_addresses` | boolean | `true` | `true` or `false` |
| `submission_mode` | enum | `ready` | `ready` or `dry-run` |

Keep these policies fixed:

- Support GitHub and GitLab only. Do not infer or implement a third provider.
- Support source and target branches in the same repository only.
- Write titles in English Conventional Commits format and bodies in Chinese; preserve commands, paths, identifiers, and quoted source text as-is.
- Analyze committed changes only and require a completely clean worktree.
- Stop when validation fails, times out, cannot start, or cannot be discovered reliably.
- Use `$release-gate` immediately before creating or updating a change request. Propagate the current release task's explicitly selected review mode to push and change-request gates; otherwise omit the environment override so the exact candidate's `.codex/release-gate.toml` or the built-in fallback selects the mode. Never reuse a push verdict or bypass as a substitute for the change-request gate.
- Create new change requests ready for review. Preserve Draft/Ready state when updating an existing request.
- Include full active non-loopback IP addresses when `include_ip_addresses` is `true`.

Use `pull request`/`PR` for GitHub and `merge request`/`MR` for GitLab. Use `change request` only when describing provider-independent workflow.

## Workflow

### 1. Announce and time each phase

Report concise progress for preflight, provider detection, template resolution, evidence collection, test discovery, test execution, push, release review, and change-request creation or update. Record elapsed time for tests, release review, and external Git or provider operations.

On failure, report the command or operation, exit status when available, relevant context, and corrective action. Never expose credentials, tokens, private keys, authorization headers, environment-variable values, or complete raw logs that may contain secrets.

### 2. Read repository instructions

Read every applicable `AGENTS.md`, contribution guide, build guide, CI definition, and test guide before acting. Repository instructions govern validation and content unless they conflict with this Skill's write-safety rules.

Do not use a template from the working branch merely because it exists there. Resolve templates from the fetched remote default branch so a proposed change cannot silently replace the repository's review contract.

### 3. Run preflight and select the provider

Perform these checks before tests or remote writes:

1. Validate every runtime override against the contract before repository or provider operations. Reject the removed `submission_mode=draft` value; do not treat it as `ready`.
2. Confirm the current directory belongs to a Git worktree.
3. Confirm `git status --porcelain=v1` is empty. Treat tracked, staged, and untracked changes as dirty and stop.
4. Confirm `remote_name` exists and obtain its URL without printing embedded credentials.
5. Resolve the remote hostname. With `provider=auto`, select `github` only for `github.com` and `gitlab` only for `gitlab.com`; require an explicit provider for every other hostname, including self-hosted services.
6. Reject a provider that conflicts with a known `github.com` or `gitlab.com` hostname.
7. Resolve the remote default branch with the remote symbolic `HEAD`; fetch it without tags and retain its exact commit as `template_commit`. Do not silently substitute `base_branch` when the default branch is unknown.
8. Confirm `base_branch` exists on the selected remote and fetch it without tags.
9. Confirm `HEAD` is attached to a named branch and the current branch is not `base_branch`.
10. Compute the merge-base between the fetched base and `HEAD`; define the only analysis range as `merge_base..HEAD` and require at least one commit.

For `submission_mode=ready`, also validate the selected publishing channel before tests:

- GitHub: normalize the remote to one exact `owner/repository` and confirm the GitHub connector can access it.
- GitLab: require `glab`, run its authentication status check for the remote hostname, and confirm it resolves the exact remote project. If `glab` is missing, stop with `brew install glab` and `glab auth login --hostname <host>`; never install or authenticate automatically.

For `submission_mode=dry-run`, skip GitHub connector and `glab` reads. Permit a local remote when `provider` is explicit, but still resolve its default branch and enforce every Git safety and validation gate.

Stop rather than substituting a different provider, remote, repository, account, base, or authentication mechanism.

### 4. Resolve the repository template

List blobs from `template_commit` and match paths case-insensitively while retaining their exact Git path. Accept only a non-empty regular file at a provider-supported location; reject absolute paths, `..`, directories, symlinks, and unsupported extensions.

Apply this precedence:

1. If `template_path` is provided, require that exact repository-relative path on `template_commit`. Use it or stop; never fall back.
2. For GitHub, find single-file templates named `pull_request_template.md` or `pull_request_template.txt` in the repository root, `docs/`, or `.github/`. Use the only match; stop and list paths when more than one matches.
3. For GitLab, find `.gitlab/merge_request_templates/Default.md` case-insensitively. Use the only match; stop and list paths when more than one case-variant matches.
4. When no provider default exists, inspect GitHub `PULL_REQUEST_TEMPLATE/` directories under the root, `docs/`, and `.github/`, or GitLab `.gitlab/merge_request_templates/*.md`. Use the candidate only when exactly one exists.
5. When multiple non-default candidates exist, stop before tests and list them. Require an explicit `template_path` on the next invocation.
6. When no repository template exists, use the built-in body structure.

Read the selected template with `git show template_commit:template_path`, never from the worktree. Log the default branch, template commit, selected path, and selection reason.

Treat the selected repository template as authoritative over provider-side defaults and the built-in structure. Preserve its headings, ordering, comments, instructions, and checkboxes. Do not delete or reorder content, and check a box only when evidence proves it. Fill matching sections in place; append missing audit material under one final `## 自动分析` section rather than duplicating template headings.

For a GitLab repository template, replace exact `%{source_branch}` and `%{target_branch}` placeholders with the known branch names. Preserve every other unknown placeholder literally instead of inventing a value.

### 5. Collect evidence

Inspect the complete range, not only the latest commit:

- Read commits in topological oldest-first order with full SHA, committer timestamp (`%cI`), author name, subject, and body.
- Inspect each commit's patch and statistics so its table row explains the actual change rather than repeating its subject.
- Inspect the aggregate diff with rename detection, relevant source, tests, schemas, configuration, documentation, and dependency manifests.
- Link only issue references or URLs supported by branch names, commit messages, repository evidence, or explicit user input.
- For a ready submission, inspect recent titles through the selected provider when available. For a dry-run, infer conventions from local evidence only.
- Classify the primary change as `bugfix`, `feature`, `refactor`, `performance`, or `docs/test`; allow evidence-backed secondary types.

Generate an English Conventional Commits title from the aggregate diff, not only the latest commit:

- Use `<type>(<scope>): <summary>` when scope is supported by evidence, otherwise use `<type>: <summary>`.
- Map `bugfix` to `fix`, `feature` to `feat`, `refactor` to `refactor`, `performance` to `perf`, documentation-only changes to `docs`, and test-only or test-dominant changes to `test`.
- Select scope from explicit repository title rules first, then the dominant changed package or module, then one scope used consistently across the analyzed commits. Omit scope when none is reliable; never guess it.
- Describe the main user-visible or operational change in concise imperative English. Start the summary in lowercase, omit a trailing period, and normally keep the complete title at or below 72 characters.
- Follow a conflicting title rule only when an applicable `AGENTS.md` or contribution guide explicitly requires it. Repository body templates do not override title format.

Treat the time range as commit history, not development time. Show the earliest and latest committer timestamps in ISO 8601 with their original offsets.

Use this evidence priority:

1. Observed command and test output.
2. Source code, tests, repository instructions, schemas, and CI definitions.
3. Commit messages and linked issues.
4. Explicit user statements.

Do not infer a root cause, discovery method, impact, benchmark, or test result. Write `未从现有证据确定` when a fact remains unknown. Unknown narrative facts do not block a change request; missing or failed validation evidence does.

### 6. Discover and run relevant tests

Use explicit `test_commands` when supplied. Otherwise derive the smallest defensible test set from repository instructions, changed modules, build manifests, and CI workflows. Prefer repository-defined commands over invented commands. Include non-rewriting build, lint, format-check, unit, integration, regression, and benchmark checks relevant to the change.

Always run `git diff --check` for the analysis range. Do not install missing dependencies or rewrite files to make checks pass. Stop before any push or provider mutation when:

- no reliable project validation command can be identified;
- a dependency or command is missing;
- a command exits non-zero;
- a command exceeds `test_timeout_minutes`;
- a formatter or test modifies the worktree.

Poll long-running commands and report progress at least once per minute. Terminate them at the configured timeout. Confirm the worktree remains clean after all checks.

Record the exact command, covered scope, result, elapsed time, and concise evidence. Never describe a check as passed unless it completed successfully in this invocation.

### 7. Collect the actual test environment

Collect facts on the host where tests ran. Support macOS and Linux through available system commands such as `uname`, `sw_vers`, `sysctl`, `lscpu`, `/etc/os-release`, `/proc`, `ifconfig`, and `ip`.

Record OS/version, kernel, CPU architecture/model, physical and logical CPU counts, total memory, relevant toolchain versions, and full IPv4/IPv6 addresses on active non-loopback interfaces when enabled.

Do not query a public-IP service. Do not include MAC addresses, hostnames, usernames, home-directory paths, environment variables, emails, or secrets. Write `无法采集` for unavailable facts and include the failed read-only command in the execution summary.

### 8. Compose the body

When no repository template exists, use this built-in order and omit genuinely irrelevant sections:

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

When a repository template exists, fill equivalent sections there and place only missing material under `自动分析`. Never prepend the built-in structure ahead of the repository template.

Include provider, base/head, merge-base, full head SHA, commit count, commit time range, changed-file statistics, selected template path or `内置结构`, and CI status as `待运行` unless a real status for the exact head was retrieved.

Create exactly one row per commit:

| Commit | 提交时间 | 作者 | 内容 | 主要影响 |
|---|---|---|---|---|

Use the first 12 SHA characters. Derive `内容` from commit subject/body and inspected patch, derive `主要影响` from changed behavior or subsystem, and escape Markdown table delimiters and line breaks.

Adapt analysis by type:

- `bugfix`: original behavior, problem, root cause, impact, reproduction, discovery, changed behavior, and prevention; separate code safeguards, regression tests, and observability.
- `feature`: current state, goal, new behavior, usage, and impact.
- `refactor`: preserved external behavior, internal change, and regression risk.
- `performance`: measured before/after values, workload, sampling method, variance, and resource impact.
- `docs/test`: corrected or added knowledge/coverage and its validation.

Require screenshots for UI changes or mark them missing. Require reproducible measurements for performance claims or stop. Cover affected components and non-goals, API/config/schema/data/dependency compatibility, justified risk, rollout, concrete rollback, observability, review focus, and exact issue links. Keep raw logs out of the body.

### 9. Dry-run or publish

For `submission_mode=dry-run`, do not push and do not call GitHub or GitLab reads or mutations. Return the selected provider, remote, template decision, base/head, proposed title, complete body, tests, blockers, and warnings.

For `submission_mode=ready`, continue only after preflight, template resolution, evidence collection, and validation pass:

1. Check the remote head. Push only the current `HEAD` with a normal fast-forward push; set upstream when the remote branch does not exist. If the user explicitly requests `--no-verify` for this push, follow `$release-gate`'s single-use push-bypass contract. Pass `CODEX_RELEASE_REVIEW_MODE` only for an explicit task override; otherwise let the push hook read the candidate project mode.
2. Stop on non-fast-forward rejection. Never rewrite commits or force-push.
3. Invoke `$release-gate` with `event=change-request`, any explicit task-mode environment override, and the exact `merge_base..HEAD` range. Without an override, let the candidate project configuration select the mode. Follow its verdict or explicit bypass contract without substituting an earlier push result.
4. If status `1` includes `Ledger sync required`, inspect each canonical entry. Put new findings in TODO by default; allow an agent-approved P2/P3 only with concrete code, test, or project-intent evidence; require explicit user approval before any P0/P1 ALLOW. Remove verified fixed TODOs and stale ALLOWs. Modify only `.codex/release-gate.md`, create `chore(release-gate): sync findings`, recompute the committed analysis range and PR/MR evidence, push the new HEAD normally, and rerun the change-request gate. If the ledger cannot be updated safely, stop with the entries instead of publishing.
5. Reconfirm that `HEAD` and the remote source branch still equal the reviewed commit. Rerun the gate if either changed.
6. Find open change requests whose source and target exactly match. Stop on more than one exact match.
7. Update the one exact match without changing its Draft/Ready state, or create a new ready-for-review request when none exists.

Apply step 4 equally when the pre-push hook reports ledger synchronization before the first push.
After the sync commit, rerun every affected release boundary against the new HEAD; never treat the
earlier status as approval.

For GitHub, use the GitHub connector for exact PR lookup, ready-for-review creation, and update. Do not request Draft state when creating. Preserve the state of an existing PR.

For GitLab:

- Use `glab mr list --source-branch <head> --target-branch <base> --output json` and verify the returned fields rather than trusting display text.
- Create with `glab mr create --source-branch <head> --target-branch <base> --title <title> --description <body> --yes`; do not pass `--draft` or `--wip`.
- Update with `glab mr update <iid> --title <title> --description <body> --yes`; do not pass `--draft`, `--ready`, `--wip`, or target-changing flags.
- Never use `--fill`, `--push`, `--web`, or an editor-driven flow.

Pass titles and bodies as data, not executable shell fragments. Use safely quoted arguments or a temporary file outside the repository; never use `eval`. Remove temporary material after the provider command when safe.

Do not wait for newly triggered CI. Report CI as pending unless a status for the exact head was already observed. A later invocation may refresh the existing PR or MR.

### 10. Report the outcome

Return provider and repository, `base <- head`, analyzed range/count, selected template, tests and total duration, release-review effective mode and source/target/verdict/bypass/advisories/accepted exceptions/ledger synchronization/duration, push state distinguishing task-mode bypass from native Git `--no-verify`, created/updated/rendered state, PR/MR URL and number, CI state, and remaining unknown facts.

If push succeeds but creation or update fails, state the partial result and corrective next step. Never claim atomic rollback of a successful push.
