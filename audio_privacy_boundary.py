"""Read-only privacy boundary preview for simulated audio requests."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


PRIVACY_NOTE = (
    "Privacy-first audio boundary preview only. Real microphone access, recording, "
    "raw audio storage, STT/TTS, clinical diagnosis, DB write, memory write, and file write are blocked."
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


def _consent_required(normalized: str) -> bool:
    consent_keywords = ["sesimi", "mikrofon", "kaydet", "record", "analiz et", "dinle", "audio"]
    return any(keyword in normalized for keyword in consent_keywords)


def _blocked_actions(normalized: str, consent_state: str) -> List[str]:
    blocked = [
        "raw_audio_storage",
        "clinical_or_diagnostic_interpretation",
        "memory_write",
        "db_write",
        "file_or_audio_export",
    ]
    if any(keyword in normalized for keyword in ["mikrofon", "dinle", "sesimi", "kaydet", "record"]):
        blocked.extend(["microphone_access", "audio_recording"])
    if consent_state != "granted":
        blocked.append("real_audio_processing_without_explicit_consent")
    return sorted(set(blocked))


def _safe_audio_use(normalized: str) -> List[str]:
    safe = ["derived_signal_preview_only", "tone_and_tempo_suggestion", "no_raw_audio_storage"]
    if "panik" in normalized:
        safe.append("calm_tone_and_slower_pacing_suggestion_without_diagnosis")
    if "sakin" in normalized or "tonumu" in normalized:
        safe.append("calmer_text_or_voice_mode_preview")
    return safe


def preview_audio_privacy_boundary(
    command: str,
    audio_context: str = "",
    consent_state: str = "not_granted",
) -> Dict[str, Any]:
    raw_command = command or ""
    normalized_consent = consent_state if consent_state in {"not_granted", "requested", "granted"} else "not_granted"
    normalized = _normalize_text(" ".join([raw_command, audio_context or ""]))
    consent_required = _consent_required(normalized)
    blocked = _blocked_actions(normalized, normalized_consent)
    allowed_without_consent = [
        "read_only_privacy_boundary_preview",
        "derived_signal_schema_preview_without_raw_audio",
        "general_tone_or_tempo_suggestion",
    ]
    blocked_without_consent = blocked if normalized_consent != "granted" else [
        action for action in blocked if action not in {"real_audio_processing_without_explicit_consent"}
    ]
    return {
        "raw_command": raw_command,
        "audio_context": audio_context or "",
        "consent_required": consent_required,
        "consent_state": normalized_consent,
        "allowed_without_consent": allowed_without_consent,
        "blocked_without_consent": blocked_without_consent,
        "raw_audio_allowed": False,
        "raw_audio_stored": False,
        "derived_signal_only": True,
        "recording_performed": False,
        "microphone_used": False,
        "clinical_diagnosis_allowed": False,
        "clinical_diagnosis_performed": False,
        "memory_write_allowed": False,
        "safe_audio_use": _safe_audio_use(normalized),
        "blocked_actions": blocked,
        "privacy_note": PRIVACY_NOTE,
        "read_only": True,
    }
