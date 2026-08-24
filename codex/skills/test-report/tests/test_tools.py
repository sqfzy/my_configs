#!/usr/bin/env python3
"""Deterministic regression tests for the test-report Skill scripts."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))


def load_script(name: str):
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_tests = load_script("run_tests")
render_report = load_script("render_report")


def fixture_contract(root: Path) -> dict[str, object]:
    artifact = root / "candidate.bin"
    artifact.write_bytes(b"candidate")
    return {
        "schema_version": 1,
        "metadata": {
            "title": "工程验收",
            "objective": "验证候选产物",
            "scope": ["unit"],
            "limitations": [],
        },
        "target": {"kind": "local", "ssh": None},
        "execution": {"default_timeout_seconds": 10},
        "evidence": {"max_stream_bytes": 1024 * 1024},
        "subject": {
            "repositories": [],
            "artifacts": [
                {
                    "name": "candidate",
                    "path": str(artifact),
                    "sha256": hashlib.sha256(b"candidate").hexdigest(),
                }
            ],
            "services": [],
        },
        "key_config": [{"name": "runtime.log_level", "source": "test", "value": "info"}],
        "tests": [
            {
                "id": "unit",
                "name": "Unit",
                "category": "unit",
                "required": True,
                "argv": [sys.executable, "-c", "print('ok')"],
                "working_directory": str(root),
                "timeout_seconds": 10,
                "expected_exit_codes": [0],
                "depends_on": [],
                "result_sources": [],
                "mutation_scope": "task_workspace",
                "external_authorized": False,
                "cleanup_argv": None,
            }
        ],
    }


class ContractTests(unittest.TestCase):
    def test_accepts_valid_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_tests.validate_contract(fixture_contract(Path(directory)))

    def test_rejects_forward_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = fixture_contract(Path(directory))
            contract["tests"][0]["depends_on"] = ["future"]
            with self.assertRaisesRegex(ValueError, "earlier tests"):
                run_tests.validate_contract(contract)

    def test_rejects_sensitive_config_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = fixture_contract(Path(directory))
            contract["key_config"] = [{"name": "api_token", "source": "env", "value": "leak"}]
            with self.assertRaisesRegex(ValueError, "sensitive value"):
                run_tests.validate_contract(contract)

    def test_rejects_sensitive_command_argument(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = fixture_contract(Path(directory))
            contract["tests"][0]["argv"] = ["tool", "--password=leak"]
            with self.assertRaisesRegex(ValueError, "sensitive command"):
                run_tests.validate_contract(contract)

    def test_builds_strict_ssh_command(self) -> None:
        target = {
            "kind": "ssh",
            "ssh": {"host": "example", "user": "tester", "port": 2222, "known_hosts": "/tmp/known_hosts"},
        }
        command = run_tests.process_command(target, ["true"], "/srv/test", 30)
        joined = " ".join(command)
        self.assertIn("StrictHostKeyChecking=yes", joined)
        self.assertIn("UserKnownHostsFile=", joined)
        self.assertIn("known_hosts", joined)
        self.assertNotIn("accept-new", joined)


class ExecutionTests(unittest.TestCase):
    def test_executes_and_redacts_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = fixture_contract(root)
            contract["tests"][0]["argv"] = [sys.executable, "-c", "print('password=visible')"]
            output = root / "output"

            execution = run_tests.execute_contract(contract, output)

            result = execution["tests"][0]
            self.assertEqual(result["status"], "passed")
            stdout = Path(result["artifacts"][0]["path"]).read_text(encoding="utf-8")
            self.assertIn("password=<redacted>", stdout)
            self.assertNotIn("visible", stdout)

    def test_blocks_unauthorized_external_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = fixture_contract(root)
            contract["tests"][0]["mutation_scope"] = "external"

            execution = run_tests.execute_contract(contract, root / "output")

            self.assertEqual(execution["tests"][0]["status"], "blocked")

    def test_blocks_failed_dependency_but_runs_independent_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = fixture_contract(root)
            contract["tests"][0]["argv"] = [sys.executable, "-c", "raise SystemExit(1)"]
            dependent = copy.deepcopy(contract["tests"][0])
            dependent.update({"id": "dependent", "name": "Dependent", "depends_on": ["unit"], "argv": [sys.executable, "-c", "print('no')"]})
            independent = copy.deepcopy(contract["tests"][0])
            independent.update({"id": "independent", "name": "Independent", "depends_on": [], "argv": [sys.executable, "-c", "print('yes')"]})
            contract["tests"].extend([dependent, independent])

            execution = run_tests.execute_contract(contract, root / "output")

            self.assertEqual([item["status"] for item in execution["tests"]], ["failed", "blocked", "passed"])

    def test_cleanup_failure_changes_status_to_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = fixture_contract(root)
            test = contract["tests"][0]
            test.update(
                {
                    "mutation_scope": "external",
                    "external_authorized": True,
                    "cleanup_argv": [sys.executable, "-c", "raise SystemExit(1)"],
                }
            )

            execution = run_tests.execute_contract(contract, root / "output")

            self.assertEqual(execution["tests"][0]["status"], "error")
            self.assertFalse(execution["tests"][0]["cleanup"]["succeeded"])

    def test_marks_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = fixture_contract(root)
            contract["tests"][0].update(
                {"argv": [sys.executable, "-c", "import time; time.sleep(2)"], "timeout_seconds": 1}
            )

            execution = run_tests.execute_contract(contract, root / "output")

            self.assertEqual(execution["tests"][0]["status"], "timed_out")

    def test_truncates_and_hashes_retained_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "retained.log"
            source.write_text("password=visible-and-long", encoding="utf-8")

            evidence = run_tests.retain_file(source, destination, 12)

            self.assertTrue(evidence["truncated"])
            self.assertEqual(evidence["sha256"], hashlib.sha256(destination.read_bytes()).hexdigest())
            self.assertNotIn("visible", destination.read_text(encoding="utf-8"))


class ParserTests(unittest.TestCase):
    def write(self, root: Path, name: str, text: str) -> Path:
        path = root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_parses_junit_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(
                Path(directory),
                "junit.xml",
                '<testsuite><testcase classname="a" name="ok"/><testcase classname="a" name="bad"><failure/></testcase><testcase name="skip"><skipped/></testcase></testsuite>',
            )
            result = render_report.parse_junit(path)
            self.assertEqual(result["tests"], 3)
            self.assertEqual(result["failures"], 1)
            self.assertEqual(result["skipped"], 1)

    def test_rejects_malformed_junit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(Path(directory), "junit.xml", "<testsuite>")
            with self.assertRaises(Exception):
                render_report.parse_junit(path)

    def test_evaluates_metrics_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "measurements": [
                            {"kind": "metric", "name": "latency", "value": 9, "unit": "ms", "operator": "<=", "threshold": 10},
                            {"kind": "coverage", "name": "line", "value": 80, "unit": "%", "operator": ">=", "threshold": 80},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            results = render_report.parse_metrics(path)
            self.assertTrue(all(item["passed"] for item in results))

    def test_supports_every_metric_operator(self) -> None:
        measurements = [
            {"kind": "metric", "name": "lt", "value": 1, "unit": "x", "operator": "<", "threshold": 2},
            {"kind": "metric", "name": "le", "value": 2, "unit": "x", "operator": "<=", "threshold": 2},
            {"kind": "metric", "name": "gt", "value": 2, "unit": "x", "operator": ">", "threshold": 1},
            {"kind": "metric", "name": "ge", "value": 2, "unit": "x", "operator": ">=", "threshold": 2},
            {"kind": "metric", "name": "eq", "value": 2, "unit": "x", "operator": "==", "threshold": 2},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            path.write_text(json.dumps({"schema_version": 1, "measurements": measurements}), encoding="utf-8")
            self.assertTrue(all(item["passed"] for item in render_report.parse_metrics(path)))

    def test_rejects_non_finite_metric(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            path.write_text(
                json.dumps({"schema_version": 1, "measurements": [{"kind": "metric", "name": "x", "value": float("inf"), "unit": "ms", "operator": "<", "threshold": 1}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "finite"):
                render_report.parse_metrics(path)


class VerdictTests(unittest.TestCase):
    def test_overall_verdict_matrix(self) -> None:
        cases = [
            ([{"required": True, "status": "passed"}], [], "passed"),
            ([{"required": True, "status": "failed"}], [], "failed"),
            ([{"required": True, "status": "blocked"}], [], "inconclusive"),
            ([{"required": True, "status": "passed"}, {"required": False, "status": "failed"}], [], "passed_with_warnings"),
            ([{"required": True, "status": "passed"}], ["warning"], "passed_with_warnings"),
        ]
        for tests, warnings, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(render_report.overall_verdict(tests, warnings), expected)

    def test_recommendation_matrix(self) -> None:
        exact = {"identifiable": True, "exact": True, "verified": True, "mismatch": False}
        test = {"status": "passed", "mutation_scope": "read_only", "cleanup": None}
        self.assertEqual(render_report.recommendation("passed", exact, [test], [])[0], "go")
        dirty = {**exact, "exact": False}
        self.assertEqual(render_report.recommendation("passed", dirty, [test], [])[0], "conditional")
        missing = {**exact, "identifiable": False}
        self.assertEqual(render_report.recommendation("passed", missing, [test], [])[0], "no-go")


class DeploymentImportTests(unittest.TestCase):
    def execution(self) -> dict[str, object]:
        return {
            "target": {"kind": "ssh"},
            "context_before": {
                "target": {"host": "server-a"},
                "subject": {"repositories": [{"role": "app", "commit": "a" * 40}], "artifacts": []},
            },
        }

    def evidence(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "deployment_test_context",
            "target": {"host": "server-a"},
            "subject": {"repositories": [{"role": "app", "commit": "a" * 40}], "artifacts": []},
        }

    def test_accepts_matching_deployment_evidence(self) -> None:
        evidence, warnings = render_report.import_deployment_evidence(self.execution(), self.evidence())
        self.assertIsNotNone(evidence)
        self.assertEqual(warnings, [])

    def test_rejects_host_conflict(self) -> None:
        evidence = self.evidence()
        evidence["target"]["host"] = "server-b"
        imported, warnings = render_report.import_deployment_evidence(self.execution(), evidence)
        self.assertIsNone(imported)
        self.assertIn("host mismatch", warnings[0])

    def test_rejects_forbidden_credentials(self) -> None:
        evidence = self.evidence()
        evidence["access_token"] = "leak"
        imported, warnings = render_report.import_deployment_evidence(self.execution(), evidence)
        self.assertIsNone(imported)
        self.assertIn("forbidden", warnings[0])


class RenderingTests(unittest.TestCase):
    def test_template_rejects_unknown_placeholder(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported placeholders"):
            render_report.render_template("{{unknown}}", {})

    def test_manifest_hashes_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "value.log").write_text("value", encoding="utf-8")
            manifest = render_report.build_manifest(root, [])
            self.assertEqual(manifest["entries"][0]["sha256"], hashlib.sha256(b"value").hexdigest())


if __name__ == "__main__":
    unittest.main()
