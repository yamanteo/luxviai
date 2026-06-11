from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview, patch_draft_registry
from change_preview_engine_preview import build_change_preview, change_preview_registry
from diff_preview_engine_preview import build_diff_preview, diff_preview_registry
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


PATCH_RISK_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "affected_files": ["app.py"],
        "affected_layers": ["legacy_chat_runtime", "production_layer_20"],
        "affected_endpoints": ["/chat", "/ws/chat"],
        "risk_score": 42,
        "risk_level": "medium",
        "risk_reasons": ["duplicate resume_owner logic", "scattered validation", "runtime state drift"],
        "dependency_risk": "low",
        "runtime_risk": "high",
        "regression_risk": "medium",
        "boundary_risk": "medium",
        "verification_required": True,
        "recommended_tests": ["resume after stop via /chat", "websocket reconnect after stop", "double-stop guard"],
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "affected_files": ["app.py", "static/index.html"],
        "affected_layers": ["legacy_chat_runtime", "voice_audio_layer_17"],
        "affected_endpoints": ["/ws/chat", "/chat"],
        "risk_score": 68,
        "risk_level": "high",
        "risk_reasons": ["stream state drift", "typewriter queue ownership", "late done event", "tab boundary unclear"],
        "dependency_risk": "medium",
        "runtime_risk": "high",
        "regression_risk": "high",
        "boundary_risk": "high",
        "verification_required": True,
        "recommended_tests": ["manual tab switch", "long answer stream", "stop during stream", "done event after disconnect"],
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "affected_files": ["workspace_export_preview.py", "app.py"],
        "affected_layers": ["workspace_layer_15", "production_layer_20"],
        "affected_endpoints": ["/workspace/export-preview"],
        "risk_score": 35,
        "risk_level": "low",
        "risk_reasons": ["file write guard not enforced", "export schema drift", "future real file integration"],
        "dependency_risk": "low",
        "runtime_risk": "low",
        "regression_risk": "low",
        "boundary_risk": "medium",
        "verification_required": False,
        "recommended_tests": ["export format validation", "write guard assertion"],
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "affected_files": ["luxway_permission_model.py", "luxway_device_safety.py", "app.py"],
        "affected_layers": ["luxway_layer_18", "agent_layer_14"],
        "affected_endpoints": ["/luxway/permission-preview", "/luxway/device-safety-preview"],
        "risk_score": 55,
        "risk_level": "medium",
        "risk_reasons": ["private data boundary", "platform permission model variance", "real-access ambiguity"],
        "dependency_risk": "medium",
        "runtime_risk": "medium",
        "regression_risk": "medium",
        "boundary_risk": "high",
        "verification_required": True,
        "recommended_tests": ["Android permission flow", "iOS permission flow", "private data guard", "device action boundary"],
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "patch", "draft", "change", "diff", "risk"],
        "target_component": "preview_schema",
        "affected_files": ["patch_risk_matrix_preview.py", "app.py", "lux_fault_report.py", "scripts/smoke_check.py"],
        "affected_layers": ["development_layer_24", "dev_agent_layer_25", "multi_agent_layer_26", "patch_draft_layer_27"],
        "affected_endpoints": ["/debug/patch-draft-preview", "/debug/change-preview", "/debug/diff-preview", "/debug/fault-report-preview"],
        "risk_score": 25,
        "risk_level": "low",
        "risk_reasons": ["preview schema drift", "new layer integration", "smoke test coverage gap"],
        "dependency_risk": "low",
        "runtime_risk": "low",
        "regression_risk": "low",
        "boundary_risk": "low",
        "verification_required": False,
        "recommended_tests": ["status endpoint smoke", "registry smoke", "preview response shape"],
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in PATCH_RISK_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def patch_risk_status() -> Dict[str, Any]:
    return {
        "layer": "27.4",
        "name": "Patch Risk Matrix Preview",
        "status": "patch_risk_matrix_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "preview_only": True,
        "real_action_performed": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "git_write_enabled": False,
        "commit_enabled": False,
        "push_enabled": False,
        "deploy_enabled": False,
        "auto_fix_enabled": False,
        "patch_apply_enabled": False,
        "subprocess_execution_enabled": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": [
            "/debug/patch-risk-status",
            "/debug/patch-risk-registry",
            "/debug/patch-risk-preview",
        ],
        "connected_layers": [
            "27.1 Patch Draft Engine",
            "27.2 Change Preview Engine",
            "27.3 Diff Preview Engine",
            "26.7 Multi-Agent Coordinator",
            "26.6 Evidence Store",
            "25.5 Safe Patch Planner",
            "25.6 Verification Planner",
            "25.4 Safe Change Boundary",
        ],
        "safety_note": "Patch Risk Matrix only evaluates risk. It never writes files, stores memory, applies patches, runs subprocesses, commits, pushes, deploys, or changes runtime behavior.",
    }


