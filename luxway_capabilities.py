"""Read-only Luxway phone assistant capability preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


PRIVACY_NOTE = (
    "Read-only Luxway capability preview only. No phone, app, storage, message, mail, "
    "calendar, notification, file, call, send, delete, DB, memory, or file access is performed."
)


def _capability(
    capability_id: str,
    display_name: str,
    category: str,
    description: str,
    requires_permission: bool,
    requires_confirmation: bool,
) -> Dict[str, Any]:
    return {
        "id": capability_id,
        "display_name": display_name,
        "category": category,
        "description": description,
        "requires_permission": requires_permission,
        "requires_confirmation": requires_confirmation,
        "real_access_enabled": False,
        "read_only": True,
        "safety_note": PRIVACY_NOTE,
    }


LUXWAY_CAPABILITIES = [
    _capability("phone_overview", "Phone Overview", "device", "Preview a future phone overview capability.", True, False),
    _capability("app_usage_preview", "App Usage Preview", "apps", "Preview unused or high-usage app insights.", True, False),
    _capability("storage_preview", "Storage Preview", "storage", "Preview storage usage insight requests.", True, False),
    _capability("notification_priority_preview", "Notification Priority Preview", "notifications", "Preview notification priority sorting.", True, False),
    _capability("message_summary_preview", "Message Summary Preview", "messages", "Preview message summary requests.", True, False),
    _capability("mail_summary_preview", "Mail Summary Preview", "mail", "Preview mail summary requests.", True, False),
    _capability("calendar_summary_preview", "Calendar Summary Preview", "calendar", "Preview calendar overview requests.", True, False),
    _capability("file_finder_preview", "File Finder Preview", "files", "Preview file finder requests.", True, False),
    _capability("weekly_phone_report_preview", "Weekly Phone Report Preview", "reports", "Preview weekly phone report planning.", True, False),
    _capability("cleanup_suggestions_preview", "Cleanup Suggestions Preview", "cleanup", "Preview cleanup suggestions without deleting anything.", True, True),
    _capability("call_or_message_draft_preview", "Call Or Message Draft Preview", "drafts", "Preview call/message/mail draft planning without sending.", True, True),
    _capability("device_safety_boundary", "Device Safety Boundary", "safety", "Preview safety boundary for destructive or device-changing actions.", True, True),
]


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return (
        text.lower()
        .replace("\u0131", "i")
        .replace("\u0130", "i")
        .replace("\u015f", "s")
        .replace("\u011f", "g")
        .replace("\u00fc", "u")
        .replace("\u00f6", "o")
        .replace("\u00e7", "c")
    )


def luxway_capability_registry() -> Dict[str, Any]:
    return {
        "capabilities": [dict(capability) for capability in LUXWAY_CAPABILITIES],
        "platform_notes": {
            "android": "Android may support broader future integrations, but real_access_enabled remains false in this scaffold.",
            "ios": "iOS may be more restricted, and real_access_enabled remains false in this scaffold.",
            "unknown": "Platform is metadata only.",
        },
        "real_access_enabled": False,
        "action_performed": False,
        "data_read": False,
        "data_written": False,
        "read_only": True,
        "privacy_note": PRIVACY_NOTE,
    }


def _capability_by_id(capability_id: str) -> Dict[str, Any]:
    for capability in LUXWAY_CAPABILITIES:
        if capability["id"] == capability_id:
            return capability
    return LUXWAY_CAPABILITIES[0]


def _has_keyword(normalized: str, keyword: str) -> bool:
    if keyword in {"ara", "sil"}:
        return f" {keyword} " in f" {normalized} "
    return keyword in normalized


def _detect_capabilities(command: str) -> List[str]:
    normalized = _normalize_text(command)
    candidates: List[str] = []
    keyword_rules = [
        ("call_or_message_draft_preview", ["mesaj taslagi", "mesaj yaz", "mail yaz", "ara", "arama", "gonder", "yolla"]),
        ("mail_summary_preview", ["mail", "e-posta", "eposta"]),
        ("calendar_summary_preview", ["takvim", "randevu", "toplanti"]),
        ("notification_priority_preview", ["bildirim", "onceliklendir", "notification"]),
        ("weekly_phone_report_preview", ["haftalik telefon raporu", "telefon raporu", "haftalik rapor"]),
        ("cleanup_suggestions_preview", ["gereksiz", "kullanmadigim", "temizle", "cleanup", "uygulamalari oner"]),
        ("app_usage_preview", ["uygulama", "app", "kullanmadigim"]),
        ("storage_preview", ["yer kaplayan", "depolama", "storage", "hafiza"]),
        ("file_finder_preview", ["dosya", "bul", "pdf"]),
        ("phone_overview", ["telefonumu tara", "telefonu tara", "telefon", "tara"]),
    ]
    for capability_id, keywords in keyword_rules:
        if any(_has_keyword(normalized, keyword) for keyword in keywords) and capability_id not in candidates:
            candidates.append(capability_id)
    destructive_keywords = ["sil", "gonder", "ara", "mail gonder", "mesaj at", "cihaz ayari", "dosya sil"]
    if any(_has_keyword(normalized, keyword) for keyword in destructive_keywords) and "device_safety_boundary" not in candidates:
        candidates.append("device_safety_boundary")
    if not candidates:
        candidates = ["phone_overview"]
    return candidates


def _platform_note(platform: str) -> str:
    notes = luxway_capability_registry()["platform_notes"]
    return notes.get(platform, notes["unknown"])


def preview_luxway_command(command: str, platform: str = "unknown", context: str = "") -> Dict[str, Any]:
    raw_command = command or ""
    normalized_platform = platform if platform in {"android", "ios", "unknown"} else "unknown"
    candidate_ids = _detect_capabilities(" ".join([raw_command, context or ""]))
    candidates = [_capability_by_id(capability_id) for capability_id in candidate_ids]
    primary = candidates[0]
    requires_permission = any(bool(item["requires_permission"]) for item in candidates)
    requires_confirmation = any(bool(item["requires_confirmation"]) for item in candidates)
    blocked_reason = (
        "Real Luxway phone/app/data access is not implemented in this scaffold; preview only."
        if requires_permission
        else "No real action is available in read-only scaffold."
    )
    return {
        "raw_command": raw_command,
        "platform": normalized_platform,
        "platform_note": _platform_note(normalized_platform),
        "context": context or "",
        "detected_capability": primary["id"],
        "capability_candidates": candidates,
        "requires_permission": requires_permission,
        "requires_confirmation": requires_confirmation,
        "real_access_enabled": False,
        "action_performed": False,
        "data_read": False,
        "data_written": False,
        "safe_preview_message": "Luxway can only preview the intended capability and safety boundary in this layer.",
        "blocked_reason": blocked_reason,
        "read_only": True,
        "privacy_note": PRIVACY_NOTE,
    }


def luxway_status_snapshot() -> Dict[str, Any]:
    return {
        "layer": "18.1",
        "name": "Luxway capability scaffold",
        "status": "scaffold_ready",
        "read_only": True,
        "real_phone_access_enabled": False,
        "real_app_access_enabled": False,
        "real_storage_access_enabled": False,
        "real_message_access_enabled": False,
        "real_mail_access_enabled": False,
        "real_calendar_access_enabled": False,
        "real_notification_access_enabled": False,
        "real_call_or_send_enabled": False,
        "file_write_enabled": False,
        "db_write_enabled": False,
        "memory_write_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": ["/luxway/capabilities", "/luxway/preview-command", "/debug/luxway-status"],
        "backlog": ["stop/durdur final block leak"],
        "privacy_note": PRIVACY_NOTE,
    }
