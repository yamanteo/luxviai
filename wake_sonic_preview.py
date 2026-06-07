from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


WAKE_MODES: List[Dict[str, Any]] = [
    {
        "id": "off",
        "display_name": "Off",
        "description": "Wake phrase is disabled. No microphone listening.",
        "opt_in_required": True,
        "microphone_access_enabled": False,
        "background_listening_enabled": False,
        "read_only": True,
    },
    {
        "id": "app_open_wake_phrase",
        "display_name": "App Open Wake Phrase",
        "description": "Wake phrase policy preview only while the app is open. No real listening.",
        "opt_in_required": True,
        "microphone_access_enabled": False,
        "background_listening_enabled": False,
        "read_only": True,
    },
    {
        "id": "permissioned_background_wake_phrase",
        "display_name": "Permissioned Background Wake Phrase",
        "description": "Future permissioned background wake phrase idea. No real background listening in this scaffold.",
        "opt_in_required": True,
        "microphone_access_enabled": False,
        "background_listening_enabled": False,
        "read_only": True,
    },
]


SONIC_FAMILY: List[Dict[str, Any]] = [
    {
        "id": "lux_wake",
        "display_name": "Lux Wake",
        "duration_seconds": "0.6-0.8",
        "description": "Thin platinum click plus a short warm amber halo.",
        "style_tags": ["platinum_click", "warm_amber_halo", "short_signature", "calm_premium"],
        "read_only": True,
    },
    {
        "id": "lux_listen",
        "display_name": "Lux Listen",
        "duration_seconds": "0.3-0.5",
        "description": "Very short soft listening cue, low fatigue and non-alarm.",
        "style_tags": ["soft_luxury", "low_fatigue", "non_alarm", "recognizable"],
        "read_only": True,
    },
    {
        "id": "lux_confirm",
        "display_name": "Lux Confirm",
        "duration_seconds": "0.25-0.4",
        "description": "Premium confirmation tick with warm amber finish.",
        "style_tags": ["platinum_click", "warm_amber_halo", "short_signature", "soft_luxury"],
        "read_only": True,
    },
    {
        "id": "lux_hold",
        "display_name": "Lux Hold",
        "duration_seconds": "0.4-0.7",
        "description": "Soft held cue for waiting or thinking without urgency.",
        "style_tags": ["calm_premium", "low_fatigue", "non_notification_generic"],
        "read_only": True,
    },
    {
        "id": "lux_soft_error",
        "display_name": "Lux Soft Error",
        "duration_seconds": "0.3-0.5",
        "description": "Gentle non-alarm error cue that avoids harsh app notification language.",
        "style_tags": ["non_alarm", "soft_luxury", "low_fatigue"],
        "read_only": True,
    },
    {
        "id": "lux_night",
        "display_name": "Lux Night",
        "duration_seconds": "0.5-0.8",
        "description": "Calmer night-safe cue with lower density and warmer halo.",
        "style_tags": ["night_safe", "warm_amber_halo", "calm_premium", "low_fatigue"],
        "read_only": True,
    },
]


SONIC_STYLE_TAGS = [
    "platinum_click",
    "warm_amber_halo",
    "soft_luxury",
    "short_signature",
    "low_fatigue",
    "non_alarm",
    "non_notification_generic",
    "night_safe",
    "calm_premium",
    "recognizable",
]


WAKE_RULES = {
    "off": ["kapali", "kapat", "off", "wake mode kapali"],
    "app_open_wake_phrase": ["uygulama acikken", "hey lux", "app open", "uyansin"],
    "permissioned_background_wake_phrase": ["arka planda", "izinli wake", "background", "wake phrase fikri"],
}


