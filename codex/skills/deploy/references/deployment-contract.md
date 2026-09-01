# Deployment Contract

## Contents

- [Supported scope](#supported-scope)
- [Runtime configuration](#runtime-configuration)
- [Frozen deployment contract](#frozen-deployment-contract)
- [Deployment report bundle](#deployment-report-bundle)
- [Program output contract](#program-output-contract)
- [Business service inventory](#business-service-inventory)
- [Hard gates](#hard-gates)
- [Atomic deployment and rollback](#atomic-deployment-and-rollback)
- [Alertd contract](#alertd-contract)
- [Test-context evidence](#test-context-evidence)
- [Evidence and report content](#evidence-and-report-content)

## Supported scope

Support Amazon Linux 2023 on `aarch64`, managed by systemd. Deploy native systemd
applications only. Permit Docker solely as an isolated build tool for `alertd` when the host
lacks the required Rust toolchain.

Limit rollback to application artifacts, symlinks, systemd units/drop-ins, and enumerated
configuration files. Never claim to roll back databases, external state, application writes, or
program outputs such as logs, dumps, and data files. Reject irreversible migrations unless an
explicit user requirement overrides that default and accepts the unavailable rollback guarantee.

## Runtime configuration

Resolve and freeze every value before writing the implementation plan. Treat deployment-specific
addresses as data; never copy them into Skill names, comments, or fixed instructions.

| Name | Type | Default | Valid values | Source | Why configurable |
|---|---|---|---|---|---|
| `ssh.host` | string | required | valid IP or DNS name | user request | deployment target |
| `ssh.user` | string | `root` | non-empty POSIX username | user request | host privilege model |
| `ssh.port` | integer | `22` | 1–65535 | user request | SSH topology |
| `ssh.known_hosts` | path | `~/.ssh/known_hosts` | readable file | local environment | host identity store |
| `capacity.min_free_percent` | integer | `10` | 10–50 | user request; may only increase | capacity policy |
| `health.observe_for` | duration | `5m` | 5–30 minutes | user request; may only increase | release risk tolerance |
| `cpu.sample_for` | duration | `10s` | 5–60 seconds | user request | observation accuracy/runtime |
| `release.keep` | integer | `2` | 2–10 | user request | rollback retention |
| `report.local_dir` | path | task output directory, otherwise CWD | writable directory | user request | downloaded archive location |
| `report.remote_dir` | path | `/var/lib/deploy/reports` | safe absolute non-root path | user request | expanded bundle and archive audit location |
| `report.transfer_timeout` | duration | `30m` | 5–120 minutes | user request / publisher CLI | bundle size and network speed vary |
| `alertd.repo` | Git URL | `git@github.com:sqfzy/alertd.git` | SSH Git URL | Skill/user config | monitoring source varies by environment |
| `alertd.target` | string | `main` | branch or tag | Skill/user config | monitoring release selection |
| `alertd.config_path` | path | `/etc/alertd/alertd.toml` | absolute path | Skill/user config | installation layout |
| `alertd.state_dir` | path | `/var/lib/alertd` | absolute path | Skill/user config | state layout |
| `business.exclude_units` | string list | `alertd.service` | valid systemd unit names | user request | infrastructure roles vary by host |
| `builder.image` | OCI reference | derive `rust:<rust-version>-alpine` | resolvable image pinned by digest | repository metadata | build toolchain compatibility |

Do not turn application behavior into Skill switches. Put build commands, application config,
health semantics, CPU affinity, and network binding in the per-deployment contract below.

Report bundle folders follow the fixed presentation rule
`YYYYMMDD-HHMMSSZ-<normalized-hostname>-deploy`. The timestamp is the UTC time at which final bundle
creation starts and is generated once per bundle. Its leading, fixed-width form makes lexical
folder order chronological. Normalize the hostname to lowercase and replace characters outside
`[a-z0-9._-]` with `-`. The expanded folder uses this basename on the server; the server and local
archives append `.tar.gz`. This is not runtime configuration because deployments do not vary the
ordering or portable archive convention.

## Frozen deployment contract

Create a JSON object with this shape in task-local scratch space. Do not mutate the server until
it is complete, validated, and recorded. An explicit deployment request authorizes execution; do
not add a default confirmation checkpoint.

```json
{
  "schema_version": 4,
  "target": {
    "host": "deploy.example",
    "user": "root",
    "port": 22,
    "known_hosts": "/absolute/path/to/known_hosts"
  },
  "deployment": {
    "service_units": ["example.service"],
    "release_root": "/opt/example/releases",
    "current_link": "/opt/example/current",
    "keep_releases": 2,
    "min_free_percent": 10,
    "observe_seconds": 300,
    "cpu_sample_seconds": 10,
    "report_remote_dir": "/var/lib/deploy/reports"
  },
  "repositories": [
    {
      "role": "application",
      "url": "git@example:team/repo.git",
      "target": "main",
      "commit": "40-hex-character commit",
      "builder_image_digest": "image@sha256:...",
      "artifact_sha256": "64-hex-character digest"
    }
  ],
  "changes": [
    {
      "path": "/absolute/target/path",
      "action": "create|replace|remove",
      "rollback": "exact restoration action"
    }
  ],
  "health": {
    "alertd_config_path": "/etc/alertd/alertd.toml",
    "alertd_state_dir": "/var/lib/alertd",
    "required_units": ["example.service"]
  },
  "configurations": [
    {
      "service": "example.service",
      "kind": "systemd",
      "purpose": "business service definition",
      "capture": "file",
      "source_path": "/etc/systemd/system/example.service",
      "package_path": "systemd/example.service",
      "content": null,
      "required": true
    },
    {
      "service": "alertd.service",
      "kind": "systemd",
      "purpose": "monitoring service definition",
      "capture": "file",
      "source_path": "/etc/systemd/system/alertd.service",
      "package_path": "systemd/alertd.service",
      "content": null,
      "required": true
    },
    {
      "service": "example.service",
      "kind": "application_config",
      "purpose": "application configuration",
      "capture": "file",
      "source_path": "/etc/example/example.toml",
      "package_path": "config/application/example.toml",
      "content": null,
      "required": true
    },
    {
      "service": "example.service",
      "kind": "runtime",
      "purpose": "effective CLI and environment",
      "capture": "generated",
      "source_path": null,
      "package_path": "config/generated/example.runtime.json",
      "content": {
        "schema_version": 1,
        "working_directory": "/opt/example/current",
        "argv": ["/opt/example/current/bin/example", "--config", "/etc/example/example.toml"],
        "environment": {"LOG_LEVEL": "info"}
      },
      "required": true
    }
  ],
  "program_outputs": [
    {
      "service": "example.service",
      "kind": "log",
      "sink": "file",
      "path": "/var/log/example/example.log",
      "locator": null,
      "source": "/etc/example/example.toml:logging.path",
      "evidence": "configured",
      "required": true,
      "readiness": "exists",
      "rotation": "/etc/logrotate.d/example",
      "retention": "7d"
    },
    {
      "service": "example.service",
      "kind": "log",
      "sink": "journald",
      "path": null,
      "locator": "journalctl -u example.service",
      "source": "systemd StandardOutput/StandardError",
      "evidence": "configured",
      "required": true,
      "readiness": "active_sink",
      "rotation": "journald",
      "retention": "unknown"
    }
  ],
  "cpu_affinity": {},
  "network_binding": {},
  "reproduce": ["ordered, concrete command with every value needed to reproduce deployment"],
  "rollback": ["ordered, concrete rollback command"],
  "irreversible_changes": []
}
```

Require full Git commits, absolute paths, an enumerated change for every mutable path, exact
rollback commands, and at least one repository. Resolve a branch/tag with `git ls-remote`, then
fetch and verify that exact commit. Record the requested target and immutable commit separately.

Require every field above, an empty `irreversible_changes`, a rollback action for every change, and
zero unresolved assumptions. Ask only when the target host, Git target, change surface, or rollback
path has multiple materially reasonable interpretations. A user-requested pause is a one-time
checkpoint, not a mode.

Treat every operationally necessary effective setting as configuration. Preserve native config,
EnvironmentFile, credential, certificate, private-key, systemd, and script files byte-for-byte.
Represent non-file settings as generated JSON with complete raw values. Use `无法确认` plus a
concrete reason when an optional value cannot be collected; do not fabricate it or replace a known
value with a presence-only marker. A required configuration that cannot be captured prevents bundle
publication.

Emit schema version 4 without a `mode` field for every new deployment. Accept schema versions 1–3
only when rendering historical single-file reports; none is valid input for a new deployment. The
output checker accepts v2–v4 and preserves v2's historical full-unit-coverage behavior.

## Deployment report bundle

`configurations` is the complete, explicit capture plan. Do not discover report files by scanning
the host. Start with every deployed unit plus `alertd.service`, then follow only effective systemd
properties, application config references, and frozen deployment requirements.

| Field | Type | Valid values | Meaning |
|---|---|---|---|
| `service` | string | deployed unit, `alertd.service`, or `deployment` | owning service or bundle-wide role |
| `kind` | enum | `application_config`, `environment`, `credential`, `systemd`, `script`, `runtime` | artifact role |
| `purpose` | string | non-empty description | why deployment or reproduction needs the file |
| `capture` | enum | `file`, `generated` | copy server bytes or materialize JSON |
| `source_path` | absolute path or null | absolute for `file`, null for `generated` | effective server source |
| `package_path` | relative path | rooted at `config/`, `systemd/`, or `scripts/` according to kind | stable bundle location |
| `content` | object or null | JSON object for `generated`, null for `file` | exact non-file configuration |
| `required` | boolean | required | whether missing capture blocks bundle publication |

Every unit in `deployment.service_units` and `alertd.service` must have a `systemd` file entry.
Enumerate each drop-in and referenced script as its own entry. A file capture preserves resolved
bytes and records the original path, resolved path, symlink target, owner, group, mode, size, and
SHA-256. The bundle never contains live symlinks back to the server.

Generated CLI configuration uses JSON and stores arguments as an array rather than a shell string:

```json
{
  "schema_version": 1,
  "working_directory": "/opt/example/current",
  "user": "example",
  "group": "example",
  "argv": ["/opt/example/current/bin/example", "--token", "complete value"],
  "environment": {"API_TOKEN": "complete value"}
}
```

Preserve native formats for existing files. Do not convert TOML, JSON, INI, YAML, env files,
systemd units, certificates, private keys, or scripts merely to make formats uniform.

The canonical bundle layout is:

```text
<timestamp>-<hostname>-deploy/
├── REPORT.md
├── manifest.json
├── checksums.sha256
├── config/
│   ├── application/
│   ├── environment/
│   ├── credentials/
│   └── generated/
├── systemd/
├── scripts/
│   ├── application/
│   ├── reproduce.sh
│   └── rollback.sh
└── evidence/
    ├── deployment-contract.json
    ├── host-before.json
    ├── host-after.json
    ├── final-gate.json
    ├── final-outputs.json
    └── deployment-evidence.json
```

Omit unavailable optional evidence and empty optional subdirectories. The first five evidence
files preserve the exact frozen deployment inputs and results; `deployment-evidence.json` is the
separately redacted, optional `$test-report` handoff. `manifest.json` uses schema v1 with
`kind=deployment_report_bundle`, deployment status and target, `report=REPORT.md`, and one entry per
captured or generated artifact. `checksums.sha256` covers every file except itself. Build under a
sibling temporary directory, verify the manifest coverage and every checksum, then atomically
rename the complete folder. Use mode `0700` for directories and scripts, and `0600` for other
files.

`REPORT.md` changes the old `关键配置` section to `配置`. It lists service, type, purpose, relative
bundle file, server source, and SHA-256; it never repeats configuration content. Reproduction and
rollback sections link to `scripts/reproduce.sh` and `scripts/rollback.sh`.

For an SSH deployment, build the expanded bundle only in task-local scratch space, then publish it
to `deployment.report_remote_dir` through strict host-key verification. Upload to a sibling
temporary directory, reject symlinks, verify full `checksums.sha256` coverage, enforce the bundle
permissions, and atomically rename the folder. On the server, create
`<bundle-name>.tar.gz` beside the expanded folder and verify that its embedded checksum manifest
matches the published folder. Keep the server archive at `0600`.

Download the server-created archive to `report.local_dir` over strict SSH. Write a uniquely named
`.partial` file at `0600`, verify the server-reported byte size and SHA-256, and atomically rename it
to `<bundle-name>.tar.gz`. Before publication, stream-verify every regular file against the embedded
checksum manifest and reject links, special files, unsafe paths, duplicates, missing entries, and
unlisted files. Never overwrite a different existing remote folder/archive or local archive; an
identical verified artifact may be reused to make retries idempotent. The server keeps the expanded
folder and compressed archive for audit, while the local final delivery is the compressed archive
containing the folder root. Compression/download failures do not roll back the application because
they occur after health adjudication; report the delivery failure, retain the remote evidence, and
retry. Remove task-local expanded/raw artifacts only after all three retained artifacts are
verified.

## Program output contract

Declare operationally important outputs for units in `deployment.service_units` and
`alertd.service`. Collect declarations from the user request, effective systemd properties,
application configuration, and
resolved startup arguments before freezing the contract. Verify them later through read-only
runtime evidence; never scan an entire filesystem to discover outputs.

| Field | Type | Default | Valid values | Source | Why configurable |
|---|---|---|---|---|---|
| `service` | string | required | a unit in this deployment or `alertd.service` | deployment contract | output ownership varies per service |
| `kind` | enum | required | `log`, `data`, `dump`, `archive`, `shared_memory`, `other` | application semantics | output purpose varies per application |
| `sink` | enum | required | `file`, `directory`, `glob`, `journald`, `syslog`, `other` | effective configuration | output mechanism varies per deployment |
| `path` | absolute path/glob or null | null for logical sinks | resolved absolute path or safe absolute glob | user/systemd/application config | installation layout varies |
| `locator` | string or null | null for filesystem sinks | concrete query entry point | effective logging config | logical sink access varies |
| `source` | string | required | non-secret provenance label | contract collection | auditors need to trace the value |
| `evidence` | enum | required | `configured`, `observed`, `inferred` | collection method | confidence differs by evidence |
| `required` | boolean | `true` when explicitly configured; `false` when only observed | boolean | declaration origin | release policy differs by output |
| `readiness` | enum | derived from sink | `exists`, `matches`, `writable_parent`, `active_sink` | output lifecycle | readiness semantics differ by output |
| `rotation` | string | `unknown` | complete policy or `unknown` | proven configuration | rotation policy varies operationally |
| `retention` | string | `unknown` | complete policy or `unknown` | proven configuration | retention policy varies operationally |

Resolve environment variables, systemd specifiers, and relative paths before freezing. Reject an
unresolved path; obtain a concrete value before mutation. Apply
these readiness rules:

- `file`, `directory`, and POSIX SHM declarations use `exists`, or `writable_parent` only when the
  application is documented to create the output lazily.
- `glob` uses `matches`, or `writable_parent` for a documented delayed first match. Restrict the
  glob to one named parent directory and return at most 100 matches.
- `journald` and `syslog` use `active_sink`, have a null `path`, and provide a usable `locator`.
  An empty journal is not a failure when the effective sink and query path are valid.
- Only report rotation or retention when configuration proves it. Use `unknown` instead of
  inference.
- Classify named `/dev/shm` objects opened through writable descriptors or present in a target
  process map as `shared_memory`. Merge observations with the matching service declaration; keep
  the descriptor evidence when both descriptor and map evidence exist. Report an undeclared object
  as optional and observed. Preserve a mapped `(deleted)` object as audit evidence.
- Do not scan `/dev/shm`, read SHM contents, or attempt System V SHM attribution.

After the observation window, a failed required readiness check fails the output gate and invokes
the frozen application rollback. A missing optional or runtime-observed output is a warning. In v3
and v4, a deployment unit without a declaration is also a warning; v2 retains the historical
full-unit coverage requirement. Never delete an output during rollback; retain failed-release
outputs in the final report as audit evidence.

## Business service inventory

Treat a service as custom only when its resolved unit file remains under `/etc/systemd/system`.
Exclude symlinks resolving into `/usr/lib/systemd` or `/lib/systemd`, plus configured infrastructure
units. Include disabled, inactive, failed, and oneshot custom units in inventory and topology output.

Use unit enablement and type to classify expected health:

- Require enabled long-running units to be active with a live main/cgroup process.
- Accept inactive successful oneshot units unless the frozen contract explicitly requires activity.
- Always report disabled/inactive units; do not silently call them healthy.
- Put every business unit in the CPU table. Use `inactive/not-applicable` when it has no running task.

## Hard gates

Treat these as default hard gates. Abort before mutation when any condition fails unless an
explicit user deployment requirement directly conflicts with that gate. Never infer an override;
freeze and report the failed evidence, user requirement, accepted risk, and unavailable guarantees
without claiming that the gate passed.

1. Verify the SSH host through the configured known-hosts file. Never use
   `StrictHostKeyChecking=no`, `accept-new`, or `/dev/null`.
2. Verify Amazon Linux 2023 and `aarch64`.
3. Resolve every repository target to an immutable full commit; reject a dirty or mismatched build.
4. Enumerate every changed path and its rollback action; reject irreversible changes.
5. Stage artifacts and retained rollback versions while preserving at least the configured free
   percentage on every affected filesystem.
6. Verify artifact architecture, hashes, file ownership/mode, unit/config syntax, and
   deployment-related core tests. Record unavailable external-environment tests and unrelated tests
   as warnings.
7. Verify minimum `alertd` observability: the service is active, config and state are readable, and
   state is fresh. Record existing business alerts, collector failures, process gaps, and journal
   coverage gaps as baseline warnings.
8. Require explicit CPU affinity or network binding instructions before changing either. Default to
   observation only.
9. Resolve every declared required program output. After the health window, fail the release when
   a required output does not satisfy its readiness rule; warn for optional outputs and uncovered
   units.

Log the frozen plan and proceed without confirmation when no critical ambiguity remains.

## Atomic deployment and rollback

Stage a new immutable release directory without touching `current`. Snapshot old artifacts,
symlink targets, unit files, drop-ins, config files, ownership, modes, and SHA-256 values into the
transaction directory. Refuse deployment if any active mutable file cannot be enumerated.

Validate the staged release, then atomically replace the `current` symlink and configuration files.
Run `systemd-analyze verify`, `systemctl daemon-reload`, and the contract's restart/start commands.
Reload `alertd` only after its new config passes `alertd --check-config`.

Observe for at least 300 seconds. Compare with the saved baseline and roll back when alertd becomes
unavailable or stale, state stops advancing, a required service exits, or an issue is new or
worsened. Do not attribute an unchanged baseline warning to this deployment. Restore files and
symlinks atomically, reload systemd, restart the old release, and record whether recovery
succeeded. Never
hide a rollback failure. Do not remove logs, dumps, archives, shared memory, or business data during
rollback; record any outputs left by the failed version.

Keep the current and previous successful releases by default. Delete older releases only after a
successful observation window and only when they are outside the frozen rollback set.

## Alertd contract

If `alertd` is absent, clone its configured repository, resolve its target to a full commit, read
`Cargo.toml` `rust-version`, select an Alpine Rust builder image, and pin the pulled image by digest.
Build on the ARM64 target host inside Docker without installing a host Rust toolchain. Deploy the
binary and config through the same versioned/rollback process, then run `--check-config` and
`--send-test` as allowed by the user's delivery setup.

Give every business unit a journal check so coverage is machine-verifiable. Give enabled,
long-running services a process check with a stable, non-secret cmdline matcher. Add SHM progress or
other application checks only when their ABI/semantics are explicit. Check oneshot unit results
directly because `alertd` has no native systemd-state collector.

Define minimum observability as all of the following:

- `alertd.service` is active.
- `state.json` exists and continues to advance within two configured collection intervals.
- Configuration and state are readable.

Abort before application mutation only when minimum observability fails. Record non-`ok` checks,
collection failures, unhealthy required units, and process/journal coverage gaps as structured
baseline warnings. Post-deployment and rollback gates compare stable `code + subject` issue keys,
severity, and counts against that baseline; unchanged warnings are inherited, while new or worsened
issues fail. Preserve any explicit user override as failed evidence with its accepted risk and
unavailable guarantee.

Collect delivery evidence separately from the deployment contract and health gates. New evidence
uses schema version 2 and contains provider, static endpoint, complete webhook URL, token/secret
environment variable names, EnvironmentFile paths, complete signing secret, signing-secret
presence, Alertd commit, collection time, status, and warnings. Accept schema v1 only to render
historical reports, where the missing signing-secret value is explicitly `无法确认`. Store this
temporary JSON with mode `0600`; remove it after the remote folder, remote archive, and local
archive are verified. A collection failure is a report warning and never independently triggers
rollback.

For the current DingTalk delivery implementation, the static webhook URL is
`https://oapi.dingtalk.com/robot/send?access_token=<URL-encoded token>`. Store delivery evidence,
including the complete signing secret, in `config/generated/alertd-delivery.json` and reference it
from the report configuration index. Dynamic `timestamp` and `sign` values are generated for each
delivery and are not static configuration or evidence fields.

## Test-context evidence

After the final deployment, rollback, or failed-action snapshot, emit a supplementary JSON object
for the independent `test-report` Skill. This artifact is an audit output, not a deployment gate;
its absence is a report warning and never changes rollback behavior.

Use schema version 1:

```json
{
  "schema_version": 1,
  "kind": "deployment_test_context",
  "generated_at": "RFC3339 timestamp",
  "deployment_status": "succeeded|failed|rolled_back",
  "target": {"host": "deploy.example", "user": "root", "port": 22},
  "subject": {
    "repositories": [
      {"role": "application", "url": "git@example:team/repo.git", "target": "main", "commit": "full commit"}
    ],
    "artifacts": [
      {"name": "application", "sha256": "64-hex digest", "repository_commit": "full commit"}
    ]
  },
  "environment": {
    "captured_at": "RFC3339 timestamp",
    "machine": {},
    "cpu": {},
    "memory": {},
    "storage_summary": {},
    "network": {},
    "services": []
  },
  "key_config": [],
  "runtime": {"health": {}, "program_outputs": {}},
  "source": {"contract_schema_version": 4, "before_captured_at": null, "after_captured_at": null, "sha256": {}},
  "warnings": []
}
```

Use the final post-action snapshot when available and otherwise the pre-deployment snapshot. Keep
full repository commits and artifact hashes. Reduce storage to aggregate size, used, and available
bytes. Preserve health failures, warnings, and program-output evidence because they help interpret
later system tests.

Apply strict redaction to this supplementary artifact and omit every field or scalar containing an
Alertd webhook, `access_token`, or signing-secret material. Do not include the dedicated Alertd
delivery evidence, `changes`, `reproduce`, `rollback`, or `irreversible_changes`. Hash each source
JSON file so the consumer can identify the exact evidence inputs without copying their sensitive
contents.

## Evidence and report content

Label resource attribution as one of:

- `configured`: explicit systemd affinity, application option, or config value.
- `observed`: sampled task CPU, kernel socket, route, or interface counter.
- `inferred`: conclusion from unit arguments or routing; state the basis.
- `unknown`: insufficient evidence, including unobservable DPDK/raw-socket ownership.

Keep topology, configured/effective allowed CPUs, and sampled CPUs in the snapshot. In the Markdown
CPU table, show one row per logical CPU and only services sampled on that CPU; omit the
allowed/configured-service presentation column and group units without a sampled CPU into the final
`未运行/不适用` row. For networking, map kernel sockets to cgroup PIDs and route remote peers to
interfaces where possible. Present the result as one row per interface listing its attributed
services, evidence, and basis; group unattributed services into one `unknown` row.

The final deployment bundle is a trusted handoff artifact and performs no content redaction inside
captured or generated configuration files. Preserve complete passwords, tokens, API keys,
credentials, authorization values, signing secrets, certificates, private keys, URI userinfo, and
sensitive command arguments. `REPORT.md` references those files and does not duplicate their
contents. Read only explicitly identified fields needed by deployed services and Alertd; never dump
an entire process environment or unrelated secret store.

Keep raw values out of host snapshots, health/output results, ordinary logs, terminal output, and
supplementary test context. Store the remote expanded bundle directories and scripts with mode
`0700`, its ordinary files with mode `0600`, and both remote/local `.tar.gz` archives with mode
`0600`. Delete temporary raw evidence only after the server folder, server archive, and downloaded
archive are verified.

Inspect writable file descriptors only by their `/proc/<pid>/fd` metadata. Record regular files and
ignore read-only descriptors, sockets, pipes, anonymous descriptors, and `/dev/null`; never read
file contents. Read `/proc/<pid>/maps` only to associate named POSIX SHM paths with the owning
service. Redact sensitive path or locator parameters before storing evidence.

In `REPORT.md`, aggregate persistent filesystem capacity by normalized source and omit
individual device, filesystem-type, and mount-path rows. Exclude virtual or memory-backed
filesystems such as tmpfs, devtmpfs, proc, sysfs, cgroup, and overlay. Keep the detailed snapshot
for capacity gates; the reduced table is a report-only presentation rule.

Apply the same report-only reduction to program outputs without changing the contract or output
result schema. Preserve the complete output-check JSON. The Markdown brief must render these items
as seven-column key details with `服务`, `类型 / Sink`, `路径 / 入口`, `查询命令`, `来源 / 证据`,
`必需 / 状态`, and `大小 / 轮转 / 保留`: every contract declaration, every required failure, every unready item,
every configured-but-undeclared warning, and any other abnormal status. A normal mapped `(deleted)`
POSIX SHM object is not abnormal by itself.

Derive query commands only while rendering the report. For a `log` with a file, directory, or glob
path, render `lnav <shell-quoted-path>` and keep a glob as one literal argument for lnav. When a log
has only a logical locator, render `<locator> | lnav`; reuse a locator that already invokes lnav.
For a non-log output, render its locator unchanged or `—` when none exists. Do not invent commands
for SHM, dump, data, or other outputs. Commands have target-server-local semantics and are never
executed by the Skill. lnav is an operator prerequisite: do not check, install, warn about, or gate
deployment on its availability. Preserve complete locator parameters under the trusted-report
policy and rely on Markdown table escaping for command separators.

Group all remaining healthy optional runtime discoveries into one row per service. Report category
counts for logs, data, dumps, archives, shared memory, hugepages, DPDK, and other outputs; include
the total object count, known aggregate size, and no more than two representative paths. Normalize
high-cardinality paths such as `/dev/hugepages/*` and `/run/dpdk/*`. Render a glob or other
multi-match declaration once with its match count and known aggregate size. Summarize mapped/open
SHM evidence using unique process counts, permission sets, and writable-FD counts without listing
individual PIDs.
