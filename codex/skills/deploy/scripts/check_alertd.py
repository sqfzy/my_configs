#!/usr/bin/env python3
"""Evaluate alertd and systemd health through a strict read-only SSH gate."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any


LOG = logging.getLogger("deploy.check_alertd")
SECTION_PREFIX = "__DEPLOY_SECTION__ "
UNIT_PATTERN = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--known-hosts", required=True)
    parser.add_argument("--config-path", default="/etc/alertd/alertd.toml")
    parser.add_argument("--state-dir", default="/var/lib/alertd")
    parser.add_argument("--required-unit", action="append", default=[])
    parser.add_argument("--observe-seconds", type=int, default=300)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--phase", choices=["baseline", "postdeploy", "rollback"], default="postdeploy")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_args(args: argparse.Namespace, snapshot: dict[str, Any]) -> Path:
    if args.phase == "baseline" and args.baseline is not None:
        raise ValueError("baseline phase cannot compare against another baseline")
    if not args.once and not 300 <= args.observe_seconds <= 1800:
        raise ValueError("observe seconds must be in 300..=1800")
    if not 5 <= args.poll_seconds <= 60:
        raise ValueError("poll seconds must be in 5..=60")
    for value in (args.config_path, args.state_dir):
        if not value.startswith("/") or "\n" in value:
            raise ValueError(f"remote path must be absolute: {value!r}")
    known_hosts = Path(args.known_hosts).expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError(f"known-hosts file is missing: {known_hosts}")
    target = snapshot.get("target", {})
    if not target.get("host") or not target.get("user"):
        raise ValueError("snapshot target is incomplete")
    for unit in business_units(snapshot) + args.required_unit:
        if not UNIT_PATTERN.fullmatch(unit):
            raise ValueError(f"invalid systemd unit: {unit!r}")
    return known_hosts


def load_baseline(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    baseline = load_json(path)
    if baseline.get("schema_version") != 2 or baseline.get("phase") != "baseline":
        raise ValueError("--baseline must be an alertd schema v2 baseline result")
    return baseline


def business_units(snapshot: dict[str, Any]) -> list[str]:
    return [str(service["unit"]) for service in snapshot.get("services", [])]


def default_required_units(snapshot: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for service in snapshot.get("services", []):
        enabled = service.get("unit_file_state") in {"enabled", "enabled-runtime"}
        long_running = service.get("service_type") != "oneshot" or service.get("remain_after_exit") == "yes"
        if enabled and long_running:
            result.append(str(service["unit"]))
    return sorted(result)


def remote_script(config_path: str, state_dir: str, units: list[str]) -> str:
    unit_values = " ".join(shlex.quote(unit) for unit in units)
    return f'''set -u
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
section observed_at
date +%s
section alertd_unit
systemctl show alertd.service --no-pager \
    -p LoadState -p ActiveState -p SubState -p Result -p MainPID 2>/dev/null || true
section state_stat
stat -c '%Y\037%s' {shlex.quote(state_dir + '/state.json')} 2>/dev/null || true
section state
cat {shlex.quote(state_dir + '/state.json')} 2>/dev/null || true
section config
cat {shlex.quote(config_path)} 2>/dev/null || true
section units
for unit in {unit_values}; do
    printf '%s\037' "$unit"
    systemctl show "$unit" --value -p ActiveState 2>/dev/null | tr -d '\n'
    printf '\037'
    systemctl show "$unit" --value -p SubState 2>/dev/null | tr -d '\n'
    printf '\037'
    systemctl show "$unit" --value -p Result 2>/dev/null | tr -d '\n'
    printf '\037'
    systemctl show "$unit" --value -p MainPID 2>/dev/null | tr -d '\n'
    printf '\n'
done
'''


def run_remote(
    snapshot: dict[str, Any],
    known_hosts: Path,
    script: str,
) -> tuple[dict[str, str], float]:
    target = snapshot["target"]
    destination = f"{target['user']}@{target['host']}"
    command = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "LogLevel=ERROR",
        "-p", str(target.get("port", 22)),
        destination,
        "bash -s",
    ]
    started = time.monotonic()
    result = subprocess.run(
        command,
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise RuntimeError(f"health probe failed after {elapsed:.3f}s: {result.stderr.strip()}")
    return split_sections(result.stdout), elapsed


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith(SECTION_PREFIX):
            current = line[len(SECTION_PREFIX):].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def parse_properties(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def parse_units(text: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        values = line.split("\x1f")
        if len(values) != 5:
            continue
        result[values[0]] = {
            "active_state": values[1],
            "sub_state": values[2],
            "result": values[3],
            "main_pid": integer_or_zero(values[4]),
        }
    return result


def integer_or_zero(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def parse_duration(value: str) -> float:
    match = re.fullmatch(r"(\d+)(ms|s|m|h)", value.strip())
    if not match:
        raise ValueError(f"invalid alertd duration: {value!r}")
    amount = int(match.group(1))
    return amount * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[match.group(2)]


def load_toml(text: str) -> dict[str, Any]:
    if not text:
        raise ValueError("alertd config is missing or empty")
    value = tomllib.loads(text)
    if not isinstance(value, dict):
        raise ValueError("alertd config is not an object")
    return value


def journal_coverage(config: dict[str, Any]) -> set[str]:
    covered: set[str] = set()
    for check in config.get("checks", []):
        if check.get("enabled", True) and check.get("type") == "journal":
            covered.update(str(unit) for unit in check.get("units", []))
    return covered


def process_checks(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        check for check in config.get("checks", [])
        if check.get("enabled", True) and check.get("type") == "process"
    ]


def issue(code: str, subject: str, message: str, **values: Any) -> dict[str, Any]:
    return {"code": code, "subject": subject, "message": message, **values}


def evaluate_state(state: dict[str, Any], configured_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    states = state.get("checks", {})
    if not isinstance(states, dict):
        return [issue("state_checks_invalid", "state.json", "alertd state.checks is not an object")]
    expected_names = {str(check.get("name")) for check in configured_checks if check.get("enabled", True)}
    missing = sorted(name for name in expected_names if name not in states)
    for name in missing:
        issues.append(issue("check_missing", name, f"alertd state has not observed check: {name}"))
    for name, check_state in states.items():
        if not isinstance(check_state, dict):
            issues.append(issue("check_state_invalid", str(name), f"alertd state {name} is malformed"))
            continue
        severity = str(check_state.get("severity", "ok"))
        failures = integer_or_zero(check_state.get("collection_failures", 0))
        if severity != "ok" or check_state.get("pending_since") or check_state.get("firing_since"):
            issues.append(issue(
                "check_unhealthy", str(name), f"alertd check {name} is unhealthy severity={severity}",
                severity=severity, severity_rank=severity_rank(severity),
            ))
        if failures:
            issues.append(issue(
                "collector_failures", str(name),
                f"alertd check {name} has collection_failures={failures}", count=failures,
            ))
    return issues


def severity_rank(value: str) -> int:
    return {"ok": 0, "info": 1, "warning": 2, "warn": 2, "critical": 3}.get(value.lower(), 2)


def evaluate_process_coverage(snapshot: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    checks = process_checks(config)
    for service in snapshot.get("services", []):
        enabled = service.get("unit_file_state") in {"enabled", "enabled-runtime"}
        long_running = service.get("service_type") != "oneshot"
        if not enabled or not long_running:
            continue
        stem = str(service["unit"]).removesuffix(".service")
        command = str(service.get("exec_start", ""))
        covered = any(
            str(check.get("name", "")) in {stem, service["unit"]}
            or str(check.get("cmdline_contains", "")) in command
            for check in checks
            if check.get("cmdline_contains")
        )
        if not covered:
            unit = str(service["unit"])
            issues.append(issue(
                "process_coverage_missing", unit,
                f"enabled long-running unit lacks process coverage: {unit}",
            ))
    return issues


def expected_unit_health(
    snapshot: dict[str, Any],
    units: dict[str, dict[str, Any]],
    required_units: set[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    service_index = {str(service["unit"]): service for service in snapshot.get("services", [])}
    for unit in sorted(required_units):
        actual = units.get(unit)
        service = service_index.get(unit, {})
        if actual is None:
            issues.append(issue("unit_status_missing", unit, f"required unit status is missing: {unit}"))
            continue
        is_oneshot = service.get("service_type") == "oneshot"
        remains = service.get("remain_after_exit") == "yes"
        if is_oneshot and not remains:
            if actual["result"] not in {"success", ""}:
                issues.append(issue(
                    "required_unit_unhealthy", unit,
                    f"required oneshot unit failed: {unit} result={actual['result']}", count=1,
                ))
        elif actual["active_state"] != "active":
            issues.append(issue(
                "required_unit_unhealthy", unit,
                f"required unit is not active: {unit} state={actual['active_state']}/{actual['sub_state']}",
                count=1,
            ))
        elif not is_oneshot and actual["main_pid"] <= 0:
            issues.append(issue(
                "required_unit_unhealthy", unit,
                f"required long-running unit has no MainPID: {unit}", count=1,
            ))
    return issues


def parse_state_stat(text: str) -> tuple[int, int]:
    values = text.split("\x1f")
    if len(values) != 2:
        return 0, 0
    return integer_or_zero(values[0]), integer_or_zero(values[1])


def evaluate_poll(
    snapshot: dict[str, Any],
    sections: dict[str, str],
    required_units: set[str],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    alertd_unit = parse_properties(sections.get("alertd_unit", ""))
    if alertd_unit.get("LoadState") != "loaded" or alertd_unit.get("ActiveState") != "active":
        issues.append(issue(
            "alertd_unavailable", "alertd.service",
            "alertd.service is not active "
            f"state={alertd_unit.get('LoadState', 'unknown')}/{alertd_unit.get('ActiveState', 'unknown')}"
        ))
    try:
        config = load_toml(sections.get("config", ""))
    except (ValueError, tomllib.TOMLDecodeError) as error:
        config = {}
        issues.append(issue(
            "config_unreadable", "alertd.toml", f"alertd config is unavailable or invalid: {error}"
        ))
    if not isinstance(config.get("checks", []), list) or not isinstance(config.get("runtime", {}), dict):
        issues.append(issue(
            "config_unreadable", "alertd.toml", "alertd config has invalid checks or runtime structure"
        ))
        config = {}
    state_text = sections.get("state", "")
    try:
        state = json.loads(state_text) if state_text else {}
    except json.JSONDecodeError as error:
        state = {}
        issues.append(issue("state_unreadable", "state.json", f"alertd state.json is invalid: {error}"))
    if not isinstance(state, dict):
        issues.append(issue("state_unreadable", "state.json", "alertd state.json is not an object"))
        state = {}
    configured_checks = config.get("checks", [])
    covered = journal_coverage(config)
    missing_journal = sorted(set(business_units(snapshot)) - covered)
    for unit in missing_journal:
        issues.append(issue(
            "journal_coverage_missing", unit, f"business unit lacks journal coverage: {unit}"
        ))
    issues.extend(evaluate_process_coverage(snapshot, config))
    issues.extend(evaluate_state(state, configured_checks))
    issues.extend(expected_unit_health(snapshot, parse_units(sections.get("units", "")), required_units))
    mtime, size = parse_state_stat(sections.get("state_stat", ""))
    observed_at = integer_or_zero(sections.get("observed_at", "")) or int(time.time())
    try:
        interval = parse_duration(str(config.get("runtime", {}).get("interval", "30s")))
    except ValueError as error:
        interval = 30.0
        issues.append(issue("interval_invalid", "alertd.toml", str(error)))
    maximum_age = max(10.0, interval * 2.0)
    state_age = observed_at - mtime if mtime else None
    if mtime <= 0 or size <= 0:
        issues.append(issue("state_unreadable", "state.json", "alertd state.json is missing or empty"))
    elif state_age is None or state_age > maximum_age:
        issues.append(issue(
            "state_stale", "state.json",
            f"alertd state.json is stale age_seconds={state_age} max={maximum_age:g}",
            count=integer_or_zero(state_age),
        ))
    return {
        "observed_at": dt.datetime.fromtimestamp(observed_at, dt.timezone.utc).isoformat(),
        "state_mtime": mtime,
        "state_size": size,
        "state_age_seconds": state_age,
        "healthy": not issues,
        "reasons": [value["message"] for value in issues],
        "issues": issues,
    }


OBSERVABILITY_CODES = {
    "alertd_unavailable", "config_unreadable", "state_unreadable", "state_stale",
    "state_not_advancing", "interval_invalid", "state_checks_invalid",
}


def issue_key(value: dict[str, Any]) -> tuple[str, str]:
    return str(value.get("code", "unknown")), str(value.get("subject", "unknown"))


def issue_worsened(current: dict[str, Any], baseline: dict[str, Any]) -> bool:
    return (
        integer_or_zero(current.get("severity_rank")) > integer_or_zero(baseline.get("severity_rank"))
        or integer_or_zero(current.get("count")) > integer_or_zero(baseline.get("count"))
    )


def baseline_issues(baseline: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    issues = baseline.get("issues", [])
    return {issue_key(value): value for value in issues if isinstance(value, dict)}


def classify_issues(
    phase: str, issues: list[dict[str, Any]], baseline: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    inherited: list[dict[str, Any]] = []
    previous = baseline_issues(baseline)
    for value in issues:
        if value["code"] in OBSERVABILITY_CODES:
            failures.append({**value, "comparison": "blocking"})
        elif phase == "baseline":
            warnings.append({**value, "comparison": "baseline"})
        elif not baseline:
            failures.append({**value, "comparison": "new"})
        elif issue_key(value) not in previous:
            failures.append({**value, "comparison": "new"})
        elif issue_worsened(value, previous[issue_key(value)]):
            failures.append({**value, "comparison": "worsened"})
        else:
            inherited_value = {**value, "comparison": "inherited"}
            warnings.append(inherited_value)
            inherited.append(inherited_value)
    return failures, warnings, inherited


def decorate_poll(poll: dict[str, Any], phase: str, baseline: dict[str, Any]) -> None:
    failures, warnings, inherited = classify_issues(phase, poll["issues"], baseline)
    poll["failures"] = failures
    poll["warnings"] = warnings
    poll["inherited_warnings"] = inherited
    poll["healthy"] = not failures
    poll["clean"] = not poll["issues"]


def observe(
    args: argparse.Namespace,
    snapshot: dict[str, Any],
    known_hosts: Path,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = baseline or {}
    required_units = set(args.required_unit or default_required_units(snapshot))
    script = remote_script(args.config_path, args.state_dir, business_units(snapshot))
    polls: list[dict[str, Any]] = []
    started_at = dt.datetime.now(dt.timezone.utc)
    deadline = time.monotonic() if args.once else time.monotonic() + args.observe_seconds
    initial_mtime: int | None = None
    while True:
        sections, duration = run_remote(snapshot, known_hosts, script)
        poll = evaluate_poll(snapshot, sections, required_units)
        decorate_poll(poll, args.phase, baseline)
        poll["probe_duration_seconds"] = round(duration, 3)
        polls.append(poll)
        initial_mtime = poll["state_mtime"] if initial_mtime is None else initial_mtime
        LOG.info(
            "health poll phase=%s healthy=%s state_age=%s duration_seconds=%.3f",
            args.phase,
            poll["healthy"],
            poll["state_age_seconds"],
            duration,
        )
        if not poll["healthy"] or args.once or time.monotonic() >= deadline:
            break
        time.sleep(min(args.poll_seconds, max(0.0, deadline - time.monotonic())))
    if not args.once and polls and polls[-1]["state_mtime"] <= (initial_mtime or 0):
        value = issue(
            "state_not_advancing", "state.json",
            "alertd state.json did not advance during observation window",
        )
        polls[-1]["issues"].append(value)
        polls[-1]["reasons"].append(value["message"])
        decorate_poll(polls[-1], args.phase, baseline)
    failures = unique_issues(value for poll in polls for value in poll["failures"])
    warnings = unique_issues(value for poll in polls for value in poll["warnings"])
    inherited = unique_issues(value for poll in polls for value in poll["inherited_warnings"])
    issues = unique_issues(value for poll in polls for value in poll["issues"])
    return {
        "schema_version": 2,
        "phase": args.phase,
        "started_at": started_at.isoformat(),
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "requested_observe_seconds": 0 if args.once else args.observe_seconds,
        "required_units": sorted(required_units),
        "healthy": not failures,
        "clean": not issues,
        "issues": issues,
        "failures": failures,
        "warnings": warnings,
        "inherited_warnings": inherited,
        "baseline_clean": baseline.get("clean") if baseline else None,
        "polls": polls,
    }


def unique_issues(values: Any) -> list[dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for value in values:
        result[issue_key(value)] = value
    return list(result.values())


def write_result(result: dict[str, Any], output: Path) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    LOG.info("health result written path=%s", output)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        snapshot = load_json(args.snapshot)
        known_hosts = validate_args(args, snapshot)
        baseline = load_baseline(args.baseline)
        result = observe(args, snapshot, known_hosts, baseline)
        write_result(result, args.output)
        print(
            f"phase={result['phase']} healthy={str(result['healthy']).lower()} "
            f"clean={str(result['clean']).lower()} polls={len(result['polls'])} "
            f"failures={len(result['failures'])} warnings={len(result['warnings'])} "
            f"result={args.output.expanduser().resolve()}"
        )
        return 0 if result["healthy"] else 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, tomllib.TOMLDecodeError, subprocess.TimeoutExpired) as error:
        LOG.error("alertd gate failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
