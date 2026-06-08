from __future__ import annotations

from typing import Any, Dict, List


def _endpoint(
    path: str,
    method: str,
    layer: str,
    purpose: str,
    smoke_covered: bool = True,
    future_integration: bool = False,
    risk_note: str = "read-only scaffold endpoint",
    status: str = "available",
) -> Dict[str, Any]:
    return {
        "path": path,
        "method": method,
        "layer": layer,
        "purpose": purpose,
        "read_only": True,
        "smoke_covered": smoke_covered,
        "real_action_enabled": False,
        "future_integration": future_integration,
        "risk_note": risk_note,
        "status": status,
    }


ENDPOINT_GROUPS: Dict[str, List[Dict[str, Any]]] = {
    "agent_layer_14": [
        _endpoint("/agent/capabilities", "GET", "14", "personal agent capability registry"),
        _endpoint("/memory/schema", "GET", "14", "multimodal memory schema"),
        _endpoint("/memory/preview_signal", "POST", "14", "memory signal preview"),
        _endpoint("/agent/preview_intent", "POST", "14", "agent intent and memory preview"),
        _endpoint("/agent/plan_action", "POST", "14", "read-only action plan"),
        _endpoint("/agent/analyze", "POST", "14", "agent analysis hub"),
        _endpoint("/router/preview", "POST", "14", "router decision preview"),
        _endpoint("/debug/layer14-status", "GET", "14", "layer 14 status"),
    ],
    "workspace_layer_15": [
        _endpoint("/workspace/schema", "GET", "15", "workspace block schema"),
        _endpoint("/debug/workspace/sample", "GET", "15", "sample workspace preview"),
        _endpoint("/workspace/preview", "POST", "15", "workspace preview"),
        _endpoint("/workspace/separation-preview", "POST", "15", "command/content separation preview"),
        _endpoint("/workspace/parse-command", "POST", "15", "workspace command parser"),
        _endpoint("/workspace/export-preview", "POST", "15", "export-clean preview", future_integration=True, risk_note="real export/file integration later"),
        _endpoint("/workspace/context-preview", "POST", "15", "evaluator/project context preview"),
        _endpoint("/workspace/builder-preview", "POST", "15", "CV/report/presentation builder preview"),
        _endpoint("/debug/workspace-status", "GET", "15", "workspace status"),
    ],
    "visual_layer_16": [
        _endpoint("/visual/styles", "GET", "16", "visual style registry"),
        _endpoint("/visual/style-preview", "POST", "16", "visual style preview"),
        _endpoint("/visual/ratio-preview", "POST", "16", "style ratio preview"),
        _endpoint("/visual/ambrosia-preview", "POST", "16", "Ambrosia state preview"),
        _endpoint("/visual/dream-scene-preview", "POST", "16", "Dream Scene state preview"),
        _endpoint("/visual/scene-lock-preview", "POST", "16", "Scene Lock preview"),
        _endpoint("/visual/prompt-preview", "POST", "16", "visual prompt preview", future_integration=True, risk_note="real image API later"),
        _endpoint("/debug/visual-status", "GET", "16", "visual status"),
    ],
    "voice_audio_layer_17": [
        _endpoint("/voice/modes", "GET", "17", "voice mode registry"),
        _endpoint("/voice/preview-mode", "POST", "17", "voice and writing speed preview"),
        _endpoint("/debug/voice-status", "GET", "17", "voice status"),
        _endpoint("/audio/signal-schema", "GET", "17", "audio signal schema"),
        _endpoint("/audio/preview-signal", "POST", "17", "audio signal preview"),
        _endpoint("/debug/audio-status", "GET", "17", "audio status"),
        _endpoint("/audio/privacy-boundary-preview", "POST", "17", "audio privacy boundary"),
        _endpoint("/voice/night-radio-preview", "POST", "17", "night radio voice preview", future_integration=True, risk_note="real voice integration later"),
        _endpoint("/debug/voice-audio-status", "GET", "17", "voice/audio status"),
    ],
    "luxway_layer_18": [
        _endpoint("/luxway/capabilities", "GET", "18", "Luxway capability registry"),
        _endpoint("/luxway/preview-command", "POST", "18", "Luxway command preview"),
        _endpoint("/debug/luxway-status", "GET", "18", "Luxway base status"),
        _endpoint("/luxway/permission-model", "GET", "18", "Android/iOS permission model"),
        _endpoint("/luxway/permission-preview", "POST", "18", "platform permission preview"),
        _endpoint("/luxway/weekly-report-schema", "GET", "18", "weekly phone report schema"),
        _endpoint("/luxway/weekly-report-preview", "POST", "18", "weekly phone report preview", future_integration=True, risk_note="real Luxway platform integration later"),
        _endpoint("/luxway/data-preview", "POST", "18", "app/storage/message/mail/calendar preview", future_integration=True, risk_note="real app/storage/message/mail/calendar access later"),
        _endpoint("/luxway/device-safety-preview", "POST", "18", "device safety boundary"),
        _endpoint("/debug/luxway-full-status", "GET", "18", "Luxway full status"),
    ],
    "model_router_layer_19": [
        _endpoint("/router/model-config", "GET", "19", "model router config"),
        _endpoint("/router/model-preview", "POST", "19", "model route preview"),
        _endpoint("/debug/model-router-status", "GET", "19", "model router status"),
        _endpoint("/router/hint-preview", "POST", "19", "router hint expansion"),
        _endpoint("/router/cost-privacy-policy", "GET", "19", "cost privacy policy"),
        _endpoint("/router/cost-preview", "POST", "19", "cost privacy preview"),
        _endpoint("/router/safe-memory-policy", "GET", "19", "safe memory policy"),
        _endpoint("/router/memory-retrieval-preview", "POST", "19", "safe memory retrieval preview"),
        _endpoint("/router/simulation-preview", "POST", "19", "routing simulation", future_integration=True, risk_note="real model routing later"),
        _endpoint("/debug/model-router-full-status", "GET", "19", "model router full status"),
    ],
    "production_layer_20": [
        _endpoint("/debug/production-hardening-status", "GET", "20", "production hardening status"),
        _endpoint("/debug/backlog-registry", "GET", "20", "backlog registry"),
        _endpoint("/debug/system-control-audit", "GET", "20", "system control audit"),
        _endpoint("/debug/endpoint-coverage", "GET", "20", "endpoint coverage matrix"),
    ],
    "development_layer_24": [
        _endpoint("/debug/fault-report-status", "GET", "24", "Lux fault report status"),
        _endpoint("/debug/fault-report-registry", "GET", "24", "Lux fault report registry"),
        _endpoint("/debug/fault-report-preview", "GET", "24", "Lux fault report preview"),
        _endpoint("/debug/fault-report-preview", "POST", "24", "fault report filtered preview"),
        _endpoint("/debug/fault-report-intelligence-status", "GET", "24", "fault report intelligence status"),
        _endpoint("/debug/fault-report-intelligence-registry", "GET", "24", "fault report intelligence registry"),
        _endpoint("/debug/fault-report-intelligence-preview", "POST", "24", "fault report intelligence preview"),
        _endpoint("/debug/investigation-context-status", "GET", "24.2", "investigation context status"),
        _endpoint("/debug/investigation-context-registry", "GET", "24.2", "investigation context registry"),
        _endpoint("/debug/investigation-context-preview", "POST", "24.2", "investigation context preview"),
    ],
}


