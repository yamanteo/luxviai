"""Read-only routing simulation preview scaffold."""

from __future__ import annotations

from typing import Any, Dict

from cost_privacy_policy import preview_cost_privacy
from model_router_config import preview_model_route
from safe_memory_retrieval import preview_safe_memory_retrieval


def preview_routing_simulation(
    command: str,
    scenario: str = "",
    task_type: str = "",
    sensitivity: str = "normal",
    response_size: str = "medium",
) -> Dict[str, Any]:
    raw_command = command or ""
    route = preview_model_route(raw_command, task_type, sensitivity, response_size)
    detected_task_type = str(route.get("detected_task_type", task_type or "unknown"))
    cost_policy = preview_cost_privacy(raw_command, detected_task_type, sensitivity, "")
    memory_policy = preview_safe_memory_retrieval(raw_command, detected_task_type, sensitivity, "")
    recommended_route = {
        "provider": route.get("recommended_provider"),
        "model_role": route.get("recommended_model_role"),
        "model_hint": route.get("recommended_provider"),
        "route_reason": route.get("route_reason"),
    }
    fallback_route = {
        "provider": route.get("fallback_provider"),
        "model_role": route.get("fallback_model_role"),
        "escalation_reason": route.get("escalation_reason"),
    }
    auxiliary_route = {
        "provider": route.get("auxiliary_provider"),
        "model_role": route.get("auxiliary_model_role"),
    }
    simulation_steps = [
        "Detect task type from command/scenario metadata.",
        "Preview model route using model_router_config without switching providers.",
        "Preview cost privacy policy using derived metadata only.",
        "Preview safe memory retrieval policy without reading memory.",
        "Return final route decision as invisible-to-user metadata.",
    ]
    return {
        "raw_command": raw_command,
        "scenario": scenario or "default",
        "detected_task_type": detected_task_type,
        "simulation_steps": simulation_steps,
        "recommended_route": recommended_route,
        "fallback_route": fallback_route,
        "auxiliary_route": auxiliary_route,
        "cost_policy_preview": {
            "privacy_risk": cost_policy.get("privacy_risk"),
            "safe_derived_metadata_only": cost_policy.get("safe_derived_metadata_only"),
            "billing_write_performed": cost_policy.get("billing_write_performed"),
            "blocked_metadata": cost_policy.get("blocked_metadata", []),
        },
        "memory_policy_preview": {
            "retrieval_allowed": memory_policy.get("retrieval_allowed"),
            "retrieval_reason": memory_policy.get("retrieval_reason"),
            "raw_memory_returned": memory_policy.get("raw_memory_returned"),
            "raw_sensitive_memory_returned": memory_policy.get("raw_sensitive_memory_returned"),
            "memory_read_performed": memory_policy.get("memory_read_performed"),
            "allowed_memory_types": memory_policy.get("allowed_memory_types", []),
        },
        "final_route_decision": {
            "provider": route.get("recommended_provider"),
            "model_role": route.get("recommended_model_role"),
            "real_execution": "not_performed",
            "reason": route.get("route_reason"),
        },
        "user_visible_model_choice": False,
        "routing_invisible_to_user": True,
        "raw_user_text_logged": False,
        "real_model_switch_performed": False,
        "real_api_call_performed": False,
        "billing_write_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "image_generation_performed": route.get("image_generation_performed", False),
        "read_only": True,
    }
