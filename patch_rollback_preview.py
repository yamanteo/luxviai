from __future__ import annotations

from typing import Any, Dict, List, Optional

from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview
from change_preview_engine_preview import build_change_preview
from diff_preview_engine_preview import build_diff_preview
from patch_risk_matrix_preview import build_patch_risk_preview
from patch_approval_engine_preview import build_patch_approval_preview
from patch_execution_readiness_preview import build_patch_execution_preview
from safe_patch_application_preview import build_safe_patch_preview
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview
from safe_verification_planner_preview import build_verification_planner_preview


ROLLBACK_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "target_component": "resume_flow",
        "rollback_required": False,
        "rollback_level": "none",
        "rollback_reason": "consolidation is low-risk; git revert suffices if needed",
        "rollback_trigger_conditions": ["resume_flow regression", "double-stop failure", "chat timeout after stop"],
        "rollback_steps": ["git revert consolidation commit", "re-run stop/continue smoke tests", "verify websocket reconnect"],
        "rollback_validation_steps": ["resume after stop", "websocket reconnect", "double-stop guard"],
        "rollback_risk_level": "low",
        "rollback_risk_reasons": ["single commit revert", "no data migration", "no schema change"],
        "rollback_dependencies": ["smoke_test_suite"],
        "rollback_safe_boundary": "can revert independently without affecting other patches",
        "rollback_recovery_plan": "revert → smoke test → if passes, redeploy original state",
        "rollback_readiness": True,
        "recommended_next_action": "no rollback needed; monitor post-merge",
        "confidence_score": 0.87,
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "target_component": "stream_flow",
        "rollback_required": True,
        "rollback_level": "mandatory",
        "rollback_reason": "high runtime risk — stream state drift requires immediate rollback capability",
        "rollback_trigger_conditions": ["tab switch regression", "typewriter queue stall", "done event missing", "stream data loss"],
        "rollback_steps": ["canary rollback first", "git revert stream change commit", "re-run full stream regression suite", "verify production stream health"],
        "rollback_validation_steps": ["manual tab switch", "long answer stream", "stop during stream", "done after disconnect"],
        "rollback_risk_level": "high",
        "rollback_risk_reasons": ["multi-hunk patch", "typewriter runtime change", "websocket state mutation", "large blast radius"],
        "rollback_dependencies": ["canary_deployment", "regression_suite", "production_monitoring"],
        "rollback_safe_boundary": "must rollback entire stream patch atomically; cannot partial revert",
        "rollback_recovery_plan": "canary rollback → full revert → regression suite → production health check → re-deploy stable",
        "rollback_readiness": False,
        "recommended_next_action": "establish canary deployment pipeline before attempting stream patch",
        "confidence_score": 0.83,
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "target_component": "export_preview",
        "rollback_required": False,
        "rollback_level": "none",
        "rollback_reason": "export guard tightening is low-risk and future-only",
        "rollback_trigger_conditions": ["export preview schema break", "write guard false positive"],
        "rollback_steps": ["git revert export guard commit", "verify export preview endpoint", "re-run format validation"],
        "rollback_validation_steps": ["export format validation", "write guard assertion"],
        "rollback_risk_level": "low",
        "rollback_risk_reasons": ["preview-only change", "no production export yet", "single commit revert"],
        "rollback_dependencies": ["smoke_test_suite"],
        "rollback_safe_boundary": "can revert independently; no other patches depend on export guard",
        "rollback_recovery_plan": "revert → smoke test → if passes, redeploy",
        "rollback_readiness": True,
        "recommended_next_action": "no rollback needed; monitor post-merge",
        "confidence_score": 0.86,
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "target_component": "permission_flow",
        "rollback_required": True,
        "rollback_level": "mandatory",
        "rollback_reason": "private data boundary change requires guaranteed rollback",
        "rollback_trigger_conditions": ["permission denial regression", "private data leak", "platform permission mismatch"],
        "rollback_steps": ["canary rollback first", "git revert permission commit", "re-run platform validation suite", "verify Android + iOS permission flows"],
        "rollback_validation_steps": ["Android permission flow", "iOS permission flow", "private data guard"],
        "rollback_risk_level": "high",
        "rollback_risk_reasons": ["private data surface change", "platform-specific behavior", "user-facing permission UX"],
        "rollback_dependencies": ["canary_deployment", "platform_validation_suite", "privacy_audit"],
        "rollback_safe_boundary": "must rollback entire permission patch atomically; device safety depends on it",
        "rollback_recovery_plan": "canary rollback → full revert → platform re-validation → privacy audit → re-deploy stable",
        "rollback_readiness": False,
        "recommended_next_action": "complete platform validation before re-evaluating rollback readiness",
        "confidence_score": 0.85,
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "rollback"],
        "target_component": "preview_schema",
        "rollback_required": False,
        "rollback_level": "none",
        "rollback_reason": "read-only scaffold with no runtime impact",
        "rollback_trigger_conditions": ["preview schema drift", "smoke test regression"],
        "rollback_steps": ["git revert scaffold commit"],
        "rollback_validation_steps": ["status endpoint smoke", "registry smoke", "preview response shape"],
        "rollback_risk_level": "low",
        "rollback_risk_reasons": ["read-only addition", "no runtime change", "single commit revert"],
        "rollback_dependencies": ["smoke_test_suite"],
        "rollback_safe_boundary": "can revert independently; no other patches depend on scaffold",
        "rollback_recovery_plan": "revert → smoke test → redeploy",
        "rollback_readiness": True,
        "recommended_next_action": "no rollback needed",
        "confidence_score": 0.9,
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str, project_area: Optional[str]) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''} {project_area or ''}")
    for profile_id, profile in ROLLBACK_PROFILES.items():
        if profile_id in haystack or any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def patch_rollback_status() -> Dict[str, Any]:
    return {
        "layer": "28.2", "name": "Patch Rollback Preview",
        "status": "patch_rollback_ready",
        "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
        "real_action_performed": False,
        "file_write_enabled": False, "memory_write_enabled": False, "db_write_enabled": False,
        "git_write_enabled": False, "commit_enabled": False, "push_enabled": False,
        "deploy_enabled": False, "auto_fix_enabled": False, "patch_apply_enabled": False,
        "subprocess_execution_enabled": False, "repo_scan_performed": False,
        "chat_stream_touched": False, "typewriter_runtime_touched": False,
        "available_endpoints": ["/debug/patch-rollback-status", "/debug/patch-rollback-registry", "/debug/patch-rollback-preview"],
        "connected_layers": ["28.1", "27.6", "27.5", "27.4", "27.3", "27.2", "27.1", "26.7", "26.6", "25.6", "25.5", "25.4"],
        "safety_note": "Patch Rollback Preview only describes rollback strategy. It never executes rollbacks, writes files, or modifies runtime.",
    }


