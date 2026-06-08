from __future__ import annotations

from typing import Any, Dict, List, Optional

from bug_intake_planner import build_bug_intake_preview
from root_flow_auditor_preview import build_root_flow_audit
from safe_self_check_runner_preview import build_self_check_preview

INVESTIGATION_TASKS: List[str] = [
    "stop_continue",
    "workspace",
    "visual_scene",
    "luxway_action",
    "model_routing",
    "memory_retrieval",
    "stream",
    "endpoint",
    "ui",
]

TASK_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "goal": "Support multiple continue cycles without losing stop/resume position.",
        "current_findings": [
            "duplicate resume branch",
            "state_source_conflict",
        ],
        "suspected_causes": [
            "duplicate_branch",
            "stale_fallback",
        ],
        "completed_steps": ["branch_analysis", "state_check"],
        "remaining_steps": ["smoke_test", "manual_scenario", "owner_validation"],
        "do_not_touch": ["chat", "stream", "websocket", "typewriter"],
        "risk_level": "medium",
        "expected_result": "multiple continue cycles work after first resume.",
    },
    "workspace": {
        "goal": "Keep workspace parse/export continuation stable under interruptions.",
        "current_findings": [
            "incomplete stream handoff",
        ],
        "suspected_causes": [
            "state_source_conflict",
        ],
        "completed_steps": ["intent_state_check", "command_state_review"],
        "remaining_steps": ["documented smoke coverage", "manual section resume check"],
        "do_not_touch": ["chat", "stream", "typewriter"],
        "risk_level": "low",
        "expected_result": "document/section continuation resumes at exact cut position.",
    },
    "visual_scene": {
        "goal": "Preserve scene-lock continuity across partial responses.",
        "current_findings": [
            "snapshot rebuild warning",
        ],
        "suspected_causes": [
            "state_source_conflict",
            "event_leak",
        ],
        "completed_steps": ["scene_metadata_check", "lock_review"],
        "remaining_steps": ["smoke test for lock preservation"],
        "do_not_touch": ["chat", "stream", "websocket"],
        "risk_level": "low",
        "expected_result": "scene updates continue with lock-first strategy.",
    },
    "luxway_action": {
        "goal": "Keep permission boundary and action planning stable for repeat checks.",
        "current_findings": [
            "permission boundary drift",
        ],
        "suspected_causes": [
            "missing_helper",
        ],
        "completed_steps": ["permission_scope_check", "behavior_owner_alignment"],
        "remaining_steps": ["manual safety scenario", "readability check"],
        "do_not_touch": ["chat", "stream", "websocket"],
        "risk_level": "medium",
        "expected_result": "luxway actions remain blocked by preview by default.",
    },
    "model_routing": {
        "goal": "Verify route hints and fallback policy stability.",
        "current_findings": [
            "route confidence drift",
        ],
        "suspected_causes": [
            "missing_helper",
            "stale_fallback",
        ],
        "completed_steps": ["routing_signal_check", "fallback_review"],
        "remaining_steps": ["route owner validation", "smoke coverage update"],
        "do_not_touch": ["chat", "stream", "websocket", "typewriter"],
        "risk_level": "low",
        "expected_result": "routing diagnostics stay read-only and deterministic.",
    },
    "memory_retrieval": {
        "goal": "Prevent unsafe memory usage while preserving retrieval previews.",
        "current_findings": [
            "memory_source_inference",
        ],
        "suspected_causes": [
            "missing_helper",
        ],
        "completed_steps": ["memory_policy_check", "sensitivity_review"],
        "remaining_steps": ["safe manual scenario for raw signals", "registry update"],
        "do_not_touch": ["chat", "stream", "websocket", "typewriter"],
        "risk_level": "low",
        "expected_result": "no raw private memory is returned in preview.",
    },
}

