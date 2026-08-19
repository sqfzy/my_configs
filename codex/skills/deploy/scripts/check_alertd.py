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


def evaluate_state(state: dict[str, Any], configured_checks: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    states = state.get("checks", {})
    if not isinstance(states, dict):
        return ["alertd state.checks is not an object"]
    expected_names = {str(check.get("name")) for check in configured_checks if check.get("enabled", True)}
    missing = sorted(name for name in expected_names if name not in states)
    if missing:
        reasons.append(f"alertd state has not observed checks: {', '.join(missing)}")
    for name, check_state in states.items():
        if not isinstance(check_state, dict):
            reasons.append(f"alertd state {name} is malformed")
            continue
        severity = str(check_state.get("severity", "ok"))
        failures = integer_or_zero(check_state.get("collection_failures", 0))
        if severity != "ok" or check_state.get("pending_since") or check_state.get("firing_since"):
            reasons.append(f"alertd check {name} is unhealthy severity={severity}")
        if failures:
            reasons.append(f"alertd check {name} has collection_failures={failures}")
    return reasons


def evaluate_process_coverage(snapshot: dict[str, Any], config: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
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
            reasons.append(f"enabled long-running unit lacks process coverage: {service['unit']}")
    return reasons


def expected_unit_health(
    snapshot: dict[str, Any],
    units: dict[str, dict[str, Any]],
    required_units: set[str],
) -> list[str]:
    reasons: list[str] = []
    service_index = {str(service["unit"]): service for service in snapshot.get("services", [])}
    for unit in sorted(required_units):
        actual = units.get(unit)
        service = service_index.get(unit, {})
        if actual is None:
            reasons.append(f"required unit status is missing: {unit}")
            continue
        is_oneshot = service.get("service_type") == "oneshot"
        remains = service.get("remain_after_exit") == "yes"
        if is_oneshot and not remains:
            if actual["result"] not in {"success", ""}:
                reasons.append(f"required oneshot unit failed: {unit} result={actual['result']}")
        elif actual["active_state"] != "active":
            reasons.append(
                f"required unit is not active: {unit} state={actual['active_state']}/{actual['sub_state']}"
            )
        elif not is_oneshot and actual["main_pid"] <= 0:
            reasons.append(f"required long-running unit has no MainPID: {unit}")
    return reasons


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
    reasons: list[str] = []
    alertd_unit = parse_properties(sections.get("alertd_unit", ""))
    if alertd_unit.get("LoadState") != "loaded" or alertd_unit.get("ActiveState") != "active":
        reasons.append(
            "alertd.service is not active "
            f"state={alertd_unit.get('LoadState', 'unknown')}/{alertd_unit.get('ActiveState', 'unknown')}"
        )
    try:
        config = load_toml(sections.get("config", ""))
    except (ValueError, tomllib.TOMLDecodeError) as error:
        config = {}
        reasons.append(f"alertd config is unavailable or invalid: {error}")
    state_text = sections.get("state", "")
    try:
        state = json.loads(state_text) if state_text else {}
    except json.JSONDecodeError as error:
        state = {}
        reasons.append(f"alertd state.json is invalid: {error}")
    configured_checks = config.get("checks", [])
    covered = journal_coverage(config)
    missing_journal = sorted(set(business_units(snapshot)) - covered)
    if missing_journal:
        reasons.append(f"business units lack journal coverage: {', '.join(missing_journal)}")
    reasons.extend(evaluate_process_coverage(snapshot, config))
    reasons.extend(evaluate_state(state, configured_checks))
    reasons.extend(expected_unit_health(snapshot, parse_units(sections.get("units", "")), required_units))
    mtime, size = parse_state_stat(sections.get("state_stat", ""))
    observed_at = integer_or_zero(sections.get("observed_at", "")) or int(time.time())
    try:
        interval = parse_duration(str(config.get("runtime", {}).get("interval", "30s")))
    except ValueError as error:
        interval = 30.0
        reasons.append(str(error))
    maximum_age = max(10.0, interval * 2.0)
    state_age = observed_at - mtime if mtime else None
    if mtime <= 0 or size <= 0:
        reasons.append("alertd state.json is missing or empty")
    elif state_age is None or state_age > maximum_age:
        reasons.append(f"alertd state.json is stale age_seconds={state_age} max={maximum_age:g}")
    return {
        "observed_at": dt.datetime.fromtimestamp(observed_at, dt.timezone.utc).isoformat(),
        "state_mtime": mtime,
        "state_size": size,
        "state_age_seconds": state_age,
        "healthy": not reasons,
        "reasons": reasons,
    }


def observe(
    args: argparse.Namespace,
    snapshot: dict[str, Any],
    known_hosts: Path,
) -> dict[str, Any]:
    required_units = set(args.required_unit or default_required_units(snapshot))
    script = remote_script(args.config_path, args.state_dir, business_units(snapshot))
    polls: list[dict[str, Any]] = []
    started_at = dt.datetime.now(dt.timezone.utc)
    deadline = time.monotonic() if args.once else time.monotonic() + args.observe_seconds
    initial_mtime: int | None = None
    while True:
        sections, duration = run_remote(snapshot, known_hosts, script)
        poll = evaluate_poll(snapshot, sections, required_units)
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
    healthy = all(poll["healthy"] for poll in polls)
    if not args.once and polls and polls[-1]["state_mtime"] <= (initial_mtime or 0):
        healthy = False
        polls[-1]["reasons"].append("alertd state.json did not advance during observation window")
        polls[-1]["healthy"] = False
    return {
        "schema_version": 1,
        "phase": args.phase,
        "started_at": started_at.isoformat(),
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "requested_observe_seconds": 0 if args.once else args.observe_seconds,
        "required_units": sorted(required_units),
        "healthy": healthy,
        "polls": polls,
    }


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
        result = observe(args, snapshot, known_hosts)
        write_result(result, args.output)
        final_reasons = result["polls"][-1]["reasons"] if result["polls"] else []
        print(
            f"phase={result['phase']} healthy={str(result['healthy']).lower()} "
            f"polls={len(result['polls'])} reasons={len(final_reasons)} "
            f"result={args.output.expanduser().resolve()}"
        )
        return 0 if result["healthy"] else 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, tomllib.TOMLDecodeError, subprocess.TimeoutExpired) as error:
        LOG.error("alertd gate failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
