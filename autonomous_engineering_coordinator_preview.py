from __future__ import annotations

from typing import Any, Dict, List, Optional

from deployment_verification_intelligence_preview import (
    deployment_verification_intelligence_registry,
)
# lazy import: clone_workspace_intelligence_registry imported inside function
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


ENGINEERING_COORDINATOR_CAPABILITIES = [
    "task_chain_coordination",
    "workspace_coordination",
    "repair_coordination",
    "verification_coordination",
    "clone_coordination",
    "deployment_coordination",
    "delivery_coordination",
    "workflow_state_tracking",
    "dependency_flow_tracking",
    "engineering_health_analysis",
    "engineering_summary_generation",
    "engineering_recommendation_engine",
]

ENGINEERING_PIPELINE = [
    "task_intake",
    "workspace_analysis",
    "repair_planning",
    "verification_planning",
    "clone_validation",
    "deployment_validation",
    "delivery_review",
    "completion",
]

WORKFLOW_STATES = [
    "idle",
    "analyzing",
    "repairing",
    "verifying",
    "clone_validating",
    "deployment_review",
    "delivery_review",
    "completed",
    "blocked",
    "recovery",
]

ENGINEERING_WORKFLOW_PROFILES: Dict[str, Dict[str, Any]] = {
    "idle": {
        "aliases": ["idle", "bos", "waiting", "beklemede", "ready"],
        "workflow_state": "idle",
        "workflow_status": "pass",
        "workflow_summary": "Engineering coordinator idle. No active workflow. All systems nominal. Ready for task intake.",
        "health_score": 0.96,
        "risk_score": 0.04,
        "pipeline_stage": "idle",
        "active_subsystem": None,
        "pipeline_progress": {
            "completed": [],
            "current": None,
            "remaining": ENGINEERING_PIPELINE,
        },
        "recommended_next_action": "awaiting task intake — systems ready",
    },
    "analyzing": {
        "aliases": ["analyzing", "analiz", "investigating", "arastirma"],
        "workflow_state": "analyzing",
        "workflow_status": "pass",
        "workflow_summary": "Engineering coordinator in analysis phase. Task intake received. Workspace being analyzed. Repair planning pending.",
        "health_score": 0.88,
        "risk_score": 0.12,
        "pipeline_stage": "workspace_analysis",
        "active_subsystem": "workspace_intelligence",
        "pipeline_progress": {
            "completed": ["task_intake"],
            "current": "workspace_analysis",
            "remaining": ENGINEERING_PIPELINE[2:],
        },
        "recommended_next_action": "continue analysis — workspace intelligence active",
    },
    "repairing": {
        "aliases": ["repairing", "onarim", "fixing", "duzeltme"],
        "workflow_state": "repairing",
        "workflow_status": "pass",
        "workflow_summary": "Engineering coordinator in repair phase. Autonomous repair intelligence active. Repair strategies being evaluated.",
        "health_score": 0.78,
        "risk_score": 0.22,
        "pipeline_stage": "repair_planning",
        "active_subsystem": "autonomous_repair",
        "pipeline_progress": {
            "completed": ["task_intake", "workspace_analysis"],
            "current": "repair_planning",
            "remaining": ENGINEERING_PIPELINE[3:],
        },
        "recommended_next_action": "repair in progress — verification planning queued",
    },
    "verifying": {
        "aliases": ["verifying", "dogrulama", "testing", "test"],
        "workflow_state": "verifying",
        "workflow_status": "warning",
        "workflow_summary": "Engineering coordinator in verification phase. Verification intelligence active. Coverage and regression analysis in progress.",
        "health_score": 0.72,
        "risk_score": 0.30,
        "pipeline_stage": "verification_planning",
        "active_subsystem": "verification_intelligence",
        "pipeline_progress": {
            "completed": ["task_intake", "workspace_analysis", "repair_planning"],
            "current": "verification_planning",
            "remaining": ENGINEERING_PIPELINE[4:],
        },
        "recommended_next_action": "verification in progress — clone validation queued",
    },
    "clone_validating": {
        "aliases": ["clone", "klon", "validating", "validation"],
        "workflow_state": "clone_validating",
        "workflow_status": "warning",
        "workflow_summary": "Engineering coordinator in clone validation phase. Clone workspace intelligence active. Sync and integrity checks in progress.",
        "health_score": 0.68,
        "risk_score": 0.35,
        "pipeline_stage": "clone_validation",
        "active_subsystem": "clone_workspace",
        "pipeline_progress": {
            "completed": ["task_intake", "workspace_analysis", "repair_planning", "verification_planning"],
            "current": "clone_validation",
            "remaining": ENGINEERING_PIPELINE[5:],
        },
        "recommended_next_action": "clone validation in progress — deployment review queued",
    },
    "deployment_review": {
        "aliases": ["deployment", "deploy", "release", "surum"],
        "workflow_state": "deployment_review",
        "workflow_status": "warning",
        "workflow_summary": "Engineering coordinator in deployment review phase. Deployment verification intelligence active. Readiness and environment checks in progress.",
        "health_score": 0.62,
        "risk_score": 0.42,
        "pipeline_stage": "deployment_validation",
        "active_subsystem": "deployment_verification",
        "pipeline_progress": {
            "completed": [
                "task_intake", "workspace_analysis", "repair_planning",
                "verification_planning", "clone_validation",
            ],
            "current": "deployment_validation",
            "remaining": ENGINEERING_PIPELINE[6:],
        },
        "recommended_next_action": "deployment review in progress — delivery review queued",
    },
    "delivery_review": {
        "aliases": ["delivery", "teslimat", "final", "son"],
        "workflow_state": "delivery_review",
        "workflow_status": "pass",
        "workflow_summary": "Engineering coordinator in delivery review phase. All prior stages completed. Final readiness assessment in progress.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "pipeline_stage": "delivery_review",
        "active_subsystem": "coordinator",
        "pipeline_progress": {
            "completed": ENGINEERING_PIPELINE[:7],
            "current": "delivery_review",
            "remaining": ["completion"],
        },
        "recommended_next_action": "delivery review in progress — final completion pending",
    },
    "completed": {
        "aliases": ["completed", "tamamlandi", "done", "bitti", "finished"],
        "workflow_state": "completed",
        "workflow_status": "pass",
        "workflow_summary": "Engineering workflow completed successfully. All stages passed. Delivery authorized.",
        "health_score": 0.94,
        "risk_score": 0.06,
        "pipeline_stage": "completion",
        "active_subsystem": None,
        "pipeline_progress": {
            "completed": ENGINEERING_PIPELINE,
            "current": None,
            "remaining": [],
        },
        "recommended_next_action": "workflow completed — no action required",
    },
    "blocked": {
        "aliases": ["blocked", "engellendi", "stuck", "takildi"],
        "workflow_state": "blocked",
        "workflow_status": "blocked",
        "workflow_summary": "Engineering workflow blocked. Issue detected in active subsystem. Resolution required before continuation.",
        "health_score": 0.28,
        "risk_score": 0.82,
        "pipeline_stage": "blocked",
        "active_subsystem": "unknown",
        "pipeline_progress": {
            "completed": ["task_intake", "workspace_analysis"],
            "current": "blocked",
            "blocked_at": "repair_planning",
            "remaining": ENGINEERING_PIPELINE[3:],
        },
        "recommended_next_action": "workflow blocked — investigate and resolve blocking issue",
    },
    "recovery": {
        "aliases": ["recovery", "kurtarma", "restore", "geri_donus"],
        "workflow_state": "recovery",
        "workflow_status": "warning",
        "workflow_summary": "Engineering coordinator in recovery mode. Previous workflow encountered issues. Recovery procedures active.",
        "health_score": 0.35,
        "risk_score": 0.75,
        "pipeline_stage": "recovery",
        "active_subsystem": "recovery",
        "pipeline_progress": {
            "completed": [],
            "current": "recovery",
            "remaining": ENGINEERING_PIPELINE,
        },
        "recommended_next_action": "recovery active — restore point recovery in progress",
    },
}

