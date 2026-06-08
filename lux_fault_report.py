from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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


def fault_report_registry() -> Dict[str, Any]:
    return {
        "layer": "24",
        "status": "registry_ready",
        "sections": {
            "open_issues": OPEN_ISSUES,
            "deferred_issues": DEFERRED_ISSUES,
            "resolved_issues": RESOLVED_ISSUES,
            "issue_archive": ARCHIVE,
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

    filtered_open = [item for item in OPEN_ISSUES if _matches(item)]
    filtered_deferred = [item for item in DEFERRED_ISSUES if _matches(item)]
    filtered_resolved = [item for item in RESOLVED_ISSUES if _matches(item)]

    if not any([filtered_open, filtered_deferred, filtered_resolved]):
        filtered_open = OPEN_ISSUES[:1]
        filtered_deferred = DEFERRED_ISSUES[:1]
        filtered_resolved = RESOLVED_ISSUES[:1]
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
