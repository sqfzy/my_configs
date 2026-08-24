#!/usr/bin/env python3
"""Render a standalone Chinese test report from normalized execution evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import math
import mimetypes
import os
import re
import shlex
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import run_tests as contract_tools


LOG = logging.getLogger("test_report.render_report")
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)}}")
OPERATORS = {
    "<": lambda value, threshold: value < threshold,
    "<=": lambda value, threshold: value <= threshold,
    ">": lambda value, threshold: value > threshold,
    ">=": lambda value, threshold: value >= threshold,
    "==": lambda value, threshold: value == threshold,
}
NON_PASSING = {"failed", "error", "timed_out", "blocked", "skipped"}
FAILURES = {"failed", "error", "timed_out"}
INCONCLUSIVE = {"blocked", "skipped"}
STATUS_LABELS = {
    "passed": "通过",
    "passed_with_warnings": "通过但有警告",
    "failed": "失败",
    "inconclusive": "无法判定",
    "error": "错误",
    "timed_out": "超时",
    "blocked": "阻塞",
    "skipped": "跳过",
}


def parse_args() -> argparse.Namespace:
    default_template = Path(__file__).resolve().parent.parent / "assets" / "report-template.md"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--deploy-evidence", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--template", type=Path, default=default_template)
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


def write_text(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def validate_execution(execution: dict[str, Any]) -> None:
    if execution.get("schema_version") != 1:
        raise ValueError("execution schema_version must be 1")
    if not isinstance(execution.get("context_before"), dict) or not isinstance(execution.get("context_after"), dict):
        raise ValueError("execution needs before and after contexts")
    if not isinstance(execution.get("tests"), list):
        raise ValueError("execution tests must be an array")


def resolve_evidence_path(item: dict[str, Any], execution_path: Path) -> Path:
    path = Path(str(item.get("path", "")))
    if path.is_absolute():
        return path
    return execution_path.parent / path


def parse_junit(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    failures = []
    errors = []
    skipped = []
    for case in cases:
        name = str(case.get("name", "unknown"))
        classname = str(case.get("classname", ""))
        identity = f"{classname}.{name}" if classname else name
        if case.find("failure") is not None:
            failures.append(identity)
        if case.find("error") is not None:
            errors.append(identity)
        if case.find("skipped") is not None:
            skipped.append(identity)
    return {
        "tests": len(cases),
        "failures": len(failures),
        "errors": len(errors),
        "skipped": len(skipped),
        "failed_cases": failures,
        "error_cases": errors,
        "skipped_cases": skipped,
    }


def finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def parse_metrics(path: Path) -> list[dict[str, Any]]:
    value = load_json(path)
    if value.get("schema_version") != 1 or not isinstance(value.get("measurements"), list):
        raise ValueError("metrics JSON must use schema_version 1 and a measurements array")
    results = []
    for index, item in enumerate(value["measurements"]):
        if not isinstance(item, dict):
            raise ValueError(f"measurement {index} must be an object")
        kind = item.get("kind")
        name = str(item.get("name", "")).strip()
        unit = str(item.get("unit", "")).strip()
        operator = item.get("operator")
        if kind not in {"metric", "coverage"} or not name or not unit or operator not in OPERATORS:
            raise ValueError(f"measurement {index} has invalid kind, name, unit, or operator")
        measured = finite_number(item.get("value"), f"measurement {index} value")
        threshold = finite_number(item.get("threshold"), f"measurement {index} threshold")
        results.append(
            {
                "kind": kind,
                "name": name,
                "value": measured,
                "unit": unit,
                "operator": operator,
                "threshold": threshold,
                "passed": OPERATORS[operator](measured, threshold),
            }
        )
    return results


def evaluate_result_source(
    item: dict[str, Any],
    execution_path: Path,
) -> tuple[str | None, dict[str, Any] | None, list[dict[str, Any]], str | None]:
    if item.get("missing"):
        return "error", None, [], f"missing result source: {item.get('original_path', 'unknown')}"
    if item.get("truncated"):
        return "error", None, [], f"truncated result source: {item.get('original_path', 'unknown')}"
    path = resolve_evidence_path(item, execution_path)
    if not path.is_file():
        return "error", None, [], f"retained result source is missing: {path}"
    try:
        if item.get("kind") == "junit_xml":
            junit = parse_junit(path)
            if junit["failures"] or junit["errors"]:
                return "failed", junit, [], None
            if junit["tests"] == 0 or junit["skipped"] == junit["tests"]:
                return "skipped", junit, [], None
            return None, junit, [], None
        if item.get("kind") == "metrics_json":
            measurements = parse_metrics(path)
            return ("failed" if any(not metric["passed"] for metric in measurements) else None), None, measurements, None
        return "error", None, [], f"unsupported result kind: {item.get('kind')}"
    except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as error:
        return "error", None, [], str(error)


def final_status(initial: str, source_statuses: list[str]) -> str:
    if initial != "passed":
        return initial
    if "error" in source_statuses:
        return "error"
    if "failed" in source_statuses:
        return "failed"
    if "skipped" in source_statuses:
        return "skipped"
    return "passed"


def evaluate_tests(
    contract: dict[str, Any],
    execution: dict[str, Any],
    execution_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    declarations = {item["id"]: item for item in contract["tests"]}
    results = []
    measurements = []
    warnings = []
    seen: set[str] = set()
    for recorded in execution["tests"]:
        test_id = str(recorded.get("id", ""))
        if test_id not in declarations or test_id in seen:
            raise ValueError(f"execution contains unknown or duplicate test id: {test_id!r}")
        seen.add(test_id)
        source_statuses = []
        junit_results = []
        source_warnings = []
        test_measurements = []
        for source in recorded.get("result_sources", []):
            status, junit, parsed_measurements, warning = evaluate_result_source(source, execution_path)
            if status:
                source_statuses.append(status)
            if junit:
                junit_results.append(junit)
            test_measurements.extend(parsed_measurements)
            if warning:
                source_warnings.append(warning)
        status = final_status(str(recorded.get("status", "error")), source_statuses)
        if recorded.get("cleanup") is not None and not recorded["cleanup"].get("succeeded"):
            status = "error"
            source_warnings.append("cleanup failed")
        result = {
            **recorded,
            "status": status,
            "junit": junit_results,
            "measurements": test_measurements,
            "warnings": source_warnings,
        }
        measurements.extend({**metric, "test_id": test_id} for metric in test_measurements)
        warnings.extend(f"{test_id}: {warning}" for warning in source_warnings)
        results.append(result)
    missing = set(declarations) - seen
    if missing:
        raise ValueError(f"execution is missing tests: {', '.join(sorted(missing))}")
    return results, measurements, warnings


def target_host(execution: dict[str, Any]) -> str:
    context = execution.get("context_before", {})
    return str(context.get("target", {}).get("host", ""))


def repository_key(repository: dict[str, Any]) -> str:
    return str(repository.get("role") or repository.get("url") or repository.get("path") or "")


def artifact_key(artifact: dict[str, Any]) -> str:
    return str(artifact.get("name") or artifact.get("path") or "")


def deployment_conflicts(execution: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    conflicts = []
    observed_host = target_host(execution)
    deployed_host = str(evidence.get("target", {}).get("host", ""))
    target_kind = execution.get("target", {}).get("kind", "local")
    if target_kind == "ssh" and observed_host and deployed_host and observed_host != deployed_host:
        conflicts.append(f"host mismatch: test={observed_host} deploy={deployed_host}")
    observed_subject = execution.get("context_before", {}).get("subject", {})
    deployed_subject = evidence.get("subject", {})
    deployed_repositories = {repository_key(item): item for item in deployed_subject.get("repositories", [])}
    for repository in observed_subject.get("repositories", []):
        candidate = deployed_repositories.get(repository_key(repository))
        if candidate and repository.get("commit") and candidate.get("commit") and str(repository["commit"]).lower() != str(candidate["commit"]).lower():
            conflicts.append(f"repository commit mismatch: {repository_key(repository)}")
    deployed_artifacts = {artifact_key(item): item for item in deployed_subject.get("artifacts", [])}
    for artifact in observed_subject.get("artifacts", []):
        candidate = deployed_artifacts.get(artifact_key(artifact))
        if candidate and artifact.get("sha256") and candidate.get("sha256") and str(artifact["sha256"]).lower() != str(candidate["sha256"]).lower():
            conflicts.append(f"artifact digest mismatch: {artifact_key(artifact)}")
    return conflicts


def import_deployment_evidence(
    execution: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    if not evidence:
        return None, []
    if evidence.get("schema_version") != 1 or evidence.get("kind") != "deployment_test_context":
        return None, ["deployment evidence has an unsupported schema"]
    forbidden = re.compile(r"(?i)(webhook|access[_-]?token|signing[_-]?secret)")
    serialized = json.dumps(evidence, ensure_ascii=False)
    if forbidden.search(serialized):
        return None, ["deployment evidence contains forbidden credential fields"]
    conflicts = deployment_conflicts(execution, evidence)
    if conflicts:
        return None, [f"deployment evidence rejected: {value}" for value in conflicts]
    return evidence, []


def subject_identity(
    contract: dict[str, Any],
    execution: dict[str, Any],
    deployment: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    observed = execution.get("context_before", {}).get("subject", {})
    repositories = list(observed.get("repositories", []))
    artifacts = list(observed.get("artifacts", []))
    if deployment:
        deployed = deployment.get("subject", {})
        known_repositories = {repository_key(item) for item in repositories}
        repositories.extend(item for item in deployed.get("repositories", []) if repository_key(item) not in known_repositories)
        known_artifacts = {artifact_key(item) for item in artifacts}
        artifacts.extend(item for item in deployed.get("artifacts", []) if artifact_key(item) not in known_artifacts)
    warnings = []
    mismatch = any(item.get("status") == "mismatch" for item in repositories + artifacts)
    if mismatch:
        warnings.append("observed subject does not match the frozen declaration")
    unavailable = [item for item in repositories + artifacts if item.get("status") == "unavailable"]
    if unavailable:
        warnings.append("some declared subject identities could not be observed")
    dirty = any(item.get("dirty") for item in repositories)
    if dirty:
        warnings.append("the tested repository has uncommitted changes")
    declared = contract["subject"]
    identifiable = any(contract_tools.GIT_COMMIT.fullmatch(str(item.get("commit", ""))) for item in repositories)
    identifiable = identifiable or any(contract_tools.SHA256.fullmatch(str(item.get("sha256", ""))) for item in artifacts)
    identifiable = identifiable or any(contract_tools.GIT_COMMIT.fullmatch(str(item.get("commit", ""))) for item in declared.get("repositories", []))
    identifiable = identifiable or any(contract_tools.SHA256.fullmatch(str(item.get("sha256", ""))) for item in declared.get("artifacts", []))
    exact = identifiable and not mismatch and not unavailable and not dirty
    verified = any(item.get("status") == "matched" and (item.get("commit") or item.get("sha256")) for item in repositories + artifacts)
    return {
        "repositories": repositories,
        "artifacts": artifacts,
        "identifiable": identifiable,
        "exact": exact,
        "verified": verified,
        "dirty": dirty,
        "mismatch": mismatch,
    }, warnings


def overall_verdict(tests: list[dict[str, Any]], warnings: list[str]) -> str:
    required = [item for item in tests if item["required"]]
    if any(item["status"] in FAILURES for item in required):
        return "failed"
    if any(item["status"] in INCONCLUSIVE for item in required):
        return "inconclusive"
    optional_nonpassing = any(item["status"] in NON_PASSING for item in tests if not item["required"])
    return "passed_with_warnings" if optional_nonpassing or warnings else "passed"


def recommendation(
    verdict: str,
    subject: dict[str, Any],
    tests: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[str, list[str]]:
    reasons = []
    cleanup_failed = any(item.get("cleanup") is not None and not item["cleanup"].get("succeeded") for item in tests)
    unauthorized_external = any(item.get("mutation_scope") == "external" and item["status"] == "blocked" for item in tests)
    if verdict in {"failed", "inconclusive"}:
        reasons.append(f"overall verdict is {verdict}")
    if not subject["identifiable"]:
        reasons.append("tested subject is not identifiable")
    if subject["mismatch"]:
        reasons.append("tested subject conflicts with the frozen declaration")
    if cleanup_failed:
        reasons.append("cleanup failed")
    if unauthorized_external:
        reasons.append("external mutation was not authorized")
    if reasons:
        return "no-go", reasons
    conditional = verdict == "passed_with_warnings" or not subject["exact"] or not subject["verified"] or bool(warnings)
    if conditional:
        if verdict == "passed_with_warnings":
            reasons.append("optional failures or warnings remain")
        if not subject["exact"] or not subject["verified"]:
            reasons.append("subject identity is dirty, unverified, or incomplete")
        return "conditional", reasons
    return "go", ["all required tests and evidence gates passed"]


def markdown(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "无。"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(markdown(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def render_summary(result: dict[str, Any]) -> str:
    return (
        f"- **测试结论：** {STATUS_LABELS[result['verdict']]}\n"
        f"- **基于测试的发布建议：** `{result['recommendation']}`\n"
        f"- **建议依据：** {'；'.join(result['recommendation_reasons'])}\n"
        f"- **测试目标：** `{markdown(target_host(result['execution']))}`\n"
        f"- **执行时间：** `{result['execution'].get('started_at', 'unknown')}` 至 `{result['execution'].get('finished_at', 'unknown')}`\n"
        f"- **报告生成时间：** `{result['generated_at']}`"
    )


def render_scope(contract: dict[str, Any]) -> str:
    metadata = contract["metadata"]
    scope = metadata.get("scope", [])
    return (
        f"- **目标：** {markdown(metadata['objective'])}\n"
        f"- **范围：** {markdown(', '.join(str(item) for item in scope) if scope else '按测试合同中的全部测试')}"
    )


def render_subject(subject: dict[str, Any]) -> str:
    rows = []
    for item in subject["repositories"]:
        rows.append(["repository", item.get("role", ""), item.get("url") or item.get("path", ""), item.get("commit") or item.get("declared_commit", "unknown"), "dirty" if item.get("dirty") else item.get("status", "imported")])
    for item in subject["artifacts"]:
        rows.append(["artifact", item.get("name", ""), item.get("path", ""), item.get("sha256") or item.get("declared_sha256", "unknown"), item.get("status", "imported")])
    return table(["类型", "角色/名称", "来源", "不可变标识", "状态"], rows)


def render_environment(execution: dict[str, Any]) -> str:
    before = execution.get("context_before", {})
    after = execution.get("context_after", {})
    machine = before.get("machine", {})
    after_machine = after.get("machine", {})
    memory = machine.get("memory", {})
    after_memory = after_machine.get("memory", {})
    rows = [
        ["主机", machine.get("hostname", "unknown"), after_machine.get("hostname", "unknown")],
        ["系统", machine.get("system", "unknown"), after_machine.get("system", "unknown")],
        ["内核", machine.get("release", "unknown"), after_machine.get("release", "unknown")],
        ["架构", machine.get("architecture", "unknown"), after_machine.get("architecture", "unknown")],
        ["逻辑 CPU", machine.get("cpu_count", "unknown"), after_machine.get("cpu_count", "unknown")],
        ["总内存(B)", memory.get("MemTotal", "unknown"), after_memory.get("MemTotal", "unknown")],
        ["可用内存(B)", memory.get("MemAvailable", "unknown"), after_memory.get("MemAvailable", "unknown")],
    ]
    services = before.get("services", [])
    service_text = table(["服务", "状态", "子状态", "结果", "MainPID"], [[item.get("unit", ""), item.get("ActiveState", item.get("status", "unknown")), item.get("SubState", ""), item.get("Result", ""), item.get("MainPID", "")] for item in services])
    return table(["字段", "测试前", "测试后"], rows) + "\n\n### 声明服务\n\n" + service_text


def render_key_config(contract: dict[str, Any]) -> str:
    return table(["名称", "来源", "有效值"], [[item.get("name", ""), item.get("source", ""), contract_tools.redact_text(str(item.get("value", "")))] for item in contract.get("key_config", [])])


def render_test_overview(tests: list[dict[str, Any]]) -> str:
    counts = {status: sum(item["status"] == status for item in tests) for status in {item["status"] for item in tests}}
    return table(["总数", "必选", "通过", "失败", "错误", "超时", "阻塞", "跳过"], [[len(tests), sum(item["required"] for item in tests), counts.get("passed", 0), counts.get("failed", 0), counts.get("error", 0), counts.get("timed_out", 0), counts.get("blocked", 0), counts.get("skipped", 0)]])


def render_test_details(tests: list[dict[str, Any]]) -> str:
    rows = []
    for item in tests:
        junit = item.get("junit", [])
        cases = sum(value.get("tests", 0) for value in junit)
        rows.append([item["id"], item.get("category", ""), "是" if item["required"] else "否", STATUS_LABELS.get(item["status"], item["status"]), item.get("duration_seconds", 0), cases or "—", item.get("reason", "")])
    return table(["ID", "类别", "必选", "状态", "耗时(s)", "JUnit 用例", "说明"], rows)


def render_failures(tests: list[dict[str, Any]]) -> str:
    rows = []
    for item in tests:
        if item["status"] not in NON_PASSING and not item.get("warnings"):
            continue
        case_names = []
        for junit in item.get("junit", []):
            case_names.extend(junit.get("failed_cases", []) + junit.get("error_cases", []))
        rows.append([item["id"], STATUS_LABELS.get(item["status"], item["status"]), item.get("reason", ""), ", ".join(case_names[:10]) or "—", "；".join(item.get("warnings", [])) or "—"])
    return table(["测试", "状态", "原因", "失败用例", "证据/清理异常"], rows)


def render_measurements(measurements: list[dict[str, Any]]) -> str:
    return table(["测试", "类型", "指标", "实测", "门槛", "结果"], [[item["test_id"], item["kind"], item["name"], f"{item['value']} {item['unit']}", f"{item['operator']} {item['threshold']} {item['unit']}", "通过" if item["passed"] else "失败"] for item in measurements])


def render_deployment(deployment: dict[str, Any] | None) -> str:
    if not deployment:
        return "未提供可兼容的部署证据；本报告使用测试时自行采集的上下文。"
    health = deployment.get("runtime", {}).get("health", {})
    outputs = deployment.get("runtime", {}).get("program_outputs", {})
    rows = [
        ["部署状态", deployment.get("deployment_status", "unknown")],
        ["证据生成时间", deployment.get("generated_at", "unknown")],
        ["健康门禁", health.get("healthy", "unknown")],
        ["程序产出门禁", outputs.get("healthy", "unknown")],
    ]
    return table(["字段", "值"], rows)


def render_risks(contract: dict[str, Any], warnings: list[str]) -> str:
    limitations = [str(item) for item in contract["metadata"].get("limitations", [])]
    values = limitations + warnings
    return "\n".join(f"- {markdown(item)}" for item in values) if values else "- 无已知限制或残余风险。"


def render_reproduce(contract: dict[str, Any]) -> str:
    rows = []
    target = contract.get("target", {"kind": "local"})
    for item in contract["tests"]:
        command = f"cd {shlex.quote(str(item.get('working_directory', '.')))} && {shlex.join(item['argv'])}"
        if target.get("kind") == "ssh":
            ssh = target["ssh"]
            command = f"ssh -p {ssh.get('port', 22)} {shlex.quote(str(ssh['user']))}@{shlex.quote(str(ssh['host']))} -- {shlex.quote(command)}"
        rows.append([item["id"], contract_tools.redact_text(command)])
    return table(["测试", "命令"], rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(output_dir: Path, tests: list[dict[str, Any]]) -> dict[str, Any]:
    artifact_metadata = {}
    for test in tests:
        for item in test.get("artifacts", []) + test.get("result_sources", []):
            if item.get("path"):
                artifact_metadata[str(Path(item["path"]).resolve())] = item
    entries = []
    for path in sorted(value for value in output_dir.rglob("*") if value.is_file() and value.name != "evidence-manifest.json"):
        metadata = artifact_metadata.get(str(path.resolve()), {})
        entries.append(
            {
                "path": str(path.relative_to(output_dir)),
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
                "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "test_id": metadata.get("test_id"),
                "redacted": bool(metadata.get("redacted", path.suffix in {".log", ".xml", ".json", ".md"})),
                "truncated": bool(metadata.get("truncated", False)),
            }
        )
    return {"schema_version": 1, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "entries": entries}


def render_evidence(manifest: dict[str, Any]) -> str:
    return table(["路径", "SHA-256", "字节", "来源测试", "脱敏", "截断"], [[item["path"], item["sha256"], item["bytes"], item.get("test_id") or "—", "是" if item["redacted"] else "否", "是" if item["truncated"] else "否"] for item in manifest["entries"]])


def render_template(template: str, sections: dict[str, str]) -> str:
    missing = set(PLACEHOLDER.findall(template)) - set(sections)
    if missing:
        raise ValueError(f"template has unsupported placeholders: {', '.join(sorted(missing))}")
    rendered = PLACEHOLDER.sub(lambda match: sections[match.group(1)], template)
    if PLACEHOLDER.search(rendered):
        raise ValueError("report contains unresolved placeholders")
    return rendered.rstrip() + "\n"


def build_result(
    contract: dict[str, Any],
    execution: dict[str, Any],
    execution_path: Path,
    deploy_evidence: dict[str, Any],
) -> dict[str, Any]:
    tests, measurements, warnings = evaluate_tests(contract, execution, execution_path)
    deployment, deployment_warnings = import_deployment_evidence(execution, deploy_evidence)
    warnings.extend(deployment_warnings)
    subject, subject_warnings = subject_identity(contract, execution, deployment)
    warnings.extend(subject_warnings)
    verdict = overall_verdict(tests, warnings)
    decision, reasons = recommendation(verdict, subject, tests, warnings)
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "metadata": contract["metadata"],
        "verdict": verdict,
        "recommendation": decision,
        "recommendation_reasons": reasons,
        "subject": subject,
        "environment": {
            "before": execution["context_before"],
            "after": execution["context_after"],
        },
        "tests": tests,
        "measurements": measurements,
        "warnings": warnings,
        "deployment_context": deployment,
        "execution": execution,
    }


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        contract = load_json(args.contract)
        contract_tools.validate_contract(contract)
        execution = load_json(args.execution)
        validate_execution(execution)
        deploy_evidence = load_json(args.deploy_evidence, required=False)
        output_dir = args.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        result = build_result(contract, execution, args.execution.expanduser().resolve(), deploy_evidence)
        result_path = output_dir / "test-result.json"
        write_json(result_path, result)
        manifest = build_manifest(output_dir, result["tests"])
        sections = {
            "title": contract_tools.redact_text(str(contract["metadata"]["title"])),
            "summary": render_summary(result),
            "scope": render_scope(contract),
            "subject": render_subject(result["subject"]),
            "environment": render_environment(execution),
            "key_config": render_key_config(contract),
            "test_overview": render_test_overview(result["tests"]),
            "test_details": render_test_details(result["tests"]),
            "failures": render_failures(result["tests"]),
            "measurements": render_measurements(result["measurements"]),
            "deployment_context": render_deployment(result["deployment_context"]),
            "risks": render_risks(contract, result["warnings"]),
            "reproduce": render_reproduce(contract),
            "evidence": render_evidence(manifest),
        }
        template = args.template.expanduser().read_text(encoding="utf-8")
        write_text(output_dir / "test-report.md", render_template(template, sections))
        manifest = build_manifest(output_dir, result["tests"])
        write_json(output_dir / "evidence-manifest.json", manifest)
        print(
            f"verdict={result['verdict']} recommendation={result['recommendation']} "
            f"report={output_dir / 'test-report.md'}"
        )
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, ET.ParseError) as error:
        LOG.error("test report rendering failed error=%s", error)
        return 2


if __name__ == "__main__":
    sys.exit(main())
