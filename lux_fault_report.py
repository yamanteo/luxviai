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
