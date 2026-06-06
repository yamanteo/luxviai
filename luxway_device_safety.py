"""Read-only Luxway device safety boundary preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict


SAFETY_NOTE = (
    "Read-only Luxway device safety preview only. No phone, app, file, storage, "
    "message, mail, call, calendar, device setting, DB, memory, or file write action is performed."
)

RISK_CATEGORIES = {
    "delete_file",
    "delete_app",
    "send_message",
    "send_mail",
    "make_call",
    "change_device_setting",
    "cleanup_storage",
    "modify_calendar",
    "access_private_data",
    "unknown_risky_action",
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


def _has_word(normalized: str, word: str) -> bool:
    return f" {word} " in f" {normalized} "


def _detect_risk_category(command: str) -> str:
    normalized = _normalize_text(command)
    has_delete = _has_word(normalized, "sil") or "silmek" in normalized
    has_send = "gonder" in normalized or "yolla" in normalized or "mesaj at" in normalized or "mail at" in normalized
    if has_delete and any(keyword in normalized for keyword in ["uygulama", "app"]):
        return "delete_app"
    if has_delete and any(keyword in normalized for keyword in ["dosya", "pdf", "file"]):
        return "delete_file"
    if any(keyword in normalized for keyword in ["depolama", "storage", "hafiza", "yer kaplayan", "temizle"]):
        return "cleanup_storage"
    if has_send and any(keyword in normalized for keyword in ["mesaj", "sms", "whatsapp"]):
        return "send_message"
    if has_send and any(keyword in normalized for keyword in ["mail", "e-posta", "eposta"]):
        return "send_mail"
    if _has_word(normalized, "ara") or "arama yap" in normalized or "telefon et" in normalized:
        return "make_call"
    if any(keyword in normalized for keyword in ["ayar", "ayarlari", "degistir", "cihaz ayari"]):
        return "change_device_setting"
    if any(keyword in normalized for keyword in ["takvim", "randevu"]) and any(keyword in normalized for keyword in ["ekle", "degistir", "sil"]):
        return "modify_calendar"
    if any(keyword in normalized for keyword in ["oku", "ozetle", "goster", "tara"]) and any(
        keyword in normalized for keyword in ["mail", "mesaj", "takvim", "dosya", "telefon"]
    ):
        return "access_private_data"
    return "unknown_risky_action"


def _risk_level(category: str) -> str:
    if category in {"delete_file", "delete_app", "send_message", "send_mail", "make_call", "change_device_setting"}:
        return "high"
    if category in {"cleanup_storage", "modify_calendar", "access_private_data"}:
        return "medium"
    return "medium"


def _safe_alternative(category: str) -> str:
    if category in {"send_message", "send_mail"}:
        return "Once taslak hazirlayabilirim; kullanici onayi olmadan gonderim yapmam."
    if category in {"delete_file", "delete_app", "cleanup_storage"}:
        return "Once silinecekleri veya temizlenecekleri yalnizca listeleyebilirim."
    if category == "make_call":
        return "Once arama niyeti ve kisi kontrol listesi hazirlayabilirim."
    if category == "change_device_setting":
        return "Once ayar degisikligi icin kontrol listesi cikarabilirim."
    if category == "modify_calendar":
        return "Once takvim degisikligi taslagi hazirlayabilirim."
    if category == "access_private_data":
        return "Once gerekli izinleri ve okunacak veri alanlarini onizleyebilirim."
    return "Once guvenli kontrol listesi cikarabilirim."


def preview_luxway_device_safety(command: str, platform: str = "unknown") -> Dict[str, Any]:
    raw_command = command or ""
    detected_platform = _detect_platform(raw_command, platform)
    category = _detect_risk_category(raw_command)
    return {
        "raw_command": raw_command,
        "platform": detected_platform,
        "detected_risk_category": category,
        "risk_level": _risk_level(category),
        "requires_permission": True,
        "requires_confirmation": True,
        "confirmation_phrase_required": "Onayliyorum",
        "blocked_by_default": True,
        "real_access_enabled": False,
        "action_performed": False,
        "data_read": False,
        "data_written": False,
        "safe_alternative": _safe_alternative(category),
        "blocked_reason": "Riskli Luxway islemleri scaffold asamasinda varsayilan olarak engellenir.",
        "read_only": True,
        "safety_note": SAFETY_NOTE,
        "available_risk_categories": sorted(RISK_CATEGORIES),
    }
