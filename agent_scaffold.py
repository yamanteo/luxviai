"""Personal agent and Luxway capability scaffold."""

from __future__ import annotations

import unicodedata
import uuid
from typing import Any, Dict, List, Sequence


def _capability(id_: str, *, title: str, description: str, enabled: bool, permission_required: str, risk_level: str, requires_user_confirmation: bool, platform: str, status: str) -> Dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "description": description,
        "enabled": enabled,
        "permission_required": permission_required,
        "risk_level": risk_level,
        "requires_user_confirmation": requires_user_confirmation,
        "platform": platform,
        "status": status,
    }


PERSONAL_AGENT_CAPABILITIES: List[Dict[str, Any]] = [
    _capability(
        id_="weekly_summary",
        title="Haftalık Özet",
        description="Sohbet özetini haftalık düzeyde gruplayıp raporlar.",
        enabled=False,
        permission_required="local_privacy_mode",
        risk_level="low",
        requires_user_confirmation=False,
        platform="web",
        status="scaffold",
    ),
    _capability(
        id_="task_followup",
        title="Görev Takibi",
        description="Acil/önde gelen kullanıcı görevlerini takip etme ve güncelleme önerileri sunma.",
        enabled=False,
        permission_required="local_storage",
        risk_level="low",
        requires_user_confirmation=False,
        platform="web",
        status="scaffold",
    ),
    _capability(
        id_="email_summary",
        title="E-posta Özeti",
        description="Kullanıcının e-posta örüntüleri için anonimleşmiş özet çıkarımı.",
        enabled=False,
        permission_required="email_read",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="future",
        status="planned",
    ),
    _capability(
        id_="message_summary",
        title="Mesaj Özeti",
        description="Mesaj akışındaki önemli noktaları anonim özetleme.",
        enabled=False,
        permission_required="read_only_content",
        risk_level="low",
        requires_user_confirmation=False,
        platform="all",
        status="scaffold",
    ),
    _capability(
        id_="calendar_overview",
        title="Takvim Genel Görünüm",
        description="Takvim yoğunluğu, toplantı dengesi ve mola pencereleri için genel görünüm sunar.",
        enabled=False,
        permission_required="calendar_read",
        risk_level="low",
        requires_user_confirmation=False,
        platform="future",
        status="planned",
    ),
    _capability(
        id_="file_finder",
        title="Dosya Bulucu",
        description="Kullanıcının proje ve çalışma dosyalarını metin tabanlı arama ile bulmayı hazırlar.",
        enabled=False,
        permission_required="file_list",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="future",
        status="scaffold",
    ),
    _capability(
        id_="device_cleanup_suggestions",
        title="Cihaz Temizlik Önerisi",
        description="Kullanıcıya cihaz temizlik önerileri için güvenli öncelik listesi sunar.",
        enabled=False,
        permission_required="local_device_metrics",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="app_usage_review",
        title="Uygulama Kullanım Gözden Geçirme",
        description="Uygulama kullanım alışkanlığı için davranış özeti.",
        enabled=False,
        permission_required="app_usage_stats",
        risk_level="medium",
        requires_user_confirmation=False,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="notification_priority",
        title="Bildirim Önceliklendirme",
        description="Bildirimleri önem düzeyine göre gruplar.",
        enabled=False,
        permission_required="notification_read",
        risk_level="low",
        requires_user_confirmation=False,
        platform="all",
        status="scaffold",
    ),
    _capability(
        id_="phone_assistant_luxway",
        title="Luxway Telefon Asistanı",
        description="Telefon odaklı eylemleri başlatmak için gelecekteki Luxway köprüsü.",
        enabled=False,
        permission_required="explicit_user_invocation",
        risk_level="high",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="workspace_helper",
        title="Çalışma Alanı Yardımcısı",
        description="Çalışma akışlarını, odağı ve görev listesini düzenlemek için destekler.",
        enabled=False,
        permission_required="local_workspace",
        risk_level="low",
        requires_user_confirmation=False,
        platform="web",
        status="scaffold",
    ),
    _capability(
        id_="cv_helper",
        title="CV Yardımcısı",
        description="CV içeriğini güvenli şekilde geliştirip revize önerileri üretir.",
        enabled=False,
        permission_required="user_content_input",
        risk_level="medium",
        requires_user_confirmation=False,
        platform="web",
        status="scaffold",
    ),
    _capability(
        id_="report_helper",
        title="Rapor Yardımcısı",
        description="Toplantı ve proje raporlarını şablonlu bir çatıda hazırlar.",
        enabled=False,
        permission_required="local_workspace",
        risk_level="low",
        requires_user_confirmation=False,
        platform="web",
        status="scaffold",
    ),
    _capability(
        id_="presentation_helper",
        title="Sunum Yardımcısı",
        description="Sunum planını bölümlere ayırıp anlatım akışını iyileştirir.",
        enabled=False,
        permission_required="local_workspace",
        risk_level="low",
        requires_user_confirmation=False,
        platform="web",
        status="scaffold",
    ),
]


