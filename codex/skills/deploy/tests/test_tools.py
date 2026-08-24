#!/usr/bin/env python3
"""Deterministic regression tests for deploy Skill scripts."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent


def load_script(name: str) -> Any:
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


collect_host = load_script("collect_host")
check_alertd = load_script("check_alertd")
check_outputs = load_script("check_outputs")
render_report = load_script("render_report")


def fixture_snapshot() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at": "2026-08-13T00:00:00+00:00",
        "target": {"host": "deploy.example", "user": "root", "port": 22},
        "support": {"supported": True, "required": "Amazon Linux 2023 aarch64 with systemd"},
        "machine": {
            "hostname": "trade-sg",
            "os_release": {"ID": "amzn", "VERSION_ID": "2023", "PRETTY_NAME": "Amazon Linux 2023"},
            "kernel": "Linux 6.1",
            "architecture": "aarch64",
            "init": "systemd",
            "aws": {
                "region": "ap-southeast-1",
                "instance_id": "i-example",
                "instance_type": "c7g.xlarge",
                "public_ipv4": "203.0.113.10",
                "interfaces": [
                    {
                        "mac": "02:00:00:00:00:01",
                        "device_number": "0",
                        "interface_id": "eni-primary",
                        "private_ipv4": ["10.0.0.10"],
                        "public_ipv4": ["203.0.113.10"],
                        "subnet_id": "subnet-example",
                    }
                ],
            },
        },
        "cpu": {
            "summary": {"Architecture": "aarch64", "Model name": "AWS Graviton3"},
            "topology": [
                {"cpu": cpu, "node": 0, "socket": 0, "core": cpu, "online": True}
                for cpu in range(4)
            ],
            "sample_seconds": 10,
        },
        "memory": {"MemTotal": 8 * 1024**3, "MemAvailable": 5 * 1024**3},
        "storage": {
            "block_devices": [],
            "filesystems": [
                {
                    "source": "/dev/nvme0n1p1",
                    "target": "/",
                    "fstype": "xfs",
                    "size": 40 * 1024**3,
                    "used": 20 * 1024**3,
                    "avail": 20 * 1024**3,
                    "use%": "50%",
                }
            ],
        },
        "network": {
            "links": [
                {"ifname": "ens5", "operstate": "UP", "address": "02:00:00:00:00:01", "mtu": 9001},
                {"ifname": "ens7", "operstate": "UP", "address": "02:00:00:00:00:02", "mtu": 9001},
            ],
            "addresses": [
                {"ifname": "ens5", "addr_info": [{"local": "10.0.0.10", "prefixlen": 24}]},
                {"ifname": "ens7", "addr_info": [{"local": "10.0.1.10", "prefixlen": 24}]},
            ],
            "routes": [{"dst": "default", "gateway": "10.0.0.1", "dev": "ens5", "metric": 100}],
            "devices": [],
        },
        "services": [
            {
                "unit": "alpha.service",
                "fragment_path": "/etc/systemd/system/alpha.service",
                "resolved_fragment_path": "/etc/systemd/system/alpha.service",
                "unit_file_state": "enabled",
                "active_state": "active",
                "sub_state": "running",
                "service_type": "simple",
                "remain_after_exit": "no",
                "main_pid": 100,
                "result": "success",
                "exec_start": "/opt/alpha/current/bin/alpha --interface ens5",
                "working_directory": "/opt/alpha/current",
                "environment_files": "/etc/alpha/alpha.env",
                "pids": [100],
                "effective_allowed_cpus": [0, 1],
                "configured_cpu_affinity": [1],
                "observed_cpus": [1],
                "network_interfaces": [
                    {"interface": "ens5", "evidence": "inferred", "basis": "unit ExecStart"}
                ],
            },
            {
                "unit": "prepare.service",
                "fragment_path": "/etc/systemd/system/prepare.service",
                "resolved_fragment_path": "/etc/systemd/system/prepare.service",
                "unit_file_state": "disabled",
                "active_state": "inactive",
                "sub_state": "dead",
                "service_type": "oneshot",
                "remain_after_exit": "no",
                "main_pid": 0,
                "result": "success",
                "exec_start": "/opt/alpha/current/bin/prepare",
                "working_directory": "/opt/alpha/current",
                "environment_files": "",
                "pids": [],
                "effective_allowed_cpus": [],
                "configured_cpu_affinity": [],
                "observed_cpus": [],
                "network_interfaces": [],
            },
        ],
    }


def fixture_contract() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "auto",
        "target": {"host": "deploy.example", "user": "root", "port": 22, "known_hosts": "/tmp/known_hosts"},
        "deployment": {
            "service_units": ["alpha.service"],
            "release_root": "/opt/alpha/releases",
            "current_link": "/opt/alpha/current",
            "keep_releases": 2,
            "min_free_percent": 10,
            "observe_seconds": 300,
            "cpu_sample_seconds": 10,
            "report_remote_dir": "/var/lib/deploy/reports",
        },
        "repositories": [
            {
                "role": "application",
                "url": "git@example:team/alpha.git",
                "target": "main",
                "commit": "a" * 40,
                "builder_image_digest": "rust@sha256:" + "b" * 64,
                "artifact_sha256": "c" * 64,
            }
        ],
        "changes": [
            {"path": "/opt/alpha/current", "action": "replace", "rollback": "ln -sfn previous /opt/alpha/current"}
        ],
        "health": {
            "alertd_config_path": "/etc/alertd/alertd.toml",
            "alertd_state_dir": "/var/lib/alertd",
            "required_units": ["alpha.service"],
        },
        "key_config": [
            {"name": "runtime.log_level", "source": "/etc/alpha/alpha.toml", "value": "info"},
            {"name": "api_token", "source": "/etc/alpha/alpha.env", "value": "must-not-leak"},
        ],
        "cpu_affinity": {"alpha.service": [1]},
        "network_binding": {"alpha.service": ["ens5"]},
        "reproduce": ["git clone git@example:team/alpha.git", "git checkout " + "a" * 40],
        "rollback": ["ln -sfn previous /opt/alpha/current", "systemctl restart alpha.service"],
        "irreversible_changes": [],
    }


def fixture_contract_v2() -> dict[str, Any]:
    contract = copy.deepcopy(fixture_contract())
    contract["schema_version"] = 2
    contract["program_outputs"] = [
        {
            "service": "alpha.service",
            "kind": "log",
            "sink": "file",
            "path": "/var/log/alpha/alpha.log",
            "locator": None,
            "source": "/etc/alpha/alpha.toml:logging.path",
            "evidence": "configured",
            "required": True,
            "readiness": "writable_parent",
            "rotation": "/etc/logrotate.d/alpha",
            "retention": "7d",
        },
        {
            "service": "alertd.service",
            "kind": "log",
            "sink": "journald",
            "path": None,
            "locator": "journalctl -u alertd.service",
            "source": "systemd StandardOutput/StandardError",
            "evidence": "configured",
            "required": True,
            "readiness": "active_sink",
            "rotation": "journald",
            "retention": "unknown",
        },
    ]
    return contract


def fixture_contract_v3() -> dict[str, Any]:
    contract = copy.deepcopy(fixture_contract_v2())
    contract["schema_version"] = 3
    contract.pop("mode")
    return contract


def fixture_output_result() -> dict[str, Any]:
    entries = copy.deepcopy(fixture_contract_v2()["program_outputs"])
    entries[0].update(
        {
            "ready": True,
            "status": "writable_parent",
            "match_count": 1,
            "truncated": False,
            "matches": [
                {
                    "path": "/var/log/alpha/alpha.log",
                    "file_type": "regular file",
                    "owner": "alpha",
                    "group": "alpha",
                    "mode": "640",
                    "size": 4096,
                    "mtime": 1786579200,
                    "mount_point": "/",
                    "device": "/dev/nvme0n1p1",
                    "filesystem": "xfs",
                }
            ],
        }
    )
    entries[1].update(
        {"ready": True, "status": "active", "match_count": 0, "truncated": False, "matches": []}
    )
    return {
        "schema_version": 1,
        "phase": "postdeploy",
        "healthy": True,
        "declared": entries,
        "discovered": [],
        "failures": [],
        "warnings": [],
    }


def runtime_output(
    service: str,
    path: str,
    size: int,
    *,
    kind: str = "other",
    status: str = "observed_open_writable",
) -> dict[str, Any]:
    return {
        "service": service,
        "kind": kind,
        "sink": "file",
        "path": path,
        "locator": None,
        "source": "/proc/runtime",
        "evidence": "observed",
        "required": False,
        "readiness": "exists",
        "rotation": "unknown",
        "retention": "unknown",
        "ready": True,
        "status": status,
        "match_count": 1,
        "truncated": False,
        "matches": [{"path": path, "size": size}],
    }


def fixture_alertd_config() -> str:
    return """
