"""Read-only router decision preview scaffold."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any, Dict

from agent_scaffold import analyze_agent_request


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


def _contains_any(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords)


def _mode_from_analysis(user_text: str, analysis: Dict[str, Any]) -> str:
    normalized = _normalize_text(user_text)
    if _contains_any(normalized, "hassas", "mahrem", "gizli", "kriz", "tehlike", "travma"):
        return "safety_sensitive"
    if _contains_any(normalized, "ruya", "sahne", "kamera", "cizim"):
        return "dream_scene"
    if _contains_any(normalized, "ambrosia"):
        return "ambrosia"
    if _contains_any(normalized, "gorsel", "amber", "pixel", "imza"):
        return "visual_style_memory"
    return str(analysis.get("recommended_mode") or "normal_chat")


def _routing_shape(mode: str) -> Dict[str, Any]:
    defaults = {
        "response_style": "normal",
        "output_type": "chat_answer",
        "model_hint": "deepseek_default",
        "should_use_agent": False,
        "should_use_memory_preview": False,
        "should_use_workspace": False,
        "should_use_visual_system": False,
        "should_use_luxway": False,
        "should_use_audio_future": False,
        "should_require_confirmation": False,
    }
    by_mode = {
        "personal_agent": {
            "response_style": "step_by_step",
            "output_type": "action_plan",
            "model_hint": "deepseek_reasoning",
            "should_use_agent": True,
        },
        "luxway_planning": {
            "response_style": "step_by_step",
            "output_type": "luxway_plan",
            "model_hint": "deepseek_reasoning",
            "should_use_agent": True,
            "should_use_luxway": True,
            "should_require_confirmation": True,
        },
        "workspace": {
            "response_style": "professional",
            "output_type": "document_draft",
            "model_hint": "deepseek_reasoning",
            "should_use_workspace": True,
        },
        "cv_builder": {
            "response_style": "professional",
            "output_type": "cv_builder",
            "model_hint": "deepseek_reasoning",
            "should_use_workspace": True,
        },
        "report_builder": {
            "response_style": "professional",
            "output_type": "report_builder",
            "model_hint": "deepseek_reasoning",
            "should_use_workspace": True,
        },
        "presentation_builder": {
            "response_style": "document_builder",
            "output_type": "presentation_plan",
            "model_hint": "deepseek_reasoning",
            "should_use_workspace": True,
        },
        "visual_style_memory": {
            "response_style": "creative_visual",
            "output_type": "visual_prompt",
            "model_hint": "image_api_future",
            "should_use_memory_preview": True,
            "should_use_visual_system": True,
        },
        "ambrosia": {
            "response_style": "creative_visual",
            "output_type": "ambrosia_state",
            "model_hint": "image_api_future",
            "should_use_memory_preview": True,
            "should_use_visual_system": True,
        },
        "dream_scene": {
            "response_style": "creative_visual",
            "output_type": "dream_scene_state",
            "model_hint": "image_api_future",
            "should_use_memory_preview": True,
            "should_use_visual_system": True,
        },
        "audio_signal_future": {
            "response_style": "concise",
            "output_type": "memory_preview",
            "model_hint": "audio_analysis_future",
            "should_use_memory_preview": True,
            "should_use_audio_future": True,
        },
        "safety_sensitive": {
            "response_style": "safety_careful",
            "output_type": "chat_answer",
            "model_hint": "deepseek_default",
            "should_require_confirmation": True,
        },
    }
    result = dict(defaults)
    result.update(by_mode.get(mode, {}))
    return result


def preview_router_decision(user_text: str, source_modality: str = "text") -> Dict[str, Any]:
    """Preview the future router decision without changing chat behavior."""
    analysis = analyze_agent_request(user_text, source_modality)
    mode = _mode_from_analysis(user_text, analysis)
    shape = _routing_shape(mode)
    should_require_confirmation = bool(shape["should_require_confirmation"]) or bool(analysis.get("requires_user_confirmation"))

    return {
        "router_id": str(uuid.uuid4()),
        "recommended_mode": mode,
        "response_style": shape["response_style"],
        "output_type": shape["output_type"],
        "model_hint": shape["model_hint"],
        "should_use_agent": bool(shape["should_use_agent"]),
        "should_use_memory_preview": bool(shape["should_use_memory_preview"]),
        "should_use_workspace": bool(shape["should_use_workspace"]),
        "should_use_visual_system": bool(shape["should_use_visual_system"]),
        "should_use_luxway": bool(shape["should_use_luxway"]),
        "should_use_audio_future": bool(shape["should_use_audio_future"]),
        "should_require_confirmation": should_require_confirmation,
        "risk_level": analysis.get("risk_level", "low"),
        "permissions_needed": list(analysis.get("permissions_needed", [])),
        "can_execute_now": False,
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "reason": f"Router preview selected {mode} from read-only agent analysis; no routing or execution was performed.",
    }
