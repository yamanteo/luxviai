"""Read-only voice mode and writing speed preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


WRITING_SPEED_REGISTRY = {
    "default_writing_speed": 0.9,
    "slower_speed": 0.8,
    "very_slow_speed": 0.7,
    "faster_speed": 1.0,
    "workspace_fast_speed": 1.1,
    "quick_summary_speed": 1.3,
    "very_fast_summary_speed": 1.5,
}

VOICE_SPEED_REGISTRY = {
    "normal_voice_speed": 1.0,
    "calm_voice_speed": 0.85,
    "night_radio_voice_speed": 0.8,
    "podcast_voice_speed": 0.95,
    "fast_brief_voice_speed": 1.15,
    "emotional_soft_voice_speed": 0.85,
    "accessibility_clear_voice_speed": 0.9,
    "silent_text_only_voice_speed": 0.0,
}

STREAM_BEHAVIOR = {
    "smooth_typewriter": True,
    "block_dump_allowed": False,
    "final_bulk_injection_allowed": False,
    "long_answer_gradual": True,
    "quick_summary_fast_but_streamed": True,
}

PRIVACY_NOTE = (
    "Read-only preview only. No TTS, STT, microphone access, recording, audio file, "
    "DB write, memory write, or export is performed. input_modality='voice' is simulated metadata."
)


def _mode(
    mode_id: str,
    display_name: str,
    aliases: List[str],
    category: str,
    description: str,
    default_writing_speed: float,
    default_voice_speed: float,
    default_tone: str,
) -> Dict[str, Any]:
    return {
        "id": mode_id,
        "display_name": display_name,
        "aliases": aliases,
        "category": category,
        "description": description,
        "default_writing_speed": default_writing_speed,
        "default_voice_speed": default_voice_speed,
        "default_tone": default_tone,
        "stream_behavior": dict(STREAM_BEHAVIOR),
        "privacy_note": PRIVACY_NOTE,
        "real_audio_enabled": False,
        "microphone_used": False,
        "recording_performed": False,
        "read_only": True,
    }


VOICE_MODES = [
    _mode("normal_voice", "Normal Voice", ["normal", "normal hiza don", "normal hiz"], "default", "Default Luxviai voice/speed preview.", 0.9, 1.0, "normal"),
    _mode("calm_voice", "Calm Voice", ["sakin anlat", "yavas anlat", "daha yavas", "yavas yaz"], "calm", "Slower calm explanation preview.", 0.8, 0.85, "calm"),
    _mode("night_radio_voice", "Night Radio Voice", ["gece radyosu", "gece modu", "yavas ve sakin"], "night", "Slow warm night-radio style preview.", 0.8, 0.8, "low_calm"),
    _mode("podcast_voice", "Podcast Voice", ["podcast tonu", "program gibi anlat"], "spoken", "Podcast-like explanatory tone preview.", 0.9, 0.95, "conversational"),
    _mode("focused_work_voice", "Focused Work Voice", ["calisma modu", "workspace hizli", "odak modu", "hizli uret"], "workspace", "Focused workspace production preview.", 1.1, 1.0, "focused"),
    _mode("fast_brief_voice", "Fast Brief Voice", ["hizli ozet", "kisaca hizlica", "cok hizli ozet"], "brief", "Fast summary preview while preserving streamed output.", 1.3, 1.15, "brief"),
    _mode("emotional_soft_voice", "Emotional Soft Voice", ["duygusal anlat", "yumusak anlat"], "emotional", "Soft emotional support preview.", 0.8, 0.85, "emotional_soft"),
    _mode("premium_low_voice", "Premium Low Voice", ["dusuk ses", "tok ses", "premium ses"], "spoken", "Low premium tone preview.", 0.9, 0.9, "low_premium"),
    _mode("silent_text_only", "Silent Text Only", ["sadece yazi", "ses yok", "sessiz mod"], "silent", "Text-only preview with no audio.", 0.9, 0.0, "silent"),
    _mode("accessibility_clear_voice", "Accessibility Clear Voice", ["net konus", "anlasilir anlat", "acik anlat"], "accessibility", "Clear accessible explanation preview.", 0.9, 0.9, "clear"),
]

SAFETY_KEYWORDS = ["korkuyorum", "panik", "acil", "tehlike", "zarar", "cok kotuyum", "cok kotuyum"]


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


def voice_mode_registry() -> Dict[str, Any]:
    return {
        "writing_speed_registry": dict(WRITING_SPEED_REGISTRY),
        "voice_speed_registry": dict(VOICE_SPEED_REGISTRY),
        "voice_modes": [dict(mode) for mode in VOICE_MODES],
        "stream_behavior_rule": dict(STREAM_BEHAVIOR),
        "block_dump_prevention": True,
        "real_audio_enabled": False,
        "microphone_used": False,
        "recording_performed": False,
        "read_only": True,
        "privacy_note": PRIVACY_NOTE,
    }


def _detect_voice_mode(command: str, context: str) -> Dict[str, Any]:
    normalized = _normalize_text(" ".join([command or "", context or ""]))
    for mode in VOICE_MODES:
        for alias in mode["aliases"]:
            if _normalize_text(alias) in normalized:
                return mode
    if "sakin" in normalized or "yavas" in normalized:
        return _mode_by_id("calm_voice")
    return _mode_by_id("normal_voice")


def _mode_by_id(mode_id: str) -> Dict[str, Any]:
    for mode in VOICE_MODES:
        if mode["id"] == mode_id:
            return mode
    return VOICE_MODES[0]


def _is_safety_sensitive(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(keyword in normalized for keyword in SAFETY_KEYWORDS)


def _workspace_auto_speed(normalized: str, response_size: str) -> tuple[float, str]:
    if response_size == "workspace_large":
        return 0.9, "workspace_large responses stay gradual at 0.9 to prevent block-like output."
    if response_size == "long":
        return 0.9, "Long answers stay near 0.9 and never exceed 1.1."
    if response_size == "short":
        return 1.0, "Small answers can use 1.0 while preserving stream/typewriter feel."
    if "kisa ozet" in normalized or "hizli ozet" in normalized:
        return 1.3, "Quick summaries can use 1.3 but remain streamed."
    return 0.9, "Normal Luxviai response starts at 0.9."


def _writing_speed(command: str, context: str, response_size: str, mode: Dict[str, Any]) -> tuple[float, str]:
    normalized = _normalize_text(" ".join([command or "", context or ""]))
    safety_sensitive = _is_safety_sensitive(normalized)
    if safety_sensitive:
        return 0.8, "Safety-sensitive preview stays calm between 0.7 and 0.9."
    if "cok hizli ozet" in normalized:
        return 1.5, "Explicit very fast summary uses 1.5 but still streams gradually."
    if "hizli ozet" in normalized or "kisaca hizlica" in normalized:
        return 1.3, "Fast summary uses 1.3 but block dump remains disabled."
    if "cok yavas" in normalized:
        return 0.7, "Very slow command maps to 0.7."
    if "gece modu" in normalized or "gece radyosu" in normalized or "duygusal anlat" in normalized or "sakin" in normalized:
        return 0.8, "Calm/night/emotional responses stay between 0.7 and 0.9."
    if "daha yavas" in normalized or "yavas yaz" in normalized:
        return 0.8, "Slower writing command maps to 0.8."
    if "daha hizli" in normalized:
        return 1.0, "Faster command maps to 1.0."
    if "hizli uret" in normalized or "calisma modu" in normalized or "workspace hizli" in normalized:
        speed = 1.0 if response_size == "long" else 1.1
        return speed, "Workspace fast preview uses 1.0-1.1 and avoids long-answer over-speed."
    auto_speed, reason = _workspace_auto_speed(normalized, response_size)
    return min(auto_speed, 1.1), reason


def preview_voice_mode(
    command: str,
    context: str = "",
    response_size: str = "medium",
    input_modality: str = "text",
) -> Dict[str, Any]:
    raw_command = command or ""
    normalized_size = response_size if response_size in {"short", "medium", "long", "workspace_large"} else "medium"
    normalized_modality = input_modality if input_modality in {"text", "voice"} else "text"
    detected_mode = _detect_voice_mode(raw_command, context)
    writing_speed, reason = _writing_speed(raw_command, context, normalized_size, detected_mode)
    if normalized_size in {"long", "workspace_large"}:
        writing_speed = min(writing_speed, 1.0 if normalized_size == "workspace_large" else 1.1)
    if _is_safety_sensitive(" ".join([raw_command, context])):
        detected_mode = _mode_by_id("calm_voice")
        writing_speed = min(max(writing_speed, 0.7), 0.9)
    voice_speed = 0.0 if detected_mode["id"] == "silent_text_only" else float(detected_mode["default_voice_speed"])
    return {
        "raw_command": raw_command,
        "context": context or "",
        "response_size": normalized_size,
        "input_modality": normalized_modality,
        "input_modality_note": "voice is simulated metadata only; no microphone or STT is used.",
        "detected_voice_mode": detected_mode["id"],
        "voice_mode": dict(detected_mode),
        "writing_speed_preview": writing_speed,
        "voice_speed_preview": voice_speed,
        "auto_speed_reason": reason,
        "tone_preview": "safety_careful_calm" if _is_safety_sensitive(" ".join([raw_command, context])) else detected_mode["default_tone"],
        "stream_behavior": dict(STREAM_BEHAVIOR),
        "block_dump_prevention": True,
        "real_audio_enabled": False,
        "microphone_used": False,
        "recording_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "user_facing_output_file_created": False,
        "privacy_note": PRIVACY_NOTE,
    }


def voice_status_snapshot() -> Dict[str, Any]:
    return {
        "voice_registry_ready": True,
        "read_only": True,
        "real_audio_enabled": False,
        "microphone_used": False,
        "recording_performed": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "file_write_enabled": False,
        "user_facing_output_file_created": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "input_modality_voice_is_simulated_metadata": True,
        "block_dump_prevention": True,
        "stream_behavior": dict(STREAM_BEHAVIOR),
        "available_endpoints": ["/voice/modes", "/voice/preview-mode", "/debug/voice-status"],
        "privacy_note": PRIVACY_NOTE,
    }
