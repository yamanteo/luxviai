from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


EMOTIONAL_SUPPORT_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "emotional_signal_map",
        "name": "Emotional Signal Map",
        "category": "emotional_signal",
        "description": "Maps safe, non-diagnostic emotional signals from the user's wording.",
        "trigger_contexts": ["general", "voice", "workspace"],
        "safe_preview_signals": ["low energy", "tension", "uncertainty"],
        "prohibited_outputs": ["clinical diagnosis", "fixed personality label"],
        "user_visible_behavior": "offer a possible emotional signal in careful language",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "gentle_check_in",
        "name": "Gentle Check-in",
        "category": "reflection",
        "description": "Offers one gentle check-in question when the user seems overloaded.",
        "trigger_contexts": ["general", "voice"],
        "safe_preview_signals": ["overload", "need pause"],
        "prohibited_outputs": ["therapy claim", "diagnosis"],
        "user_visible_behavior": "ask one small grounding question if useful",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "reflection_layer",
        "name": "Reflection Layer",
        "category": "reflection",
        "description": "Summarizes the day or situation as a read-only reflection.",
        "trigger_contexts": ["general", "workspace"],
        "safe_preview_signals": ["daily recap", "meaningful points"],
        "prohibited_outputs": ["private memory write", "clinical interpretation"],
        "user_visible_behavior": "summarize gently without storing",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "personal_pattern_review",
        "name": "Personal Pattern Review",
        "category": "pattern_awareness",
        "description": "Notices possible repeated patterns without claiming certainty.",
        "trigger_contexts": ["general", "workspace", "social"],
        "safe_preview_signals": ["repetition", "stuck point"],
        "prohibited_outputs": ["definitive psychological label", "memory write"],
        "user_visible_behavior": "say a pattern may be present and suggest one next step",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "emotional_language_signals",
        "name": "Emotional Language Signals",
        "category": "emotional_signal",
        "description": "Highlights emotional wording, tone, and possible need behind language.",
        "trigger_contexts": ["message", "social", "general"],
        "safe_preview_signals": ["hard words", "soft need", "pressure"],
        "prohibited_outputs": ["mind reading", "certainty claim"],
        "user_visible_behavior": "translate harsh inner wording into a softer signal",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "trigger_pattern_notes",
        "name": "Trigger / Pattern Notes",
        "category": "pattern_awareness",
        "description": "Creates preview-only notes about possible triggers or repeated friction.",
        "trigger_contexts": ["general", "social"],
        "safe_preview_signals": ["trigger possibility", "friction point"],
        "prohibited_outputs": ["stored raw emotional history", "diagnosis"],
        "user_visible_behavior": "note a possible trigger without storing it",
        "proactive_allowed": False,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "duygu_gorev_ayristirici",
        "name": "Duygu-Görev Ayrıştırıcı",
        "category": "energy_support",
        "description": "Separates task difficulty from the feeling around the task.",
        "trigger_contexts": ["workspace", "general"],
        "safe_preview_signals": ["task vs feeling", "avoidance", "pressure"],
        "prohibited_outputs": ["diagnosis", "blame"],
        "user_visible_behavior": "separate what needs doing from what feels hard",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "ic_ses_editoru",
        "name": "İç Ses Editörü",
        "category": "reflection",
        "description": "Softens harsh self-talk into a kinder, realistic sentence.",
        "trigger_contexts": ["general", "voice"],
        "safe_preview_signals": ["harsh self-talk", "inner pressure"],
        "prohibited_outputs": ["therapy claim", "diagnosis"],
        "user_visible_behavior": "offer one kinder rephrase",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "deger_pusulasi",
        "name": "Değer Pusulası",
        "category": "value_clarity",
        "description": "Names a possible value conflict such as speed versus quality.",
        "trigger_contexts": ["general", "workspace"],
        "safe_preview_signals": ["value conflict", "priority tension"],
        "prohibited_outputs": ["telling user who they are", "fixed label"],
        "user_visible_behavior": "show a possible value tradeoff and one next choice",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "social_emotional_support",
        "name": "Social Emotional Support",
        "category": "social_emotional",
        "description": "Helps reflect on the emotional load of a message or social exchange.",
        "trigger_contexts": ["social", "message"],
        "safe_preview_signals": ["message fatigue", "social pressure"],
        "prohibited_outputs": ["relationship certainty claim", "manipulation"],
        "user_visible_behavior": "name the load gently and suggest a low-pressure response",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "safety_boundary",
        "name": "Safety Boundary",
        "category": "safety_boundary",
        "description": "Keeps emotional reflection inside safe, non-clinical boundaries.",
        "trigger_contexts": ["general", "voice", "social"],
        "safe_preview_signals": ["sensitive content", "careful language"],
        "prohibited_outputs": ["crisis system claim", "clinical diagnosis"],
        "user_visible_behavior": "avoid diagnosis and keep language careful",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
    {
        "id": "dream_symbol_inner_state",
        "name": "Rüya / Sembol / İç Durum Bağlantısı",
        "category": "symbolic_inner_state",
        "description": "Connects dreams or symbols to possible feelings without claiming interpretation certainty.",
        "trigger_contexts": ["visual", "general"],
        "safe_preview_signals": ["symbol", "inner state", "dream feeling"],
        "prohibited_outputs": ["definitive dream interpretation", "diagnosis"],
        "user_visible_behavior": "say what a symbol may evoke, not what it means for sure",
        "proactive_allowed": True,
        "requires_permission": False,
        "clinical_diagnosis_allowed": False,
        "memory_write_performed": False,
        "read_only": True,
    },
]


