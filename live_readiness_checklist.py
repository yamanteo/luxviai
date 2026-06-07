from __future__ import annotations

from typing import Any, Dict, List


READINESS_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "core_chat_health",
        "title": "Core chat health",
        "status": "manual_check_required",
        "note": "Basic chat is covered by smoke shape; live send/receive remains a manual readiness check.",
    },
    {
        "id": "debug_panel_health",
        "title": "Debug panel health",
        "status": "ready_for_preview",
        "note": "Debug panel is available for read-only preview endpoints.",
    },
    {
        "id": "layer_status_endpoints",
        "title": "Layer status endpoints",
        "status": "ready_for_preview",
        "note": "Layer 14-20 status and audit endpoints are present.",
    },
    {
        "id": "smoke_test_coverage",
        "title": "Smoke test coverage",
        "status": "ready_for_preview",
        "note": "Smoke suite is expected to pass before live review.",
    },
    {
        "id": "privacy_safety_boundaries",
        "title": "Privacy and safety boundaries",
        "status": "ready_for_preview",
        "note": "Agent, Luxway, audio, memory, and cost privacy boundaries are preview-only.",
    },
    {
        "id": "preview_only_integrations",
        "title": "Preview-only integrations",
        "status": "preview_only",
        "note": "Workspace export, image, voice, Luxway, model routing, and memory retrieval remain preview-only.",
    },
    {
        "id": "future_real_integrations",
        "title": "Future real integrations",
        "status": "blocked_for_real_launch",
        "note": "Real integrations need dedicated safety, permission, and implementation layers.",
    },
    {
        "id": "known_backlog",
        "title": "Known backlog",
        "status": "backlog_open",
        "note": "Stop/durdur final block leak remains intentionally unfixed in this layer.",
    },
    {
        "id": "manual_live_checks",
        "title": "Manual live checks",
        "status": "manual_check_required",
        "note": "Live Render URLs and stop behavior require manual verification later.",
    },
]


READY_ITEMS = [
    "Layer 14-20 scaffold status endpoints exist",
    "smoke_check passing",
    "debug panel available",
    "read-only safety boundaries present",
]


PREVIEW_ONLY_ITEMS = [
    "workspace export preview only; real export not enabled",
    "image generation preview only; real image API not enabled",
    "voice/audio preview only; real voice not enabled",
    "Luxway phone access preview only; real Luxway platform not enabled",
    "model routing preview only; real model routing not enabled",
    "memory retrieval preview only; real memory read/write not enabled",
]


MANUAL_CHECK_ITEMS = [
    "live /health",
    "live /debug/agent-panel",
    "live /debug/system-control-audit",
    "live /debug/endpoint-coverage",
    "live /debug/live-readiness",
    "normal chat send/receive",
    "long answer stop behavior manual check later",
]


BLOCKED_FOR_REAL_LAUNCH_ITEMS = [
    "real export not enabled",
    "real image API not enabled",
    "real voice not enabled",
    "real Luxway platform not enabled",
    "real model routing not enabled",
]


KNOWN_BACKLOG_ITEMS = [
    "stop/durdur final block leak",
]


def live_readiness_checklist() -> Dict[str, Any]:
    return {
        "status": "readiness_preview_ready",
        "read_only": True,
        "real_fix_performed": False,
        "readiness_groups": READINESS_GROUPS,
        "ready_items": READY_ITEMS,
        "preview_only_items": PREVIEW_ONLY_ITEMS,
        "manual_check_items": MANUAL_CHECK_ITEMS,
        "blocked_for_real_launch_items": BLOCKED_FOR_REAL_LAUNCH_ITEMS,
        "known_backlog_items": KNOWN_BACKLOG_ITEMS,
        "recommended_manual_checks": [
            "Open the live /health endpoint after deployment.",
            "Open the live debug panel and verify status buttons load JSON.",
            "Send a normal chat message and verify response shape.",
            "Run the long answer stop behavior check in a dedicated fix/audit layer later.",
        ],
        "safe_next_step": "Use this checklist before live review; keep real fixes for explicit dedicated layers.",
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "db_write_performed": False,
        "memory_write_performed": False,
        "file_write_performed": False,
    }
