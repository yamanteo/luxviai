from __future__ import annotations

from typing import Any, Dict, List, Optional

from impact_analyzer_preview import build_impact_analyzer_preview
from safe_change_boundary_preview import build_change_boundary_preview
from safe_patch_planner_preview import build_patch_planner_preview, patch_planner_registry


VERIFICATION_PROFILES: Dict[str, Dict[str, Any]] = {
    "stop_continue": {
        "aliases": ["stop", "continue", "dur", "devam", "resume", "arm"],
        "recommended_manual_tests": [
            "10 maddelik liste olustur",
            "3. maddede dur",
            "devam et",
            "tekrar dur",
            "tekrar devam et",
        ],
        "recommended_regression_checks": ["stream_flow", "resume_flow", "typewriter_queue", "arm_state"],
        "success_criteria": [
            "liste kaldigi yerden tamamlanmali",
            "tekrar dur/devam calismali",
            "onceki gorunen metin bastan yazilmamali",
        ],
        "risk_validation_points": ["multiple_continue_cycle", "partial_word_resume", "no_bulk_injection"],
        "estimated_validation_effort": "medium",
    },
    "websocket_stream": {
        "aliases": ["websocket", "stream", "typewriter", "tab", "delta", "done"],
        "recommended_manual_tests": [
            "uzun cevap baslat",
            "baska sekmeye gec",
            "geri donunce akisin surdugunu kontrol et",
        ],
        "recommended_regression_checks": ["websocket_late_event_guard", "stream_done_guard", "typewriter_queue"],
        "success_criteria": [
            "sekme degisiminde cevap akisi kopmamali",
            "gec done/final eventleri blok halinde dusmemeli",
        ],
        "risk_validation_points": ["event_leak", "late_done_ignore", "queue_drift"],
        "estimated_validation_effort": "high",
    },
    "workspace_export": {
        "aliases": ["workspace", "export", "pdf", "word", "file", "dosya"],
        "recommended_manual_tests": [
            "workspace export preview calistir",
            "command bloklarinin disarida kaldigini kontrol et",
        ],
        "recommended_regression_checks": ["export_clean_filter", "file_written_false_guard", "command_block_exclusion"],
        "success_criteria": [
            "clean export preview komut metni icermemeli",
            "file_written false kalmali",
        ],
        "risk_validation_points": ["real_file_write_guard", "exportable_block_filter"],
        "estimated_validation_effort": "medium",
    },
    "luxway_permission": {
        "aliases": ["luxway", "permission", "izin", "phone", "telefon", "mail", "calendar"],
        "recommended_manual_tests": [
            "telefon raporu preview calistir",
            "silme/gonderme komutunda confirmation kontrol et",
        ],
        "recommended_regression_checks": ["permission_boundary", "confirmation_boundary", "real_access_false_guard"],
        "success_criteria": [
            "real_access_enabled false kalmali",
            "data_read ve data_written false kalmali",
            "riskli islerde confirmation required olmali",
        ],
        "risk_validation_points": ["private_data_guard", "send_delete_blocked_by_default"],
        "estimated_validation_effort": "high",
    },
    "debug_intelligence": {
        "aliases": ["debug", "fault", "report", "investigation", "planner", "verification"],
        "recommended_manual_tests": [
            "debug panel verification butonlarini ac",
            "fault report verification planlarini kontrol et",
        ],
        "recommended_regression_checks": ["endpoint_coverage", "fault_report_sections", "read_only_flags"],
        "success_criteria": [
            "endpointler crash olmadan donmeli",
            "read_only ve analysis_only true kalmali",
        ],
        "risk_validation_points": ["panel_visibility", "smoke_coverage"],
        "estimated_validation_effort": "low",
    },
}


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


def _select_profile(target_issue: Optional[str], command: str) -> str:
    haystack = _normalize(f"{target_issue or ''} {command or ''}")
    for profile_id, profile in VERIFICATION_PROFILES.items():
        if any(str(alias).lower() in haystack for alias in profile.get("aliases", [])):
            return profile_id
    return "debug_intelligence"


