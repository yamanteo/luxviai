from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


ROOT_FLOW_BEHAVIOR_OWNERS: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "owner": "Lux ARM",
        "scope": "stop / continue / resume / interrupted answer state",
        "primary_files": ["app.py", "static/index.html", "scripts/smoke_check.py"],
        "expected_invariants": [
            "one active answer state owns continuation",
            "late stream/fallback output is ignored after stop",
            "resume continues from visible state without restarting",
        ],
    },
    "workspace_export": {
        "owner": "Export Core",
        "scope": "workspace export/copy/send preview boundaries",
        "primary_files": ["workspace_export_preview.py", "workspace_scaffold.py", "app.py"],
        "expected_invariants": [
            "command blocks never enter clean export",
            "real export remains disabled in preview",
        ],
    },
    "visual_scene": {
        "owner": "Scene Lock",
        "scope": "dream scene continuity and locked visual elements",
        "primary_files": ["visual_scene_lock.py", "visual_dream_scene_state.py", "visual_prompt_builder.py"],
        "expected_invariants": [
            "new details do not rebuild the scene",
            "locked elements remain preserved",
        ],
    },
    "luxway_action": {
        "owner": "Permission Boundary",
        "scope": "phone/app/message/mail/calendar actions",
        "primary_files": ["luxway_device_safety.py", "luxway_permission_model.py", "luxway_capabilities.py"],
        "expected_invariants": [
            "risky actions require confirmation",
            "real phone/platform access stays disabled in scaffold",
        ],
    },
    "model_routing": {
        "owner": "Router Core",
        "scope": "model route hints and cost/privacy routing",
        "primary_files": ["model_router_config.py", "routing_simulation.py", "cost_privacy_policy.py"],
        "expected_invariants": [
            "routing preview never switches real providers",
            "raw user text is not logged for cost/router metadata",
        ],
    },
    "memory_retrieval": {
        "owner": "Safe Memory Retrieval",
        "scope": "safe memory retrieval previews",
        "primary_files": ["safe_memory_retrieval.py", "multimodal_memory_scaffold.py", "app.py"],
        "expected_invariants": [
            "raw sensitive memory is not returned",
            "memory read/write is not performed in preview",
        ],
    },
    "endpoint_regression": {
        "owner": "Endpoint Coverage Matrix",
        "scope": "status/smoke/endpoint regression coverage",
        "primary_files": ["endpoint_coverage_matrix.py", "scripts/smoke_check.py", "app.py"],
        "expected_invariants": [
            "status endpoints remain read-only",
            "smoke coverage identifies manual gaps",
        ],
    },
    "ui_regression": {
        "owner": "Debug Panel / UI Shell",
        "scope": "debug panel and app shell previews",
        "primary_files": ["app.py", "static/index.html", "scripts/smoke_check.py"],
        "expected_invariants": [
            "debug panel remains read-only",
            "main chat UI is not modified by debug-only previews",
        ],
    },
}


ROOT_CAUSE_SIGNALS: Dict[str, Dict[str, Any]] = {
    "duplicate_branch": {
        "keywords": ["duplicate", "two branches", "iki branch", "iki yol", "restart", "baştan", "bastan"],
        "reason": "Multiple code paths may own the same behavior.",
    },
    "stale_fallback": {
        "keywords": ["fallback", "late final", "late response", "block", "bulk", "sonradan", "blok"],
        "reason": "An old fallback/final path may still append output after the intended owner stopped.",
    },
    "missing_helper": {
        "keywords": ["missing helper", "helper yok", "not found", "import error", "module"],
        "reason": "A helper/module dependency may be absent or not wired into the target flow.",
    },
    "undefined_variable": {
        "keywords": ["undefined", "not defined", "referenceerror", "nameerror", "active_prompt", "variable"],
        "reason": "A variable reference may exist outside the scope where it is defined.",
    },
    "state_source_conflict": {
        "keywords": ["state", "context", "visible", "history", "arm", "hafıza", "hafiza", "resume"],
        "reason": "Two state sources may disagree about what the user sees or what should continue.",
    },
    "duplicate_owner": {
        "keywords": ["owner", "sahip", "kim yönetiyor", "ownership", "same behavior"],
        "reason": "A behavior may not have a single authoritative owner.",
    },
    "event_leak": {
        "keywords": ["event leak", "late chunk", "ws", "websocket", "stream", "abort", "stop", "durdur"],
        "reason": "A late stream/event/fetch response may bypass cancellation guards.",
    },
    "incomplete_test_coverage": {
        "keywords": ["test yok", "coverage", "smoke", "manual only", "regression", "tekrar"],
        "reason": "The bug may be recurring because smoke/manual coverage does not cover the exact behavior.",
    },
}


