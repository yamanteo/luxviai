from __future__ import annotations

from typing import Any, Dict

from layer31_status_snapshot import layer31_status_snapshot, layer31_full_status
from layer32_status_snapshot import layer32_status_snapshot, layer32_full_status
from change_memory_intelligence_preview import change_memory_intelligence_status
from failed_change_intelligence_preview import failed_change_intelligence_status
from change_planning_intelligence_preview import change_planning_intelligence_status
# lazy import: clone_workspace_intelligence_status imported inside function
from sandbox_repair_intelligence_preview import sandbox_repair_intelligence_status
# lazy import: verification_intelligence_status imported inside function
from delivery_readiness_intelligence_preview import delivery_readiness_intelligence_status


CORE_VERSION = "LuxCode Core v1"
IMPLEMENTED_COMPONENTS = [
    "31 Runtime Intelligence Suite (31.1–31.5)",
    "32 Failure Intelligence Suite (32.1–32.5)",
    "33.1 Change Memory Intelligence Preview",
    "33.2 Failed Change Intelligence Preview",
    "33.3 Change Planning Intelligence Preview",
    "33.4 Clone Workspace Intelligence Preview",
    "33.5 Sandbox Repair Intelligence Preview",
    "33.6 Verification Intelligence Preview",
    "33.7 Delivery Readiness Intelligence Preview",
]

CORE_ENDPOINTS = [
    # Layer 31
    "/debug/system-health-status", "/debug/system-health-registry", "/debug/system-health-preview",
    "/debug/runtime-stability-status", "/debug/runtime-stability-registry", "/debug/runtime-stability-preview",
    "/debug/runtime-risk-status", "/debug/runtime-risk-registry", "/debug/runtime-risk-preview",
    "/debug/runtime-drift-status", "/debug/runtime-drift-registry", "/debug/runtime-drift-preview",
    "/debug/runtime-recovery-status", "/debug/runtime-recovery-registry", "/debug/runtime-recovery-preview",
    "/debug/layer31-status", "/debug/layer31-full-status",
    # Layer 32
    "/debug/runtime-anomaly-status", "/debug/runtime-anomaly-registry", "/debug/runtime-anomaly-preview",
    "/debug/regression-status", "/debug/regression-registry", "/debug/regression-preview",
    "/debug/failure-memory-status", "/debug/failure-memory-registry", "/debug/failure-memory-preview",
    "/debug/root-cause-status", "/debug/root-cause-registry", "/debug/root-cause-preview",
    "/debug/dependency-status", "/debug/dependency-registry", "/debug/dependency-preview",
    "/debug/layer32-status", "/debug/layer32-full-status",
    # Layer 33
    "/debug/change-memory-status", "/debug/change-memory-registry", "/debug/change-memory-preview",
    "/debug/failed-change-status", "/debug/failed-change-registry", "/debug/failed-change-preview",
    "/debug/change-planning-status", "/debug/change-planning-registry", "/debug/change-planning-preview",
    "/debug/clone-workspace-status", "/debug/clone-workspace-registry", "/debug/clone-workspace-preview",
    "/debug/sandbox-repair-status", "/debug/sandbox-repair-registry", "/debug/sandbox-repair-preview",
    "/debug/verification-status", "/debug/verification-registry", "/debug/verification-preview",
    "/debug/delivery-readiness-status", "/debug/delivery-readiness-registry", "/debug/delivery-readiness-preview",
    # Core snapshot
    "/debug/luxcode-core-status", "/debug/luxcode-core-health", "/debug/luxcode-core-readiness",
]

CONNECTED_LAYERS = [
    "30.5 Release Readiness Preview",
    "30.4 Validation Readiness Preview",
    "30.3 System Readiness Preview",
    "30.2 Operational Readiness Preview",
    "30.1 Production Readiness Preview",
    "29.8 Patch Confidence Preview",
    "29.7 Patch Assurance Preview",
    "29.6 Patch Accountability Preview",
    "29.5 Patch Oversight Preview",
    "29.4 Patch Governance Preview",
    "29.3 Patch Compliance Preview",
    "29.2 Patch Policy Evaluation Preview",
    "29.1 Patch Permission Enforcement Preview",
]


