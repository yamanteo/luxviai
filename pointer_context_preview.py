from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


DETECTED_TYPES: List[Dict[str, Any]] = [
    {"id": "text_selection", "description": "Selected text or explicit quoted text.", "read_only": True},
    {"id": "paragraph", "description": "A paragraph-like selected block.", "read_only": True},
    {"id": "address", "description": "Address or route-related text.", "read_only": True},
    {"id": "date_time", "description": "Date or time context.", "read_only": True},
    {"id": "email_or_message", "description": "Email, chat, SMS, WhatsApp, or message context.", "read_only": True},
    {"id": "file_reference", "description": "A file name or file-like reference.", "read_only": True},
    {"id": "pdf_region", "description": "A referenced region inside a PDF.", "read_only": True},
    {"id": "table_region", "description": "A table, row, column, or spreadsheet-like region.", "read_only": True},
    {"id": "image_region", "description": "A visual image or screenshot region.", "read_only": True},
    {"id": "video_moment", "description": "A moment in a video or stream.", "read_only": True},
    {"id": "error_message", "description": "An error message or warning.", "read_only": True},
    {"id": "code_snippet", "description": "A code snippet or technical stack trace.", "read_only": True},
    {"id": "product", "description": "A product or shopping comparison target.", "read_only": True},
    {"id": "map_location", "description": "Map, location, or navigation context.", "read_only": True},
    {"id": "link_or_url", "description": "A link, URL, or web target.", "read_only": True},
    {"id": "unknown_context", "description": "Unclear context that needs a user-provided hint.", "read_only": True},
]


SUGGESTED_ACTIONS: List[Dict[str, Any]] = [
    {"id": "explain", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "summarize", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "rewrite", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "translate", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "extract_tasks", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "create_note", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "create_reply_draft", "risk_level": "medium", "requires_permission": True, "requires_confirmation": False},
    {"id": "create_email_draft", "risk_level": "medium", "requires_permission": True, "requires_confirmation": False},
    {"id": "build_report_section", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "clean_formatting", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "compare_options", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "troubleshoot", "risk_level": "low", "requires_permission": False, "requires_confirmation": False},
    {"id": "open_safely_preview", "risk_level": "medium", "requires_permission": True, "requires_confirmation": True},
    {"id": "send_ready_preview", "risk_level": "high", "requires_permission": True, "requires_confirmation": True},
    {"id": "export_ready_preview", "risk_level": "medium", "requires_permission": True, "requires_confirmation": True},
    {"id": "print_ready_preview", "risk_level": "medium", "requires_permission": True, "requires_confirmation": True},
    {"id": "calendar_ready_preview", "risk_level": "medium", "requires_permission": True, "requires_confirmation": True},
    {"id": "navigation_ready_preview", "risk_level": "medium", "requires_permission": True, "requires_confirmation": True},
]


TYPE_RULES = {
    "error_message": ["hata", "error", "warning", "uyari", "ne demek", "stack trace"],
    "table_region": ["tablo", "table", "satir", "sutun", "spreadsheet"],
    "pdf_region": ["pdf", "pdf alani", "rapor bolumu"],
    "video_moment": ["video", "bu ani", "bu anindan", "videonun", "stream"],
    "address": ["adres", "yol tarifi", "konum", "lokasyon"],
    "map_location": ["harita", "map", "rota", "navigasyon", "yol tarifi"],
    "email_or_message": ["mesaj", "mail", "e-posta", "whatsapp", "cevap taslagi"],
    "product": ["urun", "fiyat", "secenek", "karsilastir"],
    "link_or_url": ["http", "https", "link", "url"],
    "code_snippet": ["kod", "code", "fonksiyon", "traceback", "bug"],
    "file_reference": ["dosya", "file", ".docx", ".pdf", ".xlsx"],
    "date_time": ["tarih", "saat", "randevu", "takvim"],
    "image_region": ["gorsel", "resim", "screenshot", "ekran goruntusu"],
    "paragraph": ["paragraf", "metin", "bolum"],
    "text_selection": ["sunu acikla", "bunu acikla", "secilen", "secili"],
}