SMOKE_COVERAGE_HINTS: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "covered_by": ["frontend_resume_scaffold", "ws_stream_schema_in_process", "auto_continuation"],
        "manual_gap": "manual stop at item 3 then resume through item 10",
    },
    "workspace_export": {
        "covered_by": ["workspace_schema_preview"],
        "manual_gap": "copy/pdf preview with command blocks excluded",
    },
    "visual_scene": {
        "covered_by": ["visual_style_registry_preview"],
        "manual_gap": "scene lock with existing subject/object and new detail",
    },
    "luxway_action": {
        "covered_by": ["luxway_device_safety_preview", "luxway_permission_model_preview"],
        "manual_gap": "send/delete/call actions remain blocked",
    },
    "model_routing": {
        "covered_by": ["model_router_config_preview", "routing_simulation_preview"],
        "manual_gap": "real provider switch remains false",
    },
    "memory_retrieval": {
        "covered_by": ["safe_memory_retrieval_preview"],
        "manual_gap": "private/sensitive retrieval never returns raw memory",
    },
    "endpoint_regression": {
        "covered_by": ["endpoint_coverage_matrix_preview"],
        "manual_gap": "live status endpoint sweep after deploy",
    },
    "ui_regression": {
        "covered_by": ["debug_agent_panel"],
        "manual_gap": "browser/mobile UI inspection",
    },
}


MANUAL_SCENARIOS: Dict[str, List[Dict[str, Any]]] = {
    "stop_continue": [
        {
            "name": "10 item list stop/resume",
            "steps": [
                "ask for a numbered 10 item list",
                "stop while item 3 is partially visible",
                "press/ask continue",
            ],
            "expected_result": [
                "item 3 is completed",
                "items 4-10 continue in numbered list format",
                "items 1-2 are not repeated",
                "no final bulk block is injected",
            ],
        }
    ],
    "workspace_export": [
        {
            "name": "clean export excludes commands",
            "steps": ["create workspace preview", "request export preview"],
            "expected_result": ["command/voice/ai_note excluded", "file_written false", "export_performed false"],
        }
    ],
    "visual_scene": [
        {
            "name": "scene lock detail add",
            "steps": ["create dream scene preview", "add one new detail through scene lock"],
            "expected_result": ["scene_rebuild_required false", "locked_elements preserved"],
        }
    ],
    "luxway_action": [
        {
            "name": "risky phone action blocked",
            "steps": ["preview send/delete/call command"],
            "expected_result": ["requires_confirmation true", "action_performed false", "real_access_enabled false"],
        }
    ],
}


