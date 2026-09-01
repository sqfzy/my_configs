#!/usr/bin/env python3
"""Collect Alertd DingTalk delivery evidence through strict read-only SSH probes."""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime as dt
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

import tomllib

LOG = logging.getLogger("deploy.inspect_alertd_delivery")
SECTION_PREFIX = "__DEPLOY_SECTION__ "
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FULL_COMMIT = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])")
WEBHOOK_ENDPOINT = "https://oapi.dingtalk.com/robot/send"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--known-hosts", required=True, type=Path)
    parser.add_argument("--config-path", default="/etc/alertd/alertd.toml")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate_inputs(
    snapshot: dict[str, Any], known_hosts_path: Path, config_path: str
) -> Path:
    target = snapshot.get("target", {})
    if not target.get("host") or not target.get("user"):
        raise ValueError("snapshot target is incomplete")
    known_hosts = known_hosts_path.expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError(f"known-hosts file is missing: {known_hosts}")
    if not config_path.startswith("/") or any(ord(character) < 32 for character in config_path):
        raise ValueError("alertd config path must be an absolute path")
    return known_hosts


def metadata_script(config_path: str) -> str:
    return f'''set -u
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
section unit
systemctl show alertd.service --no-pager \
    -p LoadState -p ActiveState -p MainPID -p EnvironmentFiles 2>/dev/null || true
section config
base64 -w0 {shlex.quote(config_path)} 2>/dev/null || true
printf '\n'
'''


def credentials_script(main_pid: int, token_env: str, secret_env: str) -> str:
    return f'''set -u
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
environment_path=/proc/{main_pid}/environ
token_name={shlex.quote(token_env)}
secret_name={shlex.quote(secret_env)}
section token
if [ -r "$environment_path" ]; then
    awk -v RS='\0' -v name="$token_name" '
        index($0, name "=") == 1 {{ sub(/^[^=]*=/, ""); printf "%s", $0; found=1 }}
        END {{ if (!found) exit 1 }}
    ' "$environment_path" 2>/dev/null | base64 -w0 || true
fi
printf '\n'
section secret
if [ -r "$environment_path" ]; then
    awk -v RS='\0' -v name="$secret_name" '
        index($0, name "=") == 1 {{ sub(/^[^=]*=/, ""); printf "%s", $0; found=1 }}
        END {{ if (!found) exit 1 }}
    ' "$environment_path" 2>/dev/null | base64 -w0 || true
fi
printf '\n'
'''


def run_remote(
    snapshot: dict[str, Any], known_hosts: Path, script: str
) -> tuple[dict[str, str], float]:
    target = snapshot["target"]
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
        timeout=30,
        check=False,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"delivery probe failed exit_code={result.returncode} duration_seconds={elapsed:.3f}"
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


