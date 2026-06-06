from __future__ import annotations

from typing import Any, Dict, List


BACKLOG_ITEMS: List[Dict[str, Any]] = [
    {
        "id": "stop_final_block_leak",
        "title": "stop/durdur final block leak",
        "group": "stream_and_stop_backlog",
        "priority": "high",
        "status": "backlog",
        "safe_note": "Track only in Layer 20.1; no stream/typewriter fix is performed here.",
    },
    {
        "id": "long_answer_final_bulk_injection_risk",
        "title": "long answer final bulk injection risk",
        "group": "stream_and_stop_backlog",
        "priority": "high",
        "status": "backlog",
        "safe_note": "Future check should verify late/final payloads are ignored after stop.",
    },
    {
        "id": "typewriter_queue_clear_future_check",
        "title": "typewriter queue clear future check",
        "group": "stream_and_stop_backlog",
        "priority": "medium",
        "status": "backlog",
        "safe_note": "Future check only; static/index.html runtime is untouched in this layer.",
    },
    {
        "id": "websocket_late_done_ignore_future_check",
        "title": "websocket late done ignore future check",
        "group": "stream_and_stop_backlog",
        "priority": "medium",
        "status": "backlog",
        "safe_note": "Future WebSocket lifecycle guard review.",
    },
    {
        "id": "fallback_response_guard_future_check",
        "title": "fallback response guard future check",
        "group": "stream_and_stop_backlog",
        "priority": "medium",
        "status": "backlog",
        "safe_note": "Future HTTP fallback abort/ignore review.",
    },
    {
        "id": "mobile_ui_polish",
        "title": "mobile UI polish",
        "group": "ui_mobile_polish",
        "priority": "medium",
        "status": "backlog",
        "safe_note": "Layout polish only, no chat runtime change in this layer.",
    },
    {
        "id": "debug_panel_growing_too_large",
        "title": "debug panel growing too large",
        "group": "debug_panel_health",
        "priority": "medium",
        "status": "backlog",
        "safe_note": "Future split or navigation cleanup may be useful.",
    },
    {
        "id": "real_export_integration_later",
        "title": "real export integration later",
        "group": "real_export_future",
        "priority": "planned",
        "status": "future",
        "safe_note": "Current workspace export is preview-only.",
    },
    {
        "id": "real_image_generation_later",
        "title": "real image generation later",
        "group": "real_image_api_future",
        "priority": "planned",
        "status": "future",
        "safe_note": "Current visual system is prompt/schema preview-only.",
    },
    {
        "id": "real_voice_integration_later",
        "title": "real voice integration later",
        "group": "real_voice_future",
        "priority": "planned",
        "status": "future",
        "safe_note": "Current voice/audio system has no TTS, STT, mic, or recording.",
    },
    {
        "id": "real_luxway_platform_integration_later",
        "title": "real Luxway platform integration later",
        "group": "real_luxway_platform_future",
        "priority": "planned",
        "status": "future",
        "safe_note": "Current Luxway system has no real phone/platform access.",
    },
    {
        "id": "real_model_routing_later",
        "title": "real model routing later",
        "group": "model_router_future_integration",
        "priority": "planned",
        "status": "future",
        "safe_note": "Current model router is read-only metadata preview.",
    },
]


RISK_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "stream_and_stop_backlog",
        "title": "Stream and stop backlog",
        "risk_level": "high",
        "watch_items": [
            "stop/durdur final block leak",
            "long answer final bulk injection risk",
            "typewriter queue clear future check",
            "websocket late done ignore future check",
            "fallback response guard future check",
        ],
    },
    {
        "id": "ui_mobile_polish",
        "title": "UI and mobile polish",
        "risk_level": "medium",
        "watch_items": ["mobile UI polish"],
    },
    {
        "id": "debug_panel_health",
        "title": "Debug panel health",
        "risk_level": "medium",
        "watch_items": ["debug panel growing too large"],
    },
    {
        "id": "endpoint_smoke_coverage",
        "title": "Endpoint smoke coverage",
        "risk_level": "low",
        "watch_items": ["keep read-only endpoints covered by smoke checks"],
    },
    {
        "id": "privacy_security_audit",
        "title": "Privacy and security audit",
        "risk_level": "high",
        "watch_items": ["raw data logging guards", "permission and confirmation boundaries"],
    },
    {
        "id": "model_router_future_integration",
        "title": "Model router future integration",
        "risk_level": "medium",
        "watch_items": ["real model routing later"],
    },
    {
        "id": "real_export_future",
        "title": "Real export future",
        "risk_level": "medium",
        "watch_items": ["real export integration later"],
    },
    {
        "id": "real_image_api_future",
        "title": "Real image API future",
        "risk_level": "medium",
        "watch_items": ["real image generation later"],
    },
    {
        "id": "real_voice_future",
        "title": "Real voice future",
        "risk_level": "medium",
        "watch_items": ["real voice integration later"],
    },
    {
        "id": "real_luxway_platform_future",
        "title": "Real Luxway platform future",
        "risk_level": "high",
        "watch_items": ["real Luxway platform integration later"],
    },
    {
        "id": "performance_monitoring_future",
        "title": "Performance monitoring future",
        "risk_level": "medium",
        "watch_items": ["latency and endpoint health monitoring later"],
    },
    {
        "id": "deploy_hardening_future",
        "title": "Deploy hardening future",
        "risk_level": "medium",
        "watch_items": ["Render health and dependency checks later"],
    },
    {
        "id": "error_handling_future",
        "title": "Error handling future",
        "risk_level": "medium",
        "watch_items": ["fallback and degraded-mode responses later"],
    },
    {
        "id": "user_test_readiness",
        "title": "User test readiness",
        "risk_level": "low",
        "watch_items": ["manual test checklist before wider usage"],
    },
]


RECOMMENDED_NEXT_CHECKS = [
    "Keep stop/durdur final block leak visible until a dedicated fix layer.",
    "Review debug panel size before adding more large sections.",
    "Preserve read-only flags on all scaffold endpoints.",
    "Plan production hardening without changing stream/typewriter runtime in this layer.",
]


def _base_status() -> Dict[str, Any]:
    return {
        "layer": "20",
        "status": "planning_scaffold",
        "read_only": True,
        "real_fix_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "db_write_performed": False,
        "memory_write_performed": False,
        "file_write_performed": False,
        "backlog_items": BACKLOG_ITEMS,
        "risk_groups": RISK_GROUPS,
        "recommended_next_checks": RECOMMENDED_NEXT_CHECKS,
        "safe_next_step": "Use this registry to choose the next isolated hardening layer without changing live chat flow.",
    }


def production_hardening_status() -> Dict[str, Any]:
    status = _base_status()
    status.update(
        {
            "name": "Production Hardening / Backlog Registry scaffold",
            "registry_groups": [group["id"] for group in RISK_GROUPS],
            "focus": "read-only production risk and backlog snapshot",
        }
    )
    return status


def backlog_registry() -> Dict[str, Any]:
    registry = _base_status()
    registry.update(
        {
            "name": "Backlog Registry",
            "backlog_count": len(BACKLOG_ITEMS),
            "group_count": len(RISK_GROUPS),
        }
    )
    return registry
