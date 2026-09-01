#!/usr/bin/env python3
"""Build an atomic deployment report bundle from explicit configuration inputs."""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import render_report

LOG = logging.getLogger("deploy.build_report_bundle")
SECTION_PREFIX = "__DEPLOY_SECTION__ "
BUNDLE_NAME = re.compile(r"^\d{8}-\d{6}Z-[a-z0-9._-]+-deploy$")


def parse_args() -> argparse.Namespace:
    default_template = Path(__file__).resolve().parent.parent / "assets" / "report-template.md"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--alertd-delivery", type=Path)
    parser.add_argument("--test-context", type=Path)
    parser.add_argument(
        "--status", required=True, choices=["succeeded", "failed", "rolled_back"]
    )
    parser.add_argument("--template", type=Path, default=default_template)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def normalize_hostname(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", str(value).lower()).strip("-")
    return normalized or "unknown"


def validate_bundle_inputs(
    before: dict[str, Any], contract: dict[str, Any], output_dir: Path
) -> Path:
    render_report.validate_contract(contract)
    if contract.get("schema_version") != 4:
        raise ValueError("deployment report bundles require contract schema_version 4")
    validate_target(before, contract)
    known_hosts = Path(str(contract["target"].get("known_hosts", ""))).expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError(f"known-hosts file is missing: {known_hosts}")
    validate_bundle_name(before, output_dir)
    if output_dir.exists():
        raise ValueError(f"output bundle already exists: {output_dir}")
    return known_hosts


def validate_target(before: dict[str, Any], contract: dict[str, Any]) -> None:
    snapshot_target = before.get("target", {})
    contract_target = contract.get("target", {})
    snapshot_identity = (
        snapshot_target.get("host"),
        snapshot_target.get("user"),
        int(snapshot_target.get("port", 22)),
    )
    contract_identity = (
        contract_target.get("host"),
        contract_target.get("user"),
        int(contract_target.get("port", 22)),
    )
    if snapshot_identity != contract_identity:
        raise ValueError("snapshot target does not match deployment contract")


def validate_bundle_name(before: dict[str, Any], output_dir: Path) -> None:
    hostname = normalize_hostname(before.get("machine", {}).get("hostname", "unknown"))
    if not BUNDLE_NAME.fullmatch(output_dir.name):
        raise ValueError("bundle name must use YYYYMMDD-HHMMSSZ-<hostname>-deploy")
    if not output_dir.name.endswith(f"-{hostname}-deploy"):
        raise ValueError("bundle hostname does not match the deployment snapshot")


def remote_file_script(source_path: str) -> str:
    source = shlex.quote(source_path)
    return f'''set -u
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
source_path={source}
if [ ! -e "$source_path" ]; then
    section status; printf 'missing\n'
    exit 0
fi
resolved_path="$(readlink -f -- "$source_path" 2>/dev/null || true)"
if [ -z "$resolved_path" ] || [ ! -f "$resolved_path" ]; then
    section status; printf 'not_regular\n'
    exit 0
fi
if [ ! -r "$resolved_path" ]; then
    section status; printf 'unreadable\n'
    exit 0
fi
section status; printf 'captured\n'
section resolved_path; printf '%s' "$resolved_path" | base64 -w0; printf '\n'
section symlink_target; readlink -- "$source_path" 2>/dev/null | base64 -w0 || true; printf '\n'
section owner; stat -Lc '%U' -- "$resolved_path" 2>/dev/null || true
section group; stat -Lc '%G' -- "$resolved_path" 2>/dev/null || true
section mode; stat -Lc '%a' -- "$resolved_path" 2>/dev/null || true
section content; base64 -w0 -- "$resolved_path" 2>/dev/null || true; printf '\n'
'''


def run_remote(
    contract: dict[str, Any], known_hosts: Path, script: str
) -> tuple[dict[str, str], float]:
    target = contract["target"]
    command = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "LogLevel=ERROR",
        "-p", str(target.get("port", 22)),
        f"{target['user']}@{target['host']}",
        "bash -s",
    ]
    started = time.monotonic()
    result = subprocess.run(
        command,
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"configuration capture failed exit_code={result.returncode} "
            f"duration_seconds={elapsed:.3f}"
        )
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


def decode_text(value: str) -> str | None:
    if not value:
        return None
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as error:
        raise ValueError("remote configuration metadata is invalid") from error


def decode_bytes(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except binascii.Error as error:
        raise ValueError("remote configuration content is invalid") from error


def create_staging_directory(output_dir: Path) -> Path:
    parent = output_dir.expanduser().resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=parent))
    os.chmod(staging, 0o700)
    return staging


def write_private_bytes(path: Path, content: bytes, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    mode = 0o700 if executable else 0o600
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
    os.chmod(path, mode)


def write_private_json(path: Path, value: Any) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2).encode() + b"\n"
    write_private_bytes(path, content)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def base_manifest_entry(configuration: dict[str, Any]) -> dict[str, Any]:
    return {
        "service": configuration["service"],
        "kind": configuration["kind"],
        "purpose": configuration["purpose"],
        "source_path": configuration.get("source_path"),
        "source_description": None,
        "resolved_path": None,
        "symlink_target": None,
        "package_path": configuration["package_path"],
        "generated": configuration["capture"] == "generated",
        "required": configuration["required"],
        "status": "unavailable",
        "sha256": None,
        "size": None,
        "original_owner": None,
        "original_group": None,
        "original_mode": None,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "capture_duration_seconds": 0.0,
    }


def capture_file_configuration(
    staging: Path,
    contract: dict[str, Any],
    known_hosts: Path,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    entry = base_manifest_entry(configuration)
    sections, duration = run_remote(
        contract, known_hosts, remote_file_script(str(configuration["source_path"]))
    )
    entry["capture_duration_seconds"] = round(duration, 3)
    entry["status"] = sections.get("status", "unavailable")
    if entry["status"] != "captured":
        if configuration["required"]:
            raise ValueError(
                f"required configuration is unavailable: {configuration['source_path']}"
            )
        return entry
    content = decode_bytes(sections.get("content", ""))
    package_file = staging / str(configuration["package_path"])
    write_private_bytes(package_file, content, configuration["kind"] == "script")
    entry.update(
        resolved_path=decode_text(sections.get("resolved_path", "")),
        symlink_target=decode_text(sections.get("symlink_target", "")),
        sha256=sha256_bytes(content),
        size=len(content),
        original_owner=sections.get("owner") or None,
        original_group=sections.get("group") or None,
        original_mode=sections.get("mode") or None,
    )
    LOG.info(
        "configuration captured service=%s package_path=%s bytes=%d duration_seconds=%.3f",
        entry["service"],
        entry["package_path"],
        entry["size"],
        duration,
    )
    return entry


def capture_generated_configuration(
    staging: Path, configuration: dict[str, Any]
) -> dict[str, Any]:
    entry = base_manifest_entry(configuration)
    content = json.dumps(
        configuration["content"], ensure_ascii=False, indent=2
    ).encode() + b"\n"
    write_private_bytes(staging / str(configuration["package_path"]), content)
    entry.update(
        source_description="deployment contract generated configuration",
        status="captured",
        sha256=sha256_bytes(content),
        size=len(content),
    )
    return entry


def capture_configurations(
    staging: Path, contract: dict[str, Any], known_hosts: Path
) -> list[dict[str, Any]]:
    entries = []
    for configuration in contract["configurations"]:
        if configuration["capture"] == "file":
            entry = capture_file_configuration(
                staging, contract, known_hosts, configuration
            )
        else:
            entry = capture_generated_configuration(staging, configuration)
        entries.append(entry)
    return entries


def generated_entry(
    service: str,
    kind: str,
    purpose: str,
    package_path: str,
    content: bytes,
    source_description: str,
) -> dict[str, Any]:
    return {
        "service": service,
        "kind": kind,
        "purpose": purpose,
        "source_path": None,
        "source_description": source_description,
        "resolved_path": None,
        "symlink_target": None,
        "package_path": package_path,
        "generated": True,
        "required": True,
        "status": "captured",
        "sha256": sha256_bytes(content),
        "size": len(content),
        "original_owner": None,
        "original_group": None,
        "original_mode": None,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "capture_duration_seconds": 0.0,
    }


def add_alertd_delivery(
    staging: Path, evidence: dict[str, Any]
) -> dict[str, Any] | None:
    if not evidence:
        return None
    content = json.dumps(evidence, ensure_ascii=False, indent=2).encode() + b"\n"
    package_path = "config/generated/alertd-delivery.json"
    write_private_bytes(staging / package_path, content)
    return generated_entry(
        "alertd.service",
        "runtime",
        "Alertd 告警投递配置",
        package_path,
        content,
        "running alertd process environment",
    )


def shell_script(steps: list[Any]) -> bytes:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for index, step in enumerate(steps, 1):
        lines.extend([f"# Step {index}", str(step), ""])
    return "\n".join(lines).encode()


def add_action_script(
    staging: Path, name: str, purpose: str, steps: list[Any]
) -> dict[str, Any]:
    package_path = f"scripts/{name}.sh"
    content = shell_script(steps)
    write_private_bytes(staging / package_path, content, executable=True)
    return generated_entry(
        "deployment",
        "script",
        purpose,
        package_path,
        content,
        "frozen deployment contract",
    )


def add_test_context(staging: Path, source: Path | None) -> dict[str, Any] | None:
    return add_local_evidence(
        staging,
        source,
        "evidence/deployment-evidence.json",
        "脱敏测试上下文",
        "export_test_context.py",
    )


def add_local_evidence(
    staging: Path,
    source: Path | None,
    package_path: str,
    purpose: str,
    source_description: str,
) -> dict[str, Any] | None:
    if source is None or not source.expanduser().is_file():
        return None
    content = source.expanduser().read_bytes()
    write_private_bytes(staging / package_path, content)
    entry = generated_entry(
        "deployment",
        "evidence",
        purpose,
        package_path,
        content,
        source_description,
    )
    entry["generated"] = False
    return entry


def add_frozen_evidence(args: argparse.Namespace, staging: Path) -> list[dict[str, Any]]:
    specifications = [
        (args.contract, "evidence/deployment-contract.json", "冻结部署契约", "contract input"),
        (args.before, "evidence/host-before.json", "部署前主机快照", "before snapshot"),
        (args.after, "evidence/host-after.json", "部署后主机快照", "after snapshot"),
        (args.gate, "evidence/final-gate.json", "最终健康门禁", "health gate input"),
        (args.outputs, "evidence/final-outputs.json", "完整程序产出证据", "output gate input"),
    ]
    return [
        entry
        for source, package_path, purpose, description in specifications
        if (
            entry := add_local_evidence(
                staging, source, package_path, purpose, description
            )
        )
    ]


def build_manifest(
    status: str,
    contract: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    target = contract["target"]
    return {
        "schema_version": 1,
        "kind": "deployment_report_bundle",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "deployment_status": status,
        "target": {
            "host": target["host"],
            "user": target["user"],
            "port": target.get("port", 22),
        },
        "report": "REPORT.md",
        "entries": entries,
    }


def write_report(
    staging: Path,
    status: str,
    before: dict[str, Any],
    after: dict[str, Any],
    contract: dict[str, Any],
    gate: dict[str, Any],
    outputs: dict[str, Any],
    delivery: dict[str, Any],
    template: str,
    entries: list[dict[str, Any]],
) -> None:
    report = render_report.build_report(
        status,
        before,
        after,
        contract,
        gate,
        template,
        outputs,
        delivery,
        entries,
    )
    write_private_bytes(staging / "REPORT.md", report.encode())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_files(staging: Path) -> list[Path]:
    return sorted(
        path
        for path in staging.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )


def write_checksums(staging: Path) -> None:
    lines = [
        f"{file_sha256(path)}  {path.relative_to(staging).as_posix()}"
        for path in bundle_files(staging)
    ]
    write_private_bytes(
        staging / "checksums.sha256", ("\n".join(lines) + "\n").encode()
    )


def verify_checksums(staging: Path) -> None:
    for line in (staging / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if file_sha256(staging / relative) != expected:
            raise ValueError(f"bundle checksum mismatch: {relative}")


def secure_bundle_permissions(staging: Path) -> None:
    os.chmod(staging, 0o700)
    for path in staging.rglob("*"):
        if path.is_dir():
            os.chmod(path, 0o700)
        elif path.is_file():
            mode = 0o700 if path.relative_to(staging).parts[0] == "scripts" else 0o600
            os.chmod(path, mode)


def publish_bundle(staging: Path, output_dir: Path) -> None:
    destination = output_dir.expanduser().resolve()
    os.replace(staging, destination)
    os.chmod(destination, 0o700)


def build_bundle(args: argparse.Namespace) -> Path:
    before = render_report.load_json(args.before)
    after = render_report.load_json(args.after, required=False)
    contract = render_report.load_json(args.contract)
    gate = render_report.load_json(args.gate, required=False)
    outputs = render_report.load_json(args.outputs, required=False)
    delivery = render_report.load_json(args.alertd_delivery, required=False)
    output_dir = args.output_dir.expanduser().resolve()
    known_hosts = validate_bundle_inputs(before, contract, output_dir)
    template = args.template.expanduser().read_text(encoding="utf-8")
    staging = create_staging_directory(output_dir)
    try:
        entries = capture_configurations(staging, contract, known_hosts)
        for entry in (
            add_alertd_delivery(staging, delivery),
            add_action_script(staging, "reproduce", "部署复现流程", contract["reproduce"]),
            add_action_script(staging, "rollback", "部署回滚流程", contract["rollback"]),
            add_test_context(staging, args.test_context),
        ):
            if entry:
                entries.append(entry)
        entries.extend(add_frozen_evidence(args, staging))
        report_entries = [entry for entry in entries if entry["kind"] != "evidence"]
        write_report(
            staging,
            args.status,
            before,
            after,
            contract,
            gate,
            outputs,
            delivery,
            template,
            report_entries,
        )
        write_private_json(
            staging / "manifest.json", build_manifest(args.status, contract, entries)
        )
        write_checksums(staging)
        verify_checksums(staging)
        secure_bundle_permissions(staging)
        publish_bundle(staging, output_dir)
        return output_dir
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        output_dir = build_bundle(args)
        print(f"status={args.status} bundle={output_dir}")
        return 0
    except (
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        LOG.error("report bundle failed error_type=%s", type(error).__name__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
