from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bug_intake_planner import build_bug_intake_preview
from codex_handoff_builder_preview import build_codex_handoff_preview
from credit_saver_engine import build_credit_saver_preview
from investigation_context_preview import build_investigation_context_preview
from investigation_timeline_preview import build_investigation_timeline_preview
from knowledge_extractor_preview import build_knowledge_extractor_preview
from repeated_pattern_detector_preview import build_repeated_pattern_preview, repeated_pattern_registry
from investigation_starter_preview import build_investigation_starter_preview, investigation_starter_registry
from investigation_priority_engine_preview import build_investigation_priority_preview, investigation_priority_registry
from investigation_task_planner_preview import build_task_planner_preview, task_planner_registry
from dev_agent_explorer_preview import build_dev_agent_explorer_preview, dev_agent_explorer_registry
from dependency_mapper_preview import build_dependency_mapper_preview, dependency_mapper_registry
from impact_analyzer_preview import build_impact_analyzer_preview, impact_analyzer_registry
from safe_change_boundary_preview import build_change_boundary_preview, change_boundary_registry
from safe_patch_planner_preview import build_patch_planner_preview, patch_planner_registry
from safe_verification_planner_preview import build_verification_planner_preview, verification_planner_registry
from dev_agent_readiness_snapshot import layer25_status_snapshot
from agent_constitution_engine_preview import build_constitution_preview, constitution_registry
from project_rules_loader_preview import build_project_rules_preview, project_rules_registry
from explorer_agent_preview import build_explorer_agent_preview
from planner_agent_preview import build_planner_agent_preview
from verifier_agent_preview import build_verifier_agent_preview
from evidence_store_preview import build_evidence_store_preview
from multi_agent_coordinator_preview import build_coordinator_preview
from patch_draft_engine_preview import build_patch_draft_preview, patch_draft_registry
from change_preview_engine_preview import build_change_preview, change_preview_registry
from diff_preview_engine_preview import build_diff_preview, diff_preview_registry
from patch_risk_matrix_preview import build_patch_risk_preview, patch_risk_registry
from patch_approval_engine_preview import build_patch_approval_preview, patch_approval_registry
from patch_execution_readiness_preview import build_patch_execution_preview, patch_execution_registry
from layer27_status_snapshot import layer27_status_snapshot
from layer28_status_snapshot import layer28_status_snapshot
from safe_patch_application_preview import build_safe_patch_preview, safe_patch_registry
from patch_rollback_preview import build_patch_rollback_preview, patch_rollback_registry
from patch_validation_preview import build_patch_validation_preview, patch_validation_registry
from patch_recovery_preview import build_patch_recovery_preview, patch_recovery_registry
from patch_audit_trail_preview import build_patch_audit_preview, patch_audit_registry
from patch_lifecycle_preview import build_patch_lifecycle_preview, patch_lifecycle_registry
from patch_permission_enforcement_preview import build_patch_permission_preview, patch_permission_registry
from patch_policy_evaluation_preview import build_patch_policy_preview, patch_policy_registry
from patch_compliance_preview import build_patch_compliance_preview, patch_compliance_registry
from patch_governance_preview import build_patch_governance_preview, patch_governance_registry
from patch_oversight_preview import build_patch_oversight_preview, patch_oversight_registry
from patch_accountability_preview import build_patch_accountability_preview, patch_accountability_registry
from patch_assurance_preview import build_patch_assurance_preview, patch_assurance_registry
from patch_confidence_preview import build_patch_confidence_preview, patch_confidence_registry
from layer29_status_snapshot import layer29_status_snapshot
from production_readiness_preview import build_production_readiness_preview, production_readiness_registry
from operational_readiness_preview import build_operational_readiness_preview, operational_readiness_registry
from system_readiness_preview import build_system_readiness_preview, system_readiness_registry
from validation_readiness_preview import build_validation_readiness_preview, validation_readiness_registry
from release_readiness_preview import build_release_readiness_preview, release_readiness_registry
from layer30_status_snapshot import layer30_status_snapshot
from system_health_intelligence_preview import (
    build_system_health_intelligence_preview,
    system_health_intelligence_registry,
    system_health_intelligence_status,
)
from runtime_stability_intelligence_preview import (
    build_runtime_stability_intelligence_preview,
    runtime_stability_intelligence_registry,
    runtime_stability_intelligence_status,
)
from runtime_risk_intelligence_preview import (
    build_runtime_risk_intelligence_preview,
    runtime_risk_intelligence_registry,
    runtime_risk_intelligence_status,
)
from runtime_drift_intelligence_preview import (
    build_runtime_drift_intelligence_preview,
    runtime_drift_intelligence_registry,
    runtime_drift_intelligence_status,
)
from runtime_recovery_intelligence_preview import (
    build_runtime_recovery_intelligence_preview,
    runtime_recovery_intelligence_registry,
    runtime_recovery_intelligence_status,
)
from runtime_anomaly_intelligence_preview import (
    build_runtime_anomaly_intelligence_preview,
    runtime_anomaly_intelligence_registry,
    runtime_anomaly_intelligence_status,
)
from regression_intelligence_preview import (
    build_regression_intelligence_preview,
    regression_intelligence_registry,
    regression_intelligence_status,
)
from failure_memory_intelligence_preview import (
    build_failure_memory_intelligence_preview,
    failure_memory_intelligence_registry,
    failure_memory_intelligence_status,
)
from dependency_intelligence_preview import (
    build_dependency_intelligence_preview,
    dependency_intelligence_registry,
    dependency_intelligence_status,
)
from root_cause_intelligence_preview import (
    build_root_cause_intelligence_preview,
    root_cause_intelligence_registry,
    root_cause_intelligence_status,
)
from change_memory_intelligence_preview import (
    build_change_memory_intelligence_preview,
    change_memory_intelligence_registry,
    change_memory_intelligence_status,
)
from failed_change_intelligence_preview import (
    build_failed_change_intelligence_preview,
    failed_change_intelligence_registry,
    failed_change_intelligence_status,
)
from change_planning_intelligence_preview import (
    build_change_planning_intelligence_preview,
    change_planning_intelligence_registry,
    change_planning_intelligence_status,
)
# lazy imports: clone_workspace_intelligence_preview functions imported inside functions
from sandbox_repair_intelligence_preview import (
    build_sandbox_repair_intelligence_preview,
    sandbox_repair_intelligence_registry,
    sandbox_repair_intelligence_status,
)
from verification_intelligence_preview import (
    build_verification_intelligence_preview,
    verification_intelligence_registry,
    verification_intelligence_status,
)
from delivery_readiness_intelligence_preview import (
    build_delivery_readiness_intelligence_preview,
    delivery_readiness_intelligence_registry,
    delivery_readiness_intelligence_status,
)
from layer32_status_snapshot import layer32_status_snapshot, layer32_full_status
from layer31_status_snapshot import layer31_status_snapshot, layer31_full_status
from root_flow_auditor_preview import build_root_flow_audit
from safe_self_check_runner_preview import build_self_check_preview


def _to_iso(date_value: datetime) -> str:
    return date_value.replace(microsecond=0, tzinfo=timezone.utc).isoformat()


def _issue_card(
    title: str,
    status: str,
    priority: str,
    note: str,
    related_layers: List[str],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "title": title,
        "status": status,
        "priority": priority,
        "summary": note,
        "related_layers": related_layers,
    }
    if extra:
        payload.update(extra)
    return payload


OPEN_ISSUES = [
    _issue_card(
        title="Dur/Devam sistemi",
        status="İnceleniyor",
        priority="Kritik",
        note="İlk continue çağrısında kalma noktası doğru ancak ikinci ve sonrasında akış kesintisi görünüyor.",
        related_layers=["ARM", "Layer 23", "Stop/Continue"],
        extra={
            "first_reported": _to_iso(datetime(2026, 6, 1, 9, 12)),
            "last_updated": _to_iso(datetime(2026, 6, 8, 20, 10)),
            "notes": "Dur sonrası ikinci ve üçüncü continue senaryoları öncelikli test edilecek.",
        },
    ),
    _issue_card(
        title="Websocket canlılık drift",
        status="İnceleniyor",
        priority="Yüksek",
        note="Tab değişimi sonrası typewriter durumu bazen senkron bozulmasına gidiyor.",
        related_layers=["stream", "websocket", "Layer 23"],
        extra={
            "first_reported": _to_iso(datetime(2026, 6, 2, 17, 44)),
            "last_updated": _to_iso(datetime(2026, 6, 8, 19, 22)),
            "notes": "Canlı loglama olmadan devam davranışı koruma modu denenecek.",
        },
    ),
]

DEFERRED_ISSUES = [
    _issue_card(
        title="Konu içi tarihsel özetleme akışı",
        status="Erteleniyor",
        priority="Orta",
        note="Layer 24 sonrası gerçek hafıza akışıyla birlikte değerlendirme planlanacak.",
        related_layers=["workspace", "context bridge", "Layer 22"],
        extra={
            "deferred_since": _to_iso(datetime(2026, 6, 4, 10, 20)),
            "reeval_note": "Önce Layer 24 rapor düzeni stabil olsun.",
        },
    ),
    _issue_card(
        title="UI panel kart düzeni",
        status="Erteleniyor",
        priority="Düşük",
        note="Yeni entegrasyon sayfaları arttığında panel gruplama yeniden dengelenecek.",
        related_layers=["UI", "Layer 24"],
        extra={
            "deferred_since": _to_iso(datetime(2026, 6, 5, 15, 35)),
            "reeval_note": "Layer 22/23 kontrol alanları sonrası sadeleştirilecek.",
        },
    ),
]

RESOLVED_ISSUES = [
    _issue_card(
        title="ARM Stop/Continue temel akışı",
        status="Çözüldü",
        priority="Kritik",
        note="Generate edilen cevapların ARM’de önbelleğe alınması stabil hale getirildi.",
        related_layers=["ARM", "Layer 23", "Stop/Continue"],
        extra={
            "resolved_at": _to_iso(datetime(2026, 6, 3, 14, 10)),
            "outcome": "Resume state read/write çizelgesi netleştirildi.",
            "closure_note": "Duplicate resume branch kaldırıldı, kalıntı akışlar temizlendi.",
        },
    ),
    _issue_card(
        title="Layer 24 entegrasyon başlangıç durumu",
        status="Çözüldü",
        priority="Orta",
        note="Bug merkezi kapsamı için gerekli endpoint ve panel iskeleti eklendi.",
        related_layers=["Layer 24", "Debug Intelligence"],
        extra={
            "resolved_at": _to_iso(datetime(2026, 6, 8, 12, 5)),
            "outcome": "Read-only preview ve Türkçe panel kartları hazır.",
            "closure_note": "Kayıtlar sadece preview formatta tutuluyor.",
        },
    ),
]

ARCHIVE = [
    {
        "title": "ARM Stop Continue",
        "status": "Çözüldü",
        "updated_at": _to_iso(datetime(2026, 6, 3, 14, 10)),
        "note": "Read-only state-first yaklaşımına geçti.",
        "related_layers": ["Layer 23", "Stop/Continue", "ARM"],
    },
    {
        "title": "Logo hizalama",
        "status": "Açık",
        "updated_at": _to_iso(datetime(2026, 6, 2, 17, 44)),
        "note": "UX test listesinde beklemede.",
        "related_layers": ["UI", "Production"],
    },
    {
        "title": "Layer 23 Debug Intelligence",
        "status": "Çözüldü",
        "updated_at": _to_iso(datetime(2026, 6, 6, 11, 10)),
        "note": "Root Flow/Auditor zinciri hazır.",
        "related_layers": ["Layer 23", "Debug Intelligence"],
    },
    {
        "title": "Workspace Export",
        "status": "Erteleniyor",
        "updated_at": _to_iso(datetime(2026, 6, 5, 16, 55)),
        "note": "Gerçek export entegrasyonu gelecekteki katmana bırakıldı.",
        "related_layers": ["Workspace", "Layer 15"],
    },
]


LAYER23_ANALYSIS_LINKS = {
    "/debug/root-flow-auditor-status": {
        "name": "Root Flow Auditor Preview",
        "layer": "23.1",
        "focus": "behavior ownership + root causes",
    },
    "/debug/root-flow-audit": {
        "name": "Root Flow Audit",
        "layer": "23.1",
        "focus": "authoritative analysis + invariant check",
    },
    "/debug/codex-fix-plan": {
        "name": "Codex Fix Plan",
        "layer": "23.1",
        "focus": "technical plan generation",
    },
    "/debug/self-check-status": {
        "name": "Self Check Status",
        "layer": "23.2",
        "focus": "safe check registry",
    },
    "/debug/self-check-registry": {
        "name": "Self Check Registry",
        "layer": "23.2",
        "focus": "check catalog",
    },
    "/debug/self-check-preview": {
        "name": "Self Check Preview",
        "layer": "23.2",
        "focus": "diagnostic preview",
    },
    "/debug/codex-handoff-status": {
        "name": "Codex Handoff Status",
        "layer": "23.3",
        "focus": "handoff readiness",
    },
    "/debug/codex-handoff-registry": {
        "name": "Codex Handoff Registry",
        "layer": "23.3",
        "focus": "handoff templates",
    },
    "/debug/codex-handoff-preview": {
        "name": "Codex Handoff Preview",
        "layer": "23.3",
        "focus": "task packet prep",
    },
    "/debug/bug-intake-status": {
        "name": "Bug Intake Status",
        "layer": "23.4",
        "focus": "common bug schema",
    },
    "/debug/bug-intake-registry": {
        "name": "Bug Intake Registry",
        "layer": "23.4",
        "focus": "category catalog",
    },
    "/debug/bug-intake-preview": {
        "name": "Bug Intake Preview",
        "layer": "23.4",
        "focus": "triage planning",
    },
    "/debug/credit-saver-status": {
        "name": "Credit Saver Status",
        "layer": "23.5",
        "focus": "lux/codex split",
    },
    "/debug/credit-saver-registry": {
        "name": "Credit Saver Registry",
        "layer": "23.5",
        "focus": "task complexity paths",
    },
    "/debug/credit-saver-preview": {
        "name": "Credit Saver Preview",
        "layer": "23.5",
        "focus": "triage decision preview",
    },
    "/debug/intelligence-status": {
        "name": "Debug Intelligence Status",
        "layer": "23.6",
        "focus": "core anomaly analysis",
    },
    "/debug/intelligence-registry": {
        "name": "Debug Intelligence Registry",
        "layer": "23.6",
        "focus": "repeated failure categories",
    },
    "/debug/intelligence-preview": {
        "name": "Debug Intelligence Preview",
        "layer": "23.6",
        "focus": "anomaly + recommendation preview",
    },
    "/debug/investigation-context-status": {
        "name": "Active Investigation Context Status",
        "layer": "24.2",
        "focus": "active task + readiness guardrails",
    },
    "/debug/investigation-context-registry": {
        "name": "Investigation Context Registry",
        "layer": "24.2",
        "focus": "task-based continuation and owner checkpoints",
    },
    "/debug/investigation-context-preview": {
        "name": "Investigation Context Preview",
        "layer": "24.2",
        "focus": "live active investigation payload",
    },
}


DEFAULT_INTELLIGENCE_ENDPOINTS = [
    "/debug/root-flow-auditor-status",
    "/debug/self-check-status",
    "/debug/bug-intake-status",
    "/debug/intelligence-status",
]


