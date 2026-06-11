from __future__ import annotations

from typing import Any, Dict, List, Optional

# lazy import: verification_intelligence_registry imported inside function
# all below: lazy imports inside functions
# lazy import: luxcode_core_status_snapshot imported inside function


CLONE_CAPABILITIES = [
    "clone_workspace_mapping",
    "clone_workspace_generation_preview",
    "clone_sync_analysis",
    "clone_integrity_validation",
    "workspace_difference_analysis",
    "safe_transfer_planning",
    "rollback_restore_planning",
    "clone_health_analysis",
    "clone_dependency_mapping",
    "clone_conflict_detection",
    "clone_recovery_simulation",
    "clone_summary_generation",
]

CLONE_PIPELINE = [
    "project_detection",
    "clone_planning",
    "clone_validation",
    "workspace_analysis",
    "repair_workspace",
    "verification",
    "transfer_planning",
    "production_validation",
    "delivery",
]

CLONE_WORKSPACE_PROFILES: Dict[str, Dict[str, Any]] = {
    "clean_clone": {
        "aliases": ["clean", "temiz", "fresh", "yeni", "new"],
        "workspace_type": "clean_clone",
        "workspace_status": "pass",
        "workspace_summary": "Clean clone workspace. Fully synced with production. No modifications detected. Ready for verification pipeline.",
        "health_score": 0.98,
        "risk_score": 0.02,
        "sync_status": "synced",
        "integrity_status": "pass",
        "cloned_from": "production_master",
        "recommended_actions": ["ready_for_verification", "proceed_with_analysis"],
        "recommended_next_action": "clone ready — proceed with verification pipeline",
        "confidence_score": 0.96,
        "workspace_signals": {
            "clone_created": True,
            "clone_isolated": True,
            "files_synced": True,
            "config_synced": True,
            "dependencies_synced": True,
            "production_impact_allowed": False,
            "modifications_detected": False,
            "drift_detected": False,
            "conflicts_detected": False,
        },
    },
    "active_clone": {
        "aliases": ["active", "aktif", "working", "calisan", "in_progress"],
        "workspace_type": "active_clone",
        "workspace_status": "pass",
        "workspace_summary": "Active clone with ongoing analysis. Workspace isolated from production. Changes monitored. Continue with analysis.",
        "health_score": 0.84,
        "risk_score": 0.18,
        "sync_status": "active",
        "integrity_status": "pass",
        "cloned_from": "production_master",
        "recommended_actions": ["continue_analysis", "monitor_sync_health"],
        "recommended_next_action": "active clone — continue workspace analysis",
        "confidence_score": 0.82,
        "workspace_signals": {
            "clone_created": True,
            "clone_isolated": True,
            "files_synced": True,
            "config_synced": True,
            "dependencies_synced": True,
            "production_impact_allowed": False,
            "modifications_detected": False,
            "drift_detected": False,
            "conflicts_detected": False,
        },
    },
    "modified_clone": {
        "aliases": ["modified", "degismis", "changed", "degisti", "patched"],
        "workspace_type": "modified_clone",
        "workspace_status": "warning",
        "workspace_summary": "Clone contains modifications. Changes isolated from production. Verification required before transfer.",
        "health_score": 0.72,
        "risk_score": 0.35,
        "sync_status": "active",
        "integrity_status": "warning",
        "cloned_from": "production_master",
        "recommended_actions": ["verification_required", "run_difference_analysis"],
        "recommended_next_action": "modifications detected — run verification pipeline",
        "confidence_score": 0.68,
        "workspace_signals": {
            "clone_created": True,
            "clone_isolated": True,
            "files_synced": True,
            "config_synced": True,
            "dependencies_synced": True,
            "production_impact_allowed": False,
            "modifications_detected": True,
            "modification_count": 3,
            "drift_detected": False,
            "conflicts_detected": False,
        },
    },
    "drift_detected": {
        "aliases": ["drift", "kayma", "divergence", "sync_gap"],
        "workspace_type": "drift_detected",
        "workspace_status": "warning",
        "workspace_summary": "Workspace drift detected between clone and production. Sync review required before proceeding.",
        "health_score": 0.50,
        "risk_score": 0.68,
        "sync_status": "degraded",
        "integrity_status": "warning",
        "cloned_from": "production_master",
        "recommended_actions": ["sync_review_required", "run_sync_analysis"],
        "recommended_next_action": "drift detected — run sync analysis and review",
        "confidence_score": 0.52,
        "workspace_signals": {
            "clone_created": True,
            "clone_isolated": True,
            "files_synced": False,
            "config_synced": True,
            "dependencies_synced": False,
            "production_impact_allowed": False,
            "modifications_detected": True,
            "modification_count": 5,
            "drift_detected": True,
            "drift_items": ["file_divergence", "dependency_version_mismatch"],
            "conflicts_detected": False,
        },
    },
    "conflict_detected": {
        "aliases": ["conflict", "catisma", "merge", "birlestirme"],
        "workspace_type": "conflict_detected",
        "workspace_status": "blocked",
        "workspace_summary": "Conflicts detected between clone changes and production state. Manual resolution required.",
        "health_score": 0.35,
        "risk_score": 0.82,
        "sync_status": "blocked",
        "integrity_status": "fail",
        "cloned_from": "production_master",
        "recommended_actions": ["manual_resolution_required", "run_conflict_analysis"],
        "recommended_next_action": "conflict detected — manual resolution required",
        "confidence_score": 0.38,
        "workspace_signals": {
            "clone_created": True,
            "clone_isolated": True,
            "files_synced": False,
            "config_synced": False,
            "dependencies_synced": False,
            "production_impact_allowed": False,
            "modifications_detected": True,
            "modification_count": 8,
            "drift_detected": True,
            "drift_items": ["file_divergence", "config_divergence", "dependency_conflict"],
            "conflicts_detected": True,
            "conflict_items": ["file_overlap", "config_mismatch", "dependency_conflict"],
        },
    },
    "recovery_mode": {
        "aliases": ["recovery", "kurtarma", "restore", "geri_yukle", "rebuild"],
        "workspace_type": "recovery_mode",
        "workspace_status": "blocked",
        "workspace_summary": "Clone in recovery mode. Workspace state needs restoration. Rebuild or restore required before further use.",
        "health_score": 0.22,
        "risk_score": 0.90,
        "sync_status": "blocked",
        "integrity_status": "fail",
        "cloned_from": "production_master",
        "recommended_actions": [
            "restore_clone_state",
            "run_recovery_simulation",
            "prepare_rebuild_plan",
        ],
        "recommended_next_action": "recovery mode — restore clone state or rebuild",
        "confidence_score": 0.25,
        "workspace_signals": {
            "clone_created": True,
            "clone_isolated": True,
            "files_synced": False,
            "config_synced": False,
            "dependencies_synced": False,
            "production_impact_allowed": False,
            "modifications_detected": True,
            "modification_count": 12,
            "drift_detected": True,
            "conflicts_detected": True,
            "recovery_available": True,
            "restore_points_available": 3,
        },
    },
}

