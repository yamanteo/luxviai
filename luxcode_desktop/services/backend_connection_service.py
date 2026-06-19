from __future__ import annotations

from pathlib import Path

from luxcode_desktop.api.client import LuxCodeApiClient
from luxcode_runtime_settings import get_runtime_status


def backend_readiness(
    client: LuxCodeApiClient,
    repository_root: str,
) -> dict[str, str]:
    try:
        status = client.status(repository_root)
    except Exception as exc:
        return {
            "Backend": "disconnected",
            "Reason": str(exc),
        }

    runtime = get_runtime_status(Path(repository_root))
    providers = runtime.get("providers", {})

    def provider_state(name: str) -> str:
        item = providers.get(name, {})
        if not item.get("enabled"):
            return "disabled"
        return "ready" if item.get("ready") else "incomplete"

    return {
        "Backend": "connected" if status.get("ok") else "disconnected",
        "Persistent Runtime": str(runtime.get("status", "unknown")),
        "Secure Storage": str(runtime.get("storage", "unknown")),
        "Tier 0": "ready",
        "Local Worker": (
            "ready"
            if status.get("local_worker_connected", True)
            else "unavailable"
        ),
        "Gemini Persistent": provider_state("gemini"),
        "OpenRouter Persistent": provider_state("openrouter"),
        "DeepSeek Chat Persistent": provider_state("deepseek_chat"),
        "Direct DeepSeek": provider_state("direct_deepseek"),
        "Whale Bridge": provider_state("codewhale"),
        "Codex Bridge": provider_state("codex"),
        "Working Copy Service": (
            "ready"
            if status.get("working_copy_service_ready")
            else "missing"
        ),
        "Sandbox Service": (
            "ready"
            if status.get("sandbox_service_ready")
            else "missing"
        ),
        "Integration Service": (
            "ready"
            if status.get("integration_service_ready")
            else "missing"
        ),
    }
