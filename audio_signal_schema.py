"""Read-only audio signal schema and preview scaffold."""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Any, Dict, List


PRIVACY_NOTE = (
    "Read-only simulated audio signal preview only. No microphone access, recording, "
    "raw audio storage, STT, TTS, file write, DB write, memory write, or clinical diagnosis is performed."
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


def _signal_id(text: str) -> str:
    digest = hashlib.sha1((text or "audio-signal-preview").encode("utf-8")).hexdigest()[:10]
    return f"audio_signal_{digest}"


def audio_signal_schema() -> Dict[str, Any]:
    return {
        "signal_id": "audio_signal_schema_preview",
        "source_modality": "simulated_audio",
        "raw_audio_stored": False,
        "recording_performed": False,
        "microphone_used": False,
        "consent_required": True,
        "sensitivity": "medium",
        "retention": "none",
        "derived_signals": [],
        "rhythm_preview": {},
        "energy_preview": {},
        "pause_pattern_preview": {},
        "tone_shift_preview": {},
        "emotional_atmosphere_preview": {},
        "safety_note": PRIVACY_NOTE,
        "clinical_diagnosis_performed": False,
        "read_only": True,
    }


def _derived_signals(normalized: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    if any(word in normalized for word in ["yorgun", "dusuk", "bitkin"]):
        signals.append({"id": "low_energy_signal", "label": "Low energy preview", "confidence": "medium"})
    if any(word in normalized for word in ["panik", "hizli", "acele"]):
        signals.append({"id": "fast_rhythm_signal", "label": "Fast rhythm preview", "confidence": "medium"})
    if any(word in normalized for word in ["sakin", "yavas", "gece radyosu"]):
        signals.append({"id": "calm_slowing_signal", "label": "Calm slowing preview", "confidence": "medium"})
    if any(word in normalized for word in ["net", "anlasilir", "clear"]):
        signals.append({"id": "clarity_signal", "label": "Clear delivery preview", "confidence": "medium"})
    if not signals:
        signals.append({"id": "general_audio_context_signal", "label": "General simulated audio context", "confidence": "low"})
    return signals


def _rhythm_preview(normalized: str) -> Dict[str, Any]:
    if "panik" in normalized or "hizli" in normalized:
        return {"pace": "fast", "stability": "uneven_preview", "suggested_adjustment": "slow_gradually"}
    if "gece radyosu" in normalized or "yavas" in normalized or "sakin" in normalized:
        return {"pace": "slow", "stability": "steady_preview", "suggested_adjustment": "keep_calm_flow"}
    return {"pace": "normal", "stability": "unknown_without_audio", "suggested_adjustment": "maintain_smooth_stream"}


def _energy_preview(normalized: str) -> Dict[str, Any]:
    if "yorgun" in normalized or "dusuk" in normalized:
        return {"level": "low_preview", "supportive_response": "clear_and_gentle"}
    if "panik" in normalized or "hizli" in normalized:
        return {"level": "high_uneven_preview", "supportive_response": "calm_and_structured"}
    return {"level": "medium_or_unknown_preview", "supportive_response": "neutral_clear"}


def _pause_pattern_preview(normalized: str) -> Dict[str, Any]:
    if "panik" in normalized or "hizli" in normalized:
        return {"pattern": "short_pauses_preview", "recommendation": "add_breathing_space_between_sentences"}
    if "yorgun" in normalized or "dusuk" in normalized:
        return {"pattern": "longer_pauses_preview", "recommendation": "use_short_clear_sections"}
    return {"pattern": "unknown_without_audio", "recommendation": "keep_gradual_readable_output"}


def _tone_shift_preview(normalized: str) -> Dict[str, Any]:
    if "sakin" in normalized or "gece radyosu" in normalized:
        return {"target_tone": "calm_low", "shift": "slow_down_and_soften"}
    if "net" in normalized:
        return {"target_tone": "clear_accessible", "shift": "increase_clarity_without_speed_spike"}
    return {"target_tone": "normal_luxviai", "shift": "no_runtime_audio_change"}


def _emotional_atmosphere_preview(normalized: str) -> Dict[str, Any]:
    if "panik" in normalized:
        return {"atmosphere": "tense_preview", "response_style": "calm_safety_careful"}
    if "yorgun" in normalized or "dusuk" in normalized:
        return {"atmosphere": "tired_preview", "response_style": "gentle_clear"}
    if "sakin" in normalized or "gece radyosu" in normalized:
        return {"atmosphere": "quiet_preview", "response_style": "slow_warm"}
    return {"atmosphere": "neutral_or_unknown_preview", "response_style": "normal"}


def preview_audio_signal(description: str, simulated_voice_note: str = "", context: str = "") -> Dict[str, Any]:
    raw_description = description or ""
    combined = " ".join(part for part in [raw_description, simulated_voice_note or "", context or ""] if part)
    normalized = _normalize_text(combined)
    schema = audio_signal_schema()
    schema.update(
        {
            "signal_id": _signal_id(combined),
            "description": raw_description,
            "simulated_voice_note": simulated_voice_note or "",
            "context": context or "",
            "derived_signals": _derived_signals(normalized),
            "rhythm_preview": _rhythm_preview(normalized),
            "energy_preview": _energy_preview(normalized),
            "pause_pattern_preview": _pause_pattern_preview(normalized),
            "tone_shift_preview": _tone_shift_preview(normalized),
            "emotional_atmosphere_preview": _emotional_atmosphere_preview(normalized),
            "privacy_note": PRIVACY_NOTE,
        }
    )
    return schema


def audio_status_snapshot() -> Dict[str, Any]:
    return {
        "audio_signal_schema_ready": True,
        "source_modality": "simulated_audio",
        "read_only": True,
        "raw_audio_stored": False,
        "recording_performed": False,
        "microphone_used": False,
        "real_stt_enabled": False,
        "real_tts_enabled": False,
        "clinical_diagnosis_performed": False,
        "memory_write_enabled": False,
        "db_write_enabled": False,
        "file_write_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "available_endpoints": ["/audio/signal-schema", "/audio/preview-signal", "/debug/audio-status"],
        "privacy_note": PRIVACY_NOTE,
    }
