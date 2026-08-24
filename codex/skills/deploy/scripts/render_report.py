#!/usr/bin/env python3
"""Render a redacted deployment report from frozen contract and snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

LOG = logging.getLogger("deploy.render_report")
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
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)}}")
VIRTUAL_FILESYSTEMS = {
    "autofs",
    "binfmt_misc",
    "bpf",
    "cgroup",
    "cgroup2",
    "configfs",
    "debugfs",
    "devpts",
    "devtmpfs",
    "efivarfs",
    "fusectl",
    "hugetlbfs",
    "mqueue",
    "nsfs",
    "overlay",
    "proc",
    "pstore",
    "ramfs",
    "rootfs",
    "rpc_pipefs",
    "securityfs",
    "selinuxfs",
    "squashfs",
    "sysfs",
    "tmpfs",
    "tracefs",
}
NORMAL_DISCOVERED_OUTPUT_STATUSES = {
    "active",
    "exists",
    "matches",
    "observed_mapped",
    "observed_mapped_deleted",
    "observed_open_writable",
    "writable_parent",
}
OUTPUT_CATEGORY_LABELS = {
    "log": "日志",
    "data": "数据",
    "dump": "Dump",
    "archive": "归档",
    "shared_memory": "SHM",
    "hugepage": "Hugepage",
    "dpdk": "DPDK",
    "other": "其他",
}
OUTPUT_CATEGORY_ORDER = tuple(OUTPUT_CATEGORY_LABELS)
REPRESENTATIVE_CATEGORY_ORDER = (
    "hugepage",
    "dpdk",
    "log",
    "data",
    "dump",
    "archive",
    "shared_memory",
    "other",
)
MAPPED_EVIDENCE = re.compile(r"^mapped pid=(\d+) permissions=([^\s]+)$")
WRITABLE_FD_EVIDENCE = re.compile(r"^open_writable pid=(\d+)(?:\s|$)")


def parse_args() -> argparse.Namespace:
    default_template = Path(__file__).resolve().parent.parent / "assets" / "report-template.md"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--status", required=True, choices=["succeeded", "failed", "rolled_back"])
    parser.add_argument("--template", type=Path, default=default_template)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_json(path: Path | None, required: bool = True) -> dict[str, Any]:
    if path is None:
        return {}
    expanded = path.expanduser()
    if not expanded.is_file():
        if required:
            raise ValueError(f"JSON input is missing: {expanded}")
        return {}
    value = json.loads(expanded.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {expanded}")
    return value


def validate_contract(contract: dict[str, Any]) -> None:
    schema_version = contract.get("schema_version")
    if schema_version not in {1, 2, 3}:
        raise ValueError("contract schema_version must be 1, 2, or 3")
    if schema_version in {1, 2} and contract.get("mode") not in {"interactive", "auto"}:
        raise ValueError("historical contract mode must be interactive or auto")
    if schema_version == 3 and "mode" in contract:
        raise ValueError("contract schema_version 3 must not contain mode")
    required_objects = ["target", "deployment", "health"]
    for name in required_objects:
        if not isinstance(contract.get(name), dict):
            raise ValueError(f"contract {name} must be an object")
    required_lists = ["repositories", "changes", "key_config", "reproduce", "rollback", "irreversible_changes"]
    if schema_version in {2, 3}:
        required_lists.append("program_outputs")
    for name in required_lists:
        if not isinstance(contract.get(name), list):
            raise ValueError(f"contract {name} must be a list")
    if not contract["repositories"]:
        raise ValueError("contract needs at least one repository")
    legacy_auto = schema_version in {1, 2} and contract.get("mode") == "auto"
    if (schema_version == 3 or legacy_auto) and contract["irreversible_changes"]:
        raise ValueError("automatic contract cannot contain irreversible changes")
    for repository in contract["repositories"]:
        commit = str(repository.get("commit", ""))
        if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
            raise ValueError(f"repository commit is not a full SHA: {commit!r}")
    for change in contract["changes"]:
        if not str(change.get("path", "")).startswith("/") or not change.get("rollback"):
            raise ValueError("each change needs an absolute path and rollback action")
    deployment = contract["deployment"]
    if int(deployment.get("min_free_percent", 0)) < 10:
        raise ValueError("min_free_percent cannot be below 10")
    if int(deployment.get("observe_seconds", 0)) < 300:
        raise ValueError("observe_seconds cannot be below 300")
    if schema_version == 2:
        units = {str(unit) for unit in deployment.get("service_units", [])} | {"alertd.service"}
        covered = {
            str(output.get("service", ""))
            for output in contract["program_outputs"]
            if isinstance(output, dict)
        }
        if units - covered:
            raise ValueError(f"program_outputs does not cover units: {', '.join(sorted(units - covered))}")


def redact_scalar(name: str, value: Any) -> str:
    if SENSITIVE_NAME.search(name):
        return "<redacted>"
    text = str(value)
    text = URI_USERINFO.sub(r"\1<redacted>@", text)
    text = SENSITIVE_ARGUMENT.sub(lambda match: f"{match.group(1)}<redacted>", text)
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}<redacted>", text)


def markdown(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def human_bytes(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "unknown"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}"
        amount /= 1024
    return "unknown"


def status_label(status: str) -> str:
    return {"succeeded": "成功", "failed": "失败", "rolled_back": "已回滚"}[status]


def render_summary(status: str, contract: dict[str, Any], before: dict[str, Any], gate: dict[str, Any]) -> str:
    target = contract["target"]
    health = "通过" if gate.get("healthy") else ("未提供" if not gate else "失败")
    mode = ""
    if contract.get("schema_version") in {1, 2}:
        mode = f"- **模式：** `{markdown(contract['mode'])}`\n"
    return (
        f"- **状态：** {status_label(status)}\n"
        f"- **自动执行：** {status_label(status)}\n"
        f"{mode}"
        f"- **目标：** `{markdown(target.get('user', ''))}@{markdown(target.get('host', ''))}:{target.get('port', 22)}`\n"
        f"- **主机：** `{markdown(before.get('machine', {}).get('hostname', 'unknown'))}`\n"
        f"- **健康观察：** {health}\n"
        f"- **生成时间：** {dt.datetime.now(dt.timezone.utc).isoformat()}"
    )


def render_machine(before: dict[str, Any], after: dict[str, Any]) -> str:
    current = after or before
    machine = current.get("machine", {})
    os_release = machine.get("os_release", {})
    cpu_summary = current.get("cpu", {}).get("summary", {})
    aws = machine.get("aws", {})
    rows = [
        ("主机名", machine.get("hostname", "unknown")),
        ("操作系统", os_release.get("PRETTY_NAME", "unknown")),
        ("内核", machine.get("kernel", "unknown")),
        ("架构", machine.get("architecture", "unknown")),
        ("CPU 型号", cpu_summary.get("Model name", cpu_summary.get("BIOS Model name", "unknown"))),
        ("逻辑 CPU", len(current.get("cpu", {}).get("topology", []))),
        ("AWS 区域", aws.get("region", "unknown")),
        ("实例 ID", aws.get("instance_id", "unknown")),
        ("实例类型", aws.get("instance_type", "unknown")),
    ]
    return table(["字段", "值"], [[name, markdown(value)] for name, value in rows])


def render_network(snapshot: dict[str, Any]) -> str:
    network = snapshot.get("network", {})
    addresses_by_interface: dict[str, list[str]] = {}
    for item in network.get("addresses", []):
        addresses_by_interface[str(item.get("ifname", "unknown"))] = [
            f"{address.get('local')}/{address.get('prefixlen')}"
            for address in item.get("addr_info", []) if address.get("local")
        ]
    rows: list[list[Any]] = []
    for link in network.get("links", []):
        interface = str(link.get("ifname", "unknown"))
        rows.append(
            [
                interface,
                link.get("operstate", "unknown"),
                link.get("address", ""),
                ", ".join(addresses_by_interface.get(interface, [])) or "—",
                link.get("mtu", ""),
            ]
        )
    aws = snapshot.get("machine", {}).get("aws", {})
    link_by_mac = {
        str(link.get("address", "")).lower(): str(link.get("ifname", ""))
        for link in network.get("links", []) if link.get("address")
    }
    eni_rows = []
    for item in aws.get("interfaces", []):
        eni_rows.append(
            [
                item.get("device_number", ""),
                item.get("interface_id", ""),
                item.get("mac", ""),
                link_by_mac.get(str(item.get("mac", "")).lower(), "内核不可见/可能已解绑"),
                ", ".join(item.get("private_ipv4", [])) or "—",
                ", ".join(item.get("public_ipv4", [])) or "—",
                item.get("subnet_id", ""),
            ]
        )
    public_ips = sorted(
        {
            value
            for item in aws.get("interfaces", [])
            for value in item.get("public_ipv4", [])
        }
        | ({str(aws.get("public_ipv4"))} if aws.get("public_ipv4") else set())
    )
    route_rows = [
        [route.get("dst", ""), route.get("gateway", "—"), route.get("dev", "—"), route.get("metric", "—")]
        for route in network.get("routes", [])
    ]
    result = table(["网卡", "状态", "MAC", "地址", "MTU"], rows)
    result += f"\n\n**公网 IP：** {', '.join(public_ips) if public_ips else '未从 IMDS 获得'}"
    result += "\n\n### AWS ENI\n\n"
    result += table(["设备序号", "ENI", "MAC", "内核接口", "私网 IP", "公网 IP", "子网"], eni_rows)
    result += "\n\n" + table(["目的", "网关", "网卡", "Metric"], route_rows)
    service_rows: list[list[Any]] = []
    for service in snapshot.get("services", []):
        attributions = service.get("network_interfaces", [])
        if not attributions:
            service_rows.append([service["unit"], "unknown", "unknown", "无可验证的内核 socket 或显式绑定"])
        for attribution in attributions:
            service_rows.append(
                [service["unit"], attribution["interface"], attribution["evidence"], attribution["basis"]]
            )
    result += "\n\n### 业务服务网卡归属\n\n"
    result += table(["服务", "网卡", "证据", "依据"], service_rows)
    return result


def render_cpu(snapshot: dict[str, Any]) -> str:
    topology = snapshot.get("cpu", {}).get("topology", [])
    services = snapshot.get("services", [])
    all_cpus = [row.get("cpu") for row in topology if row.get("cpu") is not None]
    rows: list[list[Any]] = []
    covered_units: set[str] = set()
    for cpu in topology:
        cpu_id = cpu.get("cpu")
        eligible: list[str] = []
        observed: list[str] = []
        for service in services:
            allowed = service.get("configured_cpu_affinity") or service.get("effective_allowed_cpus")
            if not allowed and service.get("pids"):
                allowed = all_cpus
            if cpu_id in allowed:
                evidence = "configured" if service.get("configured_cpu_affinity") else "observed-effective"
                eligible.append(f"{service['unit']} ({evidence})")
                covered_units.add(service["unit"])
            if cpu_id in service.get("observed_cpus", []):
                observed.append(service["unit"])
                covered_units.add(service["unit"])
        rows.append(
            [
                cpu_id,
                cpu.get("socket", "—"),
                cpu.get("core", "—"),
                cpu.get("node", "—"),
                "<br>".join(eligible) or "—",
                "<br>".join(observed) or "—",
            ]
        )
    inactive = [
        f"{service['unit']} ({service.get('active_state', 'unknown')}/{service.get('sub_state', 'unknown')})"
        for service in services if service["unit"] not in covered_units
    ]
    rows.append(["未运行/不适用", "—", "—", "—", "<br>".join(inactive) or "—", "—"])
    return table(["CPU", "Socket", "Core", "NUMA", "允许/配置服务", "采样实际服务"], rows)


def flatten_filesystems(filesystems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for filesystem in filesystems:
        result.append(filesystem)
        result.extend(flatten_filesystems(filesystem.get("children", [])))
    return result


def persistent_filesystems(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    filesystems = flatten_filesystems(snapshot.get("storage", {}).get("filesystems", []))
    for filesystem in filesystems:
        filesystem_type = str(filesystem.get("fstype", "")).lower()
        source = str(filesystem.get("source", ""))
        if not source or filesystem_type in VIRTUAL_FILESYSTEMS or source in {"none", "tmpfs"}:
            continue
        source_key = filesystem_source_key(source)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        result.append(filesystem)
    return result


def filesystem_source_key(source: str) -> str:
    match = re.fullmatch(r"(.+)\[/.*]", source)
    return match.group(1) if match else source


def summarize_storage(snapshot: dict[str, Any]) -> dict[str, int] | None:
    filesystems = persistent_filesystems(snapshot)
    values = {
        name: sum(integer_or_zero(filesystem.get(name)) for filesystem in filesystems)
        for name in ("size", "used", "avail")
    }
    return values if filesystems else None


def integer_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def storage_usage(summary: dict[str, int] | None) -> str:
    if not summary or summary["size"] <= 0:
        return "unknown"
    return f"{summary['used'] / summary['size'] * 100:.1f}%"


def render_capacity(before: dict[str, Any], after: dict[str, Any]) -> str:
    current = after or before
    memory = current.get("memory", {})
    memory_table = table(
        ["指标", "部署前", "部署后"],
        [
            ["总内存", human_bytes(before.get("memory", {}).get("MemTotal")), human_bytes(current.get("memory", {}).get("MemTotal"))],
            ["可用内存", human_bytes(before.get("memory", {}).get("MemAvailable")), human_bytes(memory.get("MemAvailable"))],
        ],
    )
    before_storage = summarize_storage(before)
    after_storage = summarize_storage(current)
    rows = [
        [
            "持久化文件系统汇总",
            human_bytes(before_storage.get("size") if before_storage else None),
            human_bytes(before_storage.get("used") if before_storage else None),
            human_bytes(after_storage.get("size") if after_storage else None),
            human_bytes(after_storage.get("used") if after_storage else None),
            human_bytes(after_storage.get("avail") if after_storage else None),
            storage_usage(after_storage),
        ]
    ]
    return memory_table + "\n\n" + table(
        ["范围", "部署前总容量", "部署前已用", "部署后总容量", "部署后已用", "部署后可用", "部署后使用率"],
        rows,
    )


def render_repositories(contract: dict[str, Any]) -> str:
    rows = []
    for repository in contract.get("repositories", []):
        rows.append(
            [
                repository.get("role", "application"),
                redact_scalar("url", repository.get("url", "")),
                repository.get("target", ""),
                repository.get("commit", ""),
                repository.get("builder_image_digest", "—"),
                repository.get("artifact_sha256", "—"),
            ]
        )
    return table(["角色", "仓库", "Target", "Commit", "构建镜像", "制品 SHA-256"], rows)


def render_key_config(contract: dict[str, Any]) -> str:
    rows = [
        [item.get("name", ""), item.get("source", ""), redact_scalar(str(item.get("name", "")), item.get("value", ""))]
        for item in contract.get("key_config", [])
    ]
    return table(["配置", "来源", "最终生效值"], rows)


def render_program_outputs(contract: dict[str, Any], output_result: dict[str, Any]) -> str:
    if contract.get("schema_version") == 1:
        return "程序产出未记录（历史 schema v1 契约）。"
    if not output_result:
        key_entries = [
            {**output, "status": "未验证", "matches": []}
            for output in contract.get("program_outputs", [])
        ]
        summarized_entries: list[dict[str, Any]] = []
        gate_summary = "产出门禁结果未提供。"
    else:
        declared = output_result.get("declared", [])
        discovered = output_result.get("discovered", [])
        key_entries = [*declared, *(entry for entry in discovered if is_key_output(entry))]
        summarized_entries = [entry for entry in discovered if not is_key_output(entry)]
        gate_summary = (
            f"产出门禁：{'通过' if output_result.get('healthy') else '失败'}；"
            f"阶段 `{markdown(output_result.get('phase', 'unknown'))}`；"
            f"必需失败 {len(output_result.get('failures', []))} 项；"
            f"可选告警 {len(output_result.get('warnings', []))} 项。"
        )
    service_count = len({str(entry.get("service", "unknown")) for entry in summarized_entries})
    overview = (
        f"关键详情 {len(key_entries)} 项；健康运行时产出 {len(summarized_entries)} 项"
        f"按 {service_count} 个服务汇总。"
    )
    sections = [gate_summary, overview, "### 关键产出", render_key_output_table(key_entries)]
    if summarized_entries:
        sections.extend(["### 健康运行时产出汇总", render_runtime_output_summary(summarized_entries)])
    return "\n\n".join(sections)


def is_key_output(entry: dict[str, Any]) -> bool:
    status = str(entry.get("status", "unknown"))
    return bool(
        entry.get("required")
        or entry.get("ready") is False
        or entry.get("evidence") == "configured"
        or status not in NORMAL_DISCOVERED_OUTPUT_STATUSES
    )


def render_key_output_table(entries: list[dict[str, Any]]) -> str:
    rows = [render_key_output_row(entry) for entry in entries]
    return table(
        ["服务", "类型 / Sink", "路径 / 查询入口", "来源 / 证据", "必需 / 状态", "大小 / 轮转 / 保留"],
        rows,
    )


def render_key_output_row(entry: dict[str, Any]) -> list[Any]:
    matches = entry.get("matches") or []
    match_count = output_match_count(entry, matches)
    status = str(entry.get("status", "unknown"))
    evidence_summary = summarize_runtime_evidence(entry.get("runtime_evidence", []))
    if evidence_summary:
        status += f"<br>{evidence_summary}"
    if match_count > 1:
        status += f"<br>{match_count} 个匹配"
    return [
        entry.get("service", "unknown"),
        f"{entry.get('kind', 'other')} / {entry.get('sink', 'other')}",
        redact_scalar("output_location", output_location(entry, matches)),
        f"{redact_scalar('source', entry.get('source', 'unknown'))}<br>{entry.get('evidence', 'unknown')}",
        f"{'是' if entry.get('required') else '否'}<br>{status}",
        render_output_policy(entry, matches, match_count),
    ]


def output_location(entry: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    configured = entry.get("path") or entry.get("locator")
    if configured:
        return str(configured)
    observed = [str(match.get("path")) for match in matches if match.get("path")]
    return observed[0] if observed else "unknown"


def output_match_count(entry: dict[str, Any], matches: list[dict[str, Any]]) -> int:
    try:
        return max(int(entry.get("match_count", 0)), len(matches))
    except (TypeError, ValueError):
        return len(matches)


def output_size(matches: list[dict[str, Any]]) -> int | None:
    sizes = [match.get("size") for match in matches]
    known_sizes = [int(size) for size in sizes if isinstance(size, (int, float)) and size >= 0]
    return sum(known_sizes) if known_sizes else None


def render_output_policy(
    entry: dict[str, Any], matches: list[dict[str, Any]], match_count: int
) -> str:
    size = human_bytes(output_size(matches))
    if match_count > 1:
        size = f"{match_count} 个匹配 / {size}"
    rotation = redact_scalar("rotation", entry.get("rotation", "unknown"))
    retention = redact_scalar("retention", entry.get("retention", "unknown"))
    return f"{size}<br>轮转：{rotation}<br>保留：{retention}"


def summarize_runtime_evidence(values: list[Any]) -> str:
    mapped_pids: set[str] = set()
    permissions: set[str] = set()
    writable_pids: set[str] = set()
    other_count = 0
    for value in values:
        evidence = str(value)
        mapped = MAPPED_EVIDENCE.fullmatch(evidence)
        writable = WRITABLE_FD_EVIDENCE.match(evidence)
        if mapped:
            mapped_pids.add(mapped.group(1))
            permissions.add(mapped.group(2))
        elif writable:
            writable_pids.add(writable.group(1))
        else:
            other_count += 1
    parts = []
    if mapped_pids:
        permission_summary = "/".join(sorted(permissions)) or "unknown"
        parts.append(f"映射进程 {len(mapped_pids)} 个，权限 {permission_summary}")
    if writable_pids:
        parts.append(f"可写 FD {len(writable_pids)} 个")
    if other_count:
        parts.append(f"其他运行时证据 {other_count} 条")
    return "；".join(parts)


def render_runtime_output_summary(entries: list[dict[str, Any]]) -> str:
    services: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        services.setdefault(str(entry.get("service", "unknown")), []).append(entry)
    rows = [render_service_output_summary(service, service_entries) for service, service_entries in sorted(services.items())]
    return table(["服务", "分类统计", "对象 / 大小", "代表路径（最多两个）"], rows)


def render_service_output_summary(service: str, entries: list[dict[str, Any]]) -> list[Any]:
    counts = {category: 0 for category in OUTPUT_CATEGORY_ORDER}
    total_size = 0
    has_known_size = False
    representatives: list[tuple[int, str]] = []
    for entry in entries:
        matches = entry.get("matches") or []
        category = classify_runtime_output(entry)
        counts[category] += output_match_count(entry, matches) or 1
        size = output_size(matches)
        if size is not None:
            total_size += size
            has_known_size = True
        representative = normalize_output_path(output_location(entry, matches), category)
        representatives.append((REPRESENTATIVE_CATEGORY_ORDER.index(category), representative))
    categories = "；".join(
        f"{OUTPUT_CATEGORY_LABELS[category]} {counts[category]}"
        for category in OUTPUT_CATEGORY_ORDER
        if counts[category]
    )
    paths = unique_representative_paths(representatives)
    total_count = sum(counts.values())
    size_summary = human_bytes(total_size) if has_known_size else "unknown"
    return [service, categories, f"{total_count} 个 / {size_summary}", "<br>".join(paths) or "unknown"]


def classify_runtime_output(entry: dict[str, Any]) -> str:
    path = str(entry.get("path") or "")
    if path.startswith("/dev/hugepages/"):
        return "hugepage"
    if path.startswith("/run/dpdk/"):
        return "dpdk"
    kind = str(entry.get("kind", "other"))
    if kind == "shared_memory" or path.startswith("/dev/shm/"):
        return "shared_memory"
    if kind in {"log", "data", "dump", "archive"}:
        return kind
    if path.endswith(".log") or "/log/" in path or "/logs/" in path:
        return "log"
    if "/data/" in path or "/data_output/" in path:
        return "data"
    return "other"


def normalize_output_path(path: str, category: str) -> str:
    if category == "hugepage":
        return "/dev/hugepages/*"
    if category == "dpdk":
        return "/run/dpdk/*"
    return redact_scalar("output_location", path)


def unique_representative_paths(candidates: list[tuple[int, str]]) -> list[str]:
    paths: list[str] = []
    for _, path in sorted(candidates):
        if path not in paths:
            paths.append(path)
        if len(paths) == 2:
            break
    return paths


def format_mtime(value: Any) -> str:
    try:
        return dt.datetime.fromtimestamp(int(value), dt.timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return "unknown"


def render_deployment(
    status: str, contract: dict[str, Any], gate: dict[str, Any], output_result: dict[str, Any]
) -> str:
    rows = [
        [change.get("action", ""), change.get("path", ""), redact_scalar("rollback", change.get("rollback", ""))]
        for change in contract.get("changes", [])
    ]
    result = f"**最终状态：{status_label(status)}**\n\n"
    result += table(["动作", "路径", "回滚动作"], rows)
    if gate:
        result += f"\n\n**健康门禁：** {'通过' if gate.get('healthy') else '失败'}"
        result += f"；阶段 `{gate.get('phase', 'unknown')}`；轮询 {len(gate.get('polls', []))} 次。"
        if gate.get("schema_version") == 2:
            baseline_clean = gate.get("baseline_clean")
            if baseline_clean is not None:
                result += f"\n\n**部署前基线：** {'clean' if baseline_clean else '存在既有警告'}。"
            failure_title = (
                "新增/恶化问题"
                if gate.get("phase") in {"postdeploy", "rollback"}
                else "阻断项"
            )
            result += render_gate_issues(failure_title, gate.get("failures", []))
            result += render_gate_issues("非阻断警告", gate.get("warnings", []))
            result += render_gate_issues("继承警告", gate.get("inherited_warnings", []))
        else:
            reasons = [
                reason
                for poll in gate.get("polls", [])
                for reason in poll.get("reasons", [])
            ]
            if reasons:
                result += "\n\n" + "\n".join(
                    f"- {markdown(reason)}" for reason in sorted(set(reasons))
                )
    if output_result:
        result += f"\n\n**程序产出门禁：** {'通过' if output_result.get('healthy') else '失败'}。"
        messages = [*output_result.get("failures", []), *output_result.get("warnings", [])]
        if messages:
            result += "\n\n" + "\n".join(f"- {markdown(message)}" for message in messages)
    return result


def render_gate_issues(title: str, issues: list[Any]) -> str:
    if not issues:
        return ""
    messages = []
    for value in issues:
        if not isinstance(value, dict):
            messages.append(value)
            continue
        comparison = value.get("comparison")
        prefix = f"[{comparison}] " if comparison in {"new", "worsened"} else ""
        messages.append(prefix + str(value.get("message", value)))
    return f"\n\n**{title}：**\n\n" + "\n".join(
        f"- {markdown(message)}" for message in messages
    )


def render_steps(steps: list[Any]) -> str:
    if not steps:
        return "未提供。"
    return "\n\n".join(f"{index}. `{markdown(redact_scalar('command', step))}`" for index, step in enumerate(steps, 1))


def table(headers: list[str], rows: list[list[Any]]) -> str:
    rendered_rows = [[markdown(value) for value in row] for row in rows]
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rendered_rows]
    return "\n".join([header, separator, *body])


def render_template(template: str, values: dict[str, str]) -> str:
    missing = sorted(set(PLACEHOLDER.findall(template)) - set(values))
    if missing:
        raise ValueError(f"template has unresolved placeholders: {', '.join(missing)}")
    return PLACEHOLDER.sub(lambda match: values[match.group(1)], template)


def build_report(
    status: str,
    before: dict[str, Any],
    after: dict[str, Any],
    contract: dict[str, Any],
    gate: dict[str, Any],
    template: str,
    output_result: dict[str, Any] | None = None,
) -> str:
    output_result = output_result or {}
    current = after or before
    title = f"{current.get('machine', {}).get('hostname', 'unknown')} · {status_label(status)}"
    values = {
        "title": markdown(title),
        "summary": render_summary(status, contract, before, gate),
        "machine": render_machine(before, after),
        "network": render_network(current),
        "cpu_topology": render_cpu(current),
        "capacity": render_capacity(before, after),
        "repositories": render_repositories(contract),
        "key_config": render_key_config(contract),
        "program_outputs": render_program_outputs(contract, output_result),
        "deployment": render_deployment(status, contract, gate, output_result),
        "reproduce": render_steps(contract.get("reproduce", [])),
        "rollback": render_steps(contract.get("rollback", [])),
    }
    return render_template(template, values).rstrip() + "\n"


def write_report(text: str, output: Path) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, output)
    LOG.info("report written path=%s bytes=%d", output, output.stat().st_size)


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
        output_result = load_json(args.outputs, required=False)
        validate_contract(contract)
        template = args.template.expanduser().read_text(encoding="utf-8")
        report = build_report(args.status, before, after, contract, gate, template, output_result)
        write_report(report, args.output)
        print(
            f"status={args.status} host={before.get('machine', {}).get('hostname', 'unknown')} "
            f"services={len((after or before).get('services', []))} "
            f"health={'passed' if gate.get('healthy') else ('not-provided' if not gate else 'failed')} "
            f"outputs={'passed' if output_result.get('healthy') else ('not-provided' if not output_result else 'failed')} "
            f"report={args.output.expanduser().resolve()}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        LOG.error("report rendering failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
