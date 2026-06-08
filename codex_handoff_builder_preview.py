from __future__ import annotations

from typing import Any, Dict, List, Optional

from root_flow_auditor_preview import ROOT_FLOW_BEHAVIOR_OWNERS, build_root_flow_audit
from safe_self_check_runner_preview import SELF_CHECK_REGISTRY, build_self_check_preview


HANDOFF_REGISTRY: Dict[str, Dict[str, Any]] = {
    "bug_intake": {
        "description": "Normalize a user-reported behavior into a narrow technical bug intake.",
        "fields": ["behavior", "symptom", "expected_result", "actual_result"],
    },
    "root_flow_audit": {
        "description": "Use Root Flow Auditor to identify owner, root-cause candidates, files, risk, and scenarios.",
        "source": "Layer 23.1 Root Flow Auditor",
    },
    "safe_self_check": {
        "description": "Use Safe Self Check Runner to plan read-only checks and smoke/manual gaps.",
        "source": "Layer 23.2 Safe Self Check Runner",
    },
    "codex_handoff": {
        "description": "Build a focused Codex task package without applying fixes or touching files.",
        "fields": [
            "behavior",
            "symptom",
            "possible_root_causes",
            "recommended_files",
            "recommended_checks",
            "manual_scenarios",
            "codex_task_summary",
            "confidence_score",
            "risk_level",
        ],
    },
}


TASK_SUMMARY_TEMPLATES: Dict[str, str] = {
    "stop_continue": "Unify resume handling into a single ARM continuation flow and verify multiple stop/continue cycles.",
    "workspace_export": "Verify export ownership and keep command/AI-note blocks out of clean export previews.",
    "visual_scene": "Verify Scene Lock continuity so new details preserve locked elements without rebuilding the scene.",
    "luxway_action": "Verify Luxway permission and confirmation boundaries for risky phone/app/mail/message actions.",
    "model_routing": "Verify router hints stay preview-only and do not switch providers or log raw user text.",
    "memory_retrieval": "Verify safe memory retrieval returns only derived summaries and blocks raw sensitive memory.",
    "endpoint_regression": "Verify endpoint ownership, route existence, and smoke coverage for the reported regression.",
    "ui_regression": "Verify UI behavior ownership and inspect frontend-only branches without touching unrelated flows.",
}


