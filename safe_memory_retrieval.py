"""Read-only safe memory retrieval policy preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from model_router_config import preview_model_route


MEMORY_TYPES = [
    "text_preference",
    "visual_preference",
    "audio_signal",
    "file_context",
    "project_decision",
    "workspace_context",
    "style_preference",
    "emotional_context",
    "safety_boundary",
    "lux_visual_style",
    "lux_ambrosia_reference",
    "dream_scene_reference",
]

BASE_BLOCKED_MEMORY_TYPES = [
    "raw_private_message",
    "raw_audio",
    "raw_file_content",
    "crisis_content_raw",
    "raw_sensitive_content",
    "exact_personal_details",
    "private_contact_content",
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


def _detect_requested_type(command: str, requested_memory_type: str) -> str:
    if requested_memory_type in MEMORY_TYPES:
        return requested_memory_type
    normalized = _normalize_text(command)
    if any(keyword in normalized for keyword in ["ambrosia"]):
        return "lux_ambrosia_reference"
    if any(keyword in normalized for keyword in ["gorsel", "visual", "tarz", "renk", "style"]):
        return "lux_visual_style"
    if any(keyword in normalized for keyword in ["workspace", "proje", "not", "rapor", "cv"]):
        return "workspace_context"
    if any(keyword in normalized for keyword in ["ses", "audio", "voice"]):
        return "audio_signal"
    if any(keyword in normalized for keyword in ["ruya", "dream", "sahne"]):
        return "dream_scene_reference"
    if any(keyword in normalized for keyword in ["ozel mesaj", "mesaj gecmisi", "private message"]):
        return "safety_boundary"
    return "text_preference"


def _allowed_types(task_type: str, command: str) -> List[str]:
    normalized = _normalize_text(command)
    if "luxeph" in normalized:
        return []
    if task_type in {"visual_prompt", "dream_scene", "ambrosia_prompt"} or any(
        keyword in normalized for keyword in ["gorsel", "ambrosia", "ruya", "tarz"]
    ):
        return ["visual_preference", "style_preference", "lux_visual_style", "lux_ambrosia_reference", "dream_scene_reference"]
    if task_type in {"workspace", "report_writer", "cv_builder", "presentation_planner"} or any(
        keyword in normalized for keyword in ["workspace", "proje", "rapor", "cv"]
    ):
        return ["project_decision", "workspace_context", "style_preference", "file_context"]
    if task_type == "audio_voice" or "ses" in normalized:
        return ["audio_signal", "style_preference"]
    if task_type in {"safety_sensitive", "privacy_sensitive", "permission_boundary"}:
        return ["safety_boundary"]
    return ["text_preference", "style_preference", "safety_boundary"]


def _is_sensitive_request(command: str, sensitivity: str) -> bool:
    normalized = _normalize_text(command)
    return sensitivity in {"high", "privacy", "safety"} or any(
        keyword in normalized
        for keyword in ["ozel", "private", "hassas", "gizli", "mesaj gecmisi", "kriz", "luxeph"]
    )


def safe_memory_policy() -> Dict[str, Any]:
    return {
        "memory_types": list(MEMORY_TYPES),
        "safe_retrieval_rule": "Only safe summaries and derived preference signals may be previewed.",
        "blocked_memory_types": list(BASE_BLOCKED_MEMORY_TYPES),
        "luxeph_no_memory_rule": True,
        "raw_memory_returned": False,
        "raw_sensitive_memory_returned": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "read_only": True,
        "privacy_note": "No real memory is read or written. Raw private messages, raw audio, raw file content, and crisis raw content are blocked.",
    }


def preview_safe_memory_retrieval(
    command: str,
    task_type: str = "",
    sensitivity: str = "normal",
    requested_memory_type: str = "",
) -> Dict[str, Any]:
    raw_command = command or ""
    route = preview_model_route(raw_command, task_type, sensitivity, "medium")
    detected_task_type = str(route.get("detected_task_type", "unknown"))
    requested = _detect_requested_type(raw_command, requested_memory_type)
    allowed = _allowed_types(detected_task_type, raw_command)
    normalized = _normalize_text(raw_command)
    sensitive = _is_sensitive_request(raw_command, sensitivity)
    luxeph_block = "luxeph" in normalized
    raw_sensitive_request = any(keyword in normalized for keyword in ["ozel mesaj", "mesaj gecmisi", "private message"])
    retrieval_allowed = bool(allowed) and requested in allowed and not luxeph_block and not raw_sensitive_request
    if luxeph_block:
        retrieval_reason = "Luxeph no-memory rule blocks retrieval preview."
    elif raw_sensitive_request:
        retrieval_reason = "Raw private message/history retrieval is blocked; only safety boundary metadata may be previewed."
    elif retrieval_allowed:
        retrieval_reason = "Only safe summary or derived preference context may be previewed."
    else:
        retrieval_reason = "Requested memory type is not allowed for this task; ask for safer summary context."
    return {
        "raw_command": raw_command,
        "detected_task_type": detected_task_type,
        "requested_memory_type": requested,
        "allowed_memory_types": allowed,
        "blocked_memory_types": list(BASE_BLOCKED_MEMORY_TYPES),
        "retrieval_allowed": retrieval_allowed,
        "retrieval_reason": retrieval_reason,
        "safe_context_preview": {
            "summary_only": True,
            "derived_preference_only": True,
            "suggested_context_type": requested if retrieval_allowed else None,
            "preview_text": "Safe summary context preview only; no raw memory content is returned.",
        },
        "privacy_risk": "high" if sensitive else "low",
        "raw_memory_returned": False,
        "raw_sensitive_memory_returned": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "read_only": True,
        "privacy_note": "No real memory read/write occurs. Raw private messages, raw audio, raw file content, and crisis raw content stay blocked.",
    }
