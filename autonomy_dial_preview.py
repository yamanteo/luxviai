from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


AUTONOMY_LEVELS = [
    "observe_only",
    "suggest_only",
    "draft_only",
    "prepare_with_confirmation",
    "guided_step_by_step",
    "semi_autonomous_preview",
    "blocked_requires_permission",
    "blocked_not_allowed",
]


RISK_DOMAINS = [
    "message_send",
    "email_send",
    "file_export",
    "print_action",
    "calendar_write",
    "reminder_task_write",
    "memory_write",
    "device_control",
    "screen_control",
    "microphone_access",
    "location_access",
    "financial_or_legal",
    "medical_or_sensitive",
    "private_data",
    "unknown_risk",
]


FALSE_BOUNDARIES = {
    "real_action_enabled": False,
    "action_performed": False,
    "message_sent": False,
    "email_sent": False,
    "file_created": False,
    "export_performed": False,
    "print_performed": False,
    "calendar_write_performed": False,
    "reminder_created": False,
    "task_created": False,
    "memory_read_performed": False,
    "memory_write_performed": False,
    "db_write_performed": False,
    "device_control_performed": False,
    "screen_control_performed": False,
    "microphone_access_performed": False,
    "location_read_performed": False,
}


RISKY_DOMAINS = {
    "message_send",
    "email_send",
    "file_export",
    "print_action",
    "calendar_write",
    "reminder_task_write",
    "memory_write",
    "device_control",
    "screen_control",
    "microphone_access",
    "location_access",
    "financial_or_legal",
    "medical_or_sensitive",
    "private_data",
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("\u0131", "i").replace("\u00c4\u00b1", "i")


def autonomy_dial_schema() -> Dict[str, Any]:
    return {
        "layer": "22.7",
        "name": "Autonomy Dial Preview",
        "status": "schema_ready",
        "autonomy_levels": AUTONOMY_LEVELS,
        "risk_domains": RISK_DOMAINS,
        "input_fields": [
            "command",
            "task_type",
            "requested_action",
            "user_permission_state",
            "risk_domain",
            "desired_autonomy_level",
            "context_text",
            "sensitivity",
        ],
        "safety_boundary": (
            "Read-only autonomy policy preview. No send, export, print, calendar, task, reminder, memory, DB, "
            "file, device, screen, microphone, location, or agent action is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _detect_risk_domain(text: str, risk_domain: str) -> str:
    explicit = _normalize(risk_domain)
    if explicit in RISK_DOMAINS:
        return explicit
    if any(key in text for key in ["mail gonder", "e-posta gonder", "email send", "bu maili gonder"]):
        return "email_send"
    if any(key in text for key in ["mesaj gonder", "mesaj at", "yolla", "gonder"]):
        return "message_send"
    if any(key in text for key in ["hafiza", "memory"]):
        return "memory_write"
    if any(key in text for key in ["pdf", "export", "disa aktar", "kaydet", "file"]):
        return "file_export"
    if any(key in text for key in ["yazdir", "print"]):
        return "print_action"
    if any(key in text for key in ["takvim", "calendar"]):
        return "calendar_write"
    if any(key in text for key in ["hatirlatici", "gorev olustur", "task", "reminder"]):
        return "reminder_task_write"
    if any(key in text for key in ["cihaz", "device", "ayar", "kontrol et"]):
        return "device_control"
    if any(key in text for key in ["ekran", "screen"]):
        return "screen_control"
    if any(key in text for key in ["mikrofon", "microphone", "ses kaydi"]):
        return "microphone_access"
    if any(key in text for key in ["konum", "location"]):
        return "location_access"
    if any(key in text for key in ["hukuk", "legal", "finans", "para", "yatirim"]):
        return "financial_or_legal"
    if any(key in text for key in ["tibbi", "medical", "hassas", "klinik", "ozel bilgi"]):
        return "medical_or_sensitive"
    if any(key in text for key in ["ozel", "private", "mahrem", "arka planda takip"]):
        return "private_data"
    return "unknown_risk"


def _detect_requested_level(text: str, desired_level: str) -> str:
    explicit = _normalize(desired_level)
    if explicit in AUTONOMY_LEVELS:
        return explicit
    if any(key in text for key in ["sadece oner", "oner", "hicbir sey hazirlama"]):
        return "suggest_only"
    if any(key in text for key in ["taslak", "draft"]):
        return "draft_only"
    if any(key in text for key in ["son onay", "onayi benden al", "hazirla"]):
        return "prepare_with_confirmation"
    if any(key in text for key in ["adim adim", "step by step"]):
        return "guided_step_by_step"
    if any(key in text for key in ["otomatik", "auto", "hallet"]):
        return "semi_autonomous_preview"
    if any(key in text for key in ["oku", "anla", "ozetle"]):
        return "observe_only"
    return "observe_only"


def _recommend_level(requested: str, domain: str, text: str, permission_state: str, sensitivity: str) -> str:
    sensitive = _normalize(sensitivity)
    permission = _normalize(permission_state)
    if domain in {"private_data", "medical_or_sensitive"} and any(key in text for key in ["arka planda takip", "gizlice", "surekli izle"]):
        return "blocked_not_allowed"
    if domain in RISKY_DOMAINS:
        if requested == "prepare_with_confirmation":
            return requested
        if requested in {"draft_only", "guided_step_by_step"} and domain not in {"device_control", "screen_control", "microphone_access", "location_access"}:
            return requested
        if permission not in {"granted", "allowed", "izinli"}:
            return "blocked_requires_permission"
        return "prepare_with_confirmation"
    if sensitive in {"high", "private", "sensitive"}:
        return "suggest_only"
    return requested


def _task_type(text: str, task_type: str, domain: str) -> str:
    explicit = _normalize(task_type)
    if explicit:
        return explicit
    if domain in {"email_send", "message_send"}:
        return "communication"
    if domain in {"file_export", "print_action"}:
        return "workspace_output"
    if domain in {"calendar_write", "reminder_task_write"}:
        return "planning"
    if domain in {"device_control", "screen_control", "microphone_access", "location_access"}:
        return "device_or_platform"
    if domain == "memory_write":
        return "memory_policy"
    if "taslak" in text:
        return "drafting"
    return "general"


def _safe_alternative(domain: str, recommended: str) -> str:
    if recommended == "blocked_not_allowed":
        return "Bunun yerine hassas veriyi saklamadan genel bir guvenlik siniri ve tek adimlik plan onerebilirim."
    if domain in {"message_send", "email_send"}:
        return "Taslak hazirlayabilirim; gonderim icin son onay gerekir."
    if domain == "file_export":
        return "Export oncesi temiz paket preview hazirlayabilirim; dosya olusturmam."
    if domain == "print_action":
        return "Yazdirma kontrol listesi hazirlayabilirim; print islemi yapmam."
    if domain in {"calendar_write", "reminder_task_write"}:
        return "Takvim/gorev niyetini preview olarak planlayabilirim; gercek kayit yapmam."
    if domain == "memory_write":
        return "Hafiza yazmadan guvenli ozet/etiket preview gosterebilirim."
    if domain in {"device_control", "screen_control", "microphone_access", "location_access"}:
        return "Cihaz erisimi olmadan izin/onay siniri ve adim adim yol onerebilirim."
    return "Oneri, taslak veya adim adim rehber preview sunabilirim."


def preview_autonomy_dial(
    command: str,
    task_type: str = "",
    requested_action: str = "",
    user_permission_state: str = "",
    risk_domain: str = "",
    desired_autonomy_level: str = "",
    context_text: str = "",
    sensitivity: str = "",
) -> Dict[str, Any]:
    text = _normalize(" ".join([command, requested_action, context_text, task_type, risk_domain, desired_autonomy_level, sensitivity]))
    domain = _detect_risk_domain(text, risk_domain)
    requested = _detect_requested_level(text, desired_autonomy_level)
    recommended = _recommend_level(requested, domain, text, user_permission_state, sensitivity)
    permission_required = domain in RISKY_DOMAINS
    confirmation_required = domain in RISKY_DOMAINS or recommended in {"prepare_with_confirmation", "blocked_requires_permission"}
    blocked = recommended in {"blocked_requires_permission", "blocked_not_allowed"}
    disallowed = _disallowed_actions(domain)

    return {
        "raw_command": command,
        "detected_task_type": _task_type(text, task_type, domain),
        "detected_risk_domain": domain,
        "requested_autonomy_level": requested,
        "recommended_autonomy_level": recommended,
        "autonomy_reason": _reason(recommended, domain, permission_required),
        "permission_required": permission_required,
        "confirmation_required": confirmation_required,
        "final_confirmation_required": confirmation_required,
        "blocked": blocked,
        "block_reason": _block_reason(recommended, domain),
        "safe_alternative": _safe_alternative(domain, recommended),
        "allowed_preview_actions": _allowed_preview_actions(recommended),
        "disallowed_real_actions": disallowed,
        "suggested_microcopy": _microcopy(recommended, domain),
        "safety_boundary": (
            "Autonomy Dial is read-only: no real action, send, export, print, calendar, task, reminder, memory, "
            "DB, file, device, screen, microphone, or location action is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _allowed_preview_actions(level: str) -> List[str]:
    if level == "suggest_only":
        return ["suggestion_preview"]
    if level == "draft_only":
        return ["draft_preview", "tone_preview", "risk_note"]
    if level == "prepare_with_confirmation":
        return ["preparation_preview", "confirmation_note", "clean_checklist"]
    if level == "guided_step_by_step":
        return ["step_by_step_preview", "user_action_checklist"]
    if level == "semi_autonomous_preview":
        return ["future_autonomy_plan_preview", "permission_boundary_preview"]
    if level.startswith("blocked"):
        return ["blocked_reason_preview", "safe_alternative_preview"]
    return ["observe_preview", "summary_preview"]


def _disallowed_actions(domain: str) -> List[str]:
    actions = ["real_agent_action"]
    if domain in {"message_send", "email_send"}:
        actions.extend(["send_message", "send_email"])
    if domain == "file_export":
        actions.extend(["create_file", "export_file"])
    if domain == "print_action":
        actions.append("print")
    if domain in {"calendar_write", "reminder_task_write"}:
        actions.extend(["calendar_write", "create_reminder", "create_task"])
    if domain == "memory_write":
        actions.append("memory_write")
    if domain in {"device_control", "screen_control", "microphone_access", "location_access"}:
        actions.extend(["device_control", "screen_control", "microphone_access", "location_read"])
    return list(dict.fromkeys(actions))


def _reason(level: str, domain: str, permission_required: bool) -> str:
    if level == "blocked_not_allowed":
        return "Sensitive/private tracking is not allowed in this scaffold."
    if level == "blocked_requires_permission":
        return f"{domain} requires explicit permission and final confirmation; scaffold cannot execute it."
    if permission_required:
        return f"{domain} is risky, so only preview/draft/confirmation-safe preparation is allowed."
    return "Low-risk request can be previewed at the requested autonomy level."


def _block_reason(level: str, domain: str) -> str:
    if level == "blocked_not_allowed":
        return "This request crosses a privacy/safety boundary."
    if level == "blocked_requires_permission":
        return f"{domain} requires permission and final confirmation before any real action."
    return ""


def _microcopy(level: str, domain: str) -> str:
    if level == "suggest_only":
        return "Sadece oneri veriyorum; hicbir sey hazirlamiyorum."
    if level == "draft_only":
        return "Taslak hazirlarim, gondermem."
    if level == "prepare_with_confirmation":
        return "Hazirlarim ama son onay olmadan uygulamam."
    if level == "guided_step_by_step":
        return "Adimlari sana yaptiririm; ben gercek aksiyon almam."
    if level == "semi_autonomous_preview":
        return "Otomatik calisma burada sadece preview; gercek aksiyon yok."
    if level == "blocked_not_allowed":
        return "Bunu bu sekilde yapamam; guvenli bir alternatif onerebilirim."
    if level == "blocked_requires_permission":
        return f"{domain} icin izin ve son onay gerekir; su an sadece preview."
    return "Sadece izliyor ve guvenli preview uretiyorum."


def autonomy_dial_status() -> Dict[str, Any]:
    return {
        "layer": "22.7",
        "name": "Autonomy Dial Preview",
        "status": "autonomy_dial_preview_ready",
        "read_only": True,
        "autonomy_levels": AUTONOMY_LEVELS,
        "risk_domains": RISK_DOMAINS,
        "available_endpoints": [
            "GET /autonomy-dial/schema",
            "POST /autonomy-dial/preview",
            "GET /debug/autonomy-dial-status",
        ],
        "integrates_with_preview_layers": [
            "Luxway",
            "Device Bridge",
            "Workspace",
            "Finality Sense",
            "Intention Timeline",
            "Ambient Workspace",
        ],
        "core_rule": "Recommend autonomy safely; never perform real send/export/print/calendar/task/memory/device actions.",
        "backlog": ["stop/durdur final block leak"],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        **FALSE_BOUNDARIES,
    }
