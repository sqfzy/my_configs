---
name: deploy
description: Safely inspect, automatically deploy, update, reproduce, or roll back native systemd applications on Amazon Linux 2023 ARM64 servers over SSH. Use when Codex must report host disk, memory, network, and CPU topology before a deployment; freeze a natural-language request into an auditable deployment contract; deploy with atomic application-level rollback and alertd health gates; verify program output paths, POSIX shared memory, and logical log sinks; attribute business services to CPUs and network interfaces; or produce a complete trusted deployment bundle containing the Markdown report, native configuration files, systemd units, scripts, credentials, checksums, and reproduction evidence, archive it on the SSH host, and download it locally. Uses one automatic workflow without a default confirmation checkpoint; does not deploy Docker applications or estimate disk growth.
---

# Deploy

Deploy only after turning the request into a complete, immutable contract. Prefer an explicit abort
over an inferred production change. Keep machine data, application data, and orchestration logic
separate.

Follow an explicit user deployment requirement when it directly conflicts with this Skill's
defaults, procedures, or hard gates. Do not infer an override from silence, missing information, or
ambiguous wording. Freeze every deviation with its reason, risk, and unavailable guarantees, and
report it without claiming that the overridden gate passed. Continue to obey higher-priority
system, developer, safety, and tool constraints.

## Skill layout

```text
deploy/
├── SKILL.md                         # Orchestrates inspection, deployment, rollback, and reporting.
├── references/deployment-contract.md # Defines configuration, frozen contract, and hard gates.
├── scripts/                         # Implements deterministic evidence and bundle operations.
│   ├── build_report_bundle.py       # Captures enumerated files and atomically publishes the bundle.
│   ├── collect_host.py              # Inventories the target host without mutation.
│   ├── check_alertd.py              # Evaluates baseline, postdeploy, and rollback health.
│   ├── check_outputs.py             # Verifies declared outputs and runtime discoveries.
│   ├── inspect_alertd_delivery.py   # Captures complete trusted Alertd delivery configuration.
│   ├── export_test_context.py       # Exports the separately redacted test handoff.
│   ├── publish_report_bundle.py     # Publishes, remotely archives, and downloads the bundle.
│   └── render_report.py             # Renders REPORT.md and historical single-file reports.
├── assets/report-template.md        # Provides the bundle's REPORT.md structure.
├── tests/test_tools.py              # Covers collectors, gates, bundle integrity, and report rendering.
└── agents/openai.yaml               # Supplies Codex UI metadata.
```

## Establish the contract

Read [references/deployment-contract.md](references/deployment-contract.md) completely before any
deployment work. Apply its configuration schema, business-unit definition, hard gates, rollback
rules, `alertd` contract, evidence labels, and report-content policy.

Treat an explicit deploy, update, or rollback request as authorization to execute the frozen
transaction without a default confirmation checkpoint. Treat inspection, explanation, review, and
drafting requests as read-only. Ask only when the target host, Git target, change surface, or
rollback path has multiple materially reasonable interpretations. Honor a user-requested pause as
a one-deployment checkpoint; do not introduce a named mode.

Require the natural-language request to resolve the target host, repository and Git target,
systemd unit, build/test commands, release layout, mutable paths, key configuration, health
semantics, and exact rollback. Record an empty CPU/network binding when none is requested; do not
invent affinity or interface assignments.

## Collect the pre-deployment snapshot

Use a real known-hosts file and strict host verification. Never pass `StrictHostKeyChecking=no`,
`accept-new`, or `/dev/null`.

```bash
python3 <skill-root>/scripts/collect_host.py \
  --host <host> --user <user> --port <port> \
  --known-hosts <known-hosts> \
  --sample-seconds <5-60> \
  --output <scratch>/before.json \
  --require-supported
```

Inspect the snapshot before planning mutations. Confirm Amazon Linux 2023, `aarch64`, systemd,
all affected filesystems, every custom business unit, effective CPU allowances, observed CPUs,
network evidence, and inactive/oneshot services. Treat `unknown` attribution as unknown.

Resolve every requested Git branch/tag with `git ls-remote`, freeze the full 40-character commit,
fetch that commit, and verify it before building. Inspect the code's configuration definitions and
effective deployment values. Build the `configurations` closure from each deployed unit and
`alertd.service`: unit files, drop-ins, EnvironmentFiles, application configs, credentials,
certificates, private keys, and scripts referenced by systemd or effective application config.
Enumerate files explicitly; do not scan the host. Preserve native file formats and bytes.