[runtime]
interval = "30s"

[[checks]]
name = "alpha"
type = "process"
cmdline_contains = "/opt/alpha/current/bin/alpha"

[[checks]]
name = "service-journal"
type = "journal"
units = ["alpha.service", "prepare.service"]
rules = [{ contains = "ERROR", severity = "critical" }]
"""


def fixture_gate_sections() -> dict[str, str]:
    now = int(time.time())
    state = {
        "checks": {
            "alpha": {
                "pending_since": None,
                "firing_since": None,
                "last_sent_at": None,
                "severity": "ok",
                "collection_failures": 0,
            },
            "service-journal": {
                "pending_since": None,
                "firing_since": None,
                "last_sent_at": None,
                "severity": "ok",
                "collection_failures": 0,
            },
        },
        "journal_cursors": {},
        "last_daily_date": None,
    }
    return {
        "observed_at": str(now),
        "alertd_unit": "LoadState=loaded\nActiveState=active\nSubState=running\nResult=success\nMainPID=200",
        "state_stat": f"{now}\x1f1024",
        "state": json.dumps(state),
        "config": fixture_alertd_config(),
        "units": "alpha.service\x1factive\x1frunning\x1fsuccess\x1f100\nprepare.service\x1finactive\x1fdead\x1fsuccess\x1f0",
    }


class CollectHostTests(unittest.TestCase):
    def test_service_parser_redacts_secret_and_expands_affinity(self) -> None:
        fields = [
            "alpha.service", "/etc/systemd/system/alpha.service", "/etc/systemd/system/alpha.service",
            "enabled", "active", "running", "simple", "no", "100", "success",
            "/opt/alpha --token super-secret", "/opt/alpha", "/etc/alpha.env", "1-2", "100", "0-3",
        ]
        services = collect_host.parse_services("\x1f".join(fields), set())
        self.assertEqual(services[0]["configured_cpu_affinity"], [1, 2])
        self.assertEqual(services[0]["effective_allowed_cpus"], [0, 1, 2, 3])
        self.assertNotIn("super-secret", services[0]["exec_start"])

    def test_redacts_sensitive_environment_assignment(self) -> None:
        self.assertEqual(collect_host.redact("TOKEN=must-not-leak --mode prod"), "TOKEN=<redacted> --mode prod")

    def test_network_attribution_distinguishes_inference(self) -> None:
        snapshot = fixture_snapshot()
        service = snapshot["services"][0]
        service["network_interfaces"] = []
        collect_host.add_network_attribution(
            snapshot["services"],
            'tcp ESTAB 0 0 10.0.0.10:5000 198.51.100.4:443 users:(("alpha",pid=100,fd=3))',
            snapshot["network"]["links"],
            snapshot["network"]["addresses"],
            snapshot["network"]["routes"],
            [],
        )
        evidence = {item["evidence"] for item in service["network_interfaces"]}
        self.assertEqual(evidence, {"observed", "inferred"})


class AlertdGateTests(unittest.TestCase):
    def test_healthy_gate_covers_long_running_and_oneshot_units(self) -> None:
        result = check_alertd.evaluate_poll(
            fixture_snapshot(), fixture_gate_sections(), {"alpha.service"}
        )
        self.assertTrue(result["healthy"], result["reasons"])

    def test_pending_alert_fails_gate(self) -> None:
        sections = fixture_gate_sections()
        state = json.loads(sections["state"])
        state["checks"]["alpha"]["pending_since"] = "2026-08-13T00:00:00Z"
        sections["state"] = json.dumps(state)
        result = check_alertd.evaluate_poll(fixture_snapshot(), sections, {"alpha.service"})
        self.assertFalse(result["healthy"])
        self.assertTrue(any("unhealthy" in reason for reason in result["reasons"]))

    def test_missing_journal_coverage_fails_gate(self) -> None:
        sections = fixture_gate_sections()
        sections["config"] = sections["config"].replace(', "prepare.service"', "")
        result = check_alertd.evaluate_poll(fixture_snapshot(), sections, {"alpha.service"})
        self.assertFalse(result["healthy"])
        self.assertTrue(any("prepare.service" in reason for reason in result["reasons"]))

    def test_missing_alertd_becomes_structured_failure(self) -> None:
        sections = fixture_gate_sections()
        sections["config"] = ""
        sections["state"] = ""
        sections["state_stat"] = ""
        result = check_alertd.evaluate_poll(fixture_snapshot(), sections, {"alpha.service"})
        self.assertFalse(result["healthy"])
        self.assertTrue(any("config is unavailable" in reason for reason in result["reasons"]))

    def test_baseline_business_issue_is_warning_not_failure(self) -> None:
        sections = fixture_gate_sections()
        state = json.loads(sections["state"])
        state["checks"]["alpha"]["pending_since"] = "2026-08-13T00:00:00Z"
        sections["state"] = json.dumps(state)
        result = check_alertd.evaluate_poll(fixture_snapshot(), sections, {"alpha.service"})
        check_alertd.decorate_poll(result, "baseline", {})
        self.assertTrue(result["healthy"])
        self.assertFalse(result["clean"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["warnings"][0]["code"], "check_unhealthy")

    def test_baseline_minimum_observability_issue_is_failure(self) -> None:
        sections = fixture_gate_sections()
        sections["alertd_unit"] = "LoadState=loaded\nActiveState=inactive"
        result = check_alertd.evaluate_poll(fixture_snapshot(), sections, {"alpha.service"})
        check_alertd.decorate_poll(result, "baseline", {})
        self.assertFalse(result["healthy"])
        self.assertEqual(result["failures"][0]["code"], "alertd_unavailable")

    def test_postdeploy_inherits_unchanged_baseline_warning(self) -> None:
        value = check_alertd.issue(
            "collector_failures", "alpha", "collector failed once", count=1
        )
        baseline = {"schema_version": 2, "phase": "baseline", "clean": False, "issues": [value]}
        failures, warnings, inherited = check_alertd.classify_issues(
            "postdeploy", [copy.deepcopy(value)], baseline
        )
        self.assertEqual(failures, [])
        self.assertEqual(warnings[0]["comparison"], "inherited")
        self.assertEqual(inherited[0]["comparison"], "inherited")

    def test_postdeploy_fails_new_or_worsened_issue(self) -> None:
        old = check_alertd.issue("collector_failures", "alpha", "one failure", count=1)
        worsened = check_alertd.issue("collector_failures", "alpha", "two failures", count=2)
        new = check_alertd.issue("required_unit_unhealthy", "alpha.service", "service exited", count=1)
        baseline = {"schema_version": 2, "phase": "baseline", "clean": False, "issues": [old]}
        failures, _, _ = check_alertd.classify_issues("postdeploy", [worsened, new], baseline)
        self.assertEqual({value["code"] for value in failures}, {"collector_failures", "required_unit_unhealthy"})
        self.assertEqual(
            {value["comparison"] for value in failures}, {"new", "worsened"}
        )


class OutputGateTests(unittest.TestCase):
    def output(self, **overrides: Any) -> dict[str, Any]:
        value = {
            "service": "alpha.service",
            "kind": "log",
            "sink": "file",
            "path": "/var/log/alpha/alpha.log",
            "locator": None,
            "source": "test fixture",
            "evidence": "configured",
            "required": True,
            "readiness": "exists",
            "rotation": "unknown",
            "retention": "unknown",
        }
        value.update(overrides)
        return value

    def test_validates_file_directory_glob_delayed_shm_and_logical_sinks(self) -> None:
        outputs = [
            self.output(),
            self.output(kind="data", sink="directory", path="/var/lib/alpha", readiness="exists"),
            self.output(sink="glob", path="/var/log/alpha/*.log", readiness="matches"),
            self.output(path="/var/log/alpha/lazy.log", readiness="writable_parent"),
            self.output(kind="shared_memory", path="/dev/shm/alpha.progress"),
            self.output(sink="journald", path=None, locator="journalctl -u alpha.service", readiness="active_sink"),
            self.output(sink="syslog", path=None, locator="logger query for alpha", readiness="active_sink"),
        ]
        for index, output in enumerate(outputs):
            check_outputs.validate_output(index, output, {"alpha.service"})

    def test_rejects_recursive_or_unresolved_glob(self) -> None:
        with self.assertRaises(ValueError):
            check_outputs.validate_output(
                0, self.output(sink="glob", path="/var/log/**/alpha.log", readiness="matches"), {"alpha.service"}
            )
        with self.assertRaises(ValueError):
            check_outputs.validate_output(
                0, self.output(path="/var/log/$APP/alpha.log"), {"alpha.service"}
            )

    def test_required_failure_and_optional_warning_are_separate(self) -> None:
        outputs = [
            self.output(required=True),
            self.output(path="/var/log/alpha/optional.log", required=False),
        ]
        declared, failures, warnings = check_outputs.evaluate_declared(outputs, {}, {})
        self.assertFalse(declared[0]["ready"])
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(warnings), 1)

    def test_journald_and_syslog_use_effective_systemd_sink(self) -> None:
        journald = self.output(
            sink="journald", path=None, locator="journalctl -u alpha.service", readiness="active_sink"
        )
        syslog = self.output(
            sink="syslog", path=None, locator="syslog query", readiness="active_sink"
        )
        self.assertEqual(
            check_outputs.readiness_state(
                journald, {},
                {"load_state": "loaded", "standard_output": "journal", "journal_query_available": "yes"},
            ),
            (True, "active"),
        )
        self.assertEqual(
            check_outputs.readiness_state(syslog, {}, {"load_state": "loaded", "standard_error": "syslog"}),
            (True, "active"),
        )

    def test_remote_script_base64_encodes_journal_availability(self) -> None:
        output = self.output(
            sink="journald", path=None, locator="journalctl -u alpha.service", readiness="active_sink"
        )
        script = check_outputs.remote_script([output], ["alpha.service"])
        self.assertIn("then printf '\\037'; b64 yes; else printf '\\037'; b64 no; fi", script)

    def test_glob_parser_caps_reported_matches_at_100(self) -> None:
        encoded_path = base64.b64encode(b"/var/log/alpha/alpha.log").decode()
        empty_metadata = "\x1f".join([encoded_path, "", "", "", "640", "1", "1", "", "", ""])
        lines = [f"0\x1fexists\x1f{empty_metadata}\x1fyes" for _ in range(100)]
        lines.append("0\x1fsummary\x1f\x1f\x1f\x1f\x1f\x1f101\x1f\x1f\x1f\x1f\x1fyes")
        result = check_outputs.parse_declared("\n".join(lines))[0]
        self.assertEqual(len(result["matches"]), 100)
        self.assertEqual(result["count"], 101)
        self.assertTrue(result["truncated"])

    def test_remote_fd_probe_filters_non_regular_and_read_only_descriptors(self) -> None:
        script = check_outputs.remote_fd_probe(["alpha.service"])
        self.assertIn('[ -f "$fd" ] || continue', script)
        self.assertIn("/dev/null", script)
        self.assertIn('access_mode=$((flags_value & 3))', script)
        self.assertIn('[ "$access_mode" -eq 1 ] || [ "$access_mode" -eq 2 ] || continue', script)
        self.assertNotIn("cat \"$target\"", script)

    def test_remote_shm_probe_reads_only_target_process_maps(self) -> None:
        script = check_outputs.remote_shm_map_probe(["alpha.service"])
        self.assertIn('done < "/proc/$pid/maps"', script)
        self.assertIn('case "$pathname" in (/dev/shm/*)', script)
        self.assertNotIn("find /dev/shm", script)
        self.assertNotIn('cat "$pathname"', script)

    def test_parse_shm_maps_preserves_deleted_path_and_permissions(self) -> None:
        def encoded(value: str) -> str:
            return base64.b64encode(value.encode()).decode()

        line = "\x1f".join(
            [
                "alpha.service", "100", encoded("/dev/shm/alpha.book (deleted)"), "rw-s",
                encoded("regular file"), encoded("alpha"), encoded("alpha"), "600", "4096", "123",
                encoded("/dev/shm"), encoded("tmpfs"), encoded("tmpfs"),
            ]
        )
        mapping = check_outputs.parse_shm_maps(line)[0]
        self.assertEqual(mapping["path"], "/dev/shm/alpha.book (deleted)")
        self.assertEqual(mapping["mapping_permissions"], "rw-s")
        self.assertEqual(mapping["size"], 4096)

    def test_shm_observations_prioritize_fd_and_deduplicate_per_service(self) -> None:
        descriptor = {
            "service": "alpha.service", "pid": 100, "path": "/dev/shm/alpha.book",
            "file_type": "regular file", "owner": "alpha", "group": "alpha", "mode": "600",
            "size": 4096, "mtime": 123, "mount_point": "/dev/shm", "device": "tmpfs",
            "filesystem": "tmpfs",
        }
        mappings = [
            {**descriptor, "pid": 101, "mapping_permissions": "r--s"},
            {**descriptor, "service": "beta.service", "pid": 200, "mapping_permissions": "rw-s"},
            {
                **descriptor, "path": "/dev/shm/gone (deleted)", "pid": 102,
                "mapping_permissions": "rw-s",
            },
            {**descriptor, "path": "/tmp/not-shm", "pid": 103, "mapping_permissions": "rw-s"},
        ]
        observations = check_outputs.collect_shm_observations([descriptor], mappings)
        by_key = {check_outputs.shm_observation_key(value): value for value in observations}
        alpha = by_key[("alpha.service", "/dev/shm/alpha.book")]
        self.assertEqual(alpha["status"], "observed_open_writable")
        self.assertEqual(len(alpha["runtime_evidence"]), 2)
        self.assertIn(("beta.service", "/dev/shm/alpha.book"), by_key)
        self.assertEqual(
            by_key[("alpha.service", "/dev/shm/gone")]["status"],
            "observed_mapped_deleted",
        )
        self.assertNotIn(("alpha.service", "/tmp/not-shm"), by_key)

    def test_shm_runtime_discovery_can_exclude_infrastructure_units(self) -> None:
        descriptors = [
            {"service": "alpha.service", "pid": 100, "path": "/dev/shm/alpha"},
            {"service": "alertd.service", "pid": 200, "path": "/dev/shm/alertd"},
        ]
        observations = check_outputs.collect_shm_observations(
            descriptors, [], {"alpha.service"}
        )
        self.assertEqual([value["service"] for value in observations], ["alpha.service"])

    def test_declared_shm_merges_runtime_evidence_without_duplicate_row(self) -> None:
        output = self.output(kind="shared_memory", path="/dev/shm/alpha.book")
        probe = {
            0: {
                "matches": [{"state": "exists", "path": "/dev/shm/alpha.book"}],
                "count": 1,
                "truncated": False,
                "writable": True,
            }
        }
        observation = {
            "service": "alpha.service", "pid": 100, "path": "/dev/shm/alpha.book",
            "source": "/proc/100/fd", "status": "observed_open_writable",
            "runtime_evidence": ["open_writable pid=100"],
        }
        declared, failures, _ = check_outputs.evaluate_declared([output], probe, {}, [observation])
        discovered = check_outputs.discover_outputs([output], {}, [], [observation])
        self.assertEqual(failures, [])
        self.assertEqual(declared[0]["runtime_evidence"], ["open_writable pid=100"])
        self.assertEqual(discovered, [])

    def test_undeclared_shm_is_optional_shared_memory_output(self) -> None:
        observation = {
            "service": "alpha.service", "pid": 100, "path": "/dev/shm/alpha.book",
            "source": "/proc/100/maps", "status": "observed_mapped",
            "runtime_evidence": ["mapped pid=100 permissions=rw-s"],
            "owner": "alpha", "group": "alpha", "mode": "600", "size": 4096, "mtime": 123,
            "mount_point": "/dev/shm", "device": "tmpfs", "filesystem": "tmpfs",
        }
        discovered = check_outputs.discover_outputs([], {}, [], [observation])
        self.assertEqual(discovered[0]["kind"], "shared_memory")
        self.assertFalse(discovered[0]["required"])
        self.assertEqual(discovered[0]["status"], "observed_mapped")

    def test_descriptor_discovery_deduplicates_declared_output(self) -> None:
        descriptor = {
            "service": "alpha.service", "pid": 100, "path": "/var/log/alpha/alpha.log",
            "file_type": "regular file", "owner": "alpha", "group": "alpha", "mode": "640",
            "size": 1, "mtime": 1, "mount_point": "/", "device": "/dev/root", "filesystem": "xfs",
        }
        self.assertEqual(check_outputs.discover_outputs([self.output()], {}, [descriptor]), [])

    def test_systemd_output_directories_are_reported_without_scanning(self) -> None:
        units = {
            "alpha.service": {
                "logs_directory": "alpha alpha-audit:compat",
                "state_directory": "alpha-state",
                "runtime_directory": "",
                "cache_directory": "",
                "standard_output": "null",
                "standard_error": "null",
            }
        }
        discovered = check_outputs.discover_systemd_directories([], units)
        self.assertEqual(
            {entry["path"] for entry in discovered},
            {"/var/log/alpha", "/var/log/alpha-audit", "/var/lib/alpha-state"},
        )
        self.assertTrue(all(entry["status"] == "configured_undeclared" for entry in discovered))

    def test_output_result_redacts_sensitive_locator(self) -> None:
        value = check_outputs.redact("viewer --token must-not-leak https://user:pass@example.test")
        self.assertNotIn("must-not-leak", value)
        self.assertNotIn("user:pass", value)

    def test_v3_uncovered_units_are_warnings(self) -> None:
        contract = fixture_contract_v3()
        contract["program_outputs"] = []
        with tempfile.TemporaryDirectory() as temporary_directory:
            known_hosts = Path(temporary_directory) / "known_hosts"
            known_hosts.write_text("fixture", encoding="utf-8")
            contract["target"]["known_hosts"] = str(known_hosts)
            _, outputs, _, uncovered = check_outputs.validate_inputs(
                fixture_snapshot(), contract, known_hosts
            )
        result = check_outputs.build_result(
            "postdeploy", fixture_snapshot(), outputs, {}, 0.1, uncovered
        )
        self.assertTrue(result["healthy"])
        self.assertEqual(len(result["failures"]), 0)
        self.assertEqual(len(result["warnings"]), 2)


class ReportTests(unittest.TestCase):
    def test_capacity_summarizes_persistent_filesystems_without_mount_details(self) -> None:
        gibibyte = 1024**3
        before = fixture_snapshot()
        before["storage"]["filesystems"] = [
            {"source": "/dev/root", "target": "/", "fstype": "xfs", "size": 40 * gibibyte, "used": 20 * gibibyte, "avail": 20 * gibibyte},
            {"source": "/dev/data", "target": "/data", "fstype": "ext4", "size": 100 * gibibyte, "used": 25 * gibibyte, "avail": 75 * gibibyte},
            {"source": "/dev/data[/shared]", "target": "/srv/data", "fstype": "ext4", "size": 100 * gibibyte, "used": 25 * gibibyte, "avail": 75 * gibibyte},
            {"source": "tmpfs", "target": "/dev/shm", "fstype": "tmpfs", "size": 8 * gibibyte, "used": gibibyte, "avail": 7 * gibibyte},
            {"source": "overlay", "target": "/var/lib/containers", "fstype": "overlay", "size": 40 * gibibyte, "used": 20 * gibibyte, "avail": 20 * gibibyte},
        ]
        after = copy.deepcopy(before)
        after["storage"]["filesystems"][1].update({"used": 30 * gibibyte, "avail": 70 * gibibyte})
        after["storage"]["filesystems"][2].update({"used": 30 * gibibyte, "avail": 70 * gibibyte})
        capacity = render_report.render_capacity(before, after)
        self.assertIn("持久化文件系统汇总", capacity)
        self.assertIn("140.00 GiB", capacity)
        self.assertIn("45.00 GiB", capacity)
        self.assertIn("50.00 GiB", capacity)
        self.assertIn("90.00 GiB", capacity)
        self.assertIn("35.7%", capacity)
        self.assertNotIn("挂载点", capacity)
        self.assertNotIn("/data", capacity)
        self.assertNotIn("/dev/shm", capacity)

    def test_report_includes_all_services_and_redacts_secret(self) -> None:
        snapshot = fixture_snapshot()
        contract = fixture_contract()
        gate = {"phase": "postdeploy", "healthy": True, "polls": [{"reasons": []}]}
        template = (SKILL_ROOT / "assets" / "report-template.md").read_text(encoding="utf-8")
        report = render_report.build_report("succeeded", snapshot, snapshot, contract, gate, template)
        self.assertIn("alpha.service", report)
        self.assertIn("prepare.service", report)
        self.assertIn("未运行/不适用", report)
        self.assertIn("git@example:team/alpha.git", report)
        self.assertIn("<redacted>", report)
        self.assertNotIn("must-not-leak", report)
        self.assertIn("部署复现流程", report)
        self.assertIn("AWS ENI", report)
        self.assertIn("程序产出未记录", report)

    def test_v2_report_uses_six_column_key_output_table(self) -> None:
        snapshot = fixture_snapshot()
        contract = fixture_contract_v2()
        output_result = fixture_output_result()
        gate = {"phase": "postdeploy", "healthy": True, "polls": [{"reasons": []}]}
        template = (SKILL_ROOT / "assets" / "report-template.md").read_text(encoding="utf-8")
        render_report.validate_contract(contract)
        report = render_report.build_report(
            "succeeded", snapshot, snapshot, contract, gate, template, output_result
        )
        self.assertIn("## 程序产出", report)
        self.assertIn("/var/log/alpha/alpha.log", report)
        self.assertIn("journalctl -u alertd.service", report)
        self.assertIn("| 服务 | 类型 / Sink | 路径 / 查询入口 | 来源 / 证据 | 必需 / 状态 | 大小 / 轮转 / 保留 |", report)
        self.assertIn("/etc/logrotate.d/alpha", report)
        self.assertIn("4.00 KiB", report)
        self.assertNotIn("Owner / Mode", report)
        self.assertNotIn("大小 / mtime", report)
        self.assertNotIn("挂载点", report)
        self.assertNotIn("{{program_outputs}}", report)

    def test_report_summarizes_healthy_runtime_shm(self) -> None:
        contract = fixture_contract_v2()
        output_result = fixture_output_result()
        output_result["discovered"].append(
            {
                "service": "alpha.service", "kind": "shared_memory", "sink": "file",
                "path": "/dev/shm/alpha.book (deleted)", "locator": None,
                "source": "/proc/100/maps", "evidence": "observed", "required": False,
                "readiness": "exists", "rotation": "unknown", "retention": "unknown",
                "status": "observed_mapped_deleted",
                "runtime_evidence": ["mapped pid=100 permissions=rw-s"],
                "matches": [
                    {
                        "path": "/dev/shm/alpha.book (deleted)", "owner": "alpha",
                        "group": "alpha", "mode": "600", "size": 4096, "mtime": 1786579200,
                        "mount_point": "/dev/shm",
                    }
                ],
            }
        )
        rendered = render_report.render_program_outputs(contract, output_result)
        self.assertIn("健康运行时产出 1 项按 1 个服务汇总", rendered)
        self.assertIn("SHM 1", rendered)
        self.assertIn("/dev/shm/alpha.book (deleted)", rendered)
        self.assertNotIn("observed_mapped_deleted", rendered)
        self.assertNotIn("mapped pid=100", rendered)

    def test_report_keeps_declared_and_abnormal_outputs_in_key_details(self) -> None:
        contract = fixture_contract_v2()
        output_result = fixture_output_result()
        output_result["discovered"] = [
            {
                "service": "alpha.service", "kind": "data", "sink": "directory",
                "path": "/var/lib/alpha", "source": "systemd StateDirectory",
                "evidence": "configured", "required": False, "ready": None,
                "status": "configured_undeclared", "rotation": "unknown",
                "retention": "unknown", "matches": [],
            },
            {
                "service": "alpha.service", "kind": "dump", "sink": "file",
                "path": "/var/lib/alpha/core.dump", "source": "runtime check",
                "evidence": "observed", "required": False, "ready": False,
                "status": "missing", "rotation": "unknown", "retention": "unknown",
                "matches": [],
            },
        ]
        rendered = render_report.render_program_outputs(contract, output_result)
        self.assertIn("关键详情 4 项", rendered)
        self.assertIn("/var/lib/alpha", rendered)
        self.assertIn("configured_undeclared", rendered)
        self.assertIn("/var/lib/alpha/core.dump", rendered)
        self.assertIn("missing", rendered)
        self.assertNotIn("健康运行时产出汇总", rendered)

    def test_report_aggregates_glob_matches_into_one_key_row(self) -> None:
        contract = fixture_contract_v2()
        output_result = fixture_output_result()
        output_result["declared"][0].update(
            {
                "sink": "glob", "path": "/var/log/alpha/*.log", "status": "matches",
                "match_count": 3,
                "matches": [
                    {"path": f"/var/log/alpha/{index}.log", "size": 1024}
                    for index in range(3)
                ],
            }
        )
        rendered = render_report.render_program_outputs(contract, output_result)
        self.assertEqual(rendered.count("/var/log/alpha/*.log"), 1)
        self.assertIn("3 个匹配 / 3.00 KiB", rendered)
        self.assertNotIn("/var/log/alpha/0.log", rendered)

    def test_report_summarizes_multi_pid_shm_evidence_without_pid_values(self) -> None:
        contract = fixture_contract_v2()
        output_result = fixture_output_result()
        output_result["declared"].append(
            {
                "service": "alpha.service", "kind": "shared_memory", "sink": "file",
                "path": "/dev/shm/alpha.book", "source": "application config",
                "evidence": "configured", "required": True, "ready": True,
                "status": "exists", "rotation": "unknown", "retention": "unknown",
                "runtime_evidence": [
                    "mapped pid=100 permissions=r--s", "mapped pid=101 permissions=rw-s",
                    "mapped pid=101 permissions=rw-s", "open_writable pid=101 fd=9",
                ],
                "matches": [{"path": "/dev/shm/alpha.book", "size": 4096}],
            }
        )
        rendered = render_report.render_program_outputs(contract, output_result)
        self.assertIn("映射进程 2 个，权限 r--s/rw-s；可写 FD 1 个", rendered)
        self.assertNotIn("pid=100", rendered)
        self.assertNotIn("pid=101", rendered)

    def test_report_compacts_high_cardinality_outputs_without_mutating_result(self) -> None:
        contract = fixture_contract_v2()
        output_result = fixture_output_result()
        discovered = []
        for index in range(300):
            discovered.append(runtime_output("alpha.service", f"/dev/hugepages/rte_map_{index}", 2 * 1024**2))
        for index in range(60):
            discovered.append(runtime_output("alpha.service", f"/run/dpdk/rte/file_{index}", 1024))
        for index in range(10):
            discovered.append(
                runtime_output(
                    "alpha.service", f"/dev/shm/alpha_{index}", 4096,
                    kind="shared_memory", status="observed_mapped",
                )
            )
        discovered.append(runtime_output("beta.service", "/var/log/beta/runtime.log", 2048))
        output_result["discovered"] = discovered
        original = copy.deepcopy(output_result)
        rendered = render_report.render_program_outputs(contract, output_result)
        self.assertEqual(output_result, original)
        self.assertIn("健康运行时产出 371 项按 2 个服务汇总", rendered)
        self.assertIn("Hugepage 300", rendered)
        self.assertIn("DPDK 60", rendered)
        self.assertIn("SHM 10", rendered)
        self.assertIn("/dev/hugepages/*", rendered)
        self.assertIn("/run/dpdk/*", rendered)
        self.assertNotIn("rte_map_299", rendered)
        self.assertNotIn("file_59", rendered)

    def test_representative_paths_are_limited_to_two_per_service(self) -> None:
        entries = [
            runtime_output("alpha.service", "/var/log/alpha/a.log", 1),
            runtime_output("alpha.service", "/var/lib/alpha/data.bin", 1, kind="data"),
            runtime_output("alpha.service", "/dev/shm/alpha", 1, kind="shared_memory"),
        ]
        rendered = render_report.render_runtime_output_summary(entries)
        alpha_row = next(line for line in rendered.splitlines() if line.startswith("| alpha.service"))
        self.assertIn("/var/log/alpha/a.log", alpha_row)
        self.assertIn("/var/lib/alpha/data.bin", alpha_row)
        self.assertNotIn("/dev/shm/alpha", alpha_row)

    def test_v2_contract_requires_alertd_output_coverage(self) -> None:
        contract = fixture_contract_v2()
        contract["program_outputs"] = contract["program_outputs"][:1]
        with self.assertRaises(ValueError):
            render_report.validate_contract(contract)

    def test_v3_contract_rejects_mode_and_allows_partial_output_coverage(self) -> None:
        contract = fixture_contract_v3()
        contract["program_outputs"] = contract["program_outputs"][:1]
        render_report.validate_contract(contract)
        contract["mode"] = "auto"
        with self.assertRaises(ValueError):
            render_report.validate_contract(contract)

    def test_v3_report_omits_mode_and_reports_automatic_execution(self) -> None:
        snapshot = fixture_snapshot()
        contract = fixture_contract_v3()
        template = (SKILL_ROOT / "assets" / "report-template.md").read_text(encoding="utf-8")
        gate = {
            "schema_version": 2, "phase": "postdeploy", "healthy": True,
            "baseline_clean": False, "failures": [], "warnings": [],
            "inherited_warnings": [
                {"code": "collector_failures", "subject": "alpha", "message": "existing issue"}
            ], "polls": [],
        }
        report = render_report.build_report(
            "succeeded", snapshot, snapshot, contract, gate, template, fixture_output_result()
        )
        self.assertNotIn("**模式：**", report)
        self.assertIn("**自动执行：** 成功", report)
        self.assertIn("部署前基线：** 存在既有警告", report)
        self.assertIn("existing issue", report)

    def test_renderer_cli_accepts_outputs_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inputs = {
                "before.json": fixture_snapshot(),
                "after.json": fixture_snapshot(),
                "contract.json": fixture_contract_v2(),
                "gate.json": {"phase": "postdeploy", "healthy": True, "polls": [{"reasons": []}]},
                "outputs.json": fixture_output_result(),
            }
            for name, value in inputs.items():
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SKILL_ROOT / "scripts" / "render_report.py"),
                    "--before", str(root / "before.json"),
                    "--after", str(root / "after.json"),
                    "--contract", str(root / "contract.json"),
                    "--gate", str(root / "gate.json"),
                    "--outputs", str(root / "outputs.json"),
                    "--status", "succeeded",
                    "--output", str(root / "report.md"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = (root / "report.md").read_text(encoding="utf-8")
            self.assertIn("/var/log/alpha/alpha.log", report)
            self.assertIn("outputs=passed", result.stdout)

    def test_auto_contract_rejects_irreversible_change(self) -> None:
        contract = fixture_contract()
        contract["irreversible_changes"] = ["database migration"]
        with self.assertRaises(ValueError):
            render_report.validate_contract(contract)

    def test_contract_rejects_short_commit(self) -> None:
        contract = copy.deepcopy(fixture_contract())
        contract["repositories"][0]["commit"] = "main"
        with self.assertRaises(ValueError):
            render_report.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