# ---------- internal helpers ----------


def _select_clone_workspace_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in CLONE_WORKSPACE_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "clean_clone"


def _compute_overall_clone_status(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "unknown"
    statuses = [i.get("workspace_status", "") for i in items]
    if any(s == "blocked" for s in statuses):
        return "blocked"
    if any(s == "warning" for s in statuses):
        return "warning"
    if all(s == "pass" for s in statuses):
        return "pass"
    return "warning"


def _compute_avg_score(items: List[Dict[str, Any]], key: str) -> float:
    scores = [i.get(key, 0.0) for i in items if i.get(key) is not None]
    return round(sum(scores) / len(scores), 2) if scores else 0.0


def _compute_clone_health_scores(pid: str) -> Dict[str, float]:
    p = CLONE_WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    ws_health = round(health * 0.95, 2)
    sync_health = round(health * 0.85, 2)
    ver_health = round(health * 0.80, 2)
    transfer_health = round(health * 0.75, 2)
    overall = round(
        (ws_health * 0.3 + sync_health * 0.25 + ver_health * 0.25 + transfer_health * 0.20), 2
    )
    return {
        "workspace_health": ws_health,
        "sync_health": sync_health,
        "verification_health": ver_health,
        "transfer_health": transfer_health,
        "overall_clone_health": overall,
    }


def _compute_sync_analysis(pid: str) -> Dict[str, Any]:
    p = CLONE_WORKSPACE_PROFILES.get(pid, {})
    signals = p.get("workspace_signals", {})
    health = p.get("health_score", 0.50)
    sync_status = p.get("sync_status", "unknown")

    return {
        "sync_status": sync_status,
        "sync_health": "pass" if health > 0.70 else ("warning" if health > 0.40 else "fail"),
        "sync_conflicts": (
            [] if sync_status != "blocked"
            else ["file_sync_conflict", "dependency_sync_conflict"]
        ),
        "sync_recommendation": (
            "no_action_required" if health > 0.80
            else "sync_review_required" if health > 0.40
            else "full_resync_required"
        ),
        "added_files": [] if signals.get("files_synced") else ["new_config.yaml"],
        "removed_files": [] if signals.get("files_synced") else ["deprecated_module.py"],
        "modified_files": (
            [] if not signals.get("modifications_detected")
            else [f"file_{i}" for i in range(1, (signals.get("modification_count", 0) or 1) + 1)]
        ),
        "dependency_changes": (
            [] if signals.get("dependencies_synced")
            else ["dependency_version_bump"]
        ),
        "configuration_changes": (
            [] if signals.get("config_synced")
            else ["config_value_update"]
        ),
    }


def _compute_difference_analysis(pid: str) -> Dict[str, Any]:
    p = CLONE_WORKSPACE_PROFILES.get(pid, {})
    signals = p.get("workspace_signals", {})
    health = p.get("health_score", 0.50)

    scope = "none" if health > 0.80 else ("partial" if health > 0.40 else "full")
    diff_score = round(max(0.0, 1.0 - health), 2)

    return {
        "difference_score": diff_score,
        "affected_files": ["src/main.py", "src/config.py"] if diff_score > 0.20 else [],
        "affected_modules": ["core", "api"] if diff_score > 0.20 else [],
        "affected_dependencies": ["requests", "flask"] if diff_score > 0.30 else [],
        "transfer_scope": scope,
        "read_only": True,
        "preview_only": True,
    }


def _compute_conflict_analysis(pid: str) -> Dict[str, Any]:
    p = CLONE_WORKSPACE_PROFILES.get(pid, {})
    signals = p.get("workspace_signals", {})
    health = p.get("health_score", 0.50)

    conflict_risk = "low" if health > 0.70 else ("medium" if health > 0.40 else "high")
    return {
        "conflict_risk": conflict_risk,
        "conflict_summary": (
            "No conflicts detected" if conflict_risk == "low"
            else "Conflicts detected requiring resolution" if conflict_risk == "medium"
            else "Critical conflicts detected — manual resolution required"
        ),
        "resolution_complexity": "simple" if conflict_risk == "low" else (
            "moderate" if conflict_risk == "medium" else "complex"
        ),
        "workspace_drift": signals.get("drift_detected", False),
        "simultaneous_changes": signals.get("modifications_detected", False)
                               and signals.get("drift_detected", False),
        "dependency_conflicts": not signals.get("dependencies_synced", True),
        "configuration_conflicts": not signals.get("config_synced", True),
        "file_conflicts": signals.get("conflicts_detected", False),
        "read_only": True,
        "preview_only": True,
    }


def _compute_transfer_plan(pid: str) -> Dict[str, Any]:
    p = CLONE_WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    risk = p.get("risk_score", 0.50)

    transfer_confidence = round(max(0.0, health * 0.9 - risk * 0.1), 2)
    return {
        "transfer_confidence": transfer_confidence,
        "verification_requirements": (
            "full_verification_pipeline" if health < 0.70
            else "standard_verification"
        ),
        "deployment_readiness": "ready" if health > 0.70 else (
            "conditional" if health > 0.40 else "blocked"
        ),
        "transfer_plan": [
            "validate_clone_integrity",
            "run_verification_gates",
            "prepare_rollback_plan",
            "execute_transfer_preview",
        ],
        "verification_plan": [
            "run_smoke_tests",
            "verify_dependency_integrity",
            "run_regression_checks",
        ],
        "rollback_plan": [
            "restore_from_last_sync_point",
            "rebuild_clone_from_master",
        ],
        "safety_checks": [
            "production_impact_assessment",
            "rollback_path_verification",
            "deployment_gate_review",
        ],
        "read_only": True,
        "preview_only": True,
    }


def _compute_recovery_plan(pid: str) -> Dict[str, Any]:
    p = CLONE_WORKSPACE_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    signals = p.get("workspace_signals", {})

    recovery_confidence = round(max(0.0, health * 0.8), 2)
    recovery_complexity = "simple" if health > 0.60 else ("moderate" if health > 0.30 else "complex")

    return {
        "recovery_confidence": recovery_confidence,
        "recovery_complexity": recovery_complexity,
        "restore_points": (
            signals.get("restore_points_available", 0)
        ),
        "recovery_paths": [
            "restore_from_latest_sync_point",
            "restore_from_last_good_state",
            "full_rebuild_from_master",
        ],
        "rollback_options": [
            "discard_clone_and_rebuild",
            "apply_incremental_rollback",
            "full_system_restore",
        ],
        "clone_rebuild_plan": [
            "discard_current_clone",
            "create_fresh_clone_from_master",
            "reapply_verified_changes",
        ],
        "read_only": True,
        "preview_only": True,
    }


def _build_integration_signals(
    target: str, command: str, project_area: str, related_layer: str
) -> Dict[str, Any]:
    L = related_layer or "Layer 34.9"
    from verification_intelligence_preview import verification_intelligence_registry
    from autonomous_repair_intelligence_preview import autonomous_repair_intelligence_registry
    from device_action_intelligence_preview import device_action_intelligence_registry
    from deployment_bridge_intelligence_preview import deployment_bridge_intelligence_registry
    from terminal_bridge_intelligence_preview import terminal_bridge_intelligence_registry
    from github_bridge_intelligence_preview import github_bridge_intelligence_registry
    ver_reg = verification_intelligence_registry()
    auto_reg = autonomous_repair_intelligence_registry()
    device_reg = device_action_intelligence_registry()
    deploy_reg = deployment_bridge_intelligence_registry()
    terminal_reg = terminal_bridge_intelligence_registry()
    github_reg = github_bridge_intelligence_registry()

    return {
        "layer34_8_verification_intelligence": {
            "verification_count": ver_reg.get("verification_count"),
            "overall_verification_score": ver_reg.get("overall_verification_score"),
        },
        "layer34_7_autonomous_repair_intelligence": {
            "issue_profiles": auto_reg.get("issue_profiles"),
        },
        "layer34_4_device_action_intelligence": {
            "profile_count": device_reg.get("profile_count"),
        },
        "layer34_3_deployment_bridge_intelligence": {
            "profile_count": deploy_reg.get("profile_count"),
        },
        "layer34_2_terminal_bridge_intelligence": {
            "profile_count": terminal_reg.get("profile_count"),
        },
        "layer34_1_github_bridge_intelligence": {
            "profile_count": github_reg.get("profile_count"),
        },
        "related_layer": L,
        "target": target,
        "command": command,
        "project_area": project_area,
    }


# ---------- backward-compatible public entry points ----------


def clone_workspace_intelligence_status() -> Dict[str, Any]:
    from luxcode_core_status_snapshot import luxcode_core_status_snapshot
    core = luxcode_core_status_snapshot()
    return {
        "layer": "34.9",
        "name": "Clone Workspace Intelligence Preview",
        "status": "clone_workspace_ready",
        "version": "1.0",
        "capabilities": CLONE_CAPABILITIES,
        "pipeline": CLONE_PIPELINE,
        "workspace_architecture": {
            "real_project": "source_of_truth",
            "clone_workspace": "all_changes_here",
            "analysis": "read_only",
            "verification": "all_gates",
            "production_transfer": "after_verification",
        },
        "clone_philosophy": "never_modify_primary_project_first_always_use_clone",
        "profile_count": len(CLONE_WORKSPACE_PROFILES),
        "operation_mode": "read_only_preview_only",
        "connected_layers": [
            "34.8", "34.7", "34.6", "34.5",
            "34.4", "34.3", "34.2", "34.1", "33.8",
        ],
        "available_endpoints": [
            "/clone-workspace/status",
            "/clone-workspace/capabilities",
            "/clone-workspace/preview",
            "/clone-workspace/difference-analysis",
            "/clone-workspace/sync-analysis",
            "/clone-workspace/conflict-analysis",
            "/clone-workspace/transfer-plan",
            "/clone-workspace/recovery-plan",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "clone_creation": False,
        "workspace_modification": False,
        "transfer_execution": False,
        "rollback_execution": False,
        "file_modification": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only clone workspace intelligence preview. No actual clone or workspace modification actions performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def clone_workspace_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for wid, w in CLONE_WORKSPACE_PROFILES.items():
        items.append({
            "workspace_id": wid,
            "workspace_type": w["workspace_type"],
            "workspace_status": w["workspace_status"],
            "health_score": w.get("health_score"),
            "risk_score": w.get("risk_score"),
            "sync_status": w.get("sync_status"),
            "integrity_status": w.get("integrity_status"),
            "confidence_score": w["confidence_score"],
        })
    return {
        "layer": "34.9",
        "name": "Clone Workspace Intelligence Registry",
        "status": "clone_workspace_registry_ready",
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "workspace_count": len(items),
        "workspace_items": items,
        "pass_count": sum(1 for i in items if i["workspace_status"] == "pass"),
        "warning_count": sum(1 for i in items if i["workspace_status"] == "warning"),
        "blocked_count": sum(1 for i in items if i["workspace_status"] == "blocked"),
        "overall_clone_status": _compute_overall_clone_status(items),
        "avg_health_score": _compute_avg_score(items, "health_score"),
        "avg_confidence_score": _compute_avg_score(items, "confidence_score"),
        "sync_states": {
            "synced": sum(1 for i in items if i.get("sync_status") == "synced"),
            "active": sum(1 for i in items if i.get("sync_status") == "active"),
            "degraded": sum(1 for i in items if i.get("sync_status") == "degraded"),
            "blocked": sum(1 for i in items if i.get("sync_status") == "blocked"),
        },
    }


def build_clone_workspace_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
    related_layer: Optional[str] = None,
) -> Dict[str, Any]:
    wid = _select_clone_workspace_profile(target_issue, command, project_area)
    w = CLONE_WORKSPACE_PROFILES[wid]
    detected = target_issue or project_area or wid
    cmd = command or detected
    L = related_layer or "Layer 34.9"

    integration = _build_integration_signals(detected, cmd, project_area or detected, L)
    health = _compute_clone_health_scores(wid)

    return {
        "workspace_id": wid,
        "workspace_type": w["workspace_type"],
        "workspace_status": w["workspace_status"],
        "workspace_summary": w.get("workspace_summary"),
        "health_score": w.get("health_score"),
        "risk_score": w.get("risk_score"),
        "sync_status": w.get("sync_status"),
        "integrity_status": w.get("integrity_status"),
        "clone_health_scores": health,
        "workspace_signals": w.get("workspace_signals", {}),
        "required_actions": w.get("recommended_actions", []),
        "recommended_next_action": w.get("recommended_next_action"),
        "confidence_score": w["confidence_score"],
        "pipeline_stage": "clone_planning",
        "pipeline_progress": {
            "completed": [],
            "current": "clone_planning",
            "remaining": CLONE_PIPELINE[1:],
        },
        "integration_signals": integration,
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "clone_creation": False,
        "workspace_modification": False,
        "transfer_execution": False,
        "rollback_execution": False,
        "file_modification": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "safety_note": "Read-only clone workspace intelligence preview. No actual clone or workspace modification actions performed.",
    }


# ---------- new Layer 34.9 public entry points ----------


def clone_workspace_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "34.9",
        "name": "Clone Workspace Intelligence Capabilities",
        "status": "clone_capabilities_ready",
        "capabilities": [
            {
                "name": "clone_workspace_mapping",
                "description": "Map clone workspace structure and relationships",
                "read_only": True,
            },
            {
                "name": "clone_workspace_generation_preview",
                "description": "Preview clone workspace generation without execution",
                "read_only": True,
            },
            {
                "name": "clone_sync_analysis",
                "description": "Analyze clone sync status and detect sync gaps",
                "read_only": True,
            },
            {
                "name": "clone_integrity_validation",
                "description": "Validate clone integrity and isolation",
                "read_only": True,
            },
            {
                "name": "workspace_difference_analysis",
                "description": "Analyze differences between clone and production",
                "read_only": True,
            },
            {
                "name": "safe_transfer_planning",
                "description": "Plan safe transfer from clone to production",
                "read_only": True,
            },
            {
                "name": "rollback_restore_planning",
                "description": "Plan rollback and restore paths",
                "read_only": True,
            },
            {
                "name": "clone_health_analysis",
                "description": "Analyze clone health across workspace, sync, verification, transfer",
                "read_only": True,
            },
            {
                "name": "clone_dependency_mapping",
                "description": "Map clone dependencies and their sync state",
                "read_only": True,
            },
            {
                "name": "clone_conflict_detection",
                "description": "Detect conflicts between clone and production",
                "read_only": True,
            },
            {
                "name": "clone_recovery_simulation",
                "description": "Simulate clone recovery and restoration",
                "read_only": True,
            },
            {
                "name": "clone_summary_generation",
                "description": "Generate comprehensive clone workspace summary",
                "read_only": True,
            },
        ],
        "pipeline": CLONE_PIPELINE,
        "profiles_available": list(CLONE_WORKSPACE_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def clone_workspace_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    return build_clone_workspace_intelligence_preview(target_issue, command, project_area)


def clone_workspace_intelligence_difference_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_clone_workspace_profile(target_issue)
    return _compute_difference_analysis(pid)


def clone_workspace_intelligence_sync_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_clone_workspace_profile(target_issue)
    return _compute_sync_analysis(pid)


def clone_workspace_intelligence_conflict_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_clone_workspace_profile(target_issue)
    return _compute_conflict_analysis(pid)


def clone_workspace_intelligence_transfer_plan(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_clone_workspace_profile(target_issue)
    return _compute_transfer_plan(pid)


def clone_workspace_intelligence_recovery_plan(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_clone_workspace_profile(target_issue)
    return _compute_recovery_plan(pid)