Represent CLI, process environment, CPU/network binding, and other non-file effective settings as
generated JSON configuration. Store arguments as an `argv` array and environment as an object so
boundaries remain exact. Include complete values without masking, hashing, truncation, omission, or
presence-only markers.

Collect `program_outputs` for each unit in this deployment and for `alertd.service` from the user
request, application configuration definitions and effective values, resolved startup arguments,
and effective systemd output/directory properties. Resolve every path and systemd specifier before
freezing. Represent journald/syslog as logical sinks with query locators, not invented files. Do not
scan the filesystem to guess outputs. Limit runtime discovery to writable regular file descriptors
and named POSIX SHM observed in target-service `/proc/<pid>/maps`. Do not scan `/dev/shm`, read SHM
contents, or claim System V SHM ownership.

Write the schema-v4 frozen JSON contract described by the reference into task-local scratch space
with mode `0600`; generated configuration content may contain raw credentials. Never print the
contract or its secret values to ordinary logs or terminal output. Estimate the final free
percentage after build staging, the new release, and retained rollback releases.
Abort if any affected filesystem would fall below the configured percentage or if the estimate is
not defensible.

## Pass the independent release review

Before any remote mutation, invoke `$release-gate` separately for every repository in the frozen
deployment contract with `event=deploy`, the current release task's explicitly selected review
mode when one exists, and the exact current-to-frozen range. Without a task override, omit
`CODEX_RELEASE_REVIEW_MODE` so each exact candidate's `.codex/release-gate.toml` or the built-in
fallback selects the mode. Follow the skill's target-selection, verdict, bypass, advisory, finding
ledger, failure, and rerun contracts. Record the repository, effective mode and source, exact
range, verdict or bypass, advisories, accepted exceptions, ledger synchronization, and elapsed time
in the deployment evidence.

If status `1` includes `Ledger sync required`, do not mutate the host. Put new findings in TODO by
default; allow an agent-approved P2/P3 only with concrete code, test, or project-intent evidence;
require explicit user approval before any P0/P1 ALLOW. Remove verified fixed TODOs and stale
ALLOWs. When the authorized source workflow permits advancing the target, modify only
`.codex/release-gate.md`, create `chore(release-gate): sync findings`, then resolve the new immutable
commit and rebuild the entire frozen deployment contract before rerunning every repository gate.
Otherwise return the canonical entries and require the repository owner to update the ledger. Do
not deploy the pre-sync target or reuse its verdict.

## Establish monitoring before application mutation

Inventory `alertd` without changing the host. If absent, include its bootstrap as a separate,
rollback-covered transaction before the application transaction:

1. Resolve the configured `alertd` target to a full commit.
2. Read `Cargo.toml` `rust-version`; pull the matching Alpine Rust image on the ARM64 host and
   record its resolved digest.
3. Build with `cargo build --release --locked` inside the container. Do not install host Rust.
4. Verify architecture and SHA-256, stage a versioned release, validate config, install the unit,
   and start it atomically.
5. Require pre-provisioned delivery environment variables. Collect the complete token and signing
   secret through the dedicated delivery inspector for the final trusted report only.

Generate journal coverage for every business unit. Add a stable process check for each enabled,
long-running service and explicit SHM/application checks when their semantics are known. Check
oneshot results directly. Validate with `alertd --check-config`, reload with `SIGHUP`, wait for at
least two collection cycles, then run the baseline gate:

```bash
python3 <skill-root>/scripts/check_alertd.py \
  --snapshot <scratch>/before.json \
  --known-hosts <known-hosts> \
  --config-path <alertd-config> --state-dir <alertd-state-dir> \
  --phase baseline --once \
  --output <scratch>/baseline-gate.json
```

Require minimum `alertd` observability before application mutation: the service must be active,
configuration and state must be readable, and state must be fresh. Record existing business
alerts, collector failures, process gaps, and journal coverage gaps as baseline warnings rather
than blockers. Preserve the structured baseline so later gates can distinguish inherited issues
from new or worsened problems.

Collect the effective Alertd webhook after monitoring is established:

```bash
python3 <skill-root>/scripts/inspect_alertd_delivery.py \
  --snapshot <scratch>/before.json \
  --known-hosts <known-hosts> \
  --config-path <alertd-config> \
  --output <scratch>/alertd-delivery.json
```

The inspector reads the running process token and signing secret. It constructs the complete static
DingTalk webhook URL and records both raw values in delivery evidence schema v2. It must not record
dynamic `timestamp` or `sign`, or print either credential to logs or terminal output. Keep the
evidence file at mode `0600`. Treat unavailable delivery evidence as a report warning, not a
deployment or rollback gate.

After monitoring is established and before application mutation, record the declared output
baseline with a read-only check:

