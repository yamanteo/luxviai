from __future__ import annotations
from typing import Any, Dict, List, Optional

from verification_intelligence_preview import (
    verification_intelligence_registry,
)
from sandbox_repair_intelligence_preview import (
    sandbox_repair_intelligence_registry,
)
# lazy import: clone_workspace_intelligence_registry imported inside function
from change_planning_intelligence_preview import (
    change_planning_intelligence_registry,
)
from failed_change_intelligence_preview import (
    failed_change_intelligence_registry,
)
from change_memory_intelligence_preview import (
    change_memory_intelligence_registry,
)


DELIVERY_READINESS_PROFILES: Dict[str, Dict[str, Any]] = {
    "not_ready": {
        "aliases": ["not ready", "hazir degil", "blocked", "incomplete"],
        "delivery_status": "not_ready",
        "delivery_score": 0.25,
        "delivery_summary": "Delivery readiness not achieved. Verification incomplete. Multiple blocked gates. Release blockers unresolved. Rollback readiness not verified. Handoff documentation missing.",
        "delivery_confidence": 0.30,
        "delivery_risk_level": "critical",
        "delivery_readiness": "not_ready",
        "release_candidate_status": "blocked",
        "release_candidate_score": 0.0,
        "release_blockers": [
            "integration_verification_gate_failed",
            "production_validation_not_run",
            "rollback_readiness_not_verified",
        ],
        "release_warnings": [
            "dependency_verification_pending",
            "workflow_verification_has_warnings",
        ],
        "release_requirements": [
            "complete_all_verification_gates",
            "resolve_integration_gate_failure",
            "verify_rollback_readiness",
            "complete_production_validation",
        ],
        "deployment_readiness": "not_ready",
        "rollback_readiness": "not_verified",
        "handoff_readiness": "incomplete",
        "documentation_readiness": "incomplete",
        "verification_readiness": "blocked",
        "dependency_readiness": "warning",
        "integration_readiness": "failed",
        "workflow_readiness": "warning",
        "regression_readiness": "pending",
        "production_validation_readiness": "not_run",
        "final_delivery_recommendation": "DO NOT DELIVER. Blocking issues must be resolved first.",
        "required_actions": [
            "fix_integration_verification_gate",
            "complete_all_verification_gates",
            "verify_rollback_readiness",
            "complete_production_validation",
            "prepare_handoff_documentation",
        ],
        "recommended_next_action": "resolve integration verification gate failure first",
    },
    "partially_ready": {
        "aliases": ["partial", "kismen", "in progress", "devam ediyor"],
        "delivery_status": "partially_ready",
        "delivery_score": 0.45,
        "delivery_summary": "Delivery readiness partially achieved. Most verification gates pass. One gate has warnings. Rollback readiness verified. Documentation pending. Production validation not yet run.",
        "delivery_confidence": 0.50,
        "delivery_risk_level": "high",
        "delivery_readiness": "partially_ready",
        "release_candidate_status": "conditional",
        "release_candidate_score": 0.40,
        "release_blockers": [],
        "release_warnings": [
            "workflow_verification_has_warnings",
            "production_validation_not_run",
            "handoff_documentation_incomplete",
        ],
        "release_requirements": [
            "resolve_workflow_verification_warnings",
            "complete_production_validation",
            "complete_handoff_documentation",
        ],
        "deployment_readiness": "conditional",
        "rollback_readiness": "verified",
        "handoff_readiness": "incomplete",
        "documentation_readiness": "incomplete",
        "verification_readiness": "warning",
        "dependency_readiness": "ready",
        "integration_readiness": "ready",
        "workflow_readiness": "warning",
        "regression_readiness": "ready",
        "production_validation_readiness": "not_run",
        "final_delivery_recommendation": "CONDITIONAL. Resolve warnings and run production validation before delivery.",
        "required_actions": [
            "resolve_workflow_warnings",
            "run_production_validation",
            "complete_handoff_documentation",
        ],
        "recommended_next_action": "run production validation after resolving workflow warnings",
    },
    "conditionally_ready": {
        "aliases": ["conditional", "sartli", "almost", "neredeyse"],
        "delivery_status": "conditionally_ready",
        "delivery_score": 0.68,
        "delivery_summary": "Delivery readiness conditionally achieved. All verification gates pass. Production validation complete. Rollback readiness verified. One minor documentation gap remains. Delivery recommended with condition.",
        "delivery_confidence": 0.72,
        "delivery_risk_level": "medium",
        "delivery_readiness": "conditionally_ready",
        "release_candidate_status": "conditional",
        "release_candidate_score": 0.65,
        "release_blockers": [],
        "release_warnings": [
            "handoff_documentation_minor_gap",
        ],
        "release_requirements": [
            "complete_remaining_documentation",
        ],
        "deployment_readiness": "ready",
        "rollback_readiness": "verified",
        "handoff_readiness": "partial",
        "documentation_readiness": "partial",
        "verification_readiness": "ready",
        "dependency_readiness": "ready",
        "integration_readiness": "ready",
        "workflow_readiness": "ready",
        "regression_readiness": "ready",
        "production_validation_readiness": "verified",
        "final_delivery_recommendation": "CONDITIONALLY APPROVED. Complete remaining documentation before delivery.",
        "required_actions": [
            "complete_handoff_documentation_gap",
        ],
        "recommended_next_action": "complete remaining handoff documentation before delivery",
    },
    "ready": {
        "aliases": ["ready", "hazir", "prepared", "approved"],
        "delivery_status": "ready",
        "delivery_score": 0.85,
        "delivery_summary": "Delivery readiness achieved. All verification gates pass. Production validation complete. Rollback readiness verified. Handoff documentation complete. All requirements satisfied.",
        "delivery_confidence": 0.82,
        "delivery_risk_level": "low",
        "delivery_readiness": "ready",
        "release_candidate_status": "approved",
        "release_candidate_score": 0.82,
        "release_blockers": [],
        "release_warnings": [],
        "release_requirements": [],
        "deployment_readiness": "ready",
        "rollback_readiness": "verified",
        "handoff_readiness": "complete",
        "documentation_readiness": "complete",
        "verification_readiness": "ready",
        "dependency_readiness": "ready",
        "integration_readiness": "ready",
        "workflow_readiness": "ready",
        "regression_readiness": "ready",
        "production_validation_readiness": "verified",
        "final_delivery_recommendation": "APPROVED. All readiness requirements satisfied. Proceed with delivery.",
        "required_actions": [],
        "recommended_next_action": "proceed with delivery",
    },
    "delivery_ready": {
        "aliases": ["delivery ready", "teslim", "go", "git", "deploy"],
        "delivery_status": "delivery_ready",
        "delivery_score": 0.94,
        "delivery_summary": "Full delivery readiness confirmed. All verification gates pass. Production validation complete. Rollback readiness verified. Handoff documentation complete. Deployment plan verified. Change is correct, stable, safe, regression-free, dependency-safe, integration-safe, workflow-safe, and delivery-ready.",
        "delivery_confidence": 0.90,
        "delivery_risk_level": "low",
        "delivery_readiness": "delivery_ready",
        "release_candidate_status": "approved",
        "release_candidate_score": 0.92,
        "release_blockers": [],
        "release_warnings": [],
        "release_requirements": [],
        "deployment_readiness": "ready",
        "rollback_readiness": "verified",
        "handoff_readiness": "complete",
        "documentation_readiness": "complete",
        "verification_readiness": "ready",
        "dependency_readiness": "ready",
        "integration_readiness": "ready",
        "workflow_readiness": "ready",
        "regression_readiness": "ready",
        "production_validation_readiness": "verified",
        "final_delivery_recommendation": "FULLY APPROVED. Delivery candidate ready. All 10 readiness dimensions confirmed. No blockers. No warnings. Proceed with deployment.",
        "required_actions": [],
        "recommended_next_action": "proceed with deployment — delivery candidate ready",
    },
}


