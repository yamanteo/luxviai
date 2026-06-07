from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


CAPABILITY_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "paired_device_overview",
        "display_name": "Paired Device Overview",
        "category": "pairing",
        "description": "Preview known or requested device surfaces without real discovery.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": False,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "phone_to_pc_session",
        "display_name": "Phone to PC Session",
        "category": "session_control",
        "description": "Preview phone-as-command-center and PC-as-work-surface behavior.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "phone_to_tv_session",
        "display_name": "Phone to TV Session",
        "category": "session_control",
        "description": "Preview phone-to-TV viewing surface handoff.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "browser_surface",
        "display_name": "Browser Surface",
        "category": "surface",
        "description": "Preview using an approved browser tab as a work surface.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "youtube_video_follow",
        "display_name": "YouTube Video Follow",
        "category": "video",
        "description": "Preview how Lux would follow a YouTube video after future permission.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "live_stream_follow",
        "display_name": "Live Stream Follow",
        "category": "video",
        "description": "Preview live stream tracking without reading any real stream.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "video_pause_rewind_continue",
        "display_name": "Video Pause Rewind Continue",
        "category": "device_control",
        "description": "Preview pause, rewind, and continue commands without controlling playback.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "extract_notes",
        "display_name": "Extract Notes",
        "category": "content_preview",
        "description": "Preview note extraction structure without reading real content.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": False,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "one_page_summary",
        "display_name": "One Page Summary",
        "category": "content_preview",
        "description": "Preview a one-page summary package without writing a file.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": False,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "report_builder",
        "display_name": "Report Builder",
        "category": "workspace_output",
        "description": "Preview report preparation without exporting or saving.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": False,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "document_cleanup",
        "display_name": "Document Cleanup",
        "category": "workspace_output",
        "description": "Preview document cleanup and headings without editing a real file.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": False,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "output_folder_preview",
        "display_name": "Output Folder Preview",
        "category": "file_preview",
        "description": "Preview where output would be placed without creating folders or files.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "send_ready_preview",
        "display_name": "Send Ready Preview",
        "category": "send_preview",
        "description": "Prepare a send-ready state without sending mail, messages, or app content.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "export_ready_preview",
        "display_name": "Export Ready Preview",
        "category": "export_preview",
        "description": "Prepare export metadata without producing PDF, Word, or files.",
        "requires_pairing": False,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "print_ready_preview",
        "display_name": "Print Ready Preview",
        "category": "print_preview",
        "description": "Prepare print metadata without printing.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "nearby_printer_preview",
        "display_name": "Nearby Printer Preview",
        "category": "print_preview",
        "description": "Preview printer discovery requirements without scanning nearby devices.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
    {
        "id": "app_handoff_preview",
        "display_name": "App Handoff Preview",
        "category": "handoff",
        "description": "Preview app/browser handoff between phone and larger screens.",
        "requires_pairing": True,
        "requires_permission": True,
        "requires_confirmation": True,
        "real_action_enabled": False,
        "read_only": True,
    },
]