ACTION_RULES = {
    "explain": ["acikla", "ne demek", "anlat"],
    "summarize": ["ozetle", "toparla"],
    "rewrite": ["yeniden yaz", "duzenle", "rewrite"],
    "translate": ["cevir", "translate"],
    "extract_tasks": ["gorev cikar", "task", "yapilacak"],
    "create_note": ["not cikar", "not al", "not olustur"],
    "create_reply_draft": ["cevap taslagi", "cevap yaz", "yanit taslagi"],
    "create_email_draft": ["mail taslagi", "e-posta taslagi"],
    "build_report_section": ["rapor bolumu", "rapor", "bolum cikar"],
    "clean_formatting": ["temizle", "format", "basliklandir"],
    "compare_options": ["karsilastir", "seceneklerle", "compare"],
    "troubleshoot": ["hata", "troubleshoot", "debug", "ne demek"],
    "open_safely_preview": ["guvenli ac", "open safely", "link"],
    "send_ready_preview": ["gondermeye hazirla", "gonder", "send"],
    "export_ready_preview": ["pdf", "export", "disa aktar", "export etme"],
    "print_ready_preview": ["yazdirmaya hazirla", "yazdirma", "print"],
    "calendar_ready_preview": ["takvime", "randevu", "calendar"],
    "navigation_ready_preview": ["yol tarifi", "rota", "navigasyon"],
}