```bash
python3 <skill-root>/scripts/check_outputs.py \
  --snapshot <scratch>/before.json \
  --contract <scratch>/contract.json \
  --known-hosts <known-hosts> \
  --phase baseline \
  --output <scratch>/baseline-outputs.json
```

Use the baseline to distinguish pre-existing outputs from files created by the new release. A
missing new-release output may make the checker return status 1, but is not itself a pre-mutation
gate. Unresolved declared paths or an unverifiable required parent/sink remain hard gates; units
without declarations are warnings in schema v3 and v4.
Never read output contents.

## Stage, switch, and roll back

Stage without modifying the active release. Run declared tests and config checks. Verify artifact
architecture, hash, ownership, mode, unit syntax, and every path against the frozen contract.
Snapshot active artifacts, unit/drop-in/config bytes, metadata, hashes, and symlink targets in the
transaction directory.

Record the exact frozen contract and continue immediately when hard gates pass or an explicit user
requirement overrides a failed gate under the precedence rule above.

Atomically install configuration and replace the `current` symlink. Run `systemd-analyze verify`,
`systemctl daemon-reload`, and the contract's restart/start sequence. Update and validate `alertd`
configuration, then reload it. Record each command, exit status, duration, and relevant service
context. Keep secret values out of ordinary command logs even when the final trusted report
contains them.

Run the post-deployment gate for at least five minutes:

```bash
python3 <skill-root>/scripts/check_alertd.py \
  --snapshot <scratch>/after.json \
  --known-hosts <known-hosts> \
  --config-path <alertd-config> --state-dir <alertd-state-dir> \
  --baseline <scratch>/baseline-gate.json \
  --phase postdeploy --observe-seconds <300-1800> \
  --output <scratch>/postdeploy-gate.json
```

After the five-minute health window passes, collect the post-action snapshot and verify outputs:

```bash
python3 <skill-root>/scripts/check_outputs.py \
  --snapshot <scratch>/after.json \
  --contract <scratch>/contract.json \
  --known-hosts <known-hosts> \
  --phase postdeploy \
  --output <scratch>/postdeploy-outputs.json
```

On a health or required-output failure, stop observation and execute the frozen rollback
automatically. Compare post-deployment and rollback health with the saved baseline: unchanged
baseline warnings remain warnings, while alertd unavailability, stale/non-advancing state, a newly
exited required service, or any new or worsened issue fails the gate. Restore files and symlinks
atomically, reload systemd, restart the old release, and run `rollback` health and output gates.
Report rollback failure prominently; never mask it as deployment failure. Never delete logs,
dumps, shared memory, or business data during rollback; include failed-release outputs in the final
audit report.

After success, keep the current and previous successful release by default. Remove only releases
outside the frozen rollback set and only after the observation window passes.

## Produce the deployment bundle

Collect a post-action snapshot even after failure or rollback when SSH remains available. First
export the versioned, redacted context consumed optionally by `$test-report`:

```bash
python3 <skill-root>/scripts/export_test_context.py \
  --before <scratch>/before.json \
  --after <scratch>/after.json \
  --contract <scratch>/contract.json \
  --gate <scratch>/final-gate.json \
  --outputs <scratch>/final-outputs.json \
  --status <succeeded|failed|rolled_back> \
  --output <scratch>/deployment-evidence.json
```

The test-context artifact is supplementary and never changes deployment or rollback gates. Include
it under `evidence/` when available. It must follow the evidence contract reference and must
not contain the Alertd webhook, access token, signing secret, rollback commands, or other secrets.
This restriction applies only to the supplementary test context, not the trusted deployment bundle.

Build the complete bundle with the deterministic builder:

```bash
python3 <skill-root>/scripts/build_report_bundle.py \
  --before <scratch>/before.json \
  --after <scratch>/after.json \
  --contract <scratch>/contract.json \
  --gate <scratch>/final-gate.json \
  --outputs <scratch>/final-outputs.json \
  --alertd-delivery <scratch>/alertd-delivery.json \
  --test-context <scratch>/deployment-evidence.json \
  --status <succeeded|failed|rolled_back> \
  --output-dir <scratch>/<YYYYMMDD-HHMMSSZ>-<hostname>-deploy
```

Generate the UTC timestamp once when bundle creation starts. Put it at the beginning of the folder
name using `YYYYMMDD-HHMMSSZ` so ordinary lexical sorting is chronological. Normalize the hostname
to lowercase ASCII letters, digits, dots, underscores, and hyphens, replacing other characters
with `-`. The builder stages a sibling temporary directory, captures only enumerated files, writes
generated JSON, `REPORT.md`, `manifest.json`, `checksums.sha256`, `scripts/reproduce.sh`, and
`scripts/rollback.sh`. It also preserves the frozen contract, before/after snapshots, final health
gate, complete output-check result, and optional redacted test context under `evidence/`; it verifies
all hashes, then atomically publishes the folder.