SONIC_RULES = {
    "lux_wake": ["acilis sesi", "wake sesi", "lux wake", "acildiginda"],
    "lux_listen": ["dinlemeye basladiginda", "listen", "kisa ses"],
    "lux_confirm": ["onay sesi", "confirm", "premium olsun"],
    "lux_hold": ["bekleme", "hold", "dusunurken"],
    "lux_soft_error": ["hata sesi", "soft error", "yanlis"],
    "lux_night": ["gece modu", "gece", "daha sakin", "night"],
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


def _wake_mode_by_id(mode_id: str) -> Dict[str, Any]:
    for mode in WAKE_MODES:
        if mode["id"] == mode_id:
            return mode
    return WAKE_MODES[0]


def _sonic_by_id(event_id: str) -> Dict[str, Any]:
    for item in SONIC_FAMILY:
        if item["id"] == event_id:
            return item
    return SONIC_FAMILY[0]


def _detect_wake_mode(command: str, wake_mode: str = "") -> Dict[str, Any]:
    requested = _normalize(wake_mode)
    if requested:
        for mode in WAKE_MODES:
            if requested == mode["id"] or requested == _normalize(mode["display_name"]):
                return {"id": mode["id"], "confidence": "high", "matched_rule": "explicit_wake_mode"}

    normalized = _normalize(command)
    for mode_id, keywords in WAKE_RULES.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        if matched:
            return {"id": mode_id, "confidence": "high" if len(matched) > 1 else "medium", "matched_rule": matched[0]}
    return {"id": "off", "confidence": "low", "matched_rule": "default_off"}


def _detect_sonic_event(command: str, sonic_event: str = "") -> Dict[str, Any]:
    requested = _normalize(sonic_event)
    if requested:
        for item in SONIC_FAMILY:
            if requested == item["id"] or requested == _normalize(item["display_name"]):
                return {"id": item["id"], "confidence": "high", "matched_rule": "explicit_sonic_event"}

    normalized = _normalize(command)
    for event_id, keywords in SONIC_RULES.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        if matched:
            return {"id": event_id, "confidence": "high" if len(matched) > 1 else "medium", "matched_rule": matched[0]}
    return {"id": "lux_wake", "confidence": "low", "matched_rule": "default_signature"}


def _safety_flags() -> Dict[str, Any]:
    return {
        "microphone_access_enabled": False,
        "real_wake_detection_performed": False,
        "continuous_recording_performed": False,
        "audio_recorded": False,
        "audio_transcribed": False,
        "audio_played": False,
        "background_listening_enabled": False,
        "hidden_recording_allowed": False,
        "opt_in_required": True,
        "visible_status_required": True,
        "easy_disable_required": True,
        "read_only": True,
    }


def wake_sonic_schema() -> Dict[str, Any]:
    return {
        "status": "wake_sonic_schema_ready",
        "layer": "21.8",
        "name": "Wake Mode + Sonic Signature",
        "wake_modes": WAKE_MODES,
        "sonic_family_ids": [item["id"] for item in SONIC_FAMILY],
        "wake_safety_flags": _safety_flags(),
        "core_rules": [
            "Wake phrase is not continuous recording.",
            "No hidden recording is allowed.",
            "Opt-in is required.",
            "Visible microphone status is required.",
            "Easy disable is required.",
            "This scaffold performs no real mic access, detection, recording, playback, TTS, or STT.",
        ],
        "read_only": True,
    }


def wake_sonic_registry() -> Dict[str, Any]:
    return {
        "status": "wake_sonic_registry_ready",
        "wake_modes": WAKE_MODES,
        "sonic_signature": {
            "brand_description": "Thin platinum click plus a short warm amber halo.",
            "style_tags": SONIC_STYLE_TAGS,
            "avoid": [
                "too bright",
                "aggressive",
                "mechanical",
                "alarm-like",
                "cheap generic app notification",
            ],
        },
        "sonic_family": SONIC_FAMILY,
        "read_only": True,
        **_safety_flags(),
    }


def preview_wake_sonic(
    command: str,
    wake_mode: str = "",
    sonic_event: str = "",
    environment: str = "",
    sensitivity: str = "normal",
    user_permission_state: str = "not_granted",
) -> Dict[str, Any]:
    detected_wake = _detect_wake_mode(command, wake_mode)
    detected_sonic = _detect_sonic_event(command, sonic_event)
    wake = _wake_mode_by_id(detected_wake["id"])
    sonic = _sonic_by_id(detected_sonic["id"])
    permission_granted = _normalize(user_permission_state) in {"granted", "izinli", "allowed", "true"}
    permission_required = detected_wake["id"] != "off"
    flags = _safety_flags()
    return {
        "raw_command": command,
        "detected_wake_mode": {
            **detected_wake,
            "display_name": wake["display_name"],
            "description": wake["description"],
        },
        "detected_sonic_event": detected_sonic,
        "wake_phrase_preview": {
            "phrases": ["Lux", "Hey Lux"],
            "active_by_default": False,
            "permission_granted": permission_granted,
            "policy_only": True,
        },
        "opt_in_required": True,
        "permission_required": permission_required,
        "visible_status_required": True,
        "easy_disable_required": True,
        **flags,
        "real_device_control_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "sonic_signature_plan": {
            "brand_description": "Thin platinum click plus a short warm amber halo.",
            "style_tags": SONIC_STYLE_TAGS,
            "environment": environment or "default",
            "sensitivity": sensitivity,
            "audio_generation_performed": False,
            "audio_playback_performed": False,
        },
        "sonic_family_item": sonic,
        "safety_boundary": {
            "no_real_microphone_access": True,
            "no_wake_word_detection": True,
            "no_continuous_recording": True,
            "no_hidden_recording": True,
            "no_audio_playback": True,
            "no_tts_or_stt": True,
            "background_wake_is_future_policy_only": True,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_write_performed": False,
        },
        "preview_response": "Preview only: Wake Mode and Sonic Signature policy are described, but no microphone, recording, playback, TTS, or STT occurred.",
        "read_only": True,
        "db_write_performed": False,
        "file_write_performed": False,
    }


def wake_sonic_status() -> Dict[str, Any]:
    return {
        "layer": "21.8",
        "name": "Wake Mode + Sonic Signature",
        "status": "scaffold_ready",
        "wake_mode_count": len(WAKE_MODES),
        "sonic_family_count": len(SONIC_FAMILY),
        "available_endpoints": [
            "/wake-sonic/schema",
            "/wake-sonic/registry",
            "/wake-sonic/preview",
            "/debug/wake-sonic-status",
        ],
        **_safety_flags(),
        "real_device_control_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }
