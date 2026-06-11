from __future__ import annotations

from typing import Any, Dict, List, Optional

from engineering_memory_failure_intelligence_preview import (
    engineering_memory_intelligence_registry,
)
from autonomous_engineering_coordinator_preview import (
    autonomous_engineering_coordinator_registry,
)
from deployment_verification_intelligence_preview import (
    deployment_verification_intelligence_registry,
)
# clone_workspace_intelligence_registry not used in this file
from verification_intelligence_preview import (
    verification_intelligence_registry,
)
from autonomous_repair_intelligence_preview import (
    autonomous_repair_intelligence_registry,
)
from luxcode_core_status_snapshot import (
    luxcode_core_status_snapshot,
)


ENGINEERING_GRAPH_CAPABILITIES = [
    "project_relationship_mapping",
    "file_relationship_mapping",
    "module_dependency_mapping",
    "repair_relationship_mapping",
    "verification_relationship_mapping",
    "deployment_relationship_mapping",
    "workspace_relationship_mapping",
    "task_relationship_mapping",
    "knowledge_graph_analysis",
    "impact_chain_detection",
    "dependency_graph_generation",
    "graph_summary_generation",
]

GRAPH_PIPELINE = [
    "project_analysis",
    "dependency_discovery",
    "relationship_mapping",
    "impact_chain_detection",
    "knowledge_graph_generation",
    "risk_analysis",
    "engineering_summary",
]

GRAPH_PROFILES: Dict[str, Dict[str, Any]] = {
    "isolated_project": {
        "aliases": ["isolated", "izole", "standalone", "single", "tek"],
        "graph_status": "isolated_project",
        "graph_health": "pass",
        "graph_summary": "Isolated project with minimal external dependencies. Simple relationship graph. Basic mapping sufficient.",
        "health_score": 0.95,
        "risk_score": 0.05,
        "project_count": 1,
        "module_count": 3,
        "dependency_count": 5,
        "relationship_count": 8,
        "graph_complexity": "low",
        "recommended_actions": ["basic_mapping", "establish_baseline"],
        "recommended_next_action": "isolated project — basic mapping recommended",
        "graph_signals": {
            "has_external_dependencies": False,
            "has_cross_module_relationships": False,
            "has_deployment_dependencies": False,
            "impact_scope": "local",
        },
    },
    "connected_project": {
        "aliases": ["connected", "baglantili", "integrated", "entegre"],
        "graph_status": "connected_project",
        "graph_health": "pass",
        "graph_summary": "Connected project with moderate external dependencies. Relationship graph expanding. Dependency analysis recommended.",
        "health_score": 0.85,
        "risk_score": 0.15,
        "project_count": 2,
        "module_count": 6,
        "dependency_count": 15,
        "relationship_count": 25,
        "graph_complexity": "low",
        "recommended_actions": ["dependency_analysis", "map_key_relationships"],
        "recommended_next_action": "connected project — run dependency analysis",
        "graph_signals": {
            "has_external_dependencies": True,
            "has_cross_module_relationships": False,
            "has_deployment_dependencies": False,
            "impact_scope": "local",
        },
    },
    "multi_module_project": {
        "aliases": ["multi_module", "cok_modul", "complex", "karmasik", "large"],
        "graph_status": "multi_module_project",
        "graph_health": "warning",
        "graph_summary": "Multi-module project with significant internal relationships. Graph expansion required. Cross-module dependencies need tracking.",
        "health_score": 0.70,
        "risk_score": 0.35,
        "project_count": 3,
        "module_count": 12,
        "dependency_count": 35,
        "relationship_count": 60,
        "graph_complexity": "medium",
        "recommended_actions": ["graph_expansion", "map_module_relationships"],
        "recommended_next_action": "multi-module project — expand knowledge graph",
        "graph_signals": {
            "has_external_dependencies": True,
            "has_cross_module_relationships": True,
            "has_deployment_dependencies": False,
            "impact_scope": "module",
        },
    },
    "dependency_dense_project": {
        "aliases": ["dependency_dense", "bagimli", "dense", "complex_deps"],
        "graph_status": "dependency_dense_project",
        "graph_health": "degraded",
        "graph_summary": "Dependency-dense project with many external and internal dependencies. Impact analysis required. High relationship complexity.",
        "health_score": 0.50,
        "risk_score": 0.65,
        "project_count": 4,
        "module_count": 18,
        "dependency_count": 65,
        "relationship_count": 120,
        "graph_complexity": "high",
        "recommended_actions": ["impact_analysis_required", "run_impact_chain_detection"],
        "recommended_next_action": "dense dependencies — run impact chain analysis",
        "graph_signals": {
            "has_external_dependencies": True,
            "has_cross_module_relationships": True,
            "has_deployment_dependencies": True,
            "impact_scope": "cross_module",
        },
    },
    "critical_dependency_project": {
        "aliases": ["critical", "kritik", "high_risk", "mission_critical"],
        "graph_status": "critical_dependency_project",
        "graph_health": "critical",
        "graph_summary": "Critical dependency project with high-risk relationships. Changes may impact multiple systems. Verification priority required.",
        "health_score": 0.30,
        "risk_score": 0.90,
        "project_count": 5,
        "module_count": 24,
        "dependency_count": 100,
        "relationship_count": 200,
        "graph_complexity": "very_high",
        "recommended_actions": ["verification_priority", "full_impact_analysis", "graph_health_review"],
        "recommended_next_action": "critical dependencies — verification priority required",
        "graph_signals": {
            "has_external_dependencies": True,
            "has_cross_module_relationships": True,
            "has_deployment_dependencies": True,
            "impact_scope": "system_wide",
        },
    },
}

