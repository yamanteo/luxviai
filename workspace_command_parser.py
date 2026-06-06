"""Read-only LuxWorkspace command parser scaffold."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Mapping


_BLOCK_ALIASES = {
    "paragraf": "paragraph",
    "paragraph": "paragraph",
    "bolum": "section",
    "section": "section",
    "baslik": "heading",
    "heading": "heading",
    "slayt": "slide",
    "slide": "slide",
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


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _target_hint(normalized: str) -> Dict[str, str]:
    numbered = re.search(
        r"\b(\d+)\.?\s*(paragraf|paragraph|bolum|section|baslik|heading|slayt|slide)"
        r"(?:i|a|e|u|un|in|ini|yi|ye|ya)?\b",
        normalized,
    )
    if numbered:
        number, label = numbered.groups()
        block_type = _BLOCK_ALIASES.get(label, "unknown")
        return {
            "target_block_hint": f"{block_type} {number}",
            "target_block_type": block_type,
        }
    if "iki paragraf aras" in normalized or "paragraf aras" in normalized:
        return {
            "target_block_hint": "between adjacent paragraphs",
            "target_block_type": "paragraph",
        }
    if _contains_any(normalized, ["bu kisim", "bu bolum", "bu metin", "secilen", "secili"]):
        return {
            "target_block_hint": "selected content",
            "target_block_type": "section",
        }
    if "giris" in normalized:
        return {
            "target_block_hint": "introduction section",
            "target_block_type": "section",
        }
    return {
        "target_block_hint": "",
        "target_block_type": "",
    }


def _intent_and_operation(normalized: str) -> Dict[str, str]:
    if "cv" in normalized or "ozgecmis" in normalized:
        return {"workspace_intent": "create_cv", "operation": "create"}
    if "sunum" in normalized or "presentation" in normalized:
        return {"workspace_intent": "create_presentation", "operation": "convert"}
    if "rapor" in normalized and _contains_any(normalized, ["yaz", "hazirla", "olustur", "cevir"]):
        return {"workspace_intent": "create_report", "operation": "create"}
    if _contains_any(normalized, ["gecis cumlesi", "gecis metni"]) or (
        "arasina" in normalized and "ekle" in normalized
    ):
        return {"workspace_intent": "add_transition", "operation": "insert"}
    if "sonuc" in normalized and _contains_any(normalized, ["uygun", "cevir", "hale getir"]):
        return {"workspace_intent": "convert_to_result_section", "operation": "convert"}
    if _contains_any(normalized, ["akademik", "akademiklestir"]):
        return {"workspace_intent": "academic_rewrite", "operation": "rewrite"}
    if _contains_any(normalized, ["kisalt", "kisa yap", "ozetle"]):
        return {"workspace_intent": "shorten", "operation": "shorten"}
    if _contains_any(normalized, ["genislet", "uzat", "detaylandir"]):
        return {"workspace_intent": "expand", "operation": "expand"}
    if _contains_any(normalized, ["profesyonel", "kurumsal"]):
        return {"workspace_intent": "professionalize", "operation": "rewrite"}
    if _contains_any(normalized, ["sadelestir", "basitlestir", "anlasilir"]):
        return {"workspace_intent": "simplify", "operation": "rewrite"}
    if _contains_any(normalized, ["duzenle", "degistir", "yeniden yaz"]):
        return {"workspace_intent": "edit_paragraph", "operation": "rewrite"}
    return {"workspace_intent": "unknown", "operation": "ask_clarification"}


def _destination_hint(normalized: str, workspace_intent: str) -> str:
    if workspace_intent == "create_cv":
        return "cv_document"
    if workspace_intent == "create_report":
        return "report_document"
    if workspace_intent == "create_presentation":
        return "presentation_outline"
    if workspace_intent == "convert_to_result_section" or "sonuc" in normalized:
        return "result_section"
    if workspace_intent == "add_transition":
        return "between_paragraphs"
    return ""


def _clarification(
    workspace_intent: str,
    target_block_hint: str,
    current_blocks: List[Mapping[str, Any]],
) -> Dict[str, Any]:
    if workspace_intent == "unknown":
        return {
            "ambiguity_level": "high",
            "needs_clarification": True,
            "clarification_question": "LuxWorkspace icinde hangi belge veya blok islemini yapmak istedigini biraz acar misin?",
        }
    if workspace_intent in {"shorten", "expand", "simplify", "professionalize"} and not target_block_hint:
        if not current_blocks:
            return {
                "ambiguity_level": "high",
                "needs_clarification": True,
                "clarification_question": "Hangi bolum veya paragraf uzerinde calisayim?",
            }
        return {
            "ambiguity_level": "medium",
            "needs_clarification": True,
            "clarification_question": "Mevcut bloklardan hangisini hedef almaliyim?",
        }
    if workspace_intent in {"create_cv", "create_report", "create_presentation"}:
        return {
            "ambiguity_level": "low",
            "needs_clarification": False,
            "clarification_question": "",
        }
    return {
        "ambiguity_level": "low" if target_block_hint else "medium",
        "needs_clarification": False,
        "clarification_question": "",
    }


def parse_workspace_command(command: str, current_blocks: List[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    raw_command = command or ""
    normalized = _normalize_text(raw_command)
    blocks = list(current_blocks or [])
    target = _target_hint(normalized)
    intent = _intent_and_operation(normalized)
    destination_hint = _destination_hint(normalized, intent["workspace_intent"])
    clarification = _clarification(intent["workspace_intent"], target["target_block_hint"], blocks)
    if clarification["needs_clarification"] and intent["operation"] == "ask_clarification":
        operation = "ask_clarification"
    else:
        operation = intent["operation"]
    return {
        "raw_command": raw_command,
        "normalized_command": normalized,
        "workspace_intent": intent["workspace_intent"],
        "target_block_hint": target["target_block_hint"],
        "target_block_type": target["target_block_type"],
        "operation": operation,
        "destination_hint": destination_hint,
        "ambiguity_level": clarification["ambiguity_level"],
        "needs_clarification": clarification["needs_clarification"],
        "clarification_question": clarification["clarification_question"],
        "safe_preview_message": "Bu sadece command parser onizlemesidir; blok guncelleme, export veya dosya yazma yapilmaz.",
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "block_update_performed": False,
        "file_created": False,
        "export_performed": False,
    }
