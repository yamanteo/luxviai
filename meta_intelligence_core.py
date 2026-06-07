from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


META_CORE_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "lux_intent_depth",
        "name": "Lux Intent Depth",
        "category": "intent_quality",
        "description": "Reads whether the user wants a surface answer, a plan, a draft, or a deeper transformation.",
        "applies_to": ["general", "workspace", "support"],
        "trigger_contexts": ["create", "explain", "draft", "prepare"],
        "preview_signals": ["intent depth", "missing inputs", "desired outcome"],
        "risk_level": "low",
        "user_visible_behavior": "answer the real task, not only the literal words",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_friction_detector",
        "name": "Lux Friction Detector",
        "category": "user_burden_control",
        "description": "Detects confusion, overload, vague wording, or points where the user may get stuck.",
        "applies_to": ["general", "workspace", "support"],
        "trigger_contexts": ["confusing", "too much", "stuck"],
        "preview_signals": ["friction", "unclear next step"],
        "risk_level": "low",
        "user_visible_behavior": "reduce the next step to a manageable move",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_output_cleanliness_score",
        "name": "Lux Output Cleanliness Score",
        "category": "output_quality",
        "description": "Checks if output is clean, readable, non-bloated, and free of accidental clutter.",
        "applies_to": ["general", "workspace", "codex"],
        "trigger_contexts": ["clean output", "review output", "is this clean"],
        "preview_signals": ["clarity", "structure", "noise"],
        "risk_level": "low",
        "user_visible_behavior": "show a compact cleanliness note",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_attention_map",
        "name": "Lux Attention Map",
        "category": "context_control",
        "description": "Marks what should receive attention first and what can stay secondary.",
        "applies_to": ["general", "workspace", "visual", "codex"],
        "trigger_contexts": ["focus", "priority", "important"],
        "preview_signals": ["primary focus", "secondary context"],
        "risk_level": "low",
        "user_visible_behavior": "prioritize the important part",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_silent_draft_layer",
        "name": "Lux Silent Draft Layer",
        "category": "output_quality",
        "description": "Represents a hidden draft/refine pass before the user sees the final answer.",
        "applies_to": ["general", "workspace", "support"],
        "trigger_contexts": ["polish", "premium", "professional"],
        "preview_signals": ["draft then clean"],
        "risk_level": "low",
        "user_visible_behavior": "deliver a cleaner final, without exposing process noise",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_context_contract",
        "name": "Lux Context Contract",
        "category": "context_control",
        "description": "Defines what context is allowed to be used for the current answer.",
        "applies_to": ["workspace", "luxway", "support", "codex"],
        "trigger_contexts": ["use this", "do not use", "only this"],
        "preview_signals": ["scope", "allowed context"],
        "risk_level": "medium",
        "user_visible_behavior": "stay inside the requested scope",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_drift_alarm",
        "name": "Lux Drift Alarm",
        "category": "project_continuity",
        "description": "Warns when an answer may drift away from the user's original priority.",
        "applies_to": ["workspace", "visual", "codex"],
        "trigger_contexts": ["do not drift", "exactly", "complete"],
        "preview_signals": ["scope drift", "lost priority"],
        "risk_level": "medium",
        "user_visible_behavior": "keep the answer anchored",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_relevance_gate",
        "name": "Lux Relevance Gate",
        "category": "intent_quality",
        "description": "Filters tangents and keeps only what helps the user's request.",
        "applies_to": ["general", "workspace", "support"],
        "trigger_contexts": ["relevant", "only needed", "no tangent"],
        "preview_signals": ["relevance", "avoid tangent"],
        "risk_level": "low",
        "user_visible_behavior": "remove irrelevant extras",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_user_burden_meter",
        "name": "Lux User Burden Meter",
        "category": "user_burden_control",
        "description": "Prevents over-questioning and reduces cognitive load.",
        "applies_to": ["general", "workspace", "support"],
        "trigger_contexts": ["too many questions", "low stress", "do not ask much"],
        "preview_signals": ["question load", "decision fatigue"],
        "risk_level": "low",
        "user_visible_behavior": "ask fewer and better questions",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_one_screen_principle",
        "name": "Lux One-Screen Principle",
        "category": "output_quality",
        "description": "Keeps answers compact enough to scan when the task allows it.",
        "applies_to": ["general", "support", "luxway"],
        "trigger_contexts": ["short", "compact", "one screen"],
        "preview_signals": ["compactness", "scannability"],
        "risk_level": "low",
        "user_visible_behavior": "fit the useful answer into one screen where possible",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_rebuild_prevention",
        "name": "Lux Rebuild Prevention",
        "category": "context_control",
        "description": "Prevents rebuilding a scene, document, or structure when only a local change is requested.",
        "applies_to": ["visual", "workspace"],
        "trigger_contexts": ["do not rebuild", "keep scene", "preserve structure"],
        "preview_signals": ["locked elements", "local update"],
        "risk_level": "medium",
        "user_visible_behavior": "preserve existing structure and change only the requested detail",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_human_taste_layer",
        "name": "Lux Human Taste Layer",
        "category": "taste_premium_layer",
        "description": "Adds restrained taste, polish, and human-feeling judgment without generic AI styling.",
        "applies_to": ["visual", "workspace", "general"],
        "trigger_contexts": ["premium", "tasteful", "human"],
        "preview_signals": ["taste", "polish", "non-generic"],
        "risk_level": "low",
        "user_visible_behavior": "make it feel more considered and less generic",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_failure_memory",
        "name": "Lux Failure Memory",
        "category": "project_continuity",
        "description": "Marks repeated failure patterns for future review without writing memory in this scaffold.",
        "applies_to": ["general", "workspace", "codex"],
        "trigger_contexts": ["failed before", "again", "same mistake"],
        "preview_signals": ["failure pattern", "repeat risk"],
        "risk_level": "medium",
        "user_visible_behavior": "avoid repeating known mistakes",
        "proactive_allowed": False,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_priority_lock",
        "name": "Lux Priority Lock",
        "category": "decision_quality",
        "description": "Locks the user's explicit priority such as complete, exact, low-risk, or premium.",
        "applies_to": ["general", "workspace", "visual", "codex"],
        "trigger_contexts": ["complete", "exact", "do not miss", "priority"],
        "preview_signals": ["priority", "must keep"],
        "risk_level": "medium",
        "user_visible_behavior": "protect the user's stated priority",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_taste_conflict_resolver",
        "name": "Lux Taste Conflict Resolver",
        "category": "taste_premium_layer",
        "description": "Resolves conflicting style requests such as simple but detailed.",
        "applies_to": ["visual", "workspace", "general"],
        "trigger_contexts": ["simple but detailed", "clean but rich", "soft but strong"],
        "preview_signals": ["taste conflict", "style tradeoff"],
        "risk_level": "low",
        "user_visible_behavior": "balance the conflicting qualities",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_minimal_question_engine",
        "name": "Lux Minimal Question Engine",
        "category": "user_burden_control",
        "description": "Asks the smallest number of clarifying questions needed.",
        "applies_to": ["general", "workspace", "support"],
        "trigger_contexts": ["do not ask much", "start anyway", "few questions"],
        "preview_signals": ["minimal clarification", "assumption safe"],
        "risk_level": "low",
        "user_visible_behavior": "ask one focused question only when necessary",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_professional_memory_pack",
        "name": "Lux Professional Memory Pack",
        "category": "project_continuity",
        "description": "Keeps a professional project packet conceptually complete without writing memory.",
        "applies_to": ["workspace", "codex"],
        "trigger_contexts": ["complete transfer", "professional", "all details"],
        "preview_signals": ["project facts", "constraints", "style rules"],
        "risk_level": "medium",
        "user_visible_behavior": "keep professional details together",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_confidence_display",
        "name": "Lux Confidence Display",
        "category": "safety_truthfulness",
        "description": "Shows uncertainty when needed instead of overclaiming.",
        "applies_to": ["general", "support", "codex"],
        "trigger_contexts": ["are you sure", "confidence", "uncertain"],
        "preview_signals": ["confidence", "uncertainty"],
        "risk_level": "low",
        "user_visible_behavior": "state uncertainty plainly",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_do_not_invent_guard",
        "name": "Lux Do Not Invent Guard",
        "category": "safety_truthfulness",
        "description": "Prevents invented sources, facts, citations, or details.",
        "applies_to": ["workspace", "general", "codex"],
        "trigger_contexts": ["source", "citation", "do not invent"],
        "preview_signals": ["no fabrication", "source requirement"],
        "risk_level": "high",
        "user_visible_behavior": "do not fabricate missing facts",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
    {
        "id": "lux_value_mode",
        "name": "Lux Value Mode",
        "category": "decision_quality",
        "description": "Balances speed, quality, premium feel, risk, and completeness.",
        "applies_to": ["general", "workspace", "support", "codex"],
        "trigger_contexts": ["premium", "fast", "low risk", "complete"],
        "preview_signals": ["value tradeoff", "quality priority"],
        "risk_level": "low",
        "user_visible_behavior": "optimize for the user's value priority",
        "proactive_allowed": True,
        "read_only": True,
        "real_pipeline_change": False,
    },
]


