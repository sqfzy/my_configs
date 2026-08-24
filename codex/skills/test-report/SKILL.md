---
name: test-report
description: Execute or re-render local and SSH test runs as standalone, redacted Chinese engineering test reports with reproducible evidence and a test-based release recommendation. Use for unit, integration, system, smoke, regression, performance, or acceptance testing; do not use it to claim deployment success or replace a project test framework.
---

# Test Report

Freeze what will be tested before execution, preserve machine-readable evidence, and make the
Markdown report understandable without a deployment report. Keep test data, execution logic, and
presentation separate.

## File organization

```text
test-report/
├── SKILL.md                         # Orchestrates contract freezing, execution, and reporting.
├── references/test-contract.md     # Defines runtime configuration and JSON evidence contracts.
├── scripts/
│   ├── run_tests.py                # Executes ordered local/SSH tests and captures redacted evidence.
│   └── render_report.py            # Parses results, decides verdicts, and renders final artifacts.
├── assets/report-template.md       # Defines the standalone Chinese Markdown report structure.
├── tests/test_tools.py             # Covers contracts, execution, parsing, verdicts, and redaction.
└── agents/openai.yaml              # Supplies Codex UI metadata.
```

## Freeze the test contract

Read [references/test-contract.md](references/test-contract.md) completely before running or
rendering tests. Resolve the target, exact subject, ordered commands, required results, timeouts,
side effects, cleanup, and output directory before execution. Test commands and thresholds are
per-run business data, not Skill-wide switches.

Reject secret values in the contract. Record environment-variable names and redacted effective
configuration, never their secret values. Permit external mutation only when the user explicitly
authorized it and the test has a cleanup command. A test lacking that authorization is blocked;
authorization to test does not imply permission to mutate unrelated external state.

## Execute and capture

Run the frozen contract with:

```bash
python3 <skill-root>/scripts/run_tests.py \
  --contract <test-contract.json> \
  --output-dir <test-run-dir>
```

Use argv arrays rather than inferred shell strings. Execute tests sequentially. A dependency may
refer only to an earlier test; block a dependent test when its prerequisite did not pass, while
continuing independent tests. Use strict SSH host verification with a real known-hosts file.

Capture start/end timestamps, duration, exit status, timeout, cleanup status, subject identity,
and environment snapshots. Redact stdout, stderr, JUnit XML, and metrics JSON before retaining
them. Mark truncated evidence explicitly and hash the retained bytes. Never preserve a second
unredacted copy.

## Render the independent report

Render either a new execution or compatible existing evidence without rerunning tests:

```bash
python3 <skill-root>/scripts/render_report.py \
  --contract <test-contract.json> \
  --execution <execution.json> \
  --deploy-evidence <optional-deployment-evidence.json> \
  --output-dir <test-run-dir>
```

Deployment evidence is optional context. Fresh test-time observations take precedence. Reject the
import on a host, repository commit, or artifact digest conflict and keep the conflict in report
warnings. Copy every useful imported fact into the test result and report; do not leave the reader
dependent on another report. Never import Alertd webhook credentials.

Produce `test-result.json`, `test-report.md`, and `evidence-manifest.json`. State the test verdict
and the test-based `go`, `conditional`, or `no-go` recommendation separately. Do not describe
either as proof that a deployment succeeded.
