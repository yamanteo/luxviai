from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from investigation_context_preview import build_investigation_context_preview

TIMELINE_EVENT_TYPES = [
    "issue_created",
    "audit_started",
    "audit_completed",
    "finding_detected",
    "manual_scenario_added",
    "self_check_completed",
    "credit_saver_evaluated",
    "intelligence_analysis_completed",
    "codex_handoff_generated",
    "issue_resolved",
    "issue_parked",
    "issue_reopened",
]


def _to_iso(value: datetime) -> str:
    return value.replace(microsecond=0, tzinfo=timezone.utc).isoformat()


def _normalize(value: Optional[str]) -> str:
    return " ".join((value or "").strip().lower().split())


BASE_ISSUES: Dict[str, Dict[str, Any]] = {
    "Dur/Devam sistemi": {
        "status": "Inceleniyor",
        "related_layers": ["ARM", "Layer 23", "Stop/Continue", "stream", "websocket"],
        "entries": [
            {"event": "issue_created", "summary": "Dur/Devam davranisinda kesinti bildirimi alindi."},
            {"event": "audit_started", "summary": "Root flow audit baslatildi."},
            {"event": "finding_detected", "summary": "Duplicate resume branch ve state kaynak karmasasi tespit edildi."},
            {"event": "manual_scenario_added", "summary": "Senaryo: 10 maddelik listede 3. maddeden dur-duzeltme kontrolu eklendi."},
            {"event": "self_check_completed", "summary": "Self check ile duplicate branch ve state-source kontrolu yapildi."},
            {"event": "credit_saver_evaluated", "summary": "Otomatik analiz Lux tarafinda uygulanabilir; yeniden endpoint calismasi kod degisikligi gerektirir."},
            {"event": "intelligence_analysis_completed", "summary": "Ayrik resume akisi icin priority owner listelendi."},
            {"event": "codex_handoff_generated", "summary": "Stop/Continue akisi icin Codex handoff hazirlandi."},
            {"event": "issue_reopened", "summary": "Ayni davranis bir kez daha tekrar edip ikinci basamak testlerinde tekrarlandi."},
        ],
        "latest_finding": "duplicate resume branch",
        "recommended_next_step": "resolve duplicate resume handler and unify ARM resume owner",
    },
    "Websocket canlilik drift": {
        "status": "Inceleniyor",
        "related_layers": ["stream", "websocket", "Layer 23", "Layer 17", "typewriter"],
        "entries": [
            {"event": "issue_created", "summary": "Websocket canli akisdaki gecikme ve senkron sapma bildirildi."},
            {"event": "audit_started", "summary": "Stream/websocket yollarinda ilk analiz baslatildi."},
            {"event": "finding_detected", "summary": "Event leak ve queue temizleme sirasi ile tutarsizlik not edildi."},
            {"event": "manual_scenario_added", "summary": "Tab degisim ve gecikmeli delta senaryosu eklendi."},
            {"event": "self_check_completed", "summary": "Manual scenario ve event_leak kontrol sinyal alindi."},
            {"event": "issue_parked", "summary": "Gercek canli akis duzeltmesi Layer 23 sonrasina alindi."},
        ],
        "latest_finding": "event_leak",
        "recommended_next_step": "revisit event queue drain + late done handling",
    },
}


TIMELINE_ADDITIONAL_TAGS: Dict[str, List[Dict[str, str]]] = {
    "stop_continue": [
        {"event": "audit_completed", "summary": "Stop/continue davranisi icin kapsamli tekrar test planlamasi tamamlandi."},
        {"event": "issue_resolved", "summary": "Tekrarlanan devam et davranisi acikca izlenir sekilde loglanabilir durumda."},
    ],
    "default": [
        {"event": "audit_completed", "summary": "Konu bazli inceleme onaylandi ve timeline durumu guncellendi."},
    ],
}


def _pick_issue(issue_title: Optional[str], command: str) -> Dict[str, Any]:
    normalized_title = _normalize(issue_title)
    normalized_command = _normalize(command)

    for title, payload in BASE_ISSUES.items():
        if normalized_title and _normalize(title) in normalized_title:
            return {"title": title, **payload}

    if any(token in normalized_command for token in ("dur", "devam", "continue", "resume")):
        return {"title": "Dur/Devam sistemi", **BASE_ISSUES["Dur/Devam sistemi"]}
    if any(token in normalized_command for token in ("websocket", "ws", "stream", "kanal", "cank", "canlik")):
        return {"title": "Websocket canlilik drift", **BASE_ISSUES["Websocket canlilik drift"]}

    return {"title": list(BASE_ISSUES.keys())[0], **BASE_ISSUES["Dur/Devam sistemi"]}


