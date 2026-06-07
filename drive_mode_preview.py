from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


DRIVE_STATES: List[Dict[str, Any]] = [
    {"id": "idle", "short_status_text": "Bekliyor", "read_only": True},
    {"id": "listening", "short_status_text": "Dinliyor", "read_only": True},
    {"id": "thinking", "short_status_text": "Dusunuyor", "read_only": True},
    {"id": "draft_ready", "short_status_text": "Taslak hazir", "read_only": True},
    {"id": "confirmation_waiting", "short_status_text": "Onay bekliyor", "read_only": True},
    {"id": "sent_preview", "short_status_text": "Hazirlandi", "read_only": True},
    {"id": "noted", "short_status_text": "Not edildi", "read_only": True},
    {"id": "parked_continue_available", "short_status_text": "Varinca devam et", "read_only": True},
    {"id": "blocked_for_safety", "short_status_text": "Suruste uygun degil", "read_only": True},
    {"id": "emergency_safe_state", "short_status_text": "Guvenli moda alindi", "read_only": True},
]


DRIVE_INTENTS: List[Dict[str, Any]] = [
    {"id": "voice_note_capture_preview", "category": "note", "requires_permission": True, "requires_confirmation": False},
    {"id": "message_reply_draft_preview", "category": "message", "requires_permission": True, "requires_confirmation": True},
    {"id": "call_prepare_preview", "category": "call", "requires_permission": True, "requires_confirmation": True},
    {"id": "reminder_prepare_preview", "category": "reminder", "requires_permission": True, "requires_confirmation": True},
    {"id": "destination_note_preview", "category": "location_note", "requires_permission": True, "requires_confirmation": False},
    {"id": "parked_continue_preview", "category": "parked_resume", "requires_permission": False, "requires_confirmation": False},
    {"id": "summarize_later_preview", "category": "summary", "requires_permission": False, "requires_confirmation": False},
    {"id": "meeting_brief_preview", "category": "brief", "requires_permission": False, "requires_confirmation": False},
    {"id": "urgent_filter_preview", "category": "filter", "requires_permission": True, "requires_confirmation": False},
    {"id": "two_step_confirmation_preview", "category": "confirmation", "requires_permission": True, "requires_confirmation": True},
    {"id": "unsafe_visual_task_block", "category": "safety", "requires_permission": False, "requires_confirmation": False},
    {"id": "drive_safe_minimal_response", "category": "drive_ui", "requires_permission": False, "requires_confirmation": False},
    {"id": "hands_free_task_queue", "category": "queue", "requires_permission": False, "requires_confirmation": False},
    {"id": "arrival_resume_context", "category": "parked_resume", "requires_permission": False, "requires_confirmation": False},
]


