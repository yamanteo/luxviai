"""Personal agent and Luxway capability scaffold."""

from __future__ import annotations

from typing import Any, Dict, List


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