LUXWAY_CAPABILITIES: List[Dict[str, Any]] = [
    _capability(
        id_="read_emails",
        title="E-posta Okuma (Luxway)",
        description="Kullanıcının onayıyla e-posta başlık/özetlerini tarama.",
        enabled=False,
        permission_required="email_read",
        risk_level="high",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="read_messages",
        title="Mesaj Okuma (Luxway)",
        description="Kullanıcının onayıyla mesaj akışını bağlamsal inceleme için okuma.",
        enabled=False,
        permission_required="message_read",
        risk_level="high",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="draft_message",
        title="Mesaj Taslağı (Luxway)",
        description="Mesaj taslağı hazırlama; gönderme eylemi farklı onaydan geçecek.",
        enabled=False,
        permission_required="message_send",
        risk_level="high",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="call_contact",
        title="Kişi Arama (Luxway)",
        description="Kullanıcı onayıyla arama aksiyonunu tetikleme hazırlığı.",
        enabled=False,
        permission_required="phone_call",
        risk_level="high",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="open_app",
        title="Uygulama Açma (Luxway)",
        description="Kullanıcı onayıyla uygulama açma talimatını tetikleme.",
        enabled=False,
        permission_required="app_launch",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="scan_unused_apps",
        title="Kullanılmayan Uygulama Taraması",
        description="Kullanılmayan uygulamaları tespit etme listesi.",
        enabled=False,
        permission_required="app_usage_stats",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="scan_storage_usage",
        title="Depolama Taraması",
        description="Depolama kullanım yoğunluğunu özetleme.",
        enabled=False,
        permission_required="device_storage_stats",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="app_cleanup_suggestions",
        title="Uygulama Temizleme Önerileri",
        description="Temizlik için güvenli öneri listesi üretir; otomatik silme yapmaz.",
        enabled=False,
        permission_required="app_cleanup",
        risk_level="high",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="notification_digest",
        title="Bildirim Özetleme",
        description="Bildirim yükünü azaltmak için özet kartı üretir.",
        enabled=False,
        permission_required="notification_read",
        risk_level="low",
        requires_user_confirmation=False,
        platform="android",
        status="planned",
    ),
    _capability(
        id_="device_health_summary",
        title="Cihaz Sağlık Özeti",
        description="Pil/performans/boş alan özetini güvenli şekilde toplar.",
        enabled=False,
        permission_required="device_health_metrics",
        risk_level="medium",
        requires_user_confirmation=True,
        platform="android",
        status="planned",
    ),
]


PRIVACY_RULES: List[str] = [
    "Silme, gönderme, arama, mesaj atma, mail gönderme veya cihaz ayarı değiştirme gibi eylemler hiçbir zaman kullanıcı onayı olmadan tetiklenmeyecektir.",
    "Her yüksek risk eylem için explicit permission ve requires_user_confirmation alanı true olmalıdır.",
    "Luxway akışları için Android/iOS izinleri ileride ayrı manifest/entitlement katmanında alınacaktır.",
    "raw ham içerik saklanmaz; yalnızca güvenli özet/sinyal katmanı işlenir.",
]