def _unique(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _safe_flags() -> Dict[str, Any]:
    return {
        "read_only": True,
        "file_write": False,
        "memory_write": False,
        "db_write": False,
        "git_write": False,
        "commit": False,
        "push": False,
        "deploy": False,
        "auto_fix": False,
        "patch_applied": False,
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
    }


def codex_handoff_status() -> Dict[str, Any]:
    return {
        "layer": "23.3",
        "name": "Codex Handoff Builder Preview",
        "status": "scaffold_ready",
        "root_flow_auditor_connected": True,
        "safe_self_check_connected": True,
        "available_endpoints": [
            "/debug/codex-handoff-status",
            "/debug/codex-handoff-registry",
            "/debug/codex-handoff-preview",
        ],
        "handoff_flow": [
            "Bug Intake",
            "Root Flow Audit",
            "Safe Self Check",
            "Codex Handoff Builder",
        ],
        "safety_note": "Preview only. Builds a Codex task package without file, git, deploy, memory, db, or auto-fix actions.",
        **_safe_flags(),
    }


def codex_handoff_registry() -> Dict[str, Any]:
    return {
        "layer": "23.3",
        "status": "registry_ready",
        "registry": HANDOFF_REGISTRY,
        "bug_intake_fields": ["behavior", "symptom", "expected_result", "actual_result"],
        "handoff_fields": HANDOFF_REGISTRY["codex_handoff"]["fields"],
        "supported_behaviors": list(ROOT_FLOW_BEHAVIOR_OWNERS.keys()),
        "supported_self_checks": list(SELF_CHECK_REGISTRY.keys()),
        "credit_saver_fields": ["lux_can_handle", "codex_needed_for"],
        **_safe_flags(),
    }


def _combined_command(
    behavior: Optional[str],
    symptom: str,
    expected_result: str,
    actual_result: str,
    command: str,
) -> str:
    parts = [behavior or "", symptom or "", actual_result or "", expected_result or "", command or ""]
    return " ".join(part.strip() for part in parts if part and part.strip())


def _recommended_checks(self_check: Dict[str, Any]) -> List[str]:
    return _unique([str(item.get("id", "")) for item in self_check.get("checks_run", []) if isinstance(item, dict)])


def _root_cause_ids(audit: Dict[str, Any]) -> List[str]:
    return _unique([str(item.get("id", "")) for item in audit.get("possible_root_causes", []) if isinstance(item, dict)])


def _confidence_score(audit: Dict[str, Any], self_check: Dict[str, Any]) -> float:
    audit_score = float(audit.get("confidence_score", 0.4) or 0.4)
    check_score = float(self_check.get("confidence_score", audit_score) or audit_score)
    return round(min(0.96, (audit_score + check_score) / 2), 2)


def _codex_needed_for(behavior_id: str, self_check: Dict[str, Any]) -> List[str]:
    items = list(self_check.get("codex_recommended_for", []))
    behavior_specific = {
        "stop_continue": ["stream/ARM implementation inspection", "core continuation logic modification if needed"],
        "workspace_export": ["export helper modification if preview invariants fail"],
        "visual_scene": ["scene state logic modification if continuity fails"],
        "luxway_action": ["permission boundary logic modification if risky actions are not blocked"],
        "model_routing": ["router implementation modification if real switching/logging appears"],
        "memory_retrieval": ["memory retrieval guard modification if raw sensitive context can leak"],
    }
    items.extend(behavior_specific.get(behavior_id, ["code inspection", "targeted implementation change if checks confirm the bug"]))
    return _unique(items)


def _codex_task_summary(behavior_id: str, symptom: str, expected_result: str) -> str:
    template = TASK_SUMMARY_TEMPLATES.get(behavior_id, TASK_SUMMARY_TEMPLATES["endpoint_regression"])
    details: List[str] = []
    if symptom:
        details.append(f"Symptom: {symptom.strip()}")
    if expected_result:
        details.append(f"Expected: {expected_result.strip()}")
    if details:
        return f"{template} {' '.join(details)}"
    return template


def build_codex_handoff_preview(
    behavior: Optional[str] = None,
    symptom: str = "",
    expected_result: str = "",
    actual_result: str = "",
    command: str = "",
    requested_checks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    combined_command = _combined_command(behavior, symptom, expected_result, actual_result, command)
    audit = build_root_flow_audit(
        command=combined_command,
        behavior=behavior,
        observed_behavior=actual_result or symptom,
        expected_behavior=expected_result,
        smoke_tests=[],
    )
    behavior_id = str(audit.get("detected_behavior", behavior or "endpoint_regression"))
    self_check = build_self_check_preview(
        command=combined_command,
        behavior=behavior_id,
        observed_behavior=actual_result or symptom,
        expected_behavior=expected_result,
        requested_checks=requested_checks,
    )
    normalized_symptom = symptom or actual_result or command or "No explicit symptom provided."
    lux_can_handle = _unique(
        list(self_check.get("lux_can_handle", []))
        + [
            "bug intake normalization",
            "root-cause preview",
            "smoke gap detection",
            "handoff package drafting",
        ]
    )

    return {
        "handoff_id": f"codex_handoff_{behavior_id}",
        "bug_intake": {
            "behavior": behavior or behavior_id,
            "symptom": symptom,
            "expected_result": expected_result,
            "actual_result": actual_result,
        },
        "root_flow_audit": audit,
        "safe_self_check": self_check,
        "behavior": behavior_id,
        "symptom": normalized_symptom,
        "possible_root_causes": _root_cause_ids(audit),
        "recommended_files": audit.get("recommended_files", []),
        "recommended_checks": _recommended_checks(self_check),
        "manual_scenarios": audit.get("manual_tests", []),
        "codex_task_summary": _codex_task_summary(behavior_id, normalized_symptom, expected_result),
        "confidence_score": _confidence_score(audit, self_check),
        "risk_level": audit.get("risk_level", "low"),
        "lux_can_handle": lux_can_handle,
        "codex_needed_for": _codex_needed_for(behavior_id, self_check),
        "safety_note": "Handoff preview only. No fix, patch, commit, push, deploy, file write, memory write, or db write is performed.",
        **_safe_flags(),
    }
