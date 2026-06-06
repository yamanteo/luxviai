"""Read-only Lux Dream Scene state preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from visual_style_ratio import preview_visual_style_ratio


DREAM_NEGATIVE_CONSTRAINTS = [
    "no_image_generation",
    "no_file_write",
    "no_memory_write",
    "no_real_person_identity",
    "preserve_locked_elements",
    "do_not_rebuild_scene_from_scratch",
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


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _camera(scene: str) -> Dict[str, Any]:
    normalized = _normalize_text(scene)
    if _contains_any(normalized, ["elimde", "basim", "yakinda", "hafif sola"]):
        distance = "close"
    elif _contains_any(normalized, ["uzakta", "gokyuzunde", "denizde"]):
        distance = "wide"
    else:
        distance = "medium"
    angle = "slightly_left" if _contains_any(normalized, ["sola", "sol"]) else "neutral"
    movement = "ascending_loop" if _contains_any(normalized, ["merdiven", "cikiyorum", "bitmiyor"]) else "still_preview"
    return {
        "distance": distance,
        "angle": angle,
        "movement": movement,
        "framing": "scene_state_preview",
    }


def _subjects(scene: str) -> List[Dict[str, Any]]:
    normalized = _normalize_text(scene)
    subjects: List[Dict[str, Any]] = []
    if _contains_any(normalized, ["ben", "degilim", "yuruyor", "cikiyorum", "elimde", "basim"]):
        subjects.append({"id": "dream_self", "type": "self_presence", "description": "narrator presence without real identity"})
    if _contains_any(normalized, ["insan", "ogrenci", "kisi"]):
        subjects.append({"id": "distant_figures", "type": "figure", "description": "non-identifying figures"})
    return subjects


def _objects(scene: str) -> List[Dict[str, Any]]:
    normalized = _normalize_text(scene)
    object_map = [
        ("boat", ["sandal", "tekne"]),
        ("amber_light", ["amber", "isik", "uzakta"]),
        ("bowl", ["kase"]),
        ("stairs", ["merdiven"]),
        ("thin_symbols", ["sembol", "glyph"]),
        ("sea", ["deniz"]),
        ("sky", ["gokyuzu"]),
    ]
    objects: List[Dict[str, Any]] = []
    for object_id, keywords in object_map:
        if _contains_any(normalized, keywords):
            objects.append({"id": object_id, "type": "object_or_environment", "locked_candidate": True})
    return objects


def _spatial_relations(scene: str) -> List[Dict[str, str]]:
    normalized = _normalize_text(scene)
    relations: List[Dict[str, str]] = []
    if _contains_any(normalized, ["uzakta"]):
        relations.append({"relation": "distant", "target": "amber_light"})
    if _contains_any(normalized, ["denizde", "deniz"]):
        relations.append({"relation": "within_or_on", "target": "sea"})
    if _contains_any(normalized, ["boslukta", "asili"]):
        relations.append({"relation": "suspended", "target": "void_space"})
    if _contains_any(normalized, ["elimde"]):
        relations.append({"relation": "held_by_subject", "target": "bowl"})
    if _contains_any(normalized, ["yukari", "cikiyorum", "merdiven"]):
        relations.append({"relation": "upward_loop", "target": "stairs"})
    return relations


def _lighting(scene: str) -> Dict[str, Any]:
    normalized = _normalize_text(scene)
    if _contains_any(normalized, ["amber", "isik"]):
        return {"key_light": "distant_amber_light", "color": "#AB6B0C", "mood": "fragile_guidance"}
    if _contains_any(normalized, ["karanlik"]):
        return {"key_light": "low_darkness", "color": "#0A0A0A", "mood": "uncertain"}
    return {"key_light": "undefined_soft_light", "color": "", "mood": "unspecified"}


def _emotion(scene: str) -> Dict[str, str]:
    normalized = _normalize_text(scene)
    if _contains_any(normalized, ["karanlik", "bitmiyor", "bosluk"]):
        return {"primary": "uncertainty", "secondary": "suspension"}
    if _contains_any(normalized, ["amber", "isik"]):
        return {"primary": "fragile_hope", "secondary": "distance"}
    if _contains_any(normalized, ["ruya", "hayal", "ani"]):
        return {"primary": "dreamlike", "secondary": "memory_trace"}
    return {"primary": "unknown", "secondary": "needs_clarification"}


def _missing_details(scene: str) -> List[str]:
    normalized = _normalize_text(scene)
    missing: List[str] = []
    if not _subjects(scene):
        missing.append("subject_presence")
    if not _objects(scene):
        missing.append("key_objects")
    if not _contains_any(normalized, ["karanlik", "isik", "amber", "gokyuzu"]):
        missing.append("lighting")
    if not _contains_any(normalized, ["deniz", "oda", "bosluk", "merdiven", "gokyuzu"]):
        missing.append("space_or_environment")
    return missing


def preview_dream_scene_state(
    scene_text: str,
    style_hint: str = "",
    locked_elements: List[Any] | None = None,
) -> Dict[str, Any]:
    raw_scene = scene_text or ""
    locked = list(locked_elements or [])
    style_prompt = style_hint or f"dream scene {raw_scene}"
    ratio_preview = preview_visual_style_ratio(style_prompt, requested_styles=["dream_scene"], mode="dream_scene_state_preview")
    missing = _missing_details(raw_scene)
    return {
        "raw_scene_text": raw_scene,
        "scene_state": {
            "state_type": "dream_scene_preview",
            "source_type": "dream_memory_or_imagined_scene",
            "locked_element_policy": "new details should update the existing scene state without rebuilding it from scratch",
        },
        "camera": _camera(raw_scene),
        "subjects": _subjects(raw_scene),
        "objects": _objects(raw_scene),
        "spatial_relations": _spatial_relations(raw_scene),
        "lighting": _lighting(raw_scene),
        "emotion": _emotion(raw_scene),
        "style_ratios": ratio_preview.get("final_style_mix_preview", []),
        "locked_elements": locked,
        "negative_constraints": list(DREAM_NEGATIVE_CONSTRAINTS),
        "missing_details": missing,
        "clarification_question": "Sahnede ana ozne, mekan ve isik nasil kalmali?" if missing else "",
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only dream scene state preview only; no image generation, Image API call, file write, DB write, or memory write is performed.",
    }