ANDROID_PERMISSION_NOTES = (
    "Android: READ_SMS, READ_CONTACTS, READ_CALENDAR, READ_CALL_LOG, "
    "READ_PHONE_STATE, PROCESS_OUTGOING_CALLS, POST_NOTIFICATIONS, SYSTEM_ALERT_WINDOW."
)

IOS_PERMISSION_NOTES = (
    "iOS: User Selected/Read Contacts, Calendars, Notifications, Motion & Fitness "
    "ve ilgili hassas kategori izinleri yalnızca açık kullanıcı onayıyla istenecek."
)


def personal_agent_capabilities() -> List[Dict[str, Any]]:
    return [dict(item) for item in PERSONAL_AGENT_CAPABILITIES]


def luxway_capabilities() -> List[Dict[str, Any]]:
    return [dict(item) for item in LUXWAY_CAPABILITIES]


def all_capabilities() -> List[Dict[str, Any]]:
    return personal_agent_capabilities() + luxway_capabilities()


def get_agent_by_id(capability_id: str) -> Dict[str, Any] | None:
    for cap in all_capabilities():
        if cap.get("id") == capability_id:
            return dict(cap)
    return None


def requires_confirmation(cap: Dict[str, Any] | None) -> bool:
    if not cap:
        return False
    return bool(cap.get("requires_user_confirmation")) or str(cap.get("risk_level", "")).lower() == "high"


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return (
        text.lower()
        .replace("\u0131", "i")
        .replace("\u0130", "i")
        .replace("\u015f", "s")
        .replace("\u011f", "g")
        .replace("\u00fc", "u")
        .replace("\u00f6", "o")
        .replace("\u00e7", "c")
        .replace("ı", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
    )


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


_INTENT_RULES = [
    {
        "ids": ["email_summary", "read_emails"],
        "keywords": ["mail", "e-posta", "eposta", "email"],
        "reason": "Mail/e-posta ozetleme niyeti algilandi.",
    },
    {
        "ids": ["message_summary", "draft_message"],
        "keywords": ["mesaj", "whatsapp", "sms"],
        "reason": "Mesajlasma baglami algilandi.",
    },
    {
        "ids": ["calendar_overview"],
        "keywords": ["takvim", "randevu", "toplanti", "meeting"],
        "reason": "Takvim veya toplanti baglami algilandi.",
    },
    {
        "ids": ["file_finder"],
        "keywords": ["dosya", "pdf", "cv nerede", "nerede", "bul"],
        "reason": "Dosya bulma baglami algilandi.",
    },
    {
        "ids": ["device_cleanup_suggestions", "app_usage_review", "phone_assistant_luxway"],
        "keywords": ["uygulama", "depolama", "telefonu tara", "telefon", "sil", "temizle"],
        "reason": "Telefon, uygulama veya cihaz temizlik baglami algilandi.",
    },
    {
        "ids": ["report_helper"],
        "keywords": ["rapor"],
        "reason": "Rapor yardimi niyeti algilandi.",
    },
    {
        "ids": ["presentation_helper"],
        "keywords": ["sunum", "presentation"],
        "reason": "Sunum yardimi niyeti algilandi.",
    },
    {
        "ids": ["cv_helper"],
        "keywords": ["cv", "resume", "ozgecmis"],
        "reason": "CV yardimi niyeti algilandi.",
    },
    {
        "ids": ["workspace_helper"],
        "keywords": ["odev", "tez", "calisma alani", "workspace", "proje"],
        "reason": "Calisma alani veya proje yardimi niyeti algilandi.",
    },
]

_HIGH_RISK_ACTION_KEYWORDS = [
    "sil",
    "gonder",
    "ara",
    "mesaj at",
    "mail gonder",
    "uygulama sil",
    "telefon ayari degistir",
    "dosya sil",
    "kisisel veri",
    "kisisel veriye eris",
]


def _highest_risk(capabilities: Sequence[Dict[str, Any]], force_high: bool) -> str:
    if force_high:
        return "high"
    level = "low"
    for cap in capabilities:
        risk = str(cap.get("risk_level", "low")).lower()
        if _RISK_ORDER.get(risk, 0) > _RISK_ORDER.get(level, 0):
            level = risk
    return level


def _confidence(match_count: int, high_risk_action: bool) -> str:
    if match_count >= 2 or high_risk_action:
        return "high"
    if match_count == 1:
        return "medium"
    return "low"


def preview_agent_intent(user_text: str) -> Dict[str, Any]:
    """Return a read-only, rule-based preview of likely agent intent."""
    normalized = _normalize_text(user_text)
    matched_ids: List[str] = []
    reasons: List[str] = []

    for rule in _INTENT_RULES:
        if _contains_any(normalized, [_normalize_text(item) for item in rule["keywords"]]):
            matched_ids.extend(rule["ids"])
            reasons.append(str(rule["reason"]))

    high_risk_action = _contains_any(normalized, [_normalize_text(item) for item in _HIGH_RISK_ACTION_KEYWORDS])
    if high_risk_action:
        reasons.append("High-risk action keyword detected; confirmation is required before any future action.")
        if "mesaj at" in normalized and "draft_message" not in matched_ids:
            matched_ids.append("draft_message")
        if "mail gonder" in normalized and "read_emails" not in matched_ids:
            matched_ids.append("read_emails")
        if "ara" in normalized and "call_contact" not in matched_ids:
            matched_ids.append("call_contact")
        if "sil" in normalized and "app_cleanup_suggestions" not in matched_ids:
            matched_ids.append("app_cleanup_suggestions")

    deduped_ids = list(dict.fromkeys(matched_ids))
    matched_capabilities = [cap for cap in (get_agent_by_id(capability_id) for capability_id in deduped_ids) if cap]
    if not matched_capabilities:
        fallback = get_agent_by_id("workspace_helper")
        matched_capabilities = [fallback] if fallback else []

    high_caps = [cap for cap in matched_capabilities if str(cap.get("risk_level", "")).lower() == "high"]
    primary_capability = high_caps[0] if high_risk_action and high_caps else matched_capabilities[0] if matched_capabilities else None
    risk_level = _highest_risk(matched_capabilities, high_risk_action)
    confirmation = high_risk_action or any(requires_confirmation(cap) for cap in matched_capabilities)

    return {
        "matched_capabilities": matched_capabilities,
        "primary_capability": primary_capability,
        "confidence": _confidence(len(deduped_ids), high_risk_action),
        "risk_level": risk_level,
        "requires_user_confirmation": confirmation,
        "permission_required": primary_capability.get("permission_required") if primary_capability else "",
        "reason": " ".join(reasons) if reasons else "No specific capability keyword matched; workspace helper is suggested as a read-only fallback.",
        "read_only": True,
    }


_ACTION_STEP_TEMPLATES = {
    "email_summary": [
        "E-posta erisim izni kontrol edilir.",
        "Son e-postalar guvenli ve salt okunur sekilde okunur.",
        "Onemli basliklar ve aksiyon gerektiren maddeler ozetlenir.",
        "Kullaniciya yalnizca guvenli ozet gosterilir.",
    ],
    "read_emails": [
        "E-posta okuma izni ve kapsam siniri kontrol edilir.",
        "Izin olmadan hicbir posta kutusuna erisilmez.",
        "Okuma kapsami kullanici onayindan sonra belirlenir.",
        "Ham e-posta icerigi saklanmadan yalnizca ozet hazirlanir.",
    ],
    "message_summary": [
        "Mesaj kaynagi ve okuma izni kontrol edilir.",
        "Mesajlar yalnizca kullanici onayli kapsamda incelenir.",
        "Onemli noktalar guvenli ozet olarak gruplanir.",
        "Ham mesaj icerigi saklanmaz.",
    ],
    "draft_message": [
        "Kisi dogrulanir.",
        "Mesaj taslagi hazirlanir.",
        "Kullanici onayi istenir.",
        "Onay olmadan gonderim yapilmaz.",
    ],
    "call_contact": [
        "Kisi ve numara kullanici tarafindan dogrulanir.",
        "Arama niyeti tekrar onaylatilir.",
        "Gerekli telefon izni kontrol edilir.",
        "Onay olmadan arama baslatilmaz.",
    ],
    "device_cleanup_suggestions": [
        "Cihaz tarama izni ve platform uygunlugu kontrol edilir.",
        "Depolama ve uygulama kullanimi salt okunur metriklerle incelenir.",
        "Kullanilmayan uygulamalar icin oneriler listelenir.",
        "Onay olmadan silme veya ayar degisikligi yapilmaz.",
    ],
    "app_usage_review": [
        "Uygulama kullanim istatistigi izni kontrol edilir.",
        "Uygulama kullanimi salt okunur sekilde ozetlenir.",
        "Yogun kullanim ve dusuk kullanim sinyalleri ayrilir.",
        "Herhangi bir uygulama kaldirma islemi yapilmaz.",
    ],
    "phone_assistant_luxway": [
        "Luxway platform izni ve cihaz kapsam siniri kontrol edilir.",
        "Istenen telefon eylemi risk seviyesine gore siniflandirilir.",
        "Kullanici onayi alinmadan cihaz aksiyonu tetiklenmez.",
        "Bu scaffold yalnizca plan uretir.",
    ],
    "file_finder": [
        "Dosya arama kapsami ve izin siniri kontrol edilir.",
        "Dosya adlari ve metadata salt okunur sekilde taranir.",
        "Aday dosyalar kullaniciya liste halinde sunulur.",
        "Dosya acma, tasima veya silme islemi yapilmaz.",
    ],
    "cv_helper": [
        "CV hedefi ve kullanici tarafindan saglanan icerik belirlenir.",
        "Bolumler ve eksik alanlar planlanir.",
        "Taslak oneriler kullaniciya gosterilir.",
        "Kullanici onayi olmadan dosya yazilmaz veya paylasilmaz.",
    ],
    "report_helper": [
        "Rapor amaci ve kaynak kapsam belirlenir.",
        "Basliklar ve bolum sirasi planlanir.",
        "Ozet ve aksiyon maddeleri taslaklanir.",
        "Kaynak dosyalara yazma islemi yapilmaz.",
    ],
    "presentation_helper": [
        "Sunum hedefi ve hedef kitle belirlenir.",
        "Slayt akisi ve bolumler planlanir.",
        "Anlatim notlari icin taslak oneriler uretilir.",
        "Dosya olusturma veya duzenleme islemi yapilmaz.",
    ],
    "calendar_overview": [
        "Takvim okuma izni kontrol edilir.",
        "Toplanti ve randevu yogunlugu salt okunur sekilde incelenir.",
        "Cakisma ve bosluk onerileri hazirlanir.",
        "Takvim etkinligi olusturma veya degistirme yapilmaz.",
    ],
    "workspace_helper": [
        "Calisma hedefi ve proje baglami ayrilir.",
        "Gorevler ve sonraki adimlar planlanir.",
        "Oncelik ve zamanlama onerileri hazirlanir.",
        "Gercek dosya veya hafiza yazma islemi yapilmaz.",
    ],
}

_INTENT_LABELS = {
    "email_summary": "email_summary_request",
    "read_emails": "email_read_preview_request",
    "message_summary": "message_summary_request",
    "draft_message": "message_draft_or_send_request",
    "call_contact": "phone_call_request",
    "device_cleanup_suggestions": "device_cleanup_request",
    "app_usage_review": "app_usage_review_request",
    "phone_assistant_luxway": "luxway_phone_assistant_request",
    "file_finder": "file_finder_request",
    "cv_helper": "cv_helper_request",
    "report_helper": "report_helper_request",
    "presentation_helper": "presentation_helper_request",
    "calendar_overview": "calendar_overview_request",
    "workspace_helper": "workspace_helper_request",
}

_PERSONAL_DATA_PERMISSIONS = {
    "email_read",
    "message_read",
    "read_only_content",
    "calendar_read",
    "file_list",
    "phone_call",
    "device_storage_stats",
    "app_usage_stats",
    "notification_read",
}


def _has_high_risk_action(user_text: str) -> bool:
    normalized = _normalize_text(user_text)
    return _contains_any(normalized, [_normalize_text(item) for item in _HIGH_RISK_ACTION_KEYWORDS])


def _needs_personal_data_permission(capabilities: Sequence[Dict[str, Any]]) -> bool:
    for cap in capabilities:
        permission = str(cap.get("permission_required", ""))
        if permission in _PERSONAL_DATA_PERMISSIONS:
            return True
    return False


def _action_steps(primary_capability: Dict[str, Any] | None) -> List[str]:
    if not primary_capability:
        return [
            "Kullanici niyeti salt okunur sekilde siniflandirilir.",
            "Gerekli capability ve izinler belirlenir.",
            "Kullanici onayi gerekip gerekmedigi isaretlenir.",
            "Gercek islem yapilmaz.",
        ]
    cap_id = str(primary_capability.get("id", ""))
    return list(_ACTION_STEP_TEMPLATES.get(cap_id, _ACTION_STEP_TEMPLATES["workspace_helper"]))


def plan_agent_action(user_text: str) -> Dict[str, Any]:
    """Build a read-only action plan; no external action or memory write occurs."""
    preview = preview_agent_intent(user_text)
    matched_capabilities = list(preview.get("matched_capabilities", []))
    primary_capability = preview.get("primary_capability")
    high_risk_action = _has_high_risk_action(user_text)
    personal_data_access = _needs_personal_data_permission(matched_capabilities)
    risk_level = "high" if high_risk_action else str(preview.get("risk_level", "low"))
    requires_user_confirmation = bool(preview.get("requires_user_confirmation")) or high_risk_action or personal_data_access

    return {
        "action_id": str(uuid.uuid4()),
        "user_intent": _INTENT_LABELS.get(str(primary_capability.get("id", "")) if primary_capability else "", "general_agent_request"),
        "primary_capability": primary_capability,
        "matched_capabilities": matched_capabilities,
        "risk_level": risk_level,
        "permission_required": preview.get("permission_required", ""),
        "requires_user_confirmation": requires_user_confirmation,
        "can_execute_now": False,
        "execution_status": "not_executed",
        "read_only": True,
        "raw_data_stored": False,
        "planned_steps": _action_steps(primary_capability),
        "blocked_reason": "Read-only scaffold: external actions, device access, message/mail sending, file operations, and memory writes are disabled.",
        "safety_note": "High-risk or personal-data actions require explicit user permission and confirmation before any future execution path.",
    }


_SAFETY_SENSITIVE_KEYWORDS = [
    "hassas",
    "mahrem",
    "ozel",
    "gizli",
    "kriz",
    "tehlike",
    "travma",
    "sifre",
    "parola",
    "kimlik",
    "kisisel veri",
]


def _recommended_mode(user_text: str, agent_preview: Dict[str, Any], memory_preview: Dict[str, Any]) -> str:
    normalized = _normalize_text(user_text)
    signal_types = {str(item.get("type", "")) for item in memory_preview.get("candidate_signals", [])}

    if _contains_any(normalized, _SAFETY_SENSITIVE_KEYWORDS):
        return "safety_sensitive"
    if _contains_any(normalized, ["telefon", "uygulama", "depolama", "tara"]):
        return "luxway_planning"
    if _contains_any(normalized, ["ambrosia"]):
        return "ambrosia"
    if _contains_any(normalized, ["gorsel", "amber", "pixel", "imza", "renk"]) or signal_types & {"visual_preference", "lux_visual_style", "lux_ambrosia_reference"}:
        return "visual_style_memory"
    if _contains_any(normalized, ["ruya", "sahne", "kamera", "cizim"]) or "dream_scene_reference" in signal_types:
        return "dream_scene"
    if _contains_any(normalized, ["ses", "frekans", "ton"]) or "audio_signal" in signal_types:
        return "audio_signal_future"
    if _contains_any(normalized, ["cv", "ozgecmis"]):
        return "cv_builder"
    if _contains_any(normalized, ["rapor"]):
        return "report_builder"
    if _contains_any(normalized, ["sunum", "presentation"]):
        return "presentation_builder"
    if _contains_any(normalized, ["odev", "tez", "dosya duzenle", "dosya", "workspace", "calisma alani"]):
        return "workspace"
    if _contains_any(normalized, ["mail", "e-posta", "eposta", "email", "mesaj", "whatsapp", "sms"]):
        return "personal_agent"

    primary = agent_preview.get("primary_capability") or {}
    primary_id = str(primary.get("id", ""))
    if primary_id == "cv_helper":
        return "cv_builder"
    if primary_id == "report_helper":
        return "report_builder"
    if primary_id == "presentation_helper":
        return "presentation_builder"
    if primary_id in {"workspace_helper", "file_finder"}:
        return "workspace"
    if primary_id:
        return "personal_agent"
    return "normal_chat"


def _recommended_next_step(mode: str, action_plan: Dict[str, Any]) -> str:
    if mode == "safety_sensitive":
        return "Keep the response supportive and avoid storing raw sensitive data."
    if mode == "luxway_planning":
        return "Show the read-only Luxway plan and ask for explicit permission before any future device step."
    if mode in {"visual_style_memory", "ambrosia", "dream_scene", "audio_signal_future"}:
        return "Show the candidate signal preview without writing memory."
    if mode in {"cv_builder", "report_builder", "presentation_builder", "workspace"}:
        return "Use the plan as guidance and ask before creating or editing any file."
    if action_plan.get("requires_user_confirmation"):
        return "Explain the required permission and ask for confirmation before future execution."
    return "Continue normal chat with the read-only analysis context."


def _permissions_needed(agent_preview: Dict[str, Any], action_plan: Dict[str, Any]) -> List[str]:
    permissions: List[str] = []
    for cap in agent_preview.get("matched_capabilities", []):
        permission = str(cap.get("permission_required", "")).strip()
        if permission:
            permissions.append(permission)
    plan_permission = str(action_plan.get("permission_required", "")).strip()
    if plan_permission:
        permissions.append(plan_permission)
    return list(dict.fromkeys(permissions))


def _input_summary(user_text: str, mode: str) -> Dict[str, Any]:
    normalized = _normalize_text(user_text)
    return {
        "has_text": bool((user_text or "").strip()),
        "char_count": len(user_text or ""),
        "recommended_mode": mode,
        "contains_high_risk_action": _has_high_risk_action(user_text),
        "contains_sensitive_signal": _contains_any(normalized, _SAFETY_SENSITIVE_KEYWORDS),
    }


def analyze_agent_request(user_text: str, source_modality: str = "text") -> Dict[str, Any]:
    """Unify agent intent, memory preview, and action planning without side effects."""
    from multimodal_memory_scaffold import preview_memory_signals

    agent_preview = preview_agent_intent(user_text)
    memory_preview = preview_memory_signals(user_text, source_modality)
    action_plan = plan_agent_action(user_text)
    mode = _recommended_mode(user_text, agent_preview, memory_preview)
    risk_level = "high" if mode == "safety_sensitive" else str(action_plan.get("risk_level", agent_preview.get("risk_level", "low")))
    requires_user_confirmation = bool(action_plan.get("requires_user_confirmation")) or risk_level == "high"

    return {
        "analysis_id": str(uuid.uuid4()),
        "input_summary": _input_summary(user_text, mode),
        "agent_preview": agent_preview,
        "memory_preview": memory_preview,
        "action_plan": action_plan,
        "recommended_mode": mode,
        "recommended_next_step": _recommended_next_step(mode, action_plan),
        "risk_level": risk_level,
        "requires_user_confirmation": requires_user_confirmation,
        "permissions_needed": _permissions_needed(agent_preview, action_plan),
        "can_execute_now": False,
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
        "safety_note": "Unified analysis is read-only; no email, phone, message, file, app, or memory write operation was performed.",
    }