def _select_delivery_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in DELIVERY_READINESS_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "not_ready"


def delivery_readiness_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "33.7",
        "name": "Delivery Readiness Intelligence Preview",
        "status": "delivery_readiness_intelligence_ready",
        "delivery_model": {
            "real_system": "source_of_truth",
            "master_clone": "reference_only",
            "working_clone": "repairs_here",
            "sandbox": "testing_here",
            "verification": "all_gates",
            "delivery_readiness": "readiness_check",
            "delivery_candidate": "ready_when_all_conditions_met",
        },
        "readiness_requirements": [
            "verification_complete",
            "regression_complete",
            "dependencies_verified",
            "integration_verified",
            "workflow_verified",
            "production_validation_verified",
            "rollback_readiness_verified",
            "documentation_readiness_verified",
        ],
        "fail_conditions": [
            "any_unresolved_blocker_blocks_delivery",
            "any_critical_risk_blocks_delivery",
            "any_failed_verification_gate_blocks_delivery",
            "any_failed_rollback_readiness_check_blocks_delivery",
            "any_failed_production_validation_blocks_delivery",
        ],
        "delivery_levels": [
            "not_ready",
            "partially_ready",
            "conditionally_ready",
            "ready",
            "delivery_ready",
        ],
        "loop_protection": {
            "detect_repeated_delivery_failures": True,
            "detect_repeated_release_blockers": True,
            "detect_repeated_rollback_failures": True,
            "detect_repeated_handoff_failures": True,
            "use_33_6_verification_intelligence": True,
            "use_33_5_sandbox_repair_intelligence": True,
            "use_33_4_clone_workspace_intelligence": True,
            "use_33_3_change_planning_intelligence": True,
            "use_33_2_failed_change_intelligence": True,
            "use_33_1_change_memory_intelligence": True,
        },
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
            "/debug/delivery-readiness-status",
            "/debug/delivery-readiness-registry",
            "/debug/delivery-readiness-preview",
        ],
        "connected_layers": [
            "33.6", "33.5", "33.4", "33.3", "33.2", "33.1",
            "32", "31", "30", "29",
        ],
        "technology_support": [
            "Python", "HTML", "CSS", "JavaScript", "TypeScript",
            "JSON", "YAML", "Database", "Infrastructure", "API",
            "Workflow", "Documentation",
        ],
        "safety_note": "Read-only delivery readiness intelligence preview. No actual delivery actions performed.",
    }


