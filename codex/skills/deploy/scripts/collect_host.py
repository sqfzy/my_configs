#!/usr/bin/env python3
"""Collect a read-only deployment inventory from a remote systemd host."""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


LOG = logging.getLogger("deploy.collect_host")
SECTION_PREFIX = "__DEPLOY_SECTION__ "
SENSITIVE_NAME = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)"
)
SENSITIVE_ARGUMENT = re.compile(
    r"(?i)(--?(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)(?:=|\s+))([^\s,;]+)"
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|credential|authorization)=)([^\s,;]+)"
)
URI_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)
HOST_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
USER_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$", re.IGNORECASE)


REMOTE_PROBE = r'''set -u
section() { printf '\n__DEPLOY_SECTION__ %s\n' "$1"; }
show_value() { systemctl show "$1" --value -p "$2" 2>/dev/null || true; }
unit_pids() {
    local control_group
    control_group=$(show_value "$1" ControlGroup)
    if [ -n "$control_group" ] && [ -d "/sys/fs/cgroup${control_group}" ]; then
        find "/sys/fs/cgroup${control_group}" -name cgroup.procs -type f -exec cat {} \; 2>/dev/null | sort -nu
    fi
}
custom_units() {
    systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null |
        awk '{print $1}' |
        while IFS= read -r unit; do
            fragment=$(show_value "$unit" FragmentPath)
            [ -n "$fragment" ] || continue
            resolved=$(readlink -f "$fragment" 2>/dev/null || true)
            case "$resolved" in
                /etc/systemd/system/*) printf '%s\n' "$unit" ;;
            esac
        done
}

section os_release
cat /etc/os-release 2>/dev/null || true
section hostname
hostname 2>/dev/null || true
section kernel
uname -srvo 2>/dev/null || true
section architecture
uname -m 2>/dev/null || true
section init
ps -p 1 -o comm= 2>/dev/null || true
section cpu_summary
lscpu -J 2>/dev/null || lscpu 2>/dev/null || true
section cpu_topology
lscpu -J -e=CPU,NODE,SOCKET,CORE,ONLINE 2>/dev/null || lscpu -e=CPU,NODE,SOCKET,CORE,ONLINE 2>/dev/null || true
section memory
cat /proc/meminfo 2>/dev/null || true
section block_devices
lsblk -J -b -o NAME,KNAME,PATH,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL,SERIAL 2>/dev/null || true
section filesystems
findmnt -J -b -o SOURCE,TARGET,FSTYPE,SIZE,USED,AVAIL,USE% 2>/dev/null || true
section network_links
ip -j -details link show 2>/dev/null || true
section network_addresses
ip -j address show 2>/dev/null || true
section network_routes
ip -j route show table main 2>/dev/null || true
section network_devices
for interface_path in /sys/class/net/*; do
    [ -e "$interface_path" ] || continue
    interface=${interface_path##*/}
    device=$(readlink -f "$interface_path/device" 2>/dev/null || true)
    printf '%s\037%s\n' "$interface" "$device"
done
section aws_metadata
if command -v curl >/dev/null 2>&1; then
    token=$(curl -fsS --max-time 1 -X PUT \
        -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' \
        http://169.254.169.254/latest/api/token 2>/dev/null || true)
    if [ -n "$token" ]; then
        metadata() {
            curl -fsS --max-time 1 -H "X-aws-ec2-metadata-token: $token" \
                "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null || true
        }
        printf 'instance-id\037%s\n' "$(metadata instance-id)"
        printf 'instance-type\037%s\n' "$(metadata instance-type)"
        printf 'region\037%s\n' "$(metadata placement/region)"
        printf 'public-ipv4\037%s\n' "$(metadata public-ipv4)"
        macs=$(metadata network/interfaces/macs/)
        for mac in $macs; do
            printf 'interface\037%s\037%s\037%s\037%s\037%s\037%s\n' \
                "${mac%/}" \
                "$(metadata network/interfaces/macs/${mac}device-number)" \
                "$(metadata network/interfaces/macs/${mac}interface-id)" \
                "$(metadata network/interfaces/macs/${mac}local-ipv4s)" \
                "$(metadata network/interfaces/macs/${mac}public-ipv4s)" \
                "$(metadata network/interfaces/macs/${mac}subnet-id)"
        done
    fi
fi
section services
mapfile -t deploy_units < <(custom_units)
for unit in "${deploy_units[@]}"; do
    fragment=$(show_value "$unit" FragmentPath)
    resolved=$(readlink -f "$fragment" 2>/dev/null || true)
    pids=$(unit_pids "$unit" | paste -sd, -)
    allowed=""
    if [ -n "$pids" ]; then
        IFS=, read -ra pid_values <<< "$pids"
        for pid in "${pid_values[@]}"; do
            value=$(awk '/^Cpus_allowed_list:/ {print $2}' "/proc/$pid/status" 2>/dev/null || true)
            [ -n "$value" ] && allowed="${allowed:+${allowed};}${value}"
        done
    fi
    printf '%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\n' \
        "$unit" "$fragment" "$resolved" \
        "$(show_value "$unit" UnitFileState)" \
        "$(show_value "$unit" ActiveState)" \
        "$(show_value "$unit" SubState)" \
        "$(show_value "$unit" Type)" \
        "$(show_value "$unit" RemainAfterExit)" \
        "$(show_value "$unit" MainPID)" \
        "$(show_value "$unit" Result)" \
        "$(show_value "$unit" ExecStart)" \
        "$(show_value "$unit" WorkingDirectory)" \
        "$(show_value "$unit" EnvironmentFiles)" \
        "$(show_value "$unit" CPUAffinity)" \
        "$pids" "$allowed"
done
section cpu_observations
declare -A observed=()
sample_seconds=${DEPLOY_SAMPLE_SECONDS:-10}
for ((sample=0; sample<sample_seconds; sample++)); do
    for unit in "${deploy_units[@]}"; do
        while IFS= read -r pid; do
            [ -n "$pid" ] || continue
            while IFS= read -r cpu; do
                cpu=${cpu//[[:space:]]/}
                [ -n "$cpu" ] && observed["$unit|$cpu"]=1
            done < <(ps -L -p "$pid" -o psr= 2>/dev/null || true)
        done < <(unit_pids "$unit")
    done
    [ "$sample" -ge "$((sample_seconds - 1))" ] || sleep 1
done
for key in "${!observed[@]}"; do
    printf '%s\n' "$key"
done
section sockets
ss -Htunap 2>/dev/null || true
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--known-hosts", default="~/.ssh/known_hosts")
    parser.add_argument("--sample-seconds", type=int, default=10)
    parser.add_argument("--exclude-unit", action="append", default=["alertd.service"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-supported", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> Path:
    try:
        ipaddress.ip_address(args.host)
    except ValueError:
        if not HOST_PATTERN.fullmatch(args.host):
            raise ValueError(f"invalid SSH host: {args.host!r}")
    if not USER_PATTERN.fullmatch(args.user):
        raise ValueError(f"invalid SSH user: {args.user!r}")
    if not 1 <= args.port <= 65535:
        raise ValueError("SSH port must be in 1..=65535")
    if not 5 <= args.sample_seconds <= 60:
        raise ValueError("sample seconds must be in 5..=60")
    known_hosts = Path(args.known_hosts).expanduser().resolve()
    if not known_hosts.is_file():
        raise ValueError(f"known-hosts file is missing: {known_hosts}")
    return known_hosts


def run_probe(args: argparse.Namespace, known_hosts: Path) -> tuple[str, float]:
    target = f"{args.user}@{args.host}"
    command = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "LogLevel=ERROR",
        "-p", str(args.port),
        target,
        f"DEPLOY_SAMPLE_SECONDS={args.sample_seconds} bash -s",
    ]
    started = time.monotonic()
    LOG.info("collecting host snapshot target=%s sample_seconds=%d", target, args.sample_seconds)
    result = subprocess.run(
        command,
        input=REMOTE_PROBE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=args.sample_seconds + 45,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"remote inventory failed after {elapsed:.3f}s: {result.stderr.strip()}"
        )
    LOG.info("host snapshot collected duration_seconds=%.3f", elapsed)
    return result.stdout, elapsed


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


def parse_key_values(text: str, separator: str = "=") -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if separator not in line:
            continue
        key, value = line.split(separator, 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def parse_json(text: str, fallback: Any) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return fallback


def parse_lscpu_summary(text: str) -> dict[str, str]:
    data = parse_json(text, {})
    if isinstance(data, dict) and isinstance(data.get("lscpu"), list):
        return {
            str(item.get("field", "")).rstrip(":"): str(item.get("data", ""))
            for item in data["lscpu"]
        }
    return parse_key_values(text, ":")


def parse_cpu_topology(text: str) -> list[dict[str, Any]]:
    data = parse_json(text, {})
    rows = data.get("cpus", []) if isinstance(data, dict) else []
    topology: list[dict[str, Any]] = []
    for row in rows:
        normalized = {str(key).lower(): value for key, value in row.items()}
        topology.append(
            {
                "cpu": integer_or_none(normalized.get("cpu")),
                "node": integer_or_none(normalized.get("node")),
                "socket": integer_or_none(normalized.get("socket")),
                "core": integer_or_none(normalized.get("core")),
                "online": str(normalized.get("online", "yes")).lower() in {"yes", "y", "1", "true"},
            }
        )
    return sorted((row for row in topology if row["cpu"] is not None), key=lambda row: row["cpu"])


def integer_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def parse_memory(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"([^:]+):\s+(\d+)\s+kB", line)
        if match:
            result[match.group(1)] = int(match.group(2)) * 1024
    return result


def redact(value: str) -> str:
    value = URI_USERINFO.sub(r"\1<redacted>@", value)
    value = SENSITIVE_ARGUMENT.sub(lambda match: f"{match.group(1)}<redacted>", value)
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}<redacted>", value)


def expand_cpu_lists(values: list[str]) -> list[int]:
    cpus: set[int] = set()
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                first, last = part.split("-", 1)
                if first.isdigit() and last.isdigit():
                    cpus.update(range(int(first), int(last) + 1))
            elif part.isdigit():
                cpus.add(int(part))
    return sorted(cpus)


def parse_services(text: str, excluded: set[str]) -> list[dict[str, Any]]:
    fields = [
        "unit", "fragment_path", "resolved_fragment_path", "unit_file_state",
        "active_state", "sub_state", "service_type", "remain_after_exit",
        "main_pid", "result", "exec_start", "working_directory",
        "environment_files", "cpu_affinity", "pids", "allowed_cpu_lists",
    ]
    services: list[dict[str, Any]] = []
    for line in text.splitlines():
        values = line.split("\x1f")
        if len(values) != len(fields):
            LOG.warning("skipping malformed service record fields=%d", len(values))
            continue
        service = dict(zip(fields, values, strict=True))
        if service["unit"] in excluded:
            continue
        service["main_pid"] = integer_or_none(service["main_pid"])
        service["pids"] = [int(pid) for pid in service["pids"].split(",") if pid.isdigit()]
        allowed_lists = [item for item in service["allowed_cpu_lists"].split(";") if item]
        service["effective_allowed_cpus"] = expand_cpu_lists(allowed_lists)
        service["configured_cpu_affinity"] = expand_cpu_lists([service.pop("cpu_affinity")])
        service.pop("allowed_cpu_lists")
        service["exec_start"] = redact(service["exec_start"])
        service["environment_files"] = redact(service["environment_files"])
        service["observed_cpus"] = []
        service["network_interfaces"] = []
        services.append(service)
    return sorted(services, key=lambda service: service["unit"])


def add_cpu_observations(services: list[dict[str, Any]], text: str) -> None:
    by_unit = {service["unit"]: service for service in services}
    for line in text.splitlines():
        unit, separator, cpu = line.rpartition("|")
        if not separator or unit not in by_unit or not cpu.isdigit():
            continue
        by_unit[unit]["observed_cpus"].append(int(cpu))
    for service in services:
        service["observed_cpus"] = sorted(set(service["observed_cpus"]))


def parse_delimited_records(text: str) -> list[list[str]]:
    return [line.split("\x1f") for line in text.splitlines() if line]


def parse_aws_metadata(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {"interfaces": []}
    for record in parse_delimited_records(text):
        if len(record) == 2:
            metadata[record[0].replace("-", "_")] = record[1]
        elif len(record) == 7 and record[0] == "interface":
            metadata["interfaces"].append(
                {
                    "mac": record[1],
                    "device_number": record[2],
                    "interface_id": record[3],
                    "private_ipv4": record[4].split(),
                    "public_ipv4": record[5].split(),
                    "subnet_id": record[6],
                }
            )
    return metadata


def index_addresses(addresses: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in addresses:
        interface = str(item.get("ifname", ""))
        for address in item.get("addr_info", []):
            local = address.get("local")
            if local:
                result[str(local)] = interface
    return result


def default_interfaces(routes: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(route.get("dev"))
            for route in routes
            if route.get("dst") == "default" and route.get("dev")
        }
    )


def add_network_attribution(
    services: list[dict[str, Any]],
    sockets: str,
    links: list[dict[str, Any]],
    addresses: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    devices: list[list[str]],
) -> None:
    by_pid: dict[int, dict[str, Any]] = {}
    for service in services:
        for pid in service["pids"]:
            by_pid[pid] = service
    address_index = index_addresses(addresses)
    defaults = default_interfaces(routes)
    known_interfaces = [str(link.get("ifname", "")) for link in links if link.get("ifname")]
    pci_by_interface = {
        record[0]: Path(record[1]).name
        for record in devices
        if len(record) == 2 and record[1]
    }

    for line in sockets.splitlines():
        columns = line.split()
        if len(columns) < 6:
            continue
        local_endpoint, peer_endpoint = columns[4], columns[5]
        local_host = endpoint_host(local_endpoint)
        peer_host = endpoint_host(peer_endpoint)
        interface = address_index.get(local_host)
        if not interface and peer_host not in {"*", "0.0.0.0", "::"} and defaults:
            interface = defaults[0]
        for pid_text in re.findall(r"pid=(\d+)", line):
            service = by_pid.get(int(pid_text))
            if service and interface:
                service["network_interfaces"].append(
                    {"interface": interface, "evidence": "observed", "basis": "kernel socket and route"}
                )

    for service in services:
        command = service["exec_start"]
        for interface in known_interfaces:
            if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(interface)}(?![A-Za-z0-9_.-])", command):
                service["network_interfaces"].append(
                    {"interface": interface, "evidence": "inferred", "basis": "unit ExecStart"}
                )
        for interface, pci_address in pci_by_interface.items():
            if pci_address and pci_address in command:
                service["network_interfaces"].append(
                    {"interface": interface, "evidence": "inferred", "basis": f"PCI device {pci_address} in ExecStart"}
                )
        unique = {
            (item["interface"], item["evidence"], item["basis"]): item
            for item in service["network_interfaces"]
        }
        service["network_interfaces"] = sorted(unique.values(), key=lambda item: item["interface"])


def endpoint_host(endpoint: str) -> str:
    if endpoint.startswith("[") and "]:" in endpoint:
        return endpoint[1:endpoint.rfind("]:")]
    host, separator, _port = endpoint.rpartition(":")
    return host if separator else endpoint


def build_snapshot(
    args: argparse.Namespace,
    sections: dict[str, str],
    elapsed: float,
) -> dict[str, Any]:
    os_release = parse_key_values(sections.get("os_release", ""))
    architecture = sections.get("architecture", "").strip()
    init = sections.get("init", "").strip()
    supported = (
        os_release.get("ID") == "amzn"
        and os_release.get("VERSION_ID") == "2023"
        and architecture == "aarch64"
        and init == "systemd"
    )
    links = parse_json(sections.get("network_links", ""), [])
    addresses = parse_json(sections.get("network_addresses", ""), [])
    routes = parse_json(sections.get("network_routes", ""), [])
    devices = parse_delimited_records(sections.get("network_devices", ""))
    services = parse_services(sections.get("services", ""), set(args.exclude_unit))
    add_cpu_observations(services, sections.get("cpu_observations", ""))
    add_network_attribution(
        services,
        sections.get("sockets", ""),
        links,
        addresses,
        routes,
        devices,
    )
    return {
        "schema_version": 1,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "collection_duration_seconds": round(elapsed, 3),
        "target": {"host": args.host, "user": args.user, "port": args.port},
        "support": {
            "supported": supported,
            "required": "Amazon Linux 2023 aarch64 with systemd",
        },
        "machine": {
            "hostname": sections.get("hostname", "").strip(),
            "os_release": os_release,
            "kernel": sections.get("kernel", "").strip(),
            "architecture": architecture,
            "init": init,
            "aws": parse_aws_metadata(sections.get("aws_metadata", "")),
        },
        "cpu": {
            "summary": parse_lscpu_summary(sections.get("cpu_summary", "")),
            "topology": parse_cpu_topology(sections.get("cpu_topology", "")),
            "sample_seconds": args.sample_seconds,
        },
        "memory": parse_memory(sections.get("memory", "")),
        "storage": {
            "block_devices": parse_json(sections.get("block_devices", ""), {}).get("blockdevices", []),
            "filesystems": parse_json(sections.get("filesystems", ""), {}).get("filesystems", []),
        },
        "network": {
            "links": links,
            "addresses": addresses,
            "routes": routes,
            "devices": [
                {"interface": record[0], "device_path": record[1]}
                for record in devices if len(record) == 2
            ],
        },
        "services": services,
    }


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    LOG.info("snapshot written path=%s bytes=%d", output, output.stat().st_size)


def print_summary(snapshot: dict[str, Any], output: Path) -> None:
    memory_total = snapshot["memory"].get("MemTotal", 0)
    services = snapshot["services"]
    active = sum(service["active_state"] == "active" for service in services)
    print(
        f"host={snapshot['machine']['hostname']} "
        f"platform={snapshot['machine']['os_release'].get('PRETTY_NAME', 'unknown')} "
        f"arch={snapshot['machine']['architecture']} "
        f"cpus={len(snapshot['cpu']['topology'])} "
        f"memory_gib={memory_total / (1024 ** 3):.2f} "
        f"business_services={len(services)} active={active} "
        f"supported={str(snapshot['support']['supported']).lower()} "
        f"snapshot={output.expanduser().resolve()}"
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        known_hosts = validate_args(args)
        raw, elapsed = run_probe(args, known_hosts)
        snapshot = build_snapshot(args, split_sections(raw), elapsed)
        write_snapshot(snapshot, args.output)
        print_summary(snapshot, args.output)
        if args.require_supported and not snapshot["support"]["supported"]:
            LOG.error("unsupported target: %s", snapshot["support"]["required"])
            return 2
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        LOG.error("host collection failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
