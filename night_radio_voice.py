"""Read-only Night Radio / Podcast / Calm voice delivery preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict


STREAM_BEHAVIOR = {
    "smooth_typewriter": True,
    "block_dump_allowed": False,
    "final_bulk_injection_allowed": False,
    "long_answer_gradual": True,
    "quick_summary_fast_but_streamed": True,
}

PRIVACY_NOTE = (
    "Read-only voice delivery preview only. No TTS, STT, microphone access, recording, "
    "audio file, DB write, memory write, or export is performed."
)


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


def _detect_mode(text: str, mood: str, mode: str) -> str:
    if mode:
        normalized_mode = _normalize_text(mode).replace(" ", "_")
        if normalized_mode in {"night_radio", "night_radio_voice", "podcast", "podcast_voice", "calm", "calm_voice", "text_only_night"}:
            return normalized_mode.replace("_voice", "")
    normalized = _normalize_text(" ".join([text or "", mood or ""]))
    if "podcast" in normalized or "program gibi" in normalized:
        return "podcast"
    if "sadece yazi" in normalized and ("gece" in normalized or "night" in normalized):
        return "text_only_night"
    if "gece radyosu" in normalized or "uyumadan" in normalized or "gece modu" in normalized:
        return "night_radio"
    if "sakin" in normalized or "yumusak" in normalized or "dusuk ton" in normalized or "duygusal" in normalized:
        return "calm"
    return "night_radio"


def _speed_for_mode(detected_mode: str, normalized: str, response_size: str) -> tuple[float, float, str]:
    if detected_mode == "podcast":
        return 0.9, 0.95, "Podcast tone uses 0.9-0.95 for clear spoken pacing."
    if detected_mode == "text_only_night":
        return 0.8, 0.0, "Text-only night radio feeling keeps writing slow and audio disabled."
    if "hizli ozet" in normalized or "cok hizli" in normalized:
        return 0.95, 0.9, "Fast summary combined with night/calm voice is capped at 0.9-1.0."
    if detected_mode == "calm":
        return 0.8 if response_size != "long" else 0.75, 0.85, "Calm/emotional tone stays between 0.7 and 0.85."
    return 0.8 if response_size != "long" else 0.75, 0.8, "Night radio tone stays between 0.7 and 0.85."


def _tone_profile(detected_mode: str) -> Dict[str, Any]:
    profiles = {
        "night_radio": {
            "tone": "night_radio",
            "texture": "low, warm, slow, close",
            "intensity": "soft",
            "clarity": "clear_but_unhurried",
        },
        "podcast": {
            "tone": "podcast",
            "texture": "structured, conversational, steady",
            "intensity": "medium",
            "clarity": "clear_explanatory",
        },
        "calm": {
            "tone": "calm_emotional",
            "texture": "gentle, low pressure, soft",
            "intensity": "soft",
            "clarity": "simple_and_reassuring",
        },
        "text_only_night": {
            "tone": "silent_text_night_radio",
            "texture": "written-only, slow, warm",
            "intensity": "soft",
            "clarity": "gradual_text_only",
        },
    }
    return profiles.get(detected_mode, profiles["night_radio"])


def _pause_style(detected_mode: str, response_size: str) -> Dict[str, Any]:
    return {
        "sentence_pause": "long" if detected_mode in {"night_radio", "calm", "text_only_night"} else "medium",
        "paragraph_pause": "soft_long" if response_size in {"long", "workspace_large"} else "soft_medium",
        "breathing_room": True,
        "avoid_dense_blocks": True,
    }


def preview_night_radio_voice(text: str, mood: str = "", response_size: str = "medium", mode: str = "") -> Dict[str, Any]:
    raw_text = text or ""
    normalized_size = response_size if response_size in {"short", "medium", "long", "workspace_large"} else "medium"
    normalized = _normalize_text(" ".join([raw_text, mood or "", mode or ""]))
    detected_mode = _detect_mode(raw_text, mood, mode)
    writing_speed, voice_speed, speed_reason = _speed_for_mode(detected_mode, normalized, normalized_size)
    tone_profile = _tone_profile(detected_mode)
    script_preview = (
        "Gece radyosu hissiyle, metin kademeli ve sakin akar; son cevap tek blok halinde verilmez."
        if detected_mode in {"night_radio", "text_only_night"}
        else "Ses tonu önizlemesi düzenli, açık ve kademeli bir anlatım önerir."
    )
    return {
        "raw_text": raw_text,
        "mood": mood or "",
        "response_size": normalized_size,
        "detected_mode": detected_mode,
        "tone_profile": tone_profile,
        "writing_speed_preview": writing_speed,
        "voice_speed_preview": voice_speed,
        "delivery_notes": [
            speed_reason,
            "Text must keep a smooth stream/typewriter feeling.",
            "No block dump or final bulk injection is allowed.",
            "No real audio is generated in this scaffold.",
        ],
        "pause_style": _pause_style(detected_mode, normalized_size),
        "warmth_level": "high" if detected_mode in {"night_radio", "text_only_night"} else "medium",
        "night_radio_script_preview": script_preview,
        "stream_behavior": dict(STREAM_BEHAVIOR),
        "real_audio_enabled": False,
        "tts_performed": False,
        "microphone_used": False,
        "recording_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "privacy_note": PRIVACY_NOTE,
    }
