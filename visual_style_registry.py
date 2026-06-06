"""Read-only Lux Visual System style registry scaffold."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


LUX_VISUAL_METADATA = {
    "lux_amber_accent_color": "#ab6b0c",
    "default_line_density": "low",
    "signature_note": "Place a subtle Luxviai signature at the right bottom when visual generation is implemented.",
    "image_generation_enabled": False,
}


_STYLE_DEFINITIONS = [
    ("lux_signature", "Lux Signature", "brand", "Luxviai signature language with restrained amber accent.", 0.25, 0.0, 1.0, ["lux_amber_accent", "normal_real_clean"], "Keep signature subtle and right-bottom."),
    ("normal_real_clean", "Normal Real Clean", "base", "Clean realistic baseline with minimal stylization.", 0.55, 0.0, 1.0, ["lux_signature", "film_grain"], "Avoid over-processing faces or products."),
    ("custom_blend", "Custom Blend", "blend", "User-defined style mixture preview.", 0.2, 0.0, 1.0, ["pixel", "watercolor", "oil_paint"], "Keep ratios explicit before real generation."),
    ("lux_ambrosia", "Lux Ambrosia", "emotional", "Warm emotional visual texture with restrained glow.", 0.35, 0.0, 1.0, ["lux_amber_accent", "soft_neon", "dreamcore"], "Avoid generic AI-glow overload."),
    ("dream_scene", "Dream Scene", "dream", "Dream-state scene language for symbolic visual planning.", 0.35, 0.0, 1.0, ["dreamcore", "film_grain", "watercolor"], "Keep scene readable and grounded."),
    ("pixel", "Pixel", "texture", "Pixel-art or pixel texture influence.", 0.2, 0.0, 0.7, ["custom_blend", "vintage_poster"], "High ratios may reduce realism."),
    ("watercolor", "Watercolor", "paint", "Soft watercolor texture influence.", 0.2, 0.0, 0.8, ["dream_scene", "monochrome_organic"], "Avoid muddy low-contrast blends."),
    ("oil_paint", "Oil Paint", "paint", "Oil-paint texture and brushwork influence.", 0.2, 0.0, 0.8, ["custom_blend", "film_grain"], "Use carefully with clean realism."),
    ("soft_neon", "Soft Neon", "light", "Soft neon rim or atmosphere influence.", 0.18, 0.0, 0.6, ["lux_ambrosia", "dreamcore"], "Avoid excessive bloom."),
    ("vintage_poster", "Vintage Poster", "graphic", "Poster-like vintage composition preview.", 0.2, 0.0, 0.7, ["film_grain", "pixel"], "Text rendering is future-only."),
    ("film_grain", "Film Grain", "texture", "Subtle film grain and analog texture.", 0.16, 0.0, 0.5, ["normal_real_clean", "vintage_poster"], "Keep grain subtle."),
    ("micro_glyph", "Micro Glyph", "detail", "Tiny symbolic glyph texture language.", 0.08, 0.0, 0.35, ["lux_signature", "dreamcore"], "Avoid clutter and overdrawn lines."),
    ("dreamcore", "Dreamcore", "dream", "Surreal dreamlike atmosphere preview.", 0.24, 0.0, 0.8, ["dream_scene", "soft_neon"], "Preserve subject clarity."),
    ("monochrome_organic", "Monochrome Organic", "organic", "Muted organic monochrome texture.", 0.18, 0.0, 0.7, ["watercolor", "micro_glyph"], "Avoid flat one-note palettes."),
    ("lux_amber_accent", "Lux Amber Accent", "brand_color", "Lux amber accent color #ab6b0c.", 0.12, 0.0, 0.45, ["lux_signature", "lux_ambrosia"], "Use as an accent, not a full wash."),
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


def visual_style_registry() -> Dict[str, Any]:
    styles = [
        {
            "id": style_id,
            "display_name": display_name,
            "category": category,
            "description": description,
            "default_ratio": default_ratio,
            "min_ratio": min_ratio,
            "max_ratio": max_ratio,
            "compatible_with": compatible_with,
            "caution": caution,
            "read_only": True,
        }
        for (
            style_id,
            display_name,
            category,
            description,
            default_ratio,
            min_ratio,
            max_ratio,
            compatible_with,
            caution,
        ) in _STYLE_DEFINITIONS
    ]
    return {
        "styles": styles,
        "metadata": dict(LUX_VISUAL_METADATA),
        "read_only": True,
        "image_generation_performed": False,
        "memory_write_performed": False,
        "file_written": False,
    }


def _style_map() -> Dict[str, Dict[str, Any]]:
    return {style["id"]: style for style in visual_style_registry()["styles"]}


def _detect_styles(prompt: str, requested_styles: List[str]) -> List[str]:
    normalized = _normalize_text(prompt)
    detected: List[str] = []
    requested = [_normalize_text(style).replace(" ", "_") for style in requested_styles]
    for style_id in requested:
        if style_id in _style_map() and style_id not in detected:
            detected.append(style_id)
    keyword_map = [
        ("lux_signature", ["lux tarzi", "luxviai", "imza", "signature"]),
        ("normal_real_clean", ["normal", "gercekci", "real", "clean", "temiz"]),
        ("oil_paint", ["yagli boya", "oil"]),
        ("pixel", ["pixel", "piksel"]),
        ("lux_ambrosia", ["ambrosia", "his", "hissi"]),
        ("dream_scene", ["ruya", "sahne", "dream"]),
        ("soft_neon", ["soft neon", "neon"]),
        ("vintage_poster", ["vintage", "poster"]),
        ("watercolor", ["watercolor", "suluboya"]),
        ("film_grain", ["film grain", "grain"]),
        ("lux_amber_accent", ["amber", "#ab6b0c"]),
    ]
    for style_id, keywords in keyword_map:
        if any(keyword in normalized for keyword in keywords) and style_id not in detected:
            detected.append(style_id)
    if not detected:
        detected = ["normal_real_clean", "lux_signature", "lux_amber_accent"]
    return detected


def _explicit_ratio(prompt: str, style_id: str) -> float | None:
    normalized = _normalize_text(prompt)
    aliases = {
        "oil_paint": ["yagli boya", "oil"],
        "pixel": ["pixel", "piksel"],
        "watercolor": ["watercolor", "suluboya"],
    }.get(style_id, [style_id.replace("_", " ")])
    for alias in aliases:
        pattern = rf"%\s*(\d+)\s*{re.escape(alias)}|(\d+)\s*%\s*{re.escape(alias)}"
        match = re.search(pattern, normalized)
        if match:
            value = next(group for group in match.groups() if group)
            return max(0.0, min(1.0, int(value) / 100))
    return None


def preview_visual_style(prompt: str, requested_styles: List[str] | None = None, mode: str = "") -> Dict[str, Any]:
    styles_by_id = _style_map()
    detected_ids = _detect_styles(prompt, requested_styles or [])
    suggested_styles = [styles_by_id[style_id] for style_id in detected_ids if style_id in styles_by_id]
    style_mix_preview = []
    for style in suggested_styles:
        explicit_ratio = _explicit_ratio(prompt, style["id"])
        ratio = explicit_ratio if explicit_ratio is not None else style["default_ratio"]
        ratio = max(float(style["min_ratio"]), min(float(style["max_ratio"]), ratio))
        style_mix_preview.append(
            {
                "style_id": style["id"],
                "display_name": style["display_name"],
                "ratio": ratio,
                "read_only": True,
            }
        )
    normalized = _normalize_text(prompt)
    if any(word in normalized for word in ["ruya", "dream", "sahne"]):
        detected_visual_intent = "dream_scene_preview"
    elif any(word in normalized for word in ["ambrosia", "his", "hissi"]):
        detected_visual_intent = "ambrosia_style_preview"
    elif any(word in normalized for word in ["cv", "rapor", "sunum"]):
        detected_visual_intent = "workspace_visual_style_preview"
    else:
        detected_visual_intent = "style_preview"
    return {
        "prompt": prompt or "",
        "mode": mode or "visual_style_preview",
        "detected_visual_intent": detected_visual_intent,
        "suggested_styles": suggested_styles,
        "style_mix_preview": style_mix_preview,
        "signature_default": True,
        "lux_metadata": dict(LUX_VISUAL_METADATA),
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only visual style preview only; no image API call or file generation is performed.",
    }
