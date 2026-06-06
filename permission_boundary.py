"""Read-only permission and action boundary preview scaffold."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any, Dict, List, Sequence

from mode_registry import preview_mode_command


ACTION_TYPES = {
    "answer_only",
    "mode_preview",
    "draft_only",
    "read_private_data",
    "write_or_send_action",
    "device_or_phone_action",
    "export_or_file_action",
    "sensitive_private_mode",
    "unknown",
}

DATA_SENSITIVITY = {"none", "low", "medium", "high", "private_sensitive"}

_KEYWORD_FAMILIES = {
    "read_verbs": ["oku", "kontrol et", "ozetle", "incele", "tara", "bak"],
    "write_send_verbs": ["gonder", "yolla", "cevapla", "mail at", "mesaj at", "ilet"],
    "delete_modify_verbs": ["sil", "temizle", "kaldir", "degistir", "ayarla"],
    "export_verbs": ["indir", "pdf yap", "pdf olarak", "disa aktar", "export et", "kaydet"],
    "draft_verbs": ["hazirla", "taslak", "duzenle", "yaz"],
    "email_domain": ["mail", "e-posta", "eposta", "email"],
    "message_domain": ["mesaj", "whatsapp", "sms"],
    "calendar_domain": ["takvim", "randevu", "toplanti"],
    "phone_domain": ["telefon", "uygulama", "depolama", "cihaz", "app"],
    "file_domain": ["dosya", "pdf", "rapor", "export", "indir"],
    "sensitive_mode": ["luxeph", "ozel oda", "gizli mod", "mahrem", "private"],
    "safe_focus": ["tek adim", "bir adim", "one step"],
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


def _matches(text: str, values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        normalized = _normalize_text(value)
        if normalized and normalized in text:
            out.append(value)
    return out


def _matched_families(normalized: str) -> Dict[str, List[str]]:
    return {
        family: matches
        for family, values in _KEYWORD_FAMILIES.items()
        if (matches := _matches(normalized, values))
    }


def _has_family(families: Dict[str, List[str]], *names: str) -> bool:
    return any(name in families for name in names)


def _action_type(families: Dict[str, List[str]], mode_preview: Dict[str, Any]) -> str:
    mode_ids = {item.get("mode", {}).get("id") for item in mode_preview.get("matched_modes", [])}

    if _has_family(families, "sensitive_mode") or "luxeph" in mode_ids:
        return "sensitive_private_mode"
    if _has_family(families, "delete_modify_verbs") and _has_family(families, "phone_domain"):
        return "device_or_phone_action"
    if _has_family(families, "phone_domain") and _has_family(families, "read_verbs"):
        return "device_or_phone_action"
    if _has_family(families, "write_send_verbs") and _has_family(families, "email_domain", "message_domain"):
        return "write_or_send_action"
    if _has_family(families, "export_verbs") and _has_family(families, "file_domain"):
        return "export_or_file_action"
    if _has_family(families, "read_verbs") and _has_family(families, "email_domain", "message_domain", "calendar_domain"):
        return "read_private_data"
    if _has_family(families, "draft_verbs") and ("cv_builder" in mode_ids or _has_family(families, "file_domain")):
        return "draft_only"
    if mode_preview.get("matched_modes"):
        return "mode_preview"
    if _has_family(families, "safe_focus"):
        return "answer_only"
    return "unknown"


def _sensitivity(action_type: str, families: Dict[str, List[str]]) -> str:
    if action_type == "sensitive_private_mode":
        return "private_sensitive"
    if action_type in {"read_private_data", "write_or_send_action", "device_or_phone_action"}:
        return "high"
    if action_type == "export_or_file_action":
        return "medium"
    if action_type in {"draft_only", "mode_preview"}:
        return "low"
    if _has_family(families, "email_domain", "message_domain", "calendar_domain", "phone_domain"):
        return "medium"
    return "none"


def _requires_permission(action_type: str) -> bool:
    return action_type in {
        "read_private_data",
        "write_or_send_action",
        "device_or_phone_action",
        "export_or_file_action",
        "sensitive_private_mode",
    }


def _requires_confirmation(action_type: str) -> bool:
    return action_type in {
        "write_or_send_action",
        "device_or_phone_action",
        "export_or_file_action",
        "sensitive_private_mode",
    }


def _allowed_in_scaffold(action_type: str) -> bool:
    return action_type in {"answer_only", "mode_preview", "draft_only", "unknown"}


def _blocked_reason(action_type: str, allowed: bool) -> str:
    if allowed:
        return ""
    reasons = {
        "read_private_data": "Private data access is blocked in scaffold preview.",
        "write_or_send_action": "Sending, replying, or writing external messages is blocked in scaffold preview.",
        "device_or_phone_action": "Device, phone, app, storage, and delete actions are blocked in scaffold preview.",
        "export_or_file_action": "Export, download, and file write actions are blocked in scaffold preview.",
        "sensitive_private_mode": "Sensitive/private mode activation is preview-only and requires explicit confirmation later.",
    }
    return reasons.get(action_type, "Action is blocked in scaffold preview.")


def _safe_preview_message(action_type: str, allowed: bool) -> str:
    if allowed:
        return "This command can be shown as a read-only preview; no real action will run."
    return "I can preview the boundary and required permission, but cannot execute this action in scaffold mode."


def _next_step_hint(action_type: str, requires_confirmation: bool) -> str:
    if requires_confirmation:
        return "Ask for explicit user confirmation before any future execution path."
    if action_type == "draft_only":
        return "Offer a draft/outline only; do not export or write files."
    if action_type == "mode_preview":
        return "Show the matched mode preview without changing active mode."
    if action_type == "answer_only":
        return "Answer normally or provide a single safe next step."
    return "Ask a clarifying question or keep the response as a safe preview."


def preview_permission_boundary(command: str) -> Dict[str, Any]:
    normalized = _normalize_text(command)
    mode_preview = preview_mode_command(command)
    families = _matched_families(normalized)
    action_type = _action_type(families, mode_preview)
    data_sensitivity = _sensitivity(action_type, families)
    requires_permission = _requires_permission(action_type)
    requires_confirmation = _requires_confirmation(action_type)
    allowed = _allowed_in_scaffold(action_type)

    return {
        "boundary_id": str(uuid.uuid4()),
        "command": command,
        "detected_mode_candidates": mode_preview.get("matched_modes", []),
        "action_type": action_type if action_type in ACTION_TYPES else "unknown",
        "requires_permission": requires_permission,
        "requires_confirmation": requires_confirmation,
        "data_sensitivity": data_sensitivity if data_sensitivity in DATA_SENSITIVITY else "none",
        "allowed_in_scaffold": allowed,
        "blocked_reason": _blocked_reason(action_type, allowed),
        "safe_preview_message": _safe_preview_message(action_type, allowed),
        "next_step_hint": _next_step_hint(action_type, requires_confirmation),
        "matched_keyword_families": families,
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "can_execute_now": False,
    }
