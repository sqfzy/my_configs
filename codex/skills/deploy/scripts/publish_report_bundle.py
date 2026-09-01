#!/usr/bin/env python3
"""Publish a deployment bundle to its SSH host, archive it there, and download it."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any

import render_report

LOG = logging.getLogger("deploy.publish_report_bundle")
SECTION_PREFIX = "__DEPLOY_SECTION__ "
BUNDLE_NAME = re.compile(r"^\d{8}-\d{6}Z-[a-z0-9._-]+-deploy$")
FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")
USER_NAME = re.compile(r"^[a-z_][a-z0-9_-]*[$]?$", re.IGNORECASE)
HOST_NAME = re.compile(r"^[a-z0-9._:\[\]-]+$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--local-dir", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_timeout(value: int) -> int:
    if not 300 <= value <= 7200:
        raise ValueError("timeout-seconds must be between 300 and 7200")
    return value


def validate_remote_directory(value: Any) -> str:
    text = str(value)
    path = PurePosixPath(text)
    if (
        not text.startswith("/")
        or path == PurePosixPath("/")
        or any(part in {"", ".", ".."} for part in path.parts[1:])
        or any(ord(character) < 32 for character in text)
    ):
        raise ValueError("report_remote_dir must be a safe absolute non-root path")
    return str(path)


def validate_transfer_config(
    contract: dict[str, Any], timeout_seconds: int
) -> dict[str, Any]:
    render_report.validate_contract(contract)
    if contract.get("schema_version") != 4:
        raise ValueError("SSH bundle publication requires contract schema_version 4")
    target = contract["target"]
    host = str(target.get("host", ""))
    user = str(target.get("user", ""))
    port = int(target.get("port", 22))
    if not HOST_NAME.fullmatch(host) or host.startswith("-"):
        raise ValueError("deployment target host is invalid")
    if not USER_NAME.fullmatch(user):
        raise ValueError("deployment target user is invalid")
    if not 1 <= port <= 65535:
        raise ValueError("deployment target port is invalid")
    known_hosts = Path(str(target.get("known_hosts", ""))).expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError(f"known-hosts file is missing: {known_hosts}")
    remote_dir = validate_remote_directory(
        contract["deployment"].get("report_remote_dir", "")
    )
    return {
        "host": host,
        "user": user,
        "port": port,
        "known_hosts": known_hosts,
        "remote_dir": remote_dir,
        "timeout_seconds": validate_timeout(timeout_seconds),
    }


def validate_checksum_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("bundle checksum contains an unsafe path")
    return path.as_posix()


def parse_checksums(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "  " not in line:
            raise ValueError("bundle checksum line is invalid")
        digest, relative = line.split("  ", 1)
        relative = validate_checksum_path(relative)
        if not FULL_SHA256.fullmatch(digest) or relative in result:
            raise ValueError("bundle checksum entry is invalid")
        result[relative] = digest
    if not result:
        raise ValueError("bundle checksum manifest is empty")
    return result


def read_checksums(bundle_dir: Path) -> dict[str, str]:
    return parse_checksums(
        (bundle_dir / "checksums.sha256").read_text(encoding="utf-8")
    )


def validate_bundle(bundle_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    requested_bundle = bundle_dir.expanduser()
    if requested_bundle.is_symlink():
        raise ValueError("bundle-dir must not be a symlink")
    bundle = requested_bundle.resolve()
    if not bundle.is_dir():
        raise ValueError("bundle-dir must be a real directory")
    if not BUNDLE_NAME.fullmatch(bundle.name):
        raise ValueError("bundle name must use YYYYMMDD-HHMMSSZ-<hostname>-deploy")
    for required in ("REPORT.md", "manifest.json", "checksums.sha256"):
        if not (bundle / required).is_file():
            raise ValueError(f"deployment bundle is missing {required}")
    symlinks = [path for path in bundle.rglob("*") if path.is_symlink()]
    if symlinks:
        raise ValueError("deployment bundle must not contain symlinks")
    checksums = read_checksums(bundle)
    actual_files = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
        and path.relative_to(bundle).as_posix() != "checksums.sha256"
    }
    if actual_files != set(checksums):
        raise ValueError("bundle checksum coverage does not match bundle files")
    for relative, expected in checksums.items():
        if file_sha256(bundle / relative) != expected:
            raise ValueError(f"bundle checksum mismatch: {relative}")
    manifest = load_json(bundle / "manifest.json")
    if manifest.get("kind") != "deployment_report_bundle":
        raise ValueError("bundle manifest kind is invalid")
    expected_target = contract["target"]
    manifest_target = manifest.get("target", {})
    if (
        manifest_target.get("host"),
        manifest_target.get("user"),
        int(manifest_target.get("port", 22)),
    ) != (
        expected_target.get("host"),
        expected_target.get("user"),
        int(expected_target.get("port", 22)),
    ):
        raise ValueError("bundle manifest target does not match deployment contract")
    return {
        "path": bundle,
        "name": bundle.name,
        "checksum_manifest_sha256": file_sha256(bundle / "checksums.sha256"),
    }


def ssh_command(config: dict[str, Any], remote_command: str = "bash -s") -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={config['known_hosts']}",
        "-o",
        "LogLevel=ERROR",
        "-p",
        str(config["port"]),
        f"{config['user']}@{config['host']}",
        remote_command,
    ]


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith(SECTION_PREFIX):
            current = line[len(SECTION_PREFIX) :].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def run_remote(
    config: dict[str, Any], script: str, operation: str
) -> tuple[dict[str, str], float]:
    started = time.monotonic()
    result = subprocess.run(
        ssh_command(config),
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=config["timeout_seconds"],
        check=False,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"{operation} failed exit_code={result.returncode} "
            f"duration_seconds={elapsed:.3f}"
        )
    LOG.info("operation completed operation=%s duration_seconds=%.3f", operation, elapsed)
    return split_sections(result.stdout), elapsed


def probe_script(remote_dir: str, bundle_name: str) -> str:
    return f'''set -eu
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
remote_dir={shlex.quote(remote_dir)}
bundle_name={shlex.quote(bundle_name)}
bundle="$remote_dir/$bundle_name"
if [ ! -e "$bundle" ]; then
    section status; printf 'missing\n'
    exit 0
fi
if [ -L "$bundle" ] || [ ! -d "$bundle" ]; then
    section status; printf 'conflict\n'
    exit 0
fi
if find "$bundle" -type l -print -quit | grep -q .; then
    section status; printf 'invalid\n'
    exit 0
fi
expected_files="$(cd "$bundle" && awk '{{print substr($0, 67)}}' checksums.sha256 | LC_ALL=C sort)"
actual_files="$(cd "$bundle" && find . -type f ! -path './checksums.sha256' -printf '%P\n' | LC_ALL=C sort)"
if [ "$actual_files" != "$expected_files" ]; then
    section status; printf 'invalid\n'
    exit 0
fi
if ! (cd "$bundle" && sha256sum -c -- checksums.sha256 >/dev/null 2>&1); then
    section status; printf 'invalid\n'
    exit 0
fi
section status; printf 'ready\n'
section checksum_manifest_sha256
sha256sum -- "$bundle/checksums.sha256" | awk '{{print $1}}'
'''


def probe_remote_bundle(
    config: dict[str, Any], bundle: dict[str, Any]
) -> dict[str, str]:
    sections, _ = run_remote(
        config,
        probe_script(config["remote_dir"], bundle["name"]),
        "remote bundle probe",
    )
    status = sections.get("status", "unknown")
    if status not in {"missing", "ready"}:
        raise ValueError(f"remote bundle is not reusable: {status}")
    return sections


def upload_script(remote_dir: str, bundle_name: str) -> str:
    return f'''set -eu
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
umask 077
remote_dir={shlex.quote(remote_dir)}
bundle_name={shlex.quote(bundle_name)}
final="$remote_dir/$bundle_name"
mkdir -p -- "$remote_dir"
chmod 700 -- "$remote_dir"
if [ -e "$final" ]; then
    printf 'remote bundle already exists\n' >&2
    exit 20
fi
staging="$(mktemp -d "$remote_dir/.${{bundle_name}}.upload.XXXXXX")"
cleanup() {{ rm -rf -- "$staging"; }}
trap cleanup EXIT HUP INT TERM
tar --no-same-owner -xpf - -C "$staging"
candidate="$staging/$bundle_name"
if [ -L "$candidate" ] || [ ! -d "$candidate" ]; then
    printf 'uploaded bundle root is invalid\n' >&2
    exit 21
fi
if find "$candidate" -type l -print -quit | grep -q .; then
    printf 'uploaded bundle contains symlinks\n' >&2
    exit 22
fi
find "$candidate" -type d -exec chmod 700 {{}} +
if [ -d "$candidate/scripts" ]; then
    find "$candidate/scripts" -type f -exec chmod 700 {{}} +
fi
find "$candidate" -type f ! -path "$candidate/scripts/*" -exec chmod 600 {{}} +
(cd "$candidate" && sha256sum -c -- checksums.sha256 >/dev/null)
checksum_manifest_sha256="$(sha256sum -- "$candidate/checksums.sha256" | awk '{{print $1}}')"
mv -- "$candidate" "$final"
rmdir -- "$staging"
trap - EXIT HUP INT TERM
section status; printf 'uploaded\n'
section checksum_manifest_sha256; printf '%s\n' "$checksum_manifest_sha256"
'''


def upload_bundle(config: dict[str, Any], bundle: dict[str, Any]) -> dict[str, str]:
    tar_process = subprocess.Popen(
        [
            "tar",
            "-C",
            str(bundle["path"].parent),
            "-cf",
            "-",
            bundle["name"],
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if tar_process.stdout is None or tar_process.stderr is None:
        tar_process.kill()
        raise RuntimeError("local tar stream could not be created")
    started = time.monotonic()
    try:
        result = subprocess.run(
            ssh_command(
                config,
                f"bash -c {shlex.quote(upload_script(config['remote_dir'], bundle['name']))}",
            ),
            stdin=tar_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=config["timeout_seconds"],
            check=False,
        )
    finally:
        tar_process.stdout.close()
        if tar_process.poll() is None:
            try:
                tar_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                tar_process.kill()
                tar_process.wait()
    tar_error = tar_process.stderr.read().decode(errors="replace")
    tar_process.stderr.close()
    elapsed = time.monotonic() - started
    if tar_process.returncode != 0:
        raise RuntimeError(
            f"local bundle stream failed exit_code={tar_process.returncode} "
            f"duration_seconds={elapsed:.3f} detail={tar_error.strip()}"
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"remote bundle upload failed exit_code={result.returncode} "
            f"duration_seconds={elapsed:.3f}"
        )
    LOG.info("bundle uploaded duration_seconds=%.3f", elapsed)
    return split_sections(result.stdout.decode(errors="replace"))


def ensure_remote_bundle(config: dict[str, Any], bundle: dict[str, Any]) -> None:
    sections = probe_remote_bundle(config, bundle)
    if sections["status"] == "missing":
        sections = upload_bundle(config, bundle)
    if sections.get("status") not in {"ready", "uploaded"}:
        raise ValueError("remote bundle publication did not complete")
    if sections.get("checksum_manifest_sha256") != bundle["checksum_manifest_sha256"]:
        raise ValueError("remote bundle checksum manifest does not match local bundle")


def archive_script(remote_dir: str, bundle_name: str, manifest_sha256: str) -> str:
    return f'''set -eu
section() {{ printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }}
umask 077
remote_dir={shlex.quote(remote_dir)}
bundle_name={shlex.quote(bundle_name)}
expected_manifest_sha256={shlex.quote(manifest_sha256)}
bundle="$remote_dir/$bundle_name"
archive="$remote_dir/${{bundle_name}}.tar.gz"
if [ -L "$bundle" ] || [ ! -d "$bundle" ]; then
    printf 'remote bundle is missing or invalid\n' >&2
    exit 30
fi
if find "$bundle" -type l -print -quit | grep -q .; then
    printf 'remote bundle contains symlinks\n' >&2
    exit 31
fi
expected_files="$(cd "$bundle" && awk '{{print substr($0, 67)}}' checksums.sha256 | LC_ALL=C sort)"
actual_files="$(cd "$bundle" && find . -type f ! -path './checksums.sha256' -printf '%P\n' | LC_ALL=C sort)"
if [ "$actual_files" != "$expected_files" ]; then
    printf 'remote bundle checksum coverage is incomplete\n' >&2
    exit 31
fi
if ! (cd "$bundle" && sha256sum -c -- checksums.sha256 >/dev/null); then
    printf 'remote bundle checksum verification failed\n' >&2
    exit 31
fi
actual_manifest_sha256="$(sha256sum -- "$bundle/checksums.sha256" | awk '{{print $1}}')"
if [ "$actual_manifest_sha256" != "$expected_manifest_sha256" ]; then
    printf 'remote bundle checksum manifest is unexpected\n' >&2
    exit 32
fi
status=existing
if [ -e "$archive" ]; then
    if [ -L "$archive" ] || [ ! -f "$archive" ]; then
        printf 'remote archive path conflicts with another object\n' >&2
        exit 33
    fi
    embedded_manifest_sha256="$(tar -xOzf "$archive" -- "$bundle_name/checksums.sha256" | sha256sum | awk '{{print $1}}')"
    if [ "$embedded_manifest_sha256" != "$expected_manifest_sha256" ]; then
        printf 'existing remote archive does not match bundle\n' >&2
        exit 34
    fi
else
    temporary="$(mktemp "$remote_dir/.${{bundle_name}}.tar.gz.XXXXXX")"
    cleanup() {{ rm -f -- "$temporary"; }}
    trap cleanup EXIT HUP INT TERM
    tar -C "$remote_dir" -czf "$temporary" -- "$bundle_name"
    chmod 600 -- "$temporary"
    embedded_manifest_sha256="$(tar -xOzf "$temporary" -- "$bundle_name/checksums.sha256" | sha256sum | awk '{{print $1}}')"
    if [ "$embedded_manifest_sha256" != "$expected_manifest_sha256" ]; then
        printf 'new remote archive verification failed\n' >&2
        exit 35
    fi
    mv -- "$temporary" "$archive"
    trap - EXIT HUP INT TERM
    status=created
fi
section status; printf '%s\n' "$status"
section remote_archive; printf '%s\n' "$archive"
section archive_sha256; sha256sum -- "$archive" | awk '{{print $1}}'
section archive_size; stat -Lc '%s' -- "$archive"
'''


def archive_remote_bundle(
    config: dict[str, Any], bundle: dict[str, Any]
) -> dict[str, Any]:
    sections, _ = run_remote(
        config,
        archive_script(
            config["remote_dir"],
            bundle["name"],
            bundle["checksum_manifest_sha256"],
        ),
        "remote bundle archive",
    )
    archive_sha256 = sections.get("archive_sha256", "")
    remote_archive = sections.get("remote_archive", "")
    status = sections.get("status", "")
    if status not in {"created", "existing"} or not FULL_SHA256.fullmatch(
        archive_sha256
    ):
        raise ValueError("remote bundle archive evidence is invalid")
    expected_archive = f"{config['remote_dir']}/{bundle['name']}.tar.gz"
    if remote_archive != expected_archive:
        raise ValueError("remote bundle archive path is invalid")
    try:
        archive_size = int(sections.get("archive_size", ""))
    except ValueError as error:
        raise ValueError("remote bundle archive size is invalid") from error
    if archive_size <= 0:
        raise ValueError("remote bundle archive is empty")
    return {
        "path": remote_archive,
        "sha256": archive_sha256,
        "size": archive_size,
        "status": status,
        "bundle_name": bundle["name"],
    }


def validate_archive(archive_path: Path, bundle_name: str) -> None:
    file_hashes: dict[str, str] = {}
    checksum_text: str | None = None
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive:
            member_path = PurePosixPath(member.name)
            if (
                member_path.is_absolute()
                or not member_path.parts
                or member_path.parts[0] != bundle_name
                or any(part in {"", ".", ".."} for part in member_path.parts)
            ):
                raise ValueError("downloaded archive contains an unsafe path")
            if member.isdir():
                continue
            if not member.isreg():
                raise ValueError("downloaded archive contains a non-regular file")
            if len(member_path.parts) == 1:
                raise ValueError("downloaded archive root is not a directory")
            relative = PurePosixPath(*member_path.parts[1:]).as_posix()
            duplicate_checksum = (
                relative == "checksums.sha256" and checksum_text is not None
            )
            if relative in file_hashes or duplicate_checksum:
                raise ValueError("downloaded archive contains a duplicate file")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("downloaded archive file is unreadable")
            if relative == "checksums.sha256":
                try:
                    checksum_text = stream.read().decode("utf-8")
                except UnicodeDecodeError as error:
                    raise ValueError("downloaded checksum manifest is invalid") from error
            else:
                digest = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                file_hashes[relative] = digest.hexdigest()
    if checksum_text is None:
        raise ValueError("downloaded archive has no checksum manifest")
    expected = parse_checksums(checksum_text)
    if set(file_hashes) != set(expected):
        raise ValueError("downloaded archive checksum coverage is incomplete")
    for relative, digest in expected.items():
        if file_hashes[relative] != digest:
            raise ValueError(f"downloaded archive checksum mismatch: {relative}")


def download_remote_archive(
    config: dict[str, Any], archive: dict[str, Any], local_dir: Path
) -> Path:
    destination_dir = local_dir.expanduser().resolve()
    directory_existed = destination_dir.exists()
    destination_dir.mkdir(parents=True, exist_ok=True)
    if not destination_dir.is_dir():
        raise ValueError("local-dir must be a directory")
    if not directory_existed:
        os.chmod(destination_dir, 0o700)
    archive_name = PurePosixPath(str(archive["path"])).name
    destination = destination_dir / archive_name
    if destination.exists():
        if not destination.is_file() or file_sha256(destination) != archive["sha256"]:
            raise ValueError("local archive already exists with different content")
        validate_archive(destination, str(archive["bundle_name"]))
        os.chmod(destination, 0o600)
        return destination
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_name}.", suffix=".partial", dir=destination_dir
    )
    temporary = Path(temporary_name)
    started = time.monotonic()
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.chmod(temporary, 0o600)
            result = subprocess.run(
                ssh_command(
                    config,
                    f"cat -- {shlex.quote(str(archive['path']))}",
                ),
                stdout=stream,
                stderr=subprocess.PIPE,
                timeout=config["timeout_seconds"],
                check=False,
            )
        elapsed = time.monotonic() - started
        if result.returncode != 0:
            raise RuntimeError(
                f"archive download failed exit_code={result.returncode} "
                f"duration_seconds={elapsed:.3f}"
            )
        if file_sha256(temporary) != archive["sha256"]:
            raise ValueError("downloaded archive SHA-256 does not match server evidence")
        if temporary.stat().st_size != archive["size"]:
            raise ValueError("downloaded archive size does not match server evidence")
        validate_archive(temporary, str(archive["bundle_name"]))
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        LOG.info(
            "archive downloaded bytes=%d duration_seconds=%.3f",
            destination.stat().st_size,
            elapsed,
        )
        return destination
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def publish_and_download(args: argparse.Namespace) -> dict[str, Any]:
    contract = load_json(args.contract)
    config = validate_transfer_config(contract, args.timeout_seconds)
    bundle = validate_bundle(args.bundle_dir, contract)
    ensure_remote_bundle(config, bundle)
    archive = archive_remote_bundle(config, bundle)
    local_archive = download_remote_archive(config, archive, args.local_dir)
    return {
        "remote_bundle": f"{config['remote_dir']}/{bundle['name']}",
        "remote_archive": archive["path"],
        "local_archive": str(local_archive),
        "archive_sha256": archive["sha256"],
        "archive_size": archive["size"],
    }


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        result = publish_and_download(args)
        print(
            f"remote_bundle={result['remote_bundle']} "
            f"remote_archive={result['remote_archive']} "
            f"local_archive={result['local_archive']} "
            f"sha256={result['archive_sha256']} bytes={result['archive_size']}"
        )
        return 0
    except (
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
        tarfile.TarError,
    ) as error:
        LOG.error("report bundle publication failed error_type=%s", type(error).__name__)
        return 2


if __name__ == "__main__":
    sys.exit(main())
