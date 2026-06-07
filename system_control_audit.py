from __future__ import annotations

from typing import Any, Dict, List

from production_hardening_registry import BACKLOG_ITEMS, RISK_GROUPS


CHECKED_LAYERS: List[Dict[str, str]] = [
    {"layer": "14", "name": "Personal Agent"},
    {"layer": "15", "name": "Workspace"},
    {"layer": "16", "name": "Visual"},
    {"layer": "17", "name": "Voice / Audio"},
    {"layer": "18", "name": "Luxway"},
    {"layer": "19", "name": "Model Router"},
    {"layer": "20", "name": "Production Hardening"},
]


AVAILABLE_STATUS_ENDPOINTS = [
    "/debug/layer14-status",
    "/debug/workspace-status",
    "/debug/visual-status",
    "/debug/voice-audio-status",
    "/debug/luxway-full-status",
    "/debug/model-router-full-status",
    "/debug/production-hardening-status",
    "/debug/backlog-registry",
]


MISSING_OR_FUTURE_INTEGRATIONS = [
    "real export/file integration later",
    "real image API later",
    "real voice integration later",
    "real Luxway platform integration later",
    "real model routing later",
    "stop/durdur final block leak fix later",
]


def system_control_audit() -> Dict[str, Any]:
    backlog_titles = [str(item.get("title", "")) for item in BACKLOG_ITEMS]
    high_risk_groups = [
        {
            "id": group.get("id"),
            "title": group.get("title"),
            "risk_level": group.get("risk_level"),
        }
        for group in RISK_GROUPS
        if group.get("risk_level") == "high"
    ]
    return {
        "system_name": "Luxviai",
        "status": "scaffold_audit_ready",
        "read_only": True,
        "real_fix_performed": False,
        "checked_layers": CHECKED_LAYERS,
        "available_status_endpoints": AVAILABLE_STATUS_ENDPOINTS,
        "scaffold_health_summary": {
            "layers_checked": [item["layer"] for item in CHECKED_LAYERS],
            "status_endpoint_count": len(AVAILABLE_STATUS_ENDPOINTS),
            "all_reported_as_scaffold_or_planning": True,
            "real_integrations_enabled": False,
        },
        "risk_summary": {
            "high_risk_groups": high_risk_groups,
            "stream_stop_backlog_open": True,
            "privacy_security_audit_open": True,
        },
        "backlog_summary": {
            "items": backlog_titles,
            "count": len(backlog_titles),
            "stop_durdur_status": "backlog_only",
        },
        "missing_or_future_integrations": MISSING_OR_FUTURE_INTEGRATIONS,
        "recommended_next_actions": [
            "Keep stop/durdur final block leak for a dedicated fix layer.",
            "Use status endpoints before selecting the next production hardening task.",
            "Avoid enabling real integrations until their permission and safety boundaries are tested.",
            "Keep scaffold endpoints read-only until an explicit integration layer is planned.",
        ],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "db_write_performed": False,
        "memory_write_performed": False,
        "file_write_performed": False,
    }