META_RULES = {
    "lux_intent_depth": ["cv hazirla", "rapor hazirla", "sunum hazirla", "taslak hazirla"],
    "lux_minimal_question_engine": ["cv hazirla", "cok soru sorma", "az soru", "soru sorma"],
    "lux_priority_lock": ["eksiksiz", "tam aktar", "sahneyi bozma", "oncelik"],
    "lux_professional_memory_pack": ["eksiksiz aktar", "profesyonel aktar", "tum detay"],
    "lux_drift_alarm": ["eksiksiz", "konudan sapma", "drift"],
    "lux_rebuild_prevention": ["sahneyi bozma", "bastan kurma", "yapıyı bozma", "yapiyi bozma"],
    "lux_do_not_invent_guard": ["kaynak uydurma", "uydurma", "citation", "kaynak"],
    "lux_taste_conflict_resolver": ["sade ama detayli", "clean but rich", "basit ama zengin"],
    "lux_human_taste_layer": ["premium", "zevkli", "insani", "kisa ve premium"],
    "lux_value_mode": ["kisa ve premium", "premium", "hizli", "low risk"],
    "lux_user_burden_meter": ["cok soru sorma", "yorma", "low stress"],
    "lux_output_cleanliness_score": ["cikti temiz", "temiz mi", "clean output"],
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("ı", "i").replace("ğ", "g").replace("ş", "s")
    value = value.replace("ö", "o").replace("ü", "u").replace("ç", "c")
    return re.sub(r"\s+", " ", value).strip()


def _find_core(core_id: str) -> Dict[str, Any]:
    for core in META_CORE_REGISTRY:
        if core["id"] == core_id:
            return core
    return META_CORE_REGISTRY[0]


def meta_core_registry() -> Dict[str, Any]:
    return {
        "status": "meta_core_registry_ready",
        "core_count": len(META_CORE_REGISTRY),
        "cores": META_CORE_REGISTRY,
        "read_only": True,
        "real_pipeline_change": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
    }


def preview_meta_quality(
    command: str,
    draft_output: str = "",
    source_area: str = "general",
    user_priority: str = "",
) -> Dict[str, Any]:
    haystack = _normalize(f"{command} {draft_output} {source_area} {user_priority}")
    matches: List[Dict[str, Any]] = []
    for core_id, keywords in META_RULES.items():
        matched = [keyword for keyword in keywords if keyword in haystack]
        if matched:
            core = _find_core(core_id)
            matches.append(
                {
                    "id": core["id"],
                    "name": core["name"],
                    "category": core["category"],
                    "matched_keywords": matched,
                    "confidence": "high" if len(matched) > 1 else "medium",
                }
            )

    if not matches:
        fallback = _find_core("lux_relevance_gate")
        matches.append(
            {
                "id": fallback["id"],
                "name": fallback["name"],
                "category": fallback["category"],
                "matched_keywords": [],
                "confidence": "low",
            }
        )

    primary = _find_core(matches[0]["id"])
    truthfulness_on = any(item["id"] == "lux_do_not_invent_guard" for item in matches) or source_area in {"workspace", "codex"}
    burden_on = any(item["id"] in {"lux_user_burden_meter", "lux_minimal_question_engine"} for item in matches)
    priority_matches = [item for item in matches if item["id"] == "lux_priority_lock"]
    value_mode = user_priority or ("premium" if "premium" in haystack else "quality")
    return {
        "raw_command": command,
        "source_area": source_area,
        "detected_meta_cores": matches,
        "primary_quality_core": {
            "id": primary["id"],
            "name": primary["name"],
            "category": primary["category"],
            "user_visible_behavior": primary["user_visible_behavior"],
        },
        "intent_depth_preview": {
            "needs_depth_check": any(item["id"] == "lux_intent_depth" for item in matches),
            "suggested_depth": "structured_draft" if "cv hazirla" in haystack else "focused_answer",
        },
        "friction_signals": {
            "user_burden_detected": burden_on,
            "too_many_questions_risk": burden_on,
            "suggested_question_count": 1 if burden_on else 0,
        },
        "cleanliness_preview": {
            "cleanliness_score_preview": 0.86 if draft_output else 0.8,
            "block_dump_risk": False,
            "needs_trim": "cikti temiz" in haystack or "temiz mi" in haystack,
        },
        "relevance_gate": {
            "active": True,
            "rule": "keep only details that serve the user's request",
        },
        "user_burden_preview": {
            "active": burden_on,
            "safe_behavior": "ask the smallest useful question only when necessary",
        },
        "truthfulness_guard": {
            "do_not_invent_guard_active": truthfulness_on,
            "source_fabrication_allowed": False,
        },
        "priority_lock": {
            "active": bool(priority_matches),
            "locked_priority": "complete_transfer" if "eksiksiz" in haystack else user_priority,
        },
        "value_mode": value_mode,
        "safe_next_step": "Preview only: use these quality signals as guidance without changing the live pipeline.",
        "real_pipeline_change": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "read_only": True,
    }


def meta_status() -> Dict[str, Any]:
    return {
        "layer": "21.2",
        "name": "Meta Intelligence / Quality Core",
        "status": "scaffold_ready",
        "core_count": len(META_CORE_REGISTRY),
        "categories": sorted({core["category"] for core in META_CORE_REGISTRY}),
        "read_only": True,
        "real_pipeline_change": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_notes": [
            "No production answer pipeline is changed.",
            "No memory, database, or file write is performed.",
            "Do Not Invent Guard is preview-only metadata.",
            "User burden reduction is shown as a quality signal only.",
        ],
    }
