"""Read-only Lux Visual System style ratio preview scaffold."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List

from visual_style_registry import LUX_VISUAL_METADATA, preview_visual_style, visual_style_registry


_STYLE_ALIASES = {
    "lux_signature": ["lux signature", "lux tarzi", "luxviai", "imza"],
    "normal_real_clean": ["normal", "gercekci", "real", "clean", "temiz", "gercekci temiz"],
    "custom_blend": ["custom", "blend", "karisim"],
    "lux_ambrosia": ["ambrosia", "ambrosia hissi", "his", "hissi"],
    "dream_scene": ["ruya", "ruya sahnesi", "dream", "dream scene", "sahne"],
    "pixel": ["pixel", "piksel"],
    "watercolor": ["watercolor", "suluboya"],
    "oil_paint": ["yagli boya", "oil", "oil paint"],
    "soft_neon": ["soft neon", "neon"],
    "vintage_poster": ["vintage", "poster", "vintage poster"],
    "film_grain": ["film grain", "grain", "gren"],
    "micro_glyph": ["micro glyph", "glyph", "mikro sembol"],
    "dreamcore": ["dreamcore"],
    "monochrome_organic": ["monochrome", "organic", "organik", "monokrom"],
    "lux_amber_accent": ["amber", "lux amber", "#ab6b0c"],
}


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


def _style_map() -> Dict[str, Dict[str, Any]]:
    return {style["id"]: style for style in visual_style_registry()["styles"]}


def _expanded_style_aliases() -> Dict[str, List[str]]:
    aliases = {style_id: list(items) for style_id, items in _STYLE_ALIASES.items()}
    for style in visual_style_registry()["styles"]:
        style_id = style["id"]
        names = [
            style_id,
            style_id.replace("_", " "),
            str(style.get("display_name", "")),
            *[str(item) for item in style.get("aliases", [])],
        ]
        bucket = aliases.setdefault(style_id, [])
        for name in names:
            normalized = _normalize_text(name).replace("_", " ").strip()
            if normalized and normalized not in bucket:
                bucket.append(normalized)
    return aliases


def _style_for_alias(alias: str) -> str:
    normalized = _normalize_text(alias).replace("_", " ").strip()
    styles_by_id = _style_map()
    if normalized.replace(" ", "_") in styles_by_id:
        return normalized.replace(" ", "_")
    for style_id, aliases in _expanded_style_aliases().items():
        if normalized in aliases:
            return style_id
    for style_id, aliases in _expanded_style_aliases().items():
        if any(item in normalized for item in aliases):
            return style_id
    return ""


def _detect_styles(text: str, requested_styles: List[str]) -> List[str]:
    normalized = _normalize_text(text)
    detected: List[str] = []
    for requested in requested_styles:
        style_id = _style_for_alias(requested)
        if style_id and style_id not in detected:
            detected.append(style_id)
    for style_id, aliases in _expanded_style_aliases().items():
        if any(alias in normalized for alias in aliases) and style_id not in detected:
            detected.append(style_id)
    if not detected:
        detected = ["normal_real_clean", "lux_signature", "lux_amber_accent"]
    return detected


def _parse_direct_ratios(text: str) -> Dict[str, float]:
    normalized = _normalize_text(text)
    ratios: Dict[str, float] = {}
    for style_id, aliases in _expanded_style_aliases().items():
        for alias in aliases:
            escaped = re.escape(alias)
            patterns = [
                rf"%\s*(\d+(?:\.\d+)?)\s*{escaped}",
                rf"(\d+(?:\.\d+)?)\s*%\s*{escaped}",
                rf"{escaped}\s*%\s*(\d+(?:\.\d+)?)",
                rf"{escaped}\s*(\d+(?:\.\d+)?)\s*%",
            ]
            for pattern in patterns:
                match = re.search(pattern, normalized)
                if match:
                    ratios[style_id] = max(0.0, min(1.0, float(match.group(1)) / 100.0))
                    break
            if style_id in ratios:
                break
    return ratios


def _parse_adjustments(text: str) -> Dict[str, Dict[str, float | str]]:
    normalized = _normalize_text(text)
    adjustments: Dict[str, Dict[str, float | str]] = {}
    for style_id, aliases in _expanded_style_aliases().items():
        for alias in aliases:
            escaped = re.escape(alias)
            pattern = rf"{escaped}\s*%\s*(\d+(?:\.\d+)?)\s*(azalt|artir|arttir|cogalt|yukselt)"
            match = re.search(pattern, normalized)
            if not match:
                pattern = rf"{escaped}\s*(\d+(?:\.\d+)?)\s*%\s*(azalt|artir|arttir|cogalt|yukselt)"
                match = re.search(pattern, normalized)
            if match:
                value = max(0.0, min(1.0, float(match.group(1)) / 100.0))
                direction = str(match.group(2))
                adjustments[style_id] = {
                    "direction": "decrease" if "azalt" in direction else "increase",
                    "amount": value,
                }
                break
    return adjustments


def _adaptive_ratios(detected_styles: List[str], prompt: str) -> Dict[str, float]:
    styles_by_id = _style_map()
    preview = preview_visual_style(prompt, detected_styles)
    preview_ratios = {
        item["style_id"]: float(item["ratio"])
        for item in preview.get("style_mix_preview", [])
        if item.get("style_id") in styles_by_id
    }
    if preview_ratios:
        return preview_ratios
    return {style_id: float(styles_by_id[style_id]["default_ratio"]) for style_id in detected_styles if style_id in styles_by_id}


def _normalize_ratio_map(ratios: Dict[str, float]) -> Dict[str, float]:
    positive = {style_id: max(0.0, value) for style_id, value in ratios.items() if value > 0}
    total = sum(positive.values())
    if not positive or total <= 0:
        return {}
    return {style_id: round(value / total, 4) for style_id, value in positive.items()}


def preview_visual_style_ratio(
    prompt: str,
    ratio_text: str = "",
    requested_styles: List[str] | None = None,
    mode: str = "",
) -> Dict[str, Any]:
    raw_prompt = prompt or ""
    raw_ratio_text = ratio_text or ""
    combined_text = " ".join(part for part in [raw_prompt, raw_ratio_text] if part)
    warnings: List[str] = []
    styles_by_id = _style_map()
    requested = requested_styles or []
    detected_styles = _detect_styles(combined_text, requested)
    requested_ratios = _parse_direct_ratios(combined_text)
    adjustments = _parse_adjustments(combined_text)
    adaptive = _adaptive_ratios(detected_styles, combined_text)

    for requested_style in requested:
        if not _style_for_alias(requested_style):
            warnings.append(f"Unknown style '{requested_style}' was ignored.")

    working_ratios = dict(adaptive)
    working_ratios.update(requested_ratios)
    for style_id, adjustment in adjustments.items():
        base = working_ratios.get(style_id, adaptive.get(style_id, styles_by_id.get(style_id, {}).get("default_ratio", 0.1)))
        amount = float(adjustment["amount"])
        if adjustment["direction"] == "decrease":
            working_ratios[style_id] = max(0.0, float(base) - amount)
        else:
            working_ratios[style_id] = min(1.0, float(base) + amount)
        if style_id not in detected_styles:
            detected_styles.append(style_id)

    for style_id in detected_styles:
        if style_id not in working_ratios and style_id in adaptive:
            working_ratios[style_id] = adaptive[style_id]

    if not requested_ratios and not adjustments:
        warnings.append("No explicit ratio was provided; adaptive Lux style mix is shown.")
    raw_total = sum(requested_ratios.values())
    if requested_ratios and abs(raw_total - 1.0) > 0.001:
        warnings.append("Requested ratios do not sum to 100%; normalized preview is shown.")

    normalized_ratios = _normalize_ratio_map(working_ratios)
    final_mix = []
    for style_id, ratio in normalized_ratios.items():
        style = styles_by_id.get(style_id)
        if not style:
            warnings.append(f"Unknown style id '{style_id}' was ignored.")
            continue
        final_mix.append(
            {
                "style_id": style_id,
                "display_name": style["display_name"],
                "ratio": ratio,
                "source": "requested" if style_id in requested_ratios else "adaptive_or_adjusted",
                "read_only": True,
            }
        )

    return {
        "raw_prompt": raw_prompt,
        "raw_ratio_text": raw_ratio_text,
        "mode": mode or "ratio_preview",
        "detected_styles": detected_styles,
        "requested_ratios": requested_ratios,
        "normalized_ratios": normalized_ratios,
        "adaptive_ratios": adaptive,
        "ratio_adjustments": adjustments,
        "final_style_mix_preview": final_mix,
        "lux_amber_accent": LUX_VISUAL_METADATA["lux_amber_accent_color"],
        "line_density_default": LUX_VISUAL_METADATA["default_line_density"],
        "signature_default": True,
        "warnings": warnings,
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only ratio preview only; no image generation, file write, DB write, or memory write is performed.",
    }
