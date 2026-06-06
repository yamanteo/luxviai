"""Read-only Lux Visual System prompt builder preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from visual_style_ratio import preview_visual_style_ratio
from visual_style_registry import LUX_VISUAL_METADATA, preview_visual_style, visual_style_registry


NEGATIVE_PROMPT_ITEMS = [
    "no_city",
    "no_room",
    "no_building",
    "no_sign",
    "no_letters",
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
    if "koru" in normalized or "sahneyi degistirme" in normalized or "scene lock" in normalized:
        return "scene_lock"
    if ambrosia_state or "ambrosia" in normalized or "icimde" in normalized or "hissi" in normalized:
        return "ambrosia"
    if scene_state or "ruya" in normalized or "sahne" in normalized:
        return "dream_scene"
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


def _registry_styles_by_id() -> Dict[str, Dict[str, Any]]:
    return {style["id"]: style for style in visual_style_registry()["styles"]}


def _registry_alias_matches(text: str, style_ids: List[str]) -> List[Dict[str, str]]:
    normalized = _normalize_text(text).replace("_", " ")
    styles_by_id = _registry_styles_by_id()
    matches: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for style_id in style_ids:
        style = styles_by_id.get(style_id)
        if not style:
            continue
        aliases = [
            style_id,
            style_id.replace("_", " "),
            str(style.get("display_name", "")),
            *[str(item) for item in style.get("aliases", [])],
        ]
        for alias in aliases:
            normalized_alias = _normalize_text(alias).replace("_", " ").strip()
            if normalized_alias and normalized_alias in normalized and (style_id, normalized_alias) not in seen:
                matches.append(
                    {
                        "style_id": style_id,
                        "display_name": str(style.get("display_name", style_id)),
                        "matched_alias": normalized_alias,
                        "group": str(style.get("group", "")),
                    }
                )
                seen.add((style_id, normalized_alias))
                break
    return matches


def _detected_registry_groups(style_ids: List[str]) -> List[str]:
    styles_by_id = _registry_styles_by_id()
    groups = []
    for style_id in style_ids:
        group = styles_by_id.get(style_id, {}).get("group")
        if group and group not in groups:
            groups.append(str(group))
    return groups


def _lux_rules_applied(detected_mode: str, locked: List[Any]) -> List[str]:
    rules = [
        f"Lux amber accent is preserved as {LUX_VISUAL_METADATA['lux_amber_accent_color']}.",
        f"Default line density stays {LUX_VISUAL_METADATA['default_line_density']}.",
        "Too many lines can make the image look overdrawn.",
        "Right-bottom Luxviai signature is included by default.",
        "Lux is not a fixed place; it is a visual spirit/state language.",
    ]
    if detected_mode == "ambrosia":
        rules.append("Ambrosia is an inner state, not a place.")
        rules.append("Ambrosia avoids city, room, building, sign, letters, and readable text.")
    if detected_mode in {"dream_scene", "scene_lock"} or locked:
        rules.append("Dream Scene details are added to the existing scene instead of rebuilding it.")
        rules.append("Locked elements are preserved when provided.")
    return rules


def _palette_notes(style_ids: List[str]) -> List[str]:
    notes = []
    if "black_velvet" in style_ids:
        notes.append("black velvet #0A0A0A")
    if "platinum_gray" in style_ids or "platinum_thin_line" in style_ids or "silent_glyph" in style_ids:
        notes.append("platinum glyph/line #C0C0C0")
    if "lux_amber_accent" in style_ids:
        notes.append(f"Lux amber {LUX_VISUAL_METADATA['lux_amber_accent_color']}")
    return notes


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
    detected_style_ids = [
        str(style_id)
        for style_id in ratio_preview.get("detected_styles", [])
        if isinstance(style_id, str)
    ]
    if not detected_style_ids:
        detected_style_ids = [
            str(item.get("style_id"))
            for item in style_mix
            if isinstance(item, dict) and item.get("style_id")
        ]
    if "platin" in _normalize_text(raw_prompt) and "platinum_gray" not in detected_style_ids:
        detected_style_ids.append("platinum_gray")
    detected_registry_groups = _detected_registry_groups(detected_style_ids)
    if "lux_special_visual_rules" not in detected_registry_groups:
        detected_registry_groups.append("lux_special_visual_rules")
    used_style_aliases = _registry_alias_matches(" ".join([raw_prompt, ratio_text]), detected_style_ids)
    lux_rules_applied = _lux_rules_applied(detected_mode, locked)
    lux_signature_note = LUX_VISUAL_METADATA["signature_note"]
    negative_prompt = ", ".join(NEGATIVE_PROMPT_ITEMS)
    prompt_sections = {
        "base_prompt": raw_prompt,
        "style": {
            "mix": style_mix,
            "detected_style_ids": detected_style_ids,
            "detected_registry_groups": detected_registry_groups,
            "used_style_aliases": used_style_aliases,
            "lux_amber_accent": LUX_VISUAL_METADATA["lux_amber_accent_color"],
            "line_density": LUX_VISUAL_METADATA["default_line_density"],
            "signature": lux_signature_note,
            "palette_notes": _palette_notes(detected_style_ids),
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
        "Lux is a visual spirit/state language, not a fixed place",
        "too many lines can look overdrawn",
    ]
    style_names = [str(item.get("display_name")) for item in style_mix if isinstance(item, dict) and item.get("display_name")]
    if style_names:
        final_parts.append("styles=" + ", ".join(style_names))
    palette_notes = _palette_notes(detected_style_ids)
    if palette_notes:
        final_parts.append("palette=" + ", ".join(palette_notes))
    if detected_mode == "ambrosia":
        final_parts.append("Ambrosia rule: inner state, not a city, room, building, sign, or text scene")
        final_parts.append("Ambrosia negative constraints: " + ", ".join(LUX_VISUAL_METADATA.get("ambrosia_negative_constraints", [])))
    if scene:
        final_parts.append("dream scene state: " + _scene_summary(scene, raw_prompt))
    if locked:
        final_parts.append("preserve locked elements: " + ", ".join(str(item) for item in locked))
    if detected_mode == "scene_lock":
        final_parts.append("scene_rebuild_required=false; add new detail to the existing scene")
    final_parts.append("negative: " + negative_prompt)
    return {
        "raw_prompt": raw_prompt,
        "detected_mode": detected_mode,
        "visual_intent": _visual_intent(detected_mode),
        "scene_summary": _scene_summary(scene, raw_prompt),
        "style_mix": style_mix,
        "detected_registry_groups": detected_registry_groups,
        "used_style_aliases": used_style_aliases,
        "lux_rules_applied": lux_rules_applied,
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
