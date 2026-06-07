from __future__ import annotations

from typing import Any, Dict


COMPLETED_ITEMS = [
    "background_support_registry",
    "meta_intelligence_core",
    "emotional_reflection_support",
    "context_bridge_preview",
    "device_bridge_preview",
    "pointer_context_preview",
    "drive_mode_preview",
    "wake_sonic_registry",
]


COMPLETED_COMMITS = {
    "21.1": "de5f303 - Add background support registry preview",
    "21.2": "e462476 - Add meta intelligence core preview",
    "21.3": "20fabf6 - Add emotional reflection support preview",
    "21.4": "7a5b8a3 - Add context bridge preview",
    "21.5": "0f9ef55 - Add device bridge preview",
    "21.6": "e6fabe4 - Add pointer context preview",
    "21.7": "27cc05e - Add drive mode preview",
    "21.8": "e47986d - Add wake sonic preview",
}


ENDPOINT_GROUPS = {
    "21.1_background_support": [
        "GET /support/registry",
        "POST /support/preview",
        "GET /debug/support-status",
    ],
    "21.2_meta_intelligence": [
        "GET /meta/core-registry",
        "POST /meta/quality-preview",
        "GET /debug/meta-status",
    ],
    "21.3_emotional_reflection": [
        "GET /emotional/reflection-registry",
        "POST /emotional/reflection-preview",
        "GET /debug/emotional-status",
    ],
    "21.4_context_bridge": [
        "GET /context-bridge/schema",
        "POST /context-bridge/preview",
        "GET /debug/context-bridge-status",
    ],
    "21.5_device_bridge": [
        "GET /device-bridge/schema",
        "POST /device-bridge/preview",
        "GET /debug/device-bridge-status",
    ],
    "21.6_pointer_context": [
        "GET /pointer/schema",
        "POST /pointer/preview-action",
        "GET /debug/pointer-status",
    ],
    "21.7_drive_mode": [
        "GET /drive-mode/schema",
        "POST /drive-mode/preview",
        "GET /debug/drive-mode-status",
    ],
    "21.8_wake_sonic": [
        "GET /wake-sonic/schema",
        "GET /wake-sonic/registry",
        "POST /wake-sonic/preview",
        "GET /debug/wake-sonic-status",
    ],
}


SAFETY_BOUNDARIES = {
    "real_action_enabled": False,
    "action_performed": False,
    "real_send_performed": False,
    "real_export_performed": False,
    "real_print_performed": False,
    "real_file_created": False,
    "real_device_control_performed": False,
    "real_cross_page_read_performed": False,
    "real_screen_read_performed": False,
    "real_vehicle_connection_performed": False,
    "real_microphone_recording_performed": False,
    "real_wake_detection_performed": False,
    "memory_write_performed": False,
    "db_write_performed": False,
    "raw_sensitive_content_returned": False,
    "read_only": True,
}


FUTURE_CANDIDATES = [
    "Layer 22 - Future / Near-Future Premium Candidates",
    "Lux Time Twin",
    "Future Self Council",
    "Reality Layer",
    "Memory Cinema",
    "Cognitive Mirror",
    "Dream OS",
    "Personal Mythology",
    "Adaptive Interface",
    "Silent Companion Mode",
    "Personal World Model",
    "Emotional Weather",
    "Ambient Workspace",
    "Memory Sculpting",
    "Intention Timeline",
    "Autonomy Dial",
    "Ethical Boundary Soul",
    "Invisible Operator",
    "Context Rooms",
    "Aura System",
    "Finality Sense",
]


def layer21_status_snapshot() -> Dict[str, Any]:
    return {
        "layer": "21",
        "status": "layer_21_preview_complete",
        "completed_items": COMPLETED_ITEMS,
        "completed_commits": COMPLETED_COMMITS,
        "endpoint_groups": ENDPOINT_GROUPS,
        "safety_boundaries": SAFETY_BOUNDARIES,
        "no_real_action_summary": {
            "real_action_enabled": False,
            "action_performed": False,
            "real_send_export_print_file": False,
            "real_device_screen_vehicle_microphone_control": False,
            "memory_or_db_write": False,
        },
        "layer21_capability_summary": (
            "Layer 21 is Lux's invisible intelligent support layer. It moves Lux beyond a simple chat answerer "
            "by adding background support reflexes, quality/meta intelligence, emotional context support, "
            "cross-page context transfer preview, device bridge preview, pointer/context cursor, drive-safe surface, "
            "and wake mode plus sonic identity, making Lux more personal, practical, premium, and safe."
        ),
        "next_recommended_step": "Layer 22 - Future / Near-Future Premium Candidates",
        "future_candidates": FUTURE_CANDIDATES,
        "read_only": True,
    }
