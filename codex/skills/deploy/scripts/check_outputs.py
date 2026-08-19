#!/usr/bin/env python3
"""Verify declared program outputs through strict, read-only SSH probes."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import fnmatch
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any

LOG = logging.getLogger("deploy.check_outputs")
SECTION_PREFIX = "__DEPLOY_SECTION__ "
UNIT_PATTERN = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")
SENSITIVE_ARGUMENT = re.compile(
    r"(?i)(--?(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)(?:=|\s+))([^\s,;]+)"
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)=)([^\s,;&]+)"
)
URI_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)
KINDS = {"log", "data", "dump", "archive", "shared_memory", "other"}
SINKS = {"file", "directory", "glob", "journald", "syslog", "other"}
EVIDENCE = {"configured", "observed", "inferred"}
READINESS = {"exists", "matches", "writable_parent", "active_sink"}
FILESYSTEM_SINKS = {"file", "directory", "glob"}
LOGICAL_SINKS = {"journald", "syslog", "other"}
MAX_GLOB_MATCHES = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--known-hosts", required=True, type=Path)
    parser.add_argument("--phase", choices=["baseline", "postdeploy", "rollback"], default="postdeploy")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def deployment_units(contract: dict[str, Any]) -> list[str]:
    units = [str(unit) for unit in contract.get("deployment", {}).get("service_units", [])]
    return sorted({*units, "alertd.service"})


def validate_inputs(
    snapshot: dict[str, Any], contract: dict[str, Any], known_hosts_path: Path
) -> tuple[Path, list[dict[str, Any]], list[str]]:
    if contract.get("schema_version") != 2:
        raise ValueError("output checks require contract schema_version 2")
    target = snapshot.get("target", {})
    if not target.get("host") or not target.get("user"):
        raise ValueError("snapshot target is incomplete")
    contract_target = contract.get("target", {})
    target_identity = (target.get("host"), target.get("user"), int(target.get("port", 22)))
    contract_identity = (
        contract_target.get("host"), contract_target.get("user"), int(contract_target.get("port", 22))
    )
    if target_identity != contract_identity:
        raise ValueError("snapshot target does not match frozen contract target")
    known_hosts = known_hosts_path.expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError(f"known-hosts file is missing: {known_hosts}")
    frozen_known_hosts = Path(str(contract_target.get("known_hosts", ""))).expanduser().resolve()
    if known_hosts != frozen_known_hosts:
        raise ValueError("known-hosts path does not match frozen contract target")
    units = deployment_units(contract)
    if not units or any(not UNIT_PATTERN.fullmatch(unit) for unit in units):
        raise ValueError("deployment contains an invalid systemd unit")
    outputs = contract.get("program_outputs")
    if not isinstance(outputs, list):
        raise ValueError("contract program_outputs must be a list")
    for index, output in enumerate(outputs):
        validate_output(index, output, set(units))
    covered = {str(output["service"]) for output in outputs}
    missing = sorted(set(units) - covered)
    if missing:
        raise ValueError(f"program_outputs does not cover units: {', '.join(missing)}")
    return known_hosts, outputs, units


def validate_output(index: int, output: Any, units: set[str]) -> None:
    if not isinstance(output, dict):
        raise ValueError(f"program_outputs[{index}] must be an object")
    service = str(output.get("service", ""))
    if service not in units:
        raise ValueError(f"program_outputs[{index}] service is outside this deployment: {service!r}")
    if output.get("kind") not in KINDS:
        raise ValueError(f"program_outputs[{index}] has invalid kind")
    sink = output.get("sink")
    if sink not in SINKS:
        raise ValueError(f"program_outputs[{index}] has invalid sink")
    if output.get("evidence") not in EVIDENCE:
        raise ValueError(f"program_outputs[{index}] has invalid evidence")
    if not isinstance(output.get("required"), bool):
        raise ValueError(f"program_outputs[{index}] required must be boolean")
    readiness = output.get("readiness")
    if readiness not in READINESS:
        raise ValueError(f"program_outputs[{index}] has invalid readiness")
    source = output.get("source")
    if not isinstance(source, str) or not source.strip() or has_control_character(source):
        raise ValueError(f"program_outputs[{index}] source must be non-empty")
    for name in ("rotation", "retention"):
        if not isinstance(output.get(name), str) or not output[name].strip():
            raise ValueError(f"program_outputs[{index}] {name} must be a string or 'unknown'")
    validate_location(index, output, sink, readiness)


def validate_location(index: int, output: dict[str, Any], sink: str, readiness: str) -> None:
    path = output.get("path")
    locator = output.get("locator")
    if sink in FILESYSTEM_SINKS:
        if not isinstance(path, str) or not path.startswith("/") or has_control_character(path):
            raise ValueError(f"program_outputs[{index}] needs an absolute path")
        if any(marker in path for marker in ("$", "%", "~")):
            raise ValueError(f"program_outputs[{index}] path contains an unresolved value")
        if locator is not None:
            raise ValueError(f"program_outputs[{index}] filesystem sink locator must be null")
        if sink == "glob":
            validate_glob(index, path)
            if readiness not in {"matches", "writable_parent"}:
                raise ValueError(f"program_outputs[{index}] glob readiness is incompatible")
        elif readiness not in {"exists", "writable_parent"}:
            raise ValueError(f"program_outputs[{index}] filesystem readiness is incompatible")
        return
    if path is not None:
        raise ValueError(f"program_outputs[{index}] logical sink path must be null")
    if not isinstance(locator, str) or not locator.strip() or has_control_character(locator):
        raise ValueError(f"program_outputs[{index}] logical sink needs a locator")
    if readiness != "active_sink":
        raise ValueError(f"program_outputs[{index}] logical sink readiness must be active_sink")
    if sink == "journald" and (
        not locator.strip().startswith("journalctl ") or str(output["service"]) not in locator
    ):
        raise ValueError(f"program_outputs[{index}] journald locator must query its service")


def validate_glob(index: int, value: str) -> None:
    path = PurePosixPath(value)
    if not any(character in path.name for character in "*?["):
        raise ValueError(f"program_outputs[{index}] glob has no pattern")
    if any(any(character in part for character in "*?[") for part in path.parts[:-1]):
        raise ValueError(f"program_outputs[{index}] glob may vary only within one parent directory")
    if "**" in value or any(part == ".." for part in path.parts):
        raise ValueError(f"program_outputs[{index}] glob is recursive or escapes its parent")


def has_control_character(value: str) -> bool:
    return any(ord(character) < 32 for character in value)


def shell_functions() -> str:
    return r'''set -u
section() { printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }
b64() { printf '%s' "$1" | base64 | tr -d '\n'; }
property_b64() {
    local unit="$1" property="$2" value
    value="$(systemctl show "$unit" --value -p "$property" 2>/dev/null | tr -d '\n' || true)"
    b64 "$value"
}
service_user() {
    local value
    value="$(systemctl show "$1" --value -p User 2>/dev/null | tr -d '\n' || true)"
    printf '%s' "${value:-root}"
}
is_writable() {
    local user="$1" candidate="$2"
    if [ ! -e "$candidate" ]; then printf 'no'; return; fi
    if [ "$(id -u)" -eq 0 ] && [ "$user" != "root" ] && command -v runuser >/dev/null 2>&1; then
        if runuser -u "$user" -- test -w "$candidate" 2>/dev/null; then printf 'yes'; else printf 'no'; fi
    elif test -w "$candidate"; then printf 'yes'; else printf 'no'; fi
}
metadata() {
    local index="$1" state="$2" display="$3" probe="$4" writable="$5"
    local file_type owner group mode size mtime mount device fstype
    file_type="$(stat -Lc '%F' -- "$probe" 2>/dev/null || true)"
    owner="$(stat -Lc '%U' -- "$probe" 2>/dev/null || true)"
    group="$(stat -Lc '%G' -- "$probe" 2>/dev/null || true)"
    mode="$(stat -Lc '%a' -- "$probe" 2>/dev/null || true)"
    size="$(stat -Lc '%s' -- "$probe" 2>/dev/null || true)"
    mtime="$(stat -Lc '%Y' -- "$probe" 2>/dev/null || true)"
    mount="$(findmnt -n -o TARGET -T "$probe" 2>/dev/null | head -n1 || true)"
    device="$(findmnt -n -o SOURCE -T "$probe" 2>/dev/null | head -n1 || true)"
    fstype="$(findmnt -n -o FSTYPE -T "$probe" 2>/dev/null | head -n1 || true)"
    printf '%s\037%s\037' "$index" "$state"; b64 "$display"; printf '\037'
    b64 "$file_type"; printf '\037'; b64 "$owner"; printf '\037'; b64 "$group"; printf '\037'
    printf '%s\037%s\037%s\037' "$mode" "$size" "$mtime"; b64 "$mount"; printf '\037'
    b64 "$device"; printf '\037'; b64 "$fstype"; printf '\037%s\n' "$writable"
}
probe_exact() {
    local index="$1" service="$2" sink="$3" path="$4" user candidate exists_state writable
    user="$(service_user "$service")"
    if [ "$sink" = directory ]; then candidate="$path"; else candidate="$(dirname -- "$path")"; fi
    writable="$(is_writable "$user" "$candidate")"
    exists_state=missing
    if [ "$sink" = directory ] && [ -d "$path" ]; then exists_state=exists; fi
    if [ "$sink" = file ] && [ -f "$path" ]; then exists_state=exists; fi
    if [ "$exists_state" = exists ]; then metadata "$index" exists "$path" "$path" "$writable"
    else
        printf '%s\037missing\037' "$index"; b64 "$path"; printf '\037\037\037\037\037\037\037\037\037\037%s\n' "$writable"
    fi
}
probe_glob() {
    local index="$1" service="$2" parent="$3" pattern="$4" user writable match count=0
    user="$(service_user "$service")"; writable="$(is_writable "$user" "$parent")"
    while IFS= read -r -d '' match; do
        count=$((count + 1))
        if [ "$count" -le 100 ]; then metadata "$index" exists "$match" "$match" "$writable"; fi
        if [ "$count" -ge 101 ]; then break; fi
    done < <(find "$parent" -mindepth 1 -maxdepth 1 -name "$pattern" -print0 2>/dev/null)
    printf '%s\037summary\037\037\037\037\037\037%s\037\037\037\037\037%s\n' "$index" "$count" "$writable"
}
'''


def remote_script(outputs: list[dict[str, Any]], units: list[str]) -> str:
    lines = [shell_functions(), "section units"]
    properties = [
        "LoadState", "StandardOutput", "StandardError", "LogsDirectory", "StateDirectory",
        "RuntimeDirectory", "CacheDirectory", "User", "Group",
    ]
    for unit in units:
        fields = [f"b64 {shlex.quote(unit)}"] + [
            f"property_b64 {shlex.quote(unit)} {shlex.quote(prop)}" for prop in properties
        ]
        lines.append("printf '%s' $(" + fields[0] + ")")
        for field in fields[1:]:
            lines.append("printf '\\037%s' $(" + field + ")")
        lines.append(
            "if command -v journalctl >/dev/null 2>&1 && "
            f"journalctl --no-pager -n 0 -u {shlex.quote(unit)} >/dev/null 2>&1; "
            "then printf '\\037'; b64 yes; else printf '\\037'; b64 no; fi"
        )
        lines.append("printf '\\n'")
    lines.append("section declared")
    for index, output in enumerate(outputs):
        sink = str(output["sink"])
        if sink in {"file", "directory"}:
            lines.append(
                "probe_exact " + " ".join(
                    shlex.quote(str(value)) for value in (index, output["service"], sink, output["path"])
                )
            )
        elif sink == "glob":
            path = PurePosixPath(str(output["path"]))
            lines.append(
                "probe_glob " + " ".join(
                    shlex.quote(str(value)) for value in (index, output["service"], str(path.parent), path.name)
                )
            )
    lines.extend([
        "section fds",
        remote_fd_probe(units),
        "section shm_maps",
        remote_shm_map_probe([unit for unit in units if unit != "alertd.service"]),
    ])
    return "\n".join(lines) + "\n"


def remote_fd_probe(units: list[str]) -> str:
    units_text = " ".join(shlex.quote(unit) for unit in units)
    return f'''for unit in {units_text}; do
    cgroup="$(systemctl show "$unit" --value -p ControlGroup 2>/dev/null | tr -d '\n' || true)"
    [ -n "$cgroup" ] || continue
    while IFS= read -r pid; do
        case "$pid" in (''|*[!0-9]*) continue;; esac
        for fd in /proc/"$pid"/fd/*; do
            [ -e "$fd" ] || continue
            target="$(readlink "$fd" 2>/dev/null || true)"
            case "$target" in (/*) ;; (*) continue;; esac
            case "$target" in (/dev/null|/proc/*|/sys/*) continue;; esac
            [ -f "$fd" ] || continue
            flags="$(awk '$1 == "flags:" {{print $2}}' /proc/"$pid"/fdinfo/"${{fd##*/}}" 2>/dev/null || true)"
            case "$flags" in (''|*[!0-7]*) continue;; esac
            flags_value=$((8#$flags)); access_mode=$((flags_value & 3))
            [ "$access_mode" -eq 1 ] || [ "$access_mode" -eq 2 ] || continue
            printf '%s\037%s\037' "$unit" "$pid"; b64 "$target"; printf '\037'
            b64 "$(stat -Lc '%F' -- "$fd" 2>/dev/null || true)"; printf '\037'
            b64 "$(stat -Lc '%U' -- "$fd" 2>/dev/null || true)"; printf '\037'
            b64 "$(stat -Lc '%G' -- "$fd" 2>/dev/null || true)"; printf '\037'
            printf '%s\037%s\037%s\037' "$(stat -Lc '%a' -- "$fd" 2>/dev/null || true)" "$(stat -Lc '%s' -- "$fd" 2>/dev/null || true)" "$(stat -Lc '%Y' -- "$fd" 2>/dev/null || true)"
            b64 "$(findmnt -n -o TARGET -T "$fd" 2>/dev/null | head -n1 || true)"; printf '\037'
            b64 "$(findmnt -n -o SOURCE -T "$fd" 2>/dev/null | head -n1 || true)"; printf '\037'
            b64 "$(findmnt -n -o FSTYPE -T "$fd" 2>/dev/null | head -n1 || true)"; printf '\n'
        done
    done < <(find "/sys/fs/cgroup$cgroup" -name cgroup.procs -type f -exec cat {{}} + 2>/dev/null | sort -nu)
done'''


def remote_shm_map_probe(units: list[str]) -> str:
    units_text = " ".join(shlex.quote(unit) for unit in units)
    return f'''for unit in {units_text}; do
    cgroup="$(systemctl show "$unit" --value -p ControlGroup 2>/dev/null | tr -d '\n' || true)"
    [ -n "$cgroup" ] || continue
    while IFS= read -r pid; do
        case "$pid" in (''|*[!0-9]*) continue;; esac
        while read -r address permissions offset device inode pathname; do
            case "$pathname" in (/dev/shm/*) ;; (*) continue;; esac
            clean_path="${{pathname% (deleted)}}"
            map_file="/proc/$pid/map_files/$address"
            if [ -e "$clean_path" ]; then probe="$clean_path"; else probe="$map_file"; fi
            printf '%s\037%s\037' "$unit" "$pid"; b64 "$pathname"; printf '\037%s\037' "$permissions"
            b64 "$(stat -Lc '%F' -- "$probe" 2>/dev/null || true)"; printf '\037'
            b64 "$(stat -Lc '%U' -- "$probe" 2>/dev/null || true)"; printf '\037'
            b64 "$(stat -Lc '%G' -- "$probe" 2>/dev/null || true)"; printf '\037'
            printf '%s\037%s\037%s\037' "$(stat -Lc '%a' -- "$probe" 2>/dev/null || true)" "$(stat -Lc '%s' -- "$probe" 2>/dev/null || true)" "$(stat -Lc '%Y' -- "$probe" 2>/dev/null || true)"
            b64 "$(findmnt -n -o TARGET -T /dev/shm 2>/dev/null | head -n1 || true)"; printf '\037'
            b64 "$(findmnt -n -o SOURCE -T /dev/shm 2>/dev/null | head -n1 || true)"; printf '\037'
            b64 "$(findmnt -n -o FSTYPE -T /dev/shm 2>/dev/null | head -n1 || true)"; printf '\n'
        done < "/proc/$pid/maps" 2>/dev/null || true
    done < <(find "/sys/fs/cgroup$cgroup" -name cgroup.procs -type f -exec cat {{}} + 2>/dev/null | sort -nu)
done'''


def run_remote(snapshot: dict[str, Any], known_hosts: Path, script: str) -> tuple[dict[str, str], float]:
    target = snapshot["target"]
    command = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "LogLevel=ERROR", "-p", str(target.get("port", 22)),
        f"{target['user']}@{target['host']}", "bash -s",
    ]
    started = time.monotonic()
    result = subprocess.run(
        command, input=script, text=True, capture_output=True, timeout=60, check=False,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise RuntimeError(f"output probe failed after {elapsed:.3f}s: {result.stderr.strip()}")
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


def decode(value: str) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value, validate=True).decode("utf-8", errors="replace")
    except (ValueError, UnicodeError):
        return ""


def integer_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_units(text: str) -> dict[str, dict[str, str]]:
    names = [
        "load_state", "standard_output", "standard_error", "logs_directory", "state_directory",
        "runtime_directory", "cache_directory", "user", "group",
        "journal_query_available",
    ]
    result: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        fields = line.split("\x1f")
        if len(fields) != len(names) + 1:
            continue
        result[decode(fields[0])] = {name: decode(value) for name, value in zip(names, fields[1:])}
    return result


def metadata_from_fields(fields: list[str], offset: int = 0) -> dict[str, Any]:
    return {
        "path": redact(decode(fields[offset])),
        "file_type": decode(fields[offset + 1]) or "unknown",
        "owner": decode(fields[offset + 2]) or "unknown",
        "group": decode(fields[offset + 3]) or "unknown",
        "mode": fields[offset + 4] or "unknown",
        "size": integer_or_none(fields[offset + 5]),
        "mtime": integer_or_none(fields[offset + 6]),
        "mount_point": decode(fields[offset + 7]) or "unknown",
        "device": decode(fields[offset + 8]) or "unknown",
        "filesystem": decode(fields[offset + 9]) or "unknown",
    }


def parse_declared(text: str) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for line in text.splitlines():
        fields = line.split("\x1f")
        if len(fields) != 13:
            continue
        index = integer_or_none(fields[0])
        if index is None:
            continue
        record = result.setdefault(index, {"matches": [], "count": 0, "truncated": False, "writable": False})
        if fields[1] == "summary":
            count = integer_or_none(fields[7]) or 0
            record["count"] = count
            record["truncated"] = count > MAX_GLOB_MATCHES
            record["writable"] = fields[12] == "yes"
        else:
            metadata = metadata_from_fields(fields, 2)
            metadata["state"] = fields[1]
            record["matches"].append(metadata)
            record["count"] = max(record["count"], len(record["matches"]))
            record["writable"] = fields[12] == "yes"
    return result


def parse_fds(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line in text.splitlines():
        fields = line.split("\x1f")
        if len(fields) != 12:
            continue
        service = fields[0]
        metadata = metadata_from_fields(fields, 2)
        key = (service, metadata["path"])
        if key in seen:
            continue
        seen.add(key)
        result.append({"service": service, "pid": integer_or_none(fields[1]), **metadata})
    return result


def parse_shm_maps(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in text.splitlines():
        fields = line.split("\x1f")
        if len(fields) != 13:
            continue
        result.append({
            "service": fields[0],
            "pid": integer_or_none(fields[1]),
            "path": redact(decode(fields[2])),
            "mapping_permissions": fields[3] or "unknown",
            "file_type": decode(fields[4]) or "unknown",
            "owner": decode(fields[5]) or "unknown",
            "group": decode(fields[6]) or "unknown",
            "mode": fields[7] or "unknown",
            "size": integer_or_none(fields[8]),
            "mtime": integer_or_none(fields[9]),
            "mount_point": decode(fields[10]) or "unknown",
            "device": decode(fields[11]) or "unknown",
            "filesystem": decode(fields[12]) or "unknown",
        })
    return result


def sink_is_active(output: dict[str, Any], properties: dict[str, str]) -> bool:
    if properties.get("load_state") != "loaded":
        return False
    values = {properties.get("standard_output", ""), properties.get("standard_error", "")}
    if output["sink"] == "journald":
        configured = any(
            value in {"journal", "journal-or-kmsg", "kmsg", "kmsg-or-null"} for value in values
        )
        return configured and properties.get("journal_query_available") == "yes"
    if output["sink"] == "syslog":
        return any("syslog" in value for value in values)
    return True


def evaluate_declared(
    outputs: list[dict[str, Any]],
    probes: dict[int, dict[str, Any]],
    units: dict[str, dict[str, str]],
    shm_observations: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    declared: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    for index, output in enumerate(outputs):
        probe = probes.get(index, {"matches": [], "count": 0, "truncated": False, "writable": False})
        ready, state = readiness_state(output, probe, units.get(str(output["service"]), {}))
        rendered = sanitized_output(output)
        rendered.update({
            "ready": ready,
            "status": state,
            "matches": probe["matches"][:MAX_GLOB_MATCHES],
            "match_count": probe["count"],
            "truncated": probe["truncated"],
        })
        runtime_evidence = output_runtime_evidence(output, shm_observations or [])
        if runtime_evidence:
            rendered["runtime_evidence"] = runtime_evidence
        declared.append(rendered)
        if not ready:
            message = f"{output['service']} output {redact(output.get('path') or output.get('locator'))} is {state}"
            (failures if output["required"] else warnings).append(message)
    return declared, failures, warnings


def readiness_state(
    output: dict[str, Any], probe: dict[str, Any], properties: dict[str, str]
) -> tuple[bool, str]:
    readiness = output["readiness"]
    if readiness == "active_sink":
        active = sink_is_active(output, properties)
        return active, "active" if active else "inactive_sink"
    if readiness == "writable_parent":
        return bool(probe["writable"]), "writable_parent" if probe["writable"] else "unwritable_parent"
    if readiness == "matches":
        return probe["count"] > 0, "matches" if probe["count"] else "missing"
    exists = any(match.get("state") == "exists" for match in probe["matches"])
    return exists, "exists" if exists else "missing"


def sanitized_output(output: dict[str, Any]) -> dict[str, Any]:
    result = dict(output)
    for name in ("path", "locator", "source", "rotation", "retention"):
        if result.get(name) is not None:
            result[name] = redact(result[name])
    return result


def redact(value: Any) -> str:
    text = str(value)
    text = URI_USERINFO.sub(r"\1<redacted>@", text)
    text = SENSITIVE_ARGUMENT.sub(lambda match: f"{match.group(1)}<redacted>", text)
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}<redacted>", text)


def path_matches_output(path: str, output: dict[str, Any]) -> bool:
    configured = output.get("path")
    if not configured:
        return False
    clean_path = path.removesuffix(" (deleted)")
    if output["sink"] == "glob":
        return fnmatch.fnmatchcase(clean_path, str(configured))
    if output["sink"] == "directory":
        return clean_path == configured or clean_path.startswith(str(configured).rstrip("/") + "/")
    return clean_path == configured


def is_posix_shm_path(path: str) -> bool:
    return path.removesuffix(" (deleted)").startswith("/dev/shm/")


def shm_observation_key(observation: dict[str, Any]) -> tuple[str, str]:
    return str(observation["service"]), str(observation["path"]).removesuffix(" (deleted)")


def collect_shm_observations(
    file_descriptors: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    business_services: set[str] | None = None,
) -> list[dict[str, Any]]:
    observations: dict[tuple[str, str], dict[str, Any]] = {}
    for descriptor in file_descriptors:
        if business_services is not None and descriptor["service"] not in business_services:
            continue
        if not is_posix_shm_path(str(descriptor["path"])):
            continue
        observation = {
            **descriptor,
            "runtime_evidence": [f"open_writable pid={descriptor['pid']}"],
            "source": f"/proc/{descriptor['pid']}/fd",
            "status": "observed_open_writable",
        }
        key = shm_observation_key(observation)
        if key in observations:
            observations[key]["runtime_evidence"].extend(observation["runtime_evidence"])
        else:
            observations[key] = observation
    for mapping in mappings:
        if business_services is not None and mapping["service"] not in business_services:
            continue
        if not is_posix_shm_path(str(mapping["path"])):
            continue
        evidence = (
            f"mapped pid={mapping['pid']} permissions={mapping['mapping_permissions']}"
        )
        key = shm_observation_key(mapping)
        if key in observations:
            observations[key]["runtime_evidence"].append(evidence)
            continue
        status = "observed_mapped_deleted" if str(mapping["path"]).endswith(" (deleted)") else "observed_mapped"
        observations[key] = {
            **mapping,
            "runtime_evidence": [evidence],
            "source": f"/proc/{mapping['pid']}/maps",
            "status": status,
        }
    for observation in observations.values():
        observation["runtime_evidence"] = sorted(set(observation["runtime_evidence"]))
    return list(observations.values())


def output_runtime_evidence(
    output: dict[str, Any], observations: list[dict[str, Any]]
) -> list[str]:
    if output.get("kind") != "shared_memory":
        return []
    evidence: list[str] = []
    for observation in observations:
        if output["service"] != observation["service"]:
            continue
        if path_matches_output(str(observation["path"]), output):
            evidence.extend(str(value) for value in observation.get("runtime_evidence", []))
    return sorted(set(evidence))


def discover_outputs(
    outputs: list[dict[str, Any]],
    units: dict[str, dict[str, str]],
    file_descriptors: list[dict[str, Any]],
    shm_observations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for descriptor in file_descriptors:
        if is_posix_shm_path(str(descriptor["path"])):
            continue
        if any(
            output["service"] == descriptor["service"] and path_matches_output(descriptor["path"], output)
            for output in outputs
        ):
            continue
        discovered.append({
            "service": descriptor["service"], "kind": "other", "sink": "file",
            "path": descriptor["path"], "locator": None, "source": f"/proc/{descriptor['pid']}/fd",
            "evidence": "observed", "required": False, "readiness": "exists",
            "rotation": "unknown", "retention": "unknown", "ready": True, "status": "observed_open_writable",
            "matches": [descriptor], "match_count": 1, "truncated": False,
        })
    for observation in shm_observations or collect_shm_observations(file_descriptors, []):
        if any(
            output["service"] == observation["service"]
            and path_matches_output(str(observation["path"]), output)
            for output in outputs
        ):
            continue
        discovered.append({
            "service": observation["service"], "kind": "shared_memory", "sink": "file",
            "path": observation["path"], "locator": None, "source": observation["source"],
            "evidence": "observed", "required": False, "readiness": "exists",
            "rotation": "unknown", "retention": "unknown", "ready": True,
            "status": observation["status"], "runtime_evidence": observation["runtime_evidence"],
            "matches": [observation], "match_count": 1, "truncated": False,
        })
    discovered.extend(discover_systemd_sinks(outputs, units))
    discovered.extend(discover_systemd_directories(outputs, units))
    return discovered


def discover_systemd_sinks(
    outputs: list[dict[str, Any]], units: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for service, properties in units.items():
        values = {properties.get("standard_output", ""), properties.get("standard_error", "")}
        for sink in ("journald", "syslog"):
            active = (
                any(value in {"journal", "journal-or-kmsg", "kmsg", "kmsg-or-null"} for value in values)
                if sink == "journald" else any("syslog" in value for value in values)
            )
            if sink == "journald":
                active = active and properties.get("journal_query_available") == "yes"
            locator = f"journalctl -u {service}" if sink == "journald" else f"system logger for {service}"
            if not active or any(
                output["service"] == service and output["sink"] == sink for output in outputs
            ):
                continue
            discovered.append({
                "service": service, "kind": "log", "sink": sink, "path": None,
                "locator": locator, "source": "systemd StandardOutput/StandardError", "evidence": "configured",
                "required": False, "readiness": "active_sink", "rotation": "unknown", "retention": "unknown",
                "ready": True, "status": "active", "matches": [], "match_count": 0, "truncated": False,
            })
    return discovered


def discover_systemd_directories(
    outputs: list[dict[str, Any]], units: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    properties = {
        "logs_directory": ("log", "/var/log", "systemd LogsDirectory"),
        "state_directory": ("data", "/var/lib", "systemd StateDirectory"),
        "runtime_directory": ("other", "/run", "systemd RuntimeDirectory"),
        "cache_directory": ("data", "/var/cache", "systemd CacheDirectory"),
    }
    discovered: list[dict[str, Any]] = []
    for service, values in units.items():
        for property_name, (kind, prefix, source) in properties.items():
            for path in resolved_systemd_directories(values.get(property_name, ""), prefix):
                if any(
                    output["service"] == service
                    and output["sink"] == "directory"
                    and output.get("path") == path
                    for output in outputs
                ):
                    continue
                discovered.append({
                    "service": service, "kind": kind, "sink": "directory", "path": path,
                    "locator": None, "source": source, "evidence": "configured", "required": False,
                    "readiness": "exists", "rotation": "unknown", "retention": "unknown",
                    "ready": None, "status": "configured_undeclared", "matches": [],
                    "match_count": 0, "truncated": False,
                })
    return discovered


def resolved_systemd_directories(value: str, prefix: str) -> list[str]:
    try:
        names = shlex.split(value)
    except ValueError:
        return []
    result: list[str] = []
    for value_name in names:
        name = value_name.removeprefix("-").split(":", 1)[0]
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or "%" in name:
            continue
        result.append(str(PurePosixPath(prefix) / path))
    return result


def build_result(
    phase: str,
    snapshot: dict[str, Any],
    outputs: list[dict[str, Any]],
    sections: dict[str, str],
    duration: float,
) -> dict[str, Any]:
    units = parse_units(sections.get("units", ""))
    probes = parse_declared(sections.get("declared", ""))
    descriptors = parse_fds(sections.get("fds", ""))
    mappings = parse_shm_maps(sections.get("shm_maps", ""))
    business_services = {
        str(output["service"]) for output in outputs if output["service"] != "alertd.service"
    }
    shm_observations = collect_shm_observations(descriptors, mappings, business_services)
    declared, failures, warnings = evaluate_declared(outputs, probes, units, shm_observations)
    discovered = discover_outputs(outputs, units, descriptors, shm_observations)
    warnings.extend(
        f"{entry['service']} has undeclared configured output {entry.get('path') or entry.get('locator')}"
        for entry in discovered
        if entry.get("evidence") == "configured"
    )
    return {
        "schema_version": 1,
        "phase": phase,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "target": snapshot.get("target", {}),
        "healthy": not failures,
        "declared": declared,
        "discovered": discovered,
        "failures": failures,
        "warnings": warnings,
        "probe_duration_seconds": round(duration, 3),
        "max_glob_matches": MAX_GLOB_MATCHES,
    }


def write_result(result: dict[str, Any], output: Path) -> None:
    destination = output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    LOG.info("output result written path=%s bytes=%d", destination, destination.stat().st_size)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        snapshot = load_json(args.snapshot)
        contract = load_json(args.contract)
        known_hosts, outputs, units = validate_inputs(snapshot, contract, args.known_hosts)
        sections, duration = run_remote(snapshot, known_hosts, remote_script(outputs, units))
        result = build_result(args.phase, snapshot, outputs, sections, duration)
        write_result(result, args.output)
        LOG.info(
            "output gate phase=%s healthy=%s declared=%d discovered=%d duration_seconds=%.3f",
            args.phase, result["healthy"], len(result["declared"]), len(result["discovered"]), duration,
        )
        print(
            f"phase={args.phase} healthy={str(result['healthy']).lower()} "
            f"declared={len(result['declared'])} discovered={len(result['discovered'])} "
            f"failures={len(result['failures'])} result={args.output.expanduser().resolve()}"
        )
        return 0 if result["healthy"] else 1
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        LOG.error("output gate failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