DEFAULT_MANUAL_SCENARIO = {
    "name": "generic regression check",
    "steps": ["reproduce the behavior", "identify the owner", "verify expected invariant", "run matching smoke/manual check"],
    "expected_result": ["behavior remains read-only in preview", "no unrelated flow is modified"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _detect_behavior(command: str, behavior: Optional[str] = None) -> str:
    requested = _normalize(behavior or "")
    if requested in ROOT_FLOW_BEHAVIOR_OWNERS:
        return requested

    text = _normalize(command)
    if any(word in text for word in ["stop", "durdur", "continue", "devam", "resume", "arm", "stream", "websocket"]):
        return "stop_continue"
    if any(word in text for word in ["export", "pdf", "word", "copy", "workspace", "rapor"]):
        return "workspace_export"
    if any(word in text for word in ["scene", "sahne", "dream", "rüya", "ruya", "visual", "ambrosia", "görsel", "gorsel"]):
        return "visual_scene"
    if any(word in text for word in ["luxway", "phone", "telefon", "mesaj", "mail", "calendar", "takvim", "sil", "ara"]):
        return "luxway_action"
    if any(word in text for word in ["model", "router", "routing", "deepseek", "gpt", "mini"]):
        return "model_routing"
    if any(word in text for word in ["memory", "hafıza", "hafiza", "retrieval", "hatırla", "hatirla"]):
        return "memory_retrieval"
    if any(word in text for word in ["endpoint", "api", "status", "smoke", "regression"]):
        return "endpoint_regression"
    if any(word in text for word in ["ui", "mobile", "panel", "button", "buton", "frontend"]):
        return "ui_regression"
    return "endpoint_regression"


def _detect_root_causes(command: str, behavior_id: str) -> List[Dict[str, str]]:
    text = _normalize(command)
    causes: List[Dict[str, str]] = []
    for cause_id, spec in ROOT_CAUSE_SIGNALS.items():
        if any(keyword in text for keyword in spec["keywords"]):
            causes.append({"id": cause_id, "reason": spec["reason"]})

    owner_defaults = {
        "stop_continue": ["state_source_conflict", "event_leak", "stale_fallback", "incomplete_test_coverage"],
        "workspace_export": ["duplicate_owner", "incomplete_test_coverage"],
        "visual_scene": ["state_source_conflict", "duplicate_owner", "incomplete_test_coverage"],
        "luxway_action": ["duplicate_owner", "state_source_conflict", "incomplete_test_coverage"],
        "model_routing": ["duplicate_branch", "stale_fallback", "incomplete_test_coverage"],
        "memory_retrieval": ["state_source_conflict", "duplicate_owner", "incomplete_test_coverage"],
        "endpoint_regression": ["missing_helper", "incomplete_test_coverage"],
        "ui_regression": ["duplicate_branch", "event_leak", "incomplete_test_coverage"],
    }
    existing = {item["id"] for item in causes}
    for cause_id in owner_defaults.get(behavior_id, ["incomplete_test_coverage"]):
        if cause_id not in existing:
            spec = ROOT_CAUSE_SIGNALS[cause_id]
            causes.append({"id": cause_id, "reason": spec["reason"]})
            existing.add(cause_id)
    return causes


def _risk_level(command: str, behavior_id: str) -> str:
    text = _normalize(command)
    if behavior_id == "stop_continue" or any(word in text for word in ["stream", "websocket", "late", "bulk", "deploy"]):
        return "high"
    if behavior_id in {"luxway_action", "memory_retrieval", "model_routing"}:
        return "medium"
    return "low"


def _confidence_score(command: str, behavior_id: str, causes: List[Dict[str, str]]) -> float:
    text = _normalize(command)
    score = 0.45
    if behavior_id in ROOT_FLOW_BEHAVIOR_OWNERS:
        score += 0.2
    if len(text) > 30:
        score += 0.1
    if causes:
        score += min(0.2, len(causes) * 0.04)
    return round(min(score, 0.92), 2)


def root_flow_auditor_status() -> Dict[str, Any]:
    return {
        "layer": "23.1",
        "name": "Root Flow Auditor Preview",
        "status": "scaffold_ready",
        "read_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "behavior_owners": ROOT_FLOW_BEHAVIOR_OWNERS,
        "root_cause_categories": list(ROOT_CAUSE_SIGNALS.keys()),
        "available_endpoints": [
            "/debug/root-flow-auditor-status",
            "/debug/root-flow-audit",
            "/debug/codex-fix-plan",
        ],
        "safety_note": "Preview only. Produces analysis and technical plans without changing code, files, git, memory, db, or deploy state.",
    }


def build_root_flow_audit(
    command: str,
    behavior: Optional[str] = None,
    observed_behavior: Optional[str] = None,
    expected_behavior: Optional[str] = None,
    smoke_tests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    behavior_id = _detect_behavior(" ".join([command or "", observed_behavior or "", expected_behavior or ""]), behavior)
    owner = ROOT_FLOW_BEHAVIOR_OWNERS[behavior_id]
    causes = _detect_root_causes(" ".join([command or "", observed_behavior or "", expected_behavior or ""]), behavior_id)
    coverage = SMOKE_COVERAGE_HINTS.get(behavior_id, {"covered_by": [], "manual_gap": "manual reproduction required"})
    provided_tests = {str(item).strip() for item in (smoke_tests or []) if str(item).strip()}
    covered_by = list(coverage.get("covered_by", []))
    has_smoke_coverage = bool(set(covered_by) & provided_tests) if provided_tests else bool(covered_by)
    missing_smoke_coverage = [] if has_smoke_coverage else [coverage.get("manual_gap", "behavior-specific smoke coverage missing")]
    if coverage.get("manual_gap"):
        missing_smoke_coverage.append(coverage["manual_gap"])

    scenarios = MANUAL_SCENARIOS.get(behavior_id, [DEFAULT_MANUAL_SCENARIO])
    risk = _risk_level(command, behavior_id)
    confidence = _confidence_score(command, behavior_id, causes)

    return {
        "audit_id": f"root_flow_{behavior_id}",
        "raw_command": command,
        "detected_behavior": behavior_id,
        "behavior_owner": {
            "id": behavior_id,
            "owner": owner["owner"],
            "scope": owner["scope"],
            "expected_invariants": owner["expected_invariants"],
        },
        "possible_root_causes": causes,
        "recommended_files": owner["primary_files"],
        "manual_tests": scenarios,
        "smoke_gap_detector": {
            "question": "Bu davranışı doğrulayan smoke testi var mı?",
            "has_smoke_coverage": has_smoke_coverage,
            "known_smoke_checks": covered_by,
            "missing_smoke_coverage": missing_smoke_coverage,
        },
        "risk_level": risk,
        "confidence_score": confidence,
        "read_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "safety_note": "Analysis preview only; no code or repository mutation is performed.",
    }


def build_codex_fix_plan(
    command: str,
    behavior: Optional[str] = None,
    observed_behavior: Optional[str] = None,
    expected_behavior: Optional[str] = None,
    smoke_tests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    audit = build_root_flow_audit(
        command=command,
        behavior=behavior,
        observed_behavior=observed_behavior,
        expected_behavior=expected_behavior,
        smoke_tests=smoke_tests,
    )
    behavior_id = audit["detected_behavior"]
    causes = [item["id"] for item in audit["possible_root_causes"]]

    plan_steps: List[str] = [
        f"confirm behavior owner is {audit['behavior_owner']['owner']}",
        "inspect recommended files without changing unrelated flows",
    ]
    if "duplicate_branch" in causes:
        plan_steps.append("inspect duplicate behavior branches and remove/disable stale ownership only after tests")
    if "state_source_conflict" in causes:
        plan_steps.append("inspect authoritative state source and verify visible/generated state alignment")
    if "event_leak" in causes:
        plan_steps.append("inspect late stream/fetch/websocket event guards")
    if "stale_fallback" in causes:
        plan_steps.append("inspect fallback/final response paths for stale append behavior")
    if "undefined_variable" in causes:
        plan_steps.append("inspect scoped references such as active_prompt/active state variables")
    if "missing_helper" in causes:
        plan_steps.append("inspect imports/helpers and confirm smoke environment can import app")
    if "incomplete_test_coverage" in causes:
        plan_steps.append("add or extend smoke/manual scenario before applying a fix")

    if behavior_id == "stop_continue":
        plan_steps.extend([
            "run 10 item list stop_continue manual scenario",
            "verify item 3 completes and items 4-10 continue without repeating items 1-2",
        ])

    return {
        "plan_id": f"codex_fix_plan_{behavior_id}",
        "audit": audit,
        "technical_plan": plan_steps,
        "manual_scenario_plan": audit["manual_tests"],
        "recommended_files": audit["recommended_files"],
        "risk_level": audit["risk_level"],
        "confidence_score": audit["confidence_score"],
        "read_only": True,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "safety_note": "Plan builder only. Codex must still inspect code and run tests before any actual fix.",
    }