def investigation_timeline_status() -> Dict[str, Any]:
    return {
        "layer": "24.3",
        "name": "Investigation Timeline Preview",
        "status": "timeline_preview_ready",
        "read_only": True,
        "analysis_only": True,
        "real_action_performed": False,
        "real_file_write_performed": False,
        "real_db_write_performed": False,
        "real_memory_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "file_write_enabled": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "timeline_event_types": TIMELINE_EVENT_TYPES,
        "available_endpoints": [
            "/debug/investigation-timeline-status",
            "/debug/investigation-timeline-registry",
            "/debug/investigation-timeline-preview",
        ],
        "related_layers": [
            "/debug/bug-intake-status",
            "/debug/bug-intake-registry",
            "/debug/root-flow-auditor-status",
            "/debug/root-flow-audit",
            "/debug/self-check-status",
            "/debug/investigation-context-status",
            "/debug/fault-report-status",
            "/debug/fault-report-intelligence-preview",
            "/debug/intelligence-status",
        ],
        "safety_note": (
            "Investigation timeline is read-only diagnostic artifact. "
            "No runtime chat/stream/websocket/typewriter actions or writes are executed."
        ),
    }


def investigation_timeline_registry() -> Dict[str, Any]:
    issues = []
    for title, payload in BASE_ISSUES.items():
        first_entry = payload["entries"][0] if payload["entries"] else {}
        issues.append(
            {
                "issue_title": title,
                "current_status": payload["status"],
                "latest_summary": first_entry.get("summary"),
                "entry_count": len(payload.get("entries", [])),
                "related_layers": payload.get("related_layers", []),
            }
        )

    return {
        "layer": "24.3",
        "name": "Investigation Timeline Registry",
        "status": "timeline_registry_ready",
        "read_only": True,
        "analysis_only": True,
        "timeline_issue_count": len(issues),
        "timeline_event_types": TIMELINE_EVENT_TYPES,
        "issues": issues,
        "connected_endpoints": [
            "/debug/fault-report-status",
            "/debug/fault-report-registry",
            "/debug/fault-report-intelligence-status",
            "/debug/fault-report-intelligence-preview",
            "/debug/investigation-context-status",
            "/debug/investigation-context-registry",
            "/debug/investigation-context-preview",
            "/debug/investigation-timeline-status",
            "/debug/investigation-timeline-preview",
        ],
        "safety_flags": {
            "file_write": False,
            "memory_write": False,
            "db_write": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
    }


def _decorate_context(active_task: str, command: str, issue_title: str) -> Dict[str, Any]:
    context_payload = build_investigation_context_preview(
        active_task=active_task,
        goal=f"Investigate continuation and persistence behavior for {issue_title}",
        command=command,
        expected_result="timeline events and resume state should be deterministic.",
        risk_level="medium",
    )

    return {
        "active_task": context_payload.get("active_task"),
        "current_status": context_payload.get("current_status", "ready"),
        "current_findings": context_payload.get("current_findings", []),
        "suspected_causes": context_payload.get("suspected_causes", []),
        "recommended_next_step": context_payload.get("recommended_next_step"),
    }


def build_investigation_timeline_preview(
    issue_title: Optional[str] = None,
    command: str = "",
    current_status: Optional[str] = None,
    command_behavior: Optional[str] = None,
) -> Dict[str, Any]:
    issue = _pick_issue(issue_title, command)
    base_entries = list(issue.get("entries", []))
    issue_key = "stop_continue" if "dur" in _normalize(issue["title"]) or "devam" in _normalize(issue["title"]) else "default"
    timeline_entries: List[Dict[str, Any]] = []

    start_time = datetime(2026, 6, 9, 8, 0, 0, tzinfo=timezone.utc)
    all_entries = base_entries + TIMELINE_ADDITIONAL_TAGS.get(issue_key, TIMELINE_ADDITIONAL_TAGS["default"])
    for idx, item in enumerate(all_entries):
        timeline_entries.append(
            {
                "event": str(item.get("event")),
                "summary": str(item.get("summary", "")),
                "event_order": idx + 1,
                "timestamp": _to_iso(start_time + timedelta(minutes=idx * 7)),
            }
        )

    detected_status = current_status or issue["status"]
    context = _decorate_context(command_behavior or issue_key, command, issue["title"])

    return {
        "issue_title": issue["title"],
        "current_status": detected_status,
        "timeline_entries": timeline_entries,
        "latest_finding": issue["latest_finding"],
        "recommended_next_step": issue["recommended_next_step"],
        "related_layers": list(issue.get("related_layers", [])),
        "confidence_score": 0.89,
        "read_only": True,
        "analysis_only": True,
        "command": command,
        "active_task": context["active_task"],
        "active_investigation_context": context,
        "related_endpoints": [
            "/debug/investigation-context-preview",
            "/debug/fault-report-intelligence-preview",
            "/debug/root-flow-audit",
            "/debug/self-check-preview",
            "/debug/credit-saver-preview",
        ],
        "real_action_performed": False,
        "real_file_write_performed": False,
        "real_memory_write_performed": False,
        "real_db_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_note": "Timeline output is read-only diagnostic only; no ARM/session replay.",
    }
