from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

COMMAND_ROUTING_TABLE: Dict[str, Dict[str, Any]] = {
    "repo durumunu analiz et": {
        "route_family": "engineering",
        "primary_layer": "35",
        "secondary_layers": ["34", "37"],
        "recommended_preview_chain": ["34", "35", "37"],
        "requires_confirmation": False,
        "safe_next_step": "Produce repo status summary and highlight alignment issues.",
        "handoff_target": "github",
    },
    "bu hatayı bul": {
        "route_family": "investigation",
        "primary_layer": "36",
        "secondary_layers": ["35", "37"],
        "recommended_preview_chain": ["35", "36", "37", "39"],
        "requires_confirmation": False,
        "safe_next_step": "Identify likely fault region and recommend targeted validation.",
        "handoff_target": "terminal",
    },
    "patch planı çıkar": {
        "route_family": "patch_planning",
        "primary_layer": "38",
        "secondary_layers": ["35", "36", "40"],
        "recommended_preview_chain": ["35", "36", "38", "40"],
        "requires_confirmation": True,
        "safe_next_step": "Generate patch plan and request explicit approval before apply.",
        "handoff_target": "codex",
    },
    "testleri nasıl çalıştırmalıyım": {
        "route_family": "validation",
        "primary_layer": "37",
        "secondary_layers": ["39", "40"],
        "recommended_preview_chain": ["37", "39", "40"],
        "requires_confirmation": False,
        "safe_next_step": "Recommend smoke_check invocation and layer-specific validation.",
        "handoff_target": "terminal",
    },
    "deployment hazır mı": {
        "route_family": "release_readiness",
        "primary_layer": "41",
        "secondary_layers": ["38", "40"],
        "recommended_preview_chain": ["38", "40", "41"],
        "requires_confirmation": True,
        "safe_next_step": "Run deployment readiness checklist and surface no-go items.",
        "handoff_target": "deployment",
    },
    "iş akışı planla": {
        "route_family": "workflow_planning",
        "primary_layer": "38",
        "secondary_layers": ["36", "39"],
        "recommended_preview_chain": ["36", "38", "39"],
        "requires_confirmation": True,
        "safe_next_step": "Produce workflow preview and ask user to approve next step.",
        "handoff_target": "none",
    },
    "runtime/session devam ettir": {
        "route_family": "runtime_continuity",
        "primary_layer": "39",
        "secondary_layers": ["38", "41"],
        "recommended_preview_chain": ["39", "41"],
        "requires_confirmation": False,
        "safe_next_step": "Recommend runtime continuity preview and monitoring status.",
        "handoff_target": "terminal",
    },
    "execution yap": {
        "route_family": "execution_preview",
        "primary_layer": "40",
        "secondary_layers": ["39", "41"],
        "recommended_preview_chain": ["39", "40", "41"],
        "requires_confirmation": True,
        "safe_next_step": "Provide execution preview and explicitly block real execution.",
        "handoff_target": "none",
    },
    "operasyonları izle": {
        "route_family": "operations_monitoring",
        "primary_layer": "41",
        "secondary_layers": ["39", "40"],
        "recommended_preview_chain": ["39", "40", "41"],
        "requires_confirmation": False,
        "safe_next_step": "Provide operations preview and safety summary.",
        "handoff_target": "none",
    },
    "rollback gerekir mi": {
        "route_family": "rollback_assessment",
        "primary_layer": "41",
        "secondary_layers": ["38", "40"],
        "recommended_preview_chain": ["38", "40", "41"],
        "requires_confirmation": True,
        "safe_next_step": "Recommend rollback assessment and preserve fallback.",
        "handoff_target": "none",
    },
    "bunu codex’e gönderilecek prompta çevir": {
        "route_family": "codex_handoff",
        "primary_layer": "36",
        "secondary_layers": ["35", "37"],
        "recommended_preview_chain": ["36", "37"],
        "requires_confirmation": False,
        "safe_next_step": "Generate Codex prompt structure.",
        "handoff_target": "codex",
    },
    "whale ile devam et": {
        "route_family": "whale_handoff",
        "primary_layer": "36",
        "secondary_layers": ["35", "38"],
        "recommended_preview_chain": ["36", "38"],
        "requires_confirmation": False,
        "safe_next_step": "Route to Whale for large scaffold guidance.",
        "handoff_target": "whale",
    },
    "ai studio / cline için kaynak dosya seç": {
        "route_family": "source_selection",
        "primary_layer": "34",
        "secondary_layers": ["35", "37"],
        "recommended_preview_chain": ["34", "35", "37"],
        "requires_confirmation": False,
        "safe_next_step": "Identify source files and prepare context pack.",
        "handoff_target": "gemini_cline",
    },
    "luxviai duygusal ai katmanı planla": {
        "route_family": "emotional_ai",
        "primary_layer": "35",
        "secondary_layers": ["36", "37"],
        "recommended_preview_chain": ["35", "36"],
        "requires_confirmation": False,
        "safe_next_step": "Define emotional AI advisory scope.",
        "handoff_target": "none",
    },
}