def _normalize(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _iter_all_issues() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in OPEN_ISSUES:
        issue = dict(item)
        issue["source_section"] = "open_issues"
        items.append(issue)
    for item in DEFERRED_ISSUES:
        issue = dict(item)
        issue["source_section"] = "deferred_issues"
        items.append(issue)
    for item in RESOLVED_ISSUES:
        issue = dict(item)
        issue["source_section"] = "resolved_issues"
        items.append(issue)
    for item in ARCHIVE:
        issue = dict(item)
        issue["source_section"] = "issue_archive"
        items.append(issue)
    return items


def _pick_issue(
    issue_title: Optional[str] = None,
    focus: Optional[str] = None,
    status: Optional[str] = None,
    related_layer: Optional[str] = None,
    command: str = "",
) -> Dict[str, Any]:
    normalized_title = _normalize(issue_title)
    normalized_focus = _normalize(focus)
    normalized_status = _normalize(status)
    normalized_layer = _normalize(related_layer)
    normalized_command = _normalize(command)

    candidates = _iter_all_issues()
    for item in candidates:
        if normalized_title and normalized_title in _normalize(item.get("title")):
            return item
        if normalized_focus:
            summary_text = _normalize(item.get("summary", ""))
            if normalized_focus in summary_text or normalized_focus in _normalize(item.get("title", "")):
                return item
        if normalized_status and _normalize(item.get("priority")) == normalized_status:
            return item
        layer_hits = " ".join(str(x) for x in item.get("related_layers", []))
        if normalized_layer and normalized_layer in _normalize(layer_hits):
            return item

    if normalized_command:
        if "dur" in normalized_command or "devam" in normalized_command or "continue" in normalized_command:
            for item in candidates:
                if "dur" in _normalize(item.get("title", "")) or "devam" in _normalize(item.get("title", "")):
                    return item
        if "websocket" in normalized_command or "stream" in normalized_command:
            for item in candidates:
                if "websocket" in _normalize(item.get("title", "")) or "canli" in _normalize(item.get("title", "")):
                    return item

    return candidates[0] if candidates else {"title": "Unknown issue", "status": "Bilinmiyor", "priority": "Orta", "summary": "Önceki kart bulunamadı", "related_layers": ["Layer 23"]}


def _trim_text(value: Optional[str], limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _safe_unique(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _attach_timeline_preview(item: Dict[str, Any]) -> Dict[str, Any]:
    title = item.get("title", "")
    try:
        timeline_payload = build_investigation_timeline_preview(
            issue_title=title,
            command=str(title),
            current_status=item.get("status"),
            command_behavior="stop_continue" if "dur" in (title or "").lower() else None,
        )
        item["investigation_timeline"] = {
            "issue_title": timeline_payload.get("issue_title"),
            "current_status": timeline_payload.get("current_status"),
            "latest_finding": timeline_payload.get("latest_finding"),
            "timeline_entries": timeline_payload.get("timeline_entries", []),
            "recommended_next_step": timeline_payload.get("recommended_next_step"),
            "active_investigation_context": timeline_payload.get("active_investigation_context"),
        }
    except Exception:
        item["investigation_timeline"] = {
            "issue_title": title,
            "current_status": item.get("status"),
            "timeline_entries": [],
            "recommended_next_step": "investigation context check",
        }
    return item


def _attach_knowledge_preview(item: Dict[str, Any]) -> Dict[str, Any]:
    title = item.get("title", "")
    resolution_summary = item.get("outcome") or item.get("closure_note") or item.get("summary", "")
    try:
        knowledge_payload = build_knowledge_extractor_preview(
            issue_title=title,
            resolution_summary=str(resolution_summary),
            command=str(title),
            related_layer=", ".join(str(layer) for layer in item.get("related_layers", [])),
        )
        item["knowledge_extraction"] = {
            "issue_title": knowledge_payload.get("issue_title"),
            "resolution_summary": knowledge_payload.get("resolution_summary"),
            "lessons_learned": knowledge_payload.get("lessons_learned", []),
            "recommended_future_checks": knowledge_payload.get("recommended_future_checks", []),
            "related_patterns": knowledge_payload.get("related_patterns", []),
            "recommended_layers": knowledge_payload.get("recommended_layers", []),
            "confidence_score": knowledge_payload.get("confidence_score"),
        }
    except Exception:
        item["knowledge_extraction"] = {
            "issue_title": title,
            "resolution_summary": str(resolution_summary),
            "lessons_learned": [],
            "recommended_future_checks": [],
            "related_patterns": [],
            "recommended_layers": item.get("related_layers", []),
        }
    return item


def _fault_report_repeated_patterns() -> List[Dict[str, Any]]:
    registry = repeated_pattern_registry()
    patterns = registry.get("patterns", [])
    output: List[Dict[str, Any]] = []
    for pattern in patterns[:5]:
        preview = build_repeated_pattern_preview(
            pattern_name=pattern.get("pattern_name"),
            command=str(pattern.get("pattern_name", "")),
        )
        output.append(
            {
                "pattern_name": preview.get("pattern_name"),
                "occurrence_count": preview.get("occurrence_count"),
                "risk_trend": preview.get("risk_trend"),
                "related_issues": preview.get("related_issues", []),
                "recommended_attention_level": preview.get("recommended_attention_level"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_investigation_starters() -> List[Dict[str, Any]]:
    registry = investigation_starter_registry()
    starters = registry.get("starters", [])
    output: List[Dict[str, Any]] = []
    for starter in starters[:4]:
        preview = build_investigation_starter_preview(
            issue_title=str(starter.get("id", "")),
            command=str(starter.get("id", "")),
        )
        output.append(
            {
                "issue_title": preview.get("issue_title"),
                "similar_previous_issues": preview.get("similar_previous_issues", []),
                "recommended_starting_checks": preview.get("recommended_starting_checks", []),
                "recommended_layers": preview.get("recommended_layers", []),
                "recommended_files": preview.get("recommended_files", []),
                "recommended_tests": preview.get("recommended_tests", []),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_priority_engine() -> List[Dict[str, Any]]:
    registry = investigation_priority_registry()
    priority_items = registry.get("priority_items", [])
    output: List[Dict[str, Any]] = []
    for item in priority_items[:5]:
        preview = build_investigation_priority_preview(
            issue_title=str(item.get("id", "")),
            command=str(item.get("id", "")),
        )
        output.append(
            {
                "issue_title": preview.get("issue_title"),
                "priority_score": preview.get("priority_score"),
                "priority_level": preview.get("priority_level"),
                "reasoning_summary": preview.get("reasoning_summary"),
                "recommended_order": preview.get("recommended_order"),
                "risk_score": preview.get("risk_score"),
                "impact_score": preview.get("impact_score"),
                "frequency_score": preview.get("frequency_score"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_task_plans() -> List[Dict[str, Any]]:
    registry = task_planner_registry()
    plans = registry.get("plans", [])
    output: List[Dict[str, Any]] = []
    for plan in plans[:5]:
        preview = build_task_planner_preview(
            issue_title=str(plan.get("id", "")),
            command=str(plan.get("id", "")),
        )
        output.append(
            {
                "issue_title": preview.get("issue_title"),
                "priority_level": preview.get("priority_level"),
                "recommended_task_order": preview.get("recommended_task_order", []),
                "recommended_checks": preview.get("recommended_checks", []),
                "recommended_tests": preview.get("recommended_tests", []),
                "estimated_complexity": preview.get("estimated_complexity"),
                "recommended_codex_usage": preview.get("recommended_codex_usage"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_dev_agent_explorer() -> List[Dict[str, Any]]:
    registry = dev_agent_explorer_registry()
    areas = registry.get("project_areas", [])
    output: List[Dict[str, Any]] = []
    for area in areas[:5]:
        preview = build_dev_agent_explorer_preview(
            project_area=str(area.get("id", "")),
            command=str(area.get("id", "")),
        )
        output.append(
            {
                "project_area": preview.get("project_area"),
                "known_components": preview.get("known_components", []),
                "known_layers": preview.get("known_layers", []),
                "known_endpoints": preview.get("known_endpoints", []),
                "suggested_entry_points": preview.get("suggested_entry_points", []),
                "complexity_score": preview.get("complexity_score"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_dependency_map() -> List[Dict[str, Any]]:
    registry = dependency_mapper_registry()
    mappings = registry.get("dependency_mappings", [])
    output: List[Dict[str, Any]] = []
    for mapping in mappings[:5]:
        preview = build_dependency_mapper_preview(
            component_name=str(mapping.get("id", "")),
            command=str(mapping.get("id", "")),
        )
        output.append(
            {
                "component_name": preview.get("component_name"),
                "related_components": preview.get("related_components", []),
                "related_layers": preview.get("related_layers", []),
                "related_endpoints": preview.get("related_endpoints", []),
                "related_behaviors": preview.get("related_behaviors", []),
                "dependency_risk": preview.get("dependency_risk"),
                "complexity_score": preview.get("complexity_score"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_impact_analysis() -> List[Dict[str, Any]]:
    registry = impact_analyzer_registry()
    impact_items = registry.get("impact_items", [])
    output: List[Dict[str, Any]] = []
    for item in impact_items[:5]:
        preview = build_impact_analyzer_preview(
            target_component=str(item.get("id", "")),
            command=str(item.get("id", "")),
        )
        output.append(
            {
                "target_component": preview.get("target_component"),
                "potentially_affected_components": preview.get("potentially_affected_components", []),
                "potentially_affected_layers": preview.get("potentially_affected_layers", []),
                "potentially_affected_endpoints": preview.get("potentially_affected_endpoints", []),
                "potentially_affected_behaviors": preview.get("potentially_affected_behaviors", []),
                "impact_risk": preview.get("impact_risk"),
                "recommended_caution_level": preview.get("recommended_caution_level"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_change_boundary() -> List[Dict[str, Any]]:
    registry = change_boundary_registry()
    boundaries = registry.get("boundaries", [])
    output: List[Dict[str, Any]] = []
    for boundary in boundaries[:6]:
        preview = build_change_boundary_preview(
            target_area=str(boundary.get("id", "")),
            command=str(boundary.get("id", "")),
        )
        output.append(
            {
                "target_area": preview.get("target_area"),
                "boundary_level": preview.get("boundary_level"),
                "criticality_level": preview.get("criticality_level"),
                "user_approval_required": preview.get("user_approval_required"),
                "allowed_actions": preview.get("allowed_actions", []),
                "blocked_actions": preview.get("blocked_actions", []),
                "risk_reason": preview.get("risk_reason"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_patch_plans() -> List[Dict[str, Any]]:
    registry = patch_planner_registry()
    plans = registry.get("patch_plans", [])
    output: List[Dict[str, Any]] = []
    for plan in plans[:5]:
        preview = build_patch_planner_preview(
            target_issue=str(plan.get("id", "")),
            command=str(plan.get("id", "")),
        )
        output.append(
            {
                "target_issue": preview.get("target_issue"),
                "recommended_change_areas": preview.get("recommended_change_areas", []),
                "recommended_patch_scope": preview.get("recommended_patch_scope"),
                "risk_assessment": preview.get("risk_assessment"),
                "required_tests": preview.get("required_tests", []),
                "recommended_validation_steps": preview.get("recommended_validation_steps", []),
                "approval_required": preview.get("approval_required"),
                "estimated_complexity": preview.get("estimated_complexity"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_verification_plans() -> List[Dict[str, Any]]:
    registry = verification_planner_registry()
    plans = registry.get("verification_plans", [])
    output: List[Dict[str, Any]] = []
    for plan in plans[:5]:
        preview = build_verification_planner_preview(
            target_issue=str(plan.get("id", "")),
            command=str(plan.get("id", "")),
        )
        output.append(
            {
                "target_issue": preview.get("target_issue"),
                "recommended_smoke_tests": preview.get("recommended_smoke_tests", []),
                "recommended_manual_tests": preview.get("recommended_manual_tests", []),
                "recommended_regression_checks": preview.get("recommended_regression_checks", []),
                "success_criteria": preview.get("success_criteria", []),
                "risk_validation_points": preview.get("risk_validation_points", []),
                "estimated_validation_effort": preview.get("estimated_validation_effort"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_dev_agent_readiness() -> Dict[str, Any]:
    readiness = layer25_status_snapshot()
    return {
        "completed_layers": readiness.get("completed_layers", []),
        "available_capabilities": readiness.get("available_capabilities", []),
        "missing_capabilities": readiness.get("missing_capabilities", []),
        "readiness_score": readiness.get("readiness_score"),
        "safe_for_patch_planning": readiness.get("safe_for_patch_planning"),
        "safe_for_write_operations": readiness.get("safe_for_write_operations"),
        "recommended_next_layer": readiness.get("recommended_next_layer"),
        "confidence_score": readiness.get("confidence_score"),
    }


def _fault_report_constitution_engine() -> Dict[str, Any]:
    registry = constitution_registry()
    preview = build_constitution_preview(
        command="modify chat runtime but strict read only mode",
        conflicting_rules=["modify_chat_runtime", "read_only_mode"],
        target_area="chat",
    )
    return {
        "rule_source": preview.get("rule_source"),
        "rule_priority": preview.get("rule_priority"),
        "conflicting_rules": preview.get("conflicting_rules", []),
        "selected_rule": preview.get("selected_rule"),
        "resolution_reason": preview.get("resolution_reason"),
        "confidence_score": preview.get("confidence_score"),
        "hierarchy": registry.get("hierarchy", []),
    }


def _fault_report_project_rules() -> List[Dict[str, Any]]:
    registry = project_rules_registry()
    output: List[Dict[str, Any]] = []
    for rule in registry.get("rules", [])[:6]:
        preview = build_project_rules_preview(
            command=str(rule.get("project_rule_category", "")),
            project_rule_category=str(rule.get("project_rule_category", "")),
            target_area=str(rule.get("project_rule_category", "")),
        )
        output.append(
            {
                "project_rule_category": preview.get("project_rule_category"),
                "rule_name": preview.get("rule_name"),
                "rule_priority": preview.get("rule_priority"),
                "protected_areas": preview.get("protected_areas", []),
                "required_checks": preview.get("required_checks", []),
                "recommended_actions": preview.get("recommended_actions", []),
                "blocked_actions": preview.get("blocked_actions", []),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_explorer_agent() -> Dict[str, Any]:
    preview = build_explorer_agent_preview(
        command="stop continue arm typewriter iliskilerini kesfet",
        project_area="stop_continue",
        related_layer="Layer 26",
    )
    return {
        "agent_role": preview.get("agent_role"),
        "allowed_capabilities": preview.get("allowed_capabilities", []),
        "blocked_capabilities": preview.get("blocked_capabilities", []),
        "recommended_entry_points": preview.get("recommended_entry_points", []),
        "recommended_related_systems": preview.get("recommended_related_systems", []),
        "investigation_focus": preview.get("investigation_focus"),
        "confidence_score": preview.get("confidence_score"),
    }


def _fault_report_planner_agent() -> Dict[str, Any]:
    preview = build_planner_agent_preview(
        command="stop continue icin cozum plani ve dogrulama stratejisi olustur",
        project_area="stop_continue",
        related_layer="Layer 26",
    )
    return {
        "agent_role": preview.get("agent_role"),
        "recommended_plan": preview.get("recommended_plan", []),
        "recommended_task_order": preview.get("recommended_task_order", []),
        "risk_considerations": preview.get("risk_considerations", {}),
        "recommended_validation_strategy": preview.get("recommended_validation_strategy", {}),
        "confidence_score": preview.get("confidence_score"),
    }


def _fault_report_verifier_agent() -> Dict[str, Any]:
    preview = build_verifier_agent_preview(
        command="stop continue icin dogrulama ve regresyon kontrolu yap",
        project_area="stop_continue",
        related_layer="Layer 26",
    )
    return {
        "agent_role": preview.get("agent_role"),
        "recommended_verification_steps": preview.get("recommended_verification_steps", []),
        "recommended_regression_checks": preview.get("recommended_regression_checks", []),
        "recommended_success_criteria": preview.get("recommended_success_criteria", []),
        "risk_validation_focus": preview.get("risk_validation_focus", []),
        "confidence_score": preview.get("confidence_score"),
    }


def _fault_report_evidence_store() -> Dict[str, Any]:
    preview = build_evidence_store_preview(
        finding="state_source_conflict",
        command="stop continue state source conflict kanitlarini goster",
        project_area="stop_continue",
        related_layer="Layer 26",
    )
    return {
        "finding": preview.get("finding"),
        "evidence_items": preview.get("evidence_items", []),
        "supporting_signals": preview.get("supporting_signals", []),
        "related_agents": preview.get("related_agents", []),
        "confidence_reasoning": preview.get("confidence_reasoning"),
        "risk_reasoning": preview.get("risk_reasoning"),
        "confidence_score": preview.get("confidence_score"),
    }


def _fault_report_coordinator() -> Dict[str, Any]:
    preview = build_coordinator_preview(
        command="stop continue icin ajan ciktilarini koordine et",
        project_area="stop_continue",
        related_layer="Layer 26",
    )
    return {
        "participating_agents": preview.get("participating_agents", []),
        "agent_contributions": preview.get("agent_contributions", {}),
        "coordination_flow": preview.get("coordination_flow", []),
        "combined_findings": preview.get("combined_findings", []),
        "combined_risks": preview.get("combined_risks", []),
        "combined_recommendations": preview.get("combined_recommendations", []),
        "overall_confidence": preview.get("overall_confidence"),
    }


def _fault_report_patch_draft() -> List[Dict[str, Any]]:
    registry = patch_draft_registry()
    drafts = registry.get("drafts", [])
    output: List[Dict[str, Any]] = []
    for draft in drafts[:5]:
        preview = build_patch_draft_preview(
            target_issue=str(draft.get("id", "")),
            command=str(draft.get("id", "")),
            project_area=str(draft.get("id", "")),
            related_layer="Layer 27.1",
        )
        output.append(
            {
                "Hedef Sorun": preview.get("target_issue"),
                "Önerilen Dosyalar": preview.get("recommended_files", []),
                "Değişiklik Özeti": preview.get("draft_change_summary"),
                "Taslak Adımlar": preview.get("draft_patch_steps", []),
                "Risk": preview.get("risk_assessment"),
                "Onay Gereksinimi": preview.get("approval_required"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_change_preview() -> List[Dict[str, Any]]:
    registry = change_preview_registry()
    previews = registry.get("previews", [])
    output: List[Dict[str, Any]] = []
    for item in previews[:5]:
        preview = build_change_preview(
            target_issue=str(item.get("id", "")),
            command=str(item.get("id", "")),
            project_area=str(item.get("id", "")),
            related_layer="Layer 27.2",
        )
        output.append(
            {
                "Hedef Sorun": preview.get("target_issue"),
                "Etkilenen Alanlar": preview.get("affected_areas", []),
                "Önce Özeti": preview.get("before_summary"),
                "Sonra Özeti": preview.get("after_summary"),
                "Tahmini Etkiler": preview.get("predicted_effects", []),
                "Risk Alanları": preview.get("risk_areas", []),
                "Onay Gereksinimi": preview.get("approval_required"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_diff_preview() -> List[Dict[str, Any]]:
    registry = diff_preview_registry()
    diffs = registry.get("diffs", [])
    output: List[Dict[str, Any]] = []
    for item in diffs[:5]:
        preview = build_diff_preview(
            target_issue=str(item.get("id", "")),
            command=str(item.get("id", "")),
            project_area=str(item.get("id", "")),
            related_layer="Layer 27.3",
        )
        output.append(
            {
                "Hedef Sorun": preview.get("target_issue"),
                "Etkilenen Dosyalar": preview.get("affected_files", []),
                "Önce Kod Özeti": preview.get("before_code_summary"),
                "Sonra Kod Özeti": preview.get("after_code_summary"),
                "Tahmini Hunk Sayısı": preview.get("diff_hunks_expected"),
                "Tahmini Değişiklikler": preview.get("predicted_changes", []),
                "Risk Alanları": preview.get("risk_areas", []),
                "Onay Gereksinimi": preview.get("approval_required"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_patch_risk_matrix() -> List[Dict[str, Any]]:
    registry = patch_risk_registry()
    risks = registry.get("risks", [])
    output: List[Dict[str, Any]] = []
    for item in risks[:5]:
        preview = build_patch_risk_preview(
            target_issue=str(item.get("id", "")),
            command=str(item.get("id", "")),
            project_area=str(item.get("id", "")),
            related_layer="Layer 27.4",
        )
        output.append(
            {
                "Hedef Sorun": preview.get("target_issue"),
                "Hedef Bileşen": preview.get("target_component"),
                "Etkilenen Dosyalar": preview.get("affected_files", []),
                "Etkilenen Layer'lar": preview.get("affected_layers", []),
                "Etkilenen Endpoint'ler": preview.get("affected_endpoints", []),
                "Risk Skoru": preview.get("risk_score"),
                "Risk Seviyesi": preview.get("risk_level"),
                "Risk Sebepleri": preview.get("risk_reasons", []),
                "Bağımlılık Riski": preview.get("dependency_risk"),
                "Çalışma Zamanı Riski": preview.get("runtime_risk"),
                "Regresyon Riski": preview.get("regression_risk"),
                "Sınır Riski": preview.get("boundary_risk"),
                "Doğrulama Gerekli": preview.get("verification_required"),
                "Önerilen Testler": preview.get("recommended_tests", []),
                "Onay Gereksinimi": preview.get("approval_required"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_patch_approval() -> List[Dict[str, Any]]:
    registry = patch_approval_registry()
    approvals = registry.get("approvals", [])
    output: List[Dict[str, Any]] = []
    for item in approvals[:5]:
        preview = build_patch_approval_preview(
            target_issue=str(item.get("id", "")),
            command=str(item.get("id", "")),
            project_area=str(item.get("id", "")),
            related_layer="Layer 27.5",
        )
        output.append(
            {
                "Hedef Sorun": preview.get("target_issue"),
                "Hedef Bileşen": preview.get("target_component"),
                "Onay Gerekli": preview.get("approval_required"),
                "Onay Seviyesi": preview.get("approval_level"),
                "Onay Sebebi": preview.get("approval_reason"),
                "Onay Kaynağı": preview.get("approval_source"),
                "İnsan İncelemesi Gerekli": preview.get("human_review_required"),
                "Sınır Engelli": preview.get("blocked_by_boundary"),
                "Engel Sebepleri": preview.get("blocked_reasons", []),
                "Devam Etmek Güvenli": preview.get("safe_to_continue"),
                "Önerilen Sonraki Adım": preview.get("recommended_next_action"),
                "Önerilen Onay Yolu": preview.get("recommended_approval_path"),
                "Gerekli Doğrulamalar": preview.get("required_validations", []),
                "Gerekli Testler": preview.get("required_tests", []),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_patch_execution_readiness() -> List[Dict[str, Any]]:
    registry = patch_execution_registry()
    executions = registry.get("executions", [])
    output: List[Dict[str, Any]] = []
    for item in executions[:5]:
        preview = build_patch_execution_preview(
            target_issue=str(item.get("id", "")),
            command=str(item.get("id", "")),
            project_area=str(item.get("id", "")),
            related_layer="Layer 27.6",
        )
        output.append(
            {
                "Hedef Sorun": preview.get("target_issue"),
                "Hedef Bileşen": preview.get("target_component"),
                "Çalıştırmaya Hazır": preview.get("execution_ready"),
                "Hazırlık Skoru": preview.get("readiness_score"),
                "Go/No-Go Durumu": preview.get("go_no_go_status"),
                "Engeller": preview.get("blockers", []),
                "Engel Sebepleri": preview.get("blocking_reasons", []),
                "Eksik Gereksinimler": preview.get("missing_requirements", []),
                "Gerekli Onaylar": preview.get("required_approvals", []),
                "Gerekli Doğrulamalar": preview.get("required_validations", []),
                "Gerekli Testler": preview.get("required_tests", []),
                "Doğrulama Hazır": preview.get("verification_ready"),
                "Geri Alma Gerekli": preview.get("rollback_required"),
                "Geri Alma Stratejisi": preview.get("rollback_strategy"),
                "Çalıştırma Yolu": preview.get("execution_path"),
                "Önerilen Sonraki Adım": preview.get("recommended_next_action"),
                "confidence_score": preview.get("confidence_score"),
            }
        )
    return output


def _fault_report_patch_rollback() -> List[Dict[str, Any]]:
    registry = patch_rollback_registry()
    rollbacks = registry.get("rollbacks", [])
    output: List[Dict[str, Any]] = []
    for item in rollbacks[:5]:
        preview = build_patch_rollback_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 28.2")
        output.append({
            "Hedef Sorun": preview.get("target_issue"), "Hedef Bileşen": preview.get("target_component"),
            "Rollback Gerekli": preview.get("rollback_required"), "Rollback Seviyesi": preview.get("rollback_level"),
            "Rollback Sebebi": preview.get("rollback_reason"),
            "Tetikleme Koşulları": preview.get("rollback_trigger_conditions", []),
            "Rollback Adımları": preview.get("rollback_steps", []),
            "Doğrulama Adımları": preview.get("rollback_validation_steps", []),
            "Rollback Risk Seviyesi": preview.get("rollback_risk_level"),
            "Rollback Risk Sebepleri": preview.get("rollback_risk_reasons", []),
            "Rollback Bağımlılıkları": preview.get("rollback_dependencies", []),
            "Güvenli Sınır": preview.get("rollback_safe_boundary"),
            "Kurtarma Planı": preview.get("rollback_recovery_plan"),
            "Rollback Hazır": preview.get("rollback_readiness"),
            "Önerilen Sonraki Adım": preview.get("recommended_next_action"),
            "confidence_score": preview.get("confidence_score"),
        })
    return output


def _fault_report_patch_validation() -> List[Dict[str, Any]]:
    reg = patch_validation_registry()
    vs = reg.get("validations", [])
    out: List[Dict[str, Any]] = []
    for item in vs[:5]:
        pv = build_patch_validation_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 28.3")
        out.append({"Hedef Sorun": pv.get("target_issue"), "Hedef Bileşen": pv.get("target_component"),
                     "Doğrulama Gerekli": pv.get("validation_required"), "Doğrulama Durumu": pv.get("validation_status"),
                     "Doğrulama Stratejisi": pv.get("validation_strategy"),
                     "Doğrulama Adımları": pv.get("validation_steps", []),
                     "Doğrulama Kapsamı": pv.get("validation_scope", []),
                     "Doğrulama Risk Seviyesi": pv.get("validation_risk_level"),
                     "Doğrulama Risk Sebepleri": pv.get("validation_risk_reasons", []),
                     "Gerekli Kontroller": pv.get("required_checks", []),
                     "Gerekli Testler": pv.get("required_tests", []),
                     "Başarı Kriterleri": pv.get("success_criteria", []),
                     "Başarısızlık Kriterleri": pv.get("failure_criteria", []),
                     "Rollback Tetikleyici": pv.get("rollback_trigger"),
                     "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
                     "confidence_score": pv.get("confidence_score")})
    return out


def _fault_report_patch_recovery() -> List[Dict[str, Any]]:
    reg = patch_recovery_registry()
    rs = reg.get("recoveries", [])
    out: List[Dict[str, Any]] = []
    for item in rs[:5]:
        pv = build_patch_recovery_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 28.4")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Hata Türü": pv.get("failure_type"),
            "Hata Kapsamı": pv.get("failure_scope"),
            "Kurtarma Gerekli": pv.get("recovery_required"),
            "Kurtarma Stratejisi": pv.get("recovery_strategy"),
            "Kurtarma Adımları": pv.get("recovery_steps", []),
            "Kurtarma Bağımlılıkları": pv.get("recovery_dependencies", []),
            "Kurtarma Risk Seviyesi": pv.get("recovery_risk_level"),
            "Kurtarma Risk Sebepleri": pv.get("recovery_risk_reasons", []),
            "Rollback Bağımlılığı": pv.get("rollback_dependency"),
            "Validasyon Bağımlılığı": pv.get("validation_dependency"),
            "Kurtarma Hazır": pv.get("recovery_readiness"),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_audit_trail() -> List[Dict[str, Any]]:
    reg = patch_audit_registry()
    audits = reg.get("audits", [])
    out: List[Dict[str, Any]] = []
    for item in audits[:5]:
        pv = build_patch_audit_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 28.5")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Audit ID": pv.get("audit_id"),
            "Olay Sayısı": len(pv.get("timeline_events", [])),
            "Etkilenen Katmanlar": pv.get("affected_layers", []),
            "Etkilenen Dosyalar": pv.get("affected_files", []),
            "Etkilenen Endpointler": pv.get("affected_endpoints", []),
            "Karar Zinciri": pv.get("decision_chain", []),
            "Denetim Tamamlığı": pv.get("audit_completeness"),
            "Denetim Hazır": pv.get("audit_readiness"),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_lifecycle() -> List[Dict[str, Any]]:
    reg = patch_lifecycle_registry()
    lifecycles = reg.get("lifecycles", [])
    out: List[Dict[str, Any]] = []
    for item in lifecycles[:5]:
        pv = build_patch_lifecycle_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 28.6")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Lifecycle ID": pv.get("lifecycle_id"),
            "Mevcut Aşama": pv.get("current_stage"),
            "Tamamlanan Aşamalar": pv.get("completed_stages", []),
            "Kalan Aşamalar": pv.get("remaining_stages", []),
            "Yaşam Döngüsü Hazır": pv.get("lifecycle_readiness"),
            "Tamamlanma Skoru": pv.get("completion_score"),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_permission() -> List[Dict[str, Any]]:
    reg = patch_permission_registry()
    permissions = reg.get("permissions", [])
    out: List[Dict[str, Any]] = []
    for item in permissions[:5]:
        pv = build_patch_permission_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.1")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "İzin Seviyesi": pv.get("permission_level"),
            "İzin Kaynağı": pv.get("permission_source"),
            "İzin Verilenler": pv.get("allowed_actions", []),
            "Engellenenler": pv.get("blocked_actions", []),
            "Gerekli Onaylar": pv.get("required_approvals", []),
            "Gerekli Validasyonlar": pv.get("required_validations", []),
            "Gerekli Sınırlar": pv.get("required_boundaries", []),
            "İzin Risk Seviyesi": pv.get("permission_risk_level"),
            "İzin Hazır": pv.get("permission_readiness"),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_policy() -> List[Dict[str, Any]]:
    reg = patch_policy_registry()
    policies = reg.get("policies", [])
    out: List[Dict[str, Any]] = []
    for item in policies[:5]:
        pv = build_patch_policy_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.2")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Politika Kategorisi": pv.get("policy_category"),
            "Politika Sonucu": pv.get("policy_result"),
            "Politika Sebebi": pv.get("policy_reason"),
            "Politika Gereksinimleri": pv.get("policy_requirements", []),
            "Politika Kısıtlamaları": pv.get("policy_restrictions", []),
            "Politika İstisnaları": pv.get("policy_exceptions", []),
            "Politika Risk Seviyesi": pv.get("policy_risk_level"),
            "Politika Hazır": pv.get("policy_readiness"),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_compliance() -> List[Dict[str, Any]]:
    reg = patch_compliance_registry()
    compliances = reg.get("compliances", [])
    out: List[Dict[str, Any]] = []
    for item in compliances[:5]:
        pv = build_patch_compliance_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.3")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Uyum Kategorisi": pv.get("compliance_category"),
            "Uyum Durumu": pv.get("compliance_status"),
            "Uyum Gereksinimleri": pv.get("compliance_requirements", []),
            "Uyum İhlalleri": pv.get("compliance_violations", []),
            "Uyum İstisnaları": pv.get("compliance_exceptions", []),
            "Uyum Risk Seviyesi": pv.get("compliance_risk_level"),
            "Uyum Hazır": pv.get("compliance_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_governance() -> List[Dict[str, Any]]:
    reg = patch_governance_registry()
    governances = reg.get("governances", [])
    out: List[Dict[str, Any]] = []
    for item in governances[:5]:
        pv = build_patch_governance_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.4")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Yönetişim Kategorisi": pv.get("governance_category"),
            "Yönetişim Durumu": pv.get("governance_status"),
            "Yönetişim Gereksinimleri": pv.get("governance_requirements", []),
            "Yönetişim Kontrolleri": pv.get("governance_controls", []),
            "Yönetişim İstisnaları": pv.get("governance_exceptions", []),
            "Yönetişim Risk Seviyesi": pv.get("governance_risk_level"),
            "Yönetişim Hazır": pv.get("governance_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_oversight() -> List[Dict[str, Any]]:
    reg = patch_oversight_registry()
    oversights = reg.get("oversights", [])
    out: List[Dict[str, Any]] = []
    for item in oversights[:5]:
        pv = build_patch_oversight_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.5")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Gözetim Kategorisi": pv.get("oversight_category"),
            "Gözetim Durumu": pv.get("oversight_status"),
            "Gözetim Bulguları": pv.get("oversight_findings", []),
            "Gözetim Kontrolleri": pv.get("oversight_controls", []),
            "Gözetim İstisnaları": pv.get("oversight_exceptions", []),
            "Gözetim Risk Seviyesi": pv.get("oversight_risk_level"),
            "Gözetim Hazır": pv.get("oversight_readiness"),
            "Gözetim Önerileri": pv.get("oversight_recommendations", []),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_accountability() -> List[Dict[str, Any]]:
    reg = patch_accountability_registry()
    accountabilities = reg.get("accountabilities", [])
    out: List[Dict[str, Any]] = []
    for item in accountabilities[:5]:
        pv = build_patch_accountability_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.6")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Hesap Verebilirlik Kategorisi": pv.get("accountability_category"),
            "Hesap Verebilirlik Durumu": pv.get("accountability_status"),
            "Sahip": pv.get("accountability_owner"),
            "Kapsam": pv.get("accountability_scope"),
            "Bulgular": pv.get("accountability_findings", []),
            "Gereksinimler": pv.get("accountability_requirements", []),
            "İstisnalar": pv.get("accountability_exceptions", []),
            "Risk Seviyesi": pv.get("accountability_risk_level"),
            "Hazır": pv.get("accountability_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_assurance() -> List[Dict[str, Any]]:
    reg = patch_assurance_registry()
    assurances = reg.get("assurances", [])
    out: List[Dict[str, Any]] = []
    for item in assurances[:5]:
        pv = build_patch_assurance_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.7")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Güvence Kategorisi": pv.get("assurance_category"),
            "Güvence Durumu": pv.get("assurance_status"),
            "Kapsam": pv.get("assurance_scope"),
            "Bulgular": pv.get("assurance_findings", []),
            "Kontroller": pv.get("assurance_controls", []),
            "Gereksinimler": pv.get("assurance_requirements", []),
            "İstisnalar": pv.get("assurance_exceptions", []),
            "Risk Seviyesi": pv.get("assurance_risk_level"),
            "Hazır": pv.get("assurance_readiness"),
            "Güvence Skoru": pv.get("assurance_score"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_patch_confidence() -> List[Dict[str, Any]]:
    reg = patch_confidence_registry()
    confidences = reg.get("confidences", [])
    out: List[Dict[str, Any]] = []
    for item in confidences[:5]:
        pv = build_patch_confidence_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 29.8")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Güven Kategorisi": pv.get("confidence_category"),
            "Güven Durumu": pv.get("confidence_status"),
            "Güven Skoru": pv.get("confidence_score"),
            "Güven Faktörleri": pv.get("confidence_factors", []),
            "Bulgular": pv.get("confidence_findings", []),
            "Gereksinimler": pv.get("confidence_requirements", []),
            "İstisnalar": pv.get("confidence_exceptions", []),
            "Risk Seviyesi": pv.get("confidence_risk_level"),
            "Hazır": pv.get("confidence_readiness"),
            "Gerekçe": pv.get("confidence_reasoning"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
        })
    return out


def _fault_report_production_readiness() -> List[Dict[str, Any]]:
    reg = production_readiness_registry()
    readiness_items = reg.get("readiness_items", [])
    out: List[Dict[str, Any]] = []
    for item in readiness_items[:5]:
        pv = build_production_readiness_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 30.1")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Hazırlık Kategorisi": pv.get("readiness_category"),
            "Hazırlık Durumu": pv.get("readiness_status"),
            "Hazırlık Skoru": pv.get("readiness_score"),
            "Gereksinimler": pv.get("readiness_requirements", []),
            "Bulgular": pv.get("readiness_findings", []),
            "Engelleyiciler": pv.get("readiness_blockers", []),
            "Risk Seviyesi": pv.get("readiness_risk_level"),
            "Öneriler": pv.get("readiness_recommendations", []),
            "Üretime Hazır": pv.get("production_ready"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_operational_readiness() -> List[Dict[str, Any]]:
    reg = operational_readiness_registry()
    operational_items = reg.get("operational_items", [])
    out: List[Dict[str, Any]] = []
    for item in operational_items[:5]:
        pv = build_operational_readiness_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 30.2")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Operasyonel Kategori": pv.get("operational_category"),
            "Operasyonel Durum": pv.get("operational_status"),
            "Operasyonel Skor": pv.get("operational_score"),
            "Gereksinimler": pv.get("operational_requirements", []),
            "Bulgular": pv.get("operational_findings", []),
            "Engelleyiciler": pv.get("operational_blockers", []),
            "Risk Seviyesi": pv.get("operational_risk_level"),
            "Öneriler": pv.get("operational_recommendations", []),
            "Operasyonel Hazır": pv.get("operational_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_system_readiness() -> List[Dict[str, Any]]:
    reg = system_readiness_registry()
    system_items = reg.get("system_items", [])
    out: List[Dict[str, Any]] = []
    for item in system_items[:5]:
        pv = build_system_readiness_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 30.3")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Sistem Kategorisi": pv.get("system_category"),
            "Sistem Durumu": pv.get("system_status"),
            "Sistem Skoru": pv.get("system_score"),
            "Gereksinimler": pv.get("system_requirements", []),
            "Bulgular": pv.get("system_findings", []),
            "Engelleyiciler": pv.get("system_blockers", []),
            "Risk Seviyesi": pv.get("system_risk_level"),
            "Öneriler": pv.get("system_recommendations", []),
            "Sistem Hazır": pv.get("system_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_validation_readiness() -> List[Dict[str, Any]]:
    reg = validation_readiness_registry()
    validation_items = reg.get("validation_items", [])
    out: List[Dict[str, Any]] = []
    for item in validation_items[:5]:
        pv = build_validation_readiness_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 30.4")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Doğrulama Kategorisi": pv.get("validation_category"),
            "Doğrulama Durumu": pv.get("validation_status"),
            "Doğrulama Skoru": pv.get("validation_score"),
            "Gereksinimler": pv.get("validation_requirements", []),
            "Bulgular": pv.get("validation_findings", []),
            "Engelleyiciler": pv.get("validation_blockers", []),
            "Risk Seviyesi": pv.get("validation_risk_level"),
            "Öneriler": pv.get("validation_recommendations", []),
            "Doğrulama Hazır": pv.get("validation_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_release_readiness() -> List[Dict[str, Any]]:
    reg = release_readiness_registry()
    release_items = reg.get("release_items", [])
    out: List[Dict[str, Any]] = []
    for item in release_items[:5]:
        pv = build_release_readiness_preview(
            target_issue=str(item.get("id", "")), command=str(item.get("id", "")),
            project_area=str(item.get("id", "")), related_layer="Layer 30.5")
        out.append({
            "Hedef Sorun": pv.get("target_issue"),
            "Hedef Bileşen": pv.get("target_component"),
            "Sürüm Kategorisi": pv.get("release_category"),
            "Sürüm Durumu": pv.get("release_status"),
            "Sürüm Skoru": pv.get("release_score"),
            "Gereksinimler": pv.get("release_requirements", []),
            "Bulgular": pv.get("release_findings", []),
            "Engelleyiciler": pv.get("release_blockers", []),
            "Risk Seviyesi": pv.get("release_risk_level"),
            "Öneriler": pv.get("release_recommendations", []),
            "Sürüm Hazır": pv.get("release_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_system_health_intelligence() -> List[Dict[str, Any]]:
    reg = system_health_intelligence_registry()
    health_items = reg.get("health_items", [])
    out: List[Dict[str, Any]] = []
    for item in health_items[:5]:
        pv = build_system_health_intelligence_preview(
            target_issue=str(item.get("health_id", "")), command=str(item.get("health_id", "")),
            project_area=str(item.get("health_id", "")), related_layer="Layer 31.1")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Sağlık ID": pv.get("health_id"),
            "Sağlık Kategorisi": pv.get("health_category"),
            "Sağlık Durumu": pv.get("health_status"),
            "Sağlık Skoru": pv.get("health_score"),
            "Bulgular": pv.get("health_findings", []),
            "Uyarılar": pv.get("health_warnings", []),
            "Engelleyiciler": pv.get("health_blockers", []),
            "Risk Seviyesi": pv.get("health_risk_level"),
            "Öneriler": pv.get("health_recommendations", []),
            "Sağlık Özeti": pv.get("health_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_layer31_status_snapshot() -> List[Dict[str, Any]]:
    ss = layer31_status_snapshot()
    return [{
        "Katman Sayısı": ss.get("layer_count"),
        "Uç Nokta Sayısı": ss.get("endpoint_count"),
        "Entegrasyon Sayısı": ss.get("integration_count"),
        "Genel Runtime Skoru": ss.get("overall_runtime_score"),
        "Genel Runtime Durumu": ss.get("overall_runtime_status"),
        "Sağlık Skoru": ss.get("health_score"),
        "Sağlık Durumu": ss.get("health_status"),
        "Stabilite Skoru": ss.get("stability_score"),
        "Stabilite Durumu": ss.get("stability_status"),
        "Risk Skoru": ss.get("risk_score"),
        "Risk Durumu": ss.get("risk_status"),
        "Sapma Skoru": ss.get("drift_score"),
        "Sapma Durumu": ss.get("drift_status"),
        "Kurtarma Skoru": ss.get("recovery_score"),
        "Kurtarma Durumu": ss.get("recovery_status"),
        "Önerilen Sonraki Katman": ss.get("recommended_next_layer"),
        "confidence_score": 0.85,
    }]


def _fault_report_layer32_status_snapshot() -> List[Dict[str, Any]]:
    ss = layer32_status_snapshot()
    return [{
        "Katman Sayısı": ss.get("layer_count"),
        "Uç Nokta Sayısı": ss.get("endpoint_count"),
        "Entegrasyon Sayısı": ss.get("integration_count"),
        "Genel Layer32 Skoru": ss.get("overall_layer32_score"),
        "Genel Layer32 Durumu": ss.get("overall_layer32_status"),
        "Anomali Skoru": ss.get("anomaly_score"),
        "Anomali Durumu": ss.get("anomaly_status"),
        "Regresyon Skoru": ss.get("regression_score"),
        "Regresyon Durumu": ss.get("regression_status"),
        "Hata Hafıza Skoru": ss.get("failure_memory_score"),
        "Hata Hafıza Durumu": ss.get("failure_memory_status"),
        "Kök Neden Skoru": ss.get("root_cause_score"),
        "Kök Neden Durumu": ss.get("root_cause_status"),
        "Bağımlılık Skoru": ss.get("dependency_score"),
        "Bağımlılık Durumu": ss.get("dependency_status"),
        "Önerilen Sonraki Katman": ss.get("recommended_next_layer"),
        "confidence_score": 0.85,
    }]


def _fault_report_runtime_recovery_intelligence() -> List[Dict[str, Any]]:
    reg = runtime_recovery_intelligence_registry()
    recovery_items = reg.get("recovery_items", [])
    out: List[Dict[str, Any]] = []
    for item in recovery_items[:5]:
        pv = build_runtime_recovery_intelligence_preview(
            target_issue=str(item.get("recovery_id", "")), command=str(item.get("recovery_id", "")),
            project_area=str(item.get("recovery_id", "")), related_layer="Layer 31.5")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Kurtarma ID": pv.get("recovery_id"),
            "Kurtarma Kategorisi": pv.get("recovery_category"),
            "Kurtarma Durumu": pv.get("recovery_status"),
            "Kurtarma Skoru": pv.get("recovery_score"),
            "Bulgular": pv.get("recovery_findings", []),
            "Uyarılar": pv.get("recovery_warnings", []),
            "Engelleyiciler": pv.get("recovery_blockers", []),
            "Risk Seviyesi": pv.get("recovery_risk_level"),
            "Öneriler": pv.get("recovery_recommendations", []),
            "Kurtarma Özeti": pv.get("recovery_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_runtime_anomaly_intelligence() -> List[Dict[str, Any]]:
    reg = runtime_anomaly_intelligence_registry()
    anomaly_items = reg.get("anomaly_items", [])
    out: List[Dict[str, Any]] = []
    for item in anomaly_items[:5]:
        pv = build_runtime_anomaly_intelligence_preview(
            target_issue=str(item.get("anomaly_id", "")), command=str(item.get("anomaly_id", "")),
            project_area=str(item.get("anomaly_id", "")), related_layer="Layer 32.1")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Anomali ID": pv.get("anomaly_id"),
            "Anomali Kategorisi": pv.get("anomaly_category"),
            "Anomali Durumu": pv.get("anomaly_status"),
            "Anomali Skoru": pv.get("anomaly_score"),
            "Bulgular": pv.get("anomaly_findings", []),
            "Uyarılar": pv.get("anomaly_warnings", []),
            "Engelleyiciler": pv.get("anomaly_blockers", []),
            "Risk Seviyesi": pv.get("anomaly_risk_level"),
            "Öneriler": pv.get("anomaly_recommendations", []),
            "Anomali Özeti": pv.get("anomaly_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_regression_intelligence() -> List[Dict[str, Any]]:
    reg = regression_intelligence_registry()
    regression_items = reg.get("regression_items", [])
    out: List[Dict[str, Any]] = []
    for item in regression_items[:5]:
        pv = build_regression_intelligence_preview(
            target_issue=str(item.get("regression_id", "")), command=str(item.get("regression_id", "")),
            project_area=str(item.get("regression_id", "")), related_layer="Layer 32.2")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Regresyon ID": pv.get("regression_id"),
            "Regresyon Kategorisi": pv.get("regression_category"),
            "Regresyon Durumu": pv.get("regression_status"),
            "Regresyon Skoru": pv.get("regression_score"),
            "Bulgular": pv.get("regression_findings", []),
            "Uyarılar": pv.get("regression_warnings", []),
            "Engelleyiciler": pv.get("regression_blockers", []),
            "Risk Seviyesi": pv.get("regression_risk_level"),
            "Öneriler": pv.get("regression_recommendations", []),
            "Regresyon Özeti": pv.get("regression_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_failure_memory_intelligence() -> List[Dict[str, Any]]:
    reg = failure_memory_intelligence_registry()
    failure_items = reg.get("failure_items", [])
    out: List[Dict[str, Any]] = []
    for item in failure_items[:5]:
        pv = build_failure_memory_intelligence_preview(
            target_issue=str(item.get("failure_id", "")), command=str(item.get("failure_id", "")),
            project_area=str(item.get("failure_id", "")), related_layer="Layer 32.3")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Hata ID": pv.get("failure_id"),
            "Hata Kategorisi": pv.get("failure_category"),
            "Hata Durumu": pv.get("failure_status"),
            "Hata Skoru": pv.get("failure_score"),
            "Bulgular": pv.get("failure_findings", []),
            "Tekrar Eden Desenler": pv.get("failure_patterns", []),
            "Tekrarlama Seviyesi": pv.get("failure_recurrence_level"),
            "Benzer Hatalar": pv.get("similar_failures", []),
            "Başarılı Çözümler": pv.get("successful_resolutions", []),
            "Başarısız Çözümler": pv.get("failed_resolutions", []),
            "Risk Seviyesi": pv.get("failure_risk_level"),
            "Hata Özeti": pv.get("failure_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_dependency_intelligence() -> List[Dict[str, Any]]:
    reg = dependency_intelligence_registry()
    dependency_items = reg.get("dependency_items", [])
    out: List[Dict[str, Any]] = []
    for item in dependency_items[:5]:
        pv = build_dependency_intelligence_preview(
            target_issue=str(item.get("dependency_id", "")), command=str(item.get("dependency_id", "")),
            project_area=str(item.get("dependency_id", "")), related_layer="Layer 32.5")
        out.append({
            "Hedef Bileşen": pv.get("dependency_id"),
            "Bağımlılık ID": pv.get("dependency_id"),
            "Bağımlılık Kategorisi": pv.get("dependency_category"),
            "Bağımlılık Türü": pv.get("dependency_type"),
            "Bağımlılık Durumu": pv.get("dependency_status"),
            "Bağımlılık Skoru": pv.get("dependency_score"),
            "Etkilenen Dosyalar": pv.get("affected_files", []),
            "Etkilenen Modüller": pv.get("affected_modules", []),
            "Etkilenen Sistemler": pv.get("affected_systems", []),
            "Tetiklenen Sistemler": pv.get("triggered_systems", []),
            "Etkilenilen Sistemler": pv.get("impacted_by_systems", []),
            "Bulgular": pv.get("dependency_findings", []),
            "Risk Seviyesi": pv.get("dependency_risk_level"),
            "Öneriler": pv.get("dependency_recommendations", []),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_root_cause_intelligence() -> List[Dict[str, Any]]:
    reg = root_cause_intelligence_registry()
    root_cause_items = reg.get("root_cause_items", [])
    out: List[Dict[str, Any]] = []
    for item in root_cause_items[:5]:
        pv = build_root_cause_intelligence_preview(
            target_issue=str(item.get("root_cause_id", "")), command=str(item.get("root_cause_id", "")),
            project_area=str(item.get("root_cause_id", "")), related_layer="Layer 32.4")
        out.append({
            "Kök Neden ID": pv.get("root_cause_id"),
            "Kök Neden Kategorisi": pv.get("root_cause_category"),
            "Kök Neden Durumu": pv.get("root_cause_status"),
            "Kök Neden Skoru": pv.get("root_cause_score"),
            "Bulgular": pv.get("root_cause_findings", []),
            "Olası Nedenler": pv.get("probable_causes", []),
            "Katkıda Bulunan Faktörler": pv.get("contributing_factors", []),
            "Bağımlılık Bağlantıları": pv.get("dependency_links", []),
            "Tetikleyici Zinciri": pv.get("trigger_chain", []),
            "Neden Güveni": pv.get("cause_confidence"),
            "Risk Seviyesi": pv.get("root_cause_risk_level"),
            "Özet": pv.get("root_cause_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_change_memory_intelligence() -> List[Dict[str, Any]]:
    reg = change_memory_intelligence_registry()
    change_items = reg.get("change_items", [])
    out: List[Dict[str, Any]] = []
    for item in change_items[:5]:
        pv = build_change_memory_intelligence_preview(
            target_issue=str(item.get("change_id", "")), command=str(item.get("change_id", "")),
            project_area=str(item.get("change_id", "")), related_layer="Layer 33.1")
        out.append({
            "Değişiklik ID": pv.get("change_id"),
            "Değişiklik Kategorisi": pv.get("change_category"),
            "Değişiklik Türü": pv.get("change_type"),
            "Değişiklik Durumu": pv.get("change_status"),
            "Değişiklik Skoru": pv.get("change_score"),
            "Bulgular": pv.get("change_summary"),
            "Desenler": pv.get("change_patterns", []),
            "Benzer Değişiklikler": pv.get("similar_changes", []),
            "Başarılı Değişiklikler": pv.get("successful_changes", []),
            "Başarısız Değişiklikler": pv.get("failed_changes", []),
            "Tekrarlama Seviyesi": pv.get("change_recurrence_level"),
            "Risk Seviyesi": pv.get("change_risk_level"),
            "Öneriler": pv.get("change_recommendations", []),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("change_confidence"),
        })
    return out


def _fault_report_failed_change_intelligence() -> List[Dict[str, Any]]:
    reg = failed_change_intelligence_registry()
    failed_change_items = reg.get("failed_change_items", [])
    out: List[Dict[str, Any]] = []
    for item in failed_change_items[:5]:
        pv = build_failed_change_intelligence_preview(
            target_issue=str(item.get("failed_change_id", "")), command=str(item.get("failed_change_id", "")),
            project_area=str(item.get("failed_change_id", "")), related_layer="Layer 33.2")
        out.append({
            "Başarısız Değişiklik ID": pv.get("failed_change_id"),
            "Başarısız Değişiklik Kategorisi": pv.get("failed_change_category"),
            "Başarısız Değişiklik Türü": pv.get("failed_change_type"),
            "Başarısız Değişiklik Durumu": pv.get("failed_change_status"),
            "Başarısız Değişiklik Skoru": pv.get("failed_change_score"),
            "Bulgular": pv.get("failed_change_summary"),
            "Başarısız Desenler": pv.get("failed_change_patterns", []),
            "Benzer Başarısızlıklar": pv.get("similar_failed_changes", []),
            "Tekrarlanan Başarısızlıklar": pv.get("repeated_failures", []),
            "Tekrarlama Seviyesi": pv.get("failure_recurrence_level"),
            "Risk Seviyesi": pv.get("failure_risk_level"),
            "Kaçınma Önerileri": pv.get("avoidance_recommendations", []),
            "Öneriler": pv.get("failure_recommendations", []),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("failure_confidence"),
        })
    return out


def _fault_report_change_planning_intelligence() -> List[Dict[str, Any]]:
    reg = change_planning_intelligence_registry()
    plan_items = reg.get("plan_items", [])
    out: List[Dict[str, Any]] = []
    for item in plan_items[:5]:
        pv = build_change_planning_intelligence_preview(
            target_issue=str(item.get("plan_id", "")), command=str(item.get("plan_id", "")),
            project_area=str(item.get("plan_id", "")), related_layer="Layer 33.3")
        out.append({
            "Plan ID": pv.get("plan_id"),
            "Plan Türü": pv.get("plan_type"),
            "Plan Durumu": pv.get("plan_status"),
            "Plan Skoru": pv.get("plan_score"),
            "Önerilen Strateji": pv.get("recommended_strategy"),
            "Alternatif Stratejiler": pv.get("alternative_strategies", []),
            "Kaçınılacak Stratejiler": pv.get("avoided_strategies", []),
            "Gerekli Dosyalar": pv.get("required_files", []),
            "Etkilenen Dosyalar": pv.get("affected_files", []),
            "Bağımlılık Zinciri": pv.get("dependency_chain", []),
            "Tahmini Risk": pv.get("estimated_risk"),
            "Tahmini Karmaşıklık": pv.get("estimated_complexity"),
            "Tahmini Çaba": pv.get("estimated_effort"),
            "Doğrulama Adımları": pv.get("validation_steps", []),
            "Geri Alma Stratejisi": pv.get("rollback_strategy"),
            "Özet": pv.get("plan_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_clone_workspace_intelligence() -> List[Dict[str, Any]]:
    from clone_workspace_intelligence_preview import clone_workspace_intelligence_registry, build_clone_workspace_intelligence_preview
    reg = clone_workspace_intelligence_registry()
    workspace_items = reg.get("workspace_items", [])
    out: List[Dict[str, Any]] = []
    for item in workspace_items[:5]:
        pv = build_clone_workspace_intelligence_preview(
            target_issue=str(item.get("workspace_id", "")), command=str(item.get("workspace_id", "")),
            project_area=str(item.get("workspace_id", "")), related_layer="Layer 33.4")
        out.append({
            "Çalışma Alanı ID": pv.get("workspace_id"),
            "Çalışma Alanı Türü": pv.get("workspace_type"),
            "Çalışma Alanı Durumu": pv.get("workspace_status"),
            "Ana Klon Durumu": pv.get("master_clone_status"),
            "Çalışma Klonu Durumu": pv.get("working_clone_status"),
            "Senkronizasyon Durumu": pv.get("sync_status"),
            "Senkronizasyon Skoru": pv.get("sync_score"),
            "Klon Bütünlük Skoru": pv.get("clone_integrity_score"),
            "Klon Sağlık Skoru": pv.get("clone_health_score"),
            "Özet": pv.get("workspace_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_sandbox_repair_intelligence() -> List[Dict[str, Any]]:
    reg = sandbox_repair_intelligence_registry()
    repair_items = reg.get("repair_items", [])
    out: List[Dict[str, Any]] = []
    for item in repair_items[:5]:
        pv = build_sandbox_repair_intelligence_preview(
            target_issue=str(item.get("repair_id", "")), command=str(item.get("repair_id", "")),
            project_area=str(item.get("repair_id", "")), related_layer="Layer 33.5")
        out.append({
            "Onarım ID": pv.get("repair_id"),
            "Onarım Türü": pv.get("repair_type"),
            "Onarım Durumu": pv.get("repair_status"),
            "Onarım Skoru": pv.get("repair_score"),
            "Strateji": pv.get("repair_strategy"),
            "Adımlar": pv.get("repair_steps", []),
            "Çalışma Klonu Durumu": pv.get("working_clone_status"),
            "Sandbox Durumu": pv.get("sandbox_status"),
            "Sandbox Bütünlük Skoru": pv.get("sandbox_integrity_score"),
            "Sandbox Sağlık Skoru": pv.get("sandbox_health_score"),
            "Onarım Doğrulama Skoru": pv.get("repair_validation_score"),
            "Risk Seviyesi": pv.get("repair_risk_level"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("repair_confidence"),
        })
    return out


def _fault_report_verification_intelligence() -> List[Dict[str, Any]]:
    reg = verification_intelligence_registry()
    verification_items = reg.get("verification_items", [])
    out: List[Dict[str, Any]] = []
    for item in verification_items[:5]:
        pv = build_verification_intelligence_preview(
            target_issue=str(item.get("verification_id", "")), command=str(item.get("verification_id", "")),
            project_area=str(item.get("verification_id", "")), related_layer="Layer 33.6")
        out.append({
            "Doğrulama ID": pv.get("verification_id"),
            "Doğrulama Türü": pv.get("verification_type"),
            "Doğrulama Durumu": pv.get("verification_status"),
            "Doğrulama Skoru": pv.get("verification_score"),
            "Özet": pv.get("verification_summary"),
            "Sandbox Doğrulama": pv.get("sandbox_verification_status"),
            "Bağımlılık Doğrulama": pv.get("dependency_verification_status"),
            "Entegrasyon Doğrulama": pv.get("integration_verification_status"),
            "İş Akışı Doğrulama": pv.get("workflow_verification_status"),
            "Regresyon Doğrulama": pv.get("regression_verification_status"),
            "Üretim Doğrulama": pv.get("production_validation_status"),
            "Tüm Kapılar Geçti": pv.get("verification_signals", {}).get("all_gates_passed"),
            "Risk Seviyesi": pv.get("verification_risk_level"),
            "Hazırlık": pv.get("verification_readiness"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("verification_confidence"),
        })
    return out


def _fault_report_delivery_readiness_intelligence() -> List[Dict[str, Any]]:
    reg = delivery_readiness_intelligence_registry()
    delivery_items = reg.get("delivery_items", [])
    out: List[Dict[str, Any]] = []
    for item in delivery_items[:5]:
        pv = build_delivery_readiness_intelligence_preview(
            target_issue=str(item.get("delivery_id", "")), command=str(item.get("delivery_id", "")),
            project_area=str(item.get("delivery_id", "")), related_layer="Layer 33.7")
        out.append({
            "Teslimat ID": pv.get("delivery_id"),
            "Teslimat Durumu": pv.get("delivery_status"),
            "Teslimat Skoru": pv.get("delivery_score"),
            "Özet": pv.get("delivery_summary"),
            "Güven": pv.get("delivery_confidence"),
            "Risk Seviyesi": pv.get("delivery_risk_level"),
            "Hazırlık": pv.get("delivery_readiness"),
            "Sürüm Adayı": pv.get("release_candidate_status"),
            "Blokerlar": pv.get("release_blockers", []),
            "Uyarılar": pv.get("release_warnings", []),
            "Dağıtım Hazırlığı": pv.get("deployment_readiness"),
            "Geri Alma Hazırlığı": pv.get("rollback_readiness"),
            "Devir Hazırlığı": pv.get("handoff_readiness"),
            "Dokümantasyon Hazırlığı": pv.get("documentation_readiness"),
            "Nihai Tavsiye": pv.get("final_delivery_recommendation"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("delivery_confidence"),
        })
    return out


def _fault_report_runtime_drift_intelligence() -> List[Dict[str, Any]]:
    reg = runtime_drift_intelligence_registry()
    drift_items = reg.get("drift_items", [])
    out: List[Dict[str, Any]] = []
    for item in drift_items[:5]:
        pv = build_runtime_drift_intelligence_preview(
            target_issue=str(item.get("drift_id", "")), command=str(item.get("drift_id", "")),
            project_area=str(item.get("drift_id", "")), related_layer="Layer 31.4")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Sapma ID": pv.get("drift_id"),
            "Sapma Kategorisi": pv.get("drift_category"),
            "Sapma Durumu": pv.get("drift_status"),
            "Sapma Skoru": pv.get("drift_score"),
            "Bulgular": pv.get("drift_findings", []),
            "Uyarılar": pv.get("drift_warnings", []),
            "Engelleyiciler": pv.get("drift_blockers", []),
            "Risk Seviyesi": pv.get("drift_risk_level"),
            "Öneriler": pv.get("drift_recommendations", []),
            "Sapma Özeti": pv.get("drift_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_runtime_risk_intelligence() -> List[Dict[str, Any]]:
    reg = runtime_risk_intelligence_registry()
    risk_items = reg.get("risk_items", [])
    out: List[Dict[str, Any]] = []
    for item in risk_items[:5]:
        pv = build_runtime_risk_intelligence_preview(
            target_issue=str(item.get("risk_id", "")), command=str(item.get("risk_id", "")),
            project_area=str(item.get("risk_id", "")), related_layer="Layer 31.3")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Risk ID": pv.get("risk_id"),
            "Risk Kategorisi": pv.get("risk_category"),
            "Risk Durumu": pv.get("risk_status"),
            "Risk Skoru": pv.get("risk_score"),
            "Bulgular": pv.get("risk_findings", []),
            "Uyarılar": pv.get("risk_warnings", []),
            "Engelleyiciler": pv.get("risk_blockers", []),
            "Risk Seviyesi": pv.get("risk_level"),
            "Öneriler": pv.get("risk_recommendations", []),
            "Risk Özeti": pv.get("risk_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_runtime_stability_intelligence() -> List[Dict[str, Any]]:
    reg = runtime_stability_intelligence_registry()
    stability_items = reg.get("stability_items", [])
    out: List[Dict[str, Any]] = []
    for item in stability_items[:5]:
        pv = build_runtime_stability_intelligence_preview(
            target_issue=str(item.get("stability_id", "")), command=str(item.get("stability_id", "")),
            project_area=str(item.get("stability_id", "")), related_layer="Layer 31.2")
        out.append({
            "Hedef Bileşen": pv.get("target_component"),
            "Kararlılık ID": pv.get("stability_id"),
            "Kararlılık Kategorisi": pv.get("stability_category"),
            "Kararlılık Durumu": pv.get("stability_status"),
            "Kararlılık Skoru": pv.get("stability_score"),
            "Bulgular": pv.get("stability_findings", []),
            "Uyarılar": pv.get("stability_warnings", []),
            "Engelleyiciler": pv.get("stability_blockers", []),
            "Risk Seviyesi": pv.get("stability_risk_level"),
            "Öneriler": pv.get("stability_recommendations", []),
            "Kararlılık Özeti": pv.get("stability_summary"),
            "Gerekli Aksiyonlar": pv.get("required_actions", []),
            "Önerilen Sonraki Adım": pv.get("recommended_next_action"),
            "confidence_score": pv.get("confidence_score"),
        })
    return out


def _fault_report_safe_patch_application() -> List[Dict[str, Any]]:
    registry = safe_patch_registry()
    patches = registry.get("patches", [])
    output: List[Dict[str, Any]] = []
    for item in patches[:5]:
        preview = build_safe_patch_preview(
            target_issue=str(item.get("id", "")),
            command=str(item.get("id", "")),
            project_area=str(item.get("id", "")),
            related_layer="Layer 28.1",
        )
        output.append({
            "Hedef Sorun": preview.get("target_issue"),
            "Hedef Bileşen": preview.get("target_component"),
            "Patch Plan ID": preview.get("patch_plan_id"),
            "Uygulamaya Hazır": preview.get("application_ready"),
            "Uygulama Adımları": preview.get("application_steps", []),
            "Etkilenen Dosyalar": preview.get("affected_files", []),
            "Etkilenen Fonksiyonlar": preview.get("affected_functions", []),
            "Ön Kontroller": preview.get("pre_checks", []),
            "Son Kontroller": preview.get("post_checks", []),
            "Geri Alma Planı": preview.get("rollback_plan"),
            "Onay Gerekli": preview.get("approval_required"),
            "Doğrulama Gerekli": preview.get("verification_required"),
            "Risk Seviyesi": preview.get("risk_level"),
            "confidence_score": preview.get("confidence_score"),
        })
    return output


def fault_report_status() -> Dict[str, Any]:
    return {
        "layer": "24",
        "name": "Lux Fault Report",
        "status": "read_only_preview",
        "read_only": True,
        "real_write_performed": False,
        "real_file_write_performed": False,
        "real_db_write_performed": False,
        "real_memory_write_performed": False,
        "real_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "summary_cards": {
            "open_issues": len(OPEN_ISSUES),
            "under_review": sum(1 for item in OPEN_ISSUES if item.get("status") == "İnceleniyor"),
            "resolved": len(RESOLVED_ISSUES),
            "deferred": len(DEFERRED_ISSUES),
        },
        "latest_update": _to_iso(datetime(2026, 6, 8, 20, 10)),
        "safety_note": (
            "Developer/debug preview only. No chat/stream/websocket/typewriter changes, "
            "no real actions, writes, or memory persistence."
        ),
    }


def fault_report_intelligence_status() -> Dict[str, Any]:
    return {
        "layer": "24",
        "name": "Lux Fault Report Intelligence Preview",
        "status": "preview_ready",
        "read_only": True,
        "analysis_only": True,
        "connected_layer": "23",
        "connected_components": [
            "/debug/root-flow-auditor-status",
            "/debug/self-check-status",
            "/debug/bug-intake-status",
            "/debug/credit-saver-status",
            "/debug/intelligence-status",
            "/debug/codex-handoff-status",
            "/debug/investigation-context-status",
            "/debug/investigation-context-registry",
        ],
        "recent_readiness": "single issue cards are linked to Layer 23 analysis previews",
        "connected_layer24": [
            "/debug/investigation-context-status",
            "/debug/investigation-context-registry",
            "/debug/investigation-context-preview",
        ],
        "real_fix_performed": False,
        "analysis_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "file_write_performed": False,
        "file_write_enabled": False,
        "memory_write_performed": False,
        "memory_write_enabled": False,
        "db_write_performed": False,
        "db_write_enabled": False,
        "real_code_fix_performed": False,
        "safety_note": (
            "This endpoint only links fault cards to Layer 23 diagnostics. "
            "No runtime behavior, code, file, memory, db, or stream/write changes."
        ),
    }


def fault_report_intelligence_registry() -> Dict[str, Any]:
    issue_list = [
        {
            "id": _normalize(item["title"]),
            "title": item["title"],
            "source_section": item.get("source_section", "manual"),
            "status": item.get("status"),
            "priority": item.get("priority"),
            "related_layers": item.get("related_layers", []),
            "default_layer23_references": {
                "status": "ready",
                "recommended_endpoints": DEFAULT_INTELLIGENCE_ENDPOINTS,
            },
        }
        for item in _iter_all_issues()
    ]
    for item in issue_list:
        item["investigation_timeline"] = {
            "issue_title": item.get("title", ""),
            "current_status": item.get("status", ""),
            "recommended_next_step": "open fault card and validate timeline continuity",
            "recommended_endpoint": "/debug/investigation-timeline-preview",
            "active_investigation_context": build_investigation_context_preview(
                active_task="stop_continue" if "dur" in _normalize(item["title"]) or "devam" in _normalize(item["title"]) else "",
                goal="verify timeline continuity and repeatability",
                command=f"issue:{item['title']}",
                expected_result="investigation timeline should remain deterministic",
            ),
        }

    return {
        "layer": "24.1",
        "status": "intelligence_link_ready",
        "read_only": True,
        "analysis_ready": True,
        "issue_count": len(issue_list),
        "issues": issue_list,
        "layer23_analysis_endpoints": DEFAULT_INTELLIGENCE_ENDPOINTS,
        "related_endpoints": {
            "status": list(LAYER23_ANALYSIS_LINKS.keys()),
            "recommended": DEFAULT_INTELLIGENCE_ENDPOINTS + [
                "/debug/root-flow-audit",
                "/debug/self-check-preview",
                "/debug/investigation-context-status",
                "/debug/investigation-context-registry",
                "/debug/investigation-context-preview",
            ],
        },
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def build_fault_report_intelligence_preview(
    focus: Optional[str] = None,
    status: Optional[str] = None,
    related_layer: Optional[str] = None,
    behavior: Optional[str] = None,
    issue_title: Optional[str] = None,
    command: str = "",
) -> Dict[str, Any]:
    issue = _pick_issue(
        issue_title=issue_title,
        focus=focus,
        status=status,
        related_layer=related_layer,
        command=command,
    )
    summary_for_analysis = " ".join(
        [
            issue.get("title", ""),
            issue.get("summary", ""),
            issue.get("notes", ""),
            str(issue.get("priority", "")),
        ]
    )

    root_flow = build_root_flow_audit(
        command=summary_for_analysis,
        behavior=behavior,
        observed_behavior=issue.get("notes", ""),
        expected_behavior="issue card must stay aligned with diagnostic owner and continuation safety",
        smoke_tests=[],
    )

    detected_behavior = str(root_flow.get("detected_behavior", behavior or "endpoint_regression"))
    self_check = build_self_check_preview(
        command=summary_for_analysis,
        behavior=detected_behavior,
        observed_behavior=issue.get("notes", ""),
        expected_behavior="safe continuation + no duplicate branch + no stale fallback",
        requested_checks=[],
    )
    bug_intake = build_bug_intake_preview(
        behavior=detected_behavior,
        symptom=issue.get("summary", ""),
        expected_result="kartın tekrar eden regresyonlarında stabil çözüm",
        actual_result=issue.get("notes", ""),
        command=summary_for_analysis,
    )
    handoff = build_codex_handoff_preview(
        behavior=detected_behavior,
        symptom=issue.get("summary", ""),
        expected_result="kartın gerçek davranışa göre güvenli şekilde kapatılabilir plan",
        actual_result=issue.get("notes", ""),
        command=summary_for_analysis,
    )
    investigation_context = build_investigation_context_preview(
        active_task=detected_behavior,
        goal="keep issue investigation actionable and non-destructive",
        command=summary_for_analysis,
        expected_result="issue loop must be resumable with clear next steps",
        risk_level="medium",
        completed_steps=["initial selection", "layer linkage"],
        remaining_steps=["smoke refresh", "manual scenario run", "owner confirmation"],
    )
    credit = build_credit_saver_preview(
        behavior=detected_behavior,
        symptom=issue.get("summary", ""),
        expected_result="en ucuz ve güvenli analiz rotası",
        actual_result=issue.get("notes", ""),
        command=summary_for_analysis,
    )

    latest_possible_causes = [str(item.get("id")) for item in root_flow.get("possible_root_causes", []) if isinstance(item, dict)]
    suggested_checks = []
    for item in self_check.get("checks_run", []):
        if isinstance(item, dict) and item.get("id"):
            suggested_checks.append(str(item["id"]))
    if not suggested_checks:
        suggested_checks = ["behavior_owner_check", "manual_scenario_check"]
    suggested_checks = _safe_unique(suggested_checks)

    related_layers = issue.get("related_layers", [])
    related_layer23_endpoints = [
        "/debug/root-flow-auditor-status",
        "/debug/self-check-status",
        "/debug/bug-intake-status",
        "/debug/intelligence-status",
    ]
    if "stop_continue" in _normalize(issue.get("title")) or "durdur" in _normalize(issue.get("title")):
        related_layer23_endpoints = [
            "/debug/root-flow-audit",
            "/debug/self-check-preview",
            "/debug/codex-handoff-preview",
            "/debug/credit-saver-preview",
        ]
    if issue.get("status", "").lower() == "açık".lower():
        related_layer23_endpoints.append("/debug/layer23-status")

    related_layer23_endpoints = _safe_unique(related_layer23_endpoints)
    timeline_payload = build_investigation_timeline_preview(
        issue_title=issue["title"],
        command=summary_for_analysis,
        command_behavior=detected_behavior,
    )

    return {
        "raw_issue_title": issue_title or "",
        "focus": focus,
        "status_filter": status,
        "related_layer_filter": related_layer,
        "behavior": behavior,
        "command": command,
        "selected_issue": issue,
        "active_investigation_context": investigation_context,
        "investigation_timeline": {
            "issue_title": timeline_payload.get("issue_title"),
            "current_status": timeline_payload.get("current_status"),
            "latest_finding": timeline_payload.get("latest_finding"),
            "recommended_next_step": timeline_payload.get("recommended_next_step"),
            "timeline_entries": timeline_payload.get("timeline_entries", []),
            "related_layers": timeline_payload.get("related_layers", []),
        },
        "son_analiz": latest_possible_causes[:3] if latest_possible_causes else ["state_source_conflict"],
        "risk": root_flow.get("risk_level", "medium"),
        "confidence_score": root_flow.get("confidence_score", 0.55),
        "recommended_investigation": {
            "first": "root_flow_audit",
            "suggested": ["self_check_preview", "bug_intake_preview"],
        },
        "recommended_checks": suggested_checks,
        "recommended_files": _safe_unique(
            [str(item) for item in root_flow.get("recommended_files", [])] + bug_intake.get("recommended_files", [])
        ),
        "recommended_tests": [
            str(item.get("name")) for item in root_flow.get("manual_tests", []) if isinstance(item, dict)
        ] or ["manual stop/continue regression scenario"],
        "related_layer23_endpoints": related_layer23_endpoints,
        "related_layer24_endpoints": [
            "/debug/investigation-context-status",
            "/debug/investigation-context-registry",
            "/debug/investigation-context-preview",
        ],
        "behavior_owner": {
            "id": detected_behavior,
            "owner": root_flow.get("behavior_owner", {}).get("owner", "unknown"),
            "scope": root_flow.get("behavior_owner", {}).get("scope"),
            "possible_root_causes": latest_possible_causes,
        },
        "state_source": {
            "state_owner": root_flow.get("behavior_owner", {}).get("owner"),
            "source_recommendation": "ARM Runtime State" if "stop" in _normalize(issue.get("title")) else "Active command context",
        },
        "recommended_layer": "root_flow_auditor" if "stop_continue" in _normalize(issue.get("title", "")) else "safe_self_check_runner",
        "last_analysis": {
            "root_flow": root_flow,
            "self_check": self_check,
            "bug_intake": {
                "behavior": bug_intake.get("detected_behavior"),
                "severity": bug_intake.get("severity"),
                "investigation_priority": bug_intake.get("investigation_priority"),
            },
            "codex_handoff": {
                "recommended_files": handoff.get("recommended_files", []),
                "recommended_checks": handoff.get("recommended_checks", []),
                "risk_level": handoff.get("risk_level"),
            },
            "credit_saver": {
                "recommended_path": credit.get("recommended_path"),
                "lux_can_handle": credit.get("lux_can_handle", []),
                "codex_needed_for": credit.get("codex_needed_for", []),
            },
        },
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "real_write_performed": False,
        "real_file_write_performed": False,
        "real_db_write_performed": False,
        "real_memory_write_performed": False,
        "safe_next_step": (
            "Kart icin önerilen Layer 23 analizi calistirilip manual scenario ile "
            "durdurma/devam davranisi dogrulanmali."
        ),
    }


def fault_report_registry() -> Dict[str, Any]:
    return {
        "layer": "24",
        "status": "registry_ready",
        "sections": {
            "open_issues": OPEN_ISSUES,
            "deferred_issues": DEFERRED_ISSUES,
            "resolved_issues": [_attach_knowledge_preview(_attach_timeline_preview(dict(item))) for item in RESOLVED_ISSUES],
            "issue_archive": ARCHIVE,
            "repeated_patterns": _fault_report_repeated_patterns(),
            "investigation_starters": _fault_report_investigation_starters(),
            "priority_engine": _fault_report_priority_engine(),
            "task_plans": _fault_report_task_plans(),
            "dev_agent_explorer": _fault_report_dev_agent_explorer(),
            "dependency_map": _fault_report_dependency_map(),
            "impact_analysis": _fault_report_impact_analysis(),
            "change_boundary": _fault_report_change_boundary(),
            "patch_plans": _fault_report_patch_plans(),
            "verification_plans": _fault_report_verification_plans(),
            "dev_agent_readiness": _fault_report_dev_agent_readiness(),
            "constitution_engine": _fault_report_constitution_engine(),
            "project_rules": _fault_report_project_rules(),
            "explorer_agent": _fault_report_explorer_agent(),
            "planner_agent": _fault_report_planner_agent(),
            "verifier_agent": _fault_report_verifier_agent(),
            "evidence_store": _fault_report_evidence_store(),
            "coordinator": _fault_report_coordinator(),
            "patch_draft": _fault_report_patch_draft(),
            "change_preview": _fault_report_change_preview(),
            "diff_preview": _fault_report_diff_preview(),
            "patch_risk_matrix": _fault_report_patch_risk_matrix(),
            "patch_approval": _fault_report_patch_approval(),
            "patch_execution_readiness": _fault_report_patch_execution_readiness(),
            "layer27_snapshot": layer27_status_snapshot(),
            "layer28_snapshot": layer28_status_snapshot(),
            "layer29_snapshot": layer29_status_snapshot(),
            "layer30_snapshot": layer30_status_snapshot(),
            "safe_patch_application": _fault_report_safe_patch_application(),
            "patch_rollback": _fault_report_patch_rollback(),
            "patch_validation": _fault_report_patch_validation(),
            "patch_recovery": _fault_report_patch_recovery(),
            "patch_audit_trail": _fault_report_patch_audit_trail(),
            "patch_lifecycle": _fault_report_patch_lifecycle(),
            "patch_permission_enforcement": _fault_report_patch_permission(),
            "patch_policy_evaluation": _fault_report_patch_policy(),
            "patch_compliance": _fault_report_patch_compliance(),
            "patch_governance": _fault_report_patch_governance(),
            "patch_oversight": _fault_report_patch_oversight(),
            "patch_accountability": _fault_report_patch_accountability(),
            "patch_assurance": _fault_report_patch_assurance(),
            "patch_confidence": _fault_report_patch_confidence(),
            "production_readiness": _fault_report_production_readiness(),
            "operational_readiness": _fault_report_operational_readiness(),
            "system_readiness": _fault_report_system_readiness(),
            "validation_readiness": _fault_report_validation_readiness(),
            "release_readiness": _fault_report_release_readiness(),
            "system_health_intelligence": _fault_report_system_health_intelligence(),
            "runtime_stability_intelligence": _fault_report_runtime_stability_intelligence(),
            "runtime_risk_intelligence": _fault_report_runtime_risk_intelligence(),
            "runtime_drift_intelligence": _fault_report_runtime_drift_intelligence(),
            "runtime_recovery_intelligence": _fault_report_runtime_recovery_intelligence(),
            "runtime_anomaly_intelligence": _fault_report_runtime_anomaly_intelligence(),
            "regression_intelligence": _fault_report_regression_intelligence(),
            "failure_memory_intelligence": _fault_report_failure_memory_intelligence(),
            "dependency_intelligence": _fault_report_dependency_intelligence(),
            "root_cause_intelligence": _fault_report_root_cause_intelligence(),
            "change_memory_intelligence": _fault_report_change_memory_intelligence(),
            "failed_change_intelligence": _fault_report_failed_change_intelligence(),
            "change_planning_intelligence": _fault_report_change_planning_intelligence(),
            "clone_workspace_intelligence": _fault_report_clone_workspace_intelligence(),
            "sandbox_repair_intelligence": _fault_report_sandbox_repair_intelligence(),
            "verification_intelligence": _fault_report_verification_intelligence(),
            "delivery_readiness_intelligence": _fault_report_delivery_readiness_intelligence(),
            "layer31_status_snapshot": _fault_report_layer31_status_snapshot(),
            "layer32_status_snapshot": _fault_report_layer32_status_snapshot(),
        },
        "related_integrations": {
            "future_ready": [
                "/debug/bug-intake-preview",
                "/debug/root-flow-audit",
                "/debug/self-check-preview",
                "/debug/codex-handoff-preview",
            ],
            "future_plans": [
                "Layer 24.1 real bug persistence",
                "Layer 24.2 issue analytics dashboard",
            ],
        },
        "read_only": True,
        "can_modify_code": False,
        "real_code_fix_performed": False,
    }


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").lower().split())


def build_fault_report_preview(
    focus: Optional[str] = None,
    status: Optional[str] = None,
    related_layer: Optional[str] = None,
    command: str = "",
) -> Dict[str, Any]:
    selected_status = _normalize(status)
    selected_layer = _normalize(related_layer)
    focus_key = _normalize(focus)

    def _matches(issue: Dict[str, Any]) -> bool:
        if selected_status and _normalize(issue.get("status")) != selected_status:
            return False
        if selected_layer:
            layer_hits = _normalize(" ".join(str(item) for item in issue.get("related_layers", [])))
            if selected_layer not in layer_hits:
                return False
        if focus_key and focus_key not in _normalize(issue.get("summary", "")) and focus_key not in _normalize(issue.get("title", "")):
            return False
        return True

    filtered_open = [_attach_timeline_preview(dict(item)) for item in OPEN_ISSUES if _matches(item)]
    filtered_deferred = [_attach_timeline_preview(dict(item)) for item in DEFERRED_ISSUES if _matches(item)]
    filtered_resolved = [
        _attach_knowledge_preview(_attach_timeline_preview(dict(item)))
        for item in RESOLVED_ISSUES
        if _matches(item)
    ]

    if not any([filtered_open, filtered_deferred, filtered_resolved]):
        filtered_open = [_attach_timeline_preview(dict(item)) for item in OPEN_ISSUES[:1]]
        filtered_deferred = [_attach_timeline_preview(dict(item)) for item in DEFERRED_ISSUES[:1]]
        filtered_resolved = [
            _attach_knowledge_preview(_attach_timeline_preview(dict(item)))
            for item in RESOLVED_ISSUES[:1]
        ]
        fallback = True
    else:
        fallback = False

    return {
        "raw_command": command,
        "focus": focus or "all",
        "status_filter": status,
        "layer_filter": related_layer,
        "sections": {
            "open_issues": filtered_open,
            "deferred_issues": filtered_deferred,
            "resolved_issues": filtered_resolved,
            "issue_archive": ARCHIVE[:2],
            "repeated_patterns": _fault_report_repeated_patterns(),
            "investigation_starters": _fault_report_investigation_starters(),
            "priority_engine": _fault_report_priority_engine(),
            "task_plans": _fault_report_task_plans(),
            "dev_agent_explorer": _fault_report_dev_agent_explorer(),
            "dependency_map": _fault_report_dependency_map(),
            "impact_analysis": _fault_report_impact_analysis(),
            "change_boundary": _fault_report_change_boundary(),
            "patch_plans": _fault_report_patch_plans(),
            "verification_plans": _fault_report_verification_plans(),
            "dev_agent_readiness": _fault_report_dev_agent_readiness(),
            "constitution_engine": _fault_report_constitution_engine(),
            "project_rules": _fault_report_project_rules(),
            "explorer_agent": _fault_report_explorer_agent(),
            "planner_agent": _fault_report_planner_agent(),
            "verifier_agent": _fault_report_verifier_agent(),
            "evidence_store": _fault_report_evidence_store(),
            "coordinator": _fault_report_coordinator(),
            "patch_draft": _fault_report_patch_draft(),
            "change_preview": _fault_report_change_preview(),
            "diff_preview": _fault_report_diff_preview(),
            "patch_risk_matrix": _fault_report_patch_risk_matrix(),
            "patch_approval": _fault_report_patch_approval(),
            "patch_execution_readiness": _fault_report_patch_execution_readiness(),
            "layer27_snapshot": layer27_status_snapshot(),
            "layer28_snapshot": layer28_status_snapshot(),
            "layer29_snapshot": layer29_status_snapshot(),
            "layer30_snapshot": layer30_status_snapshot(),
            "safe_patch_application": _fault_report_safe_patch_application(),
            "patch_rollback": _fault_report_patch_rollback(),
            "patch_validation": _fault_report_patch_validation(),
            "patch_permission_enforcement": _fault_report_patch_permission(),
            "patch_policy_evaluation": _fault_report_patch_policy(),
            "patch_compliance": _fault_report_patch_compliance(),
            "patch_governance": _fault_report_patch_governance(),
            "patch_oversight": _fault_report_patch_oversight(),
            "patch_accountability": _fault_report_patch_accountability(),
            "patch_assurance": _fault_report_patch_assurance(),
            "patch_confidence": _fault_report_patch_confidence(),
            "production_readiness": _fault_report_production_readiness(),
            "operational_readiness": _fault_report_operational_readiness(),
            "system_readiness": _fault_report_system_readiness(),
            "validation_readiness": _fault_report_validation_readiness(),
            "release_readiness": _fault_report_release_readiness(),
            "system_health_intelligence": _fault_report_system_health_intelligence(),
            "runtime_stability_intelligence": _fault_report_runtime_stability_intelligence(),
            "runtime_risk_intelligence": _fault_report_runtime_risk_intelligence(),
            "runtime_drift_intelligence": _fault_report_runtime_drift_intelligence(),
            "runtime_recovery_intelligence": _fault_report_runtime_recovery_intelligence(),
            "runtime_anomaly_intelligence": _fault_report_runtime_anomaly_intelligence(),
            "regression_intelligence": _fault_report_regression_intelligence(),
            "failure_memory_intelligence": _fault_report_failure_memory_intelligence(),
            "dependency_intelligence": _fault_report_dependency_intelligence(),
            "root_cause_intelligence": _fault_report_root_cause_intelligence(),
            "change_memory_intelligence": _fault_report_change_memory_intelligence(),
            "failed_change_intelligence": _fault_report_failed_change_intelligence(),
            "change_planning_intelligence": _fault_report_change_planning_intelligence(),
            "clone_workspace_intelligence": _fault_report_clone_workspace_intelligence(),
            "sandbox_repair_intelligence": _fault_report_sandbox_repair_intelligence(),
            "verification_intelligence": _fault_report_verification_intelligence(),
            "delivery_readiness_intelligence": _fault_report_delivery_readiness_intelligence(),
            "layer31_status_snapshot": _fault_report_layer31_status_snapshot(),
            "layer32_status_snapshot": _fault_report_layer32_status_snapshot(),
        },
        "fallback_used": fallback,
        "read_only": True,
        "real_action_performed": False,
        "real_write_performed": False,
        "real_file_write_performed": False,
        "real_db_write_performed": False,
        "real_memory_write_performed": False,
        "safe_next_step": (
            "Kullanıcının yeni durum kartı akışını bozmadan, sadece gözlemlenen filtre "
            "ile özetlenmiş rapor göster."
        ),
    }
