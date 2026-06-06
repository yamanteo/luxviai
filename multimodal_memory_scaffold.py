"""Multimodal memory schema scaffold for future expansion."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping


MEMORY_SIGNAL_TYPES = [
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

SOURCE_MODALITIES = ["text", "image", "audio", "file", "drawing", "mixed"]

SENSITIVITY_LEVELS = ["low", "medium", "high"]

RETENTION_LEVELS = ["session", "project", "long_term", "never"]

VISUAL_MEMORY_SIGNAL_TEMPLATES = [
    "preferred_dark_background",
    "lux_amber_accent_#ab6b0c",
    "right_bottom_luxviai_signature",
    "low_line_density",
    "ambrosia_emotional_visual_texture",
    "dream_scene_state",
    "style_mix_ratios",
    "avoid_overdrawn_lines",
    "avoid_generic_ai_visuals",
]

DEFAULT_MEMORY_FIELDS = [
    "id",
    "type",
    "title",
    "summary",
    "source_modality",
    "sensitivity",
    "retention",
    "created_at",
    "updated_at",
    "tags",
    "raw_data_stored",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_modality(value: str) -> str:
    fallback = "text"
    value = (value or "").strip().lower()
    if value not in SOURCE_MODALITIES:
        return fallback
    return value


def _safe_sensitivity(value: str) -> str:
    fallback = "low"
    value = (value or "").strip().lower()
    if value not in SENSITIVITY_LEVELS:
        return fallback
    return value


def _safe_retention(value: str) -> str:
    fallback = "session"
    value = (value or "").strip().lower()
    if value not in RETENTION_LEVELS:
        return fallback
    return value


def _default_timestamp() -> str:
    return _now_iso()


def _default_signal_template(signal_type: str) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": signal_type,
        "title": f"{signal_type} taslağı",
        "summary": f"{signal_type} için güvenli özet/sinyal",
        "source_modality": _safe_modality("mixed" if signal_type in {"project_decision", "workspace_context"} else "text"),
        "sensitivity": "medium" if signal_type in {"emotional_context", "safety_boundary"} else "low",
        "retention": "project" if signal_type in {"project_decision", "workspace_context", "safety_boundary"} else "session",
        "created_at": _default_timestamp(),
        "updated_at": _default_timestamp(),
        "tags": [],
        "raw_data_stored": False,
    }


def _visual_signals() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in VISUAL_MEMORY_SIGNAL_TEMPLATES:
        out.append({
            "id": str(uuid.uuid4()),
            "type": "lux_visual_style",
            "title": item,
            "summary": f"{item} görsel sistem işareti",
            "source_modality": "image",
            "sensitivity": "low",
            "retention": "long_term",
            "created_at": _default_timestamp(),
            "updated_at": _default_timestamp(),
            "tags": ["lux_visual", "template"],
            "raw_data_stored": False,
        })
    return out


MULTIMODAL_MEMORY_SCHEMA = {
    "signal_types": MEMORY_SIGNAL_TYPES,
    "source_modalities": SOURCE_MODALITIES,
    "sensitivity_levels": SENSITIVITY_LEVELS,
    "retention_levels": RETENTION_LEVELS,
    "required_fields": DEFAULT_MEMORY_FIELDS,
}

MULTIMODAL_MEMORY_TEMPLATES = [
    _default_signal_template(signal_type)
    for signal_type in MEMORY_SIGNAL_TYPES
] + _visual_signals()


def multimodal_memory_schema() -> Dict[str, Any]:
    return {
        "signal_types": list(MEMORY_SIGNAL_TYPES),
        "source_modalities": list(SOURCE_MODALITIES),
        "sensitivity_levels": list(SENSITIVITY_LEVELS),
        "retention_levels": list(RETENTION_LEVELS),
        "required_fields": list(DEFAULT_MEMORY_FIELDS),
        "templates": [dict(item) for item in MULTIMODAL_MEMORY_TEMPLATES],
        "visual_templates": list(VISUAL_MEMORY_SIGNAL_TEMPLATES),
    }


def build_memory_signal(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(payload.get("id") or uuid.uuid4()),
        "type": str(payload.get("type") or "text_preference"),
        "title": str(payload.get("title") or "").strip() or f"{str(payload.get('type') or 'text_preference')} sinyal",
        "summary": str(payload.get("summary") or "").strip() or f"{str(payload.get('type') or 'text_preference')} özeti",
        "source_modality": _safe_modality(str(payload.get("source_modality", ""))),
        "sensitivity": _safe_sensitivity(str(payload.get("sensitivity", ""))),
        "retention": _safe_retention(str(payload.get("retention", ""))),
        "created_at": _default_timestamp() if not str(payload.get("created_at", "")).strip() else str(payload.get("created_at", "")).strip(),
        "updated_at": _default_timestamp() if not str(payload.get("updated_at", "")).strip() else str(payload.get("updated_at", "")).strip(),
        "tags": [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
        # Raw data her zaman güvenlik nedeniyle False tutulur.
        "raw_data_stored": False,
    }


def validate_memory_signal(payload: Mapping[str, Any]) -> Dict[str, Any]:
    signal = build_memory_signal(payload)
    errors: List[str] = []

    if signal["type"] not in MEMORY_SIGNAL_TYPES:
        errors.append("Unsupported memory signal type.")

    if signal["source_modality"] not in SOURCE_MODALITIES:
        errors.append("Unsupported source modality.")

    if signal["sensitivity"] not in SENSITIVITY_LEVELS:
        errors.append("Unsupported sensitivity.")

    if signal["retention"] not in RETENTION_LEVELS:
        errors.append("Unsupported retention.")

    if signal.get("type") in {"safety_boundary", "emotional_context"} and signal.get("sensitivity") != "high":
        errors.append("Safety/emotional signals should usually be medium/high sensitivity.")

    if signal["title"] == "":
        errors.append("Missing title.")
    if signal["summary"] == "":
        errors.append("Missing summary.")

    return {
        "ok": not errors,
        "signal": signal,
        "errors": errors,
        "checks": [
            "required_fields_present",
            "raw_data_stored_enforced_false",
            "text_or_media_channel_validated",
            "retention_and_sensitivity_validated",
            "privacy_first_policy",
        ],
    }