def patch_rollback_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for profile_id, profile in ROLLBACK_PROFILES.items():
        items.append({
            "id": profile_id, "target_component": profile["target_component"],
            "rollback_required": profile["rollback_required"], "rollback_level": profile["rollback_level"],
            "rollback_readiness": profile["rollback_readiness"], "rollback_risk_level": profile["rollback_risk_level"],
            "confidence_score": profile["confidence_score"],
        })
    return {
        "layer": "28.2", "name": "Patch Rollback Registry",
        "status": "patch_rollback_registry_ready",
        "read_only": True, "strict_read_only": True, "analysis_only": True,
        "rollback_count": len(items), "rollbacks": items,
        "mandatory_count": sum(1 for i in items if i["rollback_level"] == "mandatory"),
        "ready_count": sum(1 for i in items if i["rollback_readiness"]),
        "safety_flags": {"file_write": False, "memory_write": False, "db_write": False, "git_write": False,
                         "commit": False, "push": False, "deploy": False, "auto_fix": False,
                         "patch_apply": False, "subprocess_execution": False},
    }


def build_patch_rollback_preview(
    target_issue: Optional[str] = None, command: str = "",
    project_area: Optional[str] = None, related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command, project_area)
    profile = ROLLBACK_PROFILES[profile_id]
    detected_issue = target_issue or project_area or profile_id
    cmd = command or detected_issue
    L = related_layer or "Layer 28.2"

    safe_patch = build_safe_patch_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    execution = build_patch_execution_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    approval = build_patch_approval_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    risk = build_patch_risk_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    diff = build_diff_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    change = build_change_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    draft = build_patch_draft_preview(target_issue=detected_issue, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    coordinator = build_coordinator_preview(command=cmd, project_area=project_area or detected_issue, related_layer=L)
    evidence = build_evidence_store_preview(finding=None, command=cmd, project_area=project_area or detected_issue, related_layer=L)
    verification = build_verification_planner_preview(target_issue=detected_issue, command=cmd, related_layer=L)
    planner = build_patch_planner_preview(target_issue=detected_issue, command=cmd, related_layer=L)
    boundary = build_change_boundary_preview(target_area=detected_issue, command=cmd, related_layer=L)

    conf = round((float(profile["confidence_score"]) + float(safe_patch.get("confidence_score", 0.0))
                  + float(execution.get("confidence_score", 0.0)) + float(approval.get("confidence_score", 0.0))
                  + float(risk.get("confidence_score", 0.0)) + float(diff.get("confidence_score", 0.0))
                  + float(change.get("confidence_score", 0.0)) + float(draft.get("confidence_score", 0.0))
                  + float(coordinator.get("overall_confidence", 0.0)) + float(evidence.get("confidence_score", 0.0))) / 10, 2)

    return {
        "target_issue": detected_issue, "target_component": profile["target_component"],
        "rollback_required": profile["rollback_required"], "rollback_level": profile["rollback_level"],
        "rollback_reason": profile["rollback_reason"],
        "rollback_trigger_conditions": _unique(list(profile["rollback_trigger_conditions"]) + list(risk.get("risk_reasons", []))[:2]),
        "rollback_steps": list(profile["rollback_steps"]),
        "rollback_validation_steps": _unique(list(profile["rollback_validation_steps"]) + list(verification.get("required_tests", []))[:2]),
        "rollback_risk_level": profile["rollback_risk_level"],
        "rollback_risk_reasons": _unique(list(profile["rollback_risk_reasons"]) + list(risk.get("risk_reasons", []))[:2]),
        "rollback_dependencies": _unique(list(profile["rollback_dependencies"]) + [str(e) for e in execution.get("missing_requirements", []) if str(e)][:2]),
        "rollback_safe_boundary": profile["rollback_safe_boundary"],
        "rollback_recovery_plan": profile["rollback_recovery_plan"],
        "rollback_readiness": profile["rollback_readiness"],
        "recommended_next_action": profile["recommended_next_action"],
        "confidence_score": conf,
        "integration_signals": {
            "safe_patch_application": {"application_ready": safe_patch.get("application_ready"), "rollback_plan": safe_patch.get("rollback_plan")},
            "patch_execution_readiness": {"execution_ready": execution.get("execution_ready"), "go_no_go_status": execution.get("go_no_go_status")},
            "patch_approval": {"approval_required": approval.get("approval_required")},
            "patch_risk_matrix": {"risk_score": risk.get("risk_score"), "risk_level": risk.get("risk_level")},
            "diff_preview": {"affected_files": diff.get("affected_files", [])},
            "change_preview": {"risk_areas": change.get("risk_areas", [])},
            "patch_draft": {"recommended_files": draft.get("recommended_files", [])},
            "multi_agent_coordinator": {"combined_risks": coordinator.get("combined_risks", [])},
            "evidence_store": {"risk_reasoning": evidence.get("risk_reasoning")},
            "verification_planner": {"required_tests": verification.get("required_tests", [])},
            "safe_patch_planner": {"estimated_complexity": planner.get("estimated_complexity")},
            "safe_change_boundary": {"blocked_actions": boundary.get("blocked_actions", [])},
        },
        "read_only": True, "strict_read_only": True, "analysis_only": True, "preview_only": True,
        "real_action_performed": False,
        "file_write_performed": False, "memory_write_performed": False, "db_write_performed": False,
        "git_write_performed": False, "commit_performed": False, "push_performed": False,
        "deploy_performed": False, "auto_fix_performed": False, "patch_apply_performed": False,
        "subprocess_execution_performed": False, "repo_scan_performed": False,
        "chat_stream_touched": False, "typewriter_runtime_touched": False,
        "safety_note": "Read-only rollback preview. No actual rollback execution.",
    }
