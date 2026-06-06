"""Read-only cost/token logging privacy policy preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict

from model_router_config import preview_model_route


ALLOWED_METADATA = [
    "detected_task_type",
    "recommended_model_role",
    "fallback_model_role",
    "cost_sensitivity",
    "privacy_risk",
    "latency_bucket_future",
    "token_estimate_bucket_future",
    "route_reason",
    "response_size_bucket",
]

BLOCKED_METADATA = [
    "raw_user_message",
    "raw_private_message",
    "raw_audio",
    "raw_file_content",
    "raw_sensitive_content",
    "crisis_content_raw",
    "exact_personal_details",
    "private_contact_content",
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


def _privacy_risk(command: str, task_type: str, sensitivity: str) -> str:
    normalized = _normalize_text(" ".join([command or "", task_type or "", sensitivity or ""]))
    sensitive_keywords = [
        "private",
        "privacy",
        "hassas",
        "gizli",
        "ozel",
        "guvenlik",
        "mesaj",
        "mail",
        "ses",
        "audio",
        "dosya",
        "file",
        "kriz",
        "crisis",
        "telefon",
    ]
    if sensitivity in {"high", "privacy", "safety"} or any(keyword in normalized for keyword in sensitive_keywords):
        return "high"
    return "low"


def _token_bucket(value: str, response_size: str) -> str:
    if value in {"tiny", "small", "medium", "large", "very_large"}:
        return value
    size_map = {
        "short": "small",
        "medium": "medium",
        "long": "large",
        "workspace_large": "very_large",
    }
    return size_map.get(response_size, "medium")


def cost_privacy_policy() -> Dict[str, Any]:
    return {
        "raw_user_text_logged": False,
        "raw_private_message_logged": False,
        "raw_audio_logged": False,
        "raw_file_content_logged": False,
        "raw_sensitive_content_logged": False,
        "safe_derived_metadata_only": True,
        "allowed_metadata": list(ALLOWED_METADATA),
        "blocked_metadata": list(BLOCKED_METADATA),
        "storage_allowed": False,
        "billing_write_performed": False,
        "db_write_performed": False,
        "memory_write_performed": False,
        "file_write_performed": False,
        "read_only": True,
        "safety_note": "Only safe derived metadata may be previewed; raw user/private/audio/file/sensitive content is never logged.",
    }


def preview_cost_privacy(
    command: str,
    task_type: str = "",
    sensitivity: str = "normal",
    estimated_tokens_bucket: str = "",
) -> Dict[str, Any]:
    raw_command = command or ""
    route = preview_model_route(raw_command, task_type, sensitivity, "medium")
    privacy_risk = _privacy_risk(raw_command, str(route.get("detected_task_type", task_type)), sensitivity)
    token_bucket = _token_bucket(estimated_tokens_bucket, "medium")
    return {
        "raw_user_text_logged": False,
        "raw_private_message_logged": False,
        "raw_audio_logged": False,
        "raw_file_content_logged": False,
        "raw_sensitive_content_logged": False,
        "safe_derived_metadata_only": True,
        "allowed_metadata": list(ALLOWED_METADATA),
        "blocked_metadata": list(BLOCKED_METADATA),
        "cost_preview": {
            "detected_task_type": route.get("detected_task_type"),
            "recommended_model_role": route.get("recommended_model_role"),
            "fallback_model_role": route.get("fallback_model_role"),
            "cost_sensitivity": route.get("cost_sensitivity"),
            "route_reason": route.get("route_reason"),
            "response_size_bucket": "medium",
            "preview_only": True,
        },
        "token_bucket_preview": {
            "token_estimate_bucket_future": token_bucket,
            "exact_token_count_logged": False,
        },
        "privacy_risk": privacy_risk,
        "storage_allowed": False,
        "billing_write_performed": False,
        "db_write_performed": False,
        "memory_write_performed": False,
        "file_write_performed": False,
        "read_only": True,
        "safe_reason": "Cost preview uses only derived metadata. No raw content, billing write, DB write, memory write, or file write is performed.",
    }
