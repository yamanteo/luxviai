from __future__ import annotations

from typing import Any, Dict, List, Optional

# clone_workspace_intelligence_registry not used in this file
from verification_intelligence_preview import (
    verification_intelligence_registry,
)
from autonomous_repair_intelligence_preview import (
    autonomous_repair_intelligence_registry,
)
from workspace_intelligence_preview import (
    workspace_intelligence_status,
)
from task_orchestration_intelligence_preview import (
    task_orchestration_intelligence_status,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


DEPLOYMENT_VERIFICATION_CAPABILITIES = [
    "deployment_readiness_analysis",
    "pre_deployment_validation",
    "post_deployment_validation",
    "release_risk_scoring",
    "rollback_readiness_analysis",
    "dependency_release_validation",
    "environment_validation",
    "deployment_confidence_scoring",
    "release_summary_generation",
    "release_recommendation_engine",
    "delivery_authorization_preview",
    "deployment_health_analysis",
]

DEPLOYMENT_PIPELINE = [
    "deployment_request",
    "readiness_analysis",
    "environment_validation",
    "dependency_validation",
    "pre_deployment_checks",
    "deployment_readiness",
    "post_deployment_validation",
    "release_approval",
]

RELEASE_PROFILES: Dict[str, Dict[str, Any]] = {
    "release_ready": {
        "aliases": ["ready", "hazir", "green", "pass", "clear"],
        "release_status": "release_ready",
        "release_health": "pass",
        "release_summary": "All deployment gates passed. Environment validated. Dependencies resolved. Release is ready for production.",
        "health_score": 0.94,
        "risk_score": 0.06,
        "deployment_readiness": "ready",
        "environment_health": "pass",
        "release_confidence": 0.92,
        "recommended_actions": ["proceed_with_release", "confirm_release_window"],
        "recommended_next_action": "ready for release — proceed with deployment",
        "release_signals": {
            "all_gates_passed": True,
            "environment_validated": True,
            "dependencies_validated": True,
            "rollback_path_confirmed": True,
            "release_blocked": False,
        },
    },
    "release_warning": {
        "aliases": ["warning", "uyari", "caution", "yellow"],
        "release_status": "release_warning",
        "release_health": "warning",
        "release_summary": "Release has minor warnings. Non-critical concerns identified. Review recommended before proceeding.",
        "health_score": 0.82,
        "risk_score": 0.20,
        "deployment_readiness": "conditional",
        "environment_health": "warning",
        "release_confidence": 0.78,
        "recommended_actions": ["review_warnings", "check_non_critical_items"],
        "recommended_next_action": "review warnings before proceeding with release",
        "release_signals": {
            "all_gates_passed": False,
            "environment_validated": True,
            "dependencies_validated": True,
            "rollback_path_confirmed": True,
            "release_blocked": False,
            "blocking_reason": "minor_warnings_pending_review",
        },
    },
    "release_risk_detected": {
        "aliases": ["risk", "riskli", "moderate", "uncertain"],
        "release_status": "release_risk_detected",
        "release_health": "degraded",
        "release_summary": "Risks detected in deployment verification. Environment or dependency concerns. Extended analysis required.",
        "health_score": 0.58,
        "risk_score": 0.48,
        "deployment_readiness": "at_risk",
        "environment_health": "degraded",
        "release_confidence": 0.55,
        "recommended_actions": [
            "run_extended_risk_analysis",
            "review_environment_health",
            "validate_dependencies",
        ],
        "recommended_next_action": "risks detected — run extended analysis before release",
        "release_signals": {
            "all_gates_passed": False,
            "environment_validated": False,
            "dependencies_validated": True,
            "rollback_path_confirmed": True,
            "release_blocked": True,
            "blocking_reason": "risks_detected_extended_analysis_required",
        },
    },
    "release_blocked": {
        "aliases": ["blocked", "engellenmis", "fail", "critical"],
        "release_status": "release_blocked",
        "release_health": "critical",
        "release_summary": "Release blocked. Critical issues detected. Resolution required before any deployment.",
        "health_score": 0.30,
        "risk_score": 0.82,
        "deployment_readiness": "blocked",
        "environment_health": "fail",
        "release_confidence": 0.25,
        "recommended_actions": [
            "resolve_critical_issues",
            "rerun_verification_pipeline",
            "revalidate_clone_state",
        ],
        "recommended_next_action": "release blocked — resolve critical issues first",
        "release_signals": {
            "all_gates_passed": False,
            "environment_validated": False,
            "dependencies_validated": False,
            "rollback_path_confirmed": False,
            "release_blocked": True,
            "blocking_reason": "critical_issues_blocking_release",
        },
    },
    "rollback_required": {
        "aliases": ["rollback", "geri_alma", "revert", "restore"],
        "release_status": "rollback_required",
        "release_health": "critical",
        "release_summary": "Rollback required. Previous deployment has issues. System health degraded. Immediate rollback recommended.",
        "health_score": 0.15,
        "risk_score": 0.92,
        "deployment_readiness": "rollback",
        "environment_health": "fail",
        "release_confidence": 0.12,
        "recommended_actions": [
            "initiate_rollback",
            "restore_previous_version",
            "run_post_rollback_validation",
        ],
        "recommended_next_action": "rollback required — initiate immediately",
        "release_signals": {
            "all_gates_passed": False,
            "environment_validated": False,
            "dependencies_validated": False,
            "rollback_path_confirmed": True,
            "release_blocked": True,
            "blocking_reason": "rollback_required_previous_deployment_unstable",
        },
    },
}

# ---------- internal helpers ----------


def _select_release_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in RELEASE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "release_ready"


def _compute_release_confidence_scores(pid: str) -> Dict[str, float]:
    p = RELEASE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    ver_conf = round(max(0.0, health * 0.85), 2)
    clone_conf = round(max(0.0, health * 0.80), 2)
    deploy_conf = round(max(0.0, health * 0.90 - risk * 0.15), 2)
    release_conf = round((ver_conf * 0.3 + clone_conf * 0.2 + deploy_conf * 0.5), 2)
    overall = round(
        (ver_conf * 0.25 + clone_conf * 0.15 + deploy_conf * 0.35 + release_conf * 0.25), 2
    )

    return {
        "verification_confidence": ver_conf,
        "clone_confidence": clone_conf,
        "deployment_confidence": deploy_conf,
        "release_confidence": release_conf,
        "overall_confidence": overall,
    }


def _compute_readiness_analysis(pid: str) -> Dict[str, Any]:
    p = RELEASE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    readiness = p.get("deployment_readiness", "blocked")
    risk_level = "low" if risk < 0.25 else ("medium" if risk < 0.60 else "high")
    confidence = round(max(0.0, health * 0.9 - risk * 0.1), 2)

    return {
        "deployment_readiness": readiness,
        "deployment_risk": risk_level,
        "deployment_confidence": confidence,
        "environment_state": "validated" if health > 0.70 else (
            "needs_review" if health > 0.40 else "failed"
        ),
        "dependencies_state": "validated" if health > 0.60 else (
            "needs_review" if health > 0.30 else "failed"
        ),
        "workspace_state": "clean" if health > 0.75 else (
            "modified" if health > 0.40 else "drifted"
        ),
        "verification_state": "passed" if health > 0.70 else (
            "warning" if health > 0.40 else "failed"
        ),
        "clone_state": "synced" if health > 0.80 else (
            "active" if health > 0.50 else "drifted"
        ),
        "read_only": True,
        "preview_only": True,
    }


def _compute_environment_validation(pid: str) -> Dict[str, Any]:
    p = RELEASE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    env_health = p.get("environment_health", "fail")

    env_risk = "low" if health > 0.75 else ("medium" if health > 0.40 else "high")
    return {
        "environment_health": env_health,
        "environment_risk": env_risk,
        "github_status": "operational" if health > 0.60 else "degraded",
        "render_status": "operational" if health > 0.60 else "degraded",
        "deployment_targets": ["production", "staging"] if health > 0.50 else ["staging"],
        "configuration": "validated" if health > 0.70 else "needs_review",
        "environment_variables": "all_set" if health > 0.80 else "partial",
        "read_only": True,
        "preview_only": True,
    }


# ---------- public entry points ----------


def deployment_verification_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.0",
        "name": "Deployment Verification Intelligence Preview",
        "status": "deployment_verification_ready",
        "version": "1.0",
        "capabilities": DEPLOYMENT_VERIFICATION_CAPABILITIES,
        "pipeline": DEPLOYMENT_PIPELINE,
        "release_profile_count": len(RELEASE_PROFILES),
        "operation_mode": "read_only_preview_only",
        "deployment_philosophy": "nothing_reaches_production_without_validation",
        "connected_layers": ["34.9", "34.8", "34.7", "34.6", "34.5"],
        "available_endpoints": [
            "/deployment-verification/status",
            "/deployment-verification/capabilities",
            "/deployment-verification/preview",
            "/deployment-verification/readiness",
            "/deployment-verification/environment",
            "/deployment-verification/release-score",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "deployment_execution": False,
        "release_execution": False,
        "rollback_execution": False,
        "environment_modification": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only deployment verification preview. No actual deployments or releases executed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def deployment_verification_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.0",
        "name": "Deployment Verification Intelligence Capabilities",
        "status": "deployment_capabilities_ready",
        "capabilities": [
            {
                "name": "deployment_readiness_analysis",
                "description": "Analyze deployment readiness across all gates",
                "read_only": True,
            },
            {
                "name": "pre_deployment_validation",
                "description": "Validate pre-deployment conditions and checks",
                "read_only": True,
            },
            {
                "name": "post_deployment_validation",
                "description": "Validate post-deployment health and stability",
                "read_only": True,
            },
            {
                "name": "release_risk_scoring",
                "description": "Score release risks across deployment dimensions",
                "read_only": True,
            },
            {
                "name": "rollback_readiness_analysis",
                "description": "Analyze rollback readiness and recovery paths",
                "read_only": True,
            },
            {
                "name": "dependency_release_validation",
                "description": "Validate dependencies for release compatibility",
                "read_only": True,
            },
            {
                "name": "environment_validation",
                "description": "Validate target environment health and configuration",
                "read_only": True,
            },
            {
                "name": "deployment_confidence_scoring",
                "description": "Score deployment confidence across all dimensions",
                "read_only": True,
            },
            {
                "name": "release_summary_generation",
                "description": "Generate comprehensive release summary",
                "read_only": True,
            },
            {
                "name": "release_recommendation_engine",
                "description": "Generate release recommendations based on risk and health",
                "read_only": True,
            },
            {
                "name": "delivery_authorization_preview",
                "description": "Preview delivery authorization without execution",
                "read_only": True,
            },
            {
                "name": "deployment_health_analysis",
                "description": "Analyze deployment health across all metrics",
                "read_only": True,
            },
        ],
        "pipeline": DEPLOYMENT_PIPELINE,
        "release_profiles": list(RELEASE_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def deployment_verification_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_release_profile(target_issue, command, project_area)
    p = RELEASE_PROFILES[pid]
    confidence = _compute_release_confidence_scores(pid)

    return {
        "release_id": pid,
        "release_status": p["release_status"],
        "release_health": p["release_health"],
        "release_summary": p.get("release_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "deployment_readiness": p.get("deployment_readiness"),
        "environment_health": p.get("environment_health"),
        "release_confidence": p.get("release_confidence"),
        "confidence_scores": confidence,
        "release_signals": p.get("release_signals", {}),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "deployment_request",
        "pipeline_progress": {
            "completed": [],
            "current": "deployment_request",
            "remaining": DEPLOYMENT_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def deployment_verification_intelligence_readiness(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_release_profile(target_issue)
    readiness = _compute_readiness_analysis(pid)
    confidence = _compute_release_confidence_scores(pid)
    return {
        "readiness_analysis": readiness,
        "confidence_scores": confidence,
        "pipeline_stage": "readiness_analysis",
        "read_only": True,
        "preview_only": True,
    }


def deployment_verification_intelligence_environment(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_release_profile(target_issue)
    env = _compute_environment_validation(pid)
    return {
        "environment_validation": env,
        "pipeline_stage": "environment_validation",
        "read_only": True,
        "preview_only": True,
    }


def deployment_verification_intelligence_release_score(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_release_profile(target_issue)
    p = RELEASE_PROFILES.get(pid, {})
    confidence = _compute_release_confidence_scores(pid)
    p_confidence = p.get("release_confidence", 0.50)

    return {
        "release_scores": {
            "health_score": p.get("health_score"),
            "risk_score": p.get("risk_score"),
            "release_confidence": p_confidence,
            "computed_confidence": confidence,
        },
        "release_result": (
            "approved" if p.get("deployment_readiness") == "ready"
            else "conditional" if p.get("deployment_readiness") in ("conditional", "at_risk")
            else "blocked"
        ),
        "pipeline_stage": "release_approval",
        "read_only": True,
        "preview_only": True,
    }


def deployment_verification_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for rid, r in RELEASE_PROFILES.items():
        items.append({
            "release_id": rid,
            "release_status": r["release_status"],
            "release_health": r["release_health"],
            "health_score": r.get("health_score"),
            "risk_score": r.get("risk_score"),
            "deployment_readiness": r.get("deployment_readiness"),
            "release_confidence": r.get("release_confidence"),
        })
    return {
        "layer": "35.0",
        "name": "Deployment Verification Intelligence Registry",
        "status": "deployment_verification_registry_ready",
        "read_only": True,
        "preview_only": True,
        "release_profile_count": len(items),
        "release_profiles": items,
        "ready_count": sum(1 for i in items if i.get("deployment_readiness") == "ready"),
        "conditional_count": sum(1 for i in items if i.get("deployment_readiness") == "conditional"),
        "at_risk_count": sum(1 for i in items if i.get("deployment_readiness") == "at_risk"),
        "blocked_count": sum(1 for i in items if i.get("deployment_readiness") in ("blocked", "rollback")),
    }