Verify that every business unit appears in the CPU table, including inactive/oneshot units; every
repository has URL, requested target, full commit, and available build/artifact digests. The
`配置` section must reference every captured or generated configuration file by relative path,
server source, purpose, and SHA-256; it must not repeat configuration values inline. Reproduction
and rollback sections reference their packaged scripts, whose commands use the immutable commit.
Verify that every declared program
output appears in the program output table, including
its configured path or logical sink entry, target-server-local query command, runtime status, and proven
rotation/retention policy or `unknown`. Keep every contract declaration, failed or unready output,
configuration warning, and other anomaly in the seven-column key-output table. For a `log` with a
file, directory, or glob path, render `lnav <shell-quoted-path>`; keep a glob as one literal argument
for lnav. For a logical log sink, render `<locator> | lnav`, unless the locator already invokes lnav.
For a non-log output, show its locator unchanged or `—` when none exists. These commands are local to
the target server and are report guidance only. Treat lnav as an operator prerequisite: do not check,
install, warn about, or gate deployment on it. Group healthy optional
runtime discoveries by service and category instead of listing every object. Show object counts,
known total size, and at most two representative paths per service; normalize high-cardinality
hugepage and DPDK paths to path families. Summarize multi-process SHM evidence by process count,
permission set, and writable-FD count without listing PIDs. This compaction applies only to the
Markdown report; preserve the complete output-check JSON as audit evidence.

Present CPU and network ownership from the resource perspective. The CPU table has one row per
logical CPU and a single `服务` column containing only services actually observed on that CPU during
the sample window; group units with no sampled CPU in the final `未运行/不适用` row. Do not render an
allowed/configured-service column. The network-attribution table has one row per interface and
lists the services attributed to that interface with their evidence and basis. Group all services
without attribution into one `unknown` row instead of repeating one row per service.

Store Alertd provider metadata, complete static webhook URL including `access_token`, credential
environment names and EnvironmentFile paths, complete signing secret, Alertd commit, evidence time,
and collection status in `config/generated/alertd-delivery.json`; reference that file from the
configuration index. Dynamic `timestamp` and `sign` are not static configuration. Keep these values
out of health/output JSON, ordinary logs, terminal summary, and supplementary test context.

Classify observed `/dev/shm` objects as `shared_memory`; merge mapped/open evidence into an existing
declaration instead of duplicating it. A healthy optional SHM belongs in the per-service summary,
while declared, failed, unready, or otherwise anomalous SHM remains in key details. Show only an
aggregate of persistent filesystem capacity in the machine section, not individual devices,
filesystem types, or mount paths.

Publish the completed folder, create its archive on the SSH server, and download that archive:

```bash
python3 <skill-root>/scripts/publish_report_bundle.py \
  --bundle-dir <scratch>/<YYYYMMDD-HHMMSSZ>-<hostname>-deploy \
  --contract <scratch>/contract.json \
  --local-dir <local-report-dir> \
  --timeout-seconds <300-7200>
```

The publisher stages the uncompressed folder under a temporary name in the configured server
report directory, verifies `checksums.sha256`, fixes directories/scripts to `0700` and ordinary
files to `0600`, then atomically publishes the folder. The SSH server must then create
`<bundle-name>.tar.gz` beside it, verify that the archive contains the expected checksum manifest,
and keep the archive at `0600`. Download the archive over the same strict SSH identity into a local
`.partial` file, verify its server-reported size and SHA-256, then atomically rename it to
`<local-report-dir>/<bundle-name>.tar.gz` with mode `0600`. Before the rename, reject unsafe paths,
links, special files, extra files, missing files, and any file that fails the embedded
`checksums.sha256` manifest.

Never replace an existing remote folder, remote archive, or local archive with different content.
Reuse it only after its bundle identity is proven. Preserve failed and rolled-back bundles as audit
evidence. An archive or download failure is a report-delivery failure and does not roll back an
otherwise completed application deployment; retain the remote folder and retry the idempotent
publication step. Delete the task-local expanded folder, raw contract, and delivery evidence only
after the remote folder, remote archive, and local archive are all verified. Return the terminal
summary with the remote folder, remote archive, local archive, archive SHA-256, and byte size.

Do not estimate disk growth. Do not claim database rollback, DPDK/raw-socket attribution, CPU
pinning, or network ownership without evidence.
