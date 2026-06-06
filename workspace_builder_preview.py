"""Read-only LuxWorkspace CV/report/presentation builder preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from workspace_context_notes import preview_workspace_context_note


_STRUCTURES = {
    "cv": [
        "kisisel ozet",
        "deneyim",
        "egitim",
        "yetenekler",
        "projeler",
        "iletisim placeholder",
    ],
    "report": [
        "baslik",
        "giris",
        "ana bolumler",
        "yontem/analiz",
        "sonuc",
        "kaynaklar placeholder",
    ],
    "presentation": [
        "kapak",
        "problem",
        "ana fikirler",
        "destekleyici noktalar",
        "sonuc",
        "kapanis",
    ],
    "generic_document": [
        "amac",
        "kapsam",
        "taslak bolumler",
        "eksik bilgiler",
        "sonraki adimlar",
    ],
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


def _detect_builder_type(command: str, content: str) -> str:
    normalized = _normalize_text(f"{command} {content}")
    if "cv" in normalized or "ozgecmis" in normalized:
        return "cv"
    if "sunum" in normalized or "presentation" in normalized or "slayt" in normalized:
        return "presentation"
    if "rapor" in normalized:
        return "report"
    if "odev" in normalized or "tez" in normalized or "makale" in normalized or "belge" in normalized:
        return "generic_document"
    return "unknown"


def _detected_intent(builder_type: str, command: str) -> str:
    normalized = _normalize_text(command)
    if builder_type == "presentation" and ("cevir" in normalized or "donustur" in normalized):
        return "convert_to_presentation"
    if builder_type == "cv":
        return "build_cv_preview"
    if builder_type == "report":
        return "build_report_preview"
    if builder_type == "presentation":
        return "build_presentation_preview"
    if builder_type == "generic_document":
        return "clarify_document_preview"
    return "unknown"


def _recommended_blocks(builder_type: str) -> List[Dict[str, Any]]:
    structure = _STRUCTURES.get(builder_type, [])
    return [
        {
            "type": "section" if index == 0 else "heading",
            "title": item,
            "role": "builder_preview",
            "order": index,
            "exportable": builder_type != "unknown",
            "editable": False,
        }
        for index, item in enumerate(structure)
    ]


def _missing_inputs(builder_type: str, command: str, content: str) -> List[str]:
    missing: List[str] = []
    if builder_type == "cv":
        if not content.strip():
            missing.extend(["deneyim bilgileri", "egitim bilgileri", "yetenekler", "iletisim bilgisi"])
    elif builder_type == "report":
        if not content.strip():
            missing.extend(["konu", "hedef uzunluk", "kaynaklar", "teslim kriterleri"])
    elif builder_type == "presentation":
        if not content.strip():
            missing.extend(["sunum konusu", "hedef kitle", "slayt sayisi", "ana mesaj"])
    elif builder_type == "generic_document":
        missing.extend(["belge turu", "konu", "teslim beklentisi"])
    else:
        missing.append("hangi belge turunun istendigi")
    return missing


def _clarification_question(builder_type: str, missing_inputs: List[str]) -> str:
    if not missing_inputs:
        return ""
    if builder_type == "cv":
        return "CV icin deneyim, egitim ve yetenek bilgilerini paylasir misin?"
    if builder_type == "report":
        return "Raporun konusu, hedef uzunlugu ve kaynak beklentisi nedir?"
    if builder_type == "presentation":
        return "Sunumun hedef kitlesi, slayt sayisi ve ana mesaji nedir?"
    if builder_type == "generic_document":
        return "Bu odevi hangi belge turunde hazirlamaliyim ve konu nedir?"
    return "CV, rapor, sunum veya baska bir belge mi hazirlamak istiyorsun?"


def build_workspace_builder_preview(
    command: str,
    content: str = "",
    context_note: str = "",
    project_type: str = "",
) -> Dict[str, Any]:
    raw_command = command or ""
    builder_type = _detect_builder_type(raw_command, content)
    detected_intent = _detected_intent(builder_type, raw_command)
    suggested_structure = list(_STRUCTURES.get(builder_type, []))
    missing_inputs = _missing_inputs(builder_type, raw_command, content)
    context_preview = preview_workspace_context_note(context_note, project_type) if context_note.strip() else {}
    context_influence = {
        "used": bool(context_preview),
        "detail_level": context_preview.get("detail_level", "medium") if context_preview else "medium",
        "repetition_policy": context_preview.get("repetition_policy", "standard") if context_preview else "standard",
        "writing_style_hints": context_preview.get("writing_style_hints", []) if context_preview else [],
        "source_expectations": context_preview.get("source_expectations", []) if context_preview else [],
        "warnings": context_preview.get("warnings", []) if context_preview else [],
    }
    warnings = list(context_influence["warnings"])
    if builder_type == "report" and "kaynaklar placeholder" in suggested_structure:
        warnings.append("Kaynak gerekiyorsa kaynak uydurma; gercek kaynak veya citation gap kullan.")

    return {
        "raw_command": raw_command,
        "builder_type": builder_type,
        "detected_intent": detected_intent,
        "suggested_structure": suggested_structure,
        "recommended_blocks": _recommended_blocks(builder_type),
        "missing_inputs": missing_inputs,
        "clarification_question": _clarification_question(builder_type, missing_inputs),
        "context_influence": context_influence,
        "warnings": warnings,
        "export_ready": False,
        "read_only": True,
        "file_written": False,
        "export_performed": False,
        "write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "safety_note": "Builder preview only; no document, PDF, Word, PPT, file, DB, or memory write is performed.",
    }