def endpoint_coverage_matrix() -> Dict[str, Any]:
    all_endpoints = [endpoint for group in ENDPOINT_GROUPS.values() for endpoint in group]
    smoke_covered = [endpoint for endpoint in all_endpoints if endpoint["smoke_covered"]]
    read_only = [endpoint for endpoint in all_endpoints if endpoint["read_only"]]
    future = [endpoint for endpoint in all_endpoints if endpoint["future_integration"]]
    manual = [
        {
            "path": "/ws/chat",
            "method": "WEBSOCKET",
            "layer": "legacy_chat_runtime",
            "reason": "manual/live runtime check; stop/durdur fix is backlog-only in Layer 20.3",
        },
        {
            "path": "/chat",
            "method": "POST",
            "layer": "legacy_chat_runtime",
            "reason": "covered by basic smoke shape, but live streaming behavior remains manual/backlog-sensitive",
        },
    ]
    return {
        "status": "coverage_preview_ready",
        "read_only": True,
        "real_fix_performed": False,
        "endpoint_groups": ENDPOINT_GROUPS,
        "total_endpoint_count": len(all_endpoints),
        "smoke_covered_count": len(smoke_covered),
        "read_only_count": len(read_only),
        "future_integration_count": len(future),
        "uncovered_or_manual_check": manual,
        "backlog_related": [
            "stop/durdur final block leak",
            "long answer final bulk injection risk",
            "typewriter queue clear future check",
            "websocket late done ignore future check",
            "fallback response guard future check",
        ],
        "recommended_next_checks": [
            "Keep endpoint matrix synchronized with new scaffold endpoints.",
            "Use manual checks for live stream and stop behavior until the dedicated fix layer.",
            "Keep future integration endpoints read-only until explicit real integration work begins.",
        ],
        "future_integrations": [
            "real export",
            "image API",
            "voice",
            "Luxway platform",
            "model routing",
        ],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
    }