INTENT_RULES = {
    "phone_to_pc_session": ["telefondan bilgisayar", "pc", "bilgisayardaki lux", "lux oturumunu yonet"],
    "phone_to_tv_session": ["tv", "televizyon", "buyuk ekran"],
    "browser_surface": ["browser", "tarayici", "acik sayfa", "sayfayi"],
    "youtube_video_follow": ["youtube", "video"],
    "live_stream_follow": ["canli yayin", "live stream", "yayini takip"],
    "video_pause_rewind_continue": ["durdur", "geri al", "devam et", "20 saniye"],
    "extract_notes": ["not cikar", "not al", "notlari"],
    "one_page_summary": ["tek sayfalik", "tek sayfa", "one page"],
    "report_builder": ["rapor hazirla", "rapor"],
    "document_cleanup": ["notlari temizle", "temizle", "basliklandir"],
    "output_folder_preview": ["klasor", "output", "nereye koy"],
    "send_ready_preview": ["gondermeye hazirla", "mail olarak", "gonderme", "whatsapp", "mesaj"],
    "export_ready_preview": ["pdf", "export", "disa aktar", "hazirla"],
    "print_ready_preview": ["cikti", "yazdir", "print"],
    "nearby_printer_preview": ["yakindaki yazici", "yazici"],
    "app_handoff_preview": ["telefondan devam", "handoff", "bilgisayarda acik", "devam ettir"],
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


def _capability_by_id(capability_id: str) -> Dict[str, Any]:
    for capability in CAPABILITY_GROUPS:
        if capability["id"] == capability_id:
            return capability
    return CAPABILITY_GROUPS[0]


def _detect_capabilities(command: str) -> List[Dict[str, Any]]:
    normalized = _normalize(command)
    detected: List[Dict[str, Any]] = []
    for capability_id, keywords in INTENT_RULES.items():
        matched = [keyword for keyword in keywords if keyword in normalized]
        if matched:
            capability = _capability_by_id(capability_id)
            detected.append(
                {
                    "id": capability["id"],
                    "display_name": capability["display_name"],
                    "category": capability["category"],
                    "matched_keywords": matched,
                    "confidence": "high" if len(matched) > 1 else "medium",
                }
            )

    if not detected:
        fallback = _capability_by_id("paired_device_overview")
        detected.append(
            {
                "id": fallback["id"],
                "display_name": fallback["display_name"],
                "category": fallback["category"],
                "matched_keywords": [],
                "confidence": "low",
            }
        )

    return detected


def _surface_type(capability_ids: List[str], surface_type: str = "", content_type: str = "") -> str:
    if surface_type:
        return surface_type
    if content_type:
        return content_type
    if any(item in capability_ids for item in ["youtube_video_follow", "video_pause_rewind_continue"]):
        return "video"
    if "live_stream_follow" in capability_ids:
        return "live_stream"
    if any(item in capability_ids for item in ["browser_surface", "app_handoff_preview"]):
        return "browser"
    if any(item in capability_ids for item in ["print_ready_preview", "nearby_printer_preview"]):
        return "printer"
    if any(item in capability_ids for item in ["document_cleanup", "report_builder", "one_page_summary"]):
        return "document"
    if "phone_to_tv_session" in capability_ids:
        return "tv"
    if "phone_to_pc_session" in capability_ids:
        return "pc"
    return "device_bridge_preview"


def device_bridge_schema() -> Dict[str, Any]:
    return {
        "status": "device_bridge_schema_ready",
        "layer": "21.5",
        "name": "Lux Device Bridge / Smart Remote",
        "core_idea": {
            "phone": "command and voice input center",
            "large_surface": "PC, TV, browser, YouTube, printer, or work surface preview",
            "execution_model": "permission-first prepared-state preview only",
        },
        "capability_groups": CAPABILITY_GROUPS,
        "input_fields": [
            "command",
            "source_device",
            "target_device",
            "surface_type",
            "content_type",
            "requested_output",
            "risk_level",
        ],
        "output_fields": [
            "raw_command",
            "detected_bridge_intent",
            "detected_surface_type",
            "target_device_required",
            "pairing_required",
            "permission_required",
            "confirmation_required",
            "can_execute_now",
            "safe_device_plan",
            "prepared_state",
            "privacy_boundary",
            "read_only",
        ],
        "safety_rules": [
            "No real device discovery or control is performed.",
            "Pairing, permission, and final confirmation are required before any future device action.",
            "Send, export, print, file placement, and app/device control always require final confirmation.",
            "Video, YouTube, and live stream commands produce plans only; no real content is read.",
            "Nearby printer preview never scans for real printers.",
        ],
        "read_only": True,
        "can_execute_now": False,
        "real_device_control_performed": False,
        "real_pairing_performed": False,
        "real_screen_read_performed": False,
        "real_video_read_performed": False,
        "real_file_created": False,
        "real_export_performed": False,
        "real_send_performed": False,
        "real_print_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
    }


def preview_device_bridge(
    command: str,
    source_device: str = "",
    target_device: str = "",
    surface_type: str = "",
    content_type: str = "",
    requested_output: str = "",
    risk_level: str = "normal",
) -> Dict[str, Any]:
    detected = _detect_capabilities(command)
    capability_ids = [item["id"] for item in detected]
    detected_surface = _surface_type(capability_ids, surface_type, content_type)
    capability_details = [_capability_by_id(capability_id) for capability_id in capability_ids]
    target_required = not bool(target_device) and any(item["requires_pairing"] for item in capability_details)
    pairing_required = any(item["requires_pairing"] for item in capability_details)
    permission_required = any(item["requires_permission"] for item in capability_details)
    confirmation_required = any(item["requires_confirmation"] for item in capability_details)
    risky_outputs = {"send_ready_preview", "export_ready_preview", "print_ready_preview", "output_folder_preview"}
    if risky_outputs & set(capability_ids) or _normalize(risk_level) in {"high", "risky"}:
        confirmation_required = True

    return {
        "raw_command": command,
        "detected_bridge_intent": {
            "primary": capability_ids[0],
            "capabilities": detected,
            "capability_ids": capability_ids,
        },
        "detected_surface_type": detected_surface,
        "source_device": source_device or "phone_command_center_preview",
        "target_device": target_device or "unspecified_target_surface",
        "target_device_required": target_required,
        "pairing_required": pairing_required,
        "permission_required": permission_required,
        "confirmation_required": confirmation_required,
        "can_execute_now": False,
        "real_device_control_performed": False,
        "real_pairing_performed": False,
        "real_screen_read_performed": False,
        "real_video_read_performed": False,
        "real_file_created": False,
        "real_export_performed": False,
        "real_send_performed": False,
        "real_print_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "safe_device_plan": {
            "mode": "prepared_state_preview",
            "steps": [
                "Identify the approved source and target device in a future integration.",
                "Require pairing and explicit permission before any real device access.",
                "Prepare notes, report, send, export, or print state without executing it.",
                "Ask for final confirmation before future send/export/print/control actions.",
            ],
            "permission_first": True,
            "confirmation_first": confirmation_required,
        },
        "prepared_state": {
            "requested_output": requested_output or "preview_only",
            "ready_for_review": True,
            "file_created": False,
            "send_ready_preview": "send_ready_preview" in capability_ids,
            "export_ready_preview": "export_ready_preview" in capability_ids,
            "print_ready_preview": any(item in capability_ids for item in ["print_ready_preview", "nearby_printer_preview"]),
            "device_action_prepared": any(
                item in capability_ids
                for item in ["phone_to_pc_session", "phone_to_tv_session", "video_pause_rewind_continue", "app_handoff_preview"]
            ),
        },
        "privacy_boundary": {
            "real_device_discovery_performed": False,
            "real_screen_read_performed": False,
            "real_video_read_performed": False,
            "real_youtube_read_performed": False,
            "real_live_stream_read_performed": False,
            "real_mail_or_message_sent": False,
            "real_printer_discovery_performed": False,
            "memory_read_performed": False,
            "memory_write_performed": False,
            "db_write_performed": False,
            "file_write_performed": False,
        },
        "preview_response": (
            "Preview only: Lux would prepare a permission-first device bridge plan, but no real device action was executed."
        ),
        "read_only": True,
        "db_write_performed": False,
        "file_write_performed": False,
    }


def device_bridge_status() -> Dict[str, Any]:
    return {
        "layer": "21.5",
        "name": "Device Bridge Preview",
        "status": "scaffold_ready",
        "capability_count": len(CAPABILITY_GROUPS),
        "available_endpoints": [
            "/device-bridge/schema",
            "/device-bridge/preview",
            "/debug/device-bridge-status",
        ],
        "read_only": True,
        "can_execute_now": False,
        "real_device_control_performed": False,
        "real_pairing_performed": False,
        "real_screen_read_performed": False,
        "real_video_read_performed": False,
        "real_file_created": False,
        "real_export_performed": False,
        "real_send_performed": False,
        "real_print_performed": False,
        "memory_read_performed": False,
        "memory_write_performed": False,
        "db_write_performed": False,
        "file_write_performed": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "safety_notes": [
            "No real device discovery, pairing, or control is performed.",
            "No YouTube, live stream, screen, browser, or printer data is read.",
            "Send, export, print, and file creation remain prepared-state previews only.",
        ],
    }
