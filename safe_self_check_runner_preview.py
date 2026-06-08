from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from root_flow_auditor_preview import ROOT_FLOW_BEHAVIOR_OWNERS, build_root_flow_audit


SELF_CHECK_REGISTRY: Dict[str, Dict[str, Any]] = {
    "py_compile_check": {
        "title": "Python compile check",
        "category": "syntax",
        "description": "Preview whether a py_compile command should be run for touched Python files.",
        "safe_for_lux": True,
        "codex_required": False,
    },
    "smoke_check": {
        "title": "Smoke check",
        "category": "regression",
        "description": "Preview the repository smoke_check command for scaffold and endpoint regressions.",
        "safe_for_lux": True,
        "codex_required": False,
    },
    "endpoint_health_check": {
        "title": "Endpoint health check",
        "category": "runtime",
        "description": "Preview health/status endpoint checks without changing deployment state.",
        "safe_for_lux": True,
        "codex_required": False,
    },
    "route_existence_check": {
        "title": "Route existence check",
        "category": "routing",
        "description": "Preview checking whether expected debug/status routes are present.",
        "safe_for_lux": True,
        "codex_required": False,
    },
    "behavior_owner_check": {
        "title": "Behavior owner check",
        "category": "ownership",
        "description": "Preview whether a behavior maps to a single owner from Root Flow Auditor.",
        "safe_for_lux": True,
        "codex_required": False,
    },
    "missing_helper_check": {
        "title": "Missing helper check",
        "category": "imports",
        "description": "Preview likely helper/import gaps from root-cause signals.",
        "safe_for_lux": True,
        "codex_required": True,
    },
    "undefined_variable_check": {
        "title": "Undefined variable check",
        "category": "scope",
        "description": "Preview likely undefined variable/scope checks from root-cause signals.",
        "safe_for_lux": True,
        "codex_required": True,
    },
    "duplicate_branch_check": {
        "title": "Duplicate branch check",
        "category": "control_flow",
        "description": "Preview duplicate behavior branches or duplicate owners.",
        "safe_for_lux": True,
        "codex_required": True,
    },
    "stale_fallback_check": {
        "title": "Stale fallback check",
        "category": "fallback",
        "description": "Preview stale fallback/final response paths that may leak late output.",
        "safe_for_lux": True,
        "codex_required": True,
    },
    "manual_scenario_check": {
        "title": "Manual scenario check",
        "category": "manual",
        "description": "Preview manual reproduction steps suggested by Root Flow Auditor.",
        "safe_for_lux": True,
        "codex_required": False,
    },
}


ROOT_CAUSE_TO_CHECKS: Dict[str, List[str]] = {
    "duplicate_branch": ["duplicate_branch_check", "behavior_owner_check"],
    "stale_fallback": ["stale_fallback_check", "endpoint_health_check"],
    "missing_helper": ["missing_helper_check", "py_compile_check"],
    "undefined_variable": ["undefined_variable_check", "py_compile_check"],
    "state_source_conflict": ["behavior_owner_check", "manual_scenario_check"],
    "duplicate_owner": ["behavior_owner_check", "duplicate_branch_check"],
    "event_leak": ["stale_fallback_check", "manual_scenario_check"],
    "incomplete_test_coverage": ["smoke_check", "manual_scenario_check"],
}