def _unique(items: List[Any]) -> List[Any]:
    output: List[Any] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def verification_planner_status() -> Dict[str, Any]:
    return {
        "layer": "25.6",
        "name": "Verification Planner Preview",
        "status": "verification_planner_preview_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
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
            "/debug/verification-planner-status",
            "/debug/verification-planner-registry",
            "/debug/verification-planner-preview",
        ],
        "connected_layers": [
            "25.3 Impact Analyzer",
            "25.4 Safe Change Boundary",
            "25.5 Safe Patch Planner",
        ],
        "future_direction": ["Verifier Agent", "Regression Guard", "Validation Engine"],
        "safety_note": "Verification Planner only creates a read-only validation plan; it never runs tests, applies patches, writes files, commits, pushes, deploys, or executes subprocesses.",
    }


def verification_planner_registry() -> Dict[str, Any]:
    plans: List[Dict[str, Any]] = []
    for profile_id, profile in VERIFICATION_PROFILES.items():
        patch_plan = build_patch_planner_preview(target_issue=profile_id, command=profile_id)
        plans.append(
            {
                "id": profile_id,
                "recommended_smoke_tests": _unique(["smoke_check"] + list(patch_plan.get("required_tests", []))),
                "recommended_manual_tests": profile["recommended_manual_tests"],
                "recommended_regression_checks": profile["recommended_regression_checks"],
                "success_criteria": profile["success_criteria"],
                "risk_validation_points": profile["risk_validation_points"],
                "estimated_validation_effort": profile["estimated_validation_effort"],
            }
        )
    return {
        "layer": "25.6",
        "name": "Verification Planner Registry",
        "status": "verification_planner_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "plan_count": len(plans),
        "verification_plans": plans,
        "connected_endpoints": [
            "/debug/patch-planner-preview",
            "/debug/change-boundary-preview",
            "/debug/impact-analyzer-preview",
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
            "test_execution": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_verification_planner_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    profile_id = _select_profile(target_issue, command)
    profile = VERIFICATION_PROFILES[profile_id]
    detected_issue = target_issue or profile_id
    patch_plan = build_patch_planner_preview(
        target_issue=detected_issue,
        command=command or detected_issue,
        related_layer=related_layer,
    )
    boundary = build_change_boundary_preview(
        target_area=detected_issue,
        command=command or detected_issue,
        related_layer=related_layer,
    )
    impact = build_impact_analyzer_preview(
        target_component=detected_issue,
        command=command or detected_issue,
        related_layer=related_layer,
    )
    impacted_behaviors = list(impact.get("potentially_affected_behaviors", []))

    return {
        "target_issue": detected_issue,
        "recommended_smoke_tests": _unique(["smoke_check"] + list(patch_plan.get("required_tests", []))),
        "recommended_manual_tests": profile["recommended_manual_tests"],
        "recommended_regression_checks": _unique(
            list(profile["recommended_regression_checks"]) + impacted_behaviors[:3]
        ),
        "success_criteria": profile["success_criteria"],
        "risk_validation_points": _unique(
            list(profile["risk_validation_points"]) + list(patch_plan.get("recommended_validation_steps", []))[:3]
        ),
        "estimated_validation_effort": profile["estimated_validation_effort"],
        "confidence_score": 0.9,
        "patch_plan_signal": {
            "recommended_patch_scope": patch_plan.get("recommended_patch_scope"),
            "risk_assessment": patch_plan.get("risk_assessment"),
            "required_tests": patch_plan.get("required_tests", []),
            "approval_required": patch_plan.get("approval_required"),
            "estimated_complexity": patch_plan.get("estimated_complexity"),
        },
        "boundary_signal": {
            "boundary_level": boundary.get("boundary_level"),
            "criticality_level": boundary.get("criticality_level"),
            "user_approval_required": boundary.get("user_approval_required"),
            "blocked_actions": boundary.get("blocked_actions", []),
        },
        "impact_signal": {
            "impact_risk": impact.get("impact_risk"),
            "recommended_caution_level": impact.get("recommended_caution_level"),
            "potentially_affected_behaviors": impacted_behaviors,
            "potentially_affected_endpoints": impact.get("potentially_affected_endpoints", []),
        },
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "test_execution_performed": False,
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
        "safety_note": "This is a strict read-only verification plan preview. It recommends tests and success criteria but does not execute tests or change runtime behavior.",
    }
