"""Read-only Dream Scene lock/update preview scaffold."""

from __future__ import annotations

import copy
import unicodedata
from typing import Any, Dict, List


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


def _ids_from_items(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    ids: List[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
        elif isinstance(item, str):
            ids.append(item)
    return ids


def _locked_elements(scene_state: Dict[str, Any]) -> List[str]:
    locked = _ids_from_items(scene_state.get("locked_elements"))
    if locked:
        return locked
    candidates: List[str] = []
    for key in ["subjects", "objects"]:
        for item in scene_state.get(key, []) if isinstance(scene_state.get(key), list) else []:
            if isinstance(item, dict) and item.get("locked_candidate") and item.get("id"):
                candidates.append(str(item["id"]))
    return candidates


def _proposed_updates(new_detail: str) -> List[Dict[str, Any]]:
    normalized = _normalize_text(new_detail)
    updates: List[Dict[str, Any]] = []
    if _contains_any(normalized, ["bas", "basini", "kafa"]) and _contains_any(normalized, ["sol", "sola"]):
        updates.append({"target": "dream_self.head", "operation": "adjust_pose", "value": "turn_slightly_left"})
    if _contains_any(normalized, ["el", "elde", "elindeki"]) and _contains_any(normalized, ["kase", "koru"]):
        updates.append({"target": "bowl", "operation": "preserve_object", "value": "keep_in_hand"})
    if _contains_any(normalized, ["amber", "isik"]) and _contains_any(normalized, ["uzak", "uzaktan"]):
        updates.append({"target": "amber_light", "operation": "adjust_distance", "value": "slightly_farther"})
    if _contains_any(normalized, ["sembol", "glyph"]) and _contains_any(normalized, ["azalt", "seyrek"]):
        updates.append({"target": "thin_symbols", "operation": "reduce_density", "value": "lower_symbol_count"})
    if _contains_any(normalized, ["sag", "saga", "sag tarafa"]) and _contains_any(normalized, ["kapi"]):
        updates.append({"target": "right_side_door", "operation": "add_object", "value": "small_door_on_right"})
    if not updates and new_detail.strip():
        updates.append({"target": "scene", "operation": "append_detail_preview", "value": new_detail.strip()})
    return updates


def _conflicts(new_detail: str, locked: List[str]) -> List[Dict[str, str]]:
    normalized = _normalize_text(new_detail)
    conflicts: List[Dict[str, str]] = []
    destructive = _contains_any(normalized, ["sil", "kaldir", "degistir", "bastan", "sifirla", "yeniden kur"])
    if not destructive:
        return conflicts
    for item in locked:
        if item and item.replace("_", " ") in normalized:
            conflicts.append(
                {
                    "locked_element": item,
                    "reason": "New detail may alter or remove a locked element.",
                }
            )
    if _contains_any(normalized, ["bastan", "sifirla", "yeniden kur"]):
        conflicts.append(
            {
                "locked_element": "scene_state",
                "reason": "Scene rebuild language conflicts with scene lock policy.",
            }
        )
    return conflicts


def _missing_details(new_detail: str) -> List[str]:
    normalized = _normalize_text(new_detail)
    missing: List[str] = []
    if _contains_any(normalized, ["ekle", "koy", "yerlestir"]) and not _contains_any(
        normalized, ["sag", "sol", "ust", "alt", "arka", "on", "uzak", "yakin"]
    ):
        missing.append("placement")
    if _contains_any(normalized, ["isik", "amber"]) and not _contains_any(normalized, ["uzak", "yakin", "sag", "sol"]):
        missing.append("light_position")
    if not new_detail.strip():
        missing.append("new_detail")
    return missing


def preview_scene_lock(
    current_scene_state: Dict[str, Any] | None,
    new_detail: str,
    lock_strength: float | int | None = None,
) -> Dict[str, Any]:
    original = copy.deepcopy(current_scene_state or {})
    locked = _locked_elements(original)
    proposed_updates = _proposed_updates(new_detail)
    missing = _missing_details(new_detail)
    conflicts = _conflicts(new_detail, locked)
    preserved = [
        {
            "id": item,
            "policy": "preserve_locked_element",
            "lock_strength": lock_strength if lock_strength is not None else 1.0,
        }
        for item in locked
    ]
    updated_preview = copy.deepcopy(original)
    updated_preview["locked_elements"] = locked
    updated_preview["scene_lock_updates"] = proposed_updates
    updated_preview["scene_rebuild_required"] = False
    return {
        "original_scene_state": original,
        "new_detail": new_detail or "",
        "locked_elements": locked,
        "preserved_elements": preserved,
        "proposed_updates": proposed_updates,
        "conflicts": conflicts,
        "missing_details": missing,
        "clarification_question": "Yeni detayi sahnenin hangi konumuna eklemeliyim?" if missing else "",
        "updated_scene_preview": updated_preview,
        "scene_rebuild_required": False,
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only scene lock preview only; locked elements are preserved and no image generation or write action is performed.",
    }