INTENT_RULES = {
    "drive_safe_minimal_response": ["surus modunu ac", "drive mode", "luxway drive", "surus modu"],
    "voice_note_capture_preview": ["not al", "not et", "sesli not"],
    "arrival_resume_context": ["varinca devam", "varinca", "sonra devam"],
    "message_reply_draft_preview": ["mesaja cevap", "cevap taslagi", "mesaj taslagi"],
    "two_step_confirmation_preview": ["gonder", "cevap taslagi", "onay"],
    "urgent_filter_preview": ["acil olanlari", "acilleri", "urgent"],
    "summarize_later_preview": ["sonra ozetle", "sonra toparla", "ozetle"],
    "meeting_brief_preview": ["toplanti", "brief", "kisa brief"],
    "unsafe_visual_task_block": ["uzun raporu goster", "uzun metin", "ekranda goster", "liste goster"],
    "parked_continue_preview": ["varinca bunu ac", "park halinde", "park edince"],
    "call_prepare_preview": ["arama hazirligi", "arama baslatma", "ara", "call"],
    "reminder_prepare_preview": ["hatirlatici", "reminder", "hatirlat"],
    "hands_free_task_queue": ["eller serbest", "kuyruga al", "queue"],
    "destination_note_preview": ["konum", "navigasyon", "adres", "hedef"],
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ş": "s",
        "ö": "o",
        "ü": "u",
        "ç": "c",
        "İ": "i",
        "Ä±": "i",
        "ÄŸ": "g",
        "ÅŸ": "s",
        "Ã¶": "o",
        "Ã¼": "u",
        "Ã§": "c",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def _intent_by_id(intent_id: str) -> Dict[str, Any]:
    for intent in DRIVE_INTENTS:
        if intent["id"] == intent_id:
            return intent
    return DRIVE_INTENTS[-3]


def _state_by_id(state_id: str) -> Dict[str, Any]:
    for state in DRIVE_STATES:
        if state["id"] == state_id:
            return state
    return DRIVE_STATES[0]


def _detect_intents(command: str, requested_action: str = "") -> List[Dict[str, Any]]:
    normalized = _normalize(f"{command} {requested_action}")
    detected: List[Dict[str, Any]] = []
    for intent_id, keywords in INTENT_RULES.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        if matched:
            intent = _intent_by_id(intent_id)
            detected.append(
                {
                    "id": intent["id"],
                    "category": intent["category"],
                    "matched_keywords": matched,
                    "confidence": "high" if len(matched) > 1 else "medium",
                }
            )

    if not detected:
        intent = _intent_by_id("drive_safe_minimal_response")
        detected.append(
            {
                "id": intent["id"],
                "category": intent["category"],
                "matched_keywords": [],
                "confidence": "low",
            }
        )
    return detected


def _minimal_state(intent_ids: List[str], moving: bool) -> Dict[str, Any]:
    if "unsafe_visual_task_block" in intent_ids:
        state = _state_by_id("blocked_for_safety")
    elif any(intent in intent_ids for intent in ["message_reply_draft_preview", "call_prepare_preview", "reminder_prepare_preview", "two_step_confirmation_preview"]):
        state = _state_by_id("confirmation_waiting")
    elif any(intent in intent_ids for intent in ["voice_note_capture_preview", "destination_note_preview"]):
        state = _state_by_id("noted")
    elif any(intent in intent_ids for intent in ["arrival_resume_context", "parked_continue_preview"]):
        state = _state_by_id("parked_continue_available")
    elif moving:
        state = _state_by_id("listening")
    else:
        state = _state_by_id("idle")

    return {
        "state": state["id"],
        "short_status_text": state["short_status_text"],
        "background": "black",
        "accent": "amber/platinum",
        "logo_visible": True,
        "large_text_allowed": False,
        "button_crowding_allowed": False,
        "scroll_allowed": False,
    }


def drive_mode_schema() -> Dict[str, Any]:
    return {
        "status": "drive_mode_schema_ready",
        "layer": "21.7",
        "name": "Lux Drive Mode / Luxway Drive Mode",
        "core_idea": "Eyes on the road, work with Lux. This is not a navigation app.",
        "drive_states": DRIVE_STATES,
        "intent_groups": DRIVE_INTENTS,
        "motion_ui_principles": [
            "black background",
            "Lux logo",
            "Lux Drive Mode / Luxway Drive Mode",
            "small listening light",
            "single short status",
            "no long text",
            "no option lists",
            "no scrolling",
            "no crowded buttons",
            "no visual clutter",
            "map is not the main purpose",
            "do not make the user look at the screen",
        ],
        "input_fields": [
            "command",
            "vehicle_state",
            "motion_state",
            "user_attention_state",
            "requested_action",
            "risk_level",
            "surface_type",
        ],
        "read_only": True,
        "can_execute_now": False,
        "real_vehicle_connection_performed": False,
        "real_location_read_performed": False,
        "real_microphone_recording_performed": False,
        "real_message_sent": False,
        "real_call_started": False,
        "real_device_control_performed": False,
        "real_file_created": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
    }


def preview_drive_mode(
    command: str,
    vehicle_state: str = "",
    motion_state: str = "moving",
    user_attention_state: str = "driving",
    requested_action: str = "",
    risk_level: str = "normal",
    surface_type: str = "",
) -> Dict[str, Any]:
    intents = _detect_intents(command, requested_action)
    intent_ids = [intent["id"] for intent in intents]
    normalized_motion = _normalize(motion_state or vehicle_state or "moving")
    moving = normalized_motion not in {"parked", "stopped", "durdu", "park", "stationary"}
    risky = _normalize(risk_level) in {"high", "risky", "danger", "dangerous"}
    requires_permission = risky or any(_intent_by_id(intent_id)["requires_permission"] for intent_id in intent_ids)
    requires_confirmation = risky or any(_intent_by_id(intent_id)["requires_confirmation"] for intent_id in intent_ids)
    if any(intent_id in intent_ids for intent_id in ["message_reply_draft_preview", "call_prepare_preview", "two_step_confirmation_preview"]):
        requires_confirmation = True
    two_step = requires_confirmation or "two_step_confirmation_preview" in intent_ids
    long_text_blocked = moving
    list_ui_blocked = moving
    scroll_ui_blocked = moving
    screen_output_allowed = not moving and "unsafe_visual_task_block" not in intent_ids
    voice_output_recommended = True

    return {
        "raw_command": command,
        "detected_drive_intent": {
            "primary": intent_ids[0],
            "intents": intents,
            "intent_ids": intent_ids,
        },
        "motion_state": "moving" if moving else "parked",
        "vehicle_state": vehicle_state or "unknown_preview",
        "user_attention_state": user_attention_state,
        "attention_requirement": "eyes_on_road_minimal_status" if moving else "parked_or_low_attention_preview",
        "screen_output_allowed": screen_output_allowed,
        "voice_output_recommended": voice_output_recommended,
        "long_text_blocked": long_text_blocked,
        "list_ui_blocked": list_ui_blocked,
        "scroll_ui_blocked": scroll_ui_blocked,
        "requires_permission": requires_permission,
        "requires_confirmation": requires_confirmation,
        "two_step_confirmation_required": two_step,
        "can_execute_now": False,
        "real_vehicle_connection_performed": False,
        "real_location_read_performed": False,
        "real_microphone_recording_performed": False,
        "real_message_sent": False,
        "real_call_started": False,
        "real_device_control_performed": False,
        "real_file_created": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "safe_drive_plan": {
            "mode": "drive_safe_prepared_state_preview",
            "not_navigation_app": True,
            "steps": [
                "Keep the screen minimal while the vehicle is moving.",
                "Prefer short voice-first feedback and one status line.",
                "Block long text, lists, scrolling, and dense visual tasks while moving.",
                "Prepare drafts, reminders, notes, or queues without sending, calling, recording, or controlling devices.",
                "Require two-step confirmation for risky future actions.",
            ],
        },
        "minimal_ui_state": _minimal_state(intent_ids, moving),
        "privacy_boundary": {
            "real_vehicle_connection_performed": False,
            "real_carplay_or_android_auto_integration": False,
            "real_location_read_performed": False,
            "real_microphone_recording_performed": False,
            "real_stt_performed": False,
            "real_tts_performed": False,
            "real_message_sent": False,
            "real_call_started": False,
            "real_app_or_device_control_performed": False,
            "real_file_created": False,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_write_performed": False,
        },
        "preview_response": "Preview only: Drive Mode would keep Lux minimal and voice-first, but no vehicle, GPS, mic, send, call, or device action was performed.",
        "read_only": True,
        "db_write_performed": False,
        "file_write_performed": False,
        "surface_type": surface_type or "drive_minimal_surface",
    }


def drive_mode_status() -> Dict[str, Any]:
    return {
        "layer": "21.7",
        "name": "Drive Mode Preview",
        "status": "scaffold_ready",
        "drive_state_count": len(DRIVE_STATES),
        "intent_count": len(DRIVE_INTENTS),
        "available_endpoints": [
            "/drive-mode/schema",
            "/drive-mode/preview",
            "/debug/drive-mode-status",
        ],
        "read_only": True,
        "can_execute_now": False,
        "real_vehicle_connection_performed": False,
        "real_location_read_performed": False,
        "real_microphone_recording_performed": False,
        "real_message_sent": False,
        "real_call_started": False,
        "real_device_control_performed": False,
        "real_file_created": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "motion_ui_rules": {
            "long_text_blocked": True,
            "list_ui_blocked": True,
            "scroll_ui_blocked": True,
            "voice_output_recommended": True,
        },
    }