def delivery_readiness_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for did, d in DELIVERY_READINESS_PROFILES.items():
        items.append(
            {
                "delivery_id": did,
                "delivery_status": d["delivery_status"],
                "delivery_score": d["delivery_score"],
                "delivery_confidence": d.get("delivery_confidence"),
                "delivery_risk_level": d.get("delivery_risk_level"),
                "delivery_readiness": d.get("delivery_readiness"),
                "release_candidate_status": d.get("release_candidate_status"),
                "release_candidate_score": d.get("release_candidate_score"),
                "blocker_count": len(d.get("release_blockers", [])),
                "warning_count": len(d.get("release_warnings", [])),
                "deployment_readiness": d.get("deployment_readiness"),
                "rollback_readiness": d.get("rollback_readiness"),
                "handoff_readiness": d.get("handoff_readiness"),
            }
        )
    return {
        "layer": "33.7",
        "name": "Delivery Readiness Intelligence Registry",
        "status": "delivery_readiness_intelligence_registry_ready",
        "delivery_levels_defined": [
            "not_ready", "partially_ready", "conditionally_ready",
            "ready", "delivery_ready",
        ],
        "read_only": True,
        "strict_read_only": True,
        "analysis_only": True,
        "delivery_count": len(items),
        "delivery_items": items,
        "readiness_breakdown": {
            level: sum(1 for i in items if i["delivery_readiness"] == level)
            for level in ["not_ready", "partially_ready", "conditionally_ready", "ready", "delivery_ready"]
        },
        "overall_delivery_score": round(
            sum(i["delivery_score"] for i in items) / len(items), 2
        ) if items else 0.0,
        "release_candidate_summary": {
            "approved": sum(1 for i in items if i.get("release_candidate_status") == "approved"),
            "conditional": sum(1 for i in items if i.get("release_candidate_status") == "conditional"),
            "blocked": sum(1 for i in items if i.get("release_candidate_status") == "blocked"),
        },
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
        },
    }


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 33.7"
    verification_reg = verification_intelligence_registry()
    sandbox_reg = sandbox_repair_intelligence_registry()
    from clone_workspace_intelligence_preview import clone_workspace_intelligence_registry
    clone_reg = clone_workspace_intelligence_registry()
    planning_reg = change_planning_intelligence_registry()
    failed_change_reg = failed_change_intelligence_registry()
    change_reg = change_memory_intelligence_registry()

    return {
        "layer33_6_verification_intelligence": {
            "verification_count": verification_reg.get("verification_count"),
            "overall_verification_score": verification_reg.get("overall_verification_score"),
            "all_gates_passed_count": verification_reg.get("all_gates_passed_count"),
        },
        "layer33_5_sandbox_repair_intelligence": {
            "repair_count": sandbox_reg.get("repair_count"),
            "overall_repair_score": sandbox_reg.get("overall_repair_score"),
        },
        "layer33_4_clone_workspace_intelligence": {
            "workspace_count": clone_reg.get("workspace_count"),
            "avg_sync_score": clone_reg.get("avg_sync_score"),
        },
        "layer33_3_change_planning_intelligence": {
            "plan_count": planning_reg.get("plan_count"),
            "overall_plan_score": planning_reg.get("overall_plan_score"),
        },
        "layer33_2_failed_change_intelligence": {
            "failed_change_count": failed_change_reg.get("failed_change_count"),
            "overall_failed_change_score": failed_change_reg.get("overall_failed_change_score"),
        },
        "layer33_1_change_memory_intelligence": {
            "change_count": change_reg.get("change_count"),
            "overall_change_score": change_reg.get("overall_change_score"),
        },
    }


