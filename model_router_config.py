"""Read-only model router and cost efficiency preview scaffold."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional


DEEPSEEK_TARGET_SHARE = 0.96
MINI_5_4_TARGET_SHARE = 0.03
GPT_5_5_TARGET_SHARE = 0.01

TARGET_DISTRIBUTION = {
    "deepseek": DEEPSEEK_TARGET_SHARE,
    "mini_5_4": MINI_5_4_TARGET_SHARE,
    "gpt_5_5": GPT_5_5_TARGET_SHARE,
}

TASK_TYPES = [
    "normal_chat",
    "workspace",
    "report_writer",
    "cv_builder",
    "presentation_planner",
    "codex_prompt",
    "project_planning",
    "visual_prompt",
    "dream_scene",
    "ambrosia_prompt",
    "image_generation_request",
    "image_understanding_request",
    "sketch_understanding_request",
    "audio_voice",
    "luxway",
    "permission_boundary",
    "decision_trace",
    "code",
    "critical_debug",
    "safety_sensitive",
    "privacy_sensitive",
    "unknown",
]

MODEL_ROLE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "deepseek_primary": {
        "id": "deepseek_primary",
        "display_name": "DeepSeek",
        "target_share": DEEPSEEK_TARGET_SHARE,
        "role": "primary_reasoning",
        "priority": "default",
        "cost_tier": "low",
        "default_for": [
            "normal_chat",
            "workspace",
            "report_writer",
            "cv_builder",
            "presentation_planner",
            "codex_prompt",
            "project_planning",
            "luxway_preview",
            "permission_boundary",
            "decision_trace",
            "visual_prompt_planner",
            "dream_scene_planner",
            "voice_preview",
        ],
        "real_api_call_enabled": False,
        "read_only": True,
    },
    "mini_5_4_support": {
        "id": "mini_5_4_support",
        "display_name": "Mini 5.4",
        "target_share": MINI_5_4_TARGET_SHARE,
        "role": "auxiliary_multimodal_support",
        "priority": "helper_only",
        "cost_tier": "medium_low",
        "used_for": [
            "multimodal_reader_future",
            "image_understanding_future",
            "sketch_interpreter_future",
            "screenshot_reader_future",
            "small_classification",
            "quick_router_check",
            "low_cost_second_opinion",
            "visual_object_relation",
            "voice_text_command_classification",
            "permission_risk_classification",
        ],
        "not_default": True,
        "real_api_call_enabled": False,
        "read_only": True,
    },
    "gpt_5_5_premium_fallback": {
        "id": "gpt_5_5_premium_fallback",
        "display_name": "GPT-5.5",
        "target_share": GPT_5_5_TARGET_SHARE,
        "role": "fallback_high_quality",
        "priority": "rare_fallback",
        "cost_tier": "high",
        "used_for": [
            "critical_debugging",
            "complex_reasoning",
            "architecture_review",
            "security_privacy_review",
            "high_stakes_quality_audit",
            "final_review",
            "deepseek_uncertain",
            "mini_uncertain",
            "model_disagreement_resolution",
        ],
        "real_api_call_enabled": False,
        "read_only": True,
    },
    "image_api_future": {
        "id": "image_api_future",
        "display_name": "Image API Future",
        "target_share": None,
        "role": "image_generation_future",
        "priority": "future_specialized",
        "used_for": [
            "real_image_generation_future",
            "image_editing_future",
            "visual_output_future",
        ],
        "real_api_call_enabled": False,
        "image_generation_performed": False,
        "read_only": True,
    },
}

ROUTER_PRIVACY_POLICY = {
    "raw_user_text_logged": False,
    "only_safe_derived_metadata": True,
    "store_allowed_metadata": [
        "detected_task_type",
        "recommended_model_role",
        "fallback_model_role",
        "cost_sensitivity",
        "privacy_risk",
        "latency_bucket_future",
        "token_estimate_bucket_future",
        "route_reason",
    ],
    "never_store": [
        "raw_user_message",
        "raw_private_message",
        "raw_audio",
        "raw_file_content",
        "raw_sensitive_content",
        "crisis_content_raw",
    ],
    "user_visible_model_choice": False,
    "routing_invisible_to_user": True,
    "real_billing_write": False,
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


def _detect_task_type(command: str, task_type: str) -> str:
    if task_type in TASK_TYPES and task_type:
        return task_type
    normalized = _normalize_text(command)
    if any(keyword in normalized for keyword in ["kritik kod debug", "critical debug", "kritik debug", "zor debug"]):
        return "critical_debug"
    if any(keyword in normalized for keyword in ["gorsel uret", "resim uret", "image generate", "image generation"]):
        return "image_generation_request"
    if any(keyword in normalized for keyword in ["cizimi oku", "sketch", "cizim oku", "taslagi oku"]):
        return "sketch_understanding_request"
    if any(keyword in normalized for keyword in ["screenshot oku", "gorseli oku", "image understanding", "fotografi oku"]):
        return "image_understanding_request"
    if any(keyword in normalized for keyword in ["ruya", "dream scene", "sahnesi prompt", "dream"]):
        return "dream_scene"
    if any(keyword in normalized for keyword in ["ambrosia"]):
        return "ambrosia_prompt"
    if any(keyword in normalized for keyword in ["gorsel prompt", "visual prompt", "promptla"]):
        return "visual_prompt"
    if any(keyword in normalized for keyword in ["luxway", "telefon raporu", "telefonumu", "bildirimlerimi"]):
        return "luxway"
    if any(keyword in normalized for keyword in ["permission", "izin", "gonder", "sil", "ara", "ayar"]):
        return "permission_boundary"
    if any(keyword in normalized for keyword in ["rapor"]):
        return "report_writer"
    if any(keyword in normalized for keyword in ["cv"]):
        return "cv_builder"
    if any(keyword in normalized for keyword in ["sunum", "presentation"]):
        return "presentation_planner"
    if any(keyword in normalized for keyword in ["workspace", "belge", "odev", "tez"]):
        return "workspace"
    if any(keyword in normalized for keyword in ["kod", "code", "codex"]):
        return "code"
    if any(keyword in normalized for keyword in ["hassas", "guvenlik", "privacy", "gizlilik"]):
        return "safety_sensitive"
    return "normal_chat" if normalized.strip() else "unknown"


def _privacy_risk(task_type: str, sensitivity: str) -> str:
    if sensitivity in {"high", "privacy", "safety"}:
        return "high"
    if task_type in {"permission_boundary", "safety_sensitive", "privacy_sensitive", "luxway"}:
        return "high"
    if task_type in {"image_understanding_request", "sketch_understanding_request", "audio_voice"}:
        return "medium"
    return "low"


def _quality_sensitivity(task_type: str, sensitivity: str, response_size: str) -> str:
    if task_type in {"critical_debug", "safety_sensitive", "privacy_sensitive"}:
        return "high"
    if sensitivity in {"high", "safety", "privacy"} or response_size in {"long", "workspace_large"}:
        return "medium_high"
    return "normal"


def _base_payload(
    raw_command: str,
    task_type: str,
    sensitivity: str,
    response_size: str,
    recommended_provider: str,
    recommended_model_role: str,
    route_reason: str,
    fallback_provider: Optional[str] = "gpt_5_5_premium_fallback",
    fallback_model_role: Optional[str] = "fallback_high_quality",
    auxiliary_provider: Optional[str] = None,
    auxiliary_model_role: Optional[str] = None,
    escalation_reason: str = "",
    image_generation_performed: bool = False,
) -> Dict[str, Any]:
    return {
        "raw_command": raw_command,
        "detected_task_type": task_type,
        "sensitivity": sensitivity,
        "response_size": response_size,
        "recommended_provider": recommended_provider,
        "recommended_model_role": recommended_model_role,
        "fallback_provider": fallback_provider,
        "fallback_model_role": fallback_model_role,
        "auxiliary_provider": auxiliary_provider,
        "auxiliary_model_role": auxiliary_model_role,
        "target_distribution": dict(TARGET_DISTRIBUTION),
        "deepseek_target_share": DEEPSEEK_TARGET_SHARE,
        "mini_5_4_target_share": MINI_5_4_TARGET_SHARE,
        "gpt_5_5_target_share": GPT_5_5_TARGET_SHARE,
        "cost_sensitivity": "high" if recommended_provider != "gpt_5_5_premium_fallback" else "quality_priority",
        "quality_sensitivity": _quality_sensitivity(task_type, sensitivity, response_size),
        "privacy_risk": _privacy_risk(task_type, sensitivity),
        "route_reason": route_reason,
        "escalation_reason": escalation_reason,
        "raw_user_text_logged": False,
        "safe_derived_signals_only": True,
        "routing_changed": False,
        "real_model_switch_performed": False,
        "real_api_call_performed": False,
        "billing_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "image_generation_performed": image_generation_performed,
        "read_only": True,
        "safe_reason": "Preview only; no real provider switch, API call, billing write, raw text log, DB write, memory write, or file write is performed.",
    }


def preview_model_route(
    command: str,
    task_type: str = "",
    sensitivity: str = "normal",
    response_size: str = "medium",
) -> Dict[str, Any]:
    raw_command = command or ""
    detected = _detect_task_type(raw_command, task_type or "")
    safe_sensitivity = sensitivity if sensitivity in {"normal", "high", "privacy", "safety"} else "normal"
    safe_response_size = response_size if response_size in {"short", "medium", "long", "workspace_large"} else "medium"

    if detected in {"critical_debug"}:
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "gpt_5_5_premium_fallback",
            "fallback_high_quality",
            "critical quality preview recommends rare premium fallback metadata",
            fallback_provider="deepseek_primary",
            fallback_model_role="primary_reasoning",
            escalation_reason="critical debugging or architecture-level failure",
        )
    if detected == "image_generation_request":
        payload = _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "image_api_future",
            "image_generation_future",
            "future image generation request; only metadata is previewed",
            auxiliary_provider="mini_5_4_support",
            auxiliary_model_role="image_understanding_future",
            escalation_reason="real image generation is disabled in scaffold",
            image_generation_performed=False,
        )
        payload["planning_provider"] = "deepseek_primary"
        return payload
    if detected in {"image_understanding_request", "sketch_understanding_request"}:
        model_role = "sketch_interpreter_future" if detected == "sketch_understanding_request" else "multimodal_reader_future"
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "mini_5_4_support",
            model_role,
            "future lightweight multimodal understanding preview",
            fallback_provider="gpt_5_5_premium_fallback",
            fallback_model_role="fallback_high_quality",
            escalation_reason="rare high-quality review only if multimodal preview is uncertain",
        )
    if detected in {"visual_prompt", "dream_scene", "ambrosia_prompt"}:
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "deepseek_primary",
            "visual_prompt_planner",
            "DeepSeek plans visual prompts while Mini 5.4 may assist future image/sketch reading",
            auxiliary_provider="mini_5_4_support",
            auxiliary_model_role="multimodal_reader_future",
        )
    if detected in {"safety_sensitive", "privacy_sensitive", "permission_boundary"}:
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "deepseek_primary",
            "primary_reasoning",
            "safety and privacy take priority over cost; fallback remains rare high-quality review metadata",
            escalation_reason="privacy/safety sensitive route",
        )
    if detected == "luxway":
        payload = _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "deepseek_primary",
            "luxway_preview",
            "Luxway preview stays on DeepSeek and requires permission/safety boundary metadata",
        )
        payload["real_phone_access_enabled"] = False
        payload["permission_boundary_required"] = True
        return payload
    if detected in {"workspace", "report_writer", "cv_builder", "presentation_planner"}:
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "deepseek_primary",
            "workspace_writer",
            "default low-cost workspace/document writing route",
        )
    if detected in {"codex_prompt", "project_planning", "code"}:
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "deepseek_primary",
            "primary_reasoning",
            "DeepSeek handles code/project planning by default; GPT-5.5 is rare critical fallback metadata",
        )
    if detected == "unknown":
        return _base_payload(
            raw_command,
            detected,
            safe_sensitivity,
            safe_response_size,
            "deepseek_primary",
            "primary_reasoning",
            "unknown route defaults to safe low-cost primary and may ask clarification",
            escalation_reason="low confidence; ask clarification if needed",
        )
    return _base_payload(
        raw_command,
        detected,
        safe_sensitivity,
        safe_response_size,
        "deepseek_primary",
        "primary_reasoning",
        "default low-cost main brain",
    )


def model_router_config() -> Dict[str, Any]:
    return {
        "model_roles": list(MODEL_ROLE_REGISTRY.values()),
        "task_types": list(TASK_TYPES),
        "target_distribution": dict(TARGET_DISTRIBUTION),
        "deepseek_target_share": DEEPSEEK_TARGET_SHARE,
        "mini_5_4_target_share": MINI_5_4_TARGET_SHARE,
        "gpt_5_5_target_share": GPT_5_5_TARGET_SHARE,
        "privacy_policy": dict(ROUTER_PRIVACY_POLICY),
        "routing_changed": False,
        "real_model_switch_performed": False,
        "real_api_call_performed": False,
        "read_only": True,
    }


def model_router_status() -> Dict[str, Any]:
    return {
        "model_router_ready": True,
        "read_only": True,
        "routing_changed": False,
        "real_model_switch_performed": False,
        "real_api_call_performed": False,
        "billing_write_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "raw_user_text_logged": False,
        "deepseek_target_share": DEEPSEEK_TARGET_SHARE,
        "mini_5_4_target_share": MINI_5_4_TARGET_SHARE,
        "gpt_5_5_target_share": GPT_5_5_TARGET_SHARE,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }
