from __future__ import annotations

import unicodedata
from typing import Any, Dict, List

from layer22_future_candidates import ALIASES, FUTURE_CANDIDATES


SCORING_DIMENSIONS = [
    "practicality_score",
    "daily_use_score",
    "premium_identity_score",
    "wow_factor_score",
    "marketing_demo_score",
    "technical_complexity_score",
    "privacy_risk_score",
    "safety_risk_score",
    "dependency_score",
    "scaffold_readiness_score",
    "first_build_priority_score",
]


BASE_SCORES: Dict[str, Dict[str, int]] = {
    "lux_time_twin": {
        "practicality_score": 9,
        "daily_use_score": 9,
        "premium_identity_score": 9,
        "wow_factor_score": 8,
        "marketing_demo_score": 9,
        "technical_complexity_score": 8,
        "privacy_risk_score": 7,
        "safety_risk_score": 5,
        "dependency_score": 8,
        "scaffold_readiness_score": 5,
    },
    "future_self_council": {
        "practicality_score": 6,
        "daily_use_score": 5,
        "premium_identity_score": 8,
        "wow_factor_score": 7,
        "marketing_demo_score": 6,
        "technical_complexity_score": 4,
        "privacy_risk_score": 5,
        "safety_risk_score": 5,
        "dependency_score": 4,
        "scaffold_readiness_score": 7,
    },
    "reality_layer": {
        "practicality_score": 8,
        "daily_use_score": 8,
        "premium_identity_score": 7,
        "wow_factor_score": 5,
        "marketing_demo_score": 6,
        "technical_complexity_score": 4,
        "privacy_risk_score": 3,
        "safety_risk_score": 2,
        "dependency_score": 3,
        "scaffold_readiness_score": 9,
    },
    "memory_cinema": {
        "practicality_score": 6,
        "daily_use_score": 4,
        "premium_identity_score": 9,
        "wow_factor_score": 10,
        "marketing_demo_score": 9,
        "technical_complexity_score": 9,
        "privacy_risk_score": 9,
        "safety_risk_score": 6,
        "dependency_score": 9,
        "scaffold_readiness_score": 3,
    },
    "cognitive_mirror": {
        "practicality_score": 6,
        "daily_use_score": 5,
        "premium_identity_score": 8,
        "wow_factor_score": 6,
        "marketing_demo_score": 6,
        "technical_complexity_score": 5,
        "privacy_risk_score": 6,
        "safety_risk_score": 5,
        "dependency_score": 5,
        "scaffold_readiness_score": 6,
    },
    "dream_os": {
        "practicality_score": 5,
        "daily_use_score": 4,
        "premium_identity_score": 9,
        "wow_factor_score": 9,
        "marketing_demo_score": 8,
        "technical_complexity_score": 6,
        "privacy_risk_score": 5,
        "safety_risk_score": 5,
        "dependency_score": 5,
        "scaffold_readiness_score": 7,
    },
    "personal_mythology": {
        "practicality_score": 4,
        "daily_use_score": 3,
        "premium_identity_score": 9,
        "wow_factor_score": 8,
        "marketing_demo_score": 7,
        "technical_complexity_score": 6,
        "privacy_risk_score": 7,
        "safety_risk_score": 6,
        "dependency_score": 6,
        "scaffold_readiness_score": 4,
    },
    "adaptive_interface": {
        "practicality_score": 9,
        "daily_use_score": 9,
        "premium_identity_score": 8,
        "wow_factor_score": 6,
        "marketing_demo_score": 7,
        "technical_complexity_score": 5,
        "privacy_risk_score": 2,
        "safety_risk_score": 2,
        "dependency_score": 3,
        "scaffold_readiness_score": 9,
    },
    "silent_companion_mode": {
        "practicality_score": 8,
        "daily_use_score": 8,
        "premium_identity_score": 9,
        "wow_factor_score": 6,
        "marketing_demo_score": 7,
        "technical_complexity_score": 3,
        "privacy_risk_score": 3,
        "safety_risk_score": 2,
        "dependency_score": 2,
        "scaffold_readiness_score": 9,
    },
    "personal_world_model": {
        "practicality_score": 8,
        "daily_use_score": 8,
        "premium_identity_score": 10,
        "wow_factor_score": 9,
        "marketing_demo_score": 8,
        "technical_complexity_score": 10,
        "privacy_risk_score": 10,
        "safety_risk_score": 7,
        "dependency_score": 10,
        "scaffold_readiness_score": 2,
    },
    "emotional_weather": {
        "practicality_score": 7,
        "daily_use_score": 8,
        "premium_identity_score": 8,
        "wow_factor_score": 6,
        "marketing_demo_score": 7,
        "technical_complexity_score": 4,
        "privacy_risk_score": 5,
        "safety_risk_score": 4,
        "dependency_score": 4,
        "scaffold_readiness_score": 8,
    },
    "ambient_workspace": {
        "practicality_score": 9,
        "daily_use_score": 9,
        "premium_identity_score": 8,
        "wow_factor_score": 6,
        "marketing_demo_score": 7,
        "technical_complexity_score": 5,
        "privacy_risk_score": 3,
        "safety_risk_score": 2,
        "dependency_score": 3,
        "scaffold_readiness_score": 9,
    },
    "memory_sculpting": {
        "practicality_score": 7,
        "daily_use_score": 5,
        "premium_identity_score": 9,
        "wow_factor_score": 8,
        "marketing_demo_score": 8,
        "technical_complexity_score": 8,
        "privacy_risk_score": 9,
        "safety_risk_score": 6,
        "dependency_score": 8,
        "scaffold_readiness_score": 4,
    },
    "intention_timeline": {
        "practicality_score": 8,
        "daily_use_score": 8,
        "premium_identity_score": 8,
        "wow_factor_score": 6,
        "marketing_demo_score": 7,
        "technical_complexity_score": 4,
        "privacy_risk_score": 4,
        "safety_risk_score": 3,
        "dependency_score": 4,
        "scaffold_readiness_score": 8,
    },
    "autonomy_dial": {
        "practicality_score": 8,
        "daily_use_score": 7,
        "premium_identity_score": 9,
        "wow_factor_score": 7,
        "marketing_demo_score": 8,
        "technical_complexity_score": 5,
        "privacy_risk_score": 4,
        "safety_risk_score": 7,
        "dependency_score": 4,
        "scaffold_readiness_score": 8,
    },
    "ethical_boundary_soul": {
        "practicality_score": 7,
        "daily_use_score": 6,
        "premium_identity_score": 10,
        "wow_factor_score": 7,
        "marketing_demo_score": 7,
        "technical_complexity_score": 4,
        "privacy_risk_score": 3,
        "safety_risk_score": 3,
        "dependency_score": 3,
        "scaffold_readiness_score": 9,
    },
    "invisible_operator": {
        "practicality_score": 9,
        "daily_use_score": 8,
        "premium_identity_score": 9,
        "wow_factor_score": 9,
        "marketing_demo_score": 9,
        "technical_complexity_score": 9,
        "privacy_risk_score": 8,
        "safety_risk_score": 9,
        "dependency_score": 9,
        "scaffold_readiness_score": 3,
    },
    "context_rooms": {
        "practicality_score": 7,
        "daily_use_score": 7,
        "premium_identity_score": 8,
        "wow_factor_score": 7,
        "marketing_demo_score": 7,
        "technical_complexity_score": 6,
        "privacy_risk_score": 5,
        "safety_risk_score": 3,
        "dependency_score": 5,
        "scaffold_readiness_score": 7,
    },
    "aura_system": {
        "practicality_score": 7,
        "daily_use_score": 7,
        "premium_identity_score": 10,
        "wow_factor_score": 9,
        "marketing_demo_score": 9,
        "technical_complexity_score": 6,
        "privacy_risk_score": 4,
        "safety_risk_score": 3,
        "dependency_score": 5,
        "scaffold_readiness_score": 7,
    },
    "finality_sense": {
        "practicality_score": 10,
        "daily_use_score": 9,
        "premium_identity_score": 8,
        "wow_factor_score": 5,
        "marketing_demo_score": 7,
        "technical_complexity_score": 3,
        "privacy_risk_score": 2,
        "safety_risk_score": 2,
        "dependency_score": 2,
        "scaffold_readiness_score": 10,
    },
}


TEXT_FIELDS: Dict[str, Dict[str, Any]] = {
    "lux_time_twin": {
        "strengths": ["High daily planning value", "Strong premium personal-agent identity"],
        "concerns": ["Needs calendar/energy/memory boundaries before real use", "Not ideal as first real build"],
        "best_use_case": "Future-facing weekly planning preview.",
        "demo_phrase": "Lux shows how your week may feel before you overcommit.",
        "safest_first_scaffold": "Read-only simulated week and energy planning card.",
    },
    "future_self_council": {
        "strengths": ["Easy to scaffold", "Good reflective decision support"],
        "concerns": ["Must avoid therapy framing", "Lower daily utility than workspace-focused ideas"],
        "best_use_case": "Decision reflection with multiple future perspectives.",
        "demo_phrase": "Ask three possible future selves before choosing.",
        "safest_first_scaffold": "Perspective preview with clear non-clinical language.",
    },
    "reality_layer": {
        "strengths": ["Practical and low risk", "Prevents unrealistic planning"],
        "concerns": ["Needs user-provided context to avoid invented facts"],
        "best_use_case": "Constraint-aware plan check.",
        "demo_phrase": "Lux checks whether the plan fits your actual time and energy.",
        "safest_first_scaffold": "User-input-only reality check preview.",
    },
    "memory_cinema": {
        "strengths": ["Very high wow and demo value", "Distinctive memory experience"],
        "concerns": ["High privacy risk", "Needs memory policy and retrieval controls first"],
        "best_use_case": "Safe project recap experience.",
        "demo_phrase": "Walk through a project memory like a calm film.",
        "safest_first_scaffold": "Sample-only cinematic recap with no real memory retrieval.",
    },
    "cognitive_mirror": {
        "strengths": ["Supports meta intelligence", "Useful for work pattern reflection"],
        "concerns": ["Must avoid personality or clinical claims"],
        "best_use_case": "Output and decision-pattern reflection.",
        "demo_phrase": "Lux reflects how this work pattern is forming.",
        "safest_first_scaffold": "Draft-output quality reflection only.",
    },
    "dream_os": {
        "strengths": ["Strong visual identity", "High creative appeal"],
        "concerns": ["Must stay creative, not therapeutic"],
        "best_use_case": "Dream-to-scene creative system.",
        "demo_phrase": "Turn a dream into a visual state without losing the feeling.",
        "safest_first_scaffold": "Read-only dream scene prompt structure.",
    },
    "personal_mythology": {
        "strengths": ["Premium identity layer", "High originality"],
        "concerns": ["Identity manipulation risk", "Not a first-build practical tool"],
        "best_use_case": "Theme and symbol organization.",
        "demo_phrase": "Lux names the recurring symbols in your creative world.",
        "safest_first_scaffold": "Symbol naming preview with no identity claims.",
    },
    "adaptive_interface": {
        "strengths": ["High practical value", "Low risk", "Strong az tus cok is fit"],
        "concerns": ["Real UI changes should come after preview validation"],
        "best_use_case": "Context-aware simplified controls.",
        "demo_phrase": "Lux shows fewer controls when you are tired, more when you are building.",
        "safest_first_scaffold": "Read-only UI state recommendation.",
    },
    "silent_companion_mode": {
        "strengths": ["Easy first scaffold", "Premium calm experience"],
        "concerns": ["Must avoid hidden monitoring"],
        "best_use_case": "Low-noise support and one-line nudges.",
        "demo_phrase": "Lux helps without talking over you.",
        "safest_first_scaffold": "Manual quiet-mode response style preview.",
    },
    "personal_world_model": {
        "strengths": ["Huge long-term value", "Central personal-agent concept"],
        "concerns": ["Highest privacy/dependency risk", "Needs explicit memory policy first"],
        "best_use_case": "Permissioned personal context map.",
        "demo_phrase": "Lux understands your world, only where you explicitly allow it.",
        "safest_first_scaffold": "No real memory; only schema and permission preview.",
    },
    "emotional_weather": {
        "strengths": ["Daily check-in value", "Good premium emotional surface"],
        "concerns": ["No diagnosis or stored raw emotional history"],
        "best_use_case": "Gentle energy and mood preview.",
        "demo_phrase": "Lux shows the day as emotional weather, not a diagnosis.",
        "safest_first_scaffold": "User-described energy signal card.",
    },
    "ambient_workspace": {
        "strengths": ["Very practical", "Low risk", "Strong workspace fit"],
        "concerns": ["Real editor/export changes should wait"],
        "best_use_case": "Contextual workspace tools and clutter reduction.",
        "demo_phrase": "Lux quietly brings the next useful tool into the workspace.",
        "safest_first_scaffold": "Read-only workspace next-tool preview.",
    },
    "memory_sculpting": {
        "strengths": ["Strong trust feature", "Useful for privacy control"],
        "concerns": ["Real memory write/delete must wait for policy and confirmation"],
        "best_use_case": "Memory retention rule planning.",
        "demo_phrase": "You decide what Lux remembers, summarizes, or never stores.",
        "safest_first_scaffold": "Memory policy card with no real memory operations.",
    },
    "intention_timeline": {
        "strengths": ["Practical planning value", "Good scaffold readiness"],
        "concerns": ["No real calendar/task write in early build"],
        "best_use_case": "Visible intention and decision timeline.",
        "demo_phrase": "Lux separates ideas, intentions, and commitments.",
        "safest_first_scaffold": "Read-only timeline preview from user input.",
    },
    "autonomy_dial": {
        "strengths": ["Important safety-control concept", "Strong premium trust signal"],
        "concerns": ["Must not enable real autonomy yet"],
        "best_use_case": "Visible agent permission levels.",
        "demo_phrase": "You set exactly how much Lux may do on its own.",
        "safest_first_scaffold": "Permission-level preview only.",
    },
    "ethical_boundary_soul": {
        "strengths": ["Trust-forward identity", "Low implementation risk"],
        "concerns": ["Must be policy-aligned, not vague branding"],
        "best_use_case": "Readable privacy/safety boundary behavior.",
        "demo_phrase": "Lux's boundaries feel like part of its character.",
        "safest_first_scaffold": "Boundary explanation and refusal style preview.",
    },
    "invisible_operator": {
        "strengths": ["High practical and marketing value", "Strong personal-agent vision"],
        "concerns": ["High safety risk if mistaken for real background action"],
        "best_use_case": "Prepared drafts and checklists before action.",
        "demo_phrase": "Lux prepares the next step without crossing the line.",
        "safest_first_scaffold": "Non-executing preparation preview only.",
    },
    "context_rooms": {
        "strengths": ["Good context clarity", "Premium organization feel"],
        "concerns": ["No real cross-page/history retrieval early"],
        "best_use_case": "Project and mode context separation.",
        "demo_phrase": "Lux keeps each project in the right room.",
        "safest_first_scaffold": "Manual context-room card preview.",
    },
    "aura_system": {
        "strengths": ["Very strong premium identity", "High demo appeal"],
        "concerns": ["Real UI/audio/theme changes are later integrations"],
        "best_use_case": "Mode-based visual/voice/tone atmosphere.",
        "demo_phrase": "Lux changes the feeling of the room without clutter.",
        "safest_first_scaffold": "Read-only aura recommendation preview.",
    },
    "finality_sense": {
        "strengths": ["Highest practical close-out value", "Low risk", "Excellent first scaffold"],
        "concerns": ["Should not perform real export/task completion automatically"],
        "best_use_case": "Done/missing/needs-review decision support.",
        "demo_phrase": "Lux tells you whether this is actually finished.",
        "safest_first_scaffold": "Completion checklist preview.",
    },
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("ı", "i")


def _priority_score(scores: Dict[str, int]) -> int:
    positive = (
        scores["practicality_score"] * 1.4
        + scores["daily_use_score"] * 1.2
        + scores["premium_identity_score"] * 1.1
        + scores["marketing_demo_score"] * 0.8
        + scores["scaffold_readiness_score"] * 1.5
    )
    negative = (
        scores["technical_complexity_score"] * 0.9
        + scores["privacy_risk_score"] * 1.0
        + scores["safety_risk_score"] * 0.9
        + scores["dependency_score"] * 0.7
    )
    return max(0, min(10, round((positive - negative) / 3.2)))


def _stage_for(scores: Dict[str, int]) -> str:
    if scores["privacy_risk_score"] >= 8 or scores["safety_risk_score"] >= 8:
        return "high_risk_requires_policy_first"
    if scores["first_build_priority_score"] >= 8:
        return "immediate_preview_candidate"
    if scores["first_build_priority_score"] >= 6:
        return "near_future_candidate"
    if scores["premium_identity_score"] >= 9 and scores["practicality_score"] <= 5:
        return "identity_candidate_not_first_build"
    return "later_candidate"


def _score_item(candidate: Dict[str, Any]) -> Dict[str, Any]:
    scores = dict(BASE_SCORES[candidate["id"]])
    scores["first_build_priority_score"] = _priority_score(scores)
    text = TEXT_FIELDS[candidate["id"]]
    return {
        "id": candidate["id"],
        "name": candidate["name"],
        "category": candidate["category"],
        "scores": scores,
        "strengths": text["strengths"],
        "concerns": text["concerns"],
        "best_use_case": text["best_use_case"],
        "demo_phrase": text["demo_phrase"],
        "safest_first_scaffold": text["safest_first_scaffold"],
        "recommended_stage": _stage_for(scores),
        "required_layers": candidate.get("required_existing_layers", []),
        "read_only": True,
    }


def candidate_scoring_matrix() -> Dict[str, Any]:
    items = [_score_item(candidate) for candidate in FUTURE_CANDIDATES]
    return {
        "layer": "22.2",
        "name": "Candidate scoring / practical priority matrix",
        "status": "scoring_matrix_ready",
        "scoring_dimensions": SCORING_DIMENSIONS,
        "candidate_count": len(items),
        "items": items,
        "read_only": True,
        "real_action_enabled": False,
    }


def _find_item(command: str, candidate_id: str = "") -> Dict[str, Any] | None:
    matrix = candidate_scoring_matrix()["items"]
    if candidate_id:
        wanted = _normalize(candidate_id)
        for item in matrix:
            if _normalize(item["id"]) == wanted or _normalize(item["name"]) == wanted:
                return item
    normalized = _normalize(command)
    for item in matrix:
        if _normalize(item["name"]) in normalized or item["id"] in normalized:
            return item
        for alias in ALIASES.get(item["id"], []):
            if _normalize(alias) in normalized:
                return item
    return None


def _detect_focus(command: str, focus: str = "") -> str:
    if focus:
        return _normalize(focus)
    normalized = _normalize(command)
    if any(key in normalized for key in ["reklam", "demo", "marketing"]):
        return "marketing"
    if any(key in normalized for key in ["ozel", "kimlik", "premium"]):
        return "premium_identity"
    if any(key in normalized for key in ["guvenli", "safest", "hizli", "fastest"]):
        return "safest"
    if any(key in normalized for key in ["risk", "riskli", "privacy", "gizlilik"]):
        return "privacy_review"
    if any(key in normalized for key in ["ilk", "scaffold", "mantikli", "uc", "3"]):
        return "fastest_scaffold"
    if any(key in normalized for key in ["long", "vizyon", "gelecek"]):
        return "long_term_vision"
    if any(key in normalized for key in ["pratik", "gunluk", "kolay"]):
        return "practical"
    return "balanced"


def _sort_key_for_focus(item: Dict[str, Any], focus: str) -> tuple:
    scores = item["scores"]
    if focus == "practical":
        return (scores["practicality_score"], scores["daily_use_score"], scores["first_build_priority_score"])
    if focus == "marketing":
        return (scores["marketing_demo_score"], scores["wow_factor_score"], scores["premium_identity_score"])
    if focus == "premium_identity":
        return (scores["premium_identity_score"], scores["wow_factor_score"], scores["marketing_demo_score"])
    if focus in {"safest", "fastest_scaffold"}:
        return (
            scores["scaffold_readiness_score"],
            scores["first_build_priority_score"],
            -scores["privacy_risk_score"],
            -scores["safety_risk_score"],
        )
    if focus == "privacy_review":
        return (scores["privacy_risk_score"], scores["safety_risk_score"], scores["technical_complexity_score"])
    if focus == "long_term_vision":
        return (scores["premium_identity_score"], scores["wow_factor_score"], scores["practicality_score"])
    return (scores["first_build_priority_score"], scores["practicality_score"], scores["premium_identity_score"])


def _ranking_for_focus(items: List[Dict[str, Any]], focus: str) -> List[Dict[str, Any]]:
    reverse = True
    ranked = sorted(items, key=lambda item: _sort_key_for_focus(item, focus), reverse=reverse)
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "recommended_stage": item["recommended_stage"],
            "scores": item["scores"],
            "reason": item["safest_first_scaffold"] if focus in {"safest", "fastest_scaffold"} else item["demo_phrase"],
        }
        for item in ranked
    ]


def preview_candidate_score(
    command: str,
    candidate_id: str = "",
    focus: str = "",
    risk_tolerance: str = "",
    implementation_goal: str = "",
) -> Dict[str, Any]:
    matrix = candidate_scoring_matrix()
    items = matrix["items"]
    detected_focus = _detect_focus(command, focus)
    matched = _find_item(command, candidate_id)
    ranking = _ranking_for_focus(items, detected_focus)
    high_risk = [
        item for item in items
        if item["scores"]["privacy_risk_score"] >= 8 or item["scores"]["safety_risk_score"] >= 7
    ]
    safest = [
        item for item in _ranking_for_focus(items, "safest")
        if item["scores"]["privacy_risk_score"] <= 4 and item["scores"]["safety_risk_score"] <= 3
    ][:5]
    first_build = [
        item for item in _ranking_for_focus(items, "fastest_scaffold")
        if item["recommended_stage"] == "immediate_preview_candidate"
    ][:3]
    if not first_build:
        first_build = _ranking_for_focus(items, "fastest_scaffold")[:3]

    return {
        "raw_command": command,
        "focus": detected_focus,
        "matched_candidate": matched,
        "ranking": ranking[:10],
        "top_candidates": ranking[:5],
        "high_risk_candidates": [
            {
                "id": item["id"],
                "name": item["name"],
                "privacy_risk_score": item["scores"]["privacy_risk_score"],
                "safety_risk_score": item["scores"]["safety_risk_score"],
                "concerns": item["concerns"],
                "policy_note": "Policy/scaffold boundary should come before real implementation.",
            }
            for item in high_risk
        ],
        "safest_candidates": safest,
        "recommended_first_build": first_build,
        "reasoning_summary": (
            "Preview ranking weighs practicality, daily use, Lux identity, demo value, and scaffold readiness, "
            "then lowers priority for privacy risk, safety risk, technical complexity, and dependencies."
        ),
        "safety_boundary": (
            "Scoring is read-only and internal-preview only; it does not start a real feature, access memory, "
            "control devices, create files, export, send, print, or write to DB."
        ),
        "input_context": {
            "risk_tolerance": risk_tolerance or "not_applied_preview_only",
            "implementation_goal": implementation_goal or "scoring_preview_only",
        },
        "real_action_enabled": False,
        "action_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_created": False,
        "export_performed": False,
        "device_control_performed": False,
        "read_only": True,
    }


def layer22_scoring_status() -> Dict[str, Any]:
    matrix = candidate_scoring_matrix()
    return {
        "layer": "22.2",
        "name": "Candidate scoring / practical priority matrix",
        "status": "scoring_matrix_ready",
        "read_only": True,
        "candidate_count": matrix["candidate_count"],
        "available_endpoints": [
            "GET /future/scoring-matrix",
            "POST /future/score-preview",
            "GET /debug/layer22-scoring-status",
        ],
        "recommended_first_build": preview_candidate_score("ilk scaffold icin en mantikli uc fikri sec")["recommended_first_build"],
        "safety_boundaries": {
            "real_action_enabled": False,
            "action_performed": False,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_created": False,
            "export_performed": False,
            "device_control_performed": False,
            "chat_stream_touched": False,
            "typewriter_runtime_touched": False,
        },
        "backlog": ["stop/durdur final block leak"],
    }
