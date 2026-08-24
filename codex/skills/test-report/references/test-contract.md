# Test Contract

## Contents

- [Supported scope](#supported-scope)
- [Runtime configuration](#runtime-configuration)
- [Frozen contract](#frozen-contract)
- [Result sources](#result-sources)
- [Status and recommendation](#status-and-recommendation)
- [Evidence and redaction](#evidence-and-redaction)

## Supported scope

Run commands locally on macOS or Linux, or remotely on Linux/systemd through SSH. The Skill is an
execution and evidence layer over the project's existing test tools. It does not invent project
test cases, upload reports, deploy software, or provide toolchain-specific Cargo, xmake, or pytest
parsers.

## Runtime configuration

Resolve these values before implementation or execution:

| Name | Type | Default | Valid values | Source | Why configurable |
|---|---|---|---|---|---|
| `target.kind` | enum | `local` | `local`, `ssh` | test contract | execution environment varies |
| `target.ssh.host` | string | required for SSH | IP or DNS name | user request/test contract | target server varies |
| `target.ssh.user` | string | required for SSH | non-empty username | user request/test contract | privilege model varies |
| `target.ssh.port` | integer | `22` | 1-65535 | test contract | SSH topology varies |
| `target.ssh.known_hosts` | path | `~/.ssh/known_hosts` | readable regular file | local environment/test contract | host identity store varies |
| `execution.default_timeout_seconds` | integer | `600` | 1-86400 | test contract | suite runtime varies |
| `evidence.max_stream_bytes` | integer | `10485760` | 1048576-268435456 | test contract | evidence retention varies |
| `report.output_dir` | path | task output directory, otherwise CWD | writable directory | CLI | artifact location varies |
| `deployment_evidence.path` | path or null | null | deployment evidence schema v1 | CLI | deployment context is optional |

Do not add a concurrency switch in schema v1. Execute in declared order. Do not turn test
requirements, thresholds, or required/optional policy into global configuration.

## Frozen contract

Use schema version 1:

```json
{
  "schema_version": 1,
  "metadata": {
    "title": "Example engineering acceptance",
    "objective": "Verify the exact candidate",
    "scope": ["unit", "smoke"],
    "limitations": []
  },
  "target": {"kind": "local", "ssh": null},
  "execution": {"default_timeout_seconds": 600},
  "evidence": {"max_stream_bytes": 10485760},
  "subject": {
    "repositories": [
      {"role": "application", "path": ".", "commit": "40-hex-character commit"}
    ],
    "artifacts": [],
    "services": []
  },
  "key_config": [
    {"name": "runtime.log_level", "source": "config file", "value": "info"}
  ],
  "tests": [
    {
      "id": "unit",
      "name": "Unit tests",
      "category": "unit",
      "required": true,
      "argv": ["cargo", "test", "--locked"],
      "working_directory": ".",
      "timeout_seconds": 600,
      "expected_exit_codes": [0],
      "depends_on": [],
      "result_sources": [],
      "mutation_scope": "task_workspace",
      "external_authorized": false,
      "cleanup_argv": null
    }
  ]
}
```

Require a non-empty `metadata.title`, `metadata.objective`, and `tests`. Require at least one
declared repository or artifact. Repository commits, when supplied, must be full 40- or 64-hex Git
object IDs. Artifact digests, when supplied, must be 64-hex SHA-256 values.

Each test has a unique lowercase ID containing letters, digits, `.`, `_`, or `-`; a category; an
explicit `required` boolean; a non-empty argv array; a working directory; expected exit codes; and
a mutation scope from `read_only`, `task_workspace`, `test_target`, or `external`. A dependency
must name an earlier test. `skip_reason`, when non-empty, records an intentional skip without
executing the command.

An `external` test requires `external_authorized: true` and a non-empty `cleanup_argv`. Otherwise
record it as blocked. Run cleanup after every attempted external test and after a `test_target`
test when cleanup is declared. A failed cleanup makes the test erroneous and the recommendation
`no-go`.

Do not put passwords, tokens, private keys, authorization headers, URI userinfo, or sensitive
command arguments in the contract. Record only environment-variable names when provenance matters.

## Result sources

Exit status is always evidence. Optional `result_sources` add detail:

```json
[
  {"kind": "junit_xml", "path": "build/junit.xml"},
  {"kind": "metrics_json", "path": "build/metrics.json"}
]
```

Resolve relative paths against the test working directory and copy them into the local evidence
directory. A declared missing, truncated, or malformed result source is an execution error.

JUnit XML may have a `testsuite` root or nested `testsuites`. Count tests, failures, errors, and
skipped cases. A suite with failures/errors fails; a zero-test or fully skipped suite is skipped.

Metrics schema version 1:

```json
{
  "schema_version": 1,
  "measurements": [
    {"kind": "metric", "name": "p99_latency", "value": 12.3, "unit": "ms", "operator": "<=", "threshold": 15.0},
    {"kind": "coverage", "name": "line", "value": 82.1, "unit": "percent", "operator": ">=", "threshold": 80.0}
  ]
}
```

Accept only finite numeric values, non-empty units, and `<`, `<=`, `>`, `>=`, or `==`. Compute the
pass decision; do not trust an input `passed` field.

## Status and recommendation

Per-test statuses are `passed`, `failed`, `error`, `timed_out`, `blocked`, and `skipped`.

- Any required `failed`, `error`, or `timed_out` result makes the overall verdict `failed`.
- Otherwise, any required `blocked` or `skipped` result makes it `inconclusive`.
- Otherwise, optional non-passing results or warnings make it `passed_with_warnings`.
- Otherwise, it is `passed`.

Keep the recommendation explicitly test-based:

- `go`: overall `passed`, exact clean/pinned subject, complete evidence, and successful cleanup.
- `conditional`: required tests passed but optional failures, warnings, dirty/unverified identity,
  or non-critical evidence gaps remain.
- `no-go`: overall `failed`/`inconclusive`, no identifiable subject, identity conflict, external
  mutation without authorization, or cleanup failure.

## Evidence and redaction

Redact names and flags containing `password`, `passwd`, `secret`, `token`, `api_key`, `apikey`,
`private_key`, `credential`, or `authorization`. Redact URI userinfo and sensitive assignments.
Apply redaction before retained evidence is written. Temporary capture files must be mode `0600`
and removed after the redacted file is atomically installed.

Every manifest entry records relative path, SHA-256, byte size, media type, source test ID when
applicable, and `redacted`/`truncated` flags. The Markdown report embeds all essential context and
uses the manifest only for audit detail.
