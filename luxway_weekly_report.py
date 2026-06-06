"""Read-only weekly phone report schema preview for Luxway."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from luxway_permission_model import preview_luxway_permission


SAFETY_NOTE = (
    "Read-only weekly phone report preview only. No phone, app, storage, message, mail, "
    "calendar, notification, DB, memory, file, or real device data access is performed."
)

UNAVAILABLE_REAL_DATA_NOTE = (
    "No real phone data is available in this scaffold. All sections are structural previews; "
    "real weekly reporting would require explicit platform permissions."
)

REPORT_SECTION_IDS = [
    "week_summary",
    "screen_time_preview",
    "app_usage_preview",
    "storage_pressure_preview",
    "notification_noise_preview",
    "message_mail_load_preview",
    "calendar_density_preview",
    "unused_apps_preview",
    "cleanup_suggestions_preview",
    "focus_recommendations_preview",
    "safety_boundaries",
]

SECTION_PERMISSION_MAP = {
    "week_summary": ["app_usage", "notifications", "calendar"],
    "screen_time_preview": ["app_usage"],
    "app_usage_preview": ["app_usage"],
    "storage_pressure_preview": ["storage", "files"],
    "notification_noise_preview": ["notifications"],
    "message_mail_load_preview": ["messages", "mail"],
    "calendar_density_preview": ["calendar"],
    "unused_apps_preview": ["app_usage"],
    "cleanup_suggestions_preview": ["storage", "files", "app_usage"],
    "focus_recommendations_preview": ["notifications", "app_usage", "calendar"],
    "safety_boundaries": [],
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


def _section(section_id: str, title: str, description: str) -> Dict[str, Any]:
    return {
        "id": section_id,
        "title": title,
        "description": description,
        "required_permissions": SECTION_PERMISSION_MAP.get(section_id, []),
        "real_data_status": "unavailable",
        "simulated_values_used": False,
        "read_only": True,
    }


def _report_sections() -> List[Dict[str, Any]]:
    return [
        _section("week_summary", "Week Summary", "Preview the future weekly phone report summary structure."),
        _section("screen_time_preview", "Screen Time Preview", "Placeholder for future screen time signals without numbers."),
        _section("app_usage_preview", "App Usage Preview", "Placeholder for future app usage patterns without app names."),
        _section("storage_pressure_preview", "Storage Pressure Preview", "Placeholder for future storage pressure signals."),
        _section("notification_noise_preview", "Notification Noise Preview", "Placeholder for future notification load signals."),
        _section("message_mail_load_preview", "Message And Mail Load Preview", "Placeholder for future message/mail load signals."),
        _section("calendar_density_preview", "Calendar Density Preview", "Placeholder for future calendar density signals."),
        _section("unused_apps_preview", "Unused Apps Preview", "Placeholder for future unused app suggestions without app names."),
        _section("cleanup_suggestions_preview", "Cleanup Suggestions Preview", "Suggestion-only cleanup structure; no delete action."),
        _section("focus_recommendations_preview", "Focus Recommendations Preview", "Placeholder for future focus recommendation themes."),
        _section("safety_boundaries", "Safety Boundaries", "Privacy and permission boundaries for weekly phone reports."),
    ]


def luxway_weekly_report_schema() -> Dict[str, Any]:
    return {
        "report_sections": _report_sections(),
        "requires_permission": True,
        "real_access_enabled": False,
        "data_read": False,
        "data_written": False,
        "action_performed": False,
        "read_only": True,
        "unavailable_real_data_note": UNAVAILABLE_REAL_DATA_NOTE,
        "safety_note": SAFETY_NOTE,
    }


def _detect_focus(report_focus: str, context: str) -> str:
    normalized = _normalize_text(" ".join([report_focus or "", context or ""]))
    if any(keyword in normalized for keyword in ["bildirim", "notification", "gurultu", "yuk"]):
        return "notification_noise"
    if any(keyword in normalized for keyword in ["kullanmadigim", "gereksiz", "uygulama", "app"]):
        return "unused_apps"
    if any(keyword in normalized for keyword in ["depolama", "storage", "yer kaplayan", "hafiza"]):
        return "storage_pressure"
    if any(keyword in normalized for keyword in ["odak", "focus", "dikkat"]):
        return "focus_recommendations"
    return "weekly_overview"


def _selected_sections(focus: str) -> List[Dict[str, Any]]:
    sections = _report_sections()
    if focus == "notification_noise":
        wanted = {"week_summary", "notification_noise_preview", "focus_recommendations_preview", "safety_boundaries"}
    elif focus == "unused_apps":
        wanted = {"week_summary", "app_usage_preview", "unused_apps_preview", "cleanup_suggestions_preview", "safety_boundaries"}
    elif focus == "storage_pressure":
        wanted = {"week_summary", "storage_pressure_preview", "cleanup_suggestions_preview", "safety_boundaries"}
    elif focus == "focus_recommendations":
        wanted = {"week_summary", "notification_noise_preview", "calendar_density_preview", "focus_recommendations_preview", "safety_boundaries"}
    else:
        wanted = set(REPORT_SECTION_IDS)
    return [section for section in sections if section["id"] in wanted]


def _required_permissions(sections: List[Dict[str, Any]], platform: str) -> List[str]:
    permission_ids: List[str] = []
    for section in sections:
        for permission_id in section.get("required_permissions", []):
            if permission_id not in permission_ids:
                permission_ids.append(permission_id)
    command = " ".join(permission_ids) or "haftalik telefon raporu"
    permission_preview = preview_luxway_permission(command, platform)
    detected = permission_preview.get("detected_permission_groups", [])
    for permission_id in detected:
        if permission_id not in permission_ids:
            permission_ids.append(permission_id)
    return permission_ids


def preview_luxway_weekly_report(
    platform: str = "unknown",
    report_focus: str = "",
    context: str = "",
) -> Dict[str, Any]:
    normalized_platform = platform if platform in {"android", "ios", "unknown"} else "unknown"
    detected_focus = _detect_focus(report_focus, context)
    sections = _selected_sections(detected_focus)
    required_permissions = _required_permissions(sections, normalized_platform)
    return {
        "platform": normalized_platform,
        "report_focus": report_focus or detected_focus,
        "detected_focus": detected_focus,
        "report_sections": sections,
        "required_permissions": required_permissions,
        "missing_permissions": required_permissions,
        "safe_preview_report": {
            "summary": "Weekly phone report structure preview only; no real metrics, app names, notification details, messages, mail, calendar items, or storage values are available.",
            "section_notes": [
                {
                    "section_id": section["id"],
                    "preview_state": "unavailable_real_data",
                    "note": "This section will stay empty until explicit user permission and real integration exist.",
                }
                for section in sections
            ],
            "cleanup_suggestions": "Suggestions only. No app, file, or device cleanup action is performed.",
            "permission_message": "A real report would require explicit platform permissions before reading device data.",
        },
        "unavailable_real_data_note": UNAVAILABLE_REAL_DATA_NOTE,
        "requires_permission": True,
        "real_access_enabled": False,
        "data_read": False,
        "data_written": False,
        "action_performed": False,
        "read_only": True,
        "safety_note": SAFETY_NOTE,
    }