def _collect_core_statuses() -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    # Layer 31
    l31 = layer31_full_status()
    result["31_runtime_intelligence"] = {
        "name": "Runtime Intelligence Suite",
        "status": l31.get("overall_runtime_status"),
        "score": l31.get("overall_runtime_score"),
        "layer_count": l31.get("layer_count"),
        "complete": l31.get("layer_31_complete"),
    }

    # Layer 32
    l32 = layer32_full_status()
    result["32_failure_intelligence"] = {
        "name": "Failure Intelligence Suite",
        "status": l32.get("overall_layer32_status"),
        "score": l32.get("overall_layer32_score"),
        "layer_count": l32.get("layer_count"),
        "complete": l32.get("layer_32_complete"),
    }

    # Layer 33 components
    cm = change_memory_intelligence_status()
    result["33_1_change_memory"] = {
        "name": "Change Memory Intelligence",
        "status": cm.get("status"),
        "score": None,
    }

    fc = failed_change_intelligence_status()
    result["33_2_failed_change"] = {
        "name": "Failed Change Intelligence",
        "status": fc.get("status"),
        "score": None,
    }

    cp = change_planning_intelligence_status()
    result["33_3_change_planning"] = {
        "name": "Change Planning Intelligence",
        "status": cp.get("status"),
        "score": None,
    }

    from clone_workspace_intelligence_preview import clone_workspace_intelligence_status
    cw = clone_workspace_intelligence_status()
    result["33_4_clone_workspace"] = {
        "name": "Clone Workspace Intelligence",
        "status": cw.get("status"),
        "score": None,
    }

    sr = sandbox_repair_intelligence_status()
    result["33_5_sandbox_repair"] = {
        "name": "Sandbox Repair Intelligence",
        "status": sr.get("status"),
        "score": None,
    }

    from verification_intelligence_preview import verification_intelligence_status
    vi = verification_intelligence_status()
    result["33_6_verification"] = {
        "name": "Verification Intelligence",
        "status": vi.get("status"),
        "score": None,
    }

    dr = delivery_readiness_intelligence_status()
    result["33_7_delivery_readiness"] = {
        "name": "Delivery Readiness Intelligence",
        "status": dr.get("status"),
        "score": None,
    }

    return result


def _compute_health_score() -> float:
    l31 = layer31_full_status()
    l32 = layer32_full_status()
    overall = 0.0
    count = 0
    if l31.get("overall_runtime_score"):
        overall += float(l31["overall_runtime_score"])
        count += 1
    if l32.get("overall_layer32_score"):
        overall += float(l32["overall_layer32_score"])
        count += 1
    return round(overall / count, 2) if count else 0.0


def _compute_readiness_score() -> float:
    dr = delivery_readiness_intelligence_status()
    if dr.get("status") == "delivery_readiness_intelligence_ready":
        return 0.72
    return 0.45


def _compute_coverage_score(endpoint_count: int) -> float:
    if endpoint_count >= 70:
        return 0.92
    elif endpoint_count >= 50:
        return 0.78
    elif endpoint_count >= 30:
        return 0.60
    return 0.40