FALLBACK_DEFAULT = {
    "goal": "Observe active investigation task with no runtime mutation.",
    "current_findings": ["analysis_ready"],
    "suspected_causes": ["state_source_conflict"],
    "completed_steps": ["initial_request_capture"],
    "remaining_steps": ["task_disambiguation", "manual_followup", "owner_validation"],
    "do_not_touch": ["chat", "stream", "websocket", "typewriter"],
    "risk_level": "medium",
    "expected_result": "new command maps to a deterministic investigation context.",
}


def investigation_context_status() -> Dict[str, Any]:
    return {
        "layer": "24.2",
        "name": "Active Investigation Context Preview",
        "status": "preview_ready",
        "read_only": True,
        "analysis_only": True,
        "active_task": "stop_continue",
        "current_status": "ready_for_investigation_context",
        "available_endpoints": [
            "/debug/investigation-context-status",
            "/debug/investigation-context-registry",
            "/debug/investigation-context-preview",
        ],
        "connected_layer23_endpoints": [
            "/debug/root-flow-auditor-status",
            "/debug/self-check-status",
            "/debug/intelligence-status",
            "/debug/bug-intake-status",
        ],
        "connected_layer24_endpoints": [
            "/debug/fault-report-status",
            "/debug/fault-report-intelligence-preview",
        ],
        "real_write_performed": False,
        "real_file_write_performed": False,
        "real_db_write_performed": False,
        "real_memory_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "safety_note": (
            "Preview-only investigative context. No file write, memory write, db write, "
            "chat/stream/typewriter code changes."
        ),
    }