# ---------- internal helpers ----------


def _select_graph_profile(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> str:
    targets = [target_issue or "", command or "", project_area or ""]
    t_lower = " ".join(t.lower() for t in targets)
    for key, profile in GRAPH_PROFILES.items():
        aliases = profile.get("aliases", [])
        if any(a in t_lower for a in aliases) or key in t_lower:
            return key
    return "isolated_project"


def _compute_relationships(pid: str) -> Dict[str, Any]:
    p = GRAPH_PROFILES.get(pid, {})
    signals = p.get("graph_signals", {})
    health = p.get("health_score", 0.50)
    rel_count = p.get("relationship_count", 0)

    rel_risk = "low" if health > 0.75 else ("medium" if health > 0.45 else "high")
    return {
        "relationship_graph": {
            "nodes": [
                {"id": "project", "type": "project", "relationships": ["module", "workspace", "task"]},
                {"id": "module_core", "type": "module", "relationships": ["file", "dependency"]},
                {"id": "service_api", "type": "service", "relationships": ["module", "deployment"]},
                {"id": "workspace_main", "type": "workspace", "relationships": ["project", "report"]},
            ],
            "edges": [
                {"from": "project", "to": "module_core", "type": "contains"},
                {"from": "module_core", "to": "service_api", "type": "depends_on"},
                {"from": "workspace_main", "to": "project", "type": "maps_to"},
            ],
        },
        "relationship_health": "healthy" if health > 0.70 else (
            "degraded" if health > 0.40 else "critical"
        ),
        "relationship_risk": rel_risk,
        "relationship_count": rel_count,
        "project_count": p.get("project_count", 0),
        "module_count": p.get("module_count", 0),
        "service_count": max(1, p.get("module_count", 0) // 3),
        "workspace_count": max(1, p.get("project_count", 0)),
        "report_count": max(1, p.get("project_count", 0) * 2),
        "task_count": max(1, p.get("dependency_count", 0) // 5),
        "has_external_dependencies": signals.get("has_external_dependencies", False),
        "has_cross_module_relationships": signals.get("has_cross_module_relationships", False),
        "impact_scope": signals.get("impact_scope", "local"),
        "read_only": True,
        "preview_only": True,
    }


def _compute_impact_analysis(pid: str) -> Dict[str, Any]:
    p = GRAPH_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    dep_count = p.get("dependency_count", 0)

    impact_score = round(1.0 - health, 2)
    scope = "local" if health > 0.75 else (
        "module" if health > 0.50 else (
            "cross_module" if health > 0.30 else "system_wide"
        )
    )

    return {
        "impact_chain": [
            {"trigger": "file_change", "affected": ["module_core"], "severity": "low"},
            {"trigger": "module_change", "affected": ["service_api", "deployment"], "severity": "medium"},
            {"trigger": "dependency_change", "affected": ["all_modules", "deployment"], "severity": "high"},
        ],
        "impact_score": impact_score,
        "affected_scope": scope,
        "file_change_impacts": "local" if health > 0.70 else "cross_module",
        "module_change_impacts": "module" if health > 0.60 else "system_wide",
        "dependency_impacts": "module" if health > 0.50 else "system_wide",
        "deployment_impacts": "isolated" if health > 0.40 else "cascading",
        "verification_impacts": "standard" if health > 0.60 else "expanded",
        "dependency_count": dep_count,
        "read_only": True,
        "preview_only": True,
    }


def _compute_dependency_graph(pid: str) -> Dict[str, Any]:
    p = GRAPH_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)
    dep_count = p.get("dependency_count", 0)
    complexity = p.get("graph_complexity", "low")

    dep_health = "healthy" if health > 0.70 else (
        "degraded" if health > 0.40 else "critical"
    )

    return {
        "dependency_graph": {
            "nodes": [
                {"id": "framework", "type": "external", "risk": "low"},
                {"id": "database", "type": "external", "risk": "medium"},
                {"id": "api_gateway", "type": "service", "risk": "low"},
                {"id": "auth_service", "type": "service", "risk": "medium"},
                {"id": "core_module", "type": "internal", "risk": "low"},
            ],
            "edges": [
                {"from": "core_module", "to": "framework", "type": "imports"},
                {"from": "auth_service", "to": "database", "type": "depends_on"},
                {"from": "api_gateway", "to": "auth_service", "type": "routes_to"},
            ],
        },
        "dependency_health": dep_health,
        "dependency_complexity": complexity,
        "dependency_nodes": min(10, max(3, dep_count // 10)),
        "dependency_edges": min(20, max(3, dep_count // 5)),
        "dependency_clusters": min(5, max(1, dep_count // 20)),
        "dependency_risks": [
            "single_point_of_failure" if health < 0.50 else None,
            "circular_dependency" if health < 0.40 else None,
        ],
        "read_only": True,
        "preview_only": True,
    }


def _compute_graph_score(pid: str) -> Dict[str, float]:
    p = GRAPH_PROFILES.get(pid, {})
    health = p.get("health_score", 0.50)

    rel_score = round(health * 0.85, 2)
    dep_score = round(health * 0.75, 2)
    impact_score = round(1.0 - health, 2)
    graph_health = round(health * 0.80, 2)
    overall = round(
        (rel_score * 0.3 + dep_score * 0.3 + (1.0 - impact_score) * 0.2 + graph_health * 0.2), 2
    )
    return {
        "relationship_score": rel_score,
        "dependency_score": dep_score,
        "impact_score": impact_score,
        "graph_health": graph_health,
        "overall_graph_score": overall,
    }


# ---------- public entry points ----------


def engineering_graph_intelligence_status() -> Dict[str, Any]:
    core = luxcode_core_status_snapshot()
    return {
        "layer": "35.3",
        "name": "Engineering Knowledge Graph Intelligence Preview",
        "status": "engineering_graph_ready",
        "version": "1.0",
        "capabilities": ENGINEERING_GRAPH_CAPABILITIES,
        "pipeline": GRAPH_PIPELINE,
        "graph_profile_count": len(GRAPH_PROFILES),
        "operation_mode": "read_only_preview_only",
        "connected_layers": ["35.2", "35.1", "35.0", "34.9", "34.8", "34.7"],
        "available_endpoints": [
            "/engineering-graph/status",
            "/engineering-graph/capabilities",
            "/engineering-graph/preview",
            "/engineering-graph/relationships",
            "/engineering-graph/dependencies",
            "/engineering-graph/impact-analysis",
            "/engineering-graph/summary",
        ],
        "read_only": True,
        "strict_read_only": True,
        "preview_only": True,
        "graph_write": False,
        "relationship_modification": False,
        "repair_execution": False,
        "deployment_execution": False,
        "real_action_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Read-only engineering knowledge graph preview. No graph modifications or engineering actions performed.",
        "luxcode_core_health": core.get("core_health", "unknown"),
    }


def engineering_graph_intelligence_capabilities() -> Dict[str, Any]:
    return {
        "layer": "35.3",
        "name": "Engineering Knowledge Graph Capabilities",
        "status": "graph_capabilities_ready",
        "capabilities": [
            {"name": "project_relationship_mapping", "description": "Map relationships between projects", "read_only": True},
            {"name": "file_relationship_mapping", "description": "Map relationships between files", "read_only": True},
            {"name": "module_dependency_mapping", "description": "Map dependencies between modules", "read_only": True},
            {"name": "repair_relationship_mapping", "description": "Map relationships between repairs and affected components", "read_only": True},
            {"name": "verification_relationship_mapping", "description": "Map relationships between verifications and components", "read_only": True},
            {"name": "deployment_relationship_mapping", "description": "Map relationships between deployments and components", "read_only": True},
            {"name": "workspace_relationship_mapping", "description": "Map relationships between workspaces and projects", "read_only": True},
            {"name": "task_relationship_mapping", "description": "Map relationships between tasks and engineering entities", "read_only": True},
            {"name": "knowledge_graph_analysis", "description": "Analyze the knowledge graph for patterns and risks", "read_only": True},
            {"name": "impact_chain_detection", "description": "Detect impact chains from file, module, dependency changes", "read_only": True},
            {"name": "dependency_graph_generation", "description": "Generate dependency graph with nodes, edges, clusters", "read_only": True},
            {"name": "graph_summary_generation", "description": "Generate comprehensive knowledge graph summary", "read_only": True},
        ],
        "pipeline": GRAPH_PIPELINE,
        "graph_profiles": list(GRAPH_PROFILES.keys()),
        "operation_mode": "read_only_preview_only",
        "read_only": True,
        "preview_only": True,
    }


def engineering_graph_intelligence_preview(
    target_issue: Optional[str] = None,
    command: str = "",
    project_area: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_graph_profile(target_issue, command, project_area)
    p = GRAPH_PROFILES[pid]
    score = _compute_graph_score(pid)

    return {
        "graph_id": pid,
        "graph_status": p["graph_status"],
        "graph_health": p["graph_health"],
        "graph_summary": p.get("graph_summary"),
        "health_score": p.get("health_score"),
        "risk_score": p.get("risk_score"),
        "graph_score": score,
        "graph_complexity": p.get("graph_complexity"),
        "project_count": p.get("project_count"),
        "module_count": p.get("module_count"),
        "dependency_count": p.get("dependency_count"),
        "relationship_count": p.get("relationship_count"),
        "graph_signals": p.get("graph_signals", {}),
        "recommended_actions": p.get("recommended_actions", []),
        "recommended_next_action": p.get("recommended_next_action"),
        "pipeline_stage": "project_analysis",
        "pipeline_progress": {
            "completed": [],
            "current": "project_analysis",
            "remaining": GRAPH_PIPELINE[1:],
        },
        "read_only": True,
        "preview_only": True,
    }


def engineering_graph_intelligence_relationships(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_graph_profile(target_issue)
    rel = _compute_relationships(pid)
    score = _compute_graph_score(pid)

    return {
        "relationships": rel,
        "graph_score": score,
        "pipeline_stage": "relationship_mapping",
        "read_only": True,
        "preview_only": True,
    }


def engineering_graph_intelligence_dependencies(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_graph_profile(target_issue)
    dep = _compute_dependency_graph(pid)
    score = _compute_graph_score(pid)

    return {
        "dependency_graph": dep,
        "graph_score": score,
        "pipeline_stage": "dependency_discovery",
        "read_only": True,
        "preview_only": True,
    }


def engineering_graph_intelligence_impact_analysis(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_graph_profile(target_issue)
    impact = _compute_impact_analysis(pid)
    score = _compute_graph_score(pid)

    return {
        "impact_analysis": impact,
        "graph_score": score,
        "pipeline_stage": "impact_chain_detection",
        "read_only": True,
        "preview_only": True,
    }


def engineering_graph_intelligence_summary(
    target_issue: Optional[str] = None,
) -> Dict[str, Any]:
    pid = _select_graph_profile(target_issue)
    p = GRAPH_PROFILES.get(pid, {})
    rel = _compute_relationships(pid)
    dep = _compute_dependency_graph(pid)
    impact = _compute_impact_analysis(pid)
    score = _compute_graph_score(pid)

    return {
        "engineering_graph_summary": {
            "graph_profile": pid,
            "graph_health": p.get("graph_health"),
            "graph_complexity": p.get("graph_complexity"),
            "project_count": p.get("project_count"),
            "module_count": p.get("module_count"),
            "dependency_count": p.get("dependency_count"),
            "relationship_count": p.get("relationship_count"),
        },
        "relationships": rel,
        "dependency_graph": dep,
        "impact_analysis": impact,
        "graph_score": score,
        "pipeline_stage": "engineering_summary",
        "read_only": True,
        "preview_only": True,
    }


def engineering_graph_intelligence_registry() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for gid, g in GRAPH_PROFILES.items():
        items.append({
            "graph_id": gid,
            "graph_status": g["graph_status"],
            "graph_health": g["graph_health"],
            "health_score": g.get("health_score"),
            "risk_score": g.get("risk_score"),
            "graph_complexity": g.get("graph_complexity"),
            "project_count": g.get("project_count"),
            "dependency_count": g.get("dependency_count"),
            "relationship_count": g.get("relationship_count"),
        })
    return {
        "layer": "35.3",
        "name": "Engineering Knowledge Graph Registry",
        "status": "graph_registry_ready",
        "read_only": True,
        "preview_only": True,
        "graph_profile_count": len(items),
        "graph_profiles": items,
        "pass_count": sum(1 for i in items if i["graph_health"] == "pass"),
        "warning_count": sum(1 for i in items if i["graph_health"] == "warning"),
        "degraded_count": sum(1 for i in items if i["graph_health"] == "degraded"),
        "critical_count": sum(1 for i in items if i["graph_health"] == "critical"),
        "total_projects": sum(i.get("project_count", 0) for i in items),
        "total_dependencies": sum(i.get("dependency_count", 0) for i in items),
        "total_relationships": sum(i.get("relationship_count", 0) for i in items),
    }
