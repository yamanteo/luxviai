"""Read-only Lux Visual System prompt builder preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from visual_style_ratio import preview_visual_style_ratio
from visual_style_registry import LUX_VISUAL_METADATA, preview_visual_style


NEGATIVE_PROMPT_ITEMS = [
    "no unnecessary text",
    "no readable letters",
    "no signs",
    "no crowded linework",
    "no overdrawn lines",
    "no generic AI visual cliches",
    "no real person identity",
    "no file output",
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


def _detect_mode(prompt: str, mode: str, scene_state: Dict[str, Any], ambrosia_state: Dict[str, Any]) -> str:
    if mode:
        return mode
    normalized = _normalize_text(prompt)
    if ambrosia_state or "ambrosia" in normalized or "icimde" in normalized or "hissi" in normalized:
        return "ambrosia"
    if scene_state or "ruya" in normalized or "sahne" in normalized:
        return "dream_scene"
    if "koru" in normalized or "sahneyi degistirme" in normalized:
        return "scene_lock"
    return "visual_style"


def _visual_intent(detected_mode: str) -> str:
    return {
        "ambrosia": "inner_state_visual_prompt_preview",
        "dream_scene": "dream_scene_prompt_preview",
        "scene_lock": "locked_scene_update_prompt_preview",
        "visual_style": "visual_style_prompt_preview",
    }.get(detected_mode, "visual_prompt_preview")


def _scene_summary(scene_state: Dict[str, Any], prompt: str) -> str:
    if not scene_state:
        return prompt
    subjects = scene_state.get("subjects", [])
    objects = scene_state.get("objects", [])
    lighting = scene_state.get("lighting", {})
    parts = []
    if subjects:
        parts.append(f"subjects={len(subjects)}")
    if objects:
        object_ids = [str(item.get("id")) for item in objects if isinstance(item, dict) and item.get("id")]
        parts.append("objects=" + ", ".join(object_ids))
    if isinstance(lighting, dict) and lighting.get("key_light"):
        parts.append("lighting=" + str(lighting["key_light"]))
    return "; ".join(parts) or prompt


def _ambrosia_section(ambrosia_state: Dict[str, Any]) -> Dict[str, Any]:
    if not ambrosia_state:
        return {}
    return {
        "rule": "Ambrosia is an inner state, not a place.",
        "emotional_core": ambrosia_state.get("emotional_core", ""),
        "visual_metaphor": ambrosia_state.get("visual_metaphor", ""),
        "background": ambrosia_state.get("background", {}),
        "light": ambrosia_state.get("light", {}),
        "glyph_layer": ambrosia_state.get("glyph_layer", {}),
        "negative_constraints": ambrosia_state.get("negative_constraints", []),
    }


def _dream_section(scene_state: Dict[str, Any]) -> Dict[str, Any]:
    if not scene_state:
        return {}
    return {
        "camera": scene_state.get("camera", {}),
        "subjects": scene_state.get("subjects", []),
        "objects": scene_state.get("objects", []),
        "spatial_relations": scene_state.get("spatial_relations", []),
        "lighting": scene_state.get("lighting", {}),
        "emotion": scene_state.get("emotion", {}),
        "locked_elements": scene_state.get("locked_elements", []),
    }


def build_visual_prompt_preview(
    prompt: str,
    mode: str = "",
    style_ratios: Dict[str, Any] | None = None,
    scene_state: Dict[str, Any] | None = None,
    ambrosia_state: Dict[str, Any] | None = None,
    locked_elements: List[Any] | None = None,
) -> Dict[str, Any]:
    raw_prompt = prompt or ""
    scene = scene_state or {}
    ambrosia = ambrosia_state or {}
    locked = list(locked_elements or scene.get("locked_elements", []))
    detected_mode = _detect_mode(raw_prompt, mode, scene, ambrosia)
    ratio_text = ""
    requested_styles: List[str] = []
    if isinstance(style_ratios, dict):
        ratio_text = str(style_ratios.get("ratio_text") or "")
        requested_styles = list(style_ratios.get("requested_styles") or [])
    ratio_preview = preview_visual_style_ratio(raw_prompt, ratio_text, requested_styles, mode="prompt_builder")
    style_preview = preview_visual_style(raw_prompt, requested_styles, mode="prompt_builder")
    style_mix = ratio_preview.get("final_style_mix_preview") or style_preview.get("style_mix_preview", [])
    lux_signature_note = LUX_VISUAL_METADATA["signature_note"]
    negative_prompt = ", ".join(NEGATIVE_PROMPT_ITEMS)
    prompt_sections = {
        "base_prompt": raw_prompt,
        "style": {
            "mix": style_mix,
            "lux_amber_accent": LUX_VISUAL_METADATA["lux_amber_accent_color"],
            "line_density": LUX_VISUAL_METADATA["default_line_density"],
            "signature": lux_signature_note,
        },
        "ambrosia": _ambrosia_section(ambrosia),
        "dream_scene": _dream_section(scene),
        "scene_lock": {
            "locked_elements": locked,
            "preserve_locked_elements": bool(locked),
            "scene_rebuild_required": False,
        },
        "negative_prompt": NEGATIVE_PROMPT_ITEMS,
    }
    final_parts = [
        raw_prompt,
        f"mode={detected_mode}",
        f"lux amber accent {LUX_VISUAL_METADATA['lux_amber_accent_color']}",
        f"line density {LUX_VISUAL_METADATA['default_line_density']}",
        "right-bottom subtle Luxviai signature",
    ]
    if detected_mode == "ambrosia":
        final_parts.append("Ambrosia rule: inner state, not a city, room, building, sign, or text scene")
    if scene:
        final_parts.append("dream scene state: " + _scene_summary(scene, raw_prompt))
    if locked:
        final_parts.append("preserve locked elements: " + ", ".join(str(item) for item in locked))
    final_parts.append("negative: " + negative_prompt)
    return {
        "raw_prompt": raw_prompt,
        "detected_mode": detected_mode,
        "visual_intent": _visual_intent(detected_mode),
        "scene_summary": _scene_summary(scene, raw_prompt),
        "style_mix": style_mix,
        "lux_signature_note": lux_signature_note,
        "negative_prompt": negative_prompt,
        "final_prompt_preview": " | ".join(part for part in final_parts if part),
        "prompt_sections": prompt_sections,
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only visual prompt preview only; no image generation, Image API call, file write, DB write, or memory write is performed.",
    }
