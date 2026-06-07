from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


TRANSFER_MODES: List[Dict[str, Any]] = [
    {
        "id": "silent_continue",
        "title": "Silent Continue",
        "description": "Preview how Lux would continue from a referenced page without restating everything.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
    {
        "id": "compact_summary",
        "title": "Compact Summary",
        "description": "Preview a short safe summary transfer from a referenced context.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
    {
        "id": "detailed_transfer",
        "title": "Detailed Transfer",
        "description": "Preview a structured, detailed transfer plan with headings and checkpoints.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
    {
        "id": "exact_full_transfer_request",
        "title": "Exact Full Transfer Request",
        "description": "Preview an explicit request for complete transfer while still blocking raw sensitive content.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
    {
        "id": "topic_specific_retrieval",
        "title": "Topic Specific Retrieval",
        "description": "Preview a transfer plan focused only on the named topic.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
    {
        "id": "whole_page_transfer",
        "title": "Whole Page Transfer",
        "description": "Preview a whole-page transfer plan with privacy filtering.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
    {
        "id": "scattered_topic_extraction",
        "title": "Scattered Topic Extraction",
        "description": "Preview how scattered notes would be collected into a safe topic summary.",
        "requires_explicit_source": True,
        "raw_sensitive_content_allowed": False,
        "read_only": True,
    },
]


MODE_RULES = {
    "exact_full_transfer_request": [
        "eksiksiz aktar",
        "hicbir detayi atlama",
        "tam aktar",
        "full transfer",
        "aynen aktar",
    ],
    "silent_continue": [
        "ozetleme sadece oku",
        "sadece oku ve devam et",
        "buradan devam edelim",
        "sessiz devam",
        "okudum anladim",
    ],
    "scattered_topic_extraction": [
        "daginik",
        "konusmalardan",
        "kurallarini cikar",
        "kararlari cikar",
        "extract",
    ],
    "topic_specific_retrieval": [
        "sadece",
        "kismini getir",
        "konusunu oku",
        "topic",
        "ilgili konu",
        "luxway",
    ],
    "whole_page_transfer": [
        "butun sayfa",
        "tum sayfa",
        "sayfanin tamamini",
        "whole page",
    ],
    "detailed_transfer": [
        "detayli aktar",
        "ayrintili aktar",
        "baslik baslik",
        "detailed",
    ],
    "compact_summary": [
        "kisa ozetle",
        "kisa ozet",
        "ozetle",
        "compact summary",
    ],
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ş": "s",
        "ö": "o",
        "ü": "u",
        "ç": "c",
        "İ": "i",
        "Ã¶": "o",
        "Ã¼": "u",
        "Ã§": "c",
        "Ä±": "i",
        "ÄŸ": "g",
        "ÅŸ": "s",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def _mode_by_id(mode_id: str) -> Dict[str, Any]:
    for mode in TRANSFER_MODES:
        if mode["id"] == mode_id:
            return mode
    return TRANSFER_MODES[1]


def _detect_transfer_mode(command: str, requested_mode: str = "") -> Dict[str, Any]:
    requested = _normalize(requested_mode)
    if requested:
        for mode in TRANSFER_MODES:
            if requested == _normalize(mode["id"]) or requested == _normalize(mode["title"]):
                return {
                    "id": mode["id"],
                    "title": mode["title"],
                    "confidence": "high",
                    "matched_rule": "explicit_transfer_mode",
                }

    normalized = _normalize(command)
    for mode_id, keywords in MODE_RULES.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        if matched:
            mode = _mode_by_id(mode_id)
            return {
                "id": mode["id"],
                "title": mode["title"],
                "confidence": "high" if len(matched) > 1 else "medium",
                "matched_rule": matched[0],
            }

    fallback = _mode_by_id("compact_summary")
    return {
        "id": fallback["id"],
        "title": fallback["title"],
        "confidence": "low",
        "matched_rule": "fallback_safe_summary",
    }


def _infer_topic(command: str, target_topic: str = "") -> str:
    if target_topic:
        return target_topic
    normalized = _normalize(command)
    topic_map = [
        ("luxworkspace", "LuxWorkspace"),
        ("workspace", "LuxWorkspace"),
        ("layer 16", "Layer 16 visual rules"),
        ("gorsel", "Visual style decisions"),
        ("stil", "Visual style decisions"),
        ("luxway", "Luxway"),
        ("model router", "Model Router"),
        ("voice", "Voice / Audio"),
        ("audio", "Voice / Audio"),
        ("emotional", "Emotional Reflection"),
    ]
    for keyword, topic in topic_map:
        if keyword in normalized:
            return topic
    return "unspecified topic"


def _source_reference_needed(command: str, source_label: str) -> bool:
    if source_label:
        return False
    normalized = _normalize(command)
    references_external_context = any(
        keyword in normalized
        for keyword in ["a sayfasi", "o sayfa", "sayfadaki", "onceki", "baska sayfa", "proje", "konusmalardan"]
    )
    return references_external_context


def context_bridge_schema() -> Dict[str, Any]:
    return {
        "status": "context_bridge_schema_ready",
        "layer": "21.4",
        "name": "Lux Context Bridge / Cross-Page Context Bridge",
        "transfer_modes": TRANSFER_MODES,
        "input_fields": ["command", "source_label", "target_topic", "transfer_mode", "sensitivity"],
        "output_fields": [
            "raw_command",
            "detected_transfer_mode",
            "source_reference_needed",
            "target_topic",
            "retrieval_allowed",
            "real_cross_page_read_performed",
            "memory_read_performed",
            "memory_write_performed",
            "raw_sensitive_content_returned",
            "safe_transfer_plan",
            "user_confirmation_required",
            "privacy_boundary",
            "preview_response",
            "read_only",
        ],
        "privacy_rules": [
            "No hidden history is searched without a user-provided source or project reference.",
            "This scaffold does not perform real cross-page retrieval.",
            "Raw sensitive content is never returned.",
            "Memory read/write and DB/file writes are disabled.",
            "Exact transfer requires an explicit user request and still applies privacy filtering.",
        ],
        "read_only": True,
        "retrieval_allowed": False,
        "real_cross_page_read_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
    }


def preview_context_bridge(
    command: str,
    source_label: str = "",
    target_topic: str = "",
    transfer_mode: str = "",
    sensitivity: str = "normal",
) -> Dict[str, Any]:
    detected_mode = _detect_transfer_mode(command, transfer_mode)
    topic = _infer_topic(command, target_topic)
    source_needed = _source_reference_needed(command, source_label)
    normalized_sensitivity = _normalize(sensitivity)
    sensitive = normalized_sensitivity in {"high", "private", "privacy", "sensitive", "hassas"}
    confirmation_required = detected_mode["id"] in {
        "exact_full_transfer_request",
        "whole_page_transfer",
        "detailed_transfer",
    } or sensitive

    transfer_steps = [
        "Ask the user to identify the source page/project if it is not explicit.",
        "Read only the user-approved source in a future real integration.",
        "Extract safe summaries and topic decisions instead of raw sensitive content.",
        "Apply the selected transfer mode without writing memory or files.",
        "Show a preview and ask for confirmation before any future full transfer.",
    ]
    if detected_mode["id"] == "silent_continue":
        transfer_steps = [
            "Confirm the referenced source before any future read.",
            "Build a hidden working summary in a future integration.",
            "Continue naturally while noting that no real read happened in this preview.",
        ]
    elif detected_mode["id"] == "topic_specific_retrieval":
        transfer_steps = [
            f"Limit retrieval scope to {topic}.",
            "Ignore unrelated context from the source page.",
            "Return only a safe topic summary and open decisions.",
        ]
    elif detected_mode["id"] == "scattered_topic_extraction":
        transfer_steps = [
            f"Collect scattered mentions related to {topic}.",
            "Deduplicate decisions and rules.",
            "Return a compact bridge summary without raw private text.",
        ]

    return {
        "raw_command": command,
        "detected_transfer_mode": detected_mode,
        "source_reference_needed": source_needed,
        "source_label": source_label or "",
        "target_topic": topic,
        "retrieval_allowed": False,
        "real_cross_page_read_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "raw_sensitive_content_returned": False,
        "safe_transfer_plan": {
            "mode": detected_mode["id"],
            "steps": transfer_steps,
            "raw_sensitive_content_policy": "blocked",
            "scope": topic,
        },
        "user_confirmation_required": confirmation_required,
        "privacy_boundary": {
            "requires_user_named_source": True,
            "no_hidden_history_search": True,
            "raw_sensitive_content_returned": False,
            "real_cross_page_read_performed": False,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_write_performed": False,
        },
        "preview_response": (
            "Preview only: I would bridge the approved context safely, but no real page/history was read."
        ),
        "read_only": True,
        "db_write_performed": False,
        "file_write_performed": False,
    }


def context_bridge_status() -> Dict[str, Any]:
    return {
        "layer": "21.4",
        "name": "Context Bridge Preview",
        "status": "scaffold_ready",
        "transfer_mode_count": len(TRANSFER_MODES),
        "available_endpoints": [
            "/context-bridge/schema",
            "/context-bridge/preview",
            "/debug/context-bridge-status",
        ],
        "read_only": True,
        "retrieval_allowed": False,
        "real_cross_page_read_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "raw_sensitive_content_returned": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_notes": [
            "No real history or cross-page data is read in this scaffold.",
            "Raw sensitive content is blocked.",
            "Exact transfer requires explicit user intent and future confirmation.",
        ],
    }