def build_delivery_readiness_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    did = _select_delivery_profile(target_issue, command, project_area)
    d = DELIVERY_READINESS_PROFILES[did]
    detected = target_issue or project_area or did
    cmd = command or detected
    L = related_layer or "Layer 33.7"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)

    return {
        "delivery_id": did,
        "delivery_status": d["delivery_status"],
        "delivery_score": d["delivery_score"],
        "delivery_summary": d.get("delivery_summary"),
        "delivery_confidence": d.get("delivery_confidence"),
        "delivery_risk_level": d.get("delivery_risk_level"),
        "delivery_readiness": d.get("delivery_readiness"),
        "release_candidate_status": d.get("release_candidate_status"),
        "release_candidate_score": d.get("release_candidate_score"),
        "release_blockers": d.get("release_blockers", []),
        "release_warnings": d.get("release_warnings", []),
        "release_requirements": d.get("release_requirements", []),
        "deployment_readiness": d.get("deployment_readiness"),
        "rollback_readiness": d.get("rollback_readiness"),
        "handoff_readiness": d.get("handoff_readiness"),
        "documentation_readiness": d.get("documentation_readiness"),
        "verification_readiness": d.get("verification_readiness"),
        "dependency_readiness": d.get("dependency_readiness"),
        "integration_readiness": d.get("integration_readiness"),
        "workflow_readiness": d.get("workflow_readiness"),
        "regression_readiness": d.get("regression_readiness"),
        "production_validation_readiness": d.get("production_validation_readiness"),
        "final_delivery_recommendation": d.get("final_delivery_recommendation"),
        "required_actions": d.get("required_actions", []),
        "recommended_next_action": d.get("recommended_next_action"),
        "runtime_signals": integration,
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
        "safety_note": "Read-only delivery readiness intelligence preview. No actual delivery actions performed.",
    }