TYPE_DEFAULT_ACTIONS = {
    "error_message": ["troubleshoot", "explain"],
    "table_region": ["summarize", "extract_tasks"],
    "pdf_region": ["build_report_section", "summarize"],
    "video_moment": ["create_note", "summarize"],
    "address": ["navigation_ready_preview"],
    "map_location": ["navigation_ready_preview"],
    "email_or_message": ["create_reply_draft", "summarize"],
    "product": ["compare_options", "summarize"],
    "link_or_url": ["open_safely_preview", "summarize"],
    "code_snippet": ["troubleshoot", "explain"],
    "file_reference": ["summarize", "open_safely_preview"],
    "date_time": ["calendar_ready_preview", "summarize"],
    "image_region": ["explain", "summarize"],
    "paragraph": ["summarize", "rewrite"],
    "text_selection": ["explain", "summarize"],
    "unknown_context": ["explain"],
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ş": "s",
        "ö": "o",
        "ü": "u",
        "ç": "c",
        "İ": "i",
        "Ä±": "i",
        "ÄŸ": "g",
        "ÅŸ": "s",
        "Ã¶": "o",
        "Ã¼": "u",
        "Ã§": "c",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def _action_by_id(action_id: str) -> Dict[str, Any]:
    for action in SUGGESTED_ACTIONS:
        if action["id"] == action_id:
            return action
    return SUGGESTED_ACTIONS[0]


def _detect_type(command: str, selected_text: str = "", context_hint: str = "", surface_type: str = "") -> Dict[str, Any]:
    if surface_type:
        normalized_surface = _normalize(surface_type)
        for item in DETECTED_TYPES:
            if normalized_surface == item["id"] or normalized_surface in _normalize(item["description"]):
                return {"id": item["id"], "confidence": "high", "matched_rule": "explicit_surface_type"}

    haystack = _normalize(f"{command} {selected_text} {context_hint}")
    for type_id, keywords in TYPE_RULES.items():
        matched = [keyword for keyword in keywords if keyword in haystack]
        if matched:
            return {
                "id": type_id,
                "confidence": "high" if len(matched) > 1 else "medium",
                "matched_rule": matched[0],
            }

    if selected_text:
        text_type = "paragraph" if len(selected_text) > 180 else "text_selection"
        return {"id": text_type, "confidence": "medium", "matched_rule": "selected_text_present"}

    return {"id": "unknown_context", "confidence": "low", "matched_rule": "fallback_unknown"}


def _detect_actions(command: str, detected_type: str, target_intent: str = "") -> List[Dict[str, Any]]:
    haystack = _normalize(f"{command} {target_intent}")
    action_ids: List[str] = []
    for action_id, keywords in ACTION_RULES.items():
        if any(keyword in haystack for keyword in keywords):
            action_ids.append(action_id)

    for action_id in TYPE_DEFAULT_ACTIONS.get(detected_type, ["explain"]):
        if action_id not in action_ids:
            action_ids.append(action_id)

    return [
        {
            **_action_by_id(action_id),
            "prepared_state_only": action_id.endswith("_preview") or action_id in {"create_reply_draft", "create_email_draft"},
        }
        for action_id in action_ids[:4]
    ]


def pointer_schema() -> Dict[str, Any]:
    return {
        "status": "pointer_schema_ready",
        "layer": "21.6",
        "name": "Lux Pointer / Context Cursor",
        "core_idea": [
            "Show it, Lux understands.",
            "Select it, say it, Lux prepares the safe next action.",
            "Pointer is a context layer, not a separate heavy mode.",
        ],
        "detected_types": DETECTED_TYPES,
        "suggested_action_groups": SUGGESTED_ACTIONS,
        "input_fields": [
            "command",
            "selected_text",
            "context_hint",
            "surface_type",
            "source_app",
            "target_intent",
            "sensitivity",
        ],
        "safety_rules": [
            "No silent screen scraping.",
            "No screenshot analysis or real screen reading is performed.",
            "No click, app control, browser control, device control, send, export, print, or file write is performed.",
            "Only user-provided selected_text/context_hint/command are used for preview.",
            "Risky actions require permission and confirmation and remain prepared-state only.",
        ],
        "read_only": True,
        "can_execute_now": False,
        "real_screen_read_performed": False,
        "real_click_performed": False,
        "real_control_performed": False,
        "real_send_performed": False,
        "real_export_performed": False,
        "real_print_performed": False,
        "real_file_created": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
    }


def preview_pointer_action(
    command: str,
    selected_text: str = "",
    context_hint: str = "",
    surface_type: str = "",
    source_app: str = "",
    target_intent: str = "",
    sensitivity: str = "normal",
) -> Dict[str, Any]:
    detected_type = _detect_type(command, selected_text, context_hint, surface_type)
    actions = _detect_actions(command, detected_type["id"], target_intent)
    primary = actions[0] if actions else _action_by_id("explain")
    risky_action_ids = {"send_ready_preview", "export_ready_preview", "print_ready_preview", "calendar_ready_preview", "navigation_ready_preview", "open_safely_preview"}
    action_ids = {action["id"] for action in actions}
    normalized_sensitivity = _normalize(sensitivity)
    sensitive = normalized_sensitivity in {"high", "private", "privacy", "sensitive", "hassas"}
    requires_permission = sensitive or any(action.get("requires_permission") for action in actions)
    requires_confirmation = sensitive or any(action.get("requires_confirmation") for action in actions) or bool(action_ids & risky_action_ids)

    return {
        "raw_command": command,
        "selected_text_supplied": bool(selected_text),
        "context_hint_supplied": bool(context_hint),
        "detected_type": detected_type,
        "detected_surface_type": surface_type or detected_type["id"],
        "source_app": source_app or "unspecified_surface",
        "suggested_actions": actions,
        "recommended_primary_action": primary,
        "requires_permission": requires_permission,
        "requires_confirmation": requires_confirmation,
        "can_execute_now": False,
        "real_screen_read_performed": False,
        "real_click_performed": False,
        "real_control_performed": False,
        "real_send_performed": False,
        "real_export_performed": False,
        "real_print_performed": False,
        "real_file_created": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "safe_pointer_plan": {
            "mode": "contextual_action_preview",
            "ui_feel": "minimal amber/platinum contextual action bubble",
            "principle": "few buttons, more useful prepared-state options",
            "steps": [
                "Use only the user-provided selected text, context hint, or command.",
                "Classify the pointed context type.",
                "Offer one primary safe action and a few prepared-state alternatives.",
                "Require permission and confirmation for send/export/print/open/navigation actions.",
            ],
        },
        "privacy_boundary": {
            "no_silent_screen_scraping": True,
            "real_screenshot_analysis_performed": False,
            "real_screen_read_performed": False,
            "real_click_performed": False,
            "real_control_performed": False,
            "raw_sensitive_expansion_performed": False,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_write_performed": False,
        },
        "preview_response": "Preview only: Lux would classify the pointed context and prepare safe actions, but no real screen or device action was performed.",
        "read_only": True,
        "db_write_performed": False,
        "file_write_performed": False,
    }


def pointer_status() -> Dict[str, Any]:
    return {
        "layer": "21.6",
        "name": "Pointer / Context Cursor Preview",
        "status": "scaffold_ready",
        "detected_type_count": len(DETECTED_TYPES),
        "suggested_action_count": len(SUGGESTED_ACTIONS),
        "available_endpoints": [
            "/pointer/schema",
            "/pointer/preview-action",
            "/debug/pointer-status",
        ],
        "read_only": True,
        "can_execute_now": False,
        "real_screen_read_performed": False,
        "real_click_performed": False,
        "real_control_performed": False,
        "real_send_performed": False,
        "real_export_performed": False,
        "real_print_performed": False,
        "real_file_created": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_notes": [
            "No silent screen scraping.",
            "No real screenshot analysis, click, control, send, export, print, or file creation.",
            "Pointer works as a context layer for future Workspace, Device Bridge, Luxway, Visual, and Personal Agent flows.",
        ],
    }