def luxcode_core_status_snapshot() -> Dict[str, Any]:
    statuses = _collect_core_statuses()
    total_endpoints = len(CORE_ENDPOINTS)
    total_components = len(IMPLEMENTED_COMPONENTS)
    health_score = _compute_health_score()
    readiness_score = _compute_readiness_score()
    coverage_score = _compute_coverage_score(total_endpoints)
    completion_score = round(
        (sum(1 for s in statuses.values() if s.get("status") and "ready" in str(s.get("status", "")))
         / total_components) * 100, 1
    ) if total_components else 0.0

    return {
        "core_version": CORE_VERSION,
        "core_status": "luxcode_core_v1_ready",
        "core_health_score": health_score,
        "core_readiness_score": readiness_score,
        "runtime_status": statuses.get("31_runtime_intelligence", {}).get("status"),
        "failure_status": statuses.get("32_failure_intelligence", {}).get("status"),
        "change_status": statuses.get("33_1_change_memory", {}).get("status"),
        "clone_status": statuses.get("33_4_clone_workspace", {}).get("status"),
        "sandbox_status": statuses.get("33_5_sandbox_repair", {}).get("status"),
        "verification_status": statuses.get("33_6_verification", {}).get("status"),
        "delivery_status": statuses.get("33_7_delivery_readiness", {}).get("status"),
        "endpoint_count": total_endpoints,
        "integration_count": len(CONNECTED_LAYERS),
        "coverage_score": coverage_score,
        "layer_completion_score": completion_score,
        "implemented_components": IMPLEMENTED_COMPONENTS,
        "component_statuses": statuses,
        "connected_layers": CONNECTED_LAYERS,
        "all_read_only": True,
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "recommended_next_layer": "Layer 34 — LuxCode Production Pipeline or cross-layer remediation activation",
        "recommended_next_action": "review core health score and address degraded components before proceeding to Layer 34",
        "future_candidates": [
            "Layer 34 — LuxCode Production Pipeline",
            "Cross-layer automated remediation activation",
            "Real-time health monitoring dashboard",
            "Production deployment pipeline integration",
        ],
    }


def luxcode_core_health() -> Dict[str, Any]:
    base = luxcode_core_status_snapshot()
    statuses = _collect_core_statuses()

    component_health: Dict[str, Any] = {}
    for cid, c in statuses.items():
        cstatus = str(c.get("status", ""))
        component_health[cid] = {
            "name": c.get("name"),
            "status": cstatus,
            "healthy": "ready" in cstatus and "degraded" not in cstatus and "blocked" not in cstatus,
        }

    healthy_count = sum(1 for h in component_health.values() if h["healthy"])
    total = len(component_health)
    health_ratio = round(healthy_count / total, 2) if total else 0.0

    return {
        **base,
        "health_detail": {
            "overall_health_ratio": health_ratio,
            "healthy_components": healthy_count,
            "total_components": total,
            "component_health": component_health,
            "health_threshold": 0.7,
            "health_status": "pass" if health_ratio >= 0.7 else "degraded",
        },
        "read_only": True,
    }


def luxcode_core_readiness() -> Dict[str, Any]:
    base = luxcode_core_status_snapshot()

    delivery = delivery_readiness_intelligence_status()
    from verification_intelligence_preview import verification_intelligence_status
    verification = verification_intelligence_status()
    sandbox = sandbox_repair_intelligence_status()

    delivery_ready = delivery.get("status") == "delivery_readiness_intelligence_ready"
    verification_ready = verification.get("status") == "verification_intelligence_ready"
    sandbox_ready = sandbox.get("status") == "sandbox_repair_intelligence_ready"

    readiness_status = "ready"
    if not delivery_ready:
        readiness_status = "delivery_not_ready"
    elif not verification_ready:
        readiness_status = "verification_not_ready"
    elif not sandbox_ready:
        readiness_status = "sandbox_not_ready"

    return {
        **base,
        "readiness_detail": {
            "delivery_engine_ready": delivery_ready,
            "verification_engine_ready": verification_ready,
            "sandbox_repair_engine_ready": sandbox_ready,
            "readiness_status": readiness_status,
            "readiness_requirements": [
                "sandbox_repair_engine",
                "verification_engine",
                "delivery_readiness_engine",
            ],
            "requirements_met": sum([sandbox_ready, verification_ready, delivery_ready]),
            "requirements_total": 3,
        },
        "read_only": True,
    }
