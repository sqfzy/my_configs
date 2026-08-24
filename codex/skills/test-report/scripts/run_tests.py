#!/usr/bin/env python3
"""Execute a frozen test contract and retain only redacted evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import platform
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


LOG = logging.getLogger("test_report.run_tests")
DEFAULT_TIMEOUT_SECONDS = 600
MINIMUM_TIMEOUT_SECONDS = 1
MAXIMUM_TIMEOUT_SECONDS = 86400
DEFAULT_MAX_STREAM_BYTES = 10 * 1024 * 1024
MINIMUM_MAX_STREAM_BYTES = 1024 * 1024
MAXIMUM_MAX_STREAM_BYTES = 256 * 1024 * 1024
TEST_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
GIT_COMMIT = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
SENSITIVE_NAME = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)"
)
SENSITIVE_OPTION = re.compile(
    r"(?i)^--?(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)(?:=|$)"
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)=)([^\s,;]+)"
)
SENSITIVE_ARGUMENT = re.compile(
    r"(?i)(--?(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)(?:=|\s+))([^\s,;]+)"
)
URI_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)
MUTATION_SCOPES = {"read_only", "task_workspace", "test_target", "external"}
RESULT_KINDS = {"junit_xml", "metrics_json"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    expanded = path.expanduser().resolve()
    value = json.loads(expanded.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {expanded}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def redact_text(value: str) -> str:
    value = URI_USERINFO.sub(r"\1<redacted>@", value)
    value = SENSITIVE_ARGUMENT.sub(lambda match: f"{match.group(1)}<redacted>", value)
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}<redacted>", value)


def reject_secret_values(value: Any, path: str = "contract") -> None:
    if isinstance(value, dict):
        for name, nested in value.items():
            location = f"{path}.{name}"
            if SENSITIVE_NAME.search(str(name)) and nested not in {None, "<redacted>"}:
                raise ValueError(f"secret-bearing field must be redacted: {location}")
            reject_secret_values(nested, location)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            reject_secret_values(nested, f"{path}[{index}]")
    elif isinstance(value, str) and URI_USERINFO.search(value):
        raise ValueError(f"URI userinfo is not allowed in the contract: {path}")


def validate_argv(argv: Any, field: str) -> list[str]:
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise ValueError(f"{field} must be a non-empty string array")
    for argument in argv:
        if SENSITIVE_OPTION.search(argument):
            raise ValueError(f"sensitive command arguments are not allowed: {field}")
        if URI_USERINFO.search(argument):
            raise ValueError(f"URI userinfo is not allowed: {field}")
    return list(argv)


def integer_in_range(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return number


def validate_subject(subject: Any) -> None:
    if not isinstance(subject, dict):
        raise ValueError("subject must be an object")
    repositories = subject.get("repositories", [])
    artifacts = subject.get("artifacts", [])
    if not isinstance(repositories, list) or not isinstance(artifacts, list):
        raise ValueError("subject repositories and artifacts must be arrays")
    if not repositories and not artifacts:
        raise ValueError("subject needs at least one repository or artifact")
    for repository in repositories:
        if not isinstance(repository, dict) or not repository.get("role") or not repository.get("path"):
            raise ValueError("each repository needs role and path")
        commit = repository.get("commit")
        if commit is not None and not GIT_COMMIT.fullmatch(str(commit)):
            raise ValueError(f"repository commit must be a full object id: {commit!r}")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not artifact.get("name") or not artifact.get("path"):
            raise ValueError("each artifact needs name and path")
        digest = artifact.get("sha256")
        if digest is not None and not SHA256.fullmatch(str(digest)):
            raise ValueError(f"artifact sha256 must be 64 hexadecimal characters: {digest!r}")
    services = subject.get("services", [])
    if not isinstance(services, list) or not all(isinstance(item, str) and item for item in services):
        raise ValueError("subject.services must be a string array")


def validate_target(target: Any) -> None:
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    kind = target.get("kind", "local")
    if kind not in {"local", "ssh"}:
        raise ValueError("target.kind must be local or ssh")
    if kind == "local":
        return
    ssh = target.get("ssh")
    if not isinstance(ssh, dict) or not str(ssh.get("host", "")).strip() or not str(ssh.get("user", "")).strip():
        raise ValueError("SSH target needs host and user")
    integer_in_range(ssh.get("port", 22), "target.ssh.port", 1, 65535)
    known_hosts = Path(str(ssh.get("known_hosts", "~/.ssh/known_hosts"))).expanduser()
    if not known_hosts.is_file():
        raise ValueError(f"SSH known-hosts file is missing: {known_hosts}")


def validate_tests(contract: dict[str, Any], default_timeout: int) -> None:
    tests = contract.get("tests")
    if not isinstance(tests, list) or not tests:
        raise ValueError("tests must be a non-empty array")
    previous: set[str] = set()
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            raise ValueError(f"tests[{index}] must be an object")
        test_id = str(test.get("id", ""))
        if not TEST_ID.fullmatch(test_id) or test_id in previous:
            raise ValueError(f"tests[{index}].id must be unique and lowercase: {test_id!r}")
        if not str(test.get("name", "")).strip() or not str(test.get("category", "")).strip():
            raise ValueError(f"test {test_id} needs name and category")
        if not isinstance(test.get("required"), bool):
            raise ValueError(f"test {test_id} required must be boolean")
        validate_argv(test.get("argv"), f"test {test_id} argv")
        if not isinstance(test.get("working_directory", "."), str):
            raise ValueError(f"test {test_id} working_directory must be a string")
        integer_in_range(
            test.get("timeout_seconds", default_timeout),
            f"test {test_id} timeout_seconds",
            MINIMUM_TIMEOUT_SECONDS,
            MAXIMUM_TIMEOUT_SECONDS,
        )
        exits = test.get("expected_exit_codes", [0])
        if not isinstance(exits, list) or not exits or any(isinstance(item, bool) or not isinstance(item, int) for item in exits):
            raise ValueError(f"test {test_id} expected_exit_codes must be a non-empty integer array")
        dependencies = test.get("depends_on", [])
        if not isinstance(dependencies, list) or any(item not in previous for item in dependencies):
            raise ValueError(f"test {test_id} dependencies must reference earlier tests")
        sources = test.get("result_sources", [])
        if not isinstance(sources, list):
            raise ValueError(f"test {test_id} result_sources must be an array")
        for source in sources:
            if not isinstance(source, dict) or source.get("kind") not in RESULT_KINDS or not source.get("path"):
                raise ValueError(f"test {test_id} has an invalid result source")
        scope = test.get("mutation_scope")
        if scope not in MUTATION_SCOPES:
            raise ValueError(f"test {test_id} has an invalid mutation_scope")
        cleanup = test.get("cleanup_argv")
        if cleanup is not None:
            validate_argv(cleanup, f"test {test_id} cleanup_argv")
        previous.add(test_id)


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != 1:
        raise ValueError("test contract schema_version must be 1")
    metadata = contract.get("metadata")
    if not isinstance(metadata, dict) or not str(metadata.get("title", "")).strip() or not str(metadata.get("objective", "")).strip():
        raise ValueError("metadata needs non-empty title and objective")
    validate_target(contract.get("target", {"kind": "local"}))
    execution = contract.get("execution", {})
    evidence = contract.get("evidence", {})
    if not isinstance(execution, dict) or not isinstance(evidence, dict):
        raise ValueError("execution and evidence must be objects")
    default_timeout = integer_in_range(
        execution.get("default_timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        "execution.default_timeout_seconds",
        MINIMUM_TIMEOUT_SECONDS,
        MAXIMUM_TIMEOUT_SECONDS,
    )
    integer_in_range(
        evidence.get("max_stream_bytes", DEFAULT_MAX_STREAM_BYTES),
        "evidence.max_stream_bytes",
        MINIMUM_MAX_STREAM_BYTES,
        MAXIMUM_MAX_STREAM_BYTES,
    )
    validate_subject(contract.get("subject"))
    validate_tests(contract, default_timeout)
    reject_secret_values(contract)


def ssh_prefix(target: dict[str, Any]) -> list[str]:
    ssh = target["ssh"]
    known_hosts = str(Path(str(ssh.get("known_hosts", "~/.ssh/known_hosts"))).expanduser().resolve())
    return [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-p", str(ssh.get("port", 22)),
        f"{ssh['user']}@{ssh['host']}",
    ]


def process_command(target: dict[str, Any], argv: list[str], working_directory: str, timeout_seconds: int) -> list[str]:
    if target.get("kind", "local") == "local":
        return argv
    command = f"cd {shlex.quote(working_directory)} && exec {shlex.join(argv)}"
    bounded = f"timeout --signal=TERM --kill-after=5s {timeout_seconds}s sh -lc {shlex.quote(command)}"
    return ssh_prefix(target) + [bounded]


def make_capture_file(output_dir: Path, suffix: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".capture-", suffix=suffix, dir=output_dir)
    os.close(descriptor)
    os.chmod(name, 0o600)
    return Path(name)


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait()


def execute_capture(
    target: dict[str, Any],
    argv: list[str],
    working_directory: str,
    timeout_seconds: int,
    output_dir: Path,
) -> dict[str, Any]:
    stdout_path = make_capture_file(output_dir, ".stdout")
    stderr_path = make_capture_file(output_dir, ".stderr")
    command = process_command(target, argv, working_directory, timeout_seconds)
    started_at = utc_now()
    started = time.monotonic()
    timed_out = False
    error = None
    returncode = None
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                cwd=working_directory if target.get("kind", "local") == "local" else None,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            try:
                returncode = process.wait(timeout=timeout_seconds + (10 if target.get("kind") == "ssh" else 0))
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_process(process)
                returncode = process.returncode
    except OSError as exception:
        error = str(exception)
    return {
        "argv": command,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "returncode": returncode,
        "timed_out": timed_out,
        "error": error,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


def retain_file(source: Path, destination: Path, maximum_bytes: int) -> dict[str, Any]:
    raw = source.read_bytes()[: maximum_bytes + 8192]
    decoded = raw.decode("utf-8", errors="replace")
    redacted = redact_text(decoded).encode("utf-8")
    truncated = source.stat().st_size > maximum_bytes or len(redacted) > maximum_bytes
    retained = redacted[:maximum_bytes]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_bytes(retained)
    os.replace(temporary, destination)
    source.unlink(missing_ok=True)
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(retained).hexdigest(),
        "bytes": len(retained),
        "redacted": True,
        "truncated": truncated,
    }


def discard_capture(capture: dict[str, Any]) -> None:
    Path(capture["stdout_path"]).unlink(missing_ok=True)
    Path(capture["stderr_path"]).unlink(missing_ok=True)


def run_text(target: dict[str, Any], argv: list[str], working_directory: str = ".") -> tuple[int, str]:
    if target.get("kind", "local") == "local":
        command = argv
        cwd = working_directory
    else:
        remote = f"cd {shlex.quote(working_directory)} && exec {shlex.join(argv)}"
        command = ssh_prefix(target) + ["sh -lc " + shlex.quote(remote)]
        cwd = None
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30, check=False)
    return completed.returncode, redact_text(completed.stdout.strip())


def local_memory() -> dict[str, Any]:
    if Path("/proc/meminfo").is_file():
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            name, raw = line.split(":", maxsplit=1)
            if name in {"MemTotal", "MemAvailable"}:
                values[name] = int(raw.strip().split()[0]) * 1024
        return values
    completed = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=False)
    return {"MemTotal": int(completed.stdout.strip())} if completed.returncode == 0 else {}


def collect_machine(target: dict[str, Any]) -> dict[str, Any]:
    if target.get("kind", "local") == "local":
        return {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count(),
            "memory": local_memory(),
        }
    code, output = run_text(
        target,
        ["sh", "-lc", "hostname; uname -s; uname -r; uname -m; getconf _NPROCESSORS_ONLN; awk '/MemTotal|MemAvailable/ {print $1 $2*1024}' /proc/meminfo"],
    )
    if code != 0:
        return {"collection_error": "remote machine inventory failed"}
    lines = output.splitlines()
    memory: dict[str, int] = {}
    for line in lines[5:]:
        if ":" in line:
            name, value = line.split(":", maxsplit=1)
            if value.isdigit():
                memory[name] = int(value)
    return {
        "hostname": lines[0] if len(lines) > 0 else "unknown",
        "system": lines[1] if len(lines) > 1 else "unknown",
        "release": lines[2] if len(lines) > 2 else "unknown",
        "architecture": lines[3] if len(lines) > 3 else "unknown",
        "cpu_count": int(lines[4]) if len(lines) > 4 and lines[4].isdigit() else None,
        "memory": memory,
    }


def collect_repository(target: dict[str, Any], declaration: dict[str, Any]) -> dict[str, Any]:
    repository_path = str(declaration["path"])
    result = {"role": declaration["role"], "path": repository_path, "declared_commit": declaration.get("commit")}
    code, commit = run_text(target, ["git", "-C", repository_path, "rev-parse", "HEAD"])
    if code != 0 or not GIT_COMMIT.fullmatch(commit):
        result["status"] = "unavailable"
        return result
    _, status = run_text(target, ["git", "-C", repository_path, "status", "--porcelain=v1", "--untracked-files=normal"])
    _, url = run_text(target, ["git", "-C", repository_path, "remote", "get-url", "origin"])
    result.update(
        {
            "commit": commit.lower(),
            "dirty": bool(status),
            "url": url or declaration.get("url", ""),
            "status": "matched" if not declaration.get("commit") or commit.lower() == str(declaration["commit"]).lower() else "mismatch",
        }
    )
    return result


def collect_artifact(target: dict[str, Any], declaration: dict[str, Any]) -> dict[str, Any]:
    path = str(declaration["path"])
    result = {"name": declaration["name"], "path": path, "declared_sha256": declaration.get("sha256")}
    if target.get("kind", "local") == "local":
        artifact = Path(path).expanduser()
        if not artifact.is_file():
            result["status"] = "unavailable"
            return result
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    else:
        code, output = run_text(target, ["sha256sum", "--", path])
        digest = output.split()[0] if code == 0 and output else ""
        if not SHA256.fullmatch(digest):
            result["status"] = "unavailable"
            return result
    result.update(
        {
            "sha256": digest.lower(),
            "status": "matched" if not declaration.get("sha256") or digest.lower() == str(declaration["sha256"]).lower() else "mismatch",
        }
    )
    return result


def collect_services(target: dict[str, Any], services: list[str]) -> list[dict[str, Any]]:
    results = []
    for service in services:
        code, output = run_text(
            target,
            ["systemctl", "show", service, "--property=ActiveState,SubState,Result,MainPID", "--no-pager"],
        )
        values = {}
        if code == 0:
            for line in output.splitlines():
                if "=" in line:
                    name, value = line.split("=", maxsplit=1)
                    values[name] = value
        results.append({"unit": service, "status": "observed" if code == 0 else "unavailable", **values})
    return results


def collect_context(contract: dict[str, Any]) -> dict[str, Any]:
    target = contract.get("target", {"kind": "local"})
    subject = contract["subject"]
    return {
        "captured_at": utc_now(),
        "target": {
            "kind": target.get("kind", "local"),
            "host": target.get("ssh", {}).get("host") if isinstance(target.get("ssh"), dict) else platform.node(),
        },
        "machine": collect_machine(target),
        "subject": {
            "repositories": [collect_repository(target, item) for item in subject.get("repositories", [])],
            "artifacts": [collect_artifact(target, item) for item in subject.get("artifacts", [])],
        },
        "services": collect_services(target, subject.get("services", [])),
    }


def persist_process_logs(
    capture: dict[str, Any],
    evidence_dir: Path,
    test_id: str,
    label: str,
    maximum_bytes: int,
) -> list[dict[str, Any]]:
    artifacts = []
    for stream in ("stdout", "stderr"):
        destination = evidence_dir / f"{test_id}.{label}.{stream}.log"
        item = retain_file(Path(capture[f"{stream}_path"]), destination, maximum_bytes)
        item.update({"kind": "log", "stream": stream, "test_id": test_id})
        artifacts.append(item)
    return artifacts


def collect_result_source(
    target: dict[str, Any],
    source: dict[str, Any],
    working_directory: str,
    evidence_dir: Path,
    test_id: str,
    index: int,
    maximum_bytes: int,
) -> dict[str, Any]:
    suffix = ".xml" if source["kind"] == "junit_xml" else ".json"
    destination = evidence_dir / f"{test_id}.result-{index}{suffix}"
    if target.get("kind", "local") == "local":
        source_path = Path(source["path"])
        if not source_path.is_absolute():
            source_path = Path(working_directory) / source_path
        if not source_path.is_file():
            return {"kind": source["kind"], "original_path": source["path"], "missing": True, "test_id": test_id}
        temporary = make_capture_file(evidence_dir.parent, suffix)
        temporary.write_bytes(source_path.read_bytes())
    else:
        capture = execute_capture(target, ["cat", "--", str(source["path"])], working_directory, 60, evidence_dir.parent)
        Path(capture["stderr_path"]).unlink(missing_ok=True)
        if capture["error"] or capture["timed_out"] or capture["returncode"] != 0:
            Path(capture["stdout_path"]).unlink(missing_ok=True)
            return {"kind": source["kind"], "original_path": source["path"], "missing": True, "test_id": test_id}
        temporary = Path(capture["stdout_path"])
    item = retain_file(temporary, destination, maximum_bytes)
    item.update({"kind": source["kind"], "original_path": source["path"], "missing": False, "test_id": test_id})
    return item


def execute_test(
    contract: dict[str, Any],
    test: dict[str, Any],
    statuses: dict[str, str],
    evidence_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    test_id = test["id"]
    base = {
        "id": test_id,
        "name": test["name"],
        "category": test["category"],
        "required": test["required"],
        "depends_on": test.get("depends_on", []),
        "mutation_scope": test["mutation_scope"],
    }
    if test.get("skip_reason"):
        return {**base, "status": "skipped", "reason": str(test["skip_reason"]), "artifacts": [], "result_sources": []}
    failed_dependencies = [name for name in test.get("depends_on", []) if statuses.get(name) != "passed"]
    if failed_dependencies:
        return {**base, "status": "blocked", "reason": f"dependencies not passed: {', '.join(failed_dependencies)}", "artifacts": [], "result_sources": []}
    if test["mutation_scope"] == "external" and (
        test.get("external_authorized") is not True or not test.get("cleanup_argv")
    ):
        return {**base, "status": "blocked", "reason": "external mutation lacks explicit authorization or cleanup", "artifacts": [], "result_sources": []}

    target = contract.get("target", {"kind": "local"})
    timeout = int(test.get("timeout_seconds", contract.get("execution", {}).get("default_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)))
    maximum_bytes = int(contract.get("evidence", {}).get("max_stream_bytes", DEFAULT_MAX_STREAM_BYTES))
    working_directory = str(test.get("working_directory", "."))
    LOG.info("test started id=%s target=%s timeout_seconds=%d", test_id, target.get("kind", "local"), timeout)
    capture = execute_capture(target, list(test["argv"]), working_directory, timeout, output_dir)
    artifacts = persist_process_logs(capture, evidence_dir, test_id, "run", maximum_bytes)
    if capture["error"]:
        status = "error"
        reason = capture["error"]
    elif capture["timed_out"]:
        status = "timed_out"
        reason = f"exceeded {timeout} seconds"
    elif capture["returncode"] in test.get("expected_exit_codes", [0]):
        status = "passed"
        reason = "exit code matched"
    else:
        status = "failed"
        reason = f"unexpected exit code {capture['returncode']}"

    cleanup = None
    cleanup_argv = test.get("cleanup_argv")
    if cleanup_argv and test["mutation_scope"] in {"test_target", "external"}:
        cleanup_capture = execute_capture(target, list(cleanup_argv), working_directory, timeout, output_dir)
        artifacts.extend(persist_process_logs(cleanup_capture, evidence_dir, test_id, "cleanup", maximum_bytes))
        cleanup = {
            "returncode": cleanup_capture["returncode"],
            "timed_out": cleanup_capture["timed_out"],
            "error": cleanup_capture["error"],
            "duration_seconds": cleanup_capture["duration_seconds"],
            "succeeded": not cleanup_capture["error"] and not cleanup_capture["timed_out"] and cleanup_capture["returncode"] == 0,
        }
        if not cleanup["succeeded"]:
            status = "error"
            reason = "cleanup failed"

    result_sources = [
        collect_result_source(target, source, working_directory, evidence_dir, test_id, index, maximum_bytes)
        for index, source in enumerate(test.get("result_sources", []), start=1)
    ]
    LOG.info(
        "test finished id=%s status=%s returncode=%s duration_seconds=%.3f",
        test_id, status, capture["returncode"], capture["duration_seconds"],
    )
    return {
        **base,
        "status": status,
        "reason": reason,
        "started_at": capture["started_at"],
        "finished_at": capture["finished_at"],
        "duration_seconds": capture["duration_seconds"],
        "returncode": capture["returncode"],
        "timed_out": capture["timed_out"],
        "artifacts": artifacts,
        "result_sources": result_sources,
        "cleanup": cleanup,
    }


def execute_contract(contract: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    started_at = utc_now()
    before = collect_context(contract)
    evidence_dir = output_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    statuses: dict[str, str] = {}
    results = []
    for test in contract["tests"]:
        result = execute_test(contract, test, statuses, evidence_dir, output_dir)
        statuses[test["id"]] = result["status"]
        results.append(result)
    after = collect_context(contract)
    return {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": utc_now(),
        "target": contract.get("target", {"kind": "local"}),
        "context_before": before,
        "context_after": after,
        "tests": results,
    }


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        contract = load_json(args.contract)
        validate_contract(contract)
        output_dir = args.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / "test-contract.json", contract)
        execution = execute_contract(contract, output_dir)
        execution["contract_sha256"] = hashlib.sha256((output_dir / "test-contract.json").read_bytes()).hexdigest()
        write_json(output_dir / "execution.json", execution)
        print(f"tests={len(execution['tests'])} execution={output_dir / 'execution.json'}")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        LOG.error("test execution failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
