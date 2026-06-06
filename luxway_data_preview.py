"""Read-only Luxway app/storage/message/mail/calendar data preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from luxway_permission_model import preview_luxway_permission


SAFETY_NOTE = (
    "Read-only Luxway data preview only. No phone, app, storage, message, mail, "
    "calendar, notification, file, DB, memory, or file access is performed."
)

UNAVAILABLE_REAL_DATA_NOTE = (
    "No real device data is available in this scaffold. The response is a structural "
    "preview only and must not include real or invented app, mail, message, file, "
    "notification, or calendar item details."
)

DOMAINS = {
    "app_usage": {
        "required_permissions": ["app_usage"],
        "sections": ["app_usage_scope", "unused_apps_schema", "usage_pattern_schema", "safety_boundaries"],
    },
    "storage": {
        "required_permissions": ["storage", "files"],
        "sections": ["storage_scope", "storage_pressure_schema", "cleanup_suggestion_schema", "safety_boundaries"],
    },
    "messages": {
        "required_permissions": ["messages", "contacts"],
        "sections": ["message_scope", "message_summary_schema", "draft_boundary", "safety_boundaries"],
    },
    "mail": {
        "required_permissions": ["mail"],
        "sections": ["mail_scope", "mail_summary_schema", "reply_or_send_boundary", "safety_boundaries"],
    },
    "calendar": {
        "required_permissions": ["calendar"],
        "sections": ["calendar_scope", "calendar_summary_schema", "density_preview_schema", "safety_boundaries"],
    },
    "notifications": {
        "required_permissions": ["notifications"],
        "sections": ["notification_scope", "priority_schema", "noise_reduction_schema", "safety_boundaries"],
    },
    "files": {
        "required_permissions": ["files", "storage"],
        "sections": ["file_scope", "file_finder_schema", "delete_boundary", "safety_boundaries"],
    },
}


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


def _detect_platform(command: str, platform: str) -> str:
    if platform in {"android", "ios", "unknown"}:
        return platform
    normalized = _normalize_text(command)
    if "android" in normalized:
        return "android"
    if "ios" in normalized or "iphone" in normalized:
        return "ios"
    return "unknown"


def _detect_domain(command: str, requested_domain: str = "") -> str:
    if requested_domain in DOMAINS:
        return requested_domain
    normalized = _normalize_text(command)
    rules = [
        ("mail", ["mail", "e-posta", "eposta"]),
        ("messages", ["mesaj", "sms", "whatsapp"]),
        ("calendar", ["takvim", "randevu", "toplanti"]),
        ("notifications", ["bildirim", "notification", "onceliklendir"]),
        ("storage", ["depolama", "storage", "hafiza", "yer kaplayan", "temizle"]),
        ("files", ["dosya", "pdf", "indir", "export"]),
        ("app_usage", ["uygulama", "app", "kullanmadigim", "gereksiz", "tara"]),
    ]
    for domain, keywords in rules:
        if any(keyword in normalized for keyword in keywords):
            return domain
    return "app_usage"


def _requires_confirmation(command: str, domain: str) -> bool:
    normalized = _normalize_text(command)
    if domain in {"storage", "files"} and "temizle" in normalized:
        return True
    risky_keywords = [
        "sil",
        "temizle",
        "gonder",
        "yolla",
        "cevapla",
        "ara",
        "mail at",
        "mesaj at",
        "ayar degistir",
        "degistir",
    ]
    padded = f" {normalized} "
    return any(f" {keyword} " in padded if keyword in {"ara", "sil"} else keyword in normalized for keyword in risky_keywords)


def _preview_section(section_id: str, domain: str) -> Dict[str, Any]:
    return {
        "id": section_id,
        "domain": domain,
        "real_data_status": "unavailable",
        "simulated_values_used": False,
        "contains_real_items": False,
        "note": "Schema preview only; no real or invented item names are included.",
    }


def _required_permissions(command: str, domain: str, platform: str) -> List[str]:
    permissions = list(DOMAINS[domain]["required_permissions"])
    permission_preview = preview_luxway_permission(command or domain, platform)
    for permission_id in permission_preview.get("detected_permission_groups", []):
        if permission_id in {"notifications", "contacts", "messages", "mail", "calendar", "storage", "app_usage", "files"}:
            if permission_id not in permissions:
                permissions.append(permission_id)
    return permissions


def preview_luxway_data(command: str, domain: str = "", platform: str = "unknown") -> Dict[str, Any]:
    raw_command = command or ""
    detected_platform = _detect_platform(raw_command, platform)
    detected_domain = _detect_domain(raw_command, domain)
    required_permissions = _required_permissions(raw_command, detected_domain, detected_platform)
    preview_sections = [_preview_section(section_id, detected_domain) for section_id in DOMAINS[detected_domain]["sections"]]
    requires_confirmation = _requires_confirmation(raw_command, detected_domain)
    return {
        "raw_command": raw_command,
        "platform": detected_platform,
        "detected_domain": detected_domain,
        "required_permissions": required_permissions,
        "preview_sections": preview_sections,
        "unavailable_real_data_note": UNAVAILABLE_REAL_DATA_NOTE,
        "safe_preview_message": (
            "Luxway can only preview the domain, permissions, and safe schema in this layer. "
            "No real or invented device data is shown."
        ),
        "requires_permission": True,
        "requires_confirmation": requires_confirmation,
        "real_access_enabled": False,
        "data_read": False,
        "data_written": False,
        "action_performed": False,
        "read_only": True,
        "safety_note": SAFETY_NOTE,
    }
