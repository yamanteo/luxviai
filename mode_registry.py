"""Command-first mode registry preview scaffold."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any, Dict, List, Sequence


def _mode(
    id_: str,
    *,
    display_name: str,
    aliases: List[str],
    trigger_phrases: List[str],
    category: str,
    short_description: str,
    safety_note: str,
    requires_permission: bool,
) -> Dict[str, Any]:
    return {
        "id": id_,
        "display_name": display_name,
        "aliases": aliases,
        "trigger_phrases": trigger_phrases,
        "category": category,
        "short_description": short_description,
        "safety_note": safety_note,
        "is_read_only_preview": True,
        "requires_permission": requires_permission,
        "status": "scaffold",
    }


MODE_REGISTRY: List[Dict[str, Any]] = [
    _mode(
        "luxeph",
        display_name="Luxeph",
        aliases=["luxeph", "lux eph", "luks eph"],
        trigger_phrases=["luxeph'e gec", "luxeph modu", "luxeph baslat"],
        category="personal_reflection",
        short_description="Reflective emotional/inner-state mode preview.",
        safety_note="Read-only preview; no diagnosis, storage, or sensitive memory write.",
        requires_permission=False,
    ),
    _mode(
        "luxworkspace",
        display_name="LuxWorkspace",
        aliases=["luxworkspace", "workspace", "calisma alani", "dosya duzenle"],
        trigger_phrases=["calisma alani ac", "workspace modu", "dosya duzenle", "proje calis"],
        category="workspace",
        short_description="Workspace planning and file-adjacent help preview.",
        safety_note="No file read/write, move, delete, or external action is performed.",
        requires_permission=True,
    ),
    _mode(
        "dream_scene",
        display_name="Dream Scene",
        aliases=["dream scene", "ruya", "ruya sahnesi", "dream"],
        trigger_phrases=["ruyami gorsele cevir", "ruyami gorsellestir", "ruya sahnesi kur", "dream scene"],
        category="visual_memory",
        short_description="Dream-scene visual state preview.",
        safety_note="No image generation or memory write happens in this preview.",
        requires_permission=False,
    ),
    _mode(
        "lux_ambrosia",
        display_name="Lux Ambrosia",
        aliases=["ambrosia", "lux ambrosia"],
        trigger_phrases=["lux ambrosia olarak gorsellestir", "ambrosia modu", "ambrosia hissi"],
        category="visual_memory",
        short_description="Ambrosia emotional visual texture preview.",
        safety_note="Visual system preview only; no raw emotional data is stored.",
        requires_permission=False,
    ),
    _mode(
        "cv_builder",
        display_name="CV Builder",
        aliases=["cv", "cv builder", "ozgecmis", "resume"],
        trigger_phrases=["cv hazirla", "cv duzenle", "profesyonel cv", "ozgecmis hazirla"],
        category="document_builder",
        short_description="CV planning and builder route preview.",
        safety_note="No document file is created or edited without explicit user action.",
        requires_permission=False,
    ),
    _mode(
        "life_rehearsal",
        display_name="Life Rehearsal / Yasam Provasi",
        aliases=["life rehearsal", "yasam provasi", "prova"],
        trigger_phrases=["yasam provasi yap", "hayati prova edelim", "senaryo prova", "life rehearsal"],
        category="planning",
        short_description="Future scenario rehearsal preview.",
        safety_note="Advice is preview-only and should not replace professional judgment.",
        requires_permission=False,
    ),
    _mode(
        "social_radar",
        display_name="Social Radar",
        aliases=["social radar", "sosyal radar", "iliski radari"],
        trigger_phrases=["sosyal radar", "mesaji analiz et", "iliski sinyali", "sosyal ipucu"],
        category="social_context",
        short_description="Social signal interpretation preview.",
        safety_note="No private messages are read; user-provided text only.",
        requires_permission=True,
    ),
    _mode(
        "night_radio",
        display_name="Night Radio / Gece Radyosu",
        aliases=["night radio", "gece radyosu", "gece radyo"],
        trigger_phrases=["gece radyosu modu", "night radio", "gece sesi", "gece modu ac"],
        category="ambient",
        short_description="Night-radio style reflective response preview.",
        safety_note="No audio playback, recording, or analysis is performed.",
        requires_permission=False,
    ),
    _mode(
        "one_step",
        display_name="One Step / Tek Adim",
        aliases=["one step", "tek adim", "bir adim"],
        trigger_phrases=["tek adim soyle", "bir sonraki adim", "one step", "sadece tek adim"],
        category="focus",
        short_description="Single next-step focus preview.",
        safety_note="No task is executed; only a suggested next step is previewed.",
        requires_permission=False,
    ),
    _mode(
        "codex_mode",
        display_name="Codex Mode",
        aliases=["codex", "codex mode", "kod modu"],
        trigger_phrases=["codex modu", "kod yaz", "repo ile calis", "debug et"],
        category="coding",
        short_description="Coding-agent mode preview.",
        safety_note="No file change or command execution is performed by this preview.",
        requires_permission=True,
    ),
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


def _find_match(normalized_command: str, values: Sequence[str]) -> str:
    for value in values:
        normalized_value = _normalize_text(value)
        if normalized_value and normalized_value in normalized_command:
            return value
    return ""


def mode_registry() -> List[Dict[str, Any]]:
    return [dict(item) for item in MODE_REGISTRY]


def preview_mode_command(command_text: str) -> Dict[str, Any]:
    normalized = _normalize_text(command_text)
    candidates: List[Dict[str, Any]] = []

    for mode in mode_registry():
        matched_trigger = _find_match(normalized, mode.get("trigger_phrases", []))
        matched_alias = _find_match(normalized, mode.get("aliases", []))
        if not matched_trigger and not matched_alias:
            continue
        confidence = "high" if matched_trigger else "medium"
        candidates.append(
            {
                "mode": mode,
                "confidence": confidence,
                "matched_alias": matched_alias,
                "matched_trigger": matched_trigger,
                "reason": f"Matched {matched_trigger or matched_alias} against command-first mode registry.",
                "read_only": True,
            }
        )

    candidates.sort(key=lambda item: {"high": 2, "medium": 1, "low": 0}.get(str(item.get("confidence")), 0), reverse=True)
    primary = candidates[0] if candidates else None
    return {
        "preview_id": str(uuid.uuid4()),
        "command_text": command_text,
        "matched_modes": candidates,
        "primary_mode": primary,
        "confidence": primary.get("confidence") if primary else "low",
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "can_execute_now": False,
        "reason": "Mode candidates are preview-only; no real mode switch, persistence, or agent action was performed.",
    }