def patch_risk_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for profile_id, profile in PATCH_RISK_PROFILES.items():
        boundary = build_change_boundary_preview(target_area=profile_id, command=profile_id, related_layer="Layer 27.4")
        items.append(
            {
                "id": profile_id,
                "target_component": profile["target_component"],
                "affected_files": list(profile["affected_files"]),
                "affected_layers": list(profile["affected_layers"]),
                "affected_endpoints": list(profile["affected_endpoints"]),
                "risk_score": profile["risk_score"],
                "risk_level": profile["risk_level"],
                "risk_reasons": list(profile["risk_reasons"]),
                "verification_required": profile["verification_required"],
                "approval_required": bool(boundary.get("user_approval_required")),
                "confidence_score": profile["confidence_score"],
            }
        )

    return {
        "layer": "27.4",
        "name": "Patch Risk Registry",
        "status": "patch_risk_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "risk_count": len(items),
        "risks": items,
        "risk_level_summary": {
            "high": sum(1 for item in items if item["risk_level"] == "high"),
            "medium": sum(1 for item in items if item["risk_level"] == "medium"),
            "low": sum(1 for item in items if item["risk_level"] == "low"),
        },
        "connected_endpoints": [
            "/debug/patch-draft-preview",
            "/debug/change-preview",
            "/debug/diff-preview",
            "/debug/coordinator-preview",
            "/debug/evidence-store-preview",
            "/debug/patch-planner-preview",
            "/debug/verification-planner-preview",
            "/debug/change-boundary-preview",
            "/debug/fault-report-preview",
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
            "patch_apply": False,
            "subprocess_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_patch_risk_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = PATCH_RISK_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    command_or_issue = command or detected_issue

    patch_draft = build_patch_draft_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    change_preview = build_change_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    diff_preview = build_diff_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    coordinator = build_coordinator_preview(
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    evidence = build_evidence_store_preview(
        finding=None,
        command=command_or_issue,
        project_area=project_area or detected_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    patch_planner = build_patch_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    verification_planner = build_verification_planner_preview(
        target_issue=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.4",
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command_or_issue,
        related_layer=related_layer or "Layer 27.4",
    )

    approval_required = bool(
        boundary.get("user_approval_required")
        or patch_draft.get("approval_required")
        or profile["risk_level"] in {"medium", "high"}
    )
    confidence_score = round(
        (
            float(profile["confidence_score"])
            + float(patch_draft.get("confidence_score", 0.0))
            + float(change_preview.get("confidence_score", 0.0))
            + float(diff_preview.get("confidence_score", 0.0))
            + float(coordinator.get("overall_confidence", 0.0))
            + float(evidence.get("confidence_score", 0.0))
        )
        / 6,
        2,
    )

    return {
        "target_issue": detected_issue,
        "target_component": profile["target_component"],
        "affected_files": _unique(
            list(profile["affected_files"])
            + list(patch_draft.get("recommended_files", []))[:2]
            + list(diff_preview.get("affected_files", []))[:2]
        ),
        "affected_layers": _unique(
            list(profile["affected_layers"])
            + [str(item) for item in change_preview.get("affected_areas", []) if "." not in str(item)][:2]
        ),
        "affected_endpoints": _unique(
            list(profile["affected_endpoints"])
            + list(coordinator.get("relevant_endpoints", []))[:2]
        ),
        "risk_score": profile["risk_score"],
        "risk_level": profile["risk_level"],
        "risk_reasons": _unique(
            list(profile["risk_reasons"])
            + list(evidence.get("risk_areas", []))[:1]
            + list(coordinator.get("combined_risks", []))[:1]
        ),
        "dependency_risk": profile["dependency_risk"],
        "runtime_risk": profile["runtime_risk"],
        "regression_risk": profile["regression_risk"],
        "boundary_risk": profile["boundary_risk"],
        "verification_required": profile["verification_required"],
        "recommended_tests": _unique(
            list(profile["recommended_tests"])
            + list(verification_planner.get("required_tests", []))[:2]
            + list(patch_planner.get("required_tests", []))[:2]
        ),
        "approval_required": approval_required,
        "confidence_score": confidence_score,
        "integration_signals": {
            "patch_draft": {
                "recommended_files": patch_draft.get("recommended_files", []),
                "draft_change_summary": patch_draft.get("draft_change_summary"),
                "draft_patch_steps": patch_draft.get("draft_patch_steps", []),
                "risk_assessment": patch_draft.get("risk_assessment"),
            },
            "change_preview": {
                "affected_areas": change_preview.get("affected_areas", []),
                "before_summary": change_preview.get("before_summary"),
                "after_summary": change_preview.get("after_summary"),
                "predicted_effects": change_preview.get("predicted_effects", []),
            },
            "diff_preview": {
                "affected_files": diff_preview.get("affected_files", []),
                "before_code_summary": diff_preview.get("before_code_summary"),
                "after_code_summary": diff_preview.get("after_code_summary"),
                "diff_hunks_expected": diff_preview.get("diff_hunks_expected"),
            },
            "multi_agent_coordinator": {
                "combined_findings": coordinator.get("combined_findings", []),
                "combined_risks": coordinator.get("combined_risks", []),
                "combined_recommendations": coordinator.get("combined_recommendations", []),
                "overall_confidence": coordinator.get("overall_confidence"),
            },
            "evidence_store": {
                "finding": evidence.get("finding"),
                "evidence_items": evidence.get("evidence_items", []),
                "risk_reasoning": evidence.get("risk_reasoning"),
                "supporting_signals": evidence.get("supporting_signals", []),
            },
            "safe_patch_planner": {
                "recommended_change_areas": patch_planner.get("recommended_change_areas", []),
                "recommended_patch_scope": patch_planner.get("recommended_patch_scope"),
                "estimated_complexity": patch_planner.get("estimated_complexity"),
                "required_tests": patch_planner.get("required_tests", []),
            },
            "verification_planner": {
                "required_tests": verification_planner.get("required_tests", []),
                "recommended_validation_steps": verification_planner.get("recommended_validation_steps", []),
                "verification_approach": verification_planner.get("verification_approach"),
            },
            "safe_change_boundary": {
                "boundary_level": boundary.get("boundary_level"),
                "criticality_level": boundary.get("criticality_level"),
                "allowed_actions": boundary.get("allowed_actions", []),
                "blocked_actions": boundary.get("blocked_actions", []),
                "risk_reason": boundary.get("risk_reason"),
            },
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "preview_only": True,
        "real_action_performed": False,
        "file_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "git_write_performed": False,
        "commit_performed": False,
        "push_performed": False,
        "deploy_performed": False,
        "auto_fix_performed": False,
        "patch_apply_performed": False,
        "subprocess_execution_performed": False,
        "repo_scan_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "This is only a read-only patch risk matrix. It does not write files, execute subprocesses, apply patches, commit, push, deploy, or modify chat/stream/websocket/typewriter behavior.",
    }
