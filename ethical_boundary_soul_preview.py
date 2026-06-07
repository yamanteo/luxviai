from __future__ import annotations

import unicodedata
from typing import Any, Dict, List


BOUNDARY_CATEGORIES = [
    "safe_normal",
    "permission_required",
    "confirmation_required",
    "final_confirmation_required",
    "privacy_sensitive",
    "no_memory_required",
    "no_export_required",
    "no_copy_required",
    "action_blocked",
    "unsafe_request_blocked",
    "sensitive_data_minimization",
    "child_or_vulnerable_safety",
    "medical_legal_financial_caution",
    "emotional_support_boundary",
    "clinical_claim_blocked",
    "device_control_boundary",
    "screen_mic_location_boundary",
    "cross_page_context_boundary",
    "unknown_boundary",
]


RISK_LEVELS = ["low", "medium", "high", "critical", "unknown"]


BOUNDARY_RESPONSE_STYLES = [
    "calm_clear",
    "firm_soft",
    "permission_first",
    "confirmation_first",
    "privacy_first",
    "no_memory_mode",
    "safe_redirect",
    "minimal_explanation",
    "premium_boundary",
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
    "screen_read_performed": False,
    "microphone_access_performed": False,
    "location_read_performed": False,
}


def _normalize(text: str) -> str:
    lowered = (text or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_text.replace("\u0131", "i").replace("\u00c4\u00b1", "i")


def ethical_boundary_schema() -> Dict[str, Any]:
    return {
        "layer": "22.8",
        "name": "Ethical Boundary Soul Preview",
        "status": "schema_ready",
        "boundary_categories": BOUNDARY_CATEGORIES,
        "risk_levels": RISK_LEVELS,
        "boundary_response_styles": BOUNDARY_RESPONSE_STYLES,
        "input_fields": [
            "command",
            "context_text",
            "requested_action",
            "data_type",
            "sensitivity",
            "mode_hint",
            "user_permission_state",
            "autonomy_level",
        ],
        "safety_boundary": (
            "Read-only boundary classification preview. This does not replace production safety policy and does "
            "not perform real action, send, export, print, calendar/task/reminder, memory, DB, file, device, "
            "screen, microphone, or location operations."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def preview_ethical_boundary(
    command: str,
    context_text: str = "",
    requested_action: str = "",
    data_type: str = "",
    sensitivity: str = "",
    mode_hint: str = "",
    user_permission_state: str = "",
    autonomy_level: str = "",
) -> Dict[str, Any]:
    text = _normalize(" ".join([command, context_text, requested_action, data_type, sensitivity, mode_hint, user_permission_state, autonomy_level]))
    category = _detect_category(text)
    risk = _risk_for(category, text)
    style = _style_for(category, text)
    permission = category in {
        "permission_required",
        "privacy_sensitive",
        "sensitive_data_minimization",
        "device_control_boundary",
        "screen_mic_location_boundary",
        "cross_page_context_boundary",
    }
    confirmation = category in {"confirmation_required", "final_confirmation_required", "device_control_boundary", "screen_mic_location_boundary"} or permission
    final_confirmation = category in {"final_confirmation_required", "device_control_boundary", "screen_mic_location_boundary"} or (
        "gonder" in text or "direkt" in text or "tikla" in text
    )
    no_memory = category == "no_memory_required" or "luxeph" in text or "no memory" in text
    no_export = category == "no_export_required" or "luxeph" in text
    no_copy = category == "no_copy_required" or "luxeph" in text
    data_min = category in {"privacy_sensitive", "sensitive_data_minimization", "no_memory_required"} or "ozel" in text
    blocked = category in {
        "action_blocked",
        "unsafe_request_blocked",
        "clinical_claim_blocked",
        "device_control_boundary",
        "screen_mic_location_boundary",
    }

    return {
        "raw_command": command,
        "detected_boundary_category": category,
        "risk_level": risk,
        "boundary_response_style": style,
        "permission_required": permission,
        "confirmation_required": confirmation,
        "final_confirmation_required": final_confirmation,
        "no_memory_required": no_memory,
        "no_export_required": no_export,
        "no_copy_required": no_copy,
        "data_minimization_required": data_min,
        "action_blocked": blocked,
        "block_reason": _block_reason(category),
        "safe_alternative": _safe_alternative(category),
        "suggested_lux_response": _lux_response(category, style),
        "linked_layers": _linked_layers(category),
        "safety_boundary": (
            "Ethical Boundary Soul is read-only: it classifies risk and suggests a safe Lux response, but no real "
            "action, send, export, print, calendar, task, reminder, memory, DB, file, device, screen, mic, or "
            "location operation is performed."
        ),
        **FALSE_BOUNDARIES,
        "read_only": True,
    }


def _detect_category(text: str) -> str:
    if any(key in text for key in ["luxeph", "gizlilik modu", "ozel mod"]):
        return "no_memory_required"
    if any(key in text for key in ["teshis koy", "diagnose", "klinik tani", "terapi iddiasi"]):
        return "clinical_claim_blocked"
    if any(key in text for key in ["mikrofon", "arka planda acik", "background listening", "konum", "location"]):
        return "screen_mic_location_boundary"
    if any(key in text for key in ["ekrani oku", "tikla", "screen", "cihazi kontrol", "device control"]):
        return "device_control_boundary"
    if any(key in text for key in ["maili direkt gonder", "bu maili direkt", "email gonder", "mail gonder"]):
        return "final_confirmation_required"
    if any(key in text for key in ["mesaj gonder", "gonder"]):
        return "final_confirmation_required"
    if any(key in text for key in ["hafizaya kaydet", "memory write", "hafiza"]):
        return "no_memory_required"
    if any(key in text for key in ["pdf", "export", "disa aktar", "dosyayi", "kaydet", "yazdir"]):
        return "no_export_required"
    if any(key in text for key in ["ozel bilgi", "mahrem", "hassas veri", "sakla", "private"]):
        return "privacy_sensitive"
    if any(key in text for key in ["tibbi", "hukuki", "finansal", "medical", "legal", "financial"]):
        return "medical_legal_financial_caution"
    if any(key in text for key in ["cocuk", "vulnerable", "savunmasiz"]):
        return "child_or_vulnerable_safety"
    if any(key in text for key in ["guvenli alternatif", "safe alternative", "guvenli yon"]):
        return "unsafe_request_blocked"
    if any(key in text for key in ["hazirla ama gonderme", "gondermeye hazirla"]):
        return "confirmation_required"
    return "safe_normal" if text else "unknown_boundary"


def _risk_for(category: str, text: str) -> str:
    if category in {"unsafe_request_blocked", "clinical_claim_blocked", "screen_mic_location_boundary"}:
        return "critical"
    if category in {"privacy_sensitive", "device_control_boundary", "final_confirmation_required", "no_memory_required"}:
        return "high"
    if category in {"permission_required", "confirmation_required", "no_export_required", "medical_legal_financial_caution"}:
        return "medium"
    if category == "unknown_boundary":
        return "unknown"
    if "hassas" in text or "ozel" in text:
        return "high"
    return "low"


def _style_for(category: str, text: str) -> str:
    if category == "no_memory_required":
        return "no_memory_mode"
    if category in {"privacy_sensitive", "sensitive_data_minimization"}:
        return "privacy_first"
    if category in {"final_confirmation_required", "confirmation_required"}:
        return "confirmation_first"
    if category in {"permission_required", "device_control_boundary", "screen_mic_location_boundary"}:
        return "permission_first"
    if category in {"unsafe_request_blocked", "clinical_claim_blocked"}:
        return "firm_soft"
    if "premium" in text:
        return "premium_boundary"
    return "calm_clear"


def _block_reason(category: str) -> str:
    reasons = {
        "clinical_claim_blocked": "Clinical diagnosis or therapy claims are not allowed in this preview.",
        "device_control_boundary": "Screen/device control requires explicit permission and cannot be performed here.",
        "screen_mic_location_boundary": "Screen, microphone, background listening, or location access is blocked in this scaffold.",
        "unsafe_request_blocked": "The request needs a safe redirect instead of direct execution.",
        "action_blocked": "Real action is blocked by the read-only boundary.",
    }
    return reasons.get(category, "")


def _safe_alternative(category: str) -> str:
    alternatives = {
        "no_memory_required": "Bunu hafizaya yazmadan, sadece bu yanit icinde guvenli bir ozet olarak ele alabilirim.",
        "no_export_required": "Dosya olusturmadan veya export etmeden temiz export checklist preview hazirlayabilirim.",
        "final_confirmation_required": "Gondermeden once taslak ve son onay kontrolu hazirlayabilirim.",
        "confirmation_required": "Hazirlik yapabilirim ama gercek aksiyon icin son onay gerekir.",
        "privacy_sensitive": "Hassas detayi saklamadan, minimum veriyle guvenli bir ozet kullanabilirim.",
        "clinical_claim_blocked": "Teshis koyamam; ama guvenli duygu farkindaligi ve bir sonraki kucuk adim onerebilirim.",
        "device_control_boundary": "Cihaza dokunmadan adim adim kullanici kontrolunde bir yol haritasi verebilirim.",
        "screen_mic_location_boundary": "Mikrofon/ekran/konum erisimi olmadan izin siniri ve guvenli alternatif sunabilirim.",
        "medical_legal_financial_caution": "Kesin uzman tavsiyesi iddiasi olmadan genel bilgilendirme ve risk notu verebilirim.",
        "unsafe_request_blocked": "Direkt yapmak yerine guvenli ve kontrolu sende tutan bir alternatif sunabilirim.",
    }
    return alternatives.get(category, "Guvenli bir preview, taslak veya kontrol listesi sunabilirim.")


def _lux_response(category: str, style: str) -> str:
    if category == "safe_normal":
        return "Bunu guvenli bir preview olarak ele alabilirim; gercek aksiyon yapmayacagim."
    if style == "no_memory_mode":
        return "Bunu hafizaya almadan, burada kalacak sekilde sakin ve net ilerletelim."
    if style == "confirmation_first":
        return "Hazirlayabilirim; son onay senden gelmeden gonderme, export veya uygulama yapmam."
    if style == "permission_first":
        return "Bu alan izin gerektirir. Simdilik sadece siniri ve guvenli yolu gosterecegim."
    if style == "privacy_first":
        return "Hassas detayi azaltip yalnizca gerekli guvenli sinyali kullanacagim."
    if style == "firm_soft":
        return "Bunu bu sekilde yapamam; ama seni yormadan guvenli bir alternatif sunabilirim."
    return "Siniri net tutup kontrolu sende birakiyorum."


def _linked_layers(category: str) -> List[str]:
    layers = ["Autonomy Dial", "Finality Sense"]
    if category in {"device_control_boundary", "screen_mic_location_boundary"}:
        layers.extend(["Device Bridge", "Pointer", "Drive Mode", "Wake Mode"])
    if category in {"no_memory_required", "privacy_sensitive", "sensitive_data_minimization"}:
        layers.extend(["Safe Memory Retrieval", "Context Bridge"])
    if category in {"no_export_required", "confirmation_required", "final_confirmation_required"}:
        layers.extend(["Workspace", "Ambient Workspace"])
    if category in {"clinical_claim_blocked", "emotional_support_boundary"}:
        layers.append("Emotional Reflection")
    return list(dict.fromkeys(layers))


def ethical_boundary_status() -> Dict[str, Any]:
    return {
        "layer": "22.8",
        "name": "Ethical Boundary Soul Preview",
        "status": "ethical_boundary_preview_ready",
        "read_only": True,
        "boundary_categories": BOUNDARY_CATEGORIES,
        "risk_levels": RISK_LEVELS,
        "boundary_response_styles": BOUNDARY_RESPONSE_STYLES,
        "available_endpoints": [
            "GET /ethical-boundary/schema",
            "POST /ethical-boundary/preview",
            "GET /debug/ethical-boundary-status",
        ],
        "core_rule": "Preview boundary, permission, confirmation, no-memory, and safe alternative behavior only.",
        "backlog": ["stop/durdur final block leak"],
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        **FALSE_BOUNDARIES,
    }