# ---------- internal helpers ----------


def _select_workflow_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in ENGINEERING_WORKFLOW_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "idle"


def _compute_engineering_health(wid: str) -> Dict[str, Any]:
    p = ENGINEERING_WORKFLOW_PROFILES.get(wid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    # Gather health signals from all connected subsystems
    deploy_reg = deployment_verification_intelligence_registry()
    from clone_workspace_intelligence_preview import clone_workspace_intelligence_registry
    clone_reg = clone_workspace_intelligence_registry()
    ver_reg = verification_intelligence_registry()
    repair_reg = autonomous_repair_intelligence_registry()
    ws_status = workspace_intelligence_status()
    task_status = task_orchestration_intelligence_status()

    task_health = task_status.get("status") == "task_orchestration_ready"
    ws_health = ws_status.get("status") == "workspace_intelligence_ready"
    repair_health = repair_reg.get("status") == "autonomous_repair_registry_ready"
    ver_health = ver_reg.get("status") == "verification_intelligence_registry_ready"
    clone_health = clone_reg.get("status") == "clone_workspace_registry_ready"
    deploy_health = deploy_reg.get("status") == "deployment_verification_registry_ready"

    subsystem_count = sum([task_health, ws_health, repair_health, ver_health, clone_health, deploy_health])
    subsystem_health_ratio = subsystem_count / 6.0

    overall_health = round(health * 0.4 + subsystem_health_ratio * 0.6, 2)
    overall_risk = round(1.0 - overall_health, 2)
    overall_confidence = round(max(0.0, overall_health - overall_risk * 0.3), 2)

    return {
        "overall_engineering_health": overall_health,
        "overall_risk": overall_risk,
        "overall_confidence": overall_confidence,
        "subsystem_health": {
            "task_orchestration": "online" if task_health else "offline",
            "workspace_intelligence": "online" if ws_health else "offline",
            "autonomous_repair": "online" if repair_health else "offline",
            "verification_intelligence": "online" if ver_health else "offline",
            "clone_workspace": "online" if clone_health else "offline",
            "deployment_verification": "online" if deploy_health else "offline",
        },
        "online_subsystem_count": subsystem_count,
        "total_subsystem_count": 6,
    }


def _compute_dependency_flow(wid: str) -> Dict[str, Any]:
    p = ENGINEERING_WORKFLOW_PROFILES.get(wid, {})
    health = p.get("health_score", 0.50)

    dep_health = "healthy" if health > 0.70 else (
        "degraded" if health > 0.40 else "critical"
    )
    dep_risk = "low" if health > 0.70 else ("medium" if health > 0.40 else "high")

    return {
        "dependency_graph": {
            "35.0 → 34.9": "deployment_verification_depends_on_clone_workspace",
            "34.9 → 34.8": "clone_workspace_depends_on_verification",
            "34.8 → 34.7": "verification_depends_on_autonomous_repair",
            "34.7 → 34.6": "autonomous_repair_depends_on_workspace",
            "34.6 → 34.5": "workspace_depends_on_task_orchestration",
        },
        "dependency_health": dep_health,
        "dependency_risk": dep_risk,
        "cross_layer_dependencies": [
            "35.0_deployment_verification",
            "34.9_clone_workspace",
            "34.8_verification_intelligence",
            "34.7_autonomous_repair",
            "34.6_workspace_intelligence",
            "34.5_task_orchestration",
        ],
        "workflow_dependencies": [
            "task_intake_before_workspace",
            "workspace_before_repair",
            "repair_before_verification",
            "verification_before_clone",
            "clone_before_deployment",
            "deployment_before_delivery",
        ],
        "verification_dependencies": [
            "repair_complete_before_verification",
            "workspace_ready_before_verification",
        ],
        "deployment_dependencies": [
            "clone_validated_before_deployment",
            "verification_passed_before_deployment",
        ],
        "read_only": True,
        "preview_only": True,
    }


def _compute_delivery_orchestration(wid: str) -> Dict[str, Any]:
    p = ENGINEERING_WORKFLOW_PROFILES.get(wid, {})
    health = p.get("health_score", 0.50)

    deliverable = health > 0.70
    confidence = round(max(0.0, health * 0.9), 2)

    return {
        "delivery_confidence": confidence,
        "delivery_status": "ready" if deliverable else (
            "conditional" if health > 0.40 else "blocked"
        ),
        "delivery_summary": (
            "All engineering stages completed. Delivery authorized."
            if wid == "completed"
            else f"Engineering workflow in '{wid}' state. Delivery pending completion of current stage."
        ),
        "verification_summary": "All verification gates passed" if health > 0.70 else (
            "Verification gates pending" if health > 0.40 else "Verification gates failed"
        ),
        "deployment_summary": "Deployment validation passed" if health > 0.65 else (
            "Deployment validation pending" if health > 0.35 else "Deployment validation failed"
        ),
        "final_readiness": "go" if deliverable else ("conditional" if health > 0.40 else "no_go"),
        "pipeline_stage": "delivery_review",
        "read_only": True,
        "preview_only": True,
    }


def _compute_engineering_score(wid: str) -> Dict[str, float]:
    p = ENGINEERING_WORKFLOW_PROFILES.get(wid, {})
    health = p.get("health_score", 0.50)

    task_score = round(health * 0.85, 2)
    repair_score = round(health * 0.75, 2)
    ver_score = round(health * 0.80, 2)
    clone_score = round(health * 0.70, 2)
    deploy_score = round(health * 0.65, 2)
    eng_score = round(
        (task_score * 0.15 + repair_score * 0.20 + ver_score * 0.20
         + clone_score * 0.15 + deploy_score * 0.30),
        2,
    )

    return {
        "task_score": task_score,
        "repair_score": repair_score,
        "verification_score": ver_score,
        "clone_score": clone_score,
        "deployment_score": deploy_score,
        "engineering_score": eng_score,
    }


# ---------- public entry points ----------


def autonomous_engineering_coordinator_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.1",
        "name": "Autonomous Engineering Coordinator Preview",
        "status": "engineering_coordinator_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_COORDINATOR_CAPABILITIES,
        "pipeline": ENGINEERING_PIPELINE,
        "workflow_states": WORKFLOW_STATES,
        "workflow_profile_count": len(ENGINEERING_WORKFLOW_PROFILES),
        "operation_mode": "read_only_preview_only",
        "connected_layers": ["35.0", "34.9", "34.8", "34.7", "34.6", "34.5", "33.8"],
        "available_endpoints": [
            "/engineering-coordinator/status",
            "/engineering-coordinator/capabilities",
            "/engineering-coordinator/preview",
            "/engineering-coordinator/workflow",
            "/engineering-coordinator/health",
            "/engineering-coordinator/delivery-review",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "workflow_execution": False,
        "repair_execution": False,
        "deployment_execution": False,
        "file_modification": False,
        "system_modification": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering coordinator preview. No actual workflow execution or system modifications performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def autonomous_engineering_coordinator_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.1",
        "name": "Engineering Coordinator Capabilities",
        "status": "coordinator_capabilities_ready",
        "capabilities": [
            {"name": "task_chain_coordination", "description": "Coordinate the entire task chain from intake through delivery", "read_only": True},
            {"name": "workspace_coordination", "description": "Coordinate with workspace intelligence for analysis", "read_only": True},
            {"name": "repair_coordination", "description": "Coordinate with autonomous repair for strategy generation", "read_only": True},
            {"name": "verification_coordination", "description": "Coordinate with verification intelligence for validation", "read_only": True},
            {"name": "clone_coordination", "description": "Coordinate with clone workspace for isolation", "read_only": True},
            {"name": "deployment_coordination", "description": "Coordinate with deployment verification for release", "read_only": True},
            {"name": "delivery_coordination", "description": "Coordinate final delivery authorization", "read_only": True},
            {"name": "workflow_state_tracking", "description": "Track workflow state across all engineering stages", "read_only": True},
            {"name": "dependency_flow_tracking", "description": "Track cross-layer dependencies and workflow dependencies", "read_only": True},
            {"name": "engineering_health_analysis", "description": "Analyze engineering health across all subsystems", "read_only": True},
            {"name": "engineering_summary_generation", "description": "Generate comprehensive engineering summary", "read_only": True},
            {"name": "engineering_recommendation_engine", "description": "Generate engineering recommendations based on health and risk", "read_only": True},
        ],
        "pipeline": ENGINEERING_PIPELINE,
        "workflow_states": WORKFLOW_STATES,
        "connected_subsystems": [
            "task_orchestration",
            "workspace_intelligence",
            "autonomous_repair",
            "verification_intelligence",
            "clone_workspace",
            "deployment_verification",
        ],
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def autonomous_engineering_coordinator_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    wid = _select_workflow_profile(target_issue, command, project_area)
    w = ENGINEERING_WORKFLOW_PROFILES[wid]
    health = _compute_engineering_health(wid)
    score = _compute_engineering_score(wid)

    return {
        "workflow_id": wid,
        "workflow_state": w["workflow_state"],
        "workflow_status": w["workflow_status"],
        "workflow_summary": w.get("workflow_summary"),
        "health_score": w.get("health_score"),
        "risk_score": w.get("risk_score"),
        "pipeline_stage": w.get("pipeline_stage"),
        "active_subsystem": w.get("active_subsystem"),
        "pipeline_progress": w.get("pipeline_progress"),
        "engineering_health": health,
        "engineering_score": score,
        "recommended_next_action": w.get("recommended_next_action"),
        "read_only": True,
        "preview_only": True,
    }


def autonomous_engineering_coordinator_workflow(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    wid = _select_workflow_profile(target_issue)
    w = ENGINEERING_WORKFLOW_PROFILES.get(wid, {})
    dep_flow = _compute_dependency_flow(wid)

    return {
        "workflow_state": w.get("workflow_state"),
        "workflow_status": w.get("workflow_status"),
        "pipeline_stage": w.get("pipeline_stage"),
        "active_subsystem": w.get("active_subsystem"),
        "pipeline_progress": w.get("pipeline_progress"),
        "dependency_flow": dep_flow,
        "workflow_states_available": WORKFLOW_STATES,
        "read_only": True,
        "preview_only": True,
    }


def autonomous_engineering_coordinator_health(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    wid = _select_workflow_profile(target_issue)
    health = _compute_engineering_health(wid)
    score = _compute_engineering_score(wid)
    dep_flow = _compute_dependency_flow(wid)

    return {
        "engineering_health": health,
        "engineering_score": score,
        "dependency_flow": dep_flow,
        "read_only": True,
        "preview_only": True,
    }


def autonomous_engineering_coordinator_delivery_review(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    wid = _select_workflow_profile(target_issue)
    w = ENGINEERING_WORKFLOW_PROFILES.get(wid, {})
    delivery = _compute_delivery_orchestration(wid)
    score = _compute_engineering_score(wid)
    health = _compute_engineering_health(wid)

    return {
        "delivery_orchestration": delivery,
        "engineering_score": score,
        "engineering_health": health,
        "workflow_state": w.get("workflow_state"),
        "completed_stages": w.get("pipeline_progress", {}).get("completed", []),
        "remaining_stages": w.get("pipeline_progress", {}).get("remaining", []),
        "read_only": True,
        "preview_only": True,
    }


def autonomous_engineering_coordinator_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for wid, w in ENGINEERING_WORKFLOW_PROFILES.items():
        items.append({
            "workflow_id": wid,
            "workflow_state": w["workflow_state"],
            "workflow_status": w["workflow_status"],
            "health_score": w.get("health_score"),
            "risk_score": w.get("risk_score"),
            "pipeline_stage": w.get("pipeline_stage"),
            "active_subsystem": w.get("active_subsystem"),
        })
    return {
        "layer": "35.1",
        "name": "Engineering Coordinator Registry",
        "status": "coordinator_registry_ready",
        "read_only": True,
        "preview_only": True,
        "workflow_count": len(items),
        "workflow_profiles": items,
        "pass_count": sum(1 for i in items if i["workflow_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["workflow_status"] == "warning"),
        "blocked_count": sum(1 for i in items if i["workflow_status"] == "blocked"),
        "connected_subsystems": [
            "task_orchestration", "workspace_intelligence", "autonomous_repair",
            "verification_intelligence", "clone_workspace", "deployment_verification",
        ],
    }