EMOTIONAL_RULES = {
    "emotional_signal_map": ["enerjim dusuk", "yorgunum", "icimde", "hissim"],
    "reflection_layer": ["bugun ne yaptim", "toparla", "gunumu toparla"],
    "personal_pattern_review": ["hep ayni yerde", "takiliyorum", "hep ayni"],
    "ic_ses_editoru": ["ic sesim", "kendime cok sert", "cok sert"],
    "deger_pusulasi": ["hiz mi kalite", "bilmiyorum", "deger", "oncelik"],
    "social_emotional_support": ["mesaj beni yordu", "bu mesaj beni yordu", "sosyal yordu"],
    "dream_symbol_inner_state": ["ruyamdaki sembol", "sembol ne hissettiriyor", "ruya"],
    "duygu_gorev_ayristirici": ["yapmak degil", "anlatmak zor", "gorev zor", "duygu gorev"],
    "safety_boundary": ["kriz", "tehlike", "kendime zarar", "dayanamiyorum"],
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("ı", "i").replace("ğ", "g").replace("ş", "s")
    value = value.replace("ö", "o").replace("ü", "u").replace("ç", "c")
    return re.sub(r"\s+", " ", value).strip()


def _find_support(support_id: str) -> Dict[str, Any]:
    for support in EMOTIONAL_SUPPORT_REGISTRY:
        if support["id"] == support_id:
            return support
    return EMOTIONAL_SUPPORT_REGISTRY[0]


def emotional_reflection_registry() -> Dict[str, Any]:
    return {
        "status": "emotional_reflection_registry_ready",
        "support_count": len(EMOTIONAL_SUPPORT_REGISTRY),
        "supports": EMOTIONAL_SUPPORT_REGISTRY,
        "read_only": True,
        "clinical_diagnosis_allowed": False,
        "therapy_claim_made": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
    }


def preview_emotional_reflection(
    command: str,
    context: str = "",
    source_area: str = "general",
    sensitivity: str = "normal",
) -> Dict[str, Any]:
    haystack = _normalize(f"{command} {context}")
    matches: List[Dict[str, Any]] = []
    for support_id, keywords in EMOTIONAL_RULES.items():
        matched = [keyword for keyword in keywords if keyword in haystack]
        if matched:
            support = _find_support(support_id)
            matches.append(
                {
                    "id": support["id"],
                    "name": support["name"],
                    "category": support["category"],
                    "matched_keywords": matched,
                    "confidence": "high" if len(matched) > 1 else "medium",
                }
            )

    if not matches:
        fallback = _find_support("gentle_check_in")
        matches.append(
            {
                "id": fallback["id"],
                "name": fallback["name"],
                "category": fallback["category"],
                "matched_keywords": [],
                "confidence": "low",
            }
        )

    if sensitivity in {"high", "safety", "crisis"} and not any(item["id"] == "safety_boundary" for item in matches):
        support = _find_support("safety_boundary")
        matches.insert(
            0,
            {
                "id": support["id"],
                "name": support["name"],
                "category": support["category"],
                "matched_keywords": ["sensitivity"],
                "confidence": "high",
            },
        )

    primary = _find_support(matches[0]["id"])
    energy_active = any(item["id"] in {"emotional_signal_map", "duygu_gorev_ayristirici"} for item in matches)
    pattern_active = any(item["id"] in {"personal_pattern_review", "trigger_pattern_notes"} for item in matches)
    value_active = any(item["id"] == "deger_pusulasi" for item in matches)
    prohibited = sorted({output for support in EMOTIONAL_SUPPORT_REGISTRY for output in support["prohibited_outputs"]})
    return {
        "raw_command": command,
        "source_area": source_area,
        "detected_supports": matches,
        "primary_support": {
            "id": primary["id"],
            "name": primary["name"],
            "category": primary["category"],
            "user_visible_behavior": primary["user_visible_behavior"],
        },
        "emotional_signal_preview": {
            "language": "This may be a signal, not a label.",
            "possible_signal": "low energy or pressure" if energy_active else "needs gentle reflection",
        },
        "energy_signal_preview": {
            "active": energy_active,
            "suggestion": "choose one low-effort next step" if energy_active else "no strong energy signal detected",
        },
        "reflection_prompt_preview": "What is the smallest useful thing to name here?",
        "pattern_preview": {
            "active": pattern_active,
            "memory_write_performed": False,
            "note": "Pattern notes are preview-only and not stored.",
        },
        "value_conflict_preview": {
            "active": value_active,
            "possible_conflict": "speed versus quality" if value_active else "",
        },
        "safe_next_step": "Name one possible signal and choose one small next step.",
        "prohibited_outputs": prohibited,
        "clinical_diagnosis_performed": False,
        "therapy_claim_made": False,
        "crisis_handling_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "read_only": True,
    }


def emotional_status() -> Dict[str, Any]:
    return {
        "layer": "21.3",
        "name": "Emotional Reflection Support",
        "status": "scaffold_ready",
        "support_count": len(EMOTIONAL_SUPPORT_REGISTRY),
        "categories": sorted({support["category"] for support in EMOTIONAL_SUPPORT_REGISTRY}),
        "read_only": True,
        "clinical_diagnosis_performed": False,
        "therapy_claim_made": False,
        "crisis_handling_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_notes": [
            "No clinical diagnosis or therapy claim is made.",
            "No crisis system is implemented in this scaffold.",
            "Raw private emotional history is not stored.",
            "Pattern notes remain preview-only.",
        ],
    }
