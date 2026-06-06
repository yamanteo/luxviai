"""Read-only Lux Ambrosia inner-state visual schema preview."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict

from visual_style_ratio import preview_visual_style_ratio


AMBROSIA_COLORS = {
    "black_velvet_background": "#0A0A0A",
    "amber_inner_light": "#AB6B0C",
    "platinum_silent_glyph": "#C0C0C0",
}

AMBROSIA_NEGATIVE_CONSTRAINTS = [
    "no_city",
    "no_street",
    "no_room",
    "no_building",
    "no_sign",
    "no_letters",
    "no_real_person_identity",
    "no_overcrowded_lines",
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


def _emotional_core(text: str) -> str:
    normalized = _normalize_text(text)
    if any(word in normalized for word in ["yorgun", "agir", "bitkin"]):
        return "quiet_heavy_fatigue"
    if any(word in normalized for word in ["umut", "kirilgan"]):
        return "fragile_hope"
    if any(word in normalized for word in ["karisik", "isık", "isik"]):
        return "confused_mind_with_small_light"
    if any(word in normalized for word in ["ruhani", "amber", "siyah"]):
        return "spiritual_black_amber_presence"
    if any(word in normalized for word in ["bosluk", "asili"]):
        return "suspended_in_inner_void"
    return "inner_state_abstract"


def _visual_metaphor(emotional_core: str) -> str:
    metaphors = {
        "quiet_heavy_fatigue": "a low amber ember under a velvet-dark weight",
        "fragile_hope": "a thin amber filament protected by soft haze",
        "confused_mind_with_small_light": "scattered mist opening around a small inner glow",
        "spiritual_black_amber_presence": "silent glyphs orbiting a warm spiritual core",
        "suspended_in_inner_void": "a weightless form held in black velvet space",
        "inner_state_abstract": "an abstract inner presence shaped by haze and restrained light",
    }
    return metaphors.get(emotional_core, metaphors["inner_state_abstract"])


def _intensity_label(intensity: float | int | None) -> str:
    try:
        value = float(intensity if intensity is not None else 0.5)
    except (TypeError, ValueError):
        value = 0.5
    if value >= 0.75:
        return "high"
    if value <= 0.3:
        return "low"
    return "medium"


def preview_ambrosia_state(
    feeling_text: str,
    intensity: float | int | None = None,
    style_ratio: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    raw_text = feeling_text or ""
    intensity_value = intensity if intensity is not None else 0.5
    core = _emotional_core(raw_text)
    ratio_prompt = "Ambrosia hissi lux amber accent soft neon dreamcore"
    if isinstance(style_ratio, dict):
        ratio_prompt = str(style_ratio.get("prompt") or ratio_prompt)
        ratio_text = str(style_ratio.get("ratio_text") or "")
        requested_styles = list(style_ratio.get("requested_styles") or [])
    else:
        ratio_text = ""
        requested_styles = []
    ratio_preview = preview_visual_style_ratio(
        ratio_prompt,
        ratio_text=ratio_text,
        requested_styles=requested_styles,
        mode="ambrosia_state_preview",
    )
    return {
        "raw_feeling_text": raw_text,
        "ambrosia_state": {
            "state_type": "inner_state_not_place",
            "intensity": intensity_value,
            "intensity_label": _intensity_label(intensity_value),
            "line_density": "low",
            "spatial_rule": "Ambrosia is not a city, room, building, hotel, street, sign, or text scene.",
        },
        "emotional_core": core,
        "visual_metaphor": _visual_metaphor(core),
        "background": {
            "name": "black_velvet_ground",
            "color": AMBROSIA_COLORS["black_velvet_background"],
            "texture": "soft velvet darkness",
        },
        "light": {
            "name": "amber_inner_light",
            "color": AMBROSIA_COLORS["amber_inner_light"],
            "behavior": "subtle inner glow, not external lamp or city light",
        },
        "glyph_layer": {
            "name": "platinum_silent_glyph",
            "color": AMBROSIA_COLORS["platinum_silent_glyph"],
            "density": "low",
            "text_policy": "abstract glyph marks only; no letters or readable text",
        },
        "haze_layer": {
            "enabled": True,
            "quality": "mist/haze, abstract spiritual form",
            "density": _intensity_label(intensity_value),
        },
        "negative_constraints": list(AMBROSIA_NEGATIVE_CONSTRAINTS),
        "style_mix_preview": ratio_preview.get("final_style_mix_preview", []),
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only Ambrosia state preview only; no image generation, Image API call, file write, DB write, or memory write is performed.",
    }