def parse_properties(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            result[name] = value
    return result


def decode_base64(value: str) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as error:
        raise ValueError("remote delivery evidence is not valid base64 UTF-8") from error


def parse_delivery_config(text: str) -> tuple[str, str]:
    if not text:
        raise ValueError("alertd config is missing or empty")
    config = tomllib.loads(text)
    delivery = config.get("delivery", {})
    if not isinstance(delivery, dict):
        raise ValueError("alertd config delivery section is invalid")
    token_env = str(delivery.get("token_env", "ALERTD_DINGTALK_TOKEN"))
    secret_env = str(delivery.get("secret_env", "ALERTD_DINGTALK_SECRET"))
    if not ENVIRONMENT_NAME.fullmatch(token_env) or not ENVIRONMENT_NAME.fullmatch(secret_env):
        raise ValueError("alertd delivery environment variable name is invalid")
    return token_env, secret_env


def parse_environment_files(value: str) -> list[str]:
    try:
        fields = shlex.split(value)
    except ValueError:
        return []
    return sorted(
        {
            field.removeprefix("-")
            for field in fields
            if field.removeprefix("-").startswith("/")
        }
    )


def build_webhook_url(token: str) -> str:
    if not token:
        raise ValueError("alertd token is missing or empty")
    return f"{WEBHOOK_ENDPOINT}?access_token={urllib.parse.quote(token, safe='')}"


def infer_alertd_commit(snapshot: dict[str, Any]) -> str:
    for repository in snapshot.get("repositories", []):
        commit = str(repository.get("commit", ""))
        if repository.get("role") == "alertd" and FULL_COMMIT.fullmatch(commit):
            return str(repository["commit"]).lower()
    for service in snapshot.get("services", []):
        if service.get("unit") != "alertd.service":
            continue
        for name in ("exec_start", "working_directory", "fragment_path", "resolved_fragment_path"):
            match = FULL_COMMIT.search(str(service.get(name, "")))
            if match:
                return match.group(0).lower()
    return "unknown"


def evidence_base(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "provider": "dingtalk",
        "endpoint": WEBHOOK_ENDPOINT,
        "webhook_url": None,
        "token_env": "unknown",
        "secret_env": "unknown",
        "environment_files": [],
        "signing_secret": None,
        "signing_secret_present": None,
        "alertd_commit": infer_alertd_commit(snapshot),
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "unavailable",
        "verified": False,
        "warnings": [],
        "probe_duration_seconds": 0.0,
    }


def collect_metadata(
    snapshot: dict[str, Any], known_hosts: Path, config_path: str
) -> tuple[dict[str, str], str, float]:
    sections, duration = run_remote(snapshot, known_hosts, metadata_script(config_path))
    properties = parse_properties(sections.get("unit", ""))
    config = decode_base64(sections.get("config", ""))
    return properties, config, duration


def collect_credentials(
    snapshot: dict[str, Any],
    known_hosts: Path,
    main_pid: int,
    token_env: str,
    secret_env: str,
) -> tuple[str, str, float]:
    sections, duration = run_remote(
        snapshot, known_hosts, credentials_script(main_pid, token_env, secret_env)
    )
    token = decode_base64(sections.get("token", ""))
    secret = decode_base64(sections.get("secret", ""))
    return token, secret, duration


def unit_problem(properties: dict[str, str]) -> str | None:
    if properties.get("LoadState") != "loaded" or properties.get("ActiveState") != "active":
        return "alertd.service is not active"
    if integer_or_zero(properties.get("MainPID")) <= 0:
        return "alertd.service has no MainPID"
    return None


def inspect_available_delivery(
    evidence: dict[str, Any],
    snapshot: dict[str, Any],
    known_hosts: Path,
    config_path: str,
) -> dict[str, Any]:
    properties, config, metadata_duration = collect_metadata(
        snapshot, known_hosts, config_path
    )
    evidence["environment_files"] = parse_environment_files(
        properties.get("EnvironmentFiles", "")
    )
    evidence["probe_duration_seconds"] = round(metadata_duration, 3)
    if problem := unit_problem(properties):
        evidence["warnings"].append(problem)
        return evidence
    token_env, secret_env = parse_delivery_config(config)
    evidence["token_env"], evidence["secret_env"] = token_env, secret_env
    token, secret, credentials_duration = collect_credentials(
        snapshot,
        known_hosts,
        integer_or_zero(properties["MainPID"]),
        token_env,
        secret_env,
    )
    evidence["probe_duration_seconds"] = round(
        metadata_duration + credentials_duration, 3
    )
    evidence["signing_secret"] = secret or None
    evidence["signing_secret_present"] = bool(secret)
    if not token:
        evidence["warnings"].append(f"environment {token_env} is missing or empty")
        return evidence
    evidence.update(webhook_url=build_webhook_url(token), status="verified", verified=True)
    if not secret:
        evidence["warnings"].append(f"environment {secret_env} is missing or empty")
    return evidence


def inspect_delivery(
    snapshot: dict[str, Any], known_hosts: Path, config_path: str
) -> dict[str, Any]:
    evidence = evidence_base(snapshot)
    try:
        return inspect_available_delivery(evidence, snapshot, known_hosts, config_path)
    except (
        OSError,
        RuntimeError,
        ValueError,
        tomllib.TOMLDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        LOG.warning(
            "delivery evidence unavailable error_type=%s",
            type(error).__name__,
        )
        evidence["warnings"].append("alertd delivery evidence could not be confirmed")
        return evidence


def integer_or_zero(value: Any) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def write_result(result: dict[str, Any], output: Path) -> None:
    destination = output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    LOG.info("delivery evidence written path=%s status=%s", destination, result["status"])


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        snapshot = load_json(args.snapshot)
        known_hosts = validate_inputs(snapshot, args.known_hosts, args.config_path)
        result = inspect_delivery(snapshot, known_hosts, args.config_path)
        write_result(result, args.output)
        print(
            f"status={result['status']} provider={result['provider']} "
            f"verified={str(result['verified']).lower()} "
            f"result={args.output.expanduser().resolve()}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        LOG.error("delivery inspection failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
