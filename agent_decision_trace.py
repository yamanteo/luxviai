"""Read-only agent decision trace preview scaffold."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any, Dict, List

from mode_registry import preview_mode_command
from permission_boundary import preview_permission_boundary


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


def _mode_ids(mode_candidates: List[Dict[str, Any]]) -> set[str]:
    return {str(item.get("mode", {}).get("id", "")) for item in mode_candidates}


def _domain(boundary: Dict[str, Any], mode_candidates: List[Dict[str, Any]]) -> str:
    action_type = str(boundary.get("action_type", "unknown"))
    families = boundary.get("matched_keyword_families", {})
    ids = _mode_ids(mode_candidates)

    if "luxeph" in ids or action_type == "sensitive_private_mode":
        return "luxeph"
    if "cv_builder" in ids:
        return "cv"
    if "dream_scene" in ids:
        return "dream_scene"
    if "lux_ambrosia" in ids or {"visual_preference", "lux_visual_style"} & ids:
        return "visual_memory"
    if "codex_mode" in ids:
        return "codex"
    if "night_radio" in ids:
        return "audio_voice"
    if "luxworkspace" in ids:
        return "workspace"
    if "email_domain" in families:
        return "email"
    if "calendar_domain" in families:
        return "calendar"
    if action_type == "device_or_phone_action" or "phone_domain" in families:
        return "phone"
    if action_type == "export_or_file_action" or "file_domain" in families:
        return "file_export"
    if action_type == "answer_only":
        return "general_chat"
    return "unknown"


def _intent(boundary: Dict[str, Any], mode_candidates: List[Dict[str, Any]]) -> str:
    action_type = str(boundary.get("action_type", "unknown"))
    ids = _mode_ids(mode_candidates)

    if action_type == "read_private_data":
        return "read_private_data"
    if action_type == "write_or_send_action":
        return "send_or_write"
    if action_type == "export_or_file_action":
        return "export_file"
    if action_type == "device_or_phone_action":
        return "device_action"
    if action_type == "draft_only":
        return "draft_document"
    if action_type in {"mode_preview", "sensitive_private_mode"} or ids:
        if "life_rehearsal" in ids:
            return "rehearse_life_situation"
        if "social_radar" in ids:
            return "analyze_social_context"
        return "start_mode"
    if action_type == "answer_only":
        return "ask_answer"
    return "unknown"


def _decision(boundary: Dict[str, Any], mode_preview: Dict[str, Any]) -> str:
    action_type = str(boundary.get("action_type", "unknown"))
    confidence = str(mode_preview.get("confidence", "low"))

    if action_type == "unknown" and confidence == "low":
        return "low_confidence_ask_clarify"
    if boundary.get("data_sensitivity") == "private_sensitive":
        return "blocked_private_sensitive"
    if boundary.get("requires_confirmation"):
        return "blocked_requires_confirmation"
    if boundary.get("requires_permission"):
        return "blocked_requires_permission"
    if boundary.get("allowed_in_scaffold"):
        return "allowed_preview_only"
    return "blocked_real_action_not_implemented"


def _blocked_actions(boundary: Dict[str, Any], decision: str) -> List[str]:
    action_type = str(boundary.get("action_type", "unknown"))
    if decision == "allowed_preview_only":
        return []
    if action_type == "read_private_data":
        return ["read_private_data"]
    if action_type == "write_or_send_action":
        return ["send_message_or_email", "write_external_content"]
    if action_type == "device_or_phone_action":
        return ["device_scan_or_change", "phone_or_app_action", "delete_or_cleanup"]
    if action_type == "export_or_file_action":
        return ["export_file", "download_or_write_file"]
    if action_type == "sensitive_private_mode":
        return ["activate_private_sensitive_mode"]
    return ["real_action_execution"]


def _risk_summary(boundary: Dict[str, Any], decision: str) -> Dict[str, Any]:
    return {
        "action_type": boundary.get("action_type", "unknown"),
        "data_sensitivity": boundary.get("data_sensitivity", "none"),
        "requires_permission": bool(boundary.get("requires_permission")),
        "requires_confirmation": bool(boundary.get("requires_confirmation")),
        "allowed_in_scaffold": bool(boundary.get("allowed_in_scaffold")),
        "decision": decision,
    }


def _safe_next_step(decision: str, domain: str, intent: str) -> str:
    if decision == "low_confidence_ask_clarify":
        return "Komutu biraz daha netlestirmek icin kisa bir soru sor."
    if decision == "allowed_preview_only":
        if intent == "draft_document":
            return "Sadece taslak/plan onizlemesi sun; dosya olusturma."
        if intent == "start_mode":
            return "Sadece mode adayini goster; gercek mode degistirme."
        return "Guvenli, kisa ve read-only bir cevap ver."
    if decision == "blocked_private_sensitive":
        return "Ozel/hassas alan icin acik onay gerektigini belirt ve islem yapma."
    if decision == "blocked_requires_confirmation":
        return "Gercek islemden once acik kullanici onayi gerektigini belirt."
    if decision == "blocked_requires_permission":
        return "Gerekli izni acikla; izin olmadan veri erisimi yapma."
    if domain == "file_export":
        return "Export/dosya isleminin scaffold'da kapali oldugunu belirt."
    return "Bu asamada sadece guvenli preview sun."


def _user_facing_preview(decision: str, domain: str, intent: str) -> str:
    if decision == "allowed_preview_only":
        return f"Bu komut {domain} alaninda {intent} niyeti gibi gorunuyor; su an yalnizca guvenli onizleme yapabilirim."
    if decision == "low_confidence_ask_clarify":
        return "Bu komut icin niyet dusuk guvenle algilandi; devam etmeden once kisa bir netlestirme iyi olur."
    return f"Bu komut {domain} alaninda {intent} riski tasiyor; gercek islem yapamam, yalnizca gerekli izin/onay sinirini gosterebilirim."


def build_agent_decision_trace(command: str) -> Dict[str, Any]:
    """Build a read-only trace of mode, boundary, and scaffold decision."""
    mode_preview = preview_mode_command(command)
    boundary = preview_permission_boundary(command)
    mode_candidates = mode_preview.get("matched_modes", [])
    domain = _domain(boundary, mode_candidates)
    intent = _intent(boundary, mode_candidates)
    decision = _decision(boundary, mode_preview)

    return {
        "trace_id": str(uuid.uuid4()),
        "raw_command": command,
        "normalized_command": _normalize_text(command),
        "mode_candidates": mode_candidates,
        "permission_boundary": boundary,
        "inferred_agent_domain": domain,
        "inferred_user_intent": intent,
        "risk_summary": _risk_summary(boundary, decision),
        "scaffold_decision": decision,
        "blocked_actions": _blocked_actions(boundary, decision),
        "safe_next_step": _safe_next_step(decision, domain, intent),
        "user_facing_preview": _user_facing_preview(decision, domain, intent),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "can_execute_now": False,
    }
