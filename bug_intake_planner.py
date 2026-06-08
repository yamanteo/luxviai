from __future__ import annotations

from typing import Any, Dict, List, Optional

from root_flow_auditor_preview import build_root_flow_audit
from safe_self_check_runner_preview import ROOT_CAUSE_TO_CHECKS, build_self_check_preview


BUG_CATEGORIES = [
    "stop_continue",
    "stream",
    "websocket",
    "workspace",
    "visual",
    "luxway",
    "model_router",
    "memory",
    "endpoint",
    "ui",
    "permission_flow",
    "future_dev_agent",
]


SEVERITY_BY_BEHAVIOR = {
    "stop_continue": "high",
    "stream": "high",
    "websocket": "high",
    "luxway": "medium",
    "permission_flow": "high",
    "model_router": "medium",
    "memory": "medium",
    "workspace": "low",
    "visual": "low",
    "endpoint": "medium",
    "ui": "low",
    "future_dev_agent": "low",
}


INVESTIGATION_PRIORITY_BY_SEVERITY = {
    "high": "p1",
    "medium": "p2",
    "low": "p3",
}


def _unique(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def bug_intake_status() -> Dict[str, Any]:
    return {
        "layer": "23.4",
        "name": "Bug Intake Investigation Planner Preview",
        "status": "scaffold_ready",
        "read_only": True,
        "analysis_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "root_flow_auditor_connected": True,
        "self_check_connected": True,
        "handoff_connected": True,
        "available_endpoints": [
            "/debug/bug-intake-status",
            "/debug/bug-intake-registry",
            "/debug/bug-intake-preview",
        ],
        "bug_categories": BUG_CATEGORIES,
        "safety_note": (
            "Read-only preview only. No fix, patch, file write, git write, "
            "commit, push, deploy, memory write, or db write."
        ),
    }


def bug_intake_registry() -> Dict[str, Any]:
    return {
        "layer": "23.4",
        "status": "registry_ready",
        "read_only": True,
        "categories": [
            {
                "id": category_id,
                "description": "Bug category for shared investigation planner.",
                "requires_state_intent": category_id in {"stop_continue", "stream", "websocket", "luxway"},
                "supported_by": [
                    "/debug/root-flow-audit",
                    "/debug/self-check-preview",
                    "/debug/codex-handoff-preview",
                ],
            }
            for category_id in BUG_CATEGORIES
        ],
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "git_write": False,
            "commit": False,
            "push": False,
            "deploy": False,
            "auto_fix": False,
        },
    }


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").split()).strip().lower()


def _severity_for(behavior: str, combined_text: str) -> str:
    base = SEVERITY_BY_BEHAVIOR.get(behavior, "low")
    if base == "low":
        if any(word in combined_text for word in ("crash", "kayboldu", "durdur", "continue", "devam", "yuklenme", "tekrari")):
            return "medium"
    if base == "medium":
        if any(word in combined_text for word in ("veri kaybi", "token", "kesilme", "stream", "websocket")):
            return "high"
    return base


def build_bug_intake_preview(
    behavior: Optional[str] = None,
    symptom: str = "",
    expected_result: str = "",
    actual_result: str = "",
    command: str = "",
) -> Dict[str, Any]:
    combined = _normalize(" ".join([command or "", symptom or "", expected_result or "", actual_result or ""]))
    base_audit = build_root_flow_audit(
        command=" ".join(part for part in [command, symptom, actual_result, expected_result] if part),
        behavior=behavior,
        observed_behavior=actual_result,
        expected_behavior=expected_result,
        smoke_tests=[],
    )
    detected_behavior = base_audit.get("detected_behavior", "endpoint_regression")
    severity = _severity_for(str(detected_behavior), combined)
    confidence = float(base_audit.get("confidence_score", 0.5) or 0.5)

    recommended_self_checks: List[str] = []
    for cause in base_audit.get("possible_root_causes", []):
        cause_id = str(cause.get("id", "")).strip()
        recommended_self_checks.extend(ROOT_CAUSE_TO_CHECKS.get(cause_id, []))
    if not recommended_self_checks:
        recommended_self_checks = ["behavior_owner_check", "manual_scenario_check"]
    recommended_self_checks = _unique(recommended_self_checks)

    self_check = build_self_check_preview(
        command=combined,
        behavior=str(detected_behavior),
        observed_behavior=actual_result,
        expected_behavior=expected_result,
        requested_checks=recommended_self_checks,
    )
    manual_scenarios: List[str] = []
    for item in base_audit.get("manual_tests", []):
        if isinstance(item, dict):
            manual_scenarios.append(str(item.get("name", "")))
    if not manual_scenarios:
        manual_scenarios = ["generic regression check", "resurrect baseline state and re-test"]

    return {
        "bug_intake_id": f"bug_intake_{detected_behavior}",
        "raw_command": command,
        "behavior": behavior or detected_behavior,
        "detected_behavior": detected_behavior,
        "symptom": symptom,
        "expected_result": expected_result,
        "actual_result": actual_result,
        "severity": severity,
        "investigation_priority": INVESTIGATION_PRIORITY_BY_SEVERITY.get(severity, "p3"),
        "recommended_audit": ["root_flow_audit"],
        "recommended_self_checks": recommended_self_checks,
        "recommended_manual_scenarios": manual_scenarios,
        "recommended_files": base_audit.get("recommended_files", []),
        "confidence_score": round(min(0.98, confidence + (0.02 * len(recommended_self_checks))), 2),
        "root_flow_audit": base_audit,
        "safe_self_check": self_check,
        "analysis_only": True,
        "read_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "safety_note": "Bug intake and investigation planning are preview-only; no execution changes happen here.",
    }

