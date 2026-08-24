#!/usr/bin/env python3
"""Export a versioned, redacted deployment context for the independent test-report Skill."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any


LOG = logging.getLogger("deploy.export_test_context")
SENSITIVE_NAME = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)"
)
FORBIDDEN_CONTEXT = re.compile(r"(?i)(webhook|access[_-]?token|signing[_-]?secret)")
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)=)([^\s,;]+)"
)
SENSITIVE_ARGUMENT = re.compile(
    r"(?i)(--?(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)(?:=|\s+))([^\s,;]+)"
)
URI_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)
VIRTUAL_FILESYSTEMS = {
    "autofs", "bpf", "cgroup", "cgroup2", "debugfs", "devpts", "devtmpfs", "overlay",
    "proc", "ramfs", "rootfs", "securityfs", "squashfs", "sysfs", "tmpfs", "tracefs",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--status", required=True, choices=("succeeded", "failed", "rolled_back"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_json(path: Path | None, required: bool = True) -> dict[str, Any]:
    if path is None:
        return {}
    expanded = path.expanduser().resolve()
    if not expanded.is_file():
        if required:
            raise ValueError(f"JSON input is missing: {expanded}")
        return {}
    value = json.loads(expanded.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {expanded}")
    return value


def redact_text(value: str) -> str:
    value = URI_USERINFO.sub(r"\1<redacted>@", value)
    value = SENSITIVE_ARGUMENT.sub(lambda match: f"{match.group(1)}<redacted>", value)
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}<redacted>", value)


def sanitize(value: Any, name: str = "") -> Any:
    if FORBIDDEN_CONTEXT.search(name):
        return None
    if SENSITIVE_NAME.search(name):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            str(key): sanitize(nested, str(key))
            for key, nested in value.items()
            if not FORBIDDEN_CONTEXT.search(str(key))
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        if FORBIDDEN_CONTEXT.search(value):
            return "<redacted>"
        return redact_text(value)
    return value


def sanitize_key_config(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result = []
    for item in values:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        if FORBIDDEN_CONTEXT.search(name):
            continue
        value = "<redacted>" if SENSITIVE_NAME.search(name) else redact_text(str(item.get("value", "")))
        result.append({"name": name, "source": redact_text(str(item.get("source", ""))), "value": value})
    return result


def file_sha256(path: Path | None) -> str | None:
    if path is None or not path.expanduser().is_file():
        return None
    digest = hashlib.sha256()
    with path.expanduser().open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(contract: dict[str, Any], before: dict[str, Any]) -> None:
    if contract.get("schema_version") not in {1, 2, 3}:
        raise ValueError("deployment contract schema_version must be 1, 2, or 3")
    if before.get("schema_version") != 1:
        raise ValueError("host snapshot schema_version must be 1")
    if not isinstance(contract.get("repositories"), list) or not contract["repositories"]:
        raise ValueError("deployment contract needs repositories")


def repositories(contract: dict[str, Any]) -> list[dict[str, Any]]:
    fields = ("role", "url", "target", "commit", "builder_image_digest", "artifact_sha256")
    return [sanitize({field: item.get(field) for field in fields if item.get(field) is not None}) for item in contract["repositories"]]


def artifacts(contract: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for repository in contract["repositories"]:
        digest = repository.get("artifact_sha256")
        if digest:
            result.append(
                {
                    "name": str(repository.get("role", "application")),
                    "sha256": str(digest),
                    "repository_commit": str(repository.get("commit", "")),
                }
            )
    return result


def storage_summary(snapshot: dict[str, Any]) -> dict[str, int] | None:
    filesystems = snapshot.get("storage", {}).get("filesystems", [])
    persistent = [item for item in filesystems if str(item.get("fstype", "")).lower() not in VIRTUAL_FILESYSTEMS]
    if not persistent:
        return None
    return {
        "size": sum(int(item.get("size", 0) or 0) for item in persistent),
        "used": sum(int(item.get("used", 0) or 0) for item in persistent),
        "available": sum(int(item.get("avail", 0) or 0) for item in persistent),
    }


def environment(snapshot: dict[str, Any]) -> dict[str, Any]:
    return sanitize(
        {
            "captured_at": snapshot.get("captured_at"),
            "machine": snapshot.get("machine", {}),
            "cpu": snapshot.get("cpu", {}),
            "memory": snapshot.get("memory", {}),
            "storage_summary": storage_summary(snapshot),
            "network": snapshot.get("network", {}),
            "services": snapshot.get("services", []),
        }
    )


def health_summary(gate: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version", "phase", "started_at", "finished_at", "healthy", "clean",
        "failures", "warnings", "inherited_warnings", "required_units",
    )
    return sanitize({field: gate.get(field) for field in fields if field in gate})


def outputs_summary(outputs: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version", "phase", "checked_at", "healthy", "declared", "discovered",
        "failures", "warnings", "probe_duration_seconds",
    )
    return sanitize({field: outputs.get(field) for field in fields if field in outputs})


def build_evidence(
    before: dict[str, Any],
    after: dict[str, Any],
    contract: dict[str, Any],
    gate: dict[str, Any],
    outputs: dict[str, Any],
    status: str,
    source_paths: dict[str, Path | None],
) -> dict[str, Any]:
    current = after or before
    target = contract.get("target", {})
    return {
        "schema_version": 1,
        "kind": "deployment_test_context",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "deployment_status": status,
        "target": sanitize(
            {
                "host": target.get("host", before.get("target", {}).get("host")),
                "user": target.get("user", before.get("target", {}).get("user")),
                "port": target.get("port", before.get("target", {}).get("port", 22)),
            }
        ),
        "subject": {
            "repositories": repositories(contract),
            "artifacts": artifacts(contract),
        },
        "environment": environment(current),
        "key_config": sanitize_key_config(contract.get("key_config", [])),
        "runtime": {
            "health": health_summary(gate),
            "program_outputs": outputs_summary(outputs),
        },
        "source": {
            "contract_schema_version": contract.get("schema_version"),
            "before_captured_at": before.get("captured_at"),
            "after_captured_at": after.get("captured_at") if after else None,
            "sha256": {name: file_sha256(path) for name, path in source_paths.items()},
        },
        "warnings": [
            message
            for message, present in (
                ("post-action snapshot unavailable", not after),
                ("health evidence unavailable", not gate),
                ("program output evidence unavailable", not outputs),
            )
            if present
        ],
    }


def write_result(path: Path, value: dict[str, Any]) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if FORBIDDEN_CONTEXT.search(serialized):
        raise ValueError("deployment test context contains forbidden credential fields")
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, destination)
    LOG.info("deployment test context written path=%s bytes=%d", destination, destination.stat().st_size)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        before = load_json(args.before)
        after = load_json(args.after, required=False)
        contract = load_json(args.contract)
        gate = load_json(args.gate, required=False)
        outputs = load_json(args.outputs, required=False)
        validate_inputs(contract, before)
        evidence = build_evidence(
            before, after, contract, gate, outputs, args.status,
            {"before": args.before, "after": args.after, "contract": args.contract, "gate": args.gate, "outputs": args.outputs},
        )
        write_result(args.output, evidence)
        print(f"status={args.status} evidence={args.output.expanduser().resolve()}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        LOG.error("deployment test context export failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
