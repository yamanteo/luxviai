"""Read-only LuxWorkspace evaluator and project context note preview."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Mapping


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


def preview_workspace_context_note(
    context_note: str,
    project_type: str = "",
    current_blocks: List[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    raw_context = context_note or ""
    normalized = _normalize_text(raw_context)
    evaluator_preferences: List[str] = []
    project_constraints: List[str] = []
    grading_risks: List[str] = []
    writing_style_hints: List[str] = []
    source_expectations: List[str] = []
    warnings: List[str] = []
    recommended_workspace_behavior: List[str] = []
    repetition_policy = "standard"
    detail_level = "medium"

    if _contains_any(normalized, ["ayrintili", "detayli", "uzun aciklama", "uzun cevap"]):
        evaluator_preferences.append("Evaluator appears to prefer detailed answers.")
        writing_style_hints.append("Use fuller explanations with clear reasoning and examples.")
        recommended_workspace_behavior.append("Prefer expanded outlines and richer paragraph drafts.")
        detail_level = "high"

    if _contains_any(normalized, ["kisa degil", "kisa istem", "uzun bekliyor"]):
        evaluator_preferences.append("Short answers may be insufficient for this project.")
        writing_style_hints.append("Avoid overly brief sections unless the assignment requires it.")
        recommended_workspace_behavior.append("Ask before shortening substantial sections.")
        detail_level = "high"

    if _contains_any(normalized, ["tekrar", "tekrari", "tekrardan"]) and _contains_any(
        normalized, ["sevmez", "istem", "gorme", "azalt"]
    ):
        evaluator_preferences.append("Evaluator appears sensitive to repetition.")
        repetition_policy = "reduce_repetition"
        writing_style_hints.append("Vary wording and merge repeated claims.")
        recommended_workspace_behavior.append("Flag repeated ideas before draft/export preview.")

    if _contains_any(normalized, ["kaynak", "referans", "citation", "literatur"]):
        source_expectations.append("Sources should be explicit, relevant, and verifiable.")
        grading_risks.append("Missing or weak sources may reduce the grade.")
        recommended_workspace_behavior.append("Highlight claims that need real citations.")
        warnings.append("Do not invent sources; ask for real source material or mark citation gaps.")

    if _contains_any(normalized, ["giris", "baslangic"]) and _contains_any(
        normalized, ["guclu", "etkili", "onemli", "iyi"]
    ):
        project_constraints.append("Introduction should be strong and purposeful.")
        writing_style_hints.append("Open with a clear problem, scope, and direction.")
        recommended_workspace_behavior.append("Prioritize introduction review in workspace previews.")

    if _contains_any(normalized, ["yontem", "metod"]):
        grading_risks.append("Method section may need extra clarity.")
        project_constraints.append("Method section should be concrete and easy to follow.")
        recommended_workspace_behavior.append("Check method steps, assumptions, and limitations.")

    if _contains_any(normalized, ["profesyonel", "akademik", "resmi"]):
        evaluator_preferences.append("Evaluator expects professional or academic language.")
        writing_style_hints.append("Use a formal tone and avoid casual phrasing.")
        recommended_workspace_behavior.append("Prefer academic rewrite suggestions.")

    if not raw_context.strip():
        warnings.append("No context note was provided; ask for the evaluator or project expectation.")
    if not any(
        [
            evaluator_preferences,
            project_constraints,
            grading_risks,
            writing_style_hints,
            source_expectations,
        ]
    ):
        warnings.append("Context is ambiguous; ask a clarification before treating it as an evaluator preference.")

    return {
        "raw_context": raw_context,
        "normalized_context": normalized,
        "project_type": project_type or "",
        "current_block_count": len(list(current_blocks or [])),
        "evaluator_preferences": evaluator_preferences,
        "project_constraints": project_constraints,
        "grading_risks": grading_risks,
        "writing_style_hints": writing_style_hints,
        "source_expectations": source_expectations,
        "repetition_policy": repetition_policy,
        "detail_level": detail_level,
        "recommended_workspace_behavior": recommended_workspace_behavior,
        "warnings": warnings,
        "safe_preview_message": "Bu not sadece bu proje icin gecici context preview olarak yorumlanir; hoca bilgisi uydurulmaz.",
        "read_only": True,
        "memory_write_performed": False,
        "write_performed": False,
        "data_saved": False,
        "db_write_performed": False,
    }
