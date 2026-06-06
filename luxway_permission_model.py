"""Read-only Android / iOS permission model preview for Luxway."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


SAFETY_NOTE = (
    "Read-only Luxway permission preview only. No Android/iOS permission request, phone access, "
    "data read, data write, send, delete, call, DB write, memory write, or file write is performed."
)


def _permission(
    permission_id: str,
    display_name: str,
    platform_support: Dict[str, str],
    required_for_capabilities: List[str],
    confirmation_required_for_write: bool,
) -> Dict[str, Any]:
    return {
        "id": permission_id,
        "display_name": display_name,
        "platform_support": platform_support,
        "required_for_capabilities": required_for_capabilities,
        "permission_required": True,
        "confirmation_required_for_write": confirmation_required_for_write,
        "real_permission_requested": False,
        "real_access_enabled": False,
        "read_only": True,
        "safety_note": SAFETY_NOTE,
    }


PERMISSION_GROUPS = [
    _permission("notifications", "Notifications", {"android": "broad_future", "ios": "limited_future", "unknown": "unknown"}, ["notification_priority_preview"], False),
    _permission("contacts", "Contacts", {"android": "broad_future", "ios": "limited_future", "unknown": "unknown"}, ["call_or_message_draft_preview"], True),
    _permission("messages", "Messages", {"android": "limited_future", "ios": "very_limited_future", "unknown": "unknown"}, ["message_summary_preview", "call_or_message_draft_preview"], True),
    _permission("mail", "Mail", {"android": "account_permission_future", "ios": "account_permission_future", "unknown": "unknown"}, ["mail_summary_preview"], True),
    _permission("calendar", "Calendar", {"android": "available_future", "ios": "available_future", "unknown": "unknown"}, ["calendar_summary_preview"], False),
    _permission("storage", "Storage", {"android": "scoped_storage_future", "ios": "limited_files_future", "unknown": "unknown"}, ["storage_preview", "cleanup_suggestions_preview"], True),
    _permission("app_usage", "App Usage", {"android": "usage_access_future", "ios": "restricted_future", "unknown": "unknown"}, ["app_usage_preview"], False),
    _permission("phone_calls", "Phone Calls", {"android": "restricted_future", "ios": "very_limited_future", "unknown": "unknown"}, ["call_or_message_draft_preview"], True),
    _permission("device_settings", "Device Settings", {"android": "restricted_future", "ios": "very_limited_future", "unknown": "unknown"}, ["device_safety_boundary"], True),
    _permission("files", "Files", {"android": "scoped_files_future", "ios": "document_picker_future", "unknown": "unknown"}, ["file_finder_preview"], True),
    _permission("photos", "Photos", {"android": "photo_picker_future", "ios": "photo_picker_future", "unknown": "unknown"}, ["file_finder_preview"], True),
    _permission("reminders", "Reminders", {"android": "app_specific_future", "ios": "available_future", "unknown": "unknown"}, ["calendar_summary_preview"], False),
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


def luxway_permission_model() -> Dict[str, Any]:
    return {
        "platforms": ["android", "ios", "unknown"],
        "permission_groups": [dict(group) for group in PERMISSION_GROUPS],
        "real_permission_requested": False,
        "real_access_enabled": False,
        "action_performed": False,
        "data_read": False,
        "data_written": False,
        "read_only": True,
        "safety_note": SAFETY_NOTE,
    }


def _permission_by_id(permission_id: str) -> Dict[str, Any]:
    for group in PERMISSION_GROUPS:
        if group["id"] == permission_id:
            return group
    return PERMISSION_GROUPS[0]


def _detect_platform(command: str, platform: str) -> str:
    if platform in {"android", "ios", "unknown"}:
        return platform
    normalized = _normalize_text(command)
    if "android" in normalized:
        return "android"
    if "ios" in normalized or "iphone" in normalized:
        return "ios"
    return "unknown"


def _detect_permissions(command: str) -> List[str]:
    normalized = _normalize_text(command)
    detected: List[str] = []
    rules = [
        ("notifications", ["bildirim", "notification", "onceliklendir"]),
        ("contacts", ["kisi", "kisiler", "rehber", "ali'ye", "aliye"]),
        ("messages", ["mesaj", "sms", "whatsapp"]),
        ("mail", ["mail", "e-posta", "eposta"]),
        ("calendar", ["takvim", "randevu", "toplanti"]),
        ("storage", ["depolama", "storage", "yer kaplayan", "temizle"]),
        ("files", ["dosya", "pdf", "temizle"]),
        ("app_usage", ["uygulama", "app", "tara", "kullanmadigim"]),
        ("phone_calls", ["ara", "arama", "telefon et"]),
        ("device_settings", ["ayar", "ayarları", "ayarlari", "degistir"]),
        ("photos", ["foto", "fotograf", "photos"]),
        ("reminders", ["hatirlatici", "reminder"]),
    ]
    for permission_id, keywords in rules:
        if any(keyword in normalized for keyword in keywords) and permission_id not in detected:
            detected.append(permission_id)
    if not detected:
        detected = ["notifications"] if "bildirim" in normalized else ["app_usage"]
    return detected


def _platform_limitations(platform: str) -> List[str]:
    if platform == "android":
        return [
            "Android may support broader future capabilities, but real_access_enabled is false here.",
            "Usage/storage access would require explicit permission in a real integration.",
        ]
    if platform == "ios":
        return [
            "iOS permissions may be more restricted by platform APIs.",
            "Calendar/photos/files may require picker or app-specific permission in a real integration.",
        ]
    return ["Platform is unknown; all permissions are preview metadata only."]


def preview_luxway_permission(command: str, platform: str = "unknown") -> Dict[str, Any]:
    raw_command = command or ""
    detected_platform = _detect_platform(raw_command, platform)
    permission_ids = _detect_permissions(raw_command)
    required_permissions = [_permission_by_id(permission_id) for permission_id in permission_ids]
    requires_confirmation = any(item["confirmation_required_for_write"] for item in required_permissions)
    normalized = _normalize_text(raw_command)
    if any(keyword in normalized for keyword in ["gonder", "yaz", "temizle", "degistir", "sil", "ara"]):
        requires_confirmation = True
    return {
        "raw_command": raw_command,
        "platform": detected_platform,
        "detected_permission_groups": permission_ids,
        "platform_limitations": _platform_limitations(detected_platform),
        "required_permissions": required_permissions,
        "requires_permission": True,
        "requires_confirmation": requires_confirmation,
        "real_permission_requested": False,
        "real_access_enabled": False,
        "action_performed": False,
        "data_read": False,
        "data_written": False,
        "safe_preview_message": "Luxway can only preview platform permission requirements in this scaffold.",
        "blocked_reason": "No real Android/iOS permission request or device data access is performed.",
        "read_only": True,
        "safety_note": SAFETY_NOTE,
    }
