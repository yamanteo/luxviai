from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from bug_intake_planner import build_bug_intake_preview
from codex_handoff_builder_preview import build_codex_handoff_preview
from root_flow_auditor_preview import build_root_flow_audit
from safe_self_check_runner_preview import build_self_check_preview

INTELLIGENCE_REPEATED_FAILURE_CATEGORIES: List[str] = [
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

INTELLIGENCE_ANOMALY_TYPES: List[str] = [
    "behavior_mismatch",
    "repeated_exception",
    "repeated_user_report",
    "smoke_failure",
    "route_regression",
    "endpoint_regression",
    "state_conflict",
    "duplicate_owner",
    "stale_fallback",
    "missing_helper",
    "undefined_variable",
]

ROOT_CAUSE_ANOMALY_MAP: Dict[str, str] = {
    "duplicate_branch": "duplicate_owner",
    "stale_fallback": "stale_fallback",
    "missing_helper": "missing_helper",
    "undefined_variable": "undefined_variable",
    "state_source_conflict": "state_conflict",
    "duplicate_owner": "duplicate_owner",
    "event_leak": "smoke_failure",
    "incomplete_test_coverage": "smoke_failure",
}

BEHAVIOR_ALIAS_MAP = {
    "workspace_export": "workspace",
    "visual_scene": "visual",
    "luxway_action": "permission_flow",
    "luxway": "luxway",
    "model_routing": "model_router",
    "memory_retrieval": "memory",
    "endpoint_regression": "endpoint",
    "ui_regression": "ui",
    "stop_continue": "stop_continue",
    "stream": "stream",
    "websocket": "websocket",
    "future_dev_agent": "future_dev_agent",
}

RISK_TO_PRIORITY = {"low": 0.35, "medium": 0.65, "high": 0.88, "critical": 0.95}


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _safe_unique(values: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _map_behavior(behavior_id: str, command: str) -> str:
    if behavior_id and behavior_id in BEHAVIOR_ALIAS_MAP:
        return BEHAVIOR_ALIAS_MAP[behavior_id]
    text = _normalize(" ".join([behavior_id or "", command or ""]))
    if "stream" in text or "durdur" in text or "devam" in text:
        return "stop_continue"
    if "websocket" in text or "ws" in text:
        return "websocket"
    if "workspace" in text or "doküman" in text or "cv" in text or "rapor" in text or "sunum" in text:
        return "workspace"
    if "luxway" in text or "telefon" in text or "mail" in text or "mesaj" in text:
        return "permission_flow"
    if "rüya" in text or "visual" in text or "sahne" in text or "ambrosia" in text:
        return "visual"
    if "memory" in text or "hafıza" in text:
        return "memory"
    if "model" in text or "router" in text or "routing" in text:
        return "model_router"
    if "endpoint" in text or "route" in text or "api" in text:
        return "endpoint"
    if "ui" in text or "buton" in text or "panel" in text:
        return "ui"
    return "future_dev_agent"


def _text_flags(command: str, symptom: str, expected_result: str, actual_result: str) -> Dict[str, bool]:
    text = _normalize(" ".join(part for part in [command, symptom, expected_result, actual_result] if part))
    repeated_failure = any(token in text for token in [
        "tekrar",
        "defa",
        "ikinci kez",
        "2. kez",
        "sadece bir kere",
        "yine",
        "tekrar et",
    ])
    repeated_exception = any(token in text for token in [
        "sadece bir kelime",
        "yarım kal",
        "kelime ort",
        "tek sefer",
        "bir kere çalış",
    ])
    repeated_user_report = any(token in text for token in [
        "sürekli",
        "tekrarlı",
        "hep",
        "aynı",
        "hep aynı",
        "durakladı",
    ])
    return {
        "repeated_failure": repeated_failure,
        "repeated_exception": repeated_exception,
        "repeated_user_report": repeated_user_report,
    }


def _derive_anomaly_types(audit: Dict[str, Any], text_flags: Dict[str, bool], behavior_id: str) -> List[str]:
    anomaly_types: List[str] = []
    for cause in audit.get("possible_root_causes", []) or []:
        if isinstance(cause, dict):
            mapped = ROOT_CAUSE_ANOMALY_MAP.get(str(cause.get("id", "")))
            if mapped:
                anomaly_types.append(mapped)

    if text_flags.get("repeated_exception"):
        anomaly_types.append("repeated_exception")
    if text_flags.get("repeated_user_report"):
        anomaly_types.append("repeated_user_report")
    if text_flags.get("repeated_failure"):
        anomaly_types.append("behavior_mismatch")

    if not anomaly_types and behavior_id in {"stream", "websocket"}:
        anomaly_types.append("state_conflict")
    if behavior_id in {"endpoint", "future_dev_agent"}:
        anomaly_types.append("endpoint_regression")
    if behavior_id == "model_router":
        anomaly_types.append("route_regression")
    if behavior_id == "stop_continue":
        anomaly_types.append("smoke_failure")

    return _safe_unique(anomaly_types)


def _recommended_next_step(behavior_id: str, anomaly_types: List[str], risk_level: str) -> str:
    if any(item in {"state_conflict", "stale_fallback", "event_leak"} for item in anomaly_types):
        return "run_root_flow_audit"
    if risk_level in {"high", "critical"}:
        return "run_self_check_and_manual_scenario"
    if behavior_id in {"endpoint", "stream", "websocket", "model_router"}:
        return "run_root_flow_audit"
    if "repeated_user_report" in anomaly_types:
        return "run_bug_intake_regression_cycle"
    return "review_root_flow_signal_path"


def _recommended_layer(risk_level: str, behavior_id: str) -> str:
    if risk_level in {"high", "critical"} and behavior_id in {"stop_continue", "stream", "websocket"}:
        return "root_flow_auditor"
    if behavior_id in {"endpoint", "ui", "workspace", "visual", "memory", "luxway", "permission_flow", "model_router"}:
        return "safe_self_check_runner"
    if risk_level == "high":
        return "codex_handoff_builder"
    return "bug_intake_planner"


def _priority_score(risk_level: str, anomaly_count: int) -> float:
    base = RISK_TO_PRIORITY.get(risk_level, 0.5)
    bonus = min(0.15, 0.03 * anomaly_count)
    return round(min(0.99, base + bonus), 2)


def intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "23.6",
        "name": "Debug Intelligence Core Preview",
        "status": "scaffold_ready",
        "read_only": True,
        "analysis_only": True,
        "completed_parts": [
            "root_flow_auditor",
            "safe_self_check_runner",
            "codex_handoff_builder",
            "bug_intake_investigation_planner",
            "credit_saver_engine",
            "debug_intelligence_core",
        ],
        "available_endpoints": [
            "/debug/intelligence-status",
            "/debug/intelligence-registry",
            "/debug/intelligence-preview",
        ],
        "repeated_failure_categories": INTELLIGENCE_REPEATED_FAILURE_CATEGORIES,
        "anomaly_types": INTELLIGENCE_ANOMALY_TYPES,
        "read_only_permitted": True,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "auto_fix_enabled": False,
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
        "safety_note": "Preview-only debug intelligence core. No state mutations, file writes, memory writes, db writes, or deploy changes.",
    }


def intelligence_registry() -> Dict[str, Any]:
    return {
        "layer": "23.6",
        "status": "registry_ready",
        "read_only": True,
        "analysis_only": True,
        "behavior_categories": INTELLIGENCE_REPEATED_FAILURE_CATEGORIES,
        "anomaly_types": INTELLIGENCE_ANOMALY_TYPES,
        "risk_levels": ["low", "medium", "high", "critical"],
        "connected_components": [
            "root_flow_auditor",
            "safe_self_check_runner",
            "codex_handoff_builder",
            "bug_intake_investigation_planner",
            "credit_saver_engine",
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
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "real_fix_performed": False,
    }


def build_intelligence_preview(
    behavior: Optional[str] = None,
    symptom: str = "",
    expected_result: str = "",
    actual_result: str = "",
    command: str = "",
) -> Dict[str, Any]:
    combined = _normalize(" ".join(part for part in [command, symptom, expected_result, actual_result] if part))
    raw_text = _normalize(" ".join([command or "", symptom or "", expected_result or "", actual_result or ""]))
    root_behavior = _map_behavior(behavior or "", raw_text)

    audit = build_root_flow_audit(
        command=combined,
        behavior=behavior,
        observed_behavior=actual_result,
        expected_behavior=expected_result,
        smoke_tests=[],
    )
    detected_behavior = _map_behavior(str(audit.get("detected_behavior", root_behavior)), combined)

    flags = _text_flags(command, symptom, expected_result, actual_result)
    anomaly_types = _derive_anomaly_types(audit, flags, detected_behavior)
    anomaly_detected = bool(anomaly_types)
    repeated_failure_detected = bool(flags.get("repeated_failure") or flags.get("repeated_exception"))
    risk_level = str(audit.get("risk_level", "low"))
    if not risk_level:
        risk_level = "low"
    confidence = float(audit.get("confidence_score", 0.45) or 0.45)
    recommended_checks = _safe_unique([str(item.get("id", "")) for item in build_self_check_preview(
        command=combined,
        behavior=detected_behavior,
        observed_behavior=actual_result or symptom,
        expected_behavior=expected_result,
        requested_checks=None,
    ).get("checks_run", []) if isinstance(item, dict)])

    bug = build_bug_intake_preview(
        behavior=detected_behavior,
        symptom=symptom,
        expected_result=expected_result,
        actual_result=actual_result,
        command=command,
    )
    handoff = build_codex_handoff_preview(
        behavior=detected_behavior,
        symptom=symptom,
        expected_result=expected_result,
        actual_result=actual_result,
        command=command,
        requested_checks=recommended_checks,
    )
    credit = None
    # not used in required fields directly, but helpful for confidence and triage consistency.
    _ = credit

    possible_root_causes = [item["id"] for item in audit.get("possible_root_causes", []) if isinstance(item, dict)]
    recommended_next_step = _recommended_next_step(detected_behavior, anomaly_types, risk_level)
    investigation_recommended = anomaly_detected or repeated_failure_detected or risk_level in {"medium", "high", "critical"}
    priority = _priority_score(risk_level, len(anomaly_types))

    return {
        "analysis_id": f"intelligence_{detected_behavior}",
        "behavior": detected_behavior,
        "raw_command": command,
        "anomaly_detected": anomaly_detected,
        "investigation_recommended": investigation_recommended,
        "repeated_failure_detected": repeated_failure_detected,
        "risk_level": risk_level,
        "confidence_score": round(confidence, 2),
        "priority_score": priority,
        "recommended_next_step": recommended_next_step,
        "recommended_layer": _recommended_layer(risk_level, detected_behavior),
        "possible_root_causes": _safe_unique(possible_root_causes),
        "recommended_files": audit.get("recommended_files", []),
        "recommended_checks": recommended_checks,
        "root_flow_audit": audit,
        "self_check_preview": build_self_check_preview(
            command=combined,
            behavior=detected_behavior,
            observed_behavior=actual_result or symptom,
            expected_behavior=expected_result,
            requested_checks=recommended_checks,
        ),
        "bug_intake_preview": bug,
        "codex_handoff_preview": handoff,
        "symptom": symptom,
        "expected_result": expected_result,
        "actual_result": actual_result,
        "read_only": True,
        "analysis_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "real_fix_performed": False,
        "auto_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only debug intelligence only. No code modification, deployment, or persistent writes are executed.",
    }
