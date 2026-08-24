---
name: deploy
description: Safely inspect, automatically deploy, update, reproduce, or roll back native systemd applications on Amazon Linux 2023 ARM64 servers over SSH. Use when Codex must report host disk, memory, network, and CPU topology before a deployment; freeze a natural-language request into an auditable deployment contract; deploy with atomic application-level rollback and alertd health gates; verify program output paths, POSIX shared memory, and logical log sinks; attribute business services to CPUs and network interfaces; or produce a redacted Markdown deployment brief with repository, target, commit, effective configuration, program outputs, reproduction, and rollback steps. Uses one automatic workflow without a default confirmation checkpoint; does not deploy Docker applications or estimate disk growth.
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
├── scripts/                         # Collects evidence and evaluates health/output gates.
├── assets/report-template.md        # Provides the Markdown deployment brief structure.
├── tests/test_tools.py              # Covers collectors, gates, redaction, and report rendering.
└── agents/openai.yaml               # Supplies Codex UI metadata.
```

## Establish the contract

Read [references/deployment-contract.md](references/deployment-contract.md) completely before any
deployment work. Apply its configuration schema, business-unit definition, hard gates, rollback
rules, `alertd` contract, evidence labels, and redaction policy.

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
effective deployment values. Add only operationally important build, startup, path, logging,
CPU/network, and health values to `key_config`; redact secrets.

Collect `program_outputs` for each unit in this deployment and for `alertd.service` from the user
request, application configuration definitions and effective values, resolved startup arguments,
and effective systemd output/directory properties. Resolve every path and systemd specifier before
freezing. Represent journald/syslog as logical sinks with query locators, not invented files. Do not
scan the filesystem to guess outputs. Limit runtime discovery to writable regular file descriptors
and named POSIX SHM observed in target-service `/proc/<pid>/maps`. Do not scan `/dev/shm`, read SHM
contents, or claim System V SHM ownership.

Write the frozen JSON contract described by the reference into task-local scratch space. Estimate
the final free percentage after build staging, the new release, and retained rollback releases.
Abort if any affected filesystem would fall below the configured percentage or if the estimate is
not defensible.

## Establish monitoring before application mutation

Inventory `alertd` without changing the host. If absent, include its bootstrap as a separate,
rollback-covered transaction before the application transaction:

1. Resolve the configured `alertd` target to a full commit.
2. Read `Cargo.toml` `rust-version`; pull the matching Alpine Rust image on the ARM64 host and
   record its resolved digest.
3. Build with `cargo build --release --locked` inside the container. Do not install host Rust.
4. Verify architecture and SHA-256, stage a versioned release, validate config, install the unit,
   and start it atomically.
5. Require pre-provisioned delivery environment variables. Never read or report their values.

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
without declarations are warnings in schema v3.
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
context without secret values.

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

## Produce the deployment brief

Collect a post-action snapshot even after failure or rollback when SSH remains available. Use the
provided template and renderer:

```bash
python3 <skill-root>/scripts/render_report.py \
  --before <scratch>/before.json \
  --after <scratch>/after.json \
  --contract <scratch>/contract.json \
  --gate <scratch>/final-gate.json \
  --outputs <scratch>/final-outputs.json \
  --status <succeeded|failed|rolled_back> \
  --output <local-report>.md
```

Verify that every business unit appears in the CPU table, including inactive/oneshot units; every
repository has URL, requested target, full commit, and available build/artifact digests; key config
shows source and redacted effective value; and reproduction/rollback steps use the immutable
commit. Verify that every declared program output appears in the program output table, including
its configured path or logical query locator, runtime status, and proven
rotation/retention policy or `unknown`. Keep every contract declaration, failed or unready output,
configuration warning, and other anomaly in the six-column key-output table. Group healthy optional
runtime discoveries by service and category instead of listing every object. Show object counts,
known total size, and at most two representative paths per service; normalize high-cardinality
hugepage and DPDK paths to path families. Summarize multi-process SHM evidence by process count,
permission set, and writable-FD count without listing PIDs. This compaction applies only to the
Markdown report; preserve the complete output-check JSON as audit evidence.

Classify observed `/dev/shm` objects as `shared_memory`; merge mapped/open evidence into an existing
declaration instead of duplicating it. A healthy optional SHM belongs in the per-service summary,
while declared, failed, unready, or otherwise anomalous SHM remains in key details. Show only an
aggregate of persistent filesystem capacity in the machine section, not individual devices,
filesystem types, or mount paths.

Copy the completed report to the configured server report directory through strict SSH. Upload to
a temporary name, set controlled ownership/mode, and atomically rename it. Preserve failed and
rolled-back reports as audit evidence. Return the terminal summary and local Markdown file.

Do not estimate disk growth. Do not claim database rollback, DPDK/raw-socket attribution, CPU
pinning, or network ownership without evidence.