def _unique(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def self_check_status() -> Dict[str, Any]:
    return {
        "layer": "23.2",
        "name": "Safe Self Check Runner Preview",
        "status": "scaffold_ready",
        "read_only": True,
        "real_check_executed": False,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "real_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "root_flow_auditor_connected": True,
        "available_endpoints": [
            "/debug/self-check-status",
            "/debug/self-check-registry",
            "/debug/self-check-preview",
        ],
        "check_types": list(SELF_CHECK_REGISTRY.keys()),
        "safety_note": "Preview only. Organizes safe checks without running commands, changing files, writing git state, deploying, or fixing code.",
    }


def self_check_registry() -> Dict[str, Any]:
    return {
        "layer": "23.2",
        "status": "registry_ready",
        "read_only": True,
        "checks": [
            {"id": check_id, **spec, "read_only": True, "real_check_executed": False}
            for check_id, spec in SELF_CHECK_REGISTRY.items()
        ],
        "root_cause_to_checks": ROOT_CAUSE_TO_CHECKS,
        "behavior_owner_ids": list(ROOT_FLOW_BEHAVIOR_OWNERS.keys()),
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
    }


def _checks_for_audit(audit: Dict[str, Any], requested_checks: Optional[List[str]] = None) -> List[str]:
    requested = [item for item in (requested_checks or []) if item in SELF_CHECK_REGISTRY]
    if requested:
        return _unique(requested)

    check_ids = ["behavior_owner_check", "route_existence_check"]
    for cause in audit.get("possible_root_causes", []):
        cause_id = str(cause.get("id", ""))
        check_ids.extend(ROOT_CAUSE_TO_CHECKS.get(cause_id, []))
    if audit.get("smoke_gap_detector", {}).get("missing_smoke_coverage"):
        check_ids.extend(["smoke_check", "manual_scenario_check"])
    return _unique(check_ids)


def _possible_findings(audit: Dict[str, Any], checks_run: List[str]) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    owner = audit.get("behavior_owner", {})
    if "behavior_owner_check" in checks_run:
        findings.append({
            "id": "behavior_owner_confirmed",
            "summary": f"Behavior owner preview is {owner.get('owner', 'unknown')}.",
        })
    if "smoke_check" in checks_run and audit.get("smoke_gap_detector", {}).get("missing_smoke_coverage"):
        findings.append({
            "id": "missing_smoke_coverage_possible",
            "summary": "Exact behavior may need additional smoke/manual coverage.",
        })
    for cause in audit.get("possible_root_causes", []):
        cause_id = str(cause.get("id", ""))
        for check_id in ROOT_CAUSE_TO_CHECKS.get(cause_id, []):
            if check_id in checks_run:
                findings.append({
                    "id": f"{cause_id}_possible",
                    "summary": str(cause.get("reason", SELF_CHECK_REGISTRY[check_id]["description"])),
                })
                break
    return findings


def _confidence_score(audit: Dict[str, Any], checks_run: List[str]) -> float:
    base = float(audit.get("confidence_score", 0.4) or 0.4)
    coverage_bonus = min(0.12, len(checks_run) * 0.015)
    return round(min(0.95, base + coverage_bonus), 2)


def _codex_required(checks_run: List[str], audit: Dict[str, Any]) -> bool:
    if audit.get("risk_level") == "high":
        return True
    return any(SELF_CHECK_REGISTRY.get(check_id, {}).get("codex_required") for check_id in checks_run)


def build_self_check_preview(
    command: str,
    behavior: Optional[str] = None,
    observed_behavior: Optional[str] = None,
    expected_behavior: Optional[str] = None,
    requested_checks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    audit = build_root_flow_audit(
        command=command,
        behavior=behavior,
        observed_behavior=observed_behavior,
        expected_behavior=expected_behavior,
        smoke_tests=[],
    )
    checks_run = _checks_for_audit(audit, requested_checks)
    possible_findings = _possible_findings(audit, checks_run)
    codex_required = _codex_required(checks_run, audit)
    command_text = _normalize(" ".join([command or "", observed_behavior or "", expected_behavior or ""]))
    lux_can_handle = [
        "summarize audit findings",
        "map behavior owner",
        "suggest safe manual scenario",
        "identify missing smoke coverage",
    ]
    if "endpoint" in command_text or "health" in command_text:
        lux_can_handle.append("suggest endpoint health preview")

    codex_recommended_for = [
        "actual code inspection",
        "running real shell tests",
        "editing implementation files",
    ] if codex_required else [
        "optional verification if preview findings are ambiguous",
    ]

    return {
        "preview_id": f"self_check_{audit.get('detected_behavior', 'unknown')}",
        "raw_command": command,
        "root_flow_audit": audit,
        "checks_run": [
            {"id": check_id, **SELF_CHECK_REGISTRY[check_id], "real_check_executed": False}
            for check_id in checks_run
        ],
        "possible_findings": possible_findings,
        "confidence_score": _confidence_score(audit, checks_run),
        "codex_required": codex_required,
        "lux_can_handle": lux_can_handle,
        "codex_recommended_for": codex_recommended_for,
        "read_only": True,
        "real_check_executed": False,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "real_fix_performed": False,
        "safety_note": "Self-check preview only. No shell command, file write, git write, deploy, or fix is performed.",
    }
