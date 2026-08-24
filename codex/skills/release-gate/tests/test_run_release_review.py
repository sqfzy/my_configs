from __future__ import annotations

from io import StringIO
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_release_review.py"
SPEC = importlib.util.spec_from_file_location("run_release_review", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RuntimeConfigTests(unittest.TestCase):
    def test_loads_defaults(self) -> None:
        config = MODULE.load_runtime_config({})

        self.assertEqual(config.timeout_seconds, 900)
        self.assertEqual(config.codex_command, "codex")

    def test_rejects_timeout_outside_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 30 and 3600"):
            MODULE.load_runtime_config({"CODEX_RELEASE_REVIEW_TIMEOUT_SECONDS": "29"})


class PushUpdateTests(unittest.TestCase):
    def test_reads_sha1_and_sha256_updates(self) -> None:
        sha1 = "a" * 40
        sha256 = "b" * 64
        updates = MODULE.read_push_updates(
            StringIO(
                f"refs/heads/main {sha1} refs/heads/main {'0' * 40}\n"
                f"refs/heads/next {sha256} refs/heads/next {'0' * 64}\n"
            )
        )

        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0].local_oid, sha1)
        self.assertEqual(updates[1].local_oid, sha256)

    def test_rejects_malformed_update(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 4 fields"):
            MODULE.read_push_updates(StringIO("refs/heads/main deadbeef\n"))


class VerdictTests(unittest.TestCase):
    def write_verdict(self, payload: dict[str, object]) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        output_file = Path(temporary_directory.name) / "verdict.json"
        output_file.write_text(json.dumps(payload), encoding="utf-8")
        return output_file

    def test_accepts_consistent_pass(self) -> None:
        output_file = self.write_verdict(
            {"verdict": "pass", "summary": "No findings.", "findings": [], "residual_risks": []}
        )

        verdict = MODULE.parse_verdict(output_file)

        self.assertEqual(verdict.verdict, "pass")

    def test_rejects_pass_with_findings(self) -> None:
        output_file = self.write_verdict(
            {
                "verdict": "pass",
                "summary": "Incorrect",
                "findings": [{"priority": "P1"}],
                "residual_risks": [],
            }
        )

        with self.assertRaisesRegex(RuntimeError, "inconsistent"):
            MODULE.parse_verdict(output_file)


class CodexProcessTests(unittest.TestCase):
    def test_captures_child_output_and_writes_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            executable = root / "fake-codex"
            executable.write_text(
                """#!/usr/bin/env python3
import json
from pathlib import Path
import sys

output = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
sys.stdin.read()
print("child trace")
output.write_text(json.dumps({
    "verdict": "pass",
    "summary": "No findings.",
    "findings": [],
    "residual_risks": [],
}), encoding="utf-8")
""",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            output_file = root / "verdict.json"
            child_log_file = root / "codex.log"
            request = MODULE.ReviewRequest(
                event="change-request",
                repository=Path.cwd(),
                target="HEAD~1..HEAD",
                remote_name=None,
                push_updates=(),
            )

            return_code = MODULE.run_codex(
                str(executable),
                MODULE.RuntimeConfig(timeout_seconds=30, codex_command=str(executable)),
                request,
                output_file,
                child_log_file,
            )

            self.assertEqual(return_code, 0)
            self.assertEqual(MODULE.parse_verdict(output_file).verdict, "pass")
            self.assertIn("child trace", child_log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