DEFAULT_ROUTER_OUTPUT: Dict[str, Any] = {
    "route_family": "unknown",
    "primary_layer": "34",
    "secondary_layers": [],
    "recommended_preview_chain": ["34"],
    "requires_confirmation": True,
    "real_execution_blocked": True,
    "safe_next_step": "Review the Layer 34–41 master router consolidation plan and confirm routing before proceeding.",
    "handoff_target": "none",
    "read_only": True,
}

ROUTE_FAMILY_ALIASES: Dict[str, str] = {
    "repo": "repo durumunu analiz et",
    "hata": "bu hatayı bul",
    "patch": "patch planı çıkar",
    "test": "testleri nasıl çalıştırmalıyım",
    "deployment": "deployment hazır mı",
    "iş akışı": "iş akışı planla",
    "runtime": "runtime/session devam ettir",
    "execution": "execution yap",
    "operasyon": "operasyonları izle",
    "rollback": "rollback gerekir mi",
    "codex": "bunu Codex’e gönderilecek prompta çevir",
    "whale": "Whale ile devam et",
    "ai studio": "AI Studio / Cline için kaynak dosya seç",
    "cline": "AI Studio / Cline için kaynak dosya seç",
    "duygusal": "Luxviai duygusal AI katmanı planla",
}


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", (command or "").strip().lower())


def _find_route_by_alias(command: str) -> Optional[str]:
    normalized = _normalize_command(command)
    for alias, canonical in ROUTE_FAMILY_ALIASES.items():
        if alias in normalized:
            return canonical
    return None


def build_luxcode_master_router_preview(command: str, context: Optional[str] = None) -> Dict[str, Any]:
    normalized = _normalize_command(command)
    if normalized in COMMAND_ROUTING_TABLE:
        route = COMMAND_ROUTING_TABLE[normalized].copy()
    else:
        alias = _find_route_by_alias(normalized)
        if alias and alias in COMMAND_ROUTING_TABLE:
            route = COMMAND_ROUTING_TABLE[alias].copy()
        else:
            route = DEFAULT_ROUTER_OUTPUT.copy()

    route["read_only"] = True
    route["real_execution_blocked"] = True
    route["requires_confirmation"] = bool(route.get("requires_confirmation", True))
    route["context_hint"] = (context or "")[:120]
    route["source_command"] = command
    return route


def luxcode_master_router_schema() -> Dict[str, Any]:
    return {
        "layer": "34-41",
        "name": "LuxCode Master Router Preview",
        "status": "read_only_router_scaffold",
        "route_fields": [
            "route_family",
            "primary_layer",
            "secondary_layers",
            "recommended_preview_chain",
            "requires_confirmation",
            "real_execution_blocked",
            "safe_next_step",
            "handoff_target",
            "read_only",
            "context_hint",
            "source_command",
        ],
        "safety_boundary": "Read-only router decision preview for Layer 34–41 routes. No execution, no deployment, no repository modification.",
        "read_only": True,
    }


def luxcode_master_router_status() -> Dict[str, Any]:
    return {
        "status": "router_preview_ready",
        "layers": ["34", "35", "36", "37", "38", "39", "40", "41"],
        "read_only": True,
        "real_execution_blocked": True,
        "confirmation_required_for_actions": True,
    }