def investigation_context_registry() -> Dict[str, Any]:
    entries = []
    for task_id in INVESTIGATION_TASKS:
        context = TASK_DEFAULTS.get(task_id, FALLBACK_DEFAULT).copy()
        entries.append(
            {
                "id": task_id,
                "active_task": task_id,
                "goal": context["goal"],
                "risk_level": context["risk_level"],
                "default_completed_steps": context["completed_steps"],
                "default_remaining_steps": context["remaining_steps"],
                "do_not_touch": context["do_not_touch"],
                "read_only": True,
            }
        )

    return {
        "layer": "24.2",
        "status": "registry_ready",
        "read_only": True,
        "analysis_only": True,
        "task_count": len(entries),
        "tasks": entries,
        "recommended_checks": [
            "root_flow_audit",
            "self_check_preview",
            "bug_intake_preview",
            "codex_handoff_preview",
            "credit_saver_preview",
            "intelligence_preview",
        ],
        "can_modify_code": False,
        "can_auto_fix": False,
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
    return " ".join((value or "").strip().lower().split())


def _infer_task(active_task: str, command: str) -> str:
    if active_task and active_task in INVESTIGATION_TASKS:
        return active_task

    normalized = _normalize(command)
    if not normalized:
        return "stop_continue"
    if any(token in normalized for token in ("dur", "devam", "continue", "resume")):
        return "stop_continue"
    if any(token in normalized for token in ("workspace", "cv", "rapor", "sunum", "belge", "dokuman", "document")):
        return "workspace"
    if any(token in normalized for token in ("rüya", "dream", "sahne", "scene")):
        return "visual_scene"
    if any(token in normalized for token in ("luxway", "telefon", "mail", "mesaj", "uygulama")):
        return "luxway_action"
    if any(token in normalized for token in ("routing", "model", "router", "görüntü", "image", "gorsel")):
        return "model_routing"
    if any(token in normalized for token in ("hafi", "hafiza", "memory", "geçmiş", "hatıra", "recall")):
        return "memory_retrieval"
    if any(token in normalized for token in ("websocket", "ws", "stream")):
        return "stream"
    return "stop_continue"


def build_investigation_context_preview(
    active_task: Optional[str] = None,
    goal: Optional[str] = None,
    completed_steps: Optional[List[str]] = None,
    remaining_steps: Optional[List[str]] = None,
    do_not_touch: Optional[List[str]] = None,
    expected_result: str = "",
    command: str = "",
    risk_level: Optional[str] = None,
    command_behavior: Optional[str] = None,
) -> Dict[str, Any]:
    task = _infer_task(active_task or "", command)
    base = TASK_DEFAULTS.get(task, FALLBACK_DEFAULT).copy()

    resolved_goal = goal or base["goal"]
    resolved_expected = expected_result or base["expected_result"]
    resolved_risk = risk_level or base["risk_level"]
    resolved_completed = completed_steps[:] if completed_steps else list(base["completed_steps"])
    resolved_remaining = remaining_steps[:] if remaining_steps else list(base["remaining_steps"])
    resolved_do_not_touch = do_not_touch[:] if do_not_touch else list(base["do_not_touch"])

    root_flow = build_root_flow_audit(
        command=" ".join(part for part in [command, resolved_goal, resolved_expected] if part),
        behavior=command_behavior or task,
        observed_behavior="interrupted response context",
        expected_behavior=resolved_expected,
        smoke_tests=[],
    )
    detected_behavior = str(root_flow.get("detected_behavior", task))
    possible_causes = [str(item.get("id")) for item in root_flow.get("possible_root_causes", []) if isinstance(item, dict)] or base["suspected_causes"]
    confidence = float(root_flow.get("confidence_score", 0.55))
    self_check = build_self_check_preview(
        command=" ".join(part for part in [command, resolved_goal] if part),
        behavior=detected_behavior,
        observed_behavior="interruption preview context",
        expected_behavior=resolved_expected,
        requested_checks=[],
    )
    bug_intake = build_bug_intake_preview(
        behavior=detected_behavior,
        symptom="interruption context mismatch",
        expected_result=resolved_expected,
        actual_result="preview context incomplete",
        command=" ".join(part for part in [task, command, resolved_goal] if part),
    )

    return {
        "active_task": task,
        "goal": resolved_goal,
        "current_findings": list(
            dict.fromkeys(
                [str(item) for item in (
                    base["current_findings"]
                    + root_flow.get("manual_tests", [])
                    if isinstance(root_flow.get("manual_tests"), list)
                    else base["current_findings"]
                )]
            )
        ),
        "suspected_causes": list(dict.fromkeys([str(item) for item in possible_causes])),
        "risk_level": resolved_risk,
        "completed_steps": resolved_completed,
        "remaining_steps": resolved_remaining,
        "do_not_touch": resolved_do_not_touch,
        "recommended_next_step": "resume_owner_validation",
        "expected_result": resolved_expected,
        "confidence_score": round(min(0.99, confidence), 2),
        "read_only": True,
        "analysis_only": True,
        "behavior_owner": root_flow.get("behavior_owner"),
        "anomaly": {
            "detected": bool(root_flow.get("possible_root_causes")),
            "possible_causes": possible_causes[:3],
        },
        "suggested_checks": self_check.get("checks_run", []),
        "raw_command": command,
        "safe_next_step": (
            "Run root flow audit -> self check preview -> manual regression for resume state."
        ),
        "real_action_performed": False,
        "real_file_write_performed": False,
        "real_memory_write_performed": False,
        "real_db_write_performed": False,
        "analysis_summary": {
            "root_flow": root_flow,
            "self_check": self_check,
            "bug_intake": {
                "severity": bug_intake.get("severity"),
                "investigation_priority": bug_intake.get("investigation_priority"),
            },
            "manual_tests": [item.get("name") for item in root_flow.get("manual_tests", []) if isinstance(item, dict)],
        },
        "connected_layer23": [
            "/debug/root-flow-audit",
            "/debug/self-check-preview",
            "/debug/bug-intake-preview",
            "/debug/intelligence-preview",
        ],
        "connected_layer24": [
            "/debug/fault-report-intelligence-preview",
            "/debug/bug-intake-status",
            "/debug/intelligence-status",
        ],
        "safety_note": (
            "Active context stays in memory as debug payload only and does not request or write source state."
        ),
    }
