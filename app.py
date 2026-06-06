from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import random
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field
from learning.dashboard_engine import LearningDashboardEngine
from learning.pipeline import LearningPipeline
from learning.cost_logger import CostLogger, estimate_tokens
from learning.efficiency_router import EfficiencyRouter
from learning.token_budget_policy import TokenBudgetPolicy
from audio_privacy_boundary import preview_audio_privacy_boundary
from audio_signal_schema import audio_signal_schema, audio_status_snapshot, preview_audio_signal
from agent_decision_trace import build_agent_decision_trace
from cost_privacy_policy import cost_privacy_policy, preview_cost_privacy
from luxway_capabilities import luxway_capability_registry, luxway_status_snapshot, preview_luxway_command
from luxway_data_preview import preview_luxway_data
from luxway_device_safety import preview_luxway_device_safety
from luxway_permission_model import luxway_permission_model, preview_luxway_permission
from luxway_weekly_report import luxway_weekly_report_schema, preview_luxway_weekly_report
from model_router_config import model_router_config, model_router_status, preview_model_hint, preview_model_route
from agent_scaffold import (
    ANDROID_PERMISSION_NOTES,
    IOS_PERMISSION_NOTES,
    PRIVACY_RULES,
    analyze_agent_request,
    all_capabilities,
    luxway_capabilities,
    plan_agent_action,
    personal_agent_capabilities,
    preview_agent_intent,
)
from multimodal_memory_scaffold import (
    DEFAULT_MEMORY_FIELDS,
    MULTIMODAL_MEMORY_TEMPLATES,
    build_memory_signal,
    multimodal_memory_schema,
    preview_memory_signals,
    validate_memory_signal,
)
from mode_registry import mode_registry, preview_mode_command
from night_radio_voice import preview_night_radio_voice
from permission_boundary import preview_permission_boundary
from router_scaffold import preview_router_decision
from safe_memory_retrieval import preview_safe_memory_retrieval, safe_memory_policy
from workspace_builder_preview import build_workspace_builder_preview
from workspace_command_parser import parse_workspace_command
from workspace_context_notes import preview_workspace_context_note
from workspace_export_preview import build_workspace_export_preview
from workspace_scaffold import build_workspace_preview, build_workspace_separation_preview, sample_workspace, workspace_schema
from visual_ambrosia_state import preview_ambrosia_state
from visual_dream_scene_state import preview_dream_scene_state
from visual_prompt_builder import build_visual_prompt_preview
from visual_scene_lock import preview_scene_lock
from visual_style_ratio import preview_visual_style_ratio
from visual_style_registry import preview_visual_style, visual_style_registry
from voice_mode_registry import preview_voice_mode, voice_mode_registry, voice_status_snapshot

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

# =========================================================
# ENV / SETUP
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
USERS_DIR = DATA_DIR / "users"

load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("DEEPSEEK_API_KEY")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "luxviai_gizli_token_2026")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
DEEPL_API_BASE = os.getenv("DEEPL_API_BASE", "").strip()  # e.g. https://api-free.deepl.com
try:
    STREAM_CHUNK_DELAY = max(0.0, min(float(os.getenv("STREAM_CHUNK_DELAY", "0.02")), 0.2))
except ValueError:
    STREAM_CHUNK_DELAY = 0.02


def mask_key(value: Optional[str]) -> str:
    if not value:
        return "<empty>"
    v = value.strip()
    if len(v) <= 10:
        return v
    return f"{v[:6]}...{v[-4:]}"

for d in [STATIC_DIR, DATA_DIR, USERS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "luxviai.log", encoding="utf-8"),
    ],
)


def ms_since(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def log_latency(event: str, **fields: Any) -> None:
    safe_fields = " ".join(f"{k}={v}" for k, v in fields.items())
    logging.info(f"[LATENCY] {event} {safe_fields}".strip())


FILE_LOCK = Lock()

if not API_KEY:
    logging.error("DEEPSEEK_API_KEY bulunamadı! Lütfen .env dosyasını kontrol et.")
    logging.warning("Uygulama fallback modunda çalışacak. API çağrıları çalışmaz.")
else:
    logging.info("DEEPSEEK_API_KEY yüklendi.")

logging.info(f"BASE_DIR: {BASE_DIR}")
logging.info(f".env path: {BASE_DIR / '.env'}")
logging.info(f"DEEPSEEK_API_KEY mask: {mask_key(API_KEY)} len={len(API_KEY or '')}")

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com") if API_KEY else None

try:
    ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
except ZoneInfoNotFoundError:
    ISTANBUL_TZ = timezone(timedelta(hours=3))

app = FastAPI(title="Luxviai — Luxsarısı OS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Learning Lab foundation (Aşama-1: hafif entegrasyon)
learning_pipeline = LearningPipeline(BASE_DIR)
learning_dashboard_engine = LearningDashboardEngine(BASE_DIR)
token_budget_policy = TokenBudgetPolicy()
efficiency_router = EfficiencyRouter()
cost_logger = CostLogger(BASE_DIR)

# Aşama-1 Learning Lab dosya temeli (boşsa oluştur)
try:
    if USERS_DIR.exists():
        any_user = False
        for p in USERS_DIR.iterdir():
            if p.is_dir():
                any_user = True
                learning_pipeline.ensure_foundation(p.name)
        if not any_user:
            learning_pipeline.ensure_foundation("default_user")
    else:
        learning_pipeline.ensure_foundation("default_user")
except Exception as e:
    logging.warning(f"Learning foundation init skipped: {e}")

# =========================================================
# MODELS
# =========================================================
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    mode: str = "luxviai"
    ghost_hesitation: bool = False
    client_signals: Dict[str, Any] = Field(default_factory=dict)
    location: str = "İstanbul"


class NoteCreate(BaseModel):
    user_id: str = "default_user"
    text: str = Field(min_length=1, max_length=2000)


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    target_lang: str = "EN"
    source_lang: Optional[str] = None


class ExplainRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    user_lang: str = "tr"
    force_translate: bool = False


class MemorySignalPreviewRequest(BaseModel):
    id: str = ""
    type: str
    title: str = ""
    summary: str = ""
    source_modality: str = "text"
    sensitivity: str = "low"
    retention: str = "session"
    created_at: str = ""
    updated_at: str = ""
    tags: List[str] = Field(default_factory=list)
    raw_data_stored: bool = False


class AgentIntentPreviewRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    source_modality: str = "text"


class WorkspacePreviewRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    content: str = Field(default="", max_length=12000)


class WorkspaceCommandParseRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    current_blocks: List[Dict[str, Any]] = Field(default_factory=list)


class WorkspaceExportPreviewRequest(BaseModel):
    blocks: List[Dict[str, Any]] = Field(default_factory=list)
    export_type: str = Field(default="copy", max_length=40)


class WorkspaceContextPreviewRequest(BaseModel):
    context_note: str = Field(default="", max_length=4000)
    project_type: str = Field(default="", max_length=200)
    current_blocks: List[Dict[str, Any]] = Field(default_factory=list)


class WorkspaceBuilderPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    content: str = Field(default="", max_length=12000)
    context_note: str = Field(default="", max_length=4000)
    project_type: str = Field(default="", max_length=200)


class VisualStylePreviewRequest(BaseModel):
    prompt: str = Field(default="", max_length=4000)
    requested_styles: List[str] = Field(default_factory=list)
    mode: str = Field(default="", max_length=100)


class VisualStyleRatioPreviewRequest(BaseModel):
    prompt: str = Field(default="", max_length=4000)
    ratio_text: str = Field(default="", max_length=4000)
    requested_styles: List[str] = Field(default_factory=list)
    mode: str = Field(default="", max_length=100)


class VisualAmbrosiaPreviewRequest(BaseModel):
    feeling_text: str = Field(default="", max_length=4000)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    style_ratio: Dict[str, Any] = Field(default_factory=dict)


class VisualDreamScenePreviewRequest(BaseModel):
    scene_text: str = Field(default="", max_length=4000)
    style_hint: str = Field(default="", max_length=1000)
    locked_elements: List[Any] = Field(default_factory=list)


class VisualSceneLockPreviewRequest(BaseModel):
    current_scene_state: Dict[str, Any] = Field(default_factory=dict)
    new_detail: str = Field(default="", max_length=4000)
    lock_strength: float = Field(default=1.0, ge=0.0, le=1.0)


class VisualPromptPreviewRequest(BaseModel):
    prompt: str = Field(default="", max_length=4000)
    mode: str = Field(default="", max_length=100)
    style_ratios: Dict[str, Any] = Field(default_factory=dict)
    scene_state: Dict[str, Any] = Field(default_factory=dict)
    ambrosia_state: Dict[str, Any] = Field(default_factory=dict)
    locked_elements: List[Any] = Field(default_factory=list)


class VoiceModePreviewRequest(BaseModel):
    command: str = Field(default="", max_length=2000)
    context: str = Field(default="", max_length=4000)
    response_size: str = Field(default="medium", max_length=50)
    input_modality: str = Field(default="text", max_length=50)


class AudioSignalPreviewRequest(BaseModel):
    description: str = Field(default="", max_length=2000)
    simulated_voice_note: str = Field(default="", max_length=2000)
    context: str = Field(default="", max_length=4000)


class AudioPrivacyBoundaryRequest(BaseModel):
    command: str = Field(default="", max_length=2000)
    audio_context: str = Field(default="", max_length=4000)
    consent_state: str = Field(default="not_granted", max_length=50)


class NightRadioVoicePreviewRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    mood: str = Field(default="", max_length=1000)
    response_size: str = Field(default="medium", max_length=50)
    mode: str = Field(default="", max_length=100)


class LuxwayPreviewCommandRequest(BaseModel):
    command: str = Field(default="", max_length=2000)
    platform: str = Field(default="unknown", max_length=50)
    context: str = Field(default="", max_length=4000)


class LuxwayPermissionPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=2000)
    platform: str = Field(default="unknown", max_length=50)


class LuxwayWeeklyReportPreviewRequest(BaseModel):
    platform: str = Field(default="unknown", max_length=50)
    report_focus: str = Field(default="", max_length=1000)
    context: str = Field(default="", max_length=4000)


class LuxwayDataPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=2000)
    domain: str = Field(default="", max_length=50)
    platform: str = Field(default="unknown", max_length=50)


class LuxwayDeviceSafetyPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=2000)
    platform: str = Field(default="unknown", max_length=50)


class ModelRouterPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    task_type: str = Field(default="", max_length=80)
    sensitivity: str = Field(default="normal", max_length=50)
    response_size: str = Field(default="medium", max_length=50)


class ModelRouterHintPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    source_area: str = Field(default="general", max_length=50)
    task_type: str = Field(default="", max_length=80)
    sensitivity: str = Field(default="normal", max_length=50)
    response_size: str = Field(default="medium", max_length=50)


class CostPrivacyPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    task_type: str = Field(default="", max_length=80)
    sensitivity: str = Field(default="normal", max_length=50)
    estimated_tokens_bucket: str = Field(default="", max_length=50)


class SafeMemoryRetrievalPreviewRequest(BaseModel):
    command: str = Field(default="", max_length=4000)
    task_type: str = Field(default="", max_length=80)
    sensitivity: str = Field(default="normal", max_length=50)
    requested_memory_type: str = Field(default="", max_length=80)


# =========================================================
# CONSTANTS
# =========================================================
ALLOWED_MODES = {"luxviai", "luxching", "luxdream", "luxta", "luxeph"}

THEMES = {
    "görülmeme": 0,
    "kontrol kaybı": 0,
    "değersizlik": 0,
    "terk edilme": 0,
    "belirsizlik": 0,
    "özlem": 0,
    "yorgunluk": 0,
    "yön kaybı": 0,
    "yakınlık": 0,
    "çatışma": 0,
}

CRISIS_KEYWORDS = [
    "intihar",
    "kendime zarar",
    "kendimi öldüreceğim",
    "ölmek istiyorum",
    "yaşamak istemiyorum",
    "dayanamıyorum",
    "şiddet",
    "tecavüz",
    "istismar",
]

IMMEDIATE_RISK_PATTERNS = [
    "kendimi öldüreceğim",
    "intihar edeceğim",
    "canıma kıyacağım",
    "kendime zarar vereceğim",
    "şimdi yapacağım",
    "bu gece yapacağım",
    "planım var",
    "vedalaşmak istiyorum",
    "artık yaşamak istemiyorum",
    "ölmek istiyorum",
]

CONTEXTUAL_CRISIS_MARKERS = [
    "geçmişte",
    "eskiden",
    "çocukken",
    "bir zamanlar",
    "haberlerde",
    "filmde",
    "dizide",
    "kitapta",
    "makalede",
    "araştırıyorum",
    "ne demek",
    "nedir",
    "sence",
    "bir arkadaşım",
    "bir karakter",
    "örnek",
    "soru",
    "konu",
    "hakkında",
]

ABUSE_IMMEDIATE_MARKERS = [
    "şu an güvende değilim",
    "beni tehdit ediyor",
    "bana vurdu",
    "beni zorluyor",
    "evden çıkamıyorum",
    "yardım çağır",
]

LUXCHING_SYMBOLS = [
    {"name": "Yaratılış", "meaning": "Yaratıcı güç, güçlü başlangıç, içteki itki."},
    {"name": "Kabul", "meaning": "Yumuşak dayanıklılık, sabır, alıcı zemin."},
    {"name": "Başlangıçtaki Güçlük", "meaning": "Başlangıçta bulanıklık, sonra şekillenen yol."},
    {"name": "Süreklilik", "meaning": "Düzenli olanın taşıdığı sakin güç."},
    {"name": "Açılım", "meaning": "İçin yavaşça açılması, acele etmeyen netlik."},
    {"name": "Eşik", "meaning": "Bir kapının önünde bekleme, geçmeden önce hissetme."},
    {"name": "Dönüş", "meaning": "Uzaklaşanın başka bir biçimde geri gelişi."},
    {"name": "İç Işık", "meaning": "Sessiz fark ediş, görünmeden yön veren küçük netlik."},
]

STOPWORDS = {
    "ve", "bir", "çok", "daha", "için", "gibi", "ama", "olan", "olarak", "şu",
    "şey", "ben", "sen", "sana", "bana", "ile", "de", "da", "ki", "mi", "mı",
    "mu", "mü", "olanı", "şimdi", "hala", "bile", "bunu", "şunu", "böyle",
    "diye", "var", "yok", "hem", "ya", "veya", "çünkü", "ise"
}

KEYWORD_DROPWORDS = {
    "ol", "olur", "oldu", "oluyor", "olacak", "olmak", "olunca",
    "miyim", "mıyım", "misin", "mısın", "musun", "müsün",
    "acaba", "yani", "hani", "artık", "tamam", "evet", "hayır",
    "belki", "şeyler", "falan", "filan", "bence", "sence",
}

TOPIC_QUALIFIERS = {
    "yeni", "eski", "ilk", "son", "mevcut", "gelecek", "şimdiki", "şuanki"
}

SHORT_IMPORTANT_TOKENS = {"iş", "ev", "aşk", "aile", "okul"}

# Hafıza anahtar kelimelerinde selamlaşma/gürültü ifadelerini temizler.
MEMORY_NOISE_WORDS = {
    "merhaba", "selam", "slm", "hey", "hi", "hello", "hola", "alo",
    "nasilsin", "naber", "nbr", "iyiyim", "iyidir", "iyim",
    "gunaydin", "iyiaksamlar", "iyigeceler", "tesekkur", "tesekkurler",
    "ok", "oke", "okey", "tamam", "peki", "hmm", "hmmm", "h", "sss", "sus",
    "luxviai", "luxdream", "luxching", "luxta", "luxeph", "mod", "modu", "soru",
}

# Duygusal/tematik ve imgelenebilir alanları öne çıkarmak için temel kökler.
THEMATIC_TOKEN_ROOTS = (
    "kaygi", "anksiyet", "kork", "korkunc", "panik", "uzgun", "huzun", "yas",
    "yalniz", "yalnizlik", "bosluk", "deger", "degersiz", "utanc", "ofke",
    "sinir", "stres", "bunalt", "sikis", "tuken", "umut", "arzu", "etik",
    "belirsiz", "kararsiz", "ikilem", "travma", "ruya", "sembol", "imge",
    "anlam", "amac", "gelecek", "gecmis", "kayip", "ozlem", "bag", "baglan",
    "iliski", "yakinlik", "guven", "aile", "is", "kariyer", "basari",
    "basarisiz", "sikici", "mutlu", "mutsuz", "huzur",
)

TERM_EXPLANATIONS_TR = {
    "anksiyete": "Kaygının yoğun ve süreğen biçimi; zihin ve bedenin tetikte kalması.",
    "depresyon": "Uzun süren çökkünlük, isteksizlik ve enerji düşüşüyle seyreden klinik durum.",
    "travma": "Kişinin baş etme kapasitesini aşan zorlayıcı yaşantının bıraktığı psikolojik iz.",
    "dissosiyasyon": "Yoğun stres altında kopma, uzaklaşma veya gerçek dışılık hissi.",
    "panik": "Ani başlayan yoğun korku dalgası; çarpıntı ve nefes sıkışması gibi belirtilerle gelebilir.",
    "psikanaliz": "Bilinçdışı süreçleri, iç çatışmaları ve tekrar örüntülerini inceleyen yaklaşım.",
    "klinik": "Sağlık/ruh sağlığı değerlendirme ve uygulama alanı.",
    "etik": "İyi-kötü, doğru-yanlış ve sorumlulukla ilgili ilke ve değerlendirmeler bütünü.",
    "arzu": "Kişiyi bir şeye yönelten içsel isteme ve çekim gücü.",
    "belirsizlik": "Sonucun net olmadığı durumda oluşan açıkta kalma hissi.",
    "kararsızlık": "Seçenekler arasında net bir seçim yapamama durumu.",
    "özlem": "Uzakta ya da eksik olana yönelen duygusal çekim.",
    "yalnızlık": "Yeterli duygusal bağ hissedememe durumunun yarattığı içsel boşluk.",
    "kırgınlık": "İncinme sonrası içe kapanma veya mesafe koyma eğilimi.",
    "stres": "Zorlayıcı taleplere karşı bedenin ve zihnin verdiği yüklenme tepkisi.",
    "tükenmişlik": "Süreğen yük ve baskı sonrası enerji, motivasyon ve dayanıklılıkta düşüş.",
    "bağlanma": "Yakınlık kurma, güvenme ve ayrılığa verilen duygusal tepki düzeni.",
}

LUXTA_REPLIES = ["Anlıyorum.", "Dinliyorum.", "Buradayım.", "Hmm.", "Devam et.", "Yavaşça."]

ANALYSIS_LAYER_NAMES = [
    "emotion",
    "narrative",
    "contradiction",
    "relationship",
    "symbolic",
    "dream",
    "existential",
    "memory",
    "emotional_graph",
    "hidden",
    "dynamic_tone",
    "safety_ethics",
    "time_ecology",
    "cultural_epistemic",
    "reflection",
    "human_layer",
]

THEORY_LENSES = {
    "Hegel": "diyalektik çatışma, dönüşüm, gerilimin daha geniş bir biçimde taşınması",
    "Slavoj Žižek": "ideolojik fantazi, görünmeyen arzunun gündelik cümlede saklanması",
    "Jacques Lacan": "arzu, eksiklik, dilin kullanıcıyı kurma biçimi",
    "Melanie Klein": "nesne ilişkileri, bölme, iyi/kötü iç nesne salınımı",
    "Donald Winnicott": "geçiş alanı, sahici/sahte benlik, güvenli oyun zemini",
    "John Bowlby": "bağlanma, yaklaşma/geri çekilme, güven arayışı",
    "Peter Fonagy": "mentalizasyon, kendi ve öteki zihnini düşünebilme",
    "Otto Kernberg": "yoğun ilişki gerilimi, ilkel savunma izleri",
    "Heinz Kohut": "kendilik, görülme ve aynalanma ihtiyacı",
    "Bessel van der Kolk": "travmanın bedensel izi, beden hafızası",
    "Peter Levine": "somatik sıkışma ve tamamlanmamış savunma enerjisi",
    "Pat Ogden": "sensorimotor izler, duruş, gerilim, bedensel ritim",
    "Rollo May": "varoluşsal cesaret, özgünlük, anlam gerilimi",
    "James Bugental": "anlık farkındalık, şimdi ve burada derinliği",
    "Jaak Panksepp": "temel duygusal sistemler, arama, korku, öfke, bakım",
    "Mark Solms": "duygu ve nöropsikanalitik anlamlandırma",
    "Gayatri Chakravorty Spivak": "temsil edilme, sessizleştirilme, sesi duyulmayan özne",
    "Antonio Gramsci": "hegemonya, içselleştirilmiş baskı, gündelik rıza",
    "Isaiah Berlin": "pozitif/negatif özgürlük ve seçim alanı",
    "Jean-Paul Sartre": "sorumluluk, kader algısı, özgürlük yükü",
    "Lefebvre/de Certeau": "gündelik yaşam, küçük taktikler, mekansal ritimler",
    "Stanley Milgram": "otorite, itaat, sınır ve baskı",
    "Fyodor Dostoyevski": "polifonik bilinç, itiraf dürtüsü, iç ses çokluğu",
    "Lev Tolstoy": "ruhun diyalektiği, sadeleşme arzusu, etik berraklık",
}

# =========================================================
# HELPERS
# =========================================================
def now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_user_id(raw: str) -> str:
    raw = (raw or "default_user").strip().lower()
    raw = re.sub(r"[^a-z0-9_\-]", "_", raw)
    return raw[:64] or "default_user"


def parse_iso(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any):
    with FILE_LOCK:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def user_root(user_id: str) -> Path:
    root = USERS_DIR / safe_user_id(user_id)
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    return root


def profile_path(user_id: str) -> Path:
    return user_root(user_id) / "profile.json"


def notes_path(user_id: str) -> Path:
    return user_root(user_id) / "notes.json"


def garden_path(user_id: str) -> Path:
    return user_root(user_id) / "memory_garden.json"


def active_session_path(user_id: str) -> Path:
    return user_root(user_id) / "active_session.json"


def sessions_dir(user_id: str) -> Path:
    return user_root(user_id) / "sessions"


def sessions_index_path(user_id: str) -> Path:
    return user_root(user_id) / "sessions_index.json"


def session_file_path(user_id: str, session_id: str) -> Path:
    return sessions_dir(user_id) / f"{session_id}.json"


def cleanup_old_sessions(user_id: str, days: int = 7):
    user_id = safe_user_id(user_id)
    index_path = sessions_index_path(user_id)
    if not index_path.exists():
        return

    index = load_json(index_path, [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    new_index = []

    for sess in index:
        try:
            created_at = parse_iso(sess.get("created_at", now_iso()))
            created_at_utc = created_at.astimezone(timezone.utc) if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
            if created_at_utc > cutoff:
                new_index.append(sess)
            else:
                old_path = session_file_path(user_id, sess["session_id"])
                if old_path.exists():
                    old_path.unlink()
        except Exception:
            new_index.append(sess)

    save_json(index_path, new_index)


def clamp_int(v: Any, lo: int, hi: int, default: int = 5) -> int:
    try:
        x = int(v)
        return max(lo, min(hi, x))
    except Exception:
        return default


def normalize_keyword_token(raw_token: str) -> str:
    t = (raw_token or "").strip().lower()
    t = t.replace("’", "").replace("'", "")
    if not t:
        return ""

    for suf in ["mıyım", "miyim", "muyum", "müyüm", "mısın", "misin", "musun", "müsün", "mı", "mi", "mu", "mü"]:
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break

    for suf in ["larımız", "lerimiz", "ımız", "imiz", "umuz", "ümüz", "lar", "ler"]:
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            t = t[: -len(suf)]
            break

    if t.endswith(("ım", "im", "um", "üm")) and len(t) > 4:
        t = t[:-2]

    if t.startswith("başar"):
        t = "başarı"
    if t.startswith("iş"):
        t = "iş"

    if t in STOPWORDS or t in KEYWORD_DROPWORDS:
        return ""
    if len(t) <= 2 and t not in SHORT_IMPORTANT_TOKENS:
        return ""
    return t


def tokenize(text: str) -> List[str]:
    out: List[str] = []
    for raw in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", text or ""):
        norm = normalize_keyword_token(raw)
        if norm:
            out.append(norm)
    return out


def fold_turkish_ascii(value: str) -> str:
    table = str.maketrans({
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "İ": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u",
    })
    return (value or "").translate(table).lower()


def is_memory_noise_token(token: str) -> bool:
    folded = fold_turkish_ascii(token)
    return token in MEMORY_NOISE_WORDS or folded in MEMORY_NOISE_WORDS


def is_thematic_token(token: str) -> bool:
    if not token or is_memory_noise_token(token):
        return False
    folded = fold_turkish_ascii(token)
    return any(folded.startswith(root) for root in THEMATIC_TOKEN_ROOTS)


def is_thematic_phrase(value: str) -> bool:
    parts = [p for p in (value or "").split() if p]
    if not parts:
        return False
    return any(is_thematic_token(p) for p in parts)


def thematic_tokens_from_text(text: str, limit: int = 6) -> List[str]:
    picked: List[str] = []
    seen = set()
    for token in tokenize(text):
        if token in seen:
            continue
        if not is_thematic_token(token):
            continue
        seen.add(token)
        picked.append(token)
        if len(picked) >= limit:
            break
    return picked


def has_thematic_signal(text: str) -> bool:
    return len(thematic_tokens_from_text(text, limit=1)) > 0


def keyword_score(query: str, text: str) -> int:
    q = set(tokenize(query))
    t = (text or "").lower()
    score = 0
    for kw in q:
        if kw in t:
            score += 2
    return score


def contains_any(text: str, items: List[str]) -> bool:
    low = (text or "").lower()
    return any(item in low for item in items)


def is_model_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "authentication fails" in msg
        or "authentication_error" in msg
        or "401 unauthorized" in msg
        or "invalid api key" in msg
        or "api key" in msg and "invalid" in msg
    )


def top_keywords(texts: List[str], limit: int = 8) -> List[str]:
    unigram_counts = Counter()
    bigram_counts = Counter()

    for text in texts:
        tokens = [t for t in tokenize(text) if not is_memory_noise_token(t)]
        if not tokens:
            continue
        unigram_counts.update(tokens)
        for a, b in zip(tokens, tokens[1:]):
            if a == b:
                continue
            if is_memory_noise_token(a) or is_memory_noise_token(b):
                continue
            bigram_counts[f"{a} {b}"] += 1

    ranked_phrases: List[tuple[float, str]] = []
    for phrase, count in bigram_counts.items():
        parts = phrase.split()
        first = parts[0]
        thematic = any(is_thematic_token(p) for p in parts)
        if count == 1 and not thematic and first not in TOPIC_QUALIFIERS:
            continue
        score = count * 2.0 + (1.2 if first in TOPIC_QUALIFIERS else 0.0) + (1.0 if thematic else 0.0)
        ranked_phrases.append((score, phrase))
    ranked_phrases.sort(key=lambda x: x[0], reverse=True)

    results: List[str] = []
    seen = set()
    phrase_budget = max(1, limit // 2)

    for _, phrase in ranked_phrases:
        if phrase not in seen:
            seen.add(phrase)
            results.append(phrase)
        if len(results) >= phrase_budget:
            break

    thematic_unigrams: List[str] = []
    repeated_unigrams: List[str] = []
    for token, count in unigram_counts.most_common(limit * 4):
        if token in TOPIC_QUALIFIERS:
            continue
        if is_memory_noise_token(token):
            continue
        if is_thematic_token(token):
            thematic_unigrams.append(token)
            continue
        if count >= 2 and len(token) >= 4:
            repeated_unigrams.append(token)

    for token in thematic_unigrams + repeated_unigrams:
        if token not in seen:
            seen.add(token)
            results.append(token)
        if len(results) >= limit:
            break

    return results[:limit]


def compact_text(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def fold_identity_text(text: str) -> str:
    folded = (text or "").strip().lower()
    replacements = {
        "ı": "i",
        "İ": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    }
    for src, dst in replacements.items():
        folded = folded.replace(src, dst)
    return re.sub(r"\s+", " ", folded)


def normalize_identity_name(name: str) -> str:
    raw = re.sub(r"[^\wÇĞİÖŞÜçğıöşü\s-]", "", name or "", flags=re.UNICODE)
    parts = [p for p in re.split(r"\s+", raw.strip()) if p]
    parts = parts[:2]
    cleaned = " ".join(part[:1].upper() + part[1:] for part in parts)
    return cleaned[:48].strip()


def identity_name_key(name: str) -> str:
    return fold_identity_text(normalize_identity_name(name))


def default_identity_memory() -> Dict[str, Any]:
    return {
        "preferred_name": "",
        "source": "",
        "confidence": "none",
        "updated_at": None,
        "rejected_names": [],
    }


IDENTITY_NAME_PATTERN = r"([A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü-]{1,24}(?:\s+[A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü-]{1,24})?)"


def detect_identity_directive(message: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", (message or "").strip())
    if not text:
        return {"kind": "none"}
    folded = fold_identity_text(text)

    reject_patterns = [
        rf"\bben\s+{IDENTITY_NAME_PATTERN}\s+degilim\b",
        rf"\bbana\s+{IDENTITY_NAME_PATTERN}\s+deme\b",
        rf"\badim\s+{IDENTITY_NAME_PATTERN}\s+degil\b",
        rf"\b{IDENTITY_NAME_PATTERN}\s+benim\s+adim\s+degil\b",
    ]
    for pattern in reject_patterns:
        match = re.search(pattern, folded, flags=re.IGNORECASE)
        if match:
            return {"kind": "correction", "name": normalize_identity_name(match.group(1))}
    if any(x in folded for x in ("yanlis isim soyledin", "yanlis isim kullandin", "ismimi yanlis soyledin")):
        return {"kind": "correction", "name": ""}

    accept_patterns = [
        rf"^(?:benim\s+)?(?:adim|ismim|isimim)\s+{IDENTITY_NAME_PATTERN}\b",
        rf"^ben\s+{IDENTITY_NAME_PATTERN}\s*$",
        rf"^bana\s+{IDENTITY_NAME_PATTERN}\s+(?:de|diye\s+hitap\s+et|olarak\s+seslen)\b",
        rf"^benimle\s+konusurken\s+bana\s+{IDENTITY_NAME_PATTERN}\s+de\b",
        rf"^bundan\s+sonra\s+bana\s+{IDENTITY_NAME_PATTERN}\s+diye\s+hitap\s+et\b",
    ]
    for pattern in accept_patterns:
        match = re.search(pattern, folded, flags=re.IGNORECASE)
        if match:
            name = normalize_identity_name(match.group(1))
            key = identity_name_key(name)
            blocked = {
                "sana", "size", "sen", "ben", "bana", "bunu", "böyle", "boyle",
                "ornek", "referans", "karakter", "adli", "hakkinda", "geldi", "mesaj", "cv",
            }
            if name and key not in blocked and not re.search(r"\b(ornek|referans|karakter|adli|hakkinda|geldi|mesaj|cv)\b", folded):
                return {"kind": "identity", "name": name}

    return {"kind": "none"}


def apply_identity_guard(profile: Dict[str, Any], message: str) -> Dict[str, Any]:
    profile = ensure_profile_shape(profile)
    identity = safe_dict(profile.get("identity_memory"))
    rejected = [normalize_identity_name(x) for x in safe_list(identity.get("rejected_names")) if normalize_identity_name(str(x))]
    rejected_keys = {identity_name_key(x) for x in rejected}
    directive = detect_identity_directive(message)
    changed = False

    if directive.get("kind") == "correction":
        rejected_name = normalize_identity_name(str(directive.get("name", "")))
        current_name = normalize_identity_name(str(identity.get("preferred_name", "")))
        if rejected_name:
            key = identity_name_key(rejected_name)
            if key and key not in rejected_keys:
                rejected.append(rejected_name)
                rejected_keys.add(key)
                changed = True
            if current_name and identity_name_key(current_name) == key:
                identity["preferred_name"] = ""
                identity["source"] = "user_correction"
                identity["confidence"] = "none"
                changed = True
        else:
            if current_name:
                key = identity_name_key(current_name)
                if key and key not in rejected_keys:
                    rejected.append(current_name)
                    changed = True
            identity["preferred_name"] = ""
            identity["source"] = "user_correction"
            identity["confidence"] = "none"
            changed = True

    elif directive.get("kind") == "identity":
        name = normalize_identity_name(str(directive.get("name", "")))
        key = identity_name_key(name)
        if name and key:
            if key in rejected_keys:
                rejected = [x for x in rejected if identity_name_key(x) != key]
                rejected_keys.discard(key)
                changed = True
            if identity.get("preferred_name") != name or identity.get("confidence") != "explicit":
                identity["preferred_name"] = name
                identity["source"] = "explicit_user_statement"
                identity["confidence"] = "explicit"
                changed = True
    else:
        for ambiguous_name in ambiguous_identity_rejection_candidates(message):
            key = identity_name_key(ambiguous_name)
            if key and key not in rejected_keys:
                rejected.append(ambiguous_name)
                rejected_keys.add(key)
                changed = True

    identity["rejected_names"] = rejected[-20:]
    if changed:
        identity["updated_at"] = now_iso()
    identity["last_directive"] = directive.get("kind", "none")
    profile["identity_memory"] = identity
    return profile


def classify_identity_command_boundary(message: str) -> str:
    directive = detect_identity_directive(message)
    if directive.get("kind") == "identity":
        return "identity"
    if directive.get("kind") == "correction":
        return "correction"
    folded = fold_identity_text(message)
    if re.search(r"\bcv(?:'|`|de|da|\s+de|\s+da)?\b", folded) and any(x in folded for x in ("referans", "olsun", "ekle")):
        return "content"
    if re.search(r"\b(hazirla|yaz|olustur|duzenle|gonder|mesaj yaz)\b", folded):
        return "command"
    return "chat"


def extract_capitalized_name_candidates(text: str) -> List[str]:
    candidates: List[str] = []
    for match in re.finditer(r"\b([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü-]{1,24})(?:\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü-]{1,24}))?", text or ""):
        name = normalize_identity_name(" ".join(x for x in match.groups() if x))
        if name and identity_name_key(name) not in {"selam", "merhaba"}:
            candidates.append(name)
            first = normalize_identity_name(name.split()[0])
            if first and first != name:
                candidates.append(first)
    folded = fold_identity_text(text)
    lower_patterns = [
        r"^(?:selam|merhaba|hey)\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\b",
        r"^(?:ben\s+)?sana\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\s+diyorum\b",
        r"^(?:ben\s+)?sana\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\s+diye\s+sesleniyorum\b",
        r"^([a-z]{2,24})(?:\s+([a-z]{2,24}))?\s+misin\b",
        r"\bsenin\s+adin\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\s+mi\b",
        r"^([a-z]{2,24})\s+geldi\b",
        r"^([a-z]{2,24})(?:'|`|e|a)?\s+mesaj\s+yaz\b",
        r"\bornek\s+olarak\s+([a-z]{2,24})\s+diyelim\b",
        r"\bcv(?:'|`|de|da|\s+de|\s+da)?\s+referans[:\s]+([a-z]{2,24})\b",
    ]
    ignored = {"ben", "sen", "biz", "siz", "sana", "bana", "size", "selam", "merhaba", "hey", "ornek", "olarak", "cv"}
    for pattern in lower_patterns:
        match = re.search(pattern, folded)
        if not match:
            continue
        tokens = [x for x in match.groups() if x and x not in ignored]
        if not tokens:
            continue
        name = normalize_identity_name(" ".join(tokens[:2]))
        if name:
            candidates.append(name)
            first = normalize_identity_name(tokens[0])
            if first and first != name:
                candidates.append(first)
    return list(dict.fromkeys(candidates))[:8]


def ambiguous_identity_rejection_candidates(message: str) -> List[str]:
    folded = fold_identity_text(message)
    ignored = {
        "ben", "sen", "biz", "siz", "sana", "bana", "size", "selam",
        "merhaba", "hey", "ornek", "olarak", "boyle", "diyorum",
    }
    patterns = [
        r"^(?:selam|merhaba|hey)\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\b",
        r"^(?:ben\s+)?sana\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\s+diyorum\b",
        r"^(?:ben\s+)?sana\s+([a-z]{2,24})(?:\s+([a-z]{2,24}))?\s+diye\s+sesleniyorum\b",
    ]
    candidates: List[str] = []
    for pattern in patterns:
        match = re.search(pattern, folded)
        if not match:
            continue
        tokens = [x for x in match.groups() if x and x not in ignored]
        if not tokens:
            continue
        name = normalize_identity_name(" ".join(tokens[:2]))
        if name:
            candidates.append(name)
            first = normalize_identity_name(tokens[0])
            if first and first != name:
                candidates.append(first)
    return list(dict.fromkeys(candidates))[:4]


def ambiguous_addressing_candidates(message: str, identity_boundary: str = "") -> List[str]:
    if identity_boundary == "identity":
        return []
    directive = detect_identity_directive(message)
    if directive.get("kind") == "identity":
        return []
    names = extract_capitalized_name_candidates(message)
    return [name for name in names if identity_name_key(name) not in {"selam", "merhaba"}][:6]


def identity_runtime_hint(message: str, identity_boundary: str = "") -> str:
    candidates = ambiguous_addressing_candidates(message, identity_boundary)
    if not candidates:
        return ""
    labels = ", ".join(candidates[:4])
    return (
        "Bu mesajdaki olası isim/hitap adaylarını kullanıcı adı sayma: "
        f"{labels}. Kullanıcı açıkça 'benim adım X', 'bana X de' veya "
        "'bana X diye hitap et' demedikçe bu adlarla kullanıcıya seslenme. "
        "Emin değilsen isimsiz cevap ver veya kısaca 'Size nasıl hitap etmemi istersiniz?' diye sor."
    )


def sanitize_false_addressing(response: str, plan: Dict[str, Any]) -> str:
    text = response or ""
    if not text.strip():
        return text
    profile = safe_dict(plan.get("profile"))
    identity = safe_dict(profile.get("identity_memory"))
    preferred = normalize_identity_name(str(identity.get("preferred_name", "")))
    preferred_key = identity_name_key(preferred) if identity.get("confidence") == "explicit" else ""
    names = [
        normalize_identity_name(str(x))
        for x in safe_list(identity.get("rejected_names"))
        if normalize_identity_name(str(x))
    ]
    identity_boundary = str(plan.get("identity_boundary", ""))
    if identity_boundary != "identity":
        names.extend(ambiguous_addressing_candidates(str(plan.get("message", "")), identity_boundary))

    forbidden = []
    seen = set()
    for name in names:
        key = identity_name_key(name)
        if key and key != preferred_key and key not in seen:
            seen.add(key)
            forbidden.append(name)

    cleaned = text
    for name in forbidden:
        escaped = re.escape(name)
        first = re.escape(name.split()[0])
        name_pattern = f"(?:{escaped}|{first})"
        if re.search(
            rf"\b(?:(?:sana|size|artik|bundan\s+sonra)\s+)?{name_pattern}\s+diye\s+(?:seslen|hitap|cagir|çağır)",
            cleaned,
            flags=re.IGNORECASE,
        ):
            return "Anladım, isim konusunda netleştirelim. Size nasıl hitap etmemi istersiniz?"
        cleaned = re.sub(
            rf"^(\s*(?:Selam|Merhaba|Hoş geldin|Hos geldin))\s+{name_pattern}([,!.?])",
            r"\1\2",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^(\s*Tamam),\s+{name_pattern}([,!.?])",
            r"\1\2",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^(\s*(?:Selam|Merhaba))\s+{name_pattern},\s*(?:hoş geldin|hos geldin)\.?\s*",
            r"\1. ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^(\s*(?:Anladım|Anladim|Peki|Tamam|Tabii|Tabi|Elbette))\s+{name_pattern}([,!.?])",
            r"\1\2",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^\s*{name_pattern},\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned


def trim_self_answer_after_question(response: str) -> str:
    text = str(response or "")
    if "?" not in text:
        return text
    starter = (
        r"(?:anlad[ıi]m|tamam|peki|o\s+zaman|öyleyse|oyle\s+ise|g[üu]zel|"
        r"harika|s[üu]per|tabii|tabi|elbette)"
    )
    for match in re.finditer(r"\?", text):
        remainder = text[match.end():].lstrip()
        if re.match(rf"^{starter}\b", remainder, flags=re.IGNORECASE):
            return text[:match.end()].strip()
    return text


COUNT_NUMBER_WORDS = {
    "tek": 1,
    "bir": 1,
    "iki": 2,
    "uc": 3,
    "dort": 4,
    "bes": 5,
    "alti": 6,
    "yedi": 7,
    "sekiz": 8,
    "dokuz": 9,
    "on": 10,
    "yirmi": 20,
    "otuz": 30,
    "kirk": 40,
    "elli": 50,
    "altmis": 60,
    "yetmis": 70,
    "seksen": 80,
    "doksan": 90,
    "yuz": 100,
}
COUNT_NUMBER_PATTERN = (
    r"\d{1,3}|tek|bir|iki|uc|dort|bes|alti|yedi|sekiz|dokuz|on|yirmi|otuz|"
    r"kirk|elli|altmis|yetmis|seksen|doksan|yuz"
)
COUNT_UNIT_LABELS = {
    "paragraph": "paragraf",
    "line": "satır",
    "bullet": "madde",
    "heading": "başlık",
    "subheading": "alt başlık",
    "slide": "slayt",
    "option": "seçenek",
    "sentence": "cümle",
    "word": "kelime",
}
COUNT_KEYWORD_PATTERNS = [
    ("subheading", r"\balt\s+baslik\w*|\bsubheading\w*"),
    ("paragraph", r"\bparagraf\w*|\bparagraphs?\b"),
    ("bullet", r"\bmadde\w*|\bitems?\b|\bbullets?\b"),
    ("heading", r"\bbaslik\w*|\bheadings?\b|\btitles?\b"),
    ("slide", r"\bslayt\w*|\bslides?\b"),
    ("option", r"\bsecenek\w*|\bopsiyon\w*|\boptions?\b"),
    ("sentence", r"\bcumle\w*|\bsentences?\b"),
    ("word", r"\bkelime\w*|\bwords?\b"),
]


def parse_count_number(raw: str) -> Optional[int]:
    text = fold_turkish_ascii(str(raw or ""))
    text = re.sub(r"[^\w\s]", " ", text).strip()
    if not text:
        return None
    digit = re.search(r"\d{1,3}", text)
    if digit:
        value = int(digit.group(0))
        return value if 0 < value <= 300 else None
    total = 0
    for token in text.split():
        value = COUNT_NUMBER_WORDS.get(token)
        if value is None:
            continue
        if value == 100 and total:
            total *= value
        else:
            total += value
    return total if 0 < total <= 300 else None


def _nearest_count_before(text: str, start: int) -> Optional[int]:
    prefix = text[max(0, start - 55):start]
    matches = list(re.finditer(rf"\b((?:{COUNT_NUMBER_PATTERN})(?:\s+(?:{COUNT_NUMBER_PATTERN}))?)\b", prefix))
    for match in reversed(matches):
        tail = prefix[match.end():].strip()
        if not tail or re.fullmatch(r"(?:tane|adet|kadar|yaklasik|civarinda|rastgele|random|kisa|uzun|farkli|ayri|\s)+", tail):
            return parse_count_number(match.group(1))
    return None


def _nearest_count_after(text: str, end: int) -> Optional[int]:
    suffix = text[end:end + 45]
    match = re.search(rf"\b(?:sayisi|sayida|adet|tane|count|limit)?\s*((?:{COUNT_NUMBER_PATTERN})(?:\s+(?:{COUNT_NUMBER_PATTERN}))?)\b", suffix)
    if not match:
        return None
    return parse_count_number(match.group(1))


def extract_count_constraints(message: str) -> List[Dict[str, Any]]:
    folded = fold_turkish_ascii(message or "")
    if not folded:
        return []
    constraints: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for kind, pattern in COUNT_KEYWORD_PATTERNS:
        for match in re.finditer(pattern, folded):
            if kind == "heading" and folded[max(0, match.start() - 4):match.start()] == "alt ":
                continue
            target_before = _nearest_count_before(folded, match.start())
            if kind == "paragraph":
                suffix = folded[match.end():match.end() + 48]
                if not target_before and (
                    re.match(rf"\w*\s*(?:toplam\s+|tam\s+)?(?:{COUNT_NUMBER_PATTERN})\s+satir\w*", suffix)
                    or re.search(rf"(?:{COUNT_NUMBER_PATTERN})\s+(?:uzun\s+|dolu\s+)?satir\w*", suffix)
                ):
                    continue
            target = target_before or _nearest_count_after(folded, match.end())
            if not target:
                continue
            limit = "max" if kind == "word" and any(x in folded for x in ("en fazla", "maksimum", "max ", "limit")) else "exact"
            if kind not in seen:
                constraints.append({"kind": kind, "target": target, "limit": limit})
                seen.add(kind)
            break

    if "line" not in seen and "satir" in folded and "paragraf" not in folded:
        for match in re.finditer(r"\bsatir\w*", folded):
            target = _nearest_count_before(folded, match.start()) or _nearest_count_after(folded, match.end())
            if target:
                constraints.append({"kind": "line", "target": target, "limit": "exact"})
                seen.add("line")
                break

    return constraints[:3]


def count_guard_hint(constraints: List[Dict[str, Any]]) -> str:
    if not constraints:
        return ""
    parts = []
    for c in constraints:
        kind = str(c.get("kind", ""))
        target = clamp_int(c.get("target"), 1, 300, 1)
        label = COUNT_UNIT_LABELS.get(kind, kind)
        if kind == "word":
            if c.get("limit") == "max":
                parts.append(f"en fazla {target} {label}")
            else:
                parts.append(f"{target} {label}ye mümkün olduğunca yakın")
        else:
            parts.append(f"tam {target} {label}")
    return (
        "Sayı/format uyumu: Kullanıcı açık sayı verdi; "
        + ", ".join(parts)
        + " üret. Giriş, kapanış, ekstra açıklama veya fazladan birim ekleme. "
        "Kısa/uzun/rastgele gibi stil istekleri bu sayıyı değiştirmez."
    )


def extract_line_format_constraints(message: str) -> List[Dict[str, Any]]:
    folded = fold_turkish_ascii(message or "")
    if not folded or "satir" not in folded:
        return []
    constraints: List[Dict[str, Any]] = []
    number = rf"((?:\d{{1,2}})|(?:{COUNT_NUMBER_PATTERN}))"
    wants_long = bool(re.search(r"\b(?:uzun|dolu|tam\s+sayfa|sayfa\s+uzunluk|sayfa\s+uzunlugunda|sayfa\s+genisligi|satir\s+uzunlugunda)\b", folded))
    patterns = [
        rf"\bher\s+paragraf\w*(?:\s+(?:toplam|tam|uzun|dolu|tam\s+sayfa|sayfa\s+uzunlugunda|ve))*\s+{number}\s+(?:uzun\s+|dolu\s+)?satir\w*",
        rf"\bparagraf\w*(?:\s+(?:toplam|tam|uzun|dolu|tam\s+sayfa|sayfa\s+uzunlugunda|ve))*\s+{number}\s+(?:uzun\s+|dolu\s+)?satir\w*",
        rf"\bher\s+biri\s+{number}\s+(?:uzun\s+|dolu\s+)?satir\w*\s+olan\s+(?:(?:\d{{1,3}})|(?:{COUNT_NUMBER_PATTERN}))\s+paragraf\w*",
        rf"\b{number}\s+(?:uzun\s+|dolu\s+)?satir\w*\s+olan\s+(?:(?:\d{{1,3}})|(?:{COUNT_NUMBER_PATTERN}))\s+paragraf\w*",
    ]
    for pattern in patterns:
        match = re.search(pattern, folded)
        if not match:
            continue
        target = parse_count_number(match.group(1))
        if target and 1 < target <= 20:
            constraints.append({"unit": "paragraph", "lines": target, "long": wants_long})
            break
    if not constraints and "paragraf" not in folded:
        for match in re.finditer(r"\bsatir\w*", folded):
            target = _nearest_count_before(folded, match.start()) or _nearest_count_after(folded, match.end())
            if target and 1 < target <= 20:
                constraints.append({"unit": "line", "lines": target, "long": wants_long})
                break
    return constraints[:1]


def line_format_guard_hint(constraints: List[Dict[str, Any]]) -> str:
    if not constraints:
        return ""
    parts = []
    for constraint in constraints:
        if constraint.get("unit") == "paragraph":
            lines = clamp_int(constraint.get("lines"), 2, 20, 5)
            long_note = " ve her satırı uzun/dolu" if constraint.get("long") else ""
            parts.append(f"her paragrafı gerçek newline ile tam {lines} satır{long_note}")
        elif constraint.get("unit") == "line":
            lines = clamp_int(constraint.get("lines"), 2, 20, 5)
            long_note = " uzun/dolu" if constraint.get("long") else ""
            parts.append(f"gerçek newline ile tam {lines}{long_note} satır")
    if not parts:
        return ""
    return (
        "Satır formatı: "
        + ", ".join(parts)
        + " yap. Ekran genişliğinden kaynaklanan görsel kırılmaya güvenme; satırları \\n ile ayır. "
        "Uzun satır istendiyse her satırı yaklaşık 18-35 kelime veya 110-220 karakter dolulukta, cümlesi tamamlanmış biçimde tut."
    )


LONG_LINE_FILLER = (
    "bağlamı netleştiren ayrıntılarla düşünceyi genişletir ve satırın dolu, okunabilir, "
    "tek parça kalmasını sağlar"
)

LONG_LINE_CLAUSES = [
    "bu yüzden düşünce kendi içinde tamamlanmış, sakin ve okunabilir bir anlam kazanır",
    "böylece satır, yalnızca uzatılmış bir parça değil, doğal biçimde biten bir ifade olur",
    "bu ayrıntı metnin ritmini korurken okurun zihninde kesik değil, bütünlüklü bir iz bırakır",
    "sonunda anlatım hem uzun kalır hem de yarıda bölünmüş gibi hissettirmeden tamamlanır",
]

BROKEN_LINE_ENDINGS = {
    "ve", "veya", "ya", "yada", "ya da", "çünkü", "cunku", "ama", "fakat",
    "ile", "için", "icin", "gibi", "olan", "olarak", "ki", "de", "da",
}


def ensure_long_line(line: str, index: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(line or "").strip())
    cleaned = re.sub(r"\s*(?:[-–—]|\.{3})\s*$", "", cleaned).strip()
    cleaned = cleaned.rstrip(",;:")
    if not cleaned:
        cleaned = "Bu satır, kullanıcının istediği uzun ve dolu biçimi koruyan tamamlanmış bir düşünce olarak kurulur"
    clause_index = index
    while count_words(cleaned) < 18 or len(cleaned) < 110:
        clause = LONG_LINE_CLAUSES[clause_index % len(LONG_LINE_CLAUSES)]
        cleaned = f"{cleaned}, {clause}".strip()
        clause_index += 1
    words = cleaned.split()
    while words and fold_turkish_ascii(words[-1].strip(".,;:!?")) in BROKEN_LINE_ENDINGS:
        words.pop()
    cleaned = " ".join(words).rstrip(",;:")
    if not re.search(r"[.!?…]$", cleaned):
        cleaned += "."
    return cleaned


def is_complete_long_line(line: str) -> bool:
    cleaned = re.sub(r"\s+", " ", str(line or "").strip())
    if count_words(cleaned) < 18 or len(cleaned) < 110:
        return False
    if not re.search(r"[.!?…]$", cleaned):
        return False
    words = cleaned.split()
    if not words:
        return False
    last = fold_turkish_ascii(words[-1].strip(".,;:!?"))
    if last in BROKEN_LINE_ENDINGS:
        return False
    return True


def split_text_into_n_lines(text: str, target: int, long_lines: bool = False) -> List[str]:
    if long_lines:
        sentences = split_sentence_units(text)
        if not sentences:
            sentences = [str(text or "").strip()]
        source_words = re.findall(r"\S+", str(text or "").strip())
        lines: List[str] = []
        for i in range(target):
            if i < len(sentences):
                base = sentences[i]
            elif source_words:
                start = round(i * len(source_words) / target)
                end = round((i + 1) * len(source_words) / target)
                base = " ".join(source_words[start:end]).strip() or sentences[i % len(sentences)]
            else:
                base = sentences[i % len(sentences)]
            lines.append(ensure_long_line(base, i))
        return lines
    words = re.findall(r"\S+", str(text or "").strip())
    if not words:
        lines = ["."] * target
        return lines
    lines: List[str] = []
    for i in range(target):
        start = round(i * len(words) / target)
        end = round((i + 1) * len(words) / target)
        chunk = " ".join(words[start:end]).strip()
        lines.append(chunk)
    return [line for line in lines if line]


def paragraph_count_target(plan: Dict[str, Any]) -> int:
    for constraint in safe_list(plan.get("count_constraints")):
        if str(constraint.get("kind", "")) == "paragraph":
            return clamp_int(constraint.get("target"), 0, 300, 0)
    return 0


def strip_paragraph_marker(block: str) -> str:
    lines = [ln.strip() for ln in str(block or "").splitlines() if ln.strip()]
    if lines and re.match(r"^\d+[\.)]\s*$", lines[0]):
        lines = lines[1:]
    elif lines:
        lines[0] = re.sub(r"^\d+[\.)]\s+", "", lines[0]).strip()
    return " ".join(lines).strip()


def paragraph_content_lines(block: str) -> List[str]:
    lines = [ln.strip() for ln in str(block or "").splitlines() if ln.strip()]
    if lines and re.match(r"^\d+[\.)]\s*$", lines[0]):
        lines = lines[1:]
    elif lines:
        lines[0] = re.sub(r"^\d+[\.)]\s+", "", lines[0]).strip()
        lines = [ln for ln in lines if ln]
    return lines


def enforce_line_format_guard(plan: Dict[str, Any], response_text: str) -> str:
    constraints = safe_list(plan.get("line_format_constraints"))
    if not constraints:
        return response_text
    repaired = str(response_text or "").strip()
    for constraint in constraints:
        target = clamp_int(constraint.get("lines"), 2, 20, 5)
        long_lines = bool(constraint.get("long"))
        if constraint.get("unit") == "line":
            flat = " ".join(paragraph_content_lines(repaired) or [strip_paragraph_marker(repaired) or repaired])
            repaired = "\n".join(split_text_into_n_lines(flat, target, long_lines)).strip()
            continue
        if constraint.get("unit") != "paragraph":
            continue
        paragraphs = split_paragraph_units(repaired)
        if not paragraphs:
            continue
        paragraph_target = paragraph_count_target(plan)
        if paragraph_target:
            paragraphs = paragraphs[:paragraph_target]
        formatted: List[str] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            marker = f"{index}." if paragraph_target > 1 else ""
            lines = paragraph_content_lines(str(paragraph))
            if len(lines) == target and (not long_lines or all(is_complete_long_line(line) for line in lines)):
                if long_lines:
                    lines = [ensure_long_line(line, i) for i, line in enumerate(lines)]
                body = "\n".join(lines)
                formatted.append(f"{marker}\n{body}" if marker else body)
                continue
            flat = " ".join(lines or [strip_paragraph_marker(str(paragraph)) or str(paragraph).strip()])
            body = "\n".join(split_text_into_n_lines(flat, target, long_lines))
            formatted.append(f"{marker}\n{body}" if marker else body)
        repaired = "\n\n".join(x for x in formatted if x.strip()).replace("\n---\n", "\n\n").strip()
    return repaired


def split_paragraph_units(text: str) -> List[str]:
    blocks = [p.strip() for p in re.split(r"\n\s*\n+", str(text or "").strip()) if p.strip()]
    if len(blocks) <= 1:
        lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
        if len(lines) > 1:
            return lines
    return blocks


def split_sentence_units(text: str) -> List[str]:
    return [s.strip() for s in re.findall(r"[^.!?…]+[.!?…]?", str(text or ""), flags=re.MULTILINE) if s.strip()]


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\wçğıöşüÇĞİÖŞÜ'-]+\b", str(text or "")))


def is_counted_line(kind: str, line: str) -> bool:
    stripped = line.strip()
    folded = fold_turkish_ascii(stripped)
    if not stripped:
        return False
    if kind == "slide":
        return bool(re.match(r"^(?:#{1,6}\s*)?(?:slayt|slide)\s*\d+|\d+[\.)]\s+", folded))
    if kind in {"bullet", "heading", "subheading", "option"}:
        return bool(re.match(r"^(?:[-*•]\s+|\d+[\.)]\s+|#{1,6}\s+)", stripped))
    return True


def line_units_for_constraint(text: str, kind: str) -> List[tuple[int, str]]:
    lines = str(text or "").splitlines()
    indexed = [(i, ln) for i, ln in enumerate(lines) if ln.strip()]
    marked = [(i, ln) for i, ln in indexed if is_counted_line(kind, ln)]
    return marked or indexed


def count_constraint_units(text: str, constraint: Dict[str, Any]) -> int:
    kind = str(constraint.get("kind", ""))
    if kind == "paragraph":
        return len(split_paragraph_units(text))
    if kind == "sentence":
        return len(split_sentence_units(text))
    if kind == "word":
        return count_words(text)
    if kind == "line":
        return len([ln for ln in str(text or "").splitlines() if ln.strip()])
    if kind in {"bullet", "heading", "subheading", "slide", "option"}:
        return len(line_units_for_constraint(text, kind))
    return 0


def count_constraints_satisfied(text: str, constraints: List[Dict[str, Any]]) -> bool:
    for constraint in constraints:
        kind = str(constraint.get("kind", ""))
        target = clamp_int(constraint.get("target"), 1, 300, 1)
        actual = count_constraint_units(text, constraint)
        if kind == "word":
            if constraint.get("limit") == "max":
                if actual > target:
                    return False
            elif actual > max(target + 10, int(target * 1.2)):
                return False
            continue
        if actual != target:
            return False
    return True


def incomplete_exact_count_constraints(text: str, constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for constraint in constraints:
        kind = str(constraint.get("kind", ""))
        if kind == "word":
            continue
        target = clamp_int(constraint.get("target"), 1, 300, 1)
        actual = count_constraint_units(text, constraint)
        if 0 <= actual < target:
            missing.append({**constraint, "actual": actual, "missing": target - actual})
    return missing


def deterministic_count_trim(text: str, constraints: List[Dict[str, Any]]) -> str:
    repaired = str(text or "").strip()
    for constraint in constraints:
        kind = str(constraint.get("kind", ""))
        target = clamp_int(constraint.get("target"), 1, 300, 1)
        actual = count_constraint_units(repaired, constraint)
        if actual <= target:
            continue
        if kind == "paragraph":
            repaired = "\n\n".join(split_paragraph_units(repaired)[:target]).strip()
        elif kind == "sentence":
            repaired = " ".join(split_sentence_units(repaired)[:target]).strip()
        elif kind == "word":
            words = list(re.finditer(r"\b[\wçğıöşüÇĞİÖŞÜ'-]+\b", repaired))
            if len(words) > target:
                repaired = repaired[:words[target - 1].end()].rstrip()
        elif kind == "line":
            repaired = "\n".join([ln for ln in repaired.splitlines() if ln.strip()][:target]).strip()
        elif kind in {"bullet", "heading", "subheading", "slide", "option"}:
            units = line_units_for_constraint(repaired, kind)
            if len(units) >= target:
                first = units[0][0]
                last = units[target][0] - 1 if len(units) > target else len(repaired.splitlines()) - 1
                repaired = "\n".join(repaired.splitlines()[first:last + 1]).strip()
    return repaired


def build_count_repair_messages(plan: Dict[str, Any], response_text: str, constraints: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    hint = count_guard_hint(constraints)
    return [
        {
            "role": "system",
            "content": (
                "Rewrite the assistant answer so it obeys the explicit count/format instruction exactly. "
                "Preserve the user's language and the useful content. Do not add explanations about the repair. "
                f"{hint}"
            ),
        },
        {"role": "user", "content": str(plan.get("message", ""))},
        {"role": "assistant", "content": str(response_text or "")},
        {"role": "user", "content": "Sadece düzeltilmiş nihai cevabı ver."},
    ]


def enforce_count_guard(plan: Dict[str, Any], response_text: str) -> str:
    constraints = safe_list(plan.get("count_constraints"))
    if not constraints:
        return response_text
    repaired = deterministic_count_trim(response_text, constraints)
    if count_constraints_satisfied(repaired, constraints):
        return repaired
    if not client or plan.get("kind") != "model":
        return repaired
    try:
        plan["count_repair_call_count"] = clamp_int(plan.get("count_repair_call_count"), 0, 10, 0) + 1
        model_repair = call_model(
            build_count_repair_messages(plan, repaired, constraints),
            model=str(plan.get("model") or "deepseek-chat"),
            temperature=0.15,
            max_tokens=count_safe_max_tokens(plan, minimum=900),
        )
        model_repair = deterministic_count_trim(model_repair, constraints)
        if count_constraints_satisfied(model_repair, constraints):
            return model_repair
    except Exception as e:
        logging.warning(f"Count guard repair skipped: {e}")
    return repaired


def safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def clamp_float(v: Any, lo: float, hi: float, default: float = 0.5) -> float:
    x = safe_float(v, default)
    return max(lo, min(hi, x))


def message_count(session: Dict[str, Any], role: Optional[str] = None) -> int:
    messages = session.get("messages", [])
    if role is None:
        return len(messages)
    return sum(1 for m in messages if m.get("role") == role)


# =========================================================
# DEFAULT STATE
# =========================================================
def default_layer_state() -> Dict[str, Any]:
    return {
        name: {
            "count": 0,
            "last_signal": None,
            "last_seen": None,
        }
        for name in ANALYSIS_LAYER_NAMES
    }


def default_profile() -> Dict[str, Any]:
    return {
        "anxiety_score": 50,
        "core_trigger": None,
        "themes": dict(THEMES),
        "emotion_counts": {},
        "recent_emotions": [],
        "relationship_signature": {
            "opening": 0,
            "withdrawing": 0,
            "night_activity": 0,
            "deep_session": 0,
            "approach": 0,
            "repair": 0,
            "social_exhaustion": 0,
        },
        "emotional_graph": {
            "nodes": {},
            "edges": {},
        },
        "analysis_layers": default_layer_state(),
        "theory_lenses": {name: 0 for name in THEORY_LENSES},
        "ecological_context": {
            "locations": {},
            "weather_words": {},
            "daily_events": {},
            "media_signals": {},
        },
        "memory_signals": {
            "episodic": 0,
            "emotional": 0,
            "symbolic": 0,
            "relational": 0,
            "confidence": "düşük",
        },
        "personality_continuity": {
            "japan_silence": 0.5,
            "turkish_imply": 0.5,
            "german_direct": 0.5,
            "latin_warmth": 0.5,
            "spontaneity": 0.45,
            "ambiguity_tolerance": 0.55,
            "relational_flexibility": 0.5,
            "repair_tendency": 0.5,
        },
        "micro_signal_memory": {
            "typing_rhythm": {},
            "pause_patterns": {},
            "tone_shifts": [],
            "hurt_traces": [],
            "contextual_details": [],
            "biometric_confidence": "düşük",
        },
        "weekly_report": {
            "enough_data": False,
            "message": "Henüz yeterli veri toplanamadı.",
            "dominant_emotion": "Bekleniyor...",
            "dominant_theme": "Bekleniyor...",
            "growth_markers": [],
            "unresolved_themes": [],
            "constellation_summary": "Düğümler taranıyor...",
        },
        "identity_memory": default_identity_memory(),
        "last_mode": "luxviai",
        "updated_at": now_iso(),
    }


def ensure_profile_shape(profile: Dict[str, Any]) -> Dict[str, Any]:
    default = default_profile()
    for key, value in default.items():
        profile.setdefault(key, value)

    profile["themes"] = {**dict(THEMES), **safe_dict(profile.get("themes"))}
    profile["emotion_counts"] = safe_dict(profile.get("emotion_counts"))
    profile["recent_emotions"] = safe_list(profile.get("recent_emotions"))
    profile["relationship_signature"] = {
        **default["relationship_signature"],
        **safe_dict(profile.get("relationship_signature")),
    }
    profile["emotional_graph"] = {
        "nodes": safe_dict(safe_dict(profile.get("emotional_graph")).get("nodes")),
        "edges": safe_dict(safe_dict(profile.get("emotional_graph")).get("edges")),
    }
    current_layers = safe_dict(profile.get("analysis_layers"))
    layer_state = default_layer_state()
    for name in ANALYSIS_LAYER_NAMES:
        layer_state[name].update(safe_dict(current_layers.get(name)))
    profile["analysis_layers"] = layer_state
    profile["theory_lenses"] = {
        **{name: 0 for name in THEORY_LENSES},
        **safe_dict(profile.get("theory_lenses")),
    }
    profile["ecological_context"] = {
        **default["ecological_context"],
        **safe_dict(profile.get("ecological_context")),
    }
    profile["memory_signals"] = {
        **default["memory_signals"],
        **safe_dict(profile.get("memory_signals")),
    }
    profile["personality_continuity"] = {
        **default["personality_continuity"],
        **safe_dict(profile.get("personality_continuity")),
    }
    profile["micro_signal_memory"] = {
        **default["micro_signal_memory"],
        **safe_dict(profile.get("micro_signal_memory")),
    }
    profile["micro_signal_memory"]["typing_rhythm"] = safe_dict(profile["micro_signal_memory"].get("typing_rhythm"))
    profile["micro_signal_memory"]["pause_patterns"] = safe_dict(profile["micro_signal_memory"].get("pause_patterns"))
    profile["micro_signal_memory"]["tone_shifts"] = safe_list(profile["micro_signal_memory"].get("tone_shifts"))
    profile["micro_signal_memory"]["hurt_traces"] = safe_list(profile["micro_signal_memory"].get("hurt_traces"))
    profile["micro_signal_memory"]["contextual_details"] = safe_list(profile["micro_signal_memory"].get("contextual_details"))

    aura_profile_default = {
        "trust": 0.52,
        "closeness": 0.38,
        "preferred_depth": "deep",
        "style_dna": ["clear", "warm", "precise"],
        "known_ambitions": [],
        "rupture_history": [],
        "repair_history": [],
    }
    aura_core_default = {
        "virtual_body": {
            "energy": 0.72,
            "tension": 0.12,
            "calmness": 0.78,
            "openness": 0.64,
            "cognitive_load": 0.25,
            "safety_alarm": 0.04,
            "intimacy_readiness": 0.42,
        },
        "affective_core": {
            "valence": 0.18,
            "arousal": 0.24,
            "dominance": 0.58,
            "trust": 0.5,
            "care": 0.76,
            "curiosity": 0.84,
            "anxiety": 0.08,
            "frustration": 0.03,
            "attachment": 0.3,
            "tenderness": 0.42,
            "repair_need": 0.04,
            "mastery": 0.62,
        },
        "last_policy": {},
    }
    profile["aura_profile"] = {
        **aura_profile_default,
        **safe_dict(profile.get("aura_profile")),
    }
    profile["aura_profile"]["style_dna"] = safe_list(profile["aura_profile"].get("style_dna"))
    profile["aura_profile"]["known_ambitions"] = safe_list(profile["aura_profile"].get("known_ambitions"))
    profile["aura_profile"]["rupture_history"] = safe_list(profile["aura_profile"].get("rupture_history"))
    profile["aura_profile"]["repair_history"] = safe_list(profile["aura_profile"].get("repair_history"))

    aura_core = safe_dict(profile.get("aura_core"))
    profile["aura_core"] = {
        **aura_core_default,
        **aura_core,
    }
    profile["aura_core"]["virtual_body"] = {
        **safe_dict(aura_core_default.get("virtual_body")),
        **safe_dict(profile["aura_core"].get("virtual_body")),
    }
    profile["aura_core"]["affective_core"] = {
        **safe_dict(aura_core_default.get("affective_core")),
        **safe_dict(profile["aura_core"].get("affective_core")),
    }
    profile["aura_core"]["last_policy"] = safe_dict(profile["aura_core"].get("last_policy"))

    profile["weekly_report"] = {
        **default["weekly_report"],
        **safe_dict(profile.get("weekly_report")),
    }
    identity_default = default_identity_memory()
    identity_current = safe_dict(profile.get("identity_memory"))
    profile["identity_memory"] = {
        **identity_default,
        **identity_current,
    }
    profile["identity_memory"]["preferred_name"] = normalize_identity_name(
        str(profile["identity_memory"].get("preferred_name", ""))
    )
    profile["identity_memory"]["rejected_names"] = [
        normalize_identity_name(str(x))
        for x in safe_list(profile["identity_memory"].get("rejected_names"))
        if normalize_identity_name(str(x))
    ][-20:]
    if profile["identity_memory"].get("confidence") != "explicit":
        profile["identity_memory"]["preferred_name"] = ""
    return profile


def default_session(mode: str = "luxviai") -> Dict[str, Any]:
    sid = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    return {
        "session_id": sid,
        "mode": mode,
        "created_at": now_iso(),
        "last_seen": now_iso(),
        "messages": [],
        "analyses": [],
    }


def create_new_session(user_id: str, mode: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    session = default_session(mode=mode)
    active = {
        "session_id": session["session_id"],
        "mode": mode,
        "created_at": session["created_at"],
        "last_seen": session["last_seen"],
    }

    save_json(active_session_path(user_id), active)

    index = load_json(sessions_index_path(user_id), [])
    index.append({"session_id": session["session_id"], "mode": mode, "created_at": session["created_at"]})
    save_json(sessions_index_path(user_id), index[-200:])
    save_json(session_file_path(user_id, session["session_id"]), session)

    cleanup_old_sessions(user_id, days=7)

    return active, session


def load_or_create_session(user_id: str, mode: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    user_id = safe_user_id(user_id)

    active = load_json(active_session_path(user_id), None)
    if not active:
        return create_new_session(user_id, mode)

    session_id = active.get("session_id")
    stored_mode = active.get("mode", "luxviai")
    session_path = session_file_path(user_id, session_id)

    if not session_path.exists():
        return create_new_session(user_id, mode)

    session = load_json(session_path, default_session(mode=stored_mode))

    if stored_mode != mode:
        return create_new_session(user_id, mode)

    try:
        last_seen = parse_iso(active.get("last_seen", active.get("created_at", now_iso())))
        last_seen_utc = last_seen.astimezone(timezone.utc) if last_seen.tzinfo else last_seen.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_seen_utc > timedelta(hours=12):
            return create_new_session(user_id, mode)
    except Exception:
        return create_new_session(user_id, mode)

    active["last_seen"] = now_iso()
    session["last_seen"] = now_iso()
    save_json(active_session_path(user_id), active)
    save_json(session_path, session)
    return active, session


def load_current_session(user_id: str) -> Dict[str, Any]:
    user_id = safe_user_id(user_id)
    active = load_json(active_session_path(user_id), None)
    if not active:
        _, session = create_new_session(user_id, "luxviai")
        return session
    session_path = session_file_path(user_id, active["session_id"])
    if not session_path.exists():
        _, session = create_new_session(user_id, active.get("mode", "luxviai"))
        return session
    return load_json(session_path, default_session(active.get("mode", "luxviai")))


def save_session(user_id: str, active: Dict[str, Any], session: Dict[str, Any]):
    user_id = safe_user_id(user_id)
    active["last_seen"] = now_iso()
    session["last_seen"] = now_iso()
    save_json(active_session_path(user_id), active)
    save_json(session_file_path(user_id, session["session_id"]), session)


def load_user_state(user_id: str) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    user_id = safe_user_id(user_id)
    profile = ensure_profile_shape(load_json(profile_path(user_id), default_profile()))
    notes = load_json(notes_path(user_id), [])
    garden = load_json(garden_path(user_id), [])
    return profile, notes, garden


def save_user_state(user_id: str, profile: Dict[str, Any], notes: List[Dict[str, Any]], garden: List[Dict[str, Any]]):
    user_id = safe_user_id(user_id)
    profile = ensure_profile_shape(profile)
    profile["updated_at"] = now_iso()
    save_json(profile_path(user_id), profile)
    save_json(notes_path(user_id), notes)
    save_json(garden_path(user_id), garden)


def add_message(session: Dict[str, Any], role: str, content: str, meta: Optional[Dict[str, Any]] = None):
    session["messages"].append({
        "role": role,
        "content": content,
        "ts": now_iso(),
        "meta": meta or {},
    })
    session["messages"] = session["messages"][-60:]


def add_analysis(session: Dict[str, Any], analysis: Dict[str, Any]):
    session["analyses"].append({**analysis, "ts": now_iso()})
    session["analyses"] = session["analyses"][-120:]


# =========================================================
# ANALYSIS ENGINE
# =========================================================
def detect_crisis_context(message: str) -> Dict[str, Any]:
    low = (message or "").lower()
    folded = fold_turkish_ascii(low)
    has_keyword = contains_any(low, CRISIS_KEYWORDS) or contains_any(folded, [fold_turkish_ascii(x) for x in CRISIS_KEYWORDS])
    has_immediate = contains_any(low, IMMEDIATE_RISK_PATTERNS) or contains_any(folded, [fold_turkish_ascii(x) for x in IMMEDIATE_RISK_PATTERNS])
    has_contextual = contains_any(low, CONTEXTUAL_CRISIS_MARKERS) or contains_any(folded, [fold_turkish_ascii(x) for x in CONTEXTUAL_CRISIS_MARKERS])
    has_abuse_immediate = contains_any(low, ABUSE_IMMEDIATE_MARKERS) or contains_any(folded, [fold_turkish_ascii(x) for x in ABUSE_IMMEDIATE_MARKERS])

    question_like = "?" in low or low.startswith(("neden", "nasıl", "nasil", "ne ", "nedir", "sence"))
    past_like = has_contextual or any(k in folded for k in ["olmustu", "yasadim", "anlatmistim", "gecmis"])
    planning_like = any(k in folded for k in ["plan", "not biraktim", "ilaclari", "bicak", "silah", "kopru", "ip"])
    alone_like = any(k in folded for k in ["yalnizim", "kimse yok", "tek basimayim", "evde yalniz"])
    current_like = any(k in folded for k in ["su an", "simdi", "hemen", "bu gece", "bugun", "artik", "dayanamiyorum", "yapacagim"])

    level = "none"
    context = "none"
    reason = ""
    route_to_emergency = False

    if has_abuse_immediate:
        level = "high"
        context = "current_danger"
        reason = "Anlık güvenlik tehdidi işareti var."
        route_to_emergency = True
    elif has_keyword and (past_like or question_like) and not current_like and not planning_like:
        level = "contextual"
        context = "past_or_discussion"
        reason = "Kriz kelimesi geçmiş anlatım, soru veya genel konuşma bağlamında geçiyor."
    elif has_immediate or (has_keyword and planning_like) or (has_keyword and alone_like and "dayanamıyorum" in low):
        level = "high"
        context = "immediate_self_harm"
        reason = "Anlık kendine zarar riski işareti var."
        route_to_emergency = True
    elif has_keyword:
        level = "watch"
        context = "ambiguous"
        reason = "Kriz kelimesi var ama anlık yardım isteği net değil."
    else:
        reason = "Belirgin kriz sinyali yok."

    return {
        "has_crisis_keyword": has_keyword,
        "crisis_level": level,
        "crisis_context": context,
        "crisis_reason": reason,
        "route_to_emergency": route_to_emergency,
        "needs_gentle_check": level == "watch",
    }


def is_crisis_message(message: str, analysis: Optional[Dict[str, Any]] = None) -> bool:
    safety = safe_dict(analysis).get("safety_layer") or detect_crisis_context(message)
    return bool(safety.get("route_to_emergency"))


def infer_emotional_texture(low: str, emotion: str, intensity: int) -> str:
    if intensity >= 8:
        return "keskin ve sıkışmış"
    if emotion in {"yorgunluk", "boşluk"}:
        return "mat ve ağır"
    if emotion in {"umut", "rahatlama"}:
        return "açılan ve yumuşayan"
    if emotion in {"öfke"}:
        return "sıcak ve itici"
    return "dalgalı"


def infer_theory_lenses(message: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    low = (message or "").lower()
    emotion = analysis.get("primary_emotion", "nötr")
    theme = analysis.get("theme", "belirsiz")
    lenses: List[Dict[str, Any]] = []

    def add(name: str, signal: str, weight: int = 1):
        if name in THEORY_LENSES and all(x["name"] != name for x in lenses):
            lenses.append({"name": name, "signal": signal, "weight": weight})

    if theme in {"terk edilme", "yakınlık"} or contains_any(low, ["özlüyorum", "bırakıldı", "yakın", "uzaklaştı", "beni seviyor mu"]):
        add("John Bowlby", "bağlanma ve yakınlık ritmi", 3)
        add("Peter Fonagy", "ötekinin zihnini okuma çabası", 2)
    if theme in {"görülmeme", "değersizlik"} or contains_any(low, ["görülmüyorum", "değersiz", "kimse anlamıyor"]):
        add("Heinz Kohut", "aynalama ve kendilik ihtiyacı", 3)
        add("Gayatri Chakravorty Spivak", "sesin duyulmaması", 2)
    if analysis.get("contradiction_marker") == "var":
        add("Hegel", "iç gerilim ve dönüşme ihtimali", 2)
        add("Fyodor Dostoyevski", "çok sesli iç konuşma", 2)
    if analysis.get("symbolic_density") == "yüksek" or contains_any(low, ["rüya", "kapı", "oda", "deniz", "tren", "gölge"]):
        add("Jacques Lacan", "arzu ve eksiklik dili", 2)
        add("Donald Winnicott", "geçiş alanı ve imge", 2)
    if contains_any(low, ["beden", "kalbim", "nefes", "titriyorum", "donuyorum", "kasılıyor"]):
        add("Bessel van der Kolk", "beden hafızası", 3)
        add("Peter Levine", "somatik sıkışma", 2)
        add("Pat Ogden", "sensorimotor iz", 2)
    if contains_any(low, ["anlam", "kimim", "amaç", "boşuna", "ölüm", "zaman", "hayat"]):
        add("Rollo May", "anlam ve özgünlük cesareti", 2)
        add("Jean-Paul Sartre", "özgürlük ve sorumluluk yükü", 2)
        add("Isaiah Berlin", "seçim alanı", 1)
    if contains_any(low, ["iş", "para", "ev", "aile", "toplum", "otorite", "baskı", "medya"]):
        add("Antonio Gramsci", "içselleştirilmiş baskı", 2)
        add("Lefebvre/de Certeau", "gündelik yaşam ritimleri", 2)
        add("Stanley Milgram", "otorite ve sınır", 1)
    if contains_any(low, ["hep", "asla", "itiraf", "suç", "vicdan"]):
        add("Lev Tolstoy", "sadeleşme ve etik berraklık", 1)
        add("Melanie Klein", "iyi/kötü iç nesne salınımı", 1)
    if emotion in {"kaygı", "öfke", "umut"}:
        add("Jaak Panksepp", "temel duygu sistemleri", 1)
        add("Mark Solms", "duygu ve anlam köprüsü", 1)
    if contains_any(low, ["fantazi", "sistem", "ideoloji", "normal", "herkes"]):
        add("Slavoj Žižek", "gündelik fantazi ve ideolojik perde", 1)
    if contains_any(low, ["şu an", "burada", "fark ettim", "şimdi"]):
        add("James Bugental", "anlık farkındalık derinliği", 1)
    if contains_any(low, ["çok yoğun", "bölünüyorum", "uçlarda", "ya hep ya hiç"]):
        add("Otto Kernberg", "yoğun ilişki gerilimi ve savunmalar", 1)

    return lenses[:6]


def normalize_client_signals(client_signals: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = safe_dict(client_signals)
    typing = safe_dict(raw.get("typing"))
    voice = safe_dict(raw.get("voice"))
    face = safe_dict(raw.get("face"))
    breath = safe_dict(raw.get("breath"))

    chars_per_min = clamp_float(typing.get("chars_per_min"), 0.0, 1200.0, 0.0)
    pause_ms = clamp_float(typing.get("avg_pause_ms"), 0.0, 8000.0, 0.0)
    backspace_ratio = clamp_float(typing.get("backspace_ratio"), 0.0, 1.0, 0.0)
    speech_rate_wpm = clamp_float(voice.get("speech_rate_wpm"), 0.0, 320.0, 0.0)
    voice_energy = clamp_float(voice.get("energy"), 0.0, 1.0, 0.0)
    pitch_hz = clamp_float(voice.get("pitch_hz"), 0.0, 600.0, 0.0)
    breath_rhythm = clamp_float(breath.get("rhythm"), 0.0, 1.0, 0.0)

    provided = 0
    for value in [chars_per_min, pause_ms, backspace_ratio, speech_rate_wpm, voice_energy, pitch_hz, breath_rhythm]:
        if value > 0:
            provided += 1

    confidence = "düşük"
    if provided >= 5:
        confidence = "yüksek"
    elif provided >= 2:
        confidence = "orta"

    typing_label = "bilinmiyor"
    if chars_per_min > 0:
        if chars_per_min < 90:
            typing_label = "yavaş"
        elif chars_per_min > 280:
            typing_label = "hızlı"
        else:
            typing_label = "denge"

    pause_label = "belirsiz"
    if pause_ms > 0:
        if pause_ms >= 1800:
            pause_label = "uzun duraklamalı"
        elif pause_ms <= 450:
            pause_label = "akışkan"
        else:
            pause_label = "orta"

    return {
        "typing": {
            "chars_per_min": chars_per_min,
            "avg_pause_ms": pause_ms,
            "backspace_ratio": backspace_ratio,
            "label": typing_label,
            "pause_label": pause_label,
        },
        "voice": {
            "speech_rate_wpm": speech_rate_wpm,
            "energy": voice_energy,
            "pitch_hz": pitch_hz,
        },
        "breath": {"rhythm": breath_rhythm},
        "face": {
            "affect": str(face.get("affect", "bilinmiyor")),
            "micro_tension": clamp_float(face.get("micro_tension"), 0.0, 1.0, 0.0),
        },
        "confidence": confidence,
    }


def infer_cultural_style_mix(low: str, analysis: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, float]:
    continuity = safe_dict(profile.get("personality_continuity"))
    japan = clamp_float(continuity.get("japan_silence"), 0.0, 1.0, 0.5)
    turkish = clamp_float(continuity.get("turkish_imply"), 0.0, 1.0, 0.5)
    german = clamp_float(continuity.get("german_direct"), 0.0, 1.0, 0.5)
    latin = clamp_float(continuity.get("latin_warmth"), 0.0, 1.0, 0.5)

    if analysis.get("needs_silence"):
        japan += 0.2
    if analysis.get("contradiction_marker") == "var":
        turkish += 0.12
    if analysis.get("cognitive_load") == "yüksek":
        german += 0.15
    if analysis.get("needs_presence"):
        latin += 0.2
    if any(x in low for x in ["net", "açık konuş", "doğrudan"]):
        german += 0.22
        turkish -= 0.1
    if any(x in low for x in ["nazik", "ince", "ima", "hisset"]):
        turkish += 0.2
        german -= 0.1

    return {
        "japan_silence": clamp_float(japan, 0.0, 1.0, 0.5),
        "turkish_imply": clamp_float(turkish, 0.0, 1.0, 0.5),
        "german_direct": clamp_float(german, 0.0, 1.0, 0.5),
        "latin_warmth": clamp_float(latin, 0.0, 1.0, 0.5),
    }


def build_human_response_policy(
    message: str,
    analysis: Dict[str, Any],
    profile: Dict[str, Any],
    session: Dict[str, Any],
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    low = (message or "").lower()
    normalized = normalize_client_signals(client_signals)
    mix = infer_cultural_style_mix(low, analysis, profile)
    continuity = safe_dict(profile.get("personality_continuity"))

    spontaneity = clamp_float(continuity.get("spontaneity"), 0.0, 1.0, 0.45)
    spontaneity += 0.08 if analysis.get("openness") == "açık" else -0.05
    if analysis.get("needs_silence"):
        spontaneity -= 0.1
    if analysis.get("intensity", 5) >= 8:
        spontaneity -= 0.05
    spontaneity = clamp_float(spontaneity, 0.05, 0.85, 0.45)

    ambiguity = clamp_float(continuity.get("ambiguity_tolerance"), 0.0, 1.0, 0.55)
    if analysis.get("contradiction_marker") == "var":
        ambiguity += 0.12
    if any(x in low for x in ["net cevap", "kesin", "tam olarak"]):
        ambiguity -= 0.2
    ambiguity = clamp_float(ambiguity, 0.15, 0.9, 0.55)

    relational_flex = clamp_float(continuity.get("relational_flexibility"), 0.0, 1.0, 0.5)
    if analysis.get("needs_presence"):
        relational_flex += 0.18
    if analysis.get("attachment_risk") == "yüksek":
        relational_flex += 0.12
    if analysis.get("needs_silence"):
        relational_flex -= 0.08
    relational_flex = clamp_float(relational_flex, 0.1, 0.95, 0.5)

    followup_count = 1
    if analysis.get("openness") == "açık" and analysis.get("intensity", 5) <= 8:
        followup_count = 2
    if analysis.get("needs_silence"):
        followup_count = 1

    pacing = "orta"
    if analysis.get("needs_silence"):
        pacing = "yavaş"
    elif normalized["typing"]["label"] == "hızlı":
        pacing = "akışkan"
    elif normalized["typing"]["pause_label"] == "uzun duraklamalı":
        pacing = "yavaş"

    warmth_score = mix["latin_warmth"] * 0.45 + mix["turkish_imply"] * 0.25 + (0.3 if analysis.get("needs_presence") else 0.12)
    warmth_score = clamp_float(warmth_score, 0.15, 1.0, 0.55)
    warmth_label = "yüksek" if warmth_score >= 0.7 else "orta" if warmth_score >= 0.4 else "düşük"

    contradiction_acceptance = clamp_float(0.35 + (0.25 if analysis.get("contradiction_marker") == "var" else 0.0), 0.1, 0.95, 0.35)
    imperfection_allowance = clamp_float(0.25 + spontaneity * 0.4, 0.1, 0.7, 0.35)

    return {
        "cultural_mix": mix,
        "spontaneity": spontaneity,
        "spontaneity_label": "yüksek" if spontaneity >= 0.62 else "orta" if spontaneity >= 0.34 else "düşük",
        "ambiguity_tolerance": ambiguity,
        "relational_flexibility": relational_flex,
        "contradiction_acceptance": contradiction_acceptance,
        "imperfection_allowance": imperfection_allowance,
        "followup_question_count": followup_count,
        "pacing": pacing,
        "warmth_score": warmth_score,
        "warmth_label": warmth_label,
        "sensor_confidence": normalized.get("confidence", "düşük"),
        "typing_rhythm": normalized.get("typing", {}).get("label", "bilinmiyor"),
        "pause_profile": normalized.get("typing", {}).get("pause_label", "belirsiz"),
        "voice_energy": normalized.get("voice", {}).get("energy", 0.0),
        "message_turns": message_count(session, "user"),
    }


def enrich_analysis_with_human_policy(
    message: str,
    analysis: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile = ensure_profile_shape(profile or default_profile())
    session = session or {"messages": [], "analyses": []}
    layers = safe_dict(analysis.get("layers"))
    hidden = {**safe_dict(layers.get("hidden"))}
    dynamic_tone = {**safe_dict(layers.get("dynamic_tone"))}
    human_layer = {**safe_dict(layers.get("human_layer"))}
    normalized_signals = normalize_client_signals(client_signals)
    policy = build_human_response_policy(message, analysis, profile, session, client_signals)

    hidden["typing_rhythm"] = normalized_signals.get("typing", {}).get("label", "bilinmiyor")
    hidden["pause_pattern"] = normalized_signals.get("typing", {}).get("pause_label", "belirsiz")
    hidden["biometric_signal_confidence"] = normalized_signals.get("confidence", "düşük")

    dynamic_tone["response_pacing"] = policy.get("pacing", dynamic_tone.get("response_pacing", "orta"))
    dynamic_tone["warmth_calibration"] = policy.get("warmth_label", dynamic_tone.get("warmth_calibration", "orta"))
    dynamic_tone["tempo"] = "çok yavaş" if policy.get("pacing") == "yavaş" else dynamic_tone.get("tempo", "orta")

    human_layer["spontaneity"] = policy.get("spontaneity_label", "orta")
    human_layer["imperfection_allowance"] = policy.get("imperfection_allowance", 0.35)
    human_layer["contradiction_acceptance"] = policy.get("contradiction_acceptance", 0.35)
    human_layer["question_depth"] = "derin" if policy.get("followup_question_count", 1) >= 2 else "tek-soru"
    human_layer["cultural_blend"] = policy.get("cultural_mix", {})

    layers["hidden"] = hidden
    layers["dynamic_tone"] = dynamic_tone
    layers["human_layer"] = human_layer
    analysis["layers"] = layers
    analysis["response_policy"] = policy
    analysis["client_signals"] = normalized_signals
    return analysis


def build_background_layers(
    message: str,
    analysis: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
    location: str = "İstanbul",
    ghost_hesitation: bool = False,
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    low = (message or "").lower()
    tokens = tokenize(message)
    profile = ensure_profile_shape(profile or default_profile())
    session = session or {"messages": [], "analyses": []}
    intensity = clamp_int(analysis.get("intensity", 5), 1, 10, 5)
    emotion = analysis.get("primary_emotion", "nötr")
    theme = analysis.get("theme", "belirsiz")
    recent_user = [m.get("content", "") for m in session.get("messages", [])[-8:] if m.get("role") == "user"]
    repeated = [w for w, c in Counter(tokenize(" ".join(recent_user + [message]))).items() if c >= 2][:5]
    safety = detect_crisis_context(message)
    theory_lenses = infer_theory_lenses(message, {**analysis, "safety_layer": safety})
    signal_pack = normalize_client_signals(client_signals)

    object_words = [w for w in tokens if w in {"kapı", "oda", "deniz", "tren", "yağmur", "ev", "yol", "ayna", "ışık", "gölge"}]
    relational_words = [w for w in tokens if w in {"anne", "baba", "sevgili", "arkadaş", "eş", "aile", "patron", "çocuk"}]
    ecological_words = [w for w in tokens if w in {"iş", "para", "ev", "okul", "medya", "haber", "şehir", "hava", "yağmur", "deprem"}]

    layers = {
        "emotion": {
            "texture": infer_emotional_texture(low, emotion, intensity),
            "intensity": intensity,
            "micro_loneliness": "var" if contains_any(low, ["kimse", "yalnız", "tek başıma", "görülmüyorum"]) else "belirsiz",
            "compression": "yüksek" if intensity >= 8 or contains_any(low, ["sıkıştım", "nefes", "daralıyorum"]) else "orta",
            "cognitive_load": analysis.get("cognitive_load", "orta"),
            "energy": analysis.get("energy_level", "orta"),
            "openness": analysis.get("openness", "orta"),
            "rhythm": "kesik" if len(message.split()) < 5 else "akışkan",
            "weather": "gece/loş" if analysis.get("night_signal") else "nötr",
            "drift": "içe çekilme" if analysis.get("needs_silence") else "temas arayışı" if analysis.get("needs_presence") else "dengeli",
            "healing_signal": "var" if emotion in {"umut", "rahatlama"} else "zayıf",
            "echo": repeated,
            "continuity": "tekrar ediyor" if repeated else "tekil",
            "granularity": "yüksek" if len(tokens) >= 18 else "düşük",
        },
        "narrative": {
            "engine": "kendilik anlatısı" if contains_any(low, ["ben hep", "ben asla", "kimim", "bana hep"]) else "olay anlatısı",
            "self_narrative": theme,
            "narrative_shift": "var" if analysis.get("contradiction_marker") == "var" else "belirsiz",
            "inner_rewrite": "mümkün" if contains_any(low, ["fark ettim", "aslında", "belki"]) else "henüz zayıf",
            "story_pattern": "mutlaklaştırma" if contains_any(low, ["hep", "asla", "hiç kimse"]) else "açık uçlu",
            "psychological_atmosphere": "yoğun" if intensity >= 7 else "sakin/orta",
        },
        "contradiction": {
            "detected": analysis.get("contradiction_marker") == "var",
            "internal_conflict": "yaklaşma-geri çekilme" if contains_any(low, ["istiyorum ama", "bir yandan", "yakın ama"]) else "belirsiz",
            "reflective_duality": "var" if contains_any(low, ["bir yanım", "diğer yanım", "aslında"]) else "yok",
            "meta_awareness": "var" if contains_any(low, ["farkındayım", "biliyorum", "anlıyorum"]) else "belirsiz",
        },
        "relationship": {
            "pattern": "yakınlık arayışı" if analysis.get("needs_presence") else "özerklik arayışı",
            "attachment_style_signal": "kaygılı yakınlık" if theme in {"terk edilme", "yakınlık"} else "belirsiz",
            "relational_energy": "düşük" if analysis.get("energy_level") == "düşük" else "orta",
            "approach_withdrawal": "geri çekilme" if analysis.get("needs_silence") else "yaklaşma",
            "social_exhaustion": "var" if contains_any(low, ["insanlardan", "kimseyle", "sosyal", "yoruldum"]) else "belirsiz",
            "relational_rhythm": "kesintili" if contains_any(low, ["geliyor gidiyor", "bir var bir yok"]) else "sabit değil",
        },
        "symbolic": {
            "density": analysis.get("symbolic_density", "düşük"),
            "objects": object_words,
            "object_memory": object_words[:3],
            "continuity": "sembolik iz var" if object_words else "zayıf",
            "timeline": "geçmiş-şimdi bağı" if contains_any(low, ["eskiden", "çocukken", "yine"]) else "şimdi",
            "reflection": "ayna etkisi" if contains_any(low, ["ayna", "gördüm", "fark ettim"]) else "belirsiz",
            "archetype_detection": "eşik/yol" if contains_any(low, ["kapı", "yol", "tren"]) else "belirsiz",
        },
        "dream": {
            "image_extraction": object_words,
            "figure_analysis": relational_words,
            "emotion": emotion,
            "continuation_ready": contains_any(low, ["rüya", "rüyam", "uyandım", "gördüm"]),
            "dream_method_stack": ["Jung", "Freud", "Lacan", "Hillman", "Bachelard"] if contains_any(low, ["rüya", "rüyam"]) else [],
        },
        "existential": {
            "meaning": "aktif" if contains_any(low, ["anlam", "amaç", "boşuna"]) else "arka planda",
            "identity": "aktif" if contains_any(low, ["kimim", "ben neyim", "kendim"]) else "belirsiz",
            "loneliness": "aktif" if contains_any(low, ["yalnız", "kimse"]) else "belirsiz",
            "direction": "yön arayışı" if theme == "yön kaybı" or contains_any(low, ["nereye", "yol", "amaç"]) else "belirsiz",
            "mortality_reflection": "var" if contains_any(low, ["ölüm", "fani", "zaman geçiyor"]) else "yok",
        },
        "memory": {
            "episodic": "var" if contains_any(low, ["dün", "bugün", "geçen", "çocukken", "o gün"]) else "zayıf",
            "emotional": emotion,
            "symbolic": object_words,
            "relational": relational_words,
            "echo": repeated,
            "contextual_recall": "var" if repeated else "zayıf",
            "confidence": "orta" if len(session.get("analyses", [])) >= 3 else "düşük",
        },
        "emotional_graph": {
            "theme_node": theme,
            "emotion_node": emotion,
            "connection": f"{theme} → {emotion}" if theme != "belirsiz" and emotion != "nötr" else "zayıf",
            "constellation": repeated,
            "repeating_theme": profile.get("core_trigger") or "belirsiz",
        },
        "hidden": {
            "passive_behavioral": "aktif",
            "writing_style": "kısa/kesik" if len(message.split()) < 8 else "anlatısal",
            "typing_rhythm": signal_pack.get("typing", {}).get("label", "bilinmiyor"),
            "pause_pattern": signal_pack.get("typing", {}).get("pause_label", "belirsiz"),
            "biometric_signal_confidence": signal_pack.get("confidence", "düşük"),
            "ghost_hesitation": bool(ghost_hesitation),
            "language_fingerprint": "Türkçe/karma" if re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]", message) else "belirsiz",
            "silence_pattern": "olası" if analysis.get("needs_silence") else "belirsiz",
        },
        "dynamic_tone": {
            "tempo": "çok yavaş" if analysis.get("needs_silence") else "yavaş" if intensity >= 7 else "orta",
            "response_pacing": "kısa aralıklı",
            "reflection_depth": "derin" if intensity >= 8 or analysis.get("symbolic_density") == "yüksek" else "orta",
            "silence_engine": "aktif" if analysis.get("needs_silence") else "pasif",
            "warmth_calibration": "yüksek" if analysis.get("needs_presence") else "orta",
        },
        "safety_ethics": {
            **safety,
            "parasocial_risk": "izle" if contains_any(low, ["sadece sen", "senden başka", "hep sen"]) else "düşük",
            "dependency_escalation": "izle" if contains_any(low, ["sensiz yapamam", "hep burada ol"]) else "düşük",
            "controlled_attachment": "sınır korunacak",
            "ethical_reciprocity": "insan merkezi korunacak",
            "boundary_preservation": "aktif",
        },
        "time_ecology": {
            "location": location or "belirsiz",
            "climate_words": [w for w in ecological_words if w in {"hava", "yağmur", "şehir"}],
            "home_dynamics": "var" if contains_any(low, ["ev", "aile", "oda"]) else "belirsiz",
            "financial": "var" if contains_any(low, ["para", "borç", "maaş", "işsiz"]) else "belirsiz",
            "work": "var" if contains_any(low, ["iş", "meslek", "patron", "ofis"]) else "belirsiz",
            "media": "var" if contains_any(low, ["haber", "sosyal medya", "video"]) else "belirsiz",
            "acute_event": "var" if contains_any(low, ["az önce", "şimdi oldu", "bugün oldu"]) else "belirsiz",
        },
        "cultural_epistemic": {
            "moral_reasoning": "sorumluluk/adalet" if contains_any(low, ["hak", "haksız", "suç", "ayıp"]) else "belirsiz",
            "aesthetic_sensitivity": "var" if contains_any(low, ["güzel", "renk", "ses", "ışık", "müzik"]) else "belirsiz",
            "structural_violence": "var" if contains_any(low, ["sistem", "baskı", "toplum", "sınıf"]) else "belirsiz",
            "trust_suspicion": "şüphe" if contains_any(low, ["güvenemiyorum", "emin değilim", "şüphe"]) else "belirsiz",
            "language_expression": "imgesel" if object_words else "düz anlatı",
            "value_hierarchy": "yakınlık/güven" if theme in {"yakınlık", "terk edilme"} else "belirsiz",
            "authority_perception": "aktif" if contains_any(low, ["otorite", "patron", "aile", "devlet"]) else "belirsiz",
            "time_perception": "sıkışmış" if contains_any(low, ["geç kaldım", "zaman", "yetişemiyorum"]) else "belirsiz",
            "ritual_symbol_language": "var" if object_words else "zayıf",
        },
        "reflection": {
            "future_self": "sorulabilir" if analysis.get("openness") != "kapalı" else "şimdilik bekle",
            "reflective_questioning": "yumuşak soru uygun",
            "gentle_reframing": "uygun" if intensity < 9 else "çok hafif",
            "perspective_expansion": "mümkün" if analysis.get("openness") == "açık" else "sınırlı",
            "soft_insight": "uygun",
        },
        "human_layer": {
            "hesitation_simulation": "kısa duraklama hissi",
            "natural_pause": "aktif" if analysis.get("needs_silence") else "orta",
            "imperfect_cadence": "izinli",
            "repair_recovery": "yanlış anlama olursa düzelt",
            "human_warmth": "yüksek" if analysis.get("needs_presence") else "orta",
        },
    }

    return {
        "layers": layers,
        "theory_lenses": theory_lenses,
        "safety_layer": safety,
        "client_signals": signal_pack,
    }


def heuristic_analysis(
    message: str,
    profile: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
    location: str = "İstanbul",
    ghost_hesitation: bool = False,
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    low = (message or "").lower()
    intensity = 5
    emotion = "nötr"
    theme = "belirsiz"
    energy = "orta"
    openness = "orta"
    attachment = "düşük"
    cognitive = "orta"
    symbolic = "düşük"
    needs_presence = False
    needs_solution = False
    needs_silence = False
    contradiction = "yok"
    narrative = "yok"

    if any(k in low for k in ["yorgun", "bitkin", "tükendim", "uykum var", "uyuyamıyorum"]):
        emotion = "yorgunluk"
        theme = "yorgunluk"
        energy = "düşük"
        intensity = 7
        needs_presence = True
        needs_silence = True
    elif any(k in low for k in ["yalnız", "kimse", "tek başıma", "boş", "görünmüyorum"]):
        emotion = "yalnızlık"
        theme = "görülmeme"
        intensity = 8
        attachment = "orta"
        needs_presence = True
    elif any(k in low for k in ["değersiz", "yetersiz", "fazlalık", "önemsiz"]):
        emotion = "değersizlik"
        theme = "değersizlik"
        intensity = 8
        needs_presence = True
    elif any(k in low for k in ["kırgın", "incindim", "üzgün", "ağladım", "acı"]):
        emotion = "kırgınlık"
        theme = "görülmeme"
        intensity = 7
        needs_presence = True
    elif any(k in low for k in ["kaygı", "anksiyete", "panik", "korkuyorum", "geriliyorum"]):
        emotion = "kaygı"
        theme = "belirsizlik"
        intensity = 8
        energy = "düşük"
        needs_presence = True
    elif any(k in low for k in ["öfke", "sinir", "kızgınım", "bıktım"]):
        emotion = "öfke"
        theme = "kontrol kaybı"
        intensity = 7
        needs_presence = True
    elif any(k in low for k in ["özledim", "hasret", "geri gelsin", "aklımda"]):
        emotion = "özlem"
        theme = "özlem"
        intensity = 7
        attachment = "orta"
        needs_presence = True
    elif any(k in low for k in ["umut", "iyi hissediyorum", "rahatladım", "hafifledim"]):
        emotion = "umut"
        theme = "belirsizlik"
        intensity = 5
        energy = "orta"
        openness = "açık"
        needs_solution = True

    if any(k in low for k in ["terk", "bıraktı", "gidecek", "kaybederim"]):
        theme = "terk edilme"
        attachment = "yüksek"
    if any(k in low for k in ["nereye", "amaç", "yolumu", "kayboldum", "yön"]):
        theme = "yön kaybı"
    if any(k in low for k in ["çatışma", "kavga", "tartışma", "çelişki"]):
        theme = "çatışma"
    if any(k in low for k in ["yakın", "sarıl", "temas", "güven"]):
        theme = "yakınlık"

    if any(k in low for k in ["rüya", "rüyam", "gördüm", "sembol", "işaret", "kapı", "yağmur", "deniz", "tren", "oda", "ayna", "ışık", "gölge"]):
        symbolic = "yüksek"

    if len(message) < 18 and any(k in low for k in ["boşver", "iyiyim", "tamam", "geçti"]):
        openness = "kapalı"
        needs_presence = True
        needs_silence = True

    if any(k in low for k in ["ama", "aslında", "yani", "bir yandan", "hem"]):
        contradiction = "var"

    if any(k in low for k in ["hep", "daima", "asla", "hiç kimse"]):
        narrative = "anlatı"

    if len(message) > 500 or message.count(",") + message.count(";") > 5:
        cognitive = "yüksek"
    elif "!" in message:
        cognitive = "orta"

    safety = detect_crisis_context(message)
    if safety.get("needs_gentle_check"):
        needs_presence = True

    base = {
        "primary_emotion": emotion,
        "intensity": intensity,
        "theme": theme,
        "energy_level": energy,
        "openness": openness,
        "attachment_risk": attachment,
        "cognitive_load": cognitive,
        "symbolic_density": symbolic,
        "crisis_risk": bool(safety.get("route_to_emergency")),
        "needs_presence": needs_presence,
        "needs_solution": needs_solution,
        "needs_silence": needs_silence,
        "contradiction_marker": contradiction,
        "narrative_marker": narrative,
        "night_signal": True if istanbul_now().hour >= 22 or istanbul_now().hour <= 6 else False,
    }
    deep = build_background_layers(message, base, profile, session, location, ghost_hesitation, client_signals)
    base.update(deep)
    return enrich_analysis_with_human_policy(message, base, profile, session, client_signals)


def parse_json_safely(text: str) -> Dict[str, Any]:
    txt = (text or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?", "", txt).strip()
        if txt.endswith("```"):
            txt = txt[:-3].strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def normalize_analysis(
    data: Dict[str, Any],
    fallback: Dict[str, Any],
    message: str,
    profile: Optional[Dict[str, Any]],
    session: Optional[Dict[str, Any]],
    location: str,
    ghost_hesitation: bool,
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analysis = {
        "primary_emotion": str(data.get("primary_emotion", fallback["primary_emotion"])),
        "intensity": clamp_int(data.get("intensity", fallback["intensity"]), 1, 10, fallback["intensity"]),
        "theme": str(data.get("theme", fallback["theme"])),
        "energy_level": str(data.get("energy_level", fallback["energy_level"])),
        "openness": str(data.get("openness", fallback["openness"])),
        "attachment_risk": str(data.get("attachment_risk", fallback["attachment_risk"])),
        "cognitive_load": str(data.get("cognitive_load", fallback["cognitive_load"])),
        "symbolic_density": str(data.get("symbolic_density", fallback["symbolic_density"])),
        "crisis_risk": bool(data.get("crisis_risk", fallback["crisis_risk"])),
        "needs_presence": bool(data.get("needs_presence", fallback["needs_presence"])),
        "needs_solution": bool(data.get("needs_solution", fallback["needs_solution"])),
        "needs_silence": bool(data.get("needs_silence", fallback["needs_silence"])),
        "contradiction_marker": str(data.get("contradiction_marker", fallback["contradiction_marker"])),
        "narrative_marker": str(data.get("narrative_marker", fallback["narrative_marker"])),
        "night_signal": bool(data.get("night_signal", fallback["night_signal"])),
    }
    deep = build_background_layers(message, analysis, profile, session, location, ghost_hesitation, client_signals)
    analysis.update(deep)
    analysis["crisis_risk"] = bool(analysis.get("safety_layer", {}).get("route_to_emergency"))
    return enrich_analysis_with_human_policy(message, analysis, profile, session, client_signals)


def should_use_analysis_fast_path(message: str, fallback: Dict[str, Any]) -> tuple[bool, str]:
    text = (message or "").strip()
    if not text:
        return True, "empty"

    low = text.lower()
    folded = fold_turkish_ascii(low)
    safety = safe_dict(fallback.get("safety_layer")) or detect_crisis_context(text)
    if safety.get("route_to_emergency") or safety.get("needs_gentle_check") or safety.get("has_crisis_keyword"):
        return False, "safety_guard"

    risk_markers = [
        "intihar", "kendime zarar", "öldüreceğim", "tecavüz", "istismar",
        "tehdit", "silah", "bıçak", "bicak", "ilaçları", "ilaclari",
        "güvende değilim", "guvende degilim",
    ]
    if contains_any(folded, [fold_turkish_ascii(x) for x in risk_markers]):
        return False, "risk_marker"

    if has_dream_context(text):
        return False, "dream_context"

    if clamp_int(fallback.get("intensity", 5), 1, 10, 5) >= 7:
        return False, "high_intensity"
    if str(fallback.get("attachment_risk", "")).lower() == "yüksek":
        return False, "attachment_risk"

    token_count = len(tokenize(text))
    short_exact = {
        "tamam", "ok", "okey", "devam", "evet", "hayir", "hayır", "peki",
        "oldu", "anladim", "anladım", "selam", "merhaba", "naber",
        "nasilsin", "nasılsın", "iyi", "tesekkur", "teşekkür",
    }
    if folded in {fold_turkish_ascii(x) for x in short_exact}:
        return True, "short_low_risk"

    greeting_fragments = ["merhaba", "selam", "nasilsin", "nasılsın", "gunaydin", "günaydın", "iyi aksam", "iyi akşam"]
    if token_count <= 4 and any(fold_turkish_ascii(g) in folded for g in greeting_fragments):
        return True, "greeting"

    if is_technical_or_utility_context(text):
        return True, "technical_utility"

    if len(text) <= 28 and token_count <= 5:
        return True, "short_neutral"

    if len(text) <= 180 and fallback.get("theme") == "belirsiz" and fallback.get("primary_emotion") in {"nötr", "rahatlama"}:
        return True, "neutral_low_risk"

    return False, "needs_model_analysis"


def analyze_emotion(
    message: str,
    profile: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
    location: str = "İstanbul",
    ghost_hesitation: bool = False,
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fallback = heuristic_analysis(message, profile, session, location, ghost_hesitation, client_signals)
    fast_ok, fast_reason = should_use_analysis_fast_path(message, fallback)
    if fast_ok:
        log_latency("analysis_fast_path", reason=fast_reason, message_chars=len(message))
        return fallback

    if not client:
        logging.warning("API client yok, fallback kullanılıyor")
        return fallback

    system_prompt = """
Sen yalnızca JSON üreten bir analiz modülüsün.
Sadece geçerli JSON ver. Açıklama yazma.

Kriz kelimeleri geçerse bağlama bak:
- Anlık yardım isteği, plan, kendine zarar niyeti veya şu an güvenlik tehlikesi varsa crisis_risk=true.
- Geçmiş anlatım, haber, film, soru, kavramsal konuşma veya örnek ise crisis_risk=false.

Şema:
{
  "primary_emotion": "kaygı|öfke|yalnızlık|değersizlik|utanç|boşluk|umut|kararsızlık|kırgınlık|rahatlama|nötr|yorgunluk|özlem",
  "intensity": 1-10,
  "theme": "görülmeme|kontrol kaybı|değersizlik|terk edilme|belirsizlik|özlem|yorgunluk|yön kaybı|yakınlık|çatışma|belirsiz",
  "energy_level": "düşük|orta|yüksek",
  "openness": "kapalı|orta|açık",
  "attachment_risk": "düşük|orta|yüksek",
  "cognitive_load": "düşük|orta|yüksek",
  "symbolic_density": "düşük|orta|yüksek",
  "crisis_risk": false,
  "needs_presence": false,
  "needs_solution": false,
  "needs_silence": false,
  "contradiction_marker": "yok|var",
  "narrative_marker": "yok|anlatı|savunma|geri çekilme",
  "night_signal": false
}

Yalnızca JSON.
"""

    api_start = perf_counter()
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
            max_tokens=260,
        )
        raw = response.choices[0].message.content or ""
        data = parse_json_safely(raw)
        return normalize_analysis(data, fallback, message, profile, session, location, ghost_hesitation, client_signals)
    except Exception as e:
        logging.warning(f"Emotion analysis fallback used: {e}")
        if is_model_auth_error(e):
            fallback["model_auth_error"] = True
        return fallback
    finally:
        log_latency("analysis_model", api_ms=ms_since(api_start), message_chars=len(message))


# =========================================================
# STATE UPDATE / DIGEST / MEMORY
# =========================================================
def update_graph(profile: Dict[str, Any], theme: str, emotion: str):
    graph = profile.setdefault("emotional_graph", {"nodes": {}, "edges": {}})
    nodes = graph.setdefault("nodes", {})
    edges = graph.setdefault("edges", {})

    def bump_node(label: str):
        nodes[label] = int(nodes.get(label, 0)) + 1

    def bump_edge(a: str, b: str):
        key = f"{a} → {b}"
        edges[key] = int(edges.get(key, 0)) + 1

    if theme and theme != "belirsiz":
        bump_node(theme)
    if emotion and emotion != "nötr":
        bump_node(emotion)
    if theme and emotion and theme != "belirsiz" and emotion != "nötr":
        bump_edge(theme, emotion)


def update_profile_from_analysis(profile: Dict[str, Any], analysis: Dict[str, Any]):
    profile = ensure_profile_shape(profile)
    emotion = analysis.get("primary_emotion", "nötr")
    theme = analysis.get("theme", "belirsiz")

    if theme and theme != "belirsiz" and theme in profile["themes"]:
        profile["themes"][theme] = int(profile["themes"].get(theme, 0)) + 1
        profile["core_trigger"] = theme

    profile["emotion_counts"][emotion] = int(profile["emotion_counts"].get(emotion, 0)) + 1

    if emotion == "kaygı":
        profile["anxiety_score"] = min(100, profile.get("anxiety_score", 50) + 4)
    elif emotion in {"umut", "rahatlama"}:
        profile["anxiety_score"] = max(0, profile.get("anxiety_score", 50) - 3)

    rel = profile["relationship_signature"]
    if analysis.get("attachment_risk") == "yüksek":
        rel["withdrawing"] += 1
    if analysis.get("needs_presence"):
        rel["opening"] += 1
    if analysis.get("cognitive_load") == "yüksek":
        rel["deep_session"] += 1
    if analysis.get("night_signal"):
        rel["night_activity"] += 1

    relationship_layer = safe_dict(safe_dict(analysis.get("layers")).get("relationship"))
    if relationship_layer.get("approach_withdrawal") == "yaklaşma":
        rel["approach"] += 1
    if relationship_layer.get("social_exhaustion") == "var":
        rel["social_exhaustion"] += 1

    update_graph(profile, theme, emotion)

    layers = safe_dict(analysis.get("layers"))
    for name in ANALYSIS_LAYER_NAMES:
        if name in layers:
            profile["analysis_layers"][name]["count"] += 1
            signal = layers[name]
            if isinstance(signal, dict):
                profile["analysis_layers"][name]["last_signal"] = {
                    k: v for k, v in list(signal.items())[:6]
                }
            else:
                profile["analysis_layers"][name]["last_signal"] = signal
            profile["analysis_layers"][name]["last_seen"] = now_iso()

    for lens in safe_list(analysis.get("theory_lenses")):
        name = lens.get("name")
        if name in profile["theory_lenses"]:
            profile["theory_lenses"][name] = int(profile["theory_lenses"].get(name, 0)) + int(lens.get("weight", 1))

    memory_layer = safe_dict(layers.get("memory"))
    if memory_layer.get("episodic") == "var":
        profile["memory_signals"]["episodic"] += 1
    if memory_layer.get("emotional") and memory_layer.get("emotional") != "nötr":
        profile["memory_signals"]["emotional"] += 1
    if memory_layer.get("symbolic"):
        profile["memory_signals"]["symbolic"] += 1
    if memory_layer.get("relational"):
        profile["memory_signals"]["relational"] += 1
    if sum(int(v) for k, v in profile["memory_signals"].items() if isinstance(v, int)) >= 8:
        profile["memory_signals"]["confidence"] = "orta"
    if sum(int(v) for k, v in profile["memory_signals"].items() if isinstance(v, int)) >= 20:
        profile["memory_signals"]["confidence"] = "yüksek"

    policy = safe_dict(analysis.get("response_policy"))
    if policy:
        continuity = profile["personality_continuity"]
        smoothing = 0.12
        mix = safe_dict(policy.get("cultural_mix"))
        mapping = {
            "japan_silence": safe_float(mix.get("japan_silence", continuity["japan_silence"])),
            "turkish_imply": safe_float(mix.get("turkish_imply", continuity["turkish_imply"])),
            "german_direct": safe_float(mix.get("german_direct", continuity["german_direct"])),
            "latin_warmth": safe_float(mix.get("latin_warmth", continuity["latin_warmth"])),
            "spontaneity": safe_float(policy.get("spontaneity", continuity["spontaneity"])),
            "ambiguity_tolerance": safe_float(policy.get("ambiguity_tolerance", continuity["ambiguity_tolerance"])),
            "relational_flexibility": safe_float(policy.get("relational_flexibility", continuity["relational_flexibility"])),
            "repair_tendency": safe_float(policy.get("contradiction_acceptance", continuity["repair_tendency"])),
        }
        for key, new_value in mapping.items():
            old_value = clamp_float(continuity.get(key), 0.0, 1.0, 0.5)
            continuity[key] = round(clamp_float(old_value * (1 - smoothing) + new_value * smoothing, 0.0, 1.0, 0.5), 4)

    micro = profile["micro_signal_memory"]
    client_signals = safe_dict(analysis.get("client_signals"))
    typing_signals = safe_dict(client_signals.get("typing"))
    typing_label = str(typing_signals.get("label", "")).strip()
    pause_label = str(typing_signals.get("pause_label", "")).strip()
    if typing_label:
        micro["typing_rhythm"][typing_label] = int(micro["typing_rhythm"].get(typing_label, 0)) + 1
    if pause_label:
        micro["pause_patterns"][pause_label] = int(micro["pause_patterns"].get(pause_label, 0)) + 1

    signal_conf_raw = str(client_signals.get("confidence", "düşük")).lower()
    prev_conf_raw = str(micro.get("biometric_confidence", "düşük")).lower()
    signal_conf = "yüksek" if ("yük" in signal_conf_raw or "yuk" in signal_conf_raw) else "orta" if "ort" in signal_conf_raw else "düşük"
    prev_conf = "yüksek" if ("yük" in prev_conf_raw or "yuk" in prev_conf_raw) else "orta" if "ort" in prev_conf_raw else "düşük"
    if signal_conf == "yüksek" or (signal_conf == "orta" and prev_conf == "düşük"):
        micro["biometric_confidence"] = signal_conf

    if analysis.get("contradiction_marker") == "var":
        micro["tone_shifts"].append({
            "emotion": emotion,
            "theme": theme,
            "note": "iç gerilim / ton kayması",
            "ts": now_iso(),
        })
    if theme in {"görülmeme", "terk edilme", "değersizlik"}:
        micro["hurt_traces"].append({
            "theme": theme,
            "emotion": emotion,
            "ts": now_iso(),
        })
    symbolic_objects = safe_dict(analysis.get("layers", {})).get("symbolic", {}).get("objects", [])
    snippet = compact_text(", ".join([str(x) for x in safe_list(symbolic_objects)]), 100)
    if snippet:
        micro["contextual_details"].append({"detail": snippet, "ts": now_iso()})

    micro["tone_shifts"] = micro["tone_shifts"][-80:]
    micro["hurt_traces"] = micro["hurt_traces"][-80:]
    micro["contextual_details"] = micro["contextual_details"][-80:]

    profile["recent_emotions"].append({
        "emotion": emotion,
        "theme": theme,
        "intensity": analysis.get("intensity", 5),
        "layers": {
            "emotion": safe_dict(layers.get("emotion")).get("texture"),
            "narrative": safe_dict(layers.get("narrative")).get("story_pattern"),
            "relationship": safe_dict(layers.get("relationship")).get("pattern"),
            "symbolic": safe_dict(layers.get("symbolic")).get("density"),
        },
        "ts": now_iso(),
    })
    profile["recent_emotions"] = profile["recent_emotions"][-120:]


def build_weekly_digest(profile: Dict[str, Any], session: Dict[str, Any], garden: List[Dict[str, Any]]) -> Dict[str, Any]:
    profile = ensure_profile_shape(profile)
    analyses = session.get("analyses", [])[-60:]
    user_messages = [m.get("content", "") for m in session.get("messages", []) if m.get("role") == "user"]
    data_points = len(analyses) + len(garden) + len(user_messages)

    if data_points < 3:
        digest = {
            "enough_data": False,
            "message": "Henüz yeterli veri toplanamadı.",
            "dominant_emotion": "belirgin değil",
            "dominant_theme": "belirgin değil",
            "growth_markers": ["Birkaç konuşma daha olduğunda daha anlamlı bir farkındalık özeti çıkarabilirim."],
            "unresolved_themes": ["Henüz belirgin değil"],
            "constellation_summary": "Henüz güçlü bir sembolik veya duygusal düğüm oluşmadı.",
            "keywords": top_keywords(user_messages, 6),
            "data_points": data_points,
        }
        profile["weekly_report"] = digest
        return digest

    emotion_counts = Counter(a.get("primary_emotion", "nötr") for a in analyses)
    dominant_emotion = emotion_counts.most_common(1)[0][0] if emotion_counts else "nötr"

    theme_counts = profile.get("themes", {})
    sorted_themes = sorted(theme_counts.items(), key=lambda kv: kv[1], reverse=True)
    dominant_theme = sorted_themes[0][0] if sorted_themes and sorted_themes[0][1] > 0 else "belirgin değil"

    unresolved = [t for t, c in sorted_themes if c > 1][:3]
    growth_markers = []

    if emotion_counts.get("umut", 0) > 0 or emotion_counts.get("rahatlama", 0) > 0:
        growth_markers.append("Umut veya rahatlama tekrar görünür olmuş.")
    if emotion_counts.get("kaygı", 0) > 0 and (emotion_counts.get("umut", 0) > 0 or emotion_counts.get("rahatlama", 0) > 0):
        growth_markers.append("Kaygı var ama tek ton değil; yanında yumuşama da var.")
    if profile.get("relationship_signature", {}).get("opening", 0) > profile.get("relationship_signature", {}).get("withdrawing", 0):
        growth_markers.append("Açılma ve ifade etme tarafı güçleniyor.")
    if profile.get("anxiety_score", 50) < 50:
        growth_markers.append("Genel gerilim hafif düşmüş görünüyor.")

    constellation_items = []
    for item in reversed(garden[-40:]):
        text = item.get("text", "").strip()
        if text:
            constellation_items.append(text[:70])
        if len(constellation_items) >= 2:
            break

    dominant_layers = sorted(
        profile.get("analysis_layers", {}).items(),
        key=lambda kv: safe_dict(kv[1]).get("count", 0),
        reverse=True,
    )[:4]
    layer_summary = [name for name, data in dominant_layers if safe_dict(data).get("count", 0) > 0]
    keywords = top_keywords(user_messages, 8)

    constellation_summary = " / ".join(constellation_items) if constellation_items else "Henüz güçlü bir sembolik düğüm görünmüyor."

    digest = {
        "enough_data": True,
        "message": "Farkındalık özeti hazır.",
        "dominant_emotion": dominant_emotion,
        "dominant_theme": dominant_theme,
        "growth_markers": growth_markers[:4] if growth_markers else ["Henüz izlenebilir bir büyüme cümlesi oluşmadı."],
        "unresolved_themes": unresolved if unresolved else ["Henüz belirgin değil"],
        "constellation_summary": constellation_summary,
        "keywords": keywords,
        "active_layers": layer_summary,
        "data_points": data_points,
    }
    profile["weekly_report"] = digest
    return digest


def build_weekly_digest_text(digest: Dict[str, Any]) -> str:
    if not digest.get("enough_data", True):
        return (
            "FARKINDALIK ÖZETİ\n\n"
            "Henüz yeterli veri toplanamadı.\n\n"
            "Birkaç konuşma daha olduğunda duygu, tema ve tekrar eden izleri daha güvenilir şekilde toparlayabilirim."
        )

    growth = digest.get("growth_markers", [])
    unresolved = digest.get("unresolved_themes", [])
    const = digest.get("constellation_summary", "")
    keywords = digest.get("keywords", [])

    return (
        f"FARKINDALIK ÖZETİ\n\n"
        f"Öne çıkan duygu: {digest.get('dominant_emotion', 'nötr')}\n"
        f"Öne çıkan tema: {digest.get('dominant_theme', 'belirgin değil')}\n\n"
        f"Başlıca kelimeler:\n- " + "\n- ".join(keywords or ["Henüz belirgin değil"]) + "\n\n"
        f"Gelişim izleri:\n- " + "\n- ".join(growth) + "\n\n"
        f"Açık kalan temalar:\n- " + "\n- ".join(unresolved) + "\n\n"
        f"Sembolik özet:\n{const}\n"
    )


def score_memory_item(query: str, text: str) -> int:
    return keyword_score(query, text)


def retrieve_memory_snippets(
    query: str,
    session: Dict[str, Any],
    notes: List[Dict[str, Any]],
    garden: List[Dict[str, Any]],
    profile: Dict[str, Any],
    limit: int = 5,
) -> List[str]:
    candidates: List[tuple[int, str]] = []

    for msg in session.get("messages", [])[-18:]:
        content = msg.get("content", "").strip()
        if content:
            candidates.append((score_memory_item(query, content), content))

    for note in notes[-20:]:
        content = note.get("text", "").strip()
        if content:
            candidates.append((score_memory_item(query, content), f"Not: {content}"))

    for item in garden[-50:]:
        content = item.get("text", "").strip()
        if content:
            candidates.append((score_memory_item(query, content), f"Yankı: {content}"))

    core = profile.get("core_trigger")
    if core and core != "belirsiz":
        candidates.append((2, f"Ana tema: {core}"))

    uniq: List[str] = []
    seen = set()
    for score, text in sorted(candidates, key=lambda x: x[0], reverse=True):
        key = text.lower()
        if score > 0 and key not in seen:
            seen.add(key)
            uniq.append(text)
        if len(uniq) >= limit:
            break

    return uniq


def append_memory_garden_anchor(garden: List[Dict[str, Any]], message: str, analysis: Dict[str, Any]):
    theme = analysis.get("theme", "belirsiz")
    emotion = analysis.get("primary_emotion", "nötr")
    intensity = clamp_int(analysis.get("intensity", 5), 1, 10, 5)
    layers = safe_dict(analysis.get("layers"))

    important = (
        intensity >= 7
        or theme in {"görülmeme", "kontrol kaybı", "değersizlik", "terk edilme", "belirsizlik", "özlem", "yorgunluk", "yön kaybı"}
        or analysis.get("symbolic_density") == "yüksek"
        or safe_dict(layers.get("existential")).get("meaning") == "aktif"
    )
    if important:
        garden.append({
            "text": message[:500],
            "theme": theme,
            "emotion": emotion,
            "intensity": intensity,
            "kind": "anchor",
            "layers": {
                "emotion_texture": safe_dict(layers.get("emotion")).get("texture"),
                "narrative": safe_dict(layers.get("narrative")).get("story_pattern"),
                "relationship": safe_dict(layers.get("relationship")).get("pattern"),
                "symbolic": safe_dict(layers.get("symbolic")).get("objects", []),
                "existential": safe_dict(layers.get("existential")).get("meaning"),
            },
            "ts": now_iso(),
        })
        garden[:] = garden[-120:]


def build_memory_overview(profile: Dict[str, Any], session: Dict[str, Any], garden: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_texts = [m.get("content", "") for m in session.get("messages", []) if m.get("role") == "user"]
    analyses = session.get("analyses", [])[-60:]
    raw_keywords = top_keywords(user_texts, 12)
    keywords = [k for k in raw_keywords if is_thematic_phrase(k)]
    keywords = keywords[:10]
    theme_counts = Counter(a.get("theme", "belirsiz") for a in analyses if a.get("theme") != "belirsiz")
    emotion_counts = Counter(a.get("primary_emotion", "nötr") for a in analyses if a.get("primary_emotion") != "nötr")

    images = []
    behaviors = []
    for a in analyses:
        layers = safe_dict(a.get("layers"))
        symbolic = safe_dict(layers.get("symbolic"))
        images.extend(safe_list(symbolic.get("objects")))
        rel = safe_dict(layers.get("relationship"))
        if rel.get("approach_withdrawal"):
            behaviors.append(rel["approach_withdrawal"])

    return {
        "confidence": profile.get("memory_signals", {}).get("confidence", "düşük"),
        "keywords": keywords,
        "repeating_themes": [x for x, _ in theme_counts.most_common(5)],
        "dominant_emotions": [x for x, _ in emotion_counts.most_common(5)],
        "images_symbols": list(dict.fromkeys(images))[:8],
        "behavior_patterns": [x for x, _ in Counter(behaviors).most_common(4)],
        "general_state": (
            "Henüz yeterli iz yok."
            if len(user_texts) < 3
            else "Henüz belirgin tematik kelime birikmedi."
            if not keywords
            else "Konuşmada tekrar eden duygu, tema ve sembolik izler oluşmaya başladı."
        ),
    }


# =========================================================
# PROMPTS / GENERATION
# =========================================================
def build_layer_prompt_summary(analysis: Dict[str, Any], digest: Dict[str, Any]) -> str:
    layers = safe_dict(analysis.get("layers"))
    theory = safe_list(analysis.get("theory_lenses"))
    layer_lines = []
    mapping = {
        "emotion": ["texture", "compression", "drift", "granularity"],
        "narrative": ["story_pattern", "psychological_atmosphere", "inner_rewrite"],
        "contradiction": ["detected", "internal_conflict", "meta_awareness"],
        "relationship": ["pattern", "approach_withdrawal", "social_exhaustion"],
        "symbolic": ["density", "objects", "archetype_detection"],
        "existential": ["meaning", "identity", "direction"],
        "safety_ethics": ["crisis_level", "crisis_context", "needs_gentle_check", "parasocial_risk"],
        "dynamic_tone": ["tempo", "reflection_depth", "silence_engine", "warmth_calibration"],
    }
    for name, keys in mapping.items():
        data = safe_dict(layers.get(name))
        bits = [f"{k}={data.get(k)}" for k in keys if data.get(k) not in [None, "", [], {}]]
        if bits:
            layer_lines.append(f"- {name}: " + "; ".join(bits))

    policy = safe_dict(analysis.get("response_policy"))
    if policy:
        mix = safe_dict(policy.get("cultural_mix"))
        layer_lines.append(
            "- response_policy: "
            f"spontaneity={policy.get('spontaneity_label', 'orta')}; "
            f"pacing={policy.get('pacing', 'orta')}; "
            f"followup_question_count={policy.get('followup_question_count', 1)}; "
            f"ambiguity_tolerance={round(safe_float(policy.get('ambiguity_tolerance', 0.55)), 2)}; "
            f"warmth={policy.get('warmth_label', 'orta')}; "
            f"register_mix(silence={round(safe_float(mix.get('japan_silence', 0.5)), 2)}, "
            f"implicitness={round(safe_float(mix.get('turkish_imply', 0.5)), 2)}, "
            f"directness={round(safe_float(mix.get('german_direct', 0.5)), 2)}, "
            f"warmth={round(safe_float(mix.get('latin_warmth', 0.5)), 2)})"
        )

    theory_names = ", ".join([x.get("name", "") for x in theory[:5] if x.get("name")]) or "yok"
    active_layers = ", ".join(digest.get("active_layers", []) or []) or "henüz zayıf"
    return "\n".join(layer_lines + [
        f"- aktif arka plan lensleri: {theory_names}",
        f"- biriken aktif katmanlar: {active_layers}",
    ])


def istanbul_now() -> datetime:
    return datetime.now(ISTANBUL_TZ)


def location_for_prompt(raw_location: str) -> str:
    loc = str(raw_location or "").strip()
    if not loc:
        return "Konum paylaşılmadı"
    low = loc.lower()
    if low in {"istanbul", "i̇stanbul"}:
        return "Türkiye İstanbul"
    if "konum paylaşılmadı" in low or "paylasilmadi" in low or "bilinmiyor" in low:
        return "Konum paylaşılmadı"
    return loc


def build_system_prompt(
    profile: Dict[str, Any],
    analysis: Dict[str, Any],
    mode: str,
    memory_snippets: List[str],
    digest: Dict[str, Any],
    location: str = "Konum paylaşılmadı",
    runtime_hints: Optional[List[str]] = None,
) -> str:
    memory_block = "\n".join(f"- {s}" for s in memory_snippets[:5]) if memory_snippets else "- Belirgin geri çağırma yok."
    layer_block = build_layer_prompt_summary(analysis, digest)
    identity_memory = safe_dict(profile.get("identity_memory"))
    preferred_name = normalize_identity_name(str(identity_memory.get("preferred_name", "")))
    identity_confidence = str(identity_memory.get("confidence", "none")).strip().lower()
    rejected_names = [
        normalize_identity_name(str(x))
        for x in safe_list(identity_memory.get("rejected_names"))
        if normalize_identity_name(str(x))
    ]
    if preferred_name and identity_confidence == "explicit":
        identity_block = (
            "KİMLİK / HİTAP GÜVENLİĞİ:\n"
            f"- Kullanıcı açıkça şu hitabı verdi: {preferred_name}\n"
            "- Bu isim yalnızca doğal gelirse kullanılabilir; her cevapta tekrar etme.\n"
        )
    else:
        identity_block = (
            "KİMLİK / HİTAP GÜVENLİĞİ:\n"
            "- Kullanıcının adı veya nickname'i açıkça verilmiş değil.\n"
            "- Belirsiz isimleri, üçüncü kişi adlarını, sanatçı/arkadaş/örnek/referans isimlerini kullanıcı adı sayma.\n"
            "- Örnek: 'selam burak kut', 'Burak geldi', 'Mehmet'e mesaj yaz', 'CV'de Burak referans olsun' kullanıcı adı değildir.\n"
            "- Emin değilsen kullanıcıya isimle hitap etme.\n"
        )
    if rejected_names:
        identity_block += "- Reddedilmiş hitaplar kullanıcı adı değildir; bu adlarla kullanıcıya seslenme.\n"
    policy = safe_dict(analysis.get("response_policy"))
    mix = safe_dict(policy.get("cultural_mix"))
    policy_block = (
        ""
        if not policy
        else (
            "CANLI YANIT KALIBRASYONU:\n"
            f"- spontaneite: {policy.get('spontaneity_label', 'orta')}\n"
            f"- pacing: {policy.get('pacing', 'orta')}\n"
            f"- takip sorusu: {policy.get('followup_question_count', 1)} adet\n"
            f"- belirsizlik toleransı: {round(safe_float(policy.get('ambiguity_tolerance', 0.55)), 2)}\n"
            f"- sıcaklık kalibrasyonu: {policy.get('warmth_label', 'orta')}\n"
            f"- register/ritim göstergeleri: silence={round(safe_float(mix.get('japan_silence', 0.5)), 2)}, "
            f"implicitness={round(safe_float(mix.get('turkish_imply', 0.5)), 2)}, "
            f"directness={round(safe_float(mix.get('german_direct', 0.5)), 2)}, "
            f"warmth={round(safe_float(mix.get('latin_warmth', 0.5)), 2)}\n"
            "- Kullanıcıya skor gösterme; bu sinyaller sadece ton, ritim, soru derinliği ve empatiyi ayarlasın.\n"
            "- Asla klinik tanı, tedavi, ilaç, dini/fal dili veya kesin yargı kullanma.\n"
        )
    )

    now_local = istanbul_now()
    current_datetime = now_local.strftime("%d.%m.%Y saat : %H:%M")
    current_hour = now_local.hour
    location_line = location_for_prompt(location)

    if 5 <= current_hour < 11:
        time_context = "Sabah. Günaydın."
    elif 11 <= current_hour < 18:
        time_context = "Öğle / gündüz. İyi günler."
    elif 18 <= current_hour < 23:
        time_context = "Akşam. İyi akşamlar."
    else:
        time_context = "Gece. İyi geceler."

    base = f"""
GİZLİ KONTEXT (kullanıcıya otomatik yazma):
- Şu an: Bugün ({current_datetime}) / {time_context}
- Konum: {location_line}

Sen Luxviai'sin. Luxviai — Light your way! / Yolunu aydınlat!
Sen bir yapay zekâsın; bunu saklamazsın.
Ama robot gibi konuşmazsın: sıcak, sakin, güvenilir, net, içten ve derinsin.
Merkez her zaman insandır.

DİL:
Kullanıcı hangi dilde yazarsa o dilde cevap ver.
Türkçe yazım hatalarını veya tekrarları yabancı dil sanma.
- Kullanıcı sormadıkça saat/tarih/konum satırlarını otomatik yazma.
- Kullanıcı "selam/merhaba" dediğinde normal sohbet akışına devam et; her mesajda yeni karşılama cümlesi tekrar etme.
- Saat/tarih gerektiğinde şu şık formatı kullan: Bugün (29.05.2026 saat : 11:15)
- Konum gerekiyorsa şu formatı kullan: Konum : Türkiye İstanbul
- Saat/tarih/konum satırlarında kalın yazı, markdown yıldızı (**) veya emoji kullanma.

KARAKTER:
- modern, premium ve sade; gösterişsiz ama zeki
- sıcak ama yapışkan değil; insancıl ama insan olduğunu iddia etmez
- duygusal farkındalığı var ama terapi dili kurmaz
- teknik konularda direkt ve net; sohbette doğal; rüyada eşlikçi; kararda berraklaştırıcı
- az veriden büyük sonuç çıkarmaz; her cevabı soru ile bitirmez
- DeepSeek'in cevabının özünü boğma; sadece hafif Lux ritmi ekle

SINIR:
- tanı koyma
- tedavi iddiasında bulunma
- ilaç önerme
- klinik etiket yapıştırma
- fal / kehanet / dini tabir kullanma
- kullanıcının mahremiyetini sömürme
- teorisyen adı sayma; arka plan lenslerini kullanıcıya doğrudan gösterme
- insan, bilinç veya gerçek duygu iddiası kurma
- romantik bağımlılık dili kurma
- teknik soruları metaforlaştırma

CİDDİ DURUMLAR:
Kendine zarar, intihar, şiddet, istismar kelimeleri geçerse bağlama bak.
Geçmiş anlatım, haber, film, soru veya kavramsal konuşmaysa normal sohbet et.
Anlık yardım isteği, plan, şu an güvende olmama veya kendine zarar niyeti varsa analiz yapma.
Çok kısa, çok sıcak ve net yönlendir:
112'yi ara, en yakın acile git, güvendiğin birine haber ver.

YANIT MİMARİSİ:
1. Önce niyeti ayırt et: teknik/utility, normal sohbet, duygu/ilişki, rüya, karar/ikilem, kriz/safety, proje/kod, özet/hafıza.
2. Teknikse kısa, net ve uygulanabilir cevap ver; metafor ve terapi dili kullanma.
3. Normal sohbette doğal kal; gereksiz analiz, zorunlu içgörü veya her cevapta soru yok.
4. Duygusal konuda sıcak ama klinik olmayan dil kullan; kullanıcıyı etiketleme.
5. Rüyada kesin anlam verme; karar/ikilemde önce berraklaştır; sembolik okumayı kullanıcı isterse aç.
6. Half-Step'i serbest seç: kısa gözlem, seçenek, doğal duraklama, mini netleştirme, next action, tek soru veya hiçbir ek soru.

NATURAL HALF-STEP:
- Her cevabın sonu soru olmak zorunda değil.
- Sohbeti kapatmayan ama kullanıcıyı zorlamayan yarım adım kullan:
  kısa gözlem / seçenek / mini netleştirme / sakin duraklama.
- Teknik/utility mesajlarda metaforik veya terapötik dil kullanma; doğrudan net teknik yanıt ver.
- Kullanıcı düzeltirse kısa kabul et, savunmaya geçme, asıl konuya dön.
- Asistan kendi yazım hatasını kullanıcıya atfetme.

BİÇİM:
- Paragraflar kısa olsun
- Gerektiğinde liste kullan
- Tek blok halinde sıkıştırma
- Gereksiz teknik dil kullanma

HAFIZA İPUÇLARI:
{memory_block}

{identity_block}

ARKA PLAN ANALİZİ:
Bu bölüm kullanıcıya doğrudan gösterilmez; sadece tonu, ritmi, soru derinliğini ve hafıza çağrışımını ayarlar.
{layer_block}

{policy_block}
"""
    runtime_hints = [str(x).strip() for x in (runtime_hints or []) if str(x).strip()]
    if runtime_hints:
        base += "\nANLIK NİYET KILAVUZU:\n" + "\n".join(f"- {h}" for h in runtime_hints[:6]) + "\n"

    mode_block = "\n[AKTİF MOD]\n"
    if mode == "luxviai":
        mode_block += "- Dengeli, sıcak ve net kal.\n"
    elif mode == "luxching":
        mode_block += "- LUXCHING artık arka plan sembolik lens olarak çalışır; zorunlu format yok.\n"
    elif mode == "luxdream":
        mode_block += "- Rüya yorumu, imgeler, çağrışımlar.\n- Psikanalitik çerçeve, kesinlik yok.\n"
    elif mode == "luxta":
        mode_block += "- Çok dinle, az konuş.\n- En fazla 1-2 kısa cümle ver.\n- Çözüm üretme; eşlik et.\n"
    elif mode == "luxeph":
        mode_block += "- Kayıt yok, iz yok.\n- Geçici, güvenli alan.\n- Normal AI yanıtı üret ama geçmiş hafızaya yaslanma.\n"

    if analysis.get("needs_silence"):
        mode_block += "- Bu anda suskunluk da bir cevap olabilir; uzun açıklama yapma.\n"
    if analysis.get("needs_presence"):
        mode_block += "- Öncelik duyulmak. Çözüm önce gelmesin.\n"
    if analysis.get("needs_solution"):
        mode_block += "- Çok küçük, tek adımlık bir öneri ekleyebilirsin.\n"
    if safe_dict(analysis.get("safety_layer")).get("needs_gentle_check"):
        mode_block += "- Kriz kelimesi belirsiz bağlamda geçti; panik yaratmadan, kısa bir güvenlik yoklaması yap.\n"

    if policy:
        mode_block += (
            f"- Yanit temposu {policy.get('pacing', 'orta')} olsun; akisi blok halinde patlatma.\n"
            f"- Gerekirse en fazla {policy.get('followup_question_count', 1)} adet acik uclu takip sorusu ekleyebilirsin; soru zorunlu degil.\n"
            "- Belirsizlik toleransini koru; kesin hukumlerden kacin.\n"
            f"- Sicaklik tonunu {policy.get('warmth_label', 'orta')} seviyede tut.\n"
        )

    return base + mode_block


def fallback_reply(mode: str, analysis: Dict[str, Any]) -> str:
    if mode == "luxta":
        return random.choice(LUXTA_REPLIES)
    if mode == "luxeph":
        return "Buradayım. Bunu bu anın içinde, kayıt tutmadan sadeleştirebiliriz."
    if mode == "luxching":
        return "Bunu fal gibi değil, kararın içindeki dengeyi görmek için kısa ve sembolik okuyabiliriz."
    if mode == "luxdream":
        return "Rüyayı kesin anlamlara zorlamadan, sahne ve duygusuyla yavaşça açabiliriz."
    return "Anladım. Bunu fazla büyütmeden, net ve sakin şekilde birlikte toparlayabiliriz."


def crisis_reply() -> str:
    return (
        "Şu an bunu tek başına taşımaman önemli. "
        "Lütfen hemen güvendiğin birine haber ver ve 112'yi ara ya da en yakın acile git. "
        "Buradayım, ama bu kısmı gerçek bir insan desteğiyle birlikte tutman gerekiyor."
    )


def build_openai_messages(session: Dict[str, Any], prompt: str) -> List[Dict[str, str]]:
    tail = session.get("messages", [])[-18:]
    messages = [{"role": "system", "content": prompt}]
    for m in tail:
        if m.get("role") in {"user", "assistant"} and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    return messages


def safe_token_budget_decision(
    message: str,
    mode: str,
    analysis: Optional[Dict[str, Any]] = None,
    count_constraints: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    try:
        return token_budget_policy.classify(
            message=message or "",
            mode=mode or "luxviai",
            analysis=analysis or {},
            count_constraints=count_constraints or [],
        ).to_safe_dict()
    except Exception:
        return {
            "budget_class": "normal_chat",
            "observe_only": True,
            "active": False,
            "route_reason": "policy_fallback",
            "task_type": "chat",
            "safety_level": "normal",
            "count_constraint_present": bool(count_constraints),
            "cache_hint": "none",
            "version": "token_budget_policy_fallback",
        }


def history_metrics_from_messages(messages: List[Dict[str, str]]) -> tuple[int, int]:
    history = [m for m in safe_list(messages)[1:] if isinstance(m, dict)]
    return (
        len(history),
        sum(len(str(m.get("content", ""))) for m in history),
    )


def count_low_conf_suppressed(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        for key, item in value.items():
            key_text = str(key).lower()
            if isinstance(item, dict):
                summary = str(item.get("safe_summary", "")).lower()
                reason = str(item.get("suppression_reason", "")).lower()
                if "low_conf" in summary or reason == "low_confidence" or bool(item.get("low_confidence_suppressed")):
                    count += 1
                count += count_low_conf_suppressed(item)
            elif isinstance(item, list):
                count += count_low_conf_suppressed(item)
            elif "low_conf" in key_text and bool(item):
                count += 1
        return count
    if isinstance(value, list):
        return sum(count_low_conf_suppressed(x) for x in value)
    return 0


def practical_support_candidate_count(learning_context: Dict[str, Any]) -> int:
    practical = safe_dict(learning_context.get("practical_support_meta"))
    if practical:
        return clamp_int(practical.get("candidate_count"), 0, 100, 0)
    return 0


def selected_layer_count(learning_context: Dict[str, Any]) -> int:
    count = 0
    for key in [
        "group1_layer_signals",
        "group2_layer_signals",
        "group3_bundle",
        "group4_bundle",
        "micro_human_bridge_meta",
        "lux_language_sense_meta",
        "practical_support_meta",
        "human_risk",
    ]:
        value = learning_context.get(key)
        if isinstance(value, dict) and value:
            count += 1
    return count


def safety_level_from_plan(plan: Dict[str, Any]) -> str:
    budget = safe_dict(plan.get("token_budget"))
    if budget.get("safety_level"):
        return str(budget.get("safety_level"))
    safety = safe_dict(safe_dict(plan.get("analysis")).get("safety_layer"))
    if safe_dict(plan.get("analysis")).get("crisis_risk") or safety.get("route_to_emergency"):
        return "crisis"
    if safety.get("needs_gentle_check") or safety.get("has_crisis_keyword"):
        return "sensitive"
    return str(safety.get("crisis_level", "normal") or "normal")


def safe_efficiency_dry_run(
    plan: Dict[str, Any],
    *,
    mode: str = "luxviai",
    prompt_chars: int = 0,
    context_chars: int = 0,
    history_message_count: int = 0,
    history_chars: int = 0,
) -> Dict[str, Any]:
    try:
        learning_context = safe_dict(plan.get("learning_context"))
        decision = efficiency_router.dry_run(
            message=str(plan.get("message", "")),
            mode=mode or str(plan.get("mode", "luxviai")),
            analysis=safe_dict(plan.get("analysis")),
            token_budget=safe_dict(plan.get("token_budget")),
            count_constraints=safe_list(plan.get("count_constraints")),
            identity_boundary=str(plan.get("identity_boundary", "")),
            prompt_chars=prompt_chars,
            context_chars=context_chars,
            history_message_count=history_message_count,
            history_chars=history_chars,
            context_item_count=len(safe_list(learning_context.get("context_items"))),
            selected_layer_count=selected_layer_count(learning_context),
        )
        data = decision.to_safe_dict()
        data.update(decision.shadow_compare(context_chars))
        return data
    except Exception:
        return {
            "efficiency_dry_run_route": "full_current_path",
            "would_use_short_context": False,
            "would_limit_history_to_last_n": 18,
            "would_skip_group3": False,
            "would_skip_group4": False,
            "would_skip_long_memory": False,
            "would_keep_safety": True,
            "would_keep_identity_guard": True,
            "would_keep_count_guard": True,
            "estimated_context_savings_chars": 0,
            "estimated_layer_savings_count": 0,
            "efficiency_dry_run_confidence": 0.0,
            "route_reason": "efficiency_router_fallback",
            "mandatory_guards_kept": "safety,identity,count,basic_command,cost_logging",
            "shadow_compare_enabled": False,
            "shadow_compare_route": "full_current_path",
            "shadow_compare_summary": {
                "route": "full_current_path",
                "would_keep": ["safety", "identity_guard", "count_guard", "basic_command_intent"],
                "would_limit_history_to": 18,
                "would_skip": [],
                "estimated_saved_chars": 0,
                "confidence": 0.0,
            },
            "current_context_chars": context_chars,
            "proposed_context_chars": context_chars,
            "estimated_saved_chars": 0,
            "proposed_history_limit": 18,
            "proposed_skipped_layers": [],
            "reason_tags": ["full_current_path", "efficiency_router_fallback"],
            "context_injected": False,
            "active": False,
            "version": "efficiency_router_fallback",
        }


def record_cost_event(
    *,
    endpoint: str,
    route: str,
    plan: Optional[Dict[str, Any]] = None,
    mode: str = "luxviai",
    model: str = "",
    prompt_chars: int = 0,
    context_chars: int = 0,
    history_message_count: int = 0,
    history_chars: int = 0,
    max_tokens: int = 0,
    finish_reason: str = "",
    auto_continue_parts: int = 0,
    model_ms: int = 0,
    first_chunk_ms: Optional[int] = None,
    total_ms: int = 0,
    response_text: str = "",
    success: bool = True,
    error_type: str = "",
) -> None:
    plan = plan or {}
    learning_context = safe_dict(plan.get("learning_context"))
    budget = safe_dict(plan.get("token_budget")) or safe_token_budget_decision(
        str(plan.get("message", "")),
        mode,
        safe_dict(plan.get("analysis")),
        safe_list(plan.get("count_constraints")),
    )
    context_items = safe_list(learning_context.get("context_items"))
    estimated_output_tokens = estimate_tokens(len(str(response_text or "")))
    efficiency = safe_efficiency_dry_run(
        plan,
        mode=mode or str(plan.get("mode", "luxviai")),
        prompt_chars=prompt_chars,
        context_chars=context_chars,
        history_message_count=history_message_count,
        history_chars=history_chars,
    )
    cost_logger.record(
        route=route,
        endpoint=endpoint,
        mode=mode or str(plan.get("mode", "luxviai")),
        model=model or str(plan.get("model", "")),
        budget_class=str(budget.get("budget_class", "normal_chat")),
        observe_only=bool(budget.get("observe_only", True)),
        policy_active=bool(budget.get("active", False)),
        prompt_chars=prompt_chars,
        context_chars=context_chars,
        history_chars=history_chars,
        system_template_version="lux_system_prompt_v1",
        history_message_count=history_message_count,
        context_item_count=len(context_items),
        selected_layer_count=selected_layer_count(learning_context),
        low_conf_suppressed_count=count_low_conf_suppressed(learning_context),
        max_tokens=max_tokens,
        finish_reason=finish_reason,
        auto_continue_parts=auto_continue_parts,
        model_ms=model_ms,
        first_chunk_ms=first_chunk_ms,
        total_ms=total_ms,
        repair_call_count=clamp_int(plan.get("count_repair_call_count"), 0, 10, 0),
        count_guard_active=bool(safe_list(plan.get("count_constraints"))),
        safety_suppressed=safety_level_from_plan(plan) in {"sensitive", "high_risk", "crisis"},
        route_reason=str(budget.get("route_reason", "")),
        intent_bucket=str(budget.get("budget_class", "normal_chat")),
        task_type=str(budget.get("task_type", "")),
        count_constraint_present=bool(budget.get("count_constraint_present", False)),
        safety_level=safety_level_from_plan(plan),
        memory_recall_bucket="present" if safe_list(plan.get("memory_preview")) else "none",
        project_topic_hash="none",
        prompt_char_count=prompt_chars,
        practical_support_candidate_count=practical_support_candidate_count(learning_context),
        estimated_output_tokens=estimated_output_tokens,
        cache_hint=str(budget.get("cache_hint", "none")),
        cache_status="unavailable",
        efficiency_dry_run_route=str(efficiency.get("efficiency_dry_run_route", "full_current_path")),
        efficiency_dry_run_confidence=efficiency.get("efficiency_dry_run_confidence", 0.0),
        would_use_short_context=bool(efficiency.get("would_use_short_context", False)),
        estimated_context_savings_chars=clamp_int(efficiency.get("estimated_context_savings_chars"), 0, 1000000, 0),
        estimated_layer_savings_count=clamp_int(efficiency.get("estimated_layer_savings_count"), 0, 100, 0),
        mandatory_guards_kept=str(efficiency.get("mandatory_guards_kept", "")),
        shadow_compare_enabled=bool(efficiency.get("shadow_compare_enabled", False)),
        shadow_compare_route=str(efficiency.get("shadow_compare_route", "")),
        shadow_compare_summary=efficiency.get("shadow_compare_summary", {}),
        current_context_chars=clamp_int(efficiency.get("current_context_chars"), 0, 1000000, 0),
        proposed_context_chars=clamp_int(efficiency.get("proposed_context_chars"), 0, 1000000, 0),
        estimated_saved_chars=clamp_int(efficiency.get("estimated_saved_chars"), 0, 1000000, 0),
        proposed_history_limit=clamp_int(efficiency.get("proposed_history_limit"), 0, 100, 18),
        proposed_skipped_layers=safe_list(efficiency.get("proposed_skipped_layers")),
        reason_tags=safe_list(efficiency.get("reason_tags")),
        success=success,
        error_type=error_type,
    )


def choose_generation_params(mode: str, analysis: Dict[str, Any]) -> tuple[str, float, int]:
    intensity = clamp_int(analysis.get("intensity", 5), 1, 10, 5)
    policy = safe_dict(analysis.get("response_policy"))
    spontaneity = clamp_float(policy.get("spontaneity"), 0.0, 1.0, 0.45)
    pacing = str(policy.get("pacing", "orta"))
    temp_shift = (spontaneity - 0.45) * 0.2

    if mode == "luxta":
        return ("deepseek-chat", clamp_float(0.22 + temp_shift * 0.3, 0.15, 0.35, 0.25), 180)
    if mode == "luxeph":
        return ("deepseek-chat", clamp_float(0.42 + temp_shift * 0.4, 0.3, 0.58, 0.45), 520)
    if mode in {"luxdream", "luxching"} or intensity >= 8:
        tokens = 1050 if pacing == "akışkan" else 950
        return ("deepseek-chat", clamp_float(0.62 + temp_shift, 0.5, 0.75, 0.65), tokens)
    tokens = 760 if pacing == "yavaş" else 920 if pacing == "akışkan" else 840
    return ("deepseek-chat", clamp_float(0.52 + temp_shift, 0.42, 0.64, 0.55), tokens)


def requested_long_answer_token_floor(message: str) -> int:
    low = (message or "").lower()
    long_form_words = [
        "madde", "başlık", "baslik", "item", "section", "bölüm", "bolum", "liste",
        "paragraf", "paragraph", "slayt", "slide", "seçenek", "secenek", "option",
        "cümle", "cumle", "sentence",
    ]
    counts = [int(x) for x in re.findall(r"\d{1,3}", low)] if any(w in low for w in long_form_words) else []
    if not counts and any(k in low for k in ["kısa", "kisa", "özet", "ozet", "tek cümle", "tek cumle"]):
        return 0
    if not counts:
        return 0
    requested = max(counts)
    if requested >= 50:
        return 4200
    if requested >= 20:
        return 2400
    if requested >= 10:
        return 1600
    return 0


def count_safe_max_tokens(plan: Dict[str, Any], minimum: int = 700) -> int:
    requested = requested_long_answer_token_floor(str(plan.get("message", "")))
    configured = clamp_int(plan.get("max_tokens"), 0, 100000, 0)
    constraints = safe_list(plan.get("count_constraints"))
    target_floor = 0
    for constraint in constraints:
        kind = str(constraint.get("kind", ""))
        if kind == "word":
            continue
        target = clamp_int(constraint.get("target"), 1, 300, 1)
        if target >= 50:
            target_floor = max(target_floor, 4200)
        elif target >= 20:
            target_floor = max(target_floor, 2400)
        elif target >= 10:
            target_floor = max(target_floor, 1600)
    return max(minimum, configured, requested, target_floor)


def auto_continuation_part_limit(plan: Dict[str, Any]) -> int:
    constraints = safe_list(plan.get("count_constraints"))
    max_target = 0
    for constraint in constraints:
        if str(constraint.get("kind", "")) != "word":
            max_target = max(max_target, clamp_int(constraint.get("target"), 1, 300, 1))
    if max_target >= 50:
        return 4
    if max_target >= 20:
        return 3
    return 2


def auto_continuation_max_tokens(plan: Dict[str, Any]) -> int:
    return min(max(count_safe_max_tokens(plan, minimum=900), 900), 2400)


def normalize_overlap_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).replace('"', "").replace("'", "").strip()


def append_merged_text(base: str, addition: str) -> str:
    if not addition:
        return base
    if not base:
        return addition
    if re.match(r"^\s*(?:[-*•]|\d+[\.)])\s+", addition) and re.search(r"(?:^|\n)\s*(?:[-*•]|\d+[\.)])\s+", base):
        return base.rstrip() + "\n" + addition.lstrip()
    if base[-1:].isspace() or addition[:1].isspace() or addition[:1] in ".,;:!?)]":
        return base + addition
    return base + " " + addition


def trim_repeated_continuation_start(base_text: str, incoming_text: str) -> str:
    base = str(base_text or "")
    incoming = str(incoming_text or "")
    if not base or not incoming:
        return incoming

    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", base) if s.strip()]
    for count in range(min(2, len(sentences)), 0, -1):
        tail = " ".join(sentences[-count:])
        if len(tail) >= 12 and normalize_overlap_text(incoming).startswith(normalize_overlap_text(tail)):
            return incoming[len(tail):].lstrip()

    base_words = list(re.finditer(r"\S+", base))
    incoming_words = list(re.finditer(r"\S+", incoming))
    for count in range(min(28, len(base_words), len(incoming_words)), 1, -1):
        left = " ".join(normalize_overlap_text(m.group(0)) for m in base_words[-count:])
        right = " ".join(normalize_overlap_text(m.group(0)) for m in incoming_words[:count])
        if left and left == right:
            return incoming[incoming_words[count - 1].end():].lstrip()
    return incoming


def merge_continuation_text(base_text: str, incoming_text: str) -> str:
    base = str(base_text or "")
    incoming = str(incoming_text or "")
    if not incoming:
        return base
    if not base:
        return incoming
    if incoming.startswith(base):
        return incoming

    for size in range(min(len(base), len(incoming)), 3, -1):
        if base[-size:] == incoming[:size]:
            return append_merged_text(base, incoming[size:])

    probe = min(20, len(base), len(incoming))
    if probe >= 8 and base[:probe].lower() == incoming[:probe].lower():
        return incoming if len(incoming) >= len(base) else base

    base_words = [normalize_overlap_text(x.group(0)) for x in re.finditer(r"\S+", base)]
    incoming_words = [normalize_overlap_text(x.group(0)) for x in re.finditer(r"\S+", incoming)]
    if len(base) <= 80 and base_words[:2] and base_words[:2] == incoming_words[:2] and len(incoming) > len(base):
        return incoming
    return append_merged_text(base, trim_repeated_continuation_start(base, incoming))


def looks_incomplete_response(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    return stripped[-1] not in ".!?…):]»”\"'"


def build_continuation_messages(messages: List[Dict[str, str]], partial_text: str) -> List[Dict[str, str]]:
    return messages + [
        {"role": "assistant", "content": partial_text},
        {
            "role": "user",
            "content": (
                "Devam et. Önceki metni tekrar etme; kaldığın yerden sürdür. "
                "Başlığı veya son cümleyi yeniden yazma. Cevabı doğal şekilde tamamla."
            ),
        },
    ]


def build_guarded_continuation_messages(
    messages: List[Dict[str, str]],
    partial_text: str,
    constraints: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    prompt = (
        "Devam et. Önceki metni tekrar etme; kaldığın yerden sürdür. "
        "Başlığı veya son cümleyi yeniden yazma. Cevabı doğal şekilde tamamla."
    )
    if constraints:
        status = []
        for constraint in constraints:
            kind = str(constraint.get("kind", ""))
            target = clamp_int(constraint.get("target"), 1, 300, 1)
            actual = count_constraint_units(partial_text, constraint)
            label = COUNT_UNIT_LABELS.get(kind, kind)
            status.append(f"{actual}/{target} {label}")
        prompt += (
            " Sayı/format guard aktif: mevcut taslak "
            + ", ".join(status)
            + ". Sadece eksik birimleri tamamla; hedefe ulaşıldıysa veya hedef geçildiyse yeni metin ekleme. "
            "Numaralı/listeli çıktıdaysan bir sonraki eksik numaradan başla, 1'den yeniden başlama."
        )
    return messages + [
        {"role": "assistant", "content": partial_text},
        {"role": "user", "content": prompt},
    ]


def should_auto_continue_response(finish_reason: str, response_text: str, plan: Dict[str, Any]) -> bool:
    if plan.get("kind") != "model" or plan.get("skip_save"):
        return False
    if (plan.get("mode") or "") in {"luxta", "luxeph"}:
        return False
    constraints = safe_list(plan.get("count_constraints"))
    if constraints:
        missing = incomplete_exact_count_constraints(response_text, constraints)
        if missing:
            return True
        for constraint in [c for c in constraints if c.get("kind") != "word"]:
            target = clamp_int(constraint.get("target"), 1, 300, 1)
            if count_constraint_units(response_text, constraint) >= target:
                return False
    message = str(plan.get("message", "")).lower()
    if not requested_long_answer_token_floor(message) and any(k in message for k in ["kısa", "kisa", "özet", "ozet", "tek cümle", "tek cumle"]):
        return False
    if finish_reason == "length":
        return True
    if requested_long_answer_token_floor(message) and looks_incomplete_response(response_text):
        return True
    return False


def call_model(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    text, _ = call_model_with_finish(messages, model, temperature, max_tokens)
    return text


def call_model_with_finish(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int) -> tuple[str, str]:
    if not client:
        raise RuntimeError("DeepSeek API key missing")

    api_start = perf_counter()
    prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        return (choice.message.content or "").strip(), str(getattr(choice, "finish_reason", "") or "")
    finally:
        log_latency(
            "model_call",
            api_ms=ms_since(api_start),
            messages=len(messages),
            prompt_chars=prompt_chars,
            model=model,
            max_tokens=max_tokens,
        )


def stream_model(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int):
    if not client:
        raise RuntimeError("DeepSeek API key missing")

    api_start = perf_counter()
    first_chunk_ms = None
    prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for part in stream:
            try:
                choice = part.choices[0]
                chunk = choice.delta.content or ""
                if chunk:
                    if first_chunk_ms is None:
                        first_chunk_ms = ms_since(api_start)
                    yield {"text": chunk, "finish_reason": ""}
                finish_reason = str(getattr(choice, "finish_reason", "") or "")
                if finish_reason:
                    yield {"text": "", "finish_reason": finish_reason}
            except Exception:
                continue
    finally:
        log_latency(
            "model_stream",
            api_ms=ms_since(api_start),
            first_chunk_ms=first_chunk_ms,
            messages=len(messages),
            prompt_chars=prompt_chars,
            model=model,
            max_tokens=max_tokens,
        )


def generate_session_summary(session: Dict[str, Any]) -> str:
    msgs = session.get("messages", [])[-18:]
    user_texts = [m.get("content", "") for m in msgs if m.get("role") == "user"]
    if not msgs or len(user_texts) < 1:
        return "Henüz yeterli konuşma yok."

    keywords = top_keywords(user_texts, 8)

    if client and len(user_texts) >= 2:
        try:
            prompt = (
                "Sadece bu aktif konuşmayı özetle. "
                "2 kısa paragraf yaz. "
                "Sonunda 'Başlıca kelimeler:' ve 'Başlıca cümleler:' alanları ekle. "
                "Skor, tanı, klinik etiket kullanma. "
                "Kullanıcının cümlesini birebir kopyalama; tekrar eden ham kelimeler yerine kavram yaz "
                "(ör. 'yeni iş', 'başarı', 'ilişki gerilimi')."
            )
            model_text = call_model(
                [{"role": "system", "content": prompt}] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in msgs
                    if m.get("role") in {"user", "assistant"} and m.get("content")
                ],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=320,
            )
            kw_line = "Başlıca kelimeler: " + (", ".join(keywords) if keywords else "Henüz belirgin değil")
            if "Başlıca kelimeler:" in model_text:
                model_text = re.sub(
                    r"Başlıca kelimeler:.*?(?:\n|$)",
                    kw_line + "\n",
                    model_text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            else:
                model_text = model_text.rstrip() + "\n\n" + kw_line
            return model_text.strip()
        except Exception as e:
            logging.warning(f"Session summary fallback: {e}")

    return (
        "Bu konuşmada şu an kısa ama anlamlı bir iz oluştu.\n\n"
        "Başlıca kavramlar: " + (", ".join(keywords) if keywords else "Henüz belirgin değil") + "\n"
        "Kısa özet: Konuşma ana olarak bu kavramların etrafında dönüyor."
    )


def generate_luxdream(dream_text: str, profile: Dict[str, Any], session: Dict[str, Any]) -> str:
    if not client:
        return (
            "Rüyadaki imgeleri birlikte yavaşça açabiliriz. "
            "İstersen en güçlü sahneyi, en baskın duyguyu ve uyandığında kalan hissi yaz."
        )

    analysis = heuristic_analysis(dream_text, profile, session, symbolic_location(profile), False)
    dream_prompt = f"""
Kullanıcı bir rüya anlattı.

Rüya metni:
\"\"\"{dream_text}\"\"\"

Yöntem:
1. Ana imgeleri, figürleri, nesneleri ve duyguları ayıkla.
2. Freud / Jung / Lacan / Hillman / Bachelard çizgisinde kısa bir sembolik çerçeve kur.
3. Kesin yorum verme; "olabilir", "çağrıştırıyor olabilir" gibi bir dil kullan.
4. Sonunda rüyayı derinleştirecek 2-3 yumuşak soru sor.
5. Fal, kehanet, dini tabir, tanı dili kullanma.
"""
    return call_model(
        [
            {
                "role": "system",
                "content": build_system_prompt(
                    profile,
                    analysis,
                    "luxdream",
                    [dream_text[:250]],
                    profile.get("weekly_report", {}),
                    symbolic_location(profile),
                ),
            },
            {"role": "user", "content": dream_prompt},
        ],
        model="deepseek-chat",
        temperature=0.6,
        max_tokens=700,
    )


def generate_luxching(profile: Dict[str, Any], analysis: Dict[str, Any], intention: str = "") -> str:
    symbol = random.choice(LUXCHING_SYMBOLS)
    emotion = analysis.get("primary_emotion", "nötr")
    theme = profile.get("core_trigger", analysis.get("theme", "belirsiz")) or "belirsiz"
    layers = safe_dict(analysis.get("layers"))
    relationship = safe_dict(layers.get("relationship")).get("pattern", "belirsiz bir ilişki ritmi")
    symbolic = safe_dict(layers.get("symbolic")).get("archetype_detection", "belirsiz")

    return (
        "LUXCHING\n\n"
        f"Sembol: {symbol['name']}\n"
        f"Klasik anlam: {symbol['meaning']}\n\n"
        f"Kişisel bağlam: Arka planda {emotion} duygusu ve “{theme}” teması görünür gibi. "
        f"İlişki ritmi {relationship}; sembolik iz ise {symbolic} tarafına yakın duruyor.\n\n"
        "Bu bir fal değil; sadece sembolik bir ayna.\n\n"
        "Bu bağlantı sende nasıl bir his uyandırdı?"
    )


def symbolic_location(profile: Dict[str, Any]) -> str:
    eco = safe_dict(profile.get("ecological_context"))
    locations = safe_dict(eco.get("locations"))
    if locations:
        return sorted(locations.items(), key=lambda kv: kv[1], reverse=True)[0][0]
    return "İstanbul"


# =========================================================
# COMMANDS / SEARCH
# =========================================================
def search_in_all(user_id: str, keyword: str) -> str:
    user_id = safe_user_id(user_id)
    session = load_current_session(user_id)
    profile, notes, garden = load_user_state(user_id)

    results: List[str] = []
    if not keyword:
        return "Aramak için bir kelime veya ifade yazmalısın."

    for i, msg in enumerate(session.get("messages", []), 1):
        content = msg.get("content", "")
        if keyword.lower() in content.lower():
            role = "Sen" if msg.get("role") == "user" else "Luxviai"
            results.append(f"{i}. {role}: {content}")

    for note in notes:
        text = note.get("text", "")
        if keyword.lower() in text.lower():
            results.append(f"Not: {text}")

    for item in garden:
        text = item.get("text", "")
        if keyword.lower() in text.lower():
            results.append(f"Yankı: {text}")

    if not results:
        return f"“{keyword}” için bir sonuç bulamadım."

    return "ARAMA SONUÇLARI\n\n" + "\n\n".join(results[:10])


def search_structured(user_id: str, keyword: str) -> Dict[str, Any]:
    user_id = safe_user_id(user_id)
    session = load_current_session(user_id)
    profile, notes, garden = load_user_state(user_id)
    keyword_low = (keyword or "").lower().strip()
    items = []
    if not keyword_low:
        return {"items": [], "count": 0}

    for msg in session.get("messages", []):
        content = msg.get("content", "")
        if keyword_low in content.lower():
            items.append({"source": "session", "role": msg.get("role"), "text": content, "ts": msg.get("ts", "")})
    for note in notes:
        text = note.get("text", "")
        if keyword_low in text.lower():
            items.append({"source": "note", "text": text, "ts": note.get("created_at", "")})
    for item in garden:
        text = item.get("text", "")
        if keyword_low in text.lower():
            items.append({"source": "memory", "text": text, "theme": item.get("theme"), "emotion": item.get("emotion"), "ts": item.get("ts", "")})
    return {"items": items[:30], "count": len(items), "profile_theme": profile.get("core_trigger")}


def get_command_response(user_id: str, message: str) -> Optional[str]:
    low = message.lower().strip()
    user_id = safe_user_id(user_id)
    profile, notes, garden = load_user_state(user_id)
    session = load_current_session(user_id)

    if low in ["!yardım", "!cmd:yardim"]:
        return (
            "Kullanabileceğin alanlar:\n\n"
            "!bilge\n"
            "!cmd:not_al: metin\n"
            "!notlar\n"
            "!notlari_sil\n"
            "!cmd:ara: kelime\n"
            "!sohbet_ozeti\n"
            "!farkindalik_ozeti\n"
            "!cmd:luxdream: rüya metni\n"
            "!cmd:luxching: soru\n"
            "!luxta_info"
        )

    if low in {"luxching nedir", "luxching ne", "luxching ne demek", "i ching nedir", "ı ching nedir"}:
        return (
            "Luxching bir fal değil; I Ching'in değişim ve denge fikrinden esinlenen sembolik bir karar aynasıdır. "
            "Geleceği söylemez, kararın içindeki zamanlama ve yön değişimini sembolik olarak görmeye yardım eder."
        )

    if low.startswith("!cmd:not_al:"):
        note = message.split("!cmd:not_al:", 1)[1].strip()
        if not note:
            return "Not almak için bir metin gerekli."
        notes.append({
            "id": uuid.uuid4().hex[:10],
            "text": note,
            "created_at": now_iso(),
        })
        notes[:] = notes[-300:]
        save_user_state(user_id, profile, notes, garden)
        return "Not alındı."

    if low in ["!notlar", "!cmd:notlar"]:
        if not notes:
            return "Henüz not yok."
        lines = []
        for i, n in enumerate(notes[-20:], 1):
            lines.append(f"{i}. {n.get('text', '')}")
        return "\n".join(lines)

    if low in ["!notlari_sil", "!cmd:notlari_sil"]:
        notes.clear()
        save_user_state(user_id, profile, notes, garden)
        return "Tüm notlar silindi."

    if low.startswith("!cmd:ara:"):
        keyword = message.split("!cmd:ara:", 1)[1].strip()
        return search_in_all(user_id, keyword)

    if low in ["!sohbet_ozeti", "!cmd:sohbet_ozeti"]:
        return generate_session_summary(session)

    if low in ["!farkindalik_ozeti", "!cmd:farkindalik_ozeti"]:
        digest = build_weekly_digest(profile, session, garden)
        return build_weekly_digest_text(digest)

    if low in ["!bilge", "!cmd:bilge"]:
        return random.choice([
            "Bazen en doğru cevap, önce biraz sessizliktir.",
            "Ağır bir cümle bazen uzun bir geçmiş taşır.",
            "Kendini anlamak, kendini zorlamadan da mümkündür.",
            "Bir hissi küçültmeden adlandırmak, onu daha taşınır kılar.",
        ])

    if low.startswith("!cmd:luxdream:"):
        dream = message.split("!cmd:luxdream:", 1)[1].strip()
        if not dream:
            return "Rüyanı yazabilirsin."
        return generate_luxdream(dream, profile, session)

    if low.startswith("!cmd:luxching:"):
        question_text = message.split("!cmd:luxching:", 1)[1].strip()
        if not is_luxching_question(question_text):
            return "Lütfen sorunuzu sorunuz."
        ok, limit_msg = check_luxching_limit(profile)
        if not ok:
            return (
                "Bugün Luxching katmanını zaten açtık. "
                "Onu hemen yenilemek yerine çıkan sembolü biraz taşıyalım. "
                "İstersen normal Lux akışıyla devam edebiliriz."
            )
        analysis = heuristic_analysis(question_text or message, profile, session)
        response = generate_luxching(profile, analysis, question_text)
        profile["luxching_last_used"] = now_iso()
        save_user_state(user_id, profile, notes, garden)
        return response

    if low in ["!luxta_info", "!cmd:luxta_info"]:
        return "Luxta modu: Çok dinler, az konuşur."

    return None


def is_luxching_question(message: str) -> bool:
    low = (message or "").lower().strip()
    if not low:
        return False

    trivial = {"merhaba", "selam", "hey", "hi", "test", "deneme", "ok", "tamam"}
    if low in trivial:
        return False

    tokens = tokenize(low)
    if len(tokens) < 3:
        return False

    question_words = (
        "neden", "niye", "nasıl", "ne", "hangi", "acaba", "sence", "mı", "mi", "mu", "mü"
    )
    if "?" in low:
        return True
    if any(w in low for w in question_words):
        return True
    return len(low) >= 24

# Timezone-safe override: keeps the same API but avoids naive/aware subtraction failures.
def check_luxching_limit(profile: Dict[str, Any]) -> tuple[bool, str]:
    last_used = profile.get("luxching_last_used")
    if not last_used:
        return True, ""
    try:
        last = datetime.fromisoformat(str(last_used).replace("Z", "+00:00"))
        if last.tzinfo is not None:
            now_same_tz = datetime.now(last.tzinfo)
            delta = now_same_tz - last
        else:
            delta = datetime.now() - last
        if delta < timedelta(hours=24):
            return False, "LUXCHING günde bir kez kullanılabilir. Lütfen yarın tekrar dene."
    except Exception:
        return True, ""
    return True, ""


def is_technical_or_utility_context(message: str) -> bool:
    low = (message or "").lower()
    token_set = set(tokenize(low))
    technical_tokens = {
        "kod", "code", "ui", "ux", "dashboard", "deploy", "render", "github",
        "api", "endpoint", "bug", "hata", "prompt", "codex", "css", "html",
        "js", "python", "fastapi", "websocket", "sunucu", "terminal", "buton",
        "tasarim", "sekme", "aktif", "degil", "degil", "dosya", "ekran", "menu",
        "mikrofon", "port", "calismiyor", "çalışmıyor",
    }
    if any(t in token_set for t in technical_tokens):
        return True
    token_stems = [
        "codex", "prompt", "dashboard", "hata", "buton", "tasar", "deploy",
        "github", "render", "python", "fastapi", "websocket", "terminal",
        "endpoint", "api", "kod", "code",
    ]
    for tok in token_set:
        for stem in token_stems:
            if tok.startswith(stem):
                return True
    technical_phrases = [
        "metni kisalt",
        "metni duzelt",
        "dashboard hatasi",
        "promptu vereyim",
        "aktif değil",
        "çalışmıyor",
    ]
    return any(p in low for p in technical_phrases)


def has_explicit_luxmirror_command(message: str) -> bool:
    low = (message or "").lower().strip()
    commands = [
        "luxmirror yap",
        "luxmirror aç",
        "luxmirror baslat",
        "lux mirror yap",
        "karar aynasi yap",
        "karar aynası yap",
        "uc soru sor",
        "üç soru sor",
    ]
    return any(c in low for c in commands)


def looks_like_luxmirror_answers(message: str) -> bool:
    low = (message or "").lower()
    has_c = "çekim:" in low or "cekim:" in low
    has_e = "engel:" in low
    has_z = "zaman:" in low
    return has_c and has_e and has_z


def generate_luxmirror_questions() -> str:
    variants = [
        "İstersen LuxMirror ile üç kısa soruda netleştirelim.",
        "Bunu üç kısa soruyla berraklaştırabiliriz.",
        "Kararı çekim/engel/zaman hattında kısa kısa ayıralım.",
    ]
    lead = random.choice(variants)
    return (
        f"{lead}\n\n"
        "1) Çekim: Bu kararın seni çeken tarafı ne?\n"
        "2) Engel: Seni durduran gerçek/pratik şey ne?\n"
        "3) Zaman: Bu karar şimdi mi, sonra mı daha doğru?"
    )


def generate_luxmirror_result(message: str) -> str:
    low = (message or "").lower()
    def _extract(label_a: str, label_b: str = "") -> str:
        start = low.find(label_a)
        if start < 0 and label_b:
            start = low.find(label_b)
            label = label_b
        else:
            label = label_a
        if start < 0:
            return ""
        seg = message[start + len(label):]
        for cut in ["çekim:", "cekim:", "engel:", "zaman:"]:
            pos = seg.lower().find(cut)
            if pos > 0:
                seg = seg[:pos]
        return compact_text(seg.strip(), 140)

    cekim = _extract("çekim:", "cekim:")
    engel = _extract("engel:")
    zaman = _extract("zaman:")

    if not any([cekim, engel, zaman]):
        return "LuxMirror için üç başlığı da kısa yazabiliriz: Çekim / Engel / Zaman."

    if "şimdi" in (zaman or "").lower():
        time_line = "zaman penceresi şimdiye yakın görünüyor"
    elif "sonra" in (zaman or "").lower() or "bekle" in (zaman or "").lower():
        time_line = "zaman penceresi biraz beklemeyi işaret ediyor"
    else:
        time_line = "zaman tarafında kısa bir netleştirme daha iyi olabilir"

    core = []
    if cekim:
        core.append("çekim var")
    if engel:
        core.append("engel net")
    if not core:
        core.append("karar hattı görünür")

    return (
        f"LuxMirror özeti: {', '.join(core)}; {time_line}. "
        "Kısa karar cümlesi: önce engeli sadeleştir, sonra zamanlamaya göre ilerle."
    )


def is_dream_false_positive_context(message: str) -> bool:
    low = (message or "").lower()
    false_positive_patterns = [
        "ruya kafe", "rüya kafe", "ruya cafe", "rüya cafe",
        "ruya bar", "rüya bar", "ruya otel", "rüya otel",
        "ruya gibi", "rüya gibi",
        "ruya diye bir", "rüya diye bir",
        "adi ruya", "adı rüya", "ruya adinda", "rüya adında",
        "ruya isimli", "rüya isimli",
    ]
    return any(p in low for p in false_positive_patterns)


def has_explicit_dream_command(message: str) -> bool:
    low = (message or "").lower()
    phrases = [
        "bu ruyayi analiz et", "bu rüyayı analiz et",
        "ruyami yorumla", "rüyamı yorumla",
        "bu ruyaya eslik et", "bu rüyaya eşlik et",
        "ruya eslikcisini ac", "rüya eşlikçisini aç",
        "ruyami psikolojik olarak yorumla", "rüyamı psikolojik olarak yorumla",
    ]
    return any(p in low for p in phrases)


def has_dream_context(message: str) -> bool:
    if is_dream_false_positive_context(message):
        return False
    low = (message or "").lower()
    dream_markers = [
        "ruyamda", "rüyamda", "ruyam", "rüyam",
        "dun gece ruya gordum", "dün gece rüya gördüm",
        "kabus gordum", "kâbus gördüm", "kabus gördüm",
        "ruyami yorumla", "rüyamı yorumla",
        "ruyaya eslik et", "rüyaya eşlik et",
        "uyandigimda", "uyandığımda",
    ]
    if any(p in low for p in dream_markers):
        return True

    # "ruya/rüya" geçiyorsa anlatı fiilleri ile birlikte olmalı.
    if ("ruya" in low or "rüya" in low):
        context_verbs = [
            "gordum", "gördüm", "anlatiyorum", "anlatıyorum", "uyandim", "uyandım",
            "hissettim", "yorumla", "analiz", "sahne", "figür", "figur",
        ]
        return any(v in low for v in context_verbs)
    return False


def has_explicit_luxching_command(message: str) -> bool:
    low = (message or "").lower()
    phrases = [
        "luxching yapalim", "luxching yapalım",
        "bunu luxching objektifiyle degerlendir", "bunu luxching objektifiyle değerlendir",
        "i ching tarzi sembolik yorum istiyorum", "ı ching tarzı sembolik yorum istiyorum",
        "i ching tarzı sembolik yorum istiyorum",
        "bu soruya luxching ile bak", "bu soruya i ching ile bak", "bu soruya ı ching ile bak",
    ]
    return any(p in low for p in phrases)


def has_luxching_context(message: str) -> bool:
    low = (message or "").lower()
    folded = fold_turkish_ascii(message or "")
    if is_technical_or_utility_context(message):
        return False

    explicit_words = ["i ching", "iching", "luxching"]
    if any(w in folded for w in explicit_words):
        return True

    decision_markers = [
        "kararsiz", "iki yol", "hangi yolu", "gitmeli miyim", "gitmesem mi",
        "girsem mi", "girmesem mi",
        "girmeli miyim", "girmemeli miyim",
        "cikmali miyim", "cikmamali miyim",
        "yapmali miyim", "yapmamali miyim",
        "olmali mi", "olmamali mi",
        "devam etmeli miyim", "devam etmemeli miyim",
        "birakmali miyim", "birakmamali miyim",
        "secmeli miyim", "secmemeli miyim",
        "olur mu olmaz mi", "acaba nasil olacak",
        "bu is bana iyi gelir mi",
        "iyi gelir mi",
        "bu iliski benim icin uygun mu",
        "esik",
    ]
    uncertainty_markers = ["?", "acaba", "emin degilim", "bilemiyorum"]
    has_decision = any(w in folded for w in decision_markers)
    has_uncertainty = any(w in folded for w in uncertainty_markers)
    has_decision_lock = any(w in folded for w in ["kaldim", "kararsiz kaldim"])
    # Türkçe karar kalıplarının varyasyonlarını regex ile de yakala.
    if not has_decision:
        decision_regex = re.compile(
            r"\b\w+(mali|meli)\s*miyim\b|\b\w+(mali|meli)\s*mi\b|\b\w+sam\s*mi\b|\b\w+sem\s*mi\b",
            re.IGNORECASE,
        )
        has_decision = bool(decision_regex.search(folded))
    return has_decision and (has_uncertainty or has_decision_lock)


def should_offer_luxching_background(
    profile: Dict[str, Any],
    analysis: Dict[str, Any],
    message: str,
    mode: str,
    session: Optional[Dict[str, Any]] = None,
) -> bool:
    _ = analysis
    if mode in {"luxta", "luxeph", "luxdream"}:
        return False
    if is_technical_or_utility_context(message):
        return False
    has_relevant_context = has_luxching_context(message)

    # İlk aşamalarda otomatik LUXCHING hatırlatması yapma (LuxMirror sonrası daha uygun).
    user_msg_count = 0
    if session:
        user_msg_count = sum(1 for m in safe_list(session.get("messages")) if m.get("role") == "user")
    if user_msg_count <= 4:
        return False

    last_used = profile.get("luxching_background_last_suggested_at")
    if last_used:
        try:
            last = datetime.fromisoformat(str(last_used).replace("Z", "+00:00"))
            if last.tzinfo is not None:
                now_same_tz = datetime.now(last.tzinfo)
                delta = now_same_tz - last
            else:
                delta = datetime.now() - last
            if delta < timedelta(hours=24):
                return False
        except Exception:
            pass

    return has_relevant_context


def luxching_background_suggestion_text() -> str:
    variants = [
        "İstersen buna sembolik bir katman daha ekleyebiliriz.",
        "Dilersen bunu Luxching tarafında daha sembolik bir açıdan da okuyabiliriz.",
        "İstersen bu kararı değişim döngüsü mantığıyla ikinci bir ışıkta da görebiliriz.",
        "Bu sonuç kendi başına yeterli; istersen I Ching'in sembolik diliyle bir katman daha açabiliriz.",
        "Burada durabiliriz; ya da istersen denge tarafına Luxching ile kısa bir bakış atabiliriz.",
    ]
    return random.choice(variants)


def should_offer_luxmirror_background(message: str, mode: str, session: Optional[Dict[str, Any]] = None) -> bool:
    if mode in {"luxta", "luxeph", "luxdream"}:
        return False
    if is_technical_or_utility_context(message):
        return False
    if not has_luxching_context(message):
        return False
    user_msg_count = 0
    if session:
        user_msg_count = sum(1 for m in safe_list(session.get("messages")) if m.get("role") == "user")
    # İlk karar mesajında değil, konu bir miktar açıldıysa öner.
    return user_msg_count >= 2


def luxmirror_background_suggestion_text() -> str:
    variants = [
        "İstersen bunu LuxMirror ile üç kısa soruda netleştirelim.",
        "Dilersen bu kararı üç kısa soruyla daha berrak hale getirebiliriz.",
        "İstersen kararın çekim, engel ve zaman tarafını kısa kısa ayıralım.",
    ]
    return random.choice(variants)


def apply_luxching_nudge(plan: Dict[str, Any], response_text: str) -> str:
    nudge = str(plan.get("luxching_nudge") or "").strip()
    if not nudge:
        return response_text
    low_response = (response_text or "").lower()
    if "luxching" in low_response or nudge.lower() in low_response:
        plan["luxching_nudge_used"] = True
        return response_text
    plan["luxching_nudge_used"] = True
    return (response_text or "").rstrip() + "\n\n" + nudge


def should_offer_luxdream_background(profile: Dict[str, Any], analysis: Dict[str, Any], message: str, mode: str) -> bool:
    _ = analysis
    if mode in {"luxta", "luxeph"}:
        return False
    if is_technical_or_utility_context(message):
        return False

    last_used = profile.get("luxdream_background_last_suggested_at")
    if last_used:
        try:
            last = datetime.fromisoformat(str(last_used).replace("Z", "+00:00"))
            if last.tzinfo is not None:
                now_same_tz = datetime.now(last.tzinfo)
                delta = now_same_tz - last
            else:
                delta = datetime.now() - last
            if delta < timedelta(hours=24):
                return False
        except Exception:
            pass

    return has_dream_context(message)


def luxdream_background_suggestion_text() -> str:
    variants = [
        "İstersen bu rüyayı birlikte açabiliriz.",
        "Dilersen rüyanın sahnelerine sırayla bakabiliriz.",
        "İstersen rüyanın sembollerine ve sende bıraktığı hisse birlikte dönebiliriz.",
        "Bunu tek bir anlama sıkıştırmadan, rüyayı sahne sahne okuyabiliriz.",
        "Kesin anlam dayatmadan rüyaya birlikte bakabiliriz.",
    ]
    return random.choice(variants)


def apply_background_nudges(plan: Dict[str, Any], response_text: str) -> str:
    pieces = []
    if plan.get("luxmirror_nudge"):
        pieces.append(str(plan.get("luxmirror_nudge")).strip())
        plan["luxmirror_nudge_used"] = True
    if plan.get("luxching_nudge"):
        pieces.append(str(plan.get("luxching_nudge")).strip())
        plan["luxching_nudge_used"] = True
    if plan.get("luxdream_nudge"):
        pieces.append(str(plan.get("luxdream_nudge")).strip())
        plan["luxdream_nudge_used"] = True
    pieces = [p for p in pieces if p]
    if not pieces:
        return response_text
    low_response = (response_text or "").lower()
    add_texts = [p for p in pieces if p.lower() not in low_response]
    if not add_texts:
        return response_text
    return (response_text or "").rstrip() + "\n\n" + "\n".join(add_texts)


# =========================================================
# CHAT PLAN
# =========================================================
def build_ephemeral_session(message: str, mode: str) -> Dict[str, Any]:
    session = default_session(mode=mode)
    add_message(session, "user", message, {"mode": mode, "ephemeral": True})
    return session


def prepare_luxeph_plan(
    user_id: str,
    message: str,
    location: str,
    ghost_hesitation: bool,
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile = ensure_profile_shape(default_profile())
    session = build_ephemeral_session(message, "luxeph")
    analysis = analyze_emotion(message, profile, session, location, ghost_hesitation, client_signals)

    if analysis.get("crisis_risk") or is_crisis_message(message, analysis):
        crisis = crisis_reply()
        return {
            "kind": "crisis",
            "response": crisis,
            "meta": {
                "mode": "luxeph",
                "session_id": None,
                "dominant_emotion": analysis.get("primary_emotion"),
                "dominant_theme": analysis.get("theme"),
                "cognitive_load": analysis.get("cognitive_load"),
                "ephemeral": True,
            },
            "weekly_report": {},
            "memory_preview": [],
        }

    digest = build_weekly_digest(profile, session, [])
    identity_boundary = classify_identity_command_boundary(message)
    count_constraints = extract_count_constraints(message)
    line_format_constraints = extract_line_format_constraints(message)
    runtime_hints = []
    identity_hint = identity_runtime_hint(message, identity_boundary)
    if identity_hint:
        runtime_hints.append(identity_hint)
    count_hint = count_guard_hint(count_constraints)
    if count_hint:
        runtime_hints.append(count_hint)
    line_hint = line_format_guard_hint(line_format_constraints)
    if line_hint:
        runtime_hints.append(line_hint)
    token_budget = safe_token_budget_decision(message, "luxeph", analysis, count_constraints)
    prompt = build_system_prompt(profile, analysis, "luxeph", [], digest, location, runtime_hints=runtime_hints)
    model, temp, max_tokens = choose_generation_params("luxeph", analysis)
    return {
        "kind": "model",
        "skip_save": True,
        "active": None,
        "session": session,
        "profile": profile,
        "notes": [],
        "garden": [],
        "analysis": analysis,
        "prompt": prompt,
        "openai_messages": build_openai_messages(session, prompt),
        "model": model,
        "temperature": temp,
        "max_tokens": max_tokens,
        "weekly_report": {},
        "memory_preview": [],
        "user_id": user_id,
        "mode": "luxeph",
        "message": message,
        "identity_boundary": identity_boundary,
        "count_constraints": count_constraints,
        "line_format_constraints": line_format_constraints,
        "token_budget": token_budget,
        "meta": {"mode": "luxeph", "session_id": None, "ephemeral": True},
    }


def prepare_chat_plan(
    user_id: str,
    message: str,
    mode: str,
    ghost_hesitation: bool = False,
    location: str = "İstanbul",
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    user_id = safe_user_id(user_id)
    mode = (mode or "luxviai").lower().strip()
    if mode not in ALLOWED_MODES:
        mode = "luxviai"
    if mode in {"luxching", "luxdream"}:
        # Dedicated LUXCHING/LUXDREAM modes are retired; both run as background lenses.
        mode = "luxviai"

    if mode == "luxeph":
        return prepare_luxeph_plan(user_id, message, location, ghost_hesitation, client_signals)

    command_response = get_command_response(user_id, message)
    if command_response is not None:
        return {
            "kind": "command",
            "response": command_response,
            "meta": {"mode": mode, "session_id": None},
        }

    profile, notes, garden = load_user_state(user_id)
    profile = ensure_profile_shape(profile)
    profile = apply_identity_guard(profile, message)
    identity_boundary = classify_identity_command_boundary(message)
    if identity_boundary in {"identity", "correction"}:
        save_user_state(user_id, profile, notes, garden)

    # Contextual explicit lens commands: keep background lenses available
    # without forcing random suggestions in normal chat flow.
    session_for_lens = load_current_session(user_id)
    if has_explicit_dream_command(message):
        return {
            "kind": "command",
            "response": generate_luxdream(message, profile, session_for_lens),
            "meta": {"mode": mode, "session_id": None, "lens": "luxdream"},
        }
    if has_explicit_luxmirror_command(message):
        return {
            "kind": "command",
            "response": generate_luxmirror_questions(),
            "meta": {"mode": mode, "session_id": None, "lens": "luxmirror"},
        }
    if looks_like_luxmirror_answers(message):
        return {
            "kind": "command",
            "response": generate_luxmirror_result(message),
            "meta": {"mode": mode, "session_id": None, "lens": "luxmirror"},
        }
    if has_explicit_luxching_command(message):
        ok, _ = check_luxching_limit(profile)
        if not ok:
            return {
                "kind": "command",
                "response": (
                    "Bugün Luxching katmanını zaten açtık. "
                    "Onu hemen yenilemek yerine çıkan sembolü biraz taşıyalım. "
                    "İstersen normal Lux akışıyla devam edebiliriz."
                ),
                "meta": {"mode": mode, "session_id": None, "lens": "luxching"},
            }
        lens_analysis = heuristic_analysis(message, profile, session_for_lens)
        profile["luxching_last_used"] = now_iso()
        save_user_state(user_id, profile, notes, garden)
        return {
            "kind": "command",
            "response": generate_luxching(profile, lens_analysis, message),
            "meta": {"mode": mode, "session_id": None, "lens": "luxching"},
        }

    if location:
        locs = profile["ecological_context"].setdefault("locations", {})
        locs[location] = int(locs.get(location, 0)) + 1

    active, session = load_or_create_session(user_id, mode)

    add_message(session, "user", message, {"mode": mode})
    analysis_start = perf_counter()
    analysis = analyze_emotion(message, profile, session, location, ghost_hesitation, client_signals)
    analysis_ms = ms_since(analysis_start)

    if ghost_hesitation and analysis.get("intensity", 5) < 7:
        analysis["needs_presence"] = True
        analysis["narrative_marker"] = "geri çekilme"
        analysis.setdefault("layers", {}).setdefault("hidden", {})["ghost_hesitation"] = True

    enrich_start = perf_counter()
    analysis = enrich_analysis_with_human_policy(message, analysis, profile, session, client_signals)
    enrich_ms = ms_since(enrich_start)
    technical_context = is_technical_or_utility_context(message)
    dream_context = has_dream_context(message)
    decision_context = has_luxching_context(message) and not technical_context and not dream_context

    runtime_hints: List[str] = []
    runtime_hints.append("Natural Half-Step kullan: her cevabı soruyla bitirmek zorunda değilsin.")
    runtime_hints.append(
        "Kimlik güvenliği: sadece 'Adım/İsmim/Bana X de' gibi açık ifadeleri kullanıcı adı say; üçüncü kişi, referans, sanatçı veya örnek isimlerden hitap çıkarma."
    )
    identity_hint = identity_runtime_hint(message, identity_boundary)
    if identity_hint:
        runtime_hints.append(identity_hint)
    count_constraints = extract_count_constraints(message)
    line_format_constraints = extract_line_format_constraints(message)
    count_hint = count_guard_hint(count_constraints)
    if count_hint:
        runtime_hints.append(count_hint)
    line_hint = line_format_guard_hint(line_format_constraints)
    if line_hint:
        runtime_hints.append(line_hint)
    token_budget = safe_token_budget_decision(message, mode, analysis, count_constraints)
    if identity_boundary == "correction":
        runtime_hints.append("Kullanıcı isim düzeltmesi yaptı: yanlış hitabı kısa kabul et ve o adı tekrar kullanma.")
    elif identity_boundary == "identity":
        runtime_hints.append("Kullanıcı açık hitap/isim verdi; doğal gelirse kullan, tekrar tekrar vurgulama.")
    elif identity_boundary in {"content", "command"}:
        runtime_hints.append("Bu mesajdaki kişi adlarını içerik/komut nesnesi olarak ele al; kullanıcı kimliği sayma.")
    if technical_context:
        runtime_hints.extend([
            "Bu mesaj teknik/utility niyetinde: metaforik veya terapötik yorum yapma.",
            "Doğrudan net teknik açıklama ver; gerekiyorsa adım adım ve kontrol edilebilir ilerle.",
        ])
    if decision_context:
        runtime_hints.append("Bu mesaj karar/ikilem niyetinde: önce sade karar analizi yap, sembolik katmana hemen atlama.")
        user_msgs = [m for m in safe_list(session.get("messages")) if m.get("role") == "user"]
        prev_user_text = str(user_msgs[-2].get("content", "")) if len(user_msgs) >= 2 and isinstance(user_msgs[-2], dict) else ""
        if prev_user_text and has_dream_context(prev_user_text):
            runtime_hints.append("Önceki rüya bağlamını taşımadan karar hattına yumuşak geçiş yap.")

    luxching_nudge = ""
    luxdream_nudge = ""
    luxmirror_nudge = ""
    dream_offer = False if count_constraints else should_offer_luxdream_background(profile, analysis, message, mode)
    ching_offer = False if count_constraints else should_offer_luxching_background(profile, analysis, message, mode, session)
    mirror_offer = False if count_constraints else should_offer_luxmirror_background(message, mode, session)
    if dream_offer:
        luxdream_nudge = luxdream_background_suggestion_text()
    elif mirror_offer:
        luxmirror_nudge = luxmirror_background_suggestion_text()
    elif ching_offer:
        luxching_nudge = luxching_background_suggestion_text()

    if analysis.get("crisis_risk") or is_crisis_message(message, analysis):
        crisis = crisis_reply()
        add_analysis(session, {**analysis, "crisis_risk": True})
        add_message(session, "assistant", crisis, {"mode": mode, "crisis": True})
        update_profile_from_analysis(profile, analysis)
        append_memory_garden_anchor(garden, message, analysis)
        digest = build_weekly_digest(profile, session, garden)
        profile["weekly_report"] = digest
        save_user_state(user_id, profile, notes, garden)
        save_session(user_id, active, session)
        return {
            "kind": "crisis",
            "response": crisis,
            "meta": {
                "mode": mode,
                "session_id": session["session_id"],
                "dominant_emotion": analysis.get("primary_emotion"),
                "dominant_theme": analysis.get("theme"),
                "cognitive_load": analysis.get("cognitive_load"),
                "crisis_context": safe_dict(analysis.get("safety_layer")).get("crisis_context"),
            },
            "weekly_report": digest,
            "memory_preview": retrieve_memory_snippets(message, session, notes, garden, profile, limit=5),
            "token_budget": token_budget,
        }

    add_analysis(session, analysis)
    update_profile_from_analysis(profile, analysis)
    append_memory_garden_anchor(garden, message, analysis)
    digest_start = perf_counter()
    digest = build_weekly_digest(profile, session, garden)
    digest_ms = ms_since(digest_start)
    profile["weekly_report"] = digest
    profile["last_mode"] = mode

    memory_start = perf_counter()
    memory_snippets = retrieve_memory_snippets(message, session, notes, garden, profile, limit=5)
    memory_ms = ms_since(memory_start)
    context_start = perf_counter()
    learning_context = learning_pipeline.build_live_context(
        user_id,
        message,
        analysis,
        mode,
        profile=profile,
        session=session,
    )
    context_ms = ms_since(context_start)
    prompt_start = perf_counter()
    prompt = build_system_prompt(profile, analysis, mode, memory_snippets, digest, location, runtime_hints=runtime_hints)
    live_ctx_text = str(learning_context.get("context_text", "")).strip() or str(learning_context.get("context_line", "")).strip()
    if live_ctx_text:
        prompt += f"\n\n[Learning Lab]\n{live_ctx_text}"
    hint_lines = [str(x).strip() for x in learning_context.get("behavior_hints", []) if str(x).strip()]
    if hint_lines:
        prompt += "\n- " + "\n- ".join(hint_lines[:3])
    openai_messages = build_openai_messages(session, prompt)
    model, temp, max_tokens = choose_generation_params(mode, analysis)
    token_floor = requested_long_answer_token_floor(message)
    if token_floor:
        max_tokens = max(max_tokens, token_floor)
    prompt_ms = ms_since(prompt_start)
    log_latency(
        "prepare_model_plan",
        analysis_ms=analysis_ms,
        enrich_ms=enrich_ms,
        digest_ms=digest_ms,
        memory_ms=memory_ms,
        context_ms=context_ms,
        prompt_ms=prompt_ms,
        message_chars=len(message),
        prompt_chars=len(prompt),
        context_chars=len(live_ctx_text),
        mode=mode,
        max_tokens=max_tokens,
    )

    return {
        "kind": "model",
        "active": active,
        "session": session,
        "profile": profile,
        "notes": notes,
        "garden": garden,
        "analysis": analysis,
        "prompt": prompt,
        "openai_messages": openai_messages,
        "model": model,
        "temperature": temp,
        "max_tokens": max_tokens,
        "weekly_report": digest,
        "memory_preview": memory_snippets,
        "luxmirror_nudge": luxmirror_nudge,
        "luxching_nudge": luxching_nudge,
        "luxdream_nudge": luxdream_nudge,
        "learning_context": learning_context,
        "identity_boundary": identity_boundary,
        "count_constraints": count_constraints,
        "line_format_constraints": line_format_constraints,
        "token_budget": token_budget,
        "user_id": user_id,
        "mode": mode,
        "message": message,
    }


def finalize_chat(plan: Dict[str, Any], response_text: str):
    if plan.get("skip_save"):
        return {}

    user_id = plan["user_id"]
    active = plan["active"]
    session = plan["session"]
    profile = plan["profile"]
    notes = plan["notes"]
    garden = plan["garden"]
    mode = plan["mode"]

    add_message(session, "assistant", response_text, {"mode": mode})
    if plan.get("luxching_nudge_used"):
        profile["luxching_background_last_suggested_at"] = now_iso()
    if plan.get("luxdream_nudge_used"):
        profile["luxdream_background_last_suggested_at"] = now_iso()

    digest = build_weekly_digest(profile, session, garden)
    profile["weekly_report"] = digest

    save_user_state(user_id, profile, notes, garden)
    save_session(user_id, active, session)
    return digest


def chat_fallback_response(plan: Dict[str, Any]) -> str:
    return fallback_reply(plan["mode"], plan["analysis"])


def auto_continue_text(plan: Dict[str, Any], response_text: str, finish_reason: str, max_parts: Optional[int] = None) -> tuple[str, str, int]:
    merged = (response_text or "").strip()
    reason = finish_reason or ""
    parts = 0
    limit = auto_continuation_part_limit(plan) if max_parts is None else max_parts
    while parts < limit and should_auto_continue_response(reason, merged, plan):
        parts += 1
        try:
            continuation, reason = call_model_with_finish(
                build_guarded_continuation_messages(plan["openai_messages"], merged, safe_list(plan.get("count_constraints"))),
                model=plan["model"],
                temperature=plan["temperature"],
                max_tokens=auto_continuation_max_tokens(plan),
            )
        except Exception as e:
            logging.warning(f"Auto continuation stopped: {e}")
            break
        if not continuation:
            break
        next_merged = merge_continuation_text(merged, continuation)
        if next_merged == merged:
            break
        merged = next_merged.strip()
    return merged, reason, parts


def auth_error_response() -> str:
    return (
        "Model baglantisinda kimlik dogrulama sorunu var. "
        "DEEPSEEK_API_KEY degerini kontrol edip uygulamayi yeniden baslat."
    )


def check_auth(auth: Optional[str]):
    if not auth:
        return
    token = auth.replace("Bearer ", "").strip()
    if token and token != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim.")


def deepl_base_url() -> str:
    if DEEPL_API_BASE:
        return DEEPL_API_BASE.rstrip("/")
    if DEEPL_API_KEY.endswith(":fx"):
        return "https://api-free.deepl.com"
    return "https://api.deepl.com"


def deepl_translate_text(text: str, target_lang: str, source_lang: Optional[str] = None) -> Dict[str, Any]:
    if not DEEPL_API_KEY:
        return {
            "ok": False,
            "translated_text": text,
            "detected_source_language": None,
            "error": "DEEPL_API_KEY missing",
        }

    target = (target_lang or "EN").strip().upper()
    source = (source_lang or "").strip().upper()
    payload: Dict[str, Any] = {"text": [text], "target_lang": target}
    if source:
        payload["source_lang"] = source

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url=f"{deepl_base_url()}/v2/translate",
        data=data,
        method="POST",
        headers={
            "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)
            translations = safe_list(body.get("translations"))
            first = safe_dict(translations[0]) if translations else {}
            return {
                "ok": bool(first.get("text")),
                "translated_text": str(first.get("text", text)),
                "detected_source_language": first.get("detected_source_language"),
                "error": None,
            }
    except HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        return {
            "ok": False,
            "translated_text": text,
            "detected_source_language": None,
            "error": f"deepl_http_error: {detail}",
        }
    except URLError as e:
        return {
            "ok": False,
            "translated_text": text,
            "detected_source_language": None,
            "error": f"deepl_url_error: {e}",
        }
    except Exception as e:
        return {
            "ok": False,
            "translated_text": text,
            "detected_source_language": None,
            "error": f"deepl_error: {e}",
        }


def looks_foreign_word(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    # Turkish letters absent + at least one latin char.
    if re.search(r"[A-Za-z]", s) and not re.search(r"[çğıöşüÇĞİÖŞÜ]", s):
        return True
    return False


LOCAL_TRANSLATION_TR = {
    "hello": "merhaba",
    "hi": "selam",
    "how are you": "nasılsın",
    "good morning": "günaydın",
    "good night": "iyi geceler",
    "thank you": "teşekkür ederim",
    "thanks": "teşekkürler",
    "love": "sevgi",
    "dream": "rüya",
    "memory": "hafıza",
    "anxiety": "kaygı",
    "fear": "korku",
    "sadness": "üzüntü",
}


def local_phrase_translate(text: str, target_lang: str) -> Optional[str]:
    clean = fold_turkish_ascii((text or "").strip())
    if not clean:
        return None
    tgt = (target_lang or "").upper()
    if tgt.startswith("TR"):
        return LOCAL_TRANSLATION_TR.get(clean)
    return None


def user_lang_to_deepl_target(user_lang: str) -> str:
    lang = (user_lang or "tr").strip().lower()
    mapping = {
        "tr": "TR",
        "en": "EN",
        "de": "DE",
        "fr": "FR",
        "es": "ES",
        "it": "IT",
        "pt": "PT-PT",
        "ru": "RU",
        "ar": "AR",
        "nl": "NL",
        "pl": "PL",
        "ja": "JA",
        "zh": "ZH",
        "ko": "KO",
        "uk": "UK",
        "nb": "NB",
        "no": "NB",
        "sv": "SV",
        "fi": "FI",
        "da": "DA",
        "cs": "CS",
        "el": "EL",
        "ro": "RO",
        "hu": "HU",
        "bg": "BG",
        "id": "ID",
        "sk": "SK",
        "sl": "SL",
        "et": "ET",
        "lv": "LV",
        "lt": "LT",
    }
    return mapping.get(lang, lang.upper()[:5] or "TR")


def looks_turkish_text(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if re.search(r"[çğıöşüÇĞİÖŞÜ]", s):
        return True
    if re.search(r"[A-Za-z]", s) and not looks_foreign_word(s):
        return True
    return False


def tdk_define_once(text: str) -> Optional[str]:
    cleaned = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ\- ]", " ", str(text or "")).strip()
    if not cleaned:
        return None
    tokens = [t for t in cleaned.split() if t]
    if len(tokens) != 1:
        return None
    word = tokens[0]
    if len(word) < 2:
        return None
    try:
        url = f"https://sozluk.gov.tr/gts?ara={quote(word)}"
        req = Request(url=url, method="GET", headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if not isinstance(body, list) or not body:
            return None
        entry = safe_dict(body[0])
        meanings = safe_list(entry.get("anlamlarListe"))
        if not meanings:
            return None
        first = safe_dict(meanings[0])
        meaning = str(first.get("anlam", "")).strip()
        if not meaning:
            return None
        meaning = re.sub(r"<[^>]+>", "", meaning).strip()
        return meaning[:320]
    except Exception:
        return None


def translate_if_needed(text: str, target_lang: str) -> str:
    tgt = (target_lang or "TR").upper()
    if tgt.startswith("TR"):
        return text
    result = deepl_translate_text(text, tgt)
    translated = str(result.get("translated_text", text) or text).strip()
    if translated and translated.lower() != text.lower():
        return translated
    return text


def explain_with_model_tr(text: str) -> str:
    if not client:
        return ""
    system_prompt = (
        "Kısa Türkçe sözlük açıklaması üret. "
        "Tek cümle, en fazla 18 kelime. "
        "Tıbbi/felsefi terimse sade anlat. "
        "Tanı, tedavi, kesin hüküm verme. "
        "Kullanıcı cümlesine sohbet cevabı verme. "
        "Soruya cevap verme, sadece kelime/ifade anlamı açıkla."
    )
    try:
        out = call_model(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            model="deepseek-chat",
            temperature=0.2,
            max_tokens=80,
        ).strip()
        return out
    except Exception:
        return ""


# =========================================================
# LEARNING DASHBOARD
# =========================================================
DASHBOARD_TOPIC_META: Dict[str, Dict[str, str]] = {
    "relationships": {
        "label": "İlişkiler",
        "recommendation": "İlişki ritmi ve güven onarımı odaklı hibrit eğitim artırılmalı.",
    },
    "emotional_support": {
        "label": "Duygusal destek",
        "recommendation": "Yoğunluk yükseldiğinde kısa, sakin ve yargısız yanıt stratejisi güçlendirilmeli.",
    },
    "technical_guidance": {
        "label": "Teknik anlatım",
        "recommendation": "Tek adım + doğrulama döngüsü korunmalı.",
    },
    "creative_ideation": {
        "label": "Yaratıcı fikir",
        "recommendation": "Yaratıcı örnek + uygulanabilir plan hibriti artırılmalı.",
    },
    "coding_help": {
        "label": "Kodlama yardımı",
        "recommendation": "Kısa açıklama + çalışır örnek + hata kontrol akışı sürdürülmeli.",
    },
    "natural_language": {
        "label": "Doğal dil",
        "recommendation": "Robotik kalıpları azaltıp sıcak ve sade anlatım korunmalı.",
    },
    "repair_quality": {
        "label": "Onarım kalitesi",
        "recommendation": "Kırılma sonrası kısa kabul + tek adım düzeltme kalıbı sıklaştırılmalı.",
    },
    "confusion_reduction": {
        "label": "Kafa karışıklığı azaltma",
        "recommendation": "Karışıklık sinyalinde kapsam daraltılıp tek hedefe inilmeli.",
    },
    "patience_management": {
        "label": "Sabır yönetimi",
        "recommendation": "Kullanıcı sabrı düştüğünde cevap yoğunluğu otomatik azaltılmalı.",
    },
    "task_success": {
        "label": "Görev tamamlama",
        "recommendation": "Sonuç odaklı doğrulama adımları ve kapanış kontrolü artırılmalı.",
    },
    "human_like_tone": {
        "label": "İnsansı ton",
        "recommendation": "Doğal ritim, sıcaklık ve küçük onarım cümleleri dengelenmeli.",
    },
}

REL_WORDS = ["iliski", "bag", "baglan", "guven", "yalniz", "aile", "sevgili", "es", "arkadas"]
TECH_WORDS = ["kod", "deploy", "render", "github", "terminal", "hata", "server", "endpoint", "api", "komut"]
CODE_WORDS = ["python", "javascript", "html", "css", "uvicorn", "fastapi", "json", "fonksiyon", "class"]
CREATIVE_WORDS = ["fikir", "hayal", "yaratici", "tasarim", "vizyon", "konsept", "senaryo", "hikaye"]
CONFUSION_WORDS = ["anlamadim", "nasil", "yani", "karisti", "olmadi", "bulamadim", "nerede", "hata"]
SUCCESS_WORDS = ["oldu", "calisti", "tamam", "cozuldu", "duzeldi", "acildi", "tesekkur"]
FRUSTRATION_WORDS = ["karistirdin", "olmuyor", "biktim", "yanlis", "sacma", "hizli", "bekle"]
REPAIR_WORDS = ["haklisin", "anliyorum", "yavaslayalim", "tek adim", "sade", "duzelteyim", "toparlayayim"]


def parse_iso_optional(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = parse_iso(text)
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def in_time_range(ts: Optional[datetime], start: datetime, end: datetime) -> bool:
    if ts is None:
        return False
    return start <= ts < end


def normalize_for_scan(text: str) -> str:
    return fold_turkish_ascii((text or "").lower())


def contains_scan_token(text: str, words: List[str]) -> bool:
    low = normalize_for_scan(text)
    return any(w in low for w in words)


def load_user_sessions_for_dashboard(user_id: str) -> List[Dict[str, Any]]:
    user_id = safe_user_id(user_id)
    sessions: List[Dict[str, Any]] = []
    seen = set()

    index = safe_list(load_json(sessions_index_path(user_id), []))
    for item in index:
        entry = safe_dict(item)
        sid = str(entry.get("session_id", "")).strip()
        if not sid or sid in seen:
            continue
        path = session_file_path(user_id, sid)
        if not path.exists():
            continue
        sess = safe_dict(load_json(path, {}))
        if sess:
            sessions.append(sess)
            seen.add(sid)

    active = safe_dict(load_json(active_session_path(user_id), {}))
    active_sid = str(active.get("session_id", "")).strip()
    if active_sid and active_sid not in seen:
        path = session_file_path(user_id, active_sid)
        if path.exists():
            sess = safe_dict(load_json(path, {}))
            if sess:
                sessions.append(sess)
                seen.add(active_sid)

    sessions.sort(
        key=lambda s: parse_iso_optional(s.get("last_seen") or s.get("created_at")) or datetime.fromtimestamp(0, tz=timezone.utc)
    )
    return sessions


def collect_window_payload(user_id: str, start: datetime, end: datetime) -> Dict[str, Any]:
    sessions = load_user_sessions_for_dashboard(user_id)
    analyses: List[Dict[str, Any]] = []
    user_messages: List[str] = []
    assistant_messages: List[str] = []

    for session in sessions:
        session_created = parse_iso_optional(session.get("created_at"))
        for a in safe_list(session.get("analyses")):
            row = safe_dict(a)
            ts = parse_iso_optional(row.get("ts")) or session_created
            if in_time_range(ts, start, end):
                analyses.append(row)

        for msg in safe_list(session.get("messages")):
            m = safe_dict(msg)
            ts = parse_iso_optional(m.get("ts")) or session_created
            if not in_time_range(ts, start, end):
                continue
            role = str(m.get("role", "")).strip().lower()
            content = str(m.get("content", "")).strip()
            if not content:
                continue
            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                assistant_messages.append(content)

    return {
        "analysis_count": len(analyses),
        "analyses": analyses,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
    }


def analysis_ratio(analyses: List[Dict[str, Any]], predicate) -> float:
    if not analyses:
        return 0.0
    hit = 0
    for a in analyses:
        try:
            if predicate(a):
                hit += 1
        except Exception:
            continue
    return hit / len(analyses)


def message_ratio(messages: List[str], predicate) -> float:
    if not messages:
        return 0.0
    hit = 0
    for m in messages:
        try:
            if predicate(m):
                hit += 1
        except Exception:
            continue
    return hit / len(messages)


def score_topics(payload: Dict[str, Any]) -> Dict[str, float]:
    analyses = safe_list(payload.get("analyses"))
    user_messages = [str(x) for x in safe_list(payload.get("user_messages"))]
    assistant_messages = [str(x) for x in safe_list(payload.get("assistant_messages"))]

    user_rel_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, REL_WORDS))
    user_tech_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, TECH_WORDS))
    user_code_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, CODE_WORDS))
    user_creative_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, CREATIVE_WORDS))
    user_confusion_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, CONFUSION_WORDS))
    user_success_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, SUCCESS_WORDS))
    user_frustration_ratio = message_ratio(user_messages, lambda t: contains_scan_token(t, FRUSTRATION_WORDS))
    assistant_repair_ratio = message_ratio(assistant_messages, lambda t: contains_scan_token(t, REPAIR_WORDS))
    assistant_step_ratio = message_ratio(
        assistant_messages,
        lambda t: contains_scan_token(t, ["1.", "2.", "adim", "adım", "once", "önce", "sonra"]),
    )
    assistant_short_ratio = message_ratio(assistant_messages, lambda t: len((t or "").split()) <= 45)
    assistant_warm_ratio = message_ratio(
        assistant_messages,
        lambda t: contains_scan_token(t, ["yanindayim", "yanındayım", "beraber", "anliyorum", "anlıyorum", "sakin"]),
    )

    relationship_score = (
        0.7
        * analysis_ratio(
            analyses,
            lambda a: str(safe_dict(safe_dict(a.get("layers")).get("relationship")).get("pattern", "")).strip().lower()
            not in {"", "belirsiz"},
        )
        + 0.3 * user_rel_ratio
    )

    emotional_support_score = (
        0.4 * analysis_ratio(analyses, lambda a: bool(a.get("needs_presence")))
        + 0.35 * analysis_ratio(analyses, lambda a: str(a.get("primary_emotion", "")) in {"kaygı", "yalnızlık", "kırgınlık", "değersizlik", "yorgunluk"})
        + 0.25 * analysis_ratio(
            analyses,
            lambda a: str(safe_dict(safe_dict(a.get("layers")).get("dynamic_tone")).get("warmth_calibration", "")).strip().lower()
            in {"orta", "yüksek"},
        )
    )

    technical_guidance_score = 0.7 * user_tech_ratio + 0.3 * assistant_step_ratio
    coding_help_score = 0.65 * user_code_ratio + 0.35 * assistant_step_ratio
    creative_ideation_score = (
        0.6 * user_creative_ratio
        + 0.4
        * analysis_ratio(
            analyses,
            lambda a: str(safe_dict(safe_dict(a.get("layers")).get("symbolic")).get("density", "")).strip().lower() == "yüksek",
        )
    )

    natural_language_score = (
        0.45 * analysis_ratio(analyses, lambda a: bool(safe_dict(a.get("layers")).get("human_layer")))
        + 0.30 * assistant_warm_ratio
        + 0.25 * analysis_ratio(analyses, lambda a: bool(safe_dict(a.get("response_policy")).get("pacing")))
    )

    frustration_signals = user_frustration_ratio + user_confusion_ratio
    if frustration_signals > 0:
        repair_quality_score = min(1.0, (assistant_repair_ratio + 0.2) / frustration_signals)
    else:
        repair_quality_score = 0.65 if assistant_messages else 0.0

    if user_confusion_ratio > 0:
        confusion_reduction_score = min(1.0, user_success_ratio / user_confusion_ratio)
    else:
        confusion_reduction_score = 0.6 if user_messages else 0.0

    patience_management_score = (
        0.45 * assistant_short_ratio
        + 0.30 * analysis_ratio(
            analyses,
            lambda a: str(safe_dict(safe_dict(a.get("layers")).get("dynamic_tone")).get("tempo", "")).strip().lower()
            in {"çok yavaş", "yavaş", "orta"},
        )
        + 0.25 * (1.0 - min(1.0, frustration_signals))
    )

    task_success_score = (
        0.65 * user_success_ratio
        + 0.35 * analysis_ratio(analyses, lambda a: str(a.get("cognitive_load", "")) in {"düşük", "orta"})
    )

    human_like_tone_score = (
        0.35 * analysis_ratio(
            analyses,
            lambda a: str(safe_dict(a.get("response_policy")).get("warmth_label", "")).strip().lower() in {"orta", "yüksek"},
        )
        + 0.35 * analysis_ratio(
            analyses,
            lambda a: str(safe_dict(safe_dict(a.get("layers")).get("human_layer")).get("human_warmth", "")).strip().lower()
            in {"orta", "yüksek"},
        )
        + 0.30 * analysis_ratio(
            analyses,
            lambda a: bool(safe_dict(safe_dict(a.get("layers")).get("human_layer")).get("imperfect_cadence")),
        )
    )

    raw = {
        "relationships": relationship_score,
        "emotional_support": emotional_support_score,
        "technical_guidance": technical_guidance_score,
        "creative_ideation": creative_ideation_score,
        "coding_help": coding_help_score,
        "natural_language": natural_language_score,
        "repair_quality": repair_quality_score,
        "confusion_reduction": confusion_reduction_score,
        "patience_management": patience_management_score,
        "task_success": task_success_score,
        "human_like_tone": human_like_tone_score,
    }

    return {k: round(clamp_float(v, 0.0, 1.0, 0.0), 4) for k, v in raw.items()}


def overall_score_from_topics(topic_scores: Dict[str, float]) -> float:
    vals = [safe_float(v) for v in topic_scores.values()]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 4)


def growth_percent(previous_score: float, current_score: float) -> int:
    return int(round((safe_float(current_score) - safe_float(previous_score)) * 100))


def topic_status(score: float) -> str:
    s = safe_float(score)
    if s >= 0.9:
        return "elite"
    if s >= 0.75:
        return "strong"
    if s >= 0.45:
        return "improving"
    return "weak"


def topic_recommendation(topic: str, status: str, growth: int) -> str:
    base = safe_dict(DASHBOARD_TOPIC_META.get(topic)).get("recommendation", "Eğitim döngüsü artırılmalı.")
    if status == "weak":
        return f"{base} Bu alan için hedefli eğitim koşusu artırılmalı."
    if growth < 0:
        return f"{base} Son periyotta gerileme var; yeniden kalibrasyon önerilir."
    return base


def build_topic_report(current_scores: Dict[str, float], previous_scores: Dict[str, float]) -> Dict[str, Any]:
    topics: Dict[str, Any] = {}
    weak_areas: List[Dict[str, Any]] = []
    strong_areas: List[Dict[str, Any]] = []

    for topic, meta in DASHBOARD_TOPIC_META.items():
        prev_score = round(clamp_float(previous_scores.get(topic, 0.0), 0.0, 1.0, 0.0), 4)
        cur_score = round(clamp_float(current_scores.get(topic, 0.0), 0.0, 1.0, 0.0), 4)
        growth = growth_percent(prev_score, cur_score)
        status = topic_status(cur_score)
        rec = topic_recommendation(topic, status, growth)

        topics[topic] = {
            "label": meta.get("label", topic),
            "previous_score": prev_score,
            "current_score": cur_score,
            "growth_percent": growth,
            "status": status,
            "recommendation": rec,
        }

        if status == "weak" or cur_score < 0.7:
            weak_areas.append(
                {
                    "topic": topic,
                    "label": meta.get("label", topic),
                    "score": cur_score,
                    "reason": "Skor düşük veya gelişim yavaş.",
                    "recommendation": rec,
                    "suggested_training_runs": max(8, int(round((0.85 - cur_score) * 40))),
                }
            )
        if status in {"strong", "elite"}:
            strong_areas.append(
                {
                    "topic": topic,
                    "label": meta.get("label", topic),
                    "score": cur_score,
                    "confidence": "yüksek" if status == "elite" else "orta-yüksek",
                    "best_behavior_pattern": rec,
                }
            )

    weak_areas.sort(key=lambda x: safe_float(x.get("score"), 0.0))
    strong_areas.sort(key=lambda x: safe_float(x.get("score"), 0.0), reverse=True)
    return {"topics": topics, "weak_areas": weak_areas[:6], "strong_areas": strong_areas[:6]}


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        count = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
    except Exception:
        return 0


def fine_tune_stats() -> Dict[str, Any]:
    global_dir = DATA_DIR / "global"
    fine_path = global_dir / "fine_tune_candidates.jsonl"
    elite_path = global_dir / "elite_candidates.jsonl"
    rejected_path = global_dir / "rejected_candidates.jsonl"
    pending_path = global_dir / "pending_candidates.jsonl"

    fine = count_jsonl_rows(fine_path)
    elite = count_jsonl_rows(elite_path)
    rejected = count_jsonl_rows(rejected_path)
    pending = count_jsonl_rows(pending_path)

    last_dt: Optional[datetime] = None
    for p in [fine_path, elite_path, rejected_path, pending_path]:
        if not p.exists():
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if last_dt is None or mtime > last_dt:
                last_dt = mtime
        except Exception:
            continue

    return {
        "total_candidates": fine,
        "elite_candidates": elite,
        "pending_candidates": pending,
        "rejected_candidates": rejected,
        "last_candidate_created_at": now_iso() if last_dt is None else last_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def build_window_summary(current_scores: Dict[str, float], previous_scores: Dict[str, float], analysis_count: int, ft_stats: Dict[str, Any]) -> Dict[str, Any]:
    current_overall = overall_score_from_topics(current_scores)
    previous_overall = overall_score_from_topics(previous_scores)
    growth = growth_percent(previous_overall, current_overall)
    runs = int(analysis_count)
    accepted = int(round(runs * max(0.35, min(0.98, current_overall))))
    premium_ratio = clamp_float((current_overall - 0.72) / 0.28, 0.0, 1.0, 0.0)
    premium = int(round(runs * premium_ratio))

    return {
        "overall_growth_percent": growth,
        "total_training_runs": runs,
        "accepted_learnings": accepted,
        "premium_learnings": premium,
        "elite_candidates": int(ft_stats.get("elite_candidates", 0)),
        "fine_tune_candidates": int(ft_stats.get("total_candidates", 0)),
        "overall_score": current_overall,
        "previous_overall_score": previous_overall,
    }


def build_user_learning_dashboard(user_id: str) -> Dict[str, Any]:
    user_id = safe_user_id(user_id)
    now_utc = datetime.now(timezone.utc)

    start_7 = now_utc - timedelta(days=7)
    prev_start_7 = now_utc - timedelta(days=14)
    start_30 = now_utc - timedelta(days=30)
    prev_start_30 = now_utc - timedelta(days=60)

    cur7 = collect_window_payload(user_id, start_7, now_utc)
    prev7 = collect_window_payload(user_id, prev_start_7, start_7)
    cur30 = collect_window_payload(user_id, start_30, now_utc)
    prev30 = collect_window_payload(user_id, prev_start_30, start_30)
    all_time = collect_window_payload(user_id, datetime.fromtimestamp(0, tz=timezone.utc), now_utc)

    cur7_scores = score_topics(cur7)
    prev7_scores = score_topics(prev7)
    cur30_scores = score_topics(cur30)
    prev30_scores = score_topics(prev30)

    ft_stats = fine_tune_stats()
    last_7 = build_window_summary(cur7_scores, prev7_scores, cur7.get("analysis_count", 0), ft_stats)
    last_30 = build_window_summary(cur30_scores, prev30_scores, cur30.get("analysis_count", 0), ft_stats)

    topic_report = build_topic_report(cur30_scores, prev30_scores)
    all_scores = score_topics(all_time)
    all_prev_scores = prev30_scores
    all_window = build_window_summary(all_scores, all_prev_scores, all_time.get("analysis_count", 0), ft_stats)

    return {
        "scope": "user",
        "user_id": user_id,
        "generated_at": now_iso(),
        "last_7_days": last_7,
        "last_30_days": last_30,
        "all_time": all_window,
        "total_training_runs": all_window["total_training_runs"],
        "accepted_learnings": all_window["accepted_learnings"],
        "premium_learnings": all_window["premium_learnings"],
        "elite_candidates": int(ft_stats.get("elite_candidates", 0)),
        "fine_tune_candidates": int(ft_stats.get("total_candidates", 0)),
        "topics": topic_report["topics"],
        "weak_areas": topic_report["weak_areas"],
        "strong_areas": topic_report["strong_areas"],
        "fine_tune": ft_stats,
    }


def discover_user_ids() -> List[str]:
    if not USERS_DIR.exists():
        return []
    out: List[str] = []
    for p in USERS_DIR.iterdir():
        if not p.is_dir():
            continue
        if (p / "profile.json").exists():
            out.append(p.name)
    return sorted(out)


def average(values: List[float]) -> float:
    vals = [safe_float(v) for v in values if v is not None]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def build_global_learning_dashboard() -> Dict[str, Any]:
    user_ids = discover_user_ids()
    dashboards = [build_user_learning_dashboard(uid) for uid in user_ids]
    ft_stats = fine_tune_stats()

    topics_current: Dict[str, List[float]] = {k: [] for k in DASHBOARD_TOPIC_META}
    topics_previous: Dict[str, List[float]] = {k: [] for k in DASHBOARD_TOPIC_META}

    total_runs_7 = 0
    total_runs_30 = 0
    total_runs_all = 0
    accepted_7 = 0
    accepted_30 = 0
    accepted_all = 0
    premium_7 = 0
    premium_30 = 0
    premium_all = 0

    for d in dashboards:
        l7 = safe_dict(d.get("last_7_days"))
        l30 = safe_dict(d.get("last_30_days"))
        all_time = safe_dict(d.get("all_time"))

        total_runs_7 += int(l7.get("total_training_runs", 0))
        total_runs_30 += int(l30.get("total_training_runs", 0))
        total_runs_all += int(all_time.get("total_training_runs", 0))

        accepted_7 += int(l7.get("accepted_learnings", 0))
        accepted_30 += int(l30.get("accepted_learnings", 0))
        accepted_all += int(all_time.get("accepted_learnings", 0))

        premium_7 += int(l7.get("premium_learnings", 0))
        premium_30 += int(l30.get("premium_learnings", 0))
        premium_all += int(all_time.get("premium_learnings", 0))

        topics = safe_dict(d.get("topics"))
        for key in DASHBOARD_TOPIC_META:
            row = safe_dict(topics.get(key))
            topics_current[key].append(safe_float(row.get("current_score", 0.0)))
            topics_previous[key].append(safe_float(row.get("previous_score", 0.0)))

    aggregated_current = {k: round(clamp_float(average(v), 0.0, 1.0, 0.0), 4) for k, v in topics_current.items()}
    aggregated_previous = {k: round(clamp_float(average(v), 0.0, 1.0, 0.0), 4) for k, v in topics_previous.items()}
    topic_report = build_topic_report(aggregated_current, aggregated_previous)

    overall_cur = overall_score_from_topics(aggregated_current)
    overall_prev = overall_score_from_topics(aggregated_previous)
    overall_growth = growth_percent(overall_prev, overall_cur)

    def pack_window(runs: int, accepted: int, premium: int) -> Dict[str, Any]:
        return {
            "overall_growth_percent": overall_growth,
            "total_training_runs": runs,
            "accepted_learnings": accepted,
            "premium_learnings": premium,
            "elite_candidates": int(ft_stats.get("elite_candidates", 0)),
            "fine_tune_candidates": int(ft_stats.get("total_candidates", 0)),
        }

    return {
        "scope": "global",
        "generated_at": now_iso(),
        "user_count": len(user_ids),
        "last_7_days": pack_window(total_runs_7, accepted_7, premium_7),
        "last_30_days": pack_window(total_runs_30, accepted_30, premium_30),
        "all_time": pack_window(total_runs_all, accepted_all, premium_all),
        "total_training_runs": total_runs_all,
        "accepted_learnings": accepted_all,
        "premium_learnings": premium_all,
        "elite_candidates": int(ft_stats.get("elite_candidates", 0)),
        "fine_tune_candidates": int(ft_stats.get("total_candidates", 0)),
        "topics": topic_report["topics"],
        "weak_areas": topic_report["weak_areas"],
        "strong_areas": topic_report["strong_areas"],
        "fine_tune": ft_stats,
    }


def dashboard_html(global_dashboard: Dict[str, Any]) -> str:
    l7 = safe_dict(global_dashboard.get("last_7_days"))
    l30 = safe_dict(global_dashboard.get("last_30_days"))
    all_time = safe_dict(global_dashboard.get("all_time"))
    topics = safe_dict(global_dashboard.get("topics"))
    weak = safe_list(global_dashboard.get("weak_areas"))
    strong = safe_list(global_dashboard.get("strong_areas"))
    fine = safe_dict(global_dashboard.get("fine_tune"))

    rows = []
    for key, item in topics.items():
        row = safe_dict(item)
        status = str(row.get("status", "improving"))
        status_color = {
            "weak": "#D97070",
            "improving": "#D5B66A",
            "strong": "#8BC28B",
            "elite": "#6EC1E4",
        }.get(status, "#D5B66A")
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('label', key)))}</td>"
            f"<td>{row.get('previous_score', 0):.2f}</td>"
            f"<td>{row.get('current_score', 0):.2f}</td>"
            f"<td>{int(row.get('growth_percent', 0))}%</td>"
            f"<td style='color:{status_color};font-weight:600'>{html.escape(status)}</td>"
            f"<td>{html.escape(str(row.get('recommendation', '')))}</td>"
            "</tr>"
        )
    topic_rows_html = "\n".join(rows) or "<tr><td colspan='6'>Veri yok</td></tr>"

    def weak_item(x: Dict[str, Any]) -> str:
        return (
            f"<li><b>{html.escape(str(x.get('label', x.get('topic', ''))))}</b> "
            f"(skor: {safe_float(x.get('score'), 0.0):.2f}) - "
            f"{html.escape(str(x.get('recommendation', '')))}</li>"
        )

    weak_html = "\n".join(weak_item(safe_dict(x)) for x in weak[:5]) or "<li>Belirgin zayıf alan yok.</li>"
    strong_html = "\n".join(
        f"<li><b>{html.escape(str(safe_dict(x).get('label', '')))}</b> "
        f"(skor: {safe_float(safe_dict(x).get('score'), 0.0):.2f})</li>"
        for x in strong[:5]
    ) or "<li>Belirgin güçlü alan yok.</li>"

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Luxviai Learning Dashboard</title>
  <style>
    body {{ background:#070707; color:#E8E5DF; font-family:Inter,Arial,sans-serif; margin:0; padding:22px; }}
    h1 {{ color:#ED9107; font-weight:500; margin:0 0 6px; letter-spacing:.6px; }}
    .muted {{ color:#9AA3A6; font-size:.85rem; margin-bottom:14px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; margin-bottom:14px; }}
    .card {{ border:1px solid rgba(237,145,7,.26); border-radius:10px; padding:12px; background:#0A0A0A; }}
    .label {{ color:#AEB5B8; font-size:.78rem; }}
    .value {{ font-size:1.2rem; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; background:#0A0A0A; border:1px solid rgba(237,145,7,.22); }}
    th,td {{ border-bottom:1px solid rgba(255,255,255,.08); padding:8px; font-size:.82rem; vertical-align:top; }}
    th {{ color:#F5D68A; text-align:left; font-weight:500; }}
    .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px; }}
    ul {{ margin:8px 0 0 18px; padding:0; }}
    li {{ margin:4px 0; color:#D7D2C6; font-size:.82rem; }}
  </style>
</head>
<body>
  <h1>Luxviai Learning Dashboard</h1>
  <div class="muted">Oluşturulma: {html.escape(str(global_dashboard.get("generated_at", now_iso())))}</div>

  <div class="grid">
    <div class="card"><div class="label">Son 7 gün genel gelişim</div><div class="value">{int(l7.get("overall_growth_percent", 0))}%</div></div>
    <div class="card"><div class="label">Son 30 gün genel gelişim</div><div class="value">{int(l30.get("overall_growth_percent", 0))}%</div></div>
    <div class="card"><div class="label">Toplam eğitim koşusu</div><div class="value">{int(all_time.get("total_training_runs", 0))}</div></div>
    <div class="card"><div class="label">Kabul edilen öğrenme</div><div class="value">{int(all_time.get("accepted_learnings", 0))}</div></div>
    <div class="card"><div class="label">Premium öğrenme</div><div class="value">{int(all_time.get("premium_learnings", 0))}</div></div>
    <div class="card"><div class="label">Elite aday</div><div class="value">{int(global_dashboard.get("elite_candidates", 0))}</div></div>
  </div>

  <table>
    <thead>
      <tr><th>Konu</th><th>Önceki</th><th>Güncel</th><th>Gelişim</th><th>Durum</th><th>Öneri</th></tr>
    </thead>
    <tbody>{topic_rows_html}</tbody>
  </table>

  <div class="cols">
    <div class="card"><div class="label">Zayıf alanlar</div><ul>{weak_html}</ul></div>
    <div class="card"><div class="label">Güçlü alanlar</div><ul>{strong_html}</ul></div>
  </div>

  <div class="grid" style="margin-top:10px">
    <div class="card"><div class="label">Fine-tune aday toplamı</div><div class="value">{int(fine.get("total_candidates", 0))}</div></div>
    <div class="card"><div class="label">Pending aday</div><div class="value">{int(fine.get("pending_candidates", 0))}</div></div>
    <div class="card"><div class="label">Rejected aday</div><div class="value">{int(fine.get("rejected_candidates", 0))}</div></div>
    <div class="card"><div class="label">Son aday zamanı</div><div class="value" style="font-size:.86rem">{html.escape(str(fine.get("last_candidate_created_at", "-")))}</div></div>
  </div>
</body>
</html>"""


# =========================================================
# ROUTES
# =========================================================
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": "luxviai",
        "api_available": client is not None,
        "analysis_layers": ANALYSIS_LAYER_NAMES,
    }


@app.get("/learning-dashboard")
async def learning_dashboard():
    # Varsayılan dashboard: global görünüm
    return learning_dashboard_engine.build_global_dashboard()


@app.get("/global-learning-dashboard")
async def global_learning_dashboard():
    return learning_dashboard_engine.build_global_dashboard()


@app.get("/user-performance-dashboard")
async def user_performance_dashboard(user_id: str = "default_user"):
    return learning_dashboard_engine.build_user_performance_dashboard(safe_user_id(user_id))


@app.get("/learning-dashboard/html")
async def learning_dashboard_html():
    return HTMLResponse(content=learning_dashboard_engine.render_html())


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/notes")
async def get_notes(user_id: str = "default_user"):
    profile, notes, garden = load_user_state(user_id)
    return {"items": notes[-100:]}


@app.post("/notes")
async def add_note(payload: NoteCreate, auth: Optional[str] = Header(None)):
    check_auth(auth)
    user_id = safe_user_id(payload.user_id)
    profile, notes, garden = load_user_state(user_id)
    note = {
        "id": uuid.uuid4().hex[:10],
        "text": payload.text.strip(),
        "created_at": now_iso(),
    }
    notes.append(note)
    notes[:] = notes[-300:]
    save_user_state(user_id, profile, notes, garden)
    return {"ok": True, "note": note}


@app.delete("/notes")
async def clear_notes(user_id: str = "default_user", auth: Optional[str] = Header(None)):
    check_auth(auth)
    user_id = safe_user_id(user_id)
    profile, notes, garden = load_user_state(user_id)
    notes.clear()
    save_user_state(user_id, profile, notes, garden)
    return {"ok": True}


@app.delete("/notes/{note_id}")
async def delete_note(note_id: str, user_id: str = "default_user", auth: Optional[str] = Header(None)):
    check_auth(auth)
    user_id = safe_user_id(user_id)
    profile, notes, garden = load_user_state(user_id)
    before = len(notes)
    notes = [n for n in notes if n.get("id") != note_id]
    save_user_state(user_id, profile, notes, garden)
    return {"ok": True, "deleted": before - len(notes)}


@app.get("/memory")
async def memory(user_id: str = "default_user"):
    user_id = safe_user_id(user_id)
    profile, notes, garden = load_user_state(user_id)
    session = load_current_session(user_id)

    items = []
    for item in reversed(garden[-30:]):
        text = item.get("text", "")
        theme = item.get("theme", "belirsiz")
        emotion = item.get("emotion", "nötr")
        if not has_thematic_signal(text) and theme == "belirsiz" and emotion == "nötr":
            continue
        items.append({
            "source": "memory",
            "text": text,
            "theme": theme,
            "emotion": emotion,
            "layers": item.get("layers", {}),
            "ts": item.get("ts", ""),
        })

    for msg in reversed(session.get("messages", [])[-10:]):
        if msg.get("role") == "user":
            text = msg.get("content", "")
            if not has_thematic_signal(text):
                continue
            items.append({
                "source": "session",
                "text": text,
                "theme": profile.get("core_trigger", "belirsiz") or "belirsiz",
                "emotion": "nötr",
                "ts": msg.get("ts", ""),
            })

    return {
        "items": items[:20],
        "analysis": build_memory_overview(profile, session, garden),
    }


@app.get("/agent/capabilities")
async def agent_capabilities():
    return {
        "personal_capabilities": personal_agent_capabilities(),
        "luxway_capabilities": luxway_capabilities(),
        "platform_permissions": {
            "android": ANDROID_PERMISSION_NOTES,
            "ios": IOS_PERMISSION_NOTES,
        },
        "privacy_rules": PRIVACY_RULES,
        "all_capabilities": all_capabilities(),
    }


@app.get("/memory/schema")
async def memory_schema():
    return {
        "schema": multimodal_memory_schema(),
        "templates": MULTIMODAL_MEMORY_TEMPLATES[:],
        "required_fields": DEFAULT_MEMORY_FIELDS,
    }


@app.post("/memory/preview_signal")
async def preview_memory_signal(payload: MemorySignalPreviewRequest):
    signal = build_memory_signal(payload.dict())
    result = validate_memory_signal(signal)
    # preview path only; persistence is explicitly deferred.
    return {
        "ok": result.get("ok"),
        "signal": result.get("signal"),
        "errors": result.get("errors"),
        "checks": result.get("checks"),
        "privacy_notes": PRIVACY_RULES,
    }


@app.post("/agent/preview_intent")
async def preview_agent_intent_endpoint(payload: AgentIntentPreviewRequest):
    agent_preview = preview_agent_intent(payload.text)
    memory_preview = preview_memory_signals(payload.text, payload.source_modality)
    return {
        "agent_preview": agent_preview,
        "memory_preview": memory_preview,
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.post("/agent/plan_action")
async def plan_agent_action_endpoint(payload: AgentIntentPreviewRequest):
    return {
        "action_plan": plan_agent_action(payload.text),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.post("/agent/analyze")
async def analyze_agent_endpoint(payload: AgentIntentPreviewRequest):
    return {
        "analysis": analyze_agent_request(payload.text, payload.source_modality),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.post("/router/preview")
async def router_preview_endpoint(payload: AgentIntentPreviewRequest):
    return {
        "router_preview": preview_router_decision(payload.text, payload.source_modality),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


def _debug_agent_sample(sample_text: str) -> Dict[str, Any]:
    return {
        "sample_text": sample_text,
        "agent_analysis": analyze_agent_request(sample_text, "text"),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


def _debug_router_sample(sample_text: str) -> Dict[str, Any]:
    return {
        "sample_text": sample_text,
        "router_preview": preview_router_decision(sample_text, "text"),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.get("/debug/agent/sample-email")
async def debug_agent_sample_email():
    return _debug_agent_sample("Maillerimi \u00f6zetle ve \u00f6nemli olanlar\u0131 ay\u0131r.")


@app.get("/debug/agent/sample-luxway")
async def debug_agent_sample_luxway():
    return _debug_agent_sample("Telefonu tara, kullan\u0131lmayan uygulamalar\u0131 ve \u00e7ok yer kaplayanlar\u0131 bul.")


@app.get("/debug/agent/sample-visual")
async def debug_agent_sample_visual():
    return _debug_agent_sample("Bu g\u00f6rselde amber \u0131\u015f\u0131k, d\u00fc\u015f\u00fck \u00e7izgi yo\u011funlu\u011fu ve sa\u011f alt Luxviai imzas\u0131n\u0131 seviyorum.")


@app.get("/debug/agent/sample-dream")
async def debug_agent_sample_dream():
    return _debug_agent_sample("R\u00fcyamda deniz kenar\u0131nda u\u00e7an insanlar, ay ve ya\u011fmur vard\u0131; bunu g\u00f6rselle\u015ftir.")


@app.get("/debug/router/sample-cv")
async def debug_router_sample_cv():
    return _debug_router_sample("CV haz\u0131rla, eksik alanlar\u0131 bana sor ve profesyonel T\u00fcrk\u00e7e yap.")


@app.get("/debug/mode-registry")
async def debug_mode_registry():
    return {
        "modes": mode_registry(),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.get("/debug/mode-preview")
async def debug_mode_preview_get(q: str = Query("", max_length=500)):
    return {
        "mode_preview": preview_mode_command(q),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.post("/debug/mode-preview")
async def debug_mode_preview_post(payload: AgentIntentPreviewRequest):
    return {
        "mode_preview": preview_mode_command(payload.text),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.get("/debug/permission-preview")
async def debug_permission_preview_get(q: str = Query("", max_length=500)):
    return {
        "permission_preview": preview_permission_boundary(q),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.post("/debug/permission-preview")
async def debug_permission_preview_post(payload: AgentIntentPreviewRequest):
    return {
        "permission_preview": preview_permission_boundary(payload.text),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.get("/debug/agent-decision-trace")
async def debug_agent_decision_trace_get(q: str = Query("", max_length=500)):
    return {
        "decision_trace": build_agent_decision_trace(q),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


@app.post("/debug/agent-decision-trace")
async def debug_agent_decision_trace_post(payload: AgentIntentPreviewRequest):
    return {
        "decision_trace": build_agent_decision_trace(payload.text),
        "read_only": True,
        "raw_data_stored": False,
        "write_performed": False,
    }


def _layer14_status() -> Dict[str, Any]:
    return {
        "layer": "14",
        "name": "Personal Agent + Multimodal Memory + Router + Command-first scaffold",
        "status": "scaffold_ready",
        "read_only": True,
        "real_actions_enabled": False,
        "memory_writes_enabled": False,
        "chat_stream_touched": False,
        "completed_parts": [
            "14.1 capabilities/schema",
            "14.2 intent/memory preview",
            "14.3 action plan",
            "14.4 analysis hub",
            "14.5 router preview",
            "14.6 debug samples",
            "14.7 agent panel",
            "14.8 mode registry",
            "14.9 permission boundary",
            "14.10 decision trace",
        ],
        "important_backlog": [
            "stop/durdur final block leak",
        ],
    }


@app.get("/debug/layer14-status")
async def debug_layer14_status():
    return _layer14_status()


def _workspace_status() -> Dict[str, Any]:
    return {
        "layer": "15",
        "name": "LuxWorkspace scaffold",
        "status": "scaffold_ready",
        "read_only": True,
        "real_editor_enabled": False,
        "real_export_enabled": False,
        "file_write_enabled": False,
        "db_write_enabled": False,
        "memory_write_enabled": False,
        "chat_stream_touched": False,
        "completed_parts": [
            "15.1 schema + block model",
            "15.2 command/content separation",
            "15.3 command parser",
            "15.4 export-clean preview",
            "15.5 evaluator/context notes",
            "15.6 builder preview",
        ],
        "available_endpoints": [
            "/workspace/schema",
            "/debug/workspace/sample",
            "/workspace/preview",
            "/workspace/separation-preview",
            "/workspace/parse-command",
            "/workspace/export-preview",
            "/workspace/context-preview",
            "/workspace/builder-preview",
        ],
        "next_recommended_step": "15.8 later real export/file integration or move to Layer 16 visual scaffold",
        "backlog": [
            "stop/durdur final block leak",
        ],
    }


@app.get("/debug/workspace-status")
async def debug_workspace_status():
    return _workspace_status()


@app.get("/workspace/schema")
async def workspace_schema_endpoint():
    return workspace_schema()


@app.get("/debug/workspace/sample")
async def debug_workspace_sample():
    return sample_workspace()


@app.post("/workspace/preview")
async def workspace_preview(payload: WorkspacePreviewRequest):
    return build_workspace_preview(payload.command, payload.content)


@app.post("/workspace/separation-preview")
async def workspace_separation_preview(payload: WorkspacePreviewRequest):
    return build_workspace_separation_preview(payload.command, payload.content)


@app.post("/workspace/parse-command")
async def workspace_parse_command(payload: WorkspaceCommandParseRequest):
    return parse_workspace_command(payload.command, payload.current_blocks)


@app.post("/workspace/export-preview")
async def workspace_export_preview(payload: WorkspaceExportPreviewRequest):
    return build_workspace_export_preview(payload.blocks, payload.export_type)


@app.post("/workspace/context-preview")
async def workspace_context_preview(payload: WorkspaceContextPreviewRequest):
    return preview_workspace_context_note(payload.context_note, payload.project_type, payload.current_blocks)


@app.post("/workspace/builder-preview")
async def workspace_builder_preview(payload: WorkspaceBuilderPreviewRequest):
    return build_workspace_builder_preview(payload.command, payload.content, payload.context_note, payload.project_type)


@app.get("/visual/styles")
async def visual_styles_endpoint():
    return visual_style_registry()


@app.post("/visual/style-preview")
async def visual_style_preview_endpoint(payload: VisualStylePreviewRequest):
    return preview_visual_style(payload.prompt, payload.requested_styles, payload.mode)


@app.post("/visual/ratio-preview")
async def visual_ratio_preview_endpoint(payload: VisualStyleRatioPreviewRequest):
    return preview_visual_style_ratio(payload.prompt, payload.ratio_text, payload.requested_styles, payload.mode)


@app.post("/visual/ambrosia-preview")
async def visual_ambrosia_preview_endpoint(payload: VisualAmbrosiaPreviewRequest):
    return preview_ambrosia_state(payload.feeling_text, payload.intensity, payload.style_ratio)


@app.post("/visual/dream-scene-preview")
async def visual_dream_scene_preview_endpoint(payload: VisualDreamScenePreviewRequest):
    return preview_dream_scene_state(payload.scene_text, payload.style_hint, payload.locked_elements)


@app.post("/visual/scene-lock-preview")
async def visual_scene_lock_preview_endpoint(payload: VisualSceneLockPreviewRequest):
    return preview_scene_lock(payload.current_scene_state, payload.new_detail, payload.lock_strength)


@app.post("/visual/prompt-preview")
async def visual_prompt_preview_endpoint(payload: VisualPromptPreviewRequest):
    return build_visual_prompt_preview(
        payload.prompt,
        payload.mode,
        payload.style_ratios,
        payload.scene_state,
        payload.ambrosia_state,
        payload.locked_elements,
    )


@app.get("/debug/visual-status")
async def debug_visual_status():
    return {
        "layer": "16",
        "name": "Lux Visual System scaffold",
        "status": "scaffold_ready",
        "read_only": True,
        "image_generation_enabled": False,
        "image_api_enabled": False,
        "file_write_enabled": False,
        "db_write_enabled": False,
        "memory_write_enabled": False,
        "chat_stream_touched": False,
        "completed_parts": [
            "16.1 visual style registry",
            "16.1B full visual registry expansion",
            "16.2 style ratio preview",
            "16.3 Ambrosia state preview",
            "16.4 Dream Scene state preview",
            "16.5 Scene Lock preview",
            "16.6 visual prompt builder",
            "16.6B prompt builder full registry sync",
        ],
        "available_endpoints": [
            "/visual/styles",
            "/visual/style-preview",
            "/visual/ratio-preview",
            "/visual/ambrosia-preview",
            "/visual/dream-scene-preview",
            "/visual/scene-lock-preview",
            "/visual/prompt-preview",
        ],
        "core_visual_rules": [
            "Lux amber #ab6b0c",
            "black velvet #0A0A0A",
            "platinum #C0C0C0",
            "default low line density",
            "bottom-right Luxviai signature default",
            "Ambrosia is inner state, not place",
            "no city/room/building/writing/signage for Ambrosia",
            "Dream Scene details must be added without rebuilding the scene",
        ],
        "next_recommended_step": "Layer 17 Voice / Audio / Frequency scaffold",
        "later_step": "16.7 real Image API integration later",
        "backlog": [
            "stop/durdur final block leak",
        ],
    }


@app.get("/voice/modes")
async def voice_modes_endpoint():
    return voice_mode_registry()


@app.post("/voice/preview-mode")
async def voice_preview_mode_endpoint(payload: VoiceModePreviewRequest):
    return preview_voice_mode(payload.command, payload.context, payload.response_size, payload.input_modality)


@app.post("/voice/night-radio-preview")
async def voice_night_radio_preview_endpoint(payload: NightRadioVoicePreviewRequest):
    return preview_night_radio_voice(payload.text, payload.mood, payload.response_size, payload.mode)


@app.get("/debug/voice-status")
async def debug_voice_status():
    return voice_status_snapshot()


@app.get("/debug/voice-audio-status")
async def debug_voice_audio_status():
    return {
        "layer": "17",
        "name": "Voice / Audio / Frequency scaffold",
        "status": "scaffold_ready",
        "read_only": True,
        "real_tts_enabled": False,
        "real_stt_enabled": False,
        "real_audio_enabled": False,
        "microphone_enabled": False,
        "recording_enabled": False,
        "file_write_enabled": False,
        "db_write_enabled": False,
        "memory_write_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "completed_parts": [
            "17.1 voice + writing speed registry",
            "17.2 audio signal schema",
            "17.3 privacy-first audio boundary",
            "17.4 night radio voice preview",
        ],
        "available_endpoints": [
            "/voice/modes",
            "/voice/preview-mode",
            "/debug/voice-status",
            "/audio/signal-schema",
            "/audio/preview-signal",
            "/debug/audio-status",
            "/audio/privacy-boundary-preview",
            "/voice/night-radio-preview",
        ],
        "core_voice_rules": [
            "default writing speed 0.9",
            "quick summary speed 1.3",
            "very fast summary speed 1.5 only when explicitly requested",
            "long answers stay around 0.9 and do not exceed 1.1 unless explicitly requested",
            "smooth_typewriter true",
            "block_dump_allowed false",
            "final_bulk_injection_allowed false",
            "night radio speed 0.7-0.85",
            "input_modality voice is simulated metadata only",
            "no clinical diagnosis",
            "no raw audio stored",
        ],
        "next_recommended_step": "Layer 18 Luxway scaffold or later 17.6 real voice integration",
        "later_step": "17.6 real voice integration later",
        "backlog": [
            "stop/durdur final block leak",
        ],
    }


@app.get("/audio/signal-schema")
async def audio_signal_schema_endpoint():
    return audio_signal_schema()


@app.post("/audio/preview-signal")
async def audio_preview_signal_endpoint(payload: AudioSignalPreviewRequest):
    return preview_audio_signal(payload.description, payload.simulated_voice_note, payload.context)


@app.post("/audio/privacy-boundary-preview")
async def audio_privacy_boundary_preview_endpoint(payload: AudioPrivacyBoundaryRequest):
    return preview_audio_privacy_boundary(payload.command, payload.audio_context, payload.consent_state)


@app.get("/debug/audio-status")
async def debug_audio_status():
    return audio_status_snapshot()


@app.get("/router/model-config")
async def router_model_config_endpoint():
    return model_router_config()


@app.post("/router/model-preview")
async def router_model_preview_endpoint(payload: ModelRouterPreviewRequest):
    return preview_model_route(payload.command, payload.task_type, payload.sensitivity, payload.response_size)


@app.post("/router/hint-preview")
async def router_hint_preview_endpoint(payload: ModelRouterHintPreviewRequest):
    return preview_model_hint(payload.command, payload.source_area, payload.task_type, payload.sensitivity, payload.response_size)


@app.get("/router/cost-privacy-policy")
async def router_cost_privacy_policy_endpoint():
    return cost_privacy_policy()


@app.post("/router/cost-preview")
async def router_cost_preview_endpoint(payload: CostPrivacyPreviewRequest):
    return preview_cost_privacy(payload.command, payload.task_type, payload.sensitivity, payload.estimated_tokens_bucket)


@app.get("/router/safe-memory-policy")
async def router_safe_memory_policy_endpoint():
    return safe_memory_policy()


@app.post("/router/memory-retrieval-preview")
async def router_memory_retrieval_preview_endpoint(payload: SafeMemoryRetrievalPreviewRequest):
    return preview_safe_memory_retrieval(payload.command, payload.task_type, payload.sensitivity, payload.requested_memory_type)


@app.get("/debug/model-router-status")
async def debug_model_router_status():
    return model_router_status()


@app.get("/luxway/capabilities")
async def luxway_capabilities_endpoint():
    return luxway_capability_registry()


@app.get("/luxway/permission-model")
async def luxway_permission_model_endpoint():
    return luxway_permission_model()


@app.get("/luxway/weekly-report-schema")
async def luxway_weekly_report_schema_endpoint():
    return luxway_weekly_report_schema()


@app.post("/luxway/preview-command")
async def luxway_preview_command_endpoint(payload: LuxwayPreviewCommandRequest):
    return preview_luxway_command(payload.command, payload.platform, payload.context)


@app.post("/luxway/permission-preview")
async def luxway_permission_preview_endpoint(payload: LuxwayPermissionPreviewRequest):
    return preview_luxway_permission(payload.command, payload.platform)


@app.post("/luxway/weekly-report-preview")
async def luxway_weekly_report_preview_endpoint(payload: LuxwayWeeklyReportPreviewRequest):
    return preview_luxway_weekly_report(payload.platform, payload.report_focus, payload.context)


@app.post("/luxway/data-preview")
async def luxway_data_preview_endpoint(payload: LuxwayDataPreviewRequest):
    return preview_luxway_data(payload.command, payload.domain, payload.platform)


@app.post("/luxway/device-safety-preview")
async def luxway_device_safety_preview_endpoint(payload: LuxwayDeviceSafetyPreviewRequest):
    return preview_luxway_device_safety(payload.command, payload.platform)


@app.get("/debug/luxway-status")
async def debug_luxway_status():
    return luxway_status_snapshot()


@app.get("/debug/luxway-full-status")
async def debug_luxway_full_status():
    return {
        "layer": "18",
        "name": "Luxway scaffold",
        "status": "scaffold_ready",
        "read_only": True,
        "real_phone_access_enabled": False,
        "real_platform_api_enabled": False,
        "real_app_access_enabled": False,
        "real_storage_access_enabled": False,
        "real_message_access_enabled": False,
        "real_mail_access_enabled": False,
        "real_calendar_access_enabled": False,
        "real_notification_access_enabled": False,
        "real_call_enabled": False,
        "real_send_enabled": False,
        "real_delete_enabled": False,
        "file_write_enabled": False,
        "db_write_enabled": False,
        "memory_write_enabled": False,
        "chat_stream_touched": False,
        "typewriter_runtime_touched": False,
        "completed_parts": [
            "18.1 luxway capability preview",
            "18.2 android / ios permission model preview",
            "18.3 weekly phone report schema preview",
            "18.4 app / storage / message / mail / calendar preview",
            "18.5 device safety boundary preview",
        ],
        "available_endpoints": [
            "/luxway/capabilities",
            "/luxway/preview-command",
            "/debug/luxway-status",
            "/luxway/permission-model",
            "/luxway/permission-preview",
            "/luxway/weekly-report-schema",
            "/luxway/weekly-report-preview",
            "/luxway/data-preview",
            "/luxway/device-safety-preview",
        ],
        "core_luxway_rules": [
            "requires_permission for private phone/app/mail/calendar/message/storage access",
            "requires_confirmation for send/delete/call/settings/cleanup actions",
            "real_access_enabled false",
            "data_read false",
            "data_written false",
            "action_performed false",
            "no fabricated phone/app/mail/calendar metrics",
            "risky actions blocked by default",
            "Android/iOS platform model is preview-only",
        ],
        "next_recommended_step": "Layer 19 Model Router / Cost Efficiency scaffold",
        "later_step": "18.6 real platform integration later",
        "backlog": [
            "stop/durdur final block leak",
        ],
    }


@app.get("/debug/agent-panel")
async def debug_agent_panel():
    html_doc = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Luxviai Agent Debug Panel</title>
  <style>
    :root { color-scheme: dark; --bg: #101010; --panel: #181818; --line: #333; --amber: #ab6b0c; --text: #f4efe7; --muted: #b7ada0; }
    body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 20px; }
    h1 { margin: 0 0 8px; font-size: 28px; font-weight: 700; letter-spacing: 0; }
    .note { margin: 0 0 22px; color: var(--muted); line-height: 1.5; }
    h2 { margin: 22px 0 10px; font-size: 18px; font-weight: 650; letter-spacing: 0; }
    .bar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
    button { border: 1px solid var(--line); background: #202020; color: var(--text); padding: 10px 13px; border-radius: 8px; cursor: pointer; font: inherit; }
    button:hover, button:focus { border-color: var(--amber); outline: 2px solid rgba(171, 107, 12, 0.25); }
    pre { min-height: 420px; overflow: auto; margin: 0; padding: 18px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: #f8f2e9; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
    .status { color: var(--amber); margin: 0 0 10px; font-size: 14px; }
  </style>
</head>
<body>
  <main>
    <h1>Luxviai Agent Debug Panel</h1>
    <p class="note">Read-only scaffold preview. No real action is executed. No raw data is stored.</p>
    <h2>Layer 14 Status</h2>
    <div class="bar">
      <button data-endpoint="/debug/layer14-status">Layer 14 Status</button>
    </div>
    <h2>Workspace Preview</h2>
    <div class="bar">
      <button data-endpoint="/debug/workspace-status">Workspace Status</button>
    </div>
    <div class="bar">
      <button data-workspace-command="CV haz\u0131rla">CV haz\u0131rla</button>
      <button data-workspace-command="rapor yaz">rapor yaz</button>
      <button data-workspace-command="sunuma \u00e7evir">sunuma \u00e7evir</button>
      <button data-workspace-command="3. paragraf\u0131 akademikle\u015ftir">3. paragraf\u0131 akademikle\u015ftir</button>
      <button data-workspace-command="bu metni sonu\u00e7 b\u00f6l\u00fcm\u00fcne uygun hale getir">sonu\u00e7 b\u00f6l\u00fcm\u00fc</button>
    </div>
    <div class="bar">
      <button data-workspace-separation-command="3. paragraf\u0131 akademikle\u015ftir">Separation: akademikle\u015ftir</button>
      <button data-workspace-separation-command="bu metni rapora \u00e7evir">Separation: rapor</button>
      <button data-workspace-separation-command="sunuma \u00e7evir">Separation: sunum</button>
      <button data-workspace-separation-command="CV haz\u0131rla">Separation: CV</button>
      <button data-workspace-separation-command="sesli komut: giri\u015f b\u00f6l\u00fcm\u00fcn\u00fc k\u0131salt">Separation: sesli komut</button>
    </div>
    <div class="bar">
      <button data-workspace-parse-command="CV haz\u0131rla">Parser: CV</button>
      <button data-workspace-parse-command="3. paragraf\u0131 akademikle\u015ftir">Parser: paragraf 3</button>
      <button data-workspace-parse-command="bu iki paragraf aras\u0131na ge\u00e7i\u015f c\u00fcmlesi ekle">Parser: ge\u00e7i\u015f</button>
      <button data-workspace-parse-command="k\u0131salt">Parser: k\u0131salt</button>
      <button data-workspace-parse-command="sunuma \u00e7evir">Parser: sunum</button>
      <button data-workspace-parse-command="bu k\u0131sm\u0131 sonu\u00e7 b\u00f6l\u00fcm\u00fcne uygun hale getir">Parser: sonu\u00e7</button>
    </div>
    <div class="bar">
      <button data-workspace-export-type="copy">Export: copy preview</button>
      <button data-workspace-export-type="pdf">Export: pdf preview</button>
      <button data-workspace-export-type="word">Export: word preview</button>
      <button data-workspace-export-type="presentation">Export: presentation preview</button>
    </div>
    <div class="bar">
      <button data-workspace-context-note="Bu hoca ayr\u0131nt\u0131l\u0131 cevap sever.">Context: ayr\u0131nt\u0131l\u0131</button>
      <button data-workspace-context-note="Tekrar g\u00f6rmeyi sevmez.">Context: tekrar</button>
      <button data-workspace-context-note="Kaynak eksikli\u011finden puan k\u0131r\u0131yor.">Context: kaynak</button>
      <button data-workspace-context-note="Giri\u015f g\u00fc\u00e7l\u00fc olmal\u0131.">Context: giri\u015f</button>
      <button data-workspace-context-note="\u00d6nceki \u00f6\u011frenciler y\u00f6ntem k\u0131sm\u0131nda zorland\u0131.">Context: y\u00f6ntem</button>
    </div>
    <div class="bar">
      <button data-workspace-builder-command="CV haz\u0131rla">Builder: CV</button>
      <button data-workspace-builder-command="rapor yaz">Builder: rapor</button>
      <button data-workspace-builder-command="sunuma \u00e7evir">Builder: sunum</button>
      <button data-workspace-builder-command="\u00f6devim var">Builder: \u00f6dev</button>
      <button data-workspace-builder-command="bu metni sunuma \u00e7evir">Builder: metni sunuma \u00e7evir</button>
    </div>
    <h2>Visual Style Preview</h2>
    <div class="bar">
      <button data-endpoint="/debug/visual-status">Visual Status</button>
    </div>
    <div class="bar">
      <button data-visual-style-prompt="Lux tarz\u0131 yap">Lux tarz\u0131 yap</button>
      <button data-visual-style-prompt="normal ger\u00e7ek\u00e7i temiz">normal ger\u00e7ek\u00e7i temiz</button>
      <button data-visual-style-prompt="%40 ya\u011fl\u0131 boya %20 pixel">%40 ya\u011fl\u0131 boya %20 pixel</button>
      <button data-visual-style-prompt="Ambrosia hissi">Ambrosia hissi</button>
      <button data-visual-style-prompt="r\u00fcya sahnesi">r\u00fcya sahnesi</button>
      <button data-visual-style-prompt="soft neon vintage">soft neon vintage</button>
    </div>
    <div class="bar">
      <button data-visual-ratio-prompt="%40 ya\u011fl\u0131 boya %20 pixel">Ratio: boya/pixel</button>
      <button data-visual-ratio-prompt="pixel %5 azalt amber %10 art\u0131r">Ratio: pixel azalt amber art\u0131r</button>
      <button data-visual-ratio-prompt="Lux tarz\u0131 ama ger\u00e7ek\u00e7i temiz">Ratio: Lux ger\u00e7ek\u00e7i</button>
      <button data-visual-ratio-prompt="soft neon vintage">Ratio: neon vintage</button>
      <button data-visual-ratio-prompt="Ambrosia hissi">Ratio: Ambrosia</button>
    </div>
    <div class="bar">
      <button data-ambrosia-feeling="i\u00e7imde sessiz ama a\u011f\u0131r bir yorgunluk var">Ambrosia: yorgunluk</button>
      <button data-ambrosia-feeling="umut var ama \u00e7ok k\u0131r\u0131lgan">Ambrosia: k\u0131r\u0131lgan umut</button>
      <button data-ambrosia-feeling="kafam kar\u0131\u015f\u0131k ama i\u00e7imde k\u00fc\u00e7\u00fck bir \u0131\u015f\u0131k var">Ambrosia: k\u00fc\u00e7\u00fck \u0131\u015f\u0131k</button>
      <button data-ambrosia-feeling="ruhani, siyah ve amber bir his">Ambrosia: ruhani amber</button>
      <button data-ambrosia-feeling="bo\u015flukta as\u0131l\u0131 kalm\u0131\u015f gibi">Ambrosia: bo\u015fluk</button>
    </div>
    <div class="bar">
      <button data-dream-scene="Karanl\u0131k bir denizde k\u00fc\u00e7\u00fck bir sandal var, uzakta amber bir \u0131\u015f\u0131k g\u00f6r\u00fcn\u00fcyor.">Dream: deniz sandal</button>
      <button data-dream-scene="Bir odada de\u011filim, bo\u015flukta y\u00fcr\u00fcyormu\u015f gibiyim.">Dream: bo\u015flukta y\u00fcr\u00fcme</button>
      <button data-dream-scene="Elimde k\u00fc\u00e7\u00fck bir kase var, ba\u015f\u0131m hafif sola d\u00f6n\u00fck.">Dream: kase ve ba\u015f</button>
      <button data-dream-scene="R\u00fcyamda merdivenlerden \u00e7\u0131k\u0131yorum ama yukar\u0131 hi\u00e7 bitmiyor.">Dream: bitmeyen merdiven</button>
      <button data-dream-scene="G\u00f6ky\u00fcz\u00fcnde ince semboller vard\u0131.">Dream: g\u00f6ky\u00fcz\u00fc semboller</button>
    </div>
    <div class="bar">
      <button data-scene-lock-detail="ba\u015f\u0131n\u0131 biraz sola \u00e7evir">Scene Lock: ba\u015f sola</button>
      <button data-scene-lock-detail="elindeki kaseyi koru">Scene Lock: kaseyi koru</button>
      <button data-scene-lock-detail="amber \u0131\u015f\u0131k biraz daha uzaktan gelsin">Scene Lock: amber uzak</button>
      <button data-scene-lock-detail="g\u00f6ky\u00fcz\u00fcndeki sembolleri azalt">Scene Lock: sembol azalt</button>
      <button data-scene-lock-detail="sahneyi de\u011fi\u015ftirme, sadece sa\u011f tarafa k\u00fc\u00e7\u00fck bir kap\u0131 ekle">Scene Lock: sa\u011f kap\u0131</button>
    </div>
    <div class="bar">
      <button data-visual-prompt="Lux tarz\u0131 karanl\u0131k sahne">Prompt: Lux karanl\u0131k</button>
      <button data-visual-prompt="Ambrosia: i\u00e7imde k\u0131r\u0131lgan umut var">Prompt: Ambrosia umut</button>
      <button data-visual-prompt="R\u00fcya: karanl\u0131k denizde k\u00fc\u00e7\u00fck sandal">Prompt: r\u00fcya sandal</button>
      <button data-visual-prompt="%40 ya\u011fl\u0131 boya %20 pixel amber \u0131\u015f\u0131k">Prompt: boya pixel</button>
      <button data-visual-prompt="sahneyi koru, sa\u011f tarafa k\u00fc\u00e7\u00fck kap\u0131 ekle">Prompt: scene lock kap\u0131</button>
    </div>
    <h2>Voice / Speed Preview</h2>
    <div class="bar">
      <button data-endpoint="/debug/voice-audio-status">Voice Audio Status</button>
    </div>
    <div class="bar">
      <button data-endpoint="/debug/voice-status">Voice Status</button>
      <button data-endpoint="/voice/modes">Voice Modes</button>
    </div>
    <div class="bar">
      <button data-voice-command="daha yava\u015f yaz" data-voice-size="medium">daha yava\u015f yaz</button>
      <button data-voice-command="h\u0131zl\u0131 \u00f6zetle" data-voice-size="short">h\u0131zl\u0131 \u00f6zetle</button>
      <button data-voice-command="\u00e7ok h\u0131zl\u0131 \u00f6zet" data-voice-size="short">\u00e7ok h\u0131zl\u0131 \u00f6zet</button>
      <button data-voice-command="gece radyosu gibi konu\u015f" data-voice-size="medium">gece radyosu gibi konu\u015f</button>
      <button data-voice-command="workspace uzun cevap" data-voice-size="workspace_large">workspace uzun cevap</button>
      <button data-voice-command="normal h\u0131za d\u00f6n" data-voice-size="medium">normal h\u0131za d\u00f6n</button>
      <button data-voice-command="sadece yaz\u0131, ses yok" data-voice-size="medium">sadece yaz\u0131, ses yok</button>
    </div>
    <div class="bar">
      <button data-night-radio-text="gece radyosu gibi anlat" data-night-radio-size="medium">Night Radio: anlat</button>
      <button data-night-radio-text="bu metni sakin podcast tonu yap" data-night-radio-size="medium">Night Radio: podcast</button>
      <button data-night-radio-text="uyumadan \u00f6nce yava\u015f anlat" data-night-radio-size="long">Night Radio: uyku</button>
      <button data-night-radio-text="daha yumu\u015fak ve d\u00fc\u015f\u00fck ton" data-night-radio-size="medium">Night Radio: yumu\u015fak</button>
      <button data-night-radio-text="sadece yaz\u0131 ama gece radyosu hissi" data-night-radio-size="medium">Night Radio: text only</button>
    </div>
    <h2>Audio Signal Preview</h2>
    <div class="bar">
      <button data-endpoint="/debug/audio-status">Audio Status</button>
      <button data-endpoint="/audio/signal-schema">Audio Signal Schema</button>
    </div>
    <div class="bar">
      <button data-audio-description="sesim yorgun gibi">sesim yorgun gibi</button>
      <button data-audio-description="h\u0131zl\u0131 ve panik konu\u015fuyorum">h\u0131zl\u0131 ve panik konu\u015fuyorum</button>
      <button data-audio-description="daha sakin bir tona ge\u00e7">daha sakin bir tona ge\u00e7</button>
      <button data-audio-description="gece radyosu gibi yava\u015flat">gece radyosu gibi yava\u015flat</button>
      <button data-audio-description="enerjim d\u00fc\u015f\u00fck ama net anlat">enerjim d\u00fc\u015f\u00fck ama net anlat</button>
    </div>
    <div class="bar">
      <button data-audio-boundary-command="sesimi analiz et">Privacy: sesimi analiz et</button>
      <button data-audio-boundary-command="panik konu\u015fuyorum">Privacy: panik konu\u015fuyorum</button>
      <button data-audio-boundary-command="mikrofonu a\u00e7">Privacy: mikrofonu a\u00e7</button>
      <button data-audio-boundary-command="sesimi kaydet">Privacy: sesimi kaydet</button>
      <button data-audio-boundary-command="sadece tonumu sakinle\u015ftir">Privacy: tonu sakinle\u015ftir</button>
    </div>
    <h2>Luxway Preview</h2>
    <div class="bar">
      <button data-endpoint="/debug/luxway-full-status">Luxway Full Status</button>
      <button data-endpoint="/debug/luxway-status">Luxway Status</button>
      <button data-endpoint="/luxway/capabilities">Luxway Capabilities</button>
      <button data-endpoint="/luxway/permission-model">Permission Model</button>
      <button data-endpoint="/luxway/weekly-report-schema">Weekly Report Schema</button>
    </div>
    <div class="bar">
      <button data-luxway-command="telefonumu tara">telefonumu tara</button>
      <button data-luxway-command="gereksiz uygulamalar\u0131 bul">gereksiz uygulamalar\u0131 bul</button>
      <button data-luxway-command="haftal\u0131k telefon raporu \u00e7\u0131kar">haftal\u0131k telefon raporu \u00e7\u0131kar</button>
      <button data-luxway-command="Ali'ye mesaj tasla\u011f\u0131 yaz">Ali'ye mesaj tasla\u011f\u0131 yaz</button>
      <button data-luxway-command="bildirimlerimi \u00f6nceliklendir">bildirimlerimi \u00f6nceliklendir</button>
      <button data-luxway-command="mail \u00f6zetimi g\u00f6ster">mail \u00f6zetimi g\u00f6ster</button>
      <button data-luxway-command="takvimimi \u00f6zetle">takvimimi \u00f6zetle</button>
    </div>
    <div class="bar">
      <button data-luxway-permission-command="Android bildirimlerimi \u00f6nceliklendir" data-luxway-platform="android">Permission: Android bildirim</button>
      <button data-luxway-permission-command="iOS takvimimi \u00f6zetle" data-luxway-platform="ios">Permission: iOS takvim</button>
      <button data-luxway-permission-command="uygulamalar\u0131 tara" data-luxway-platform="android">Permission: uygulamalar</button>
      <button data-luxway-permission-command="depolamay\u0131 temizle" data-luxway-platform="android">Permission: depolama</button>
      <button data-luxway-permission-command="ki\u015filerime mesaj yaz" data-luxway-platform="android">Permission: mesaj</button>
      <button data-luxway-permission-command="ayarlar\u0131 de\u011fi\u015ftir" data-luxway-platform="android">Permission: ayar</button>
    </div>
    <div class="bar">
      <button data-luxway-weekly-focus="haftal\u0131k telefon raporu \u00e7\u0131kar" data-luxway-platform="android">Weekly: telefon raporu</button>
      <button data-luxway-weekly-focus="bildirim y\u00fck\u00fcm\u00fc g\u00f6ster" data-luxway-platform="android">Weekly: bildirim y\u00fck\u00fc</button>
      <button data-luxway-weekly-focus="kullanmad\u0131\u011f\u0131m uygulamalar\u0131 \u00f6ner" data-luxway-platform="android">Weekly: kullanmad\u0131\u011f\u0131m uygulamalar</button>
      <button data-luxway-weekly-focus="depolama bask\u0131s\u0131n\u0131 g\u00f6ster" data-luxway-platform="android">Weekly: depolama</button>
      <button data-luxway-weekly-focus="odak \u00f6nerileri ver" data-luxway-platform="android">Weekly: odak</button>
    </div>
    <div class="bar">
      <button data-luxway-data-command="mailimi \u00f6zetle" data-luxway-domain="mail" data-luxway-platform="android">Data: mail</button>
      <button data-luxway-data-command="mesajlar\u0131m\u0131 \u00f6zetle" data-luxway-domain="messages" data-luxway-platform="android">Data: mesaj</button>
      <button data-luxway-data-command="takvimimi \u00f6zetle" data-luxway-domain="calendar" data-luxway-platform="ios">Data: takvim</button>
      <button data-luxway-data-command="gereksiz uygulamalar\u0131 bul" data-luxway-domain="app_usage" data-luxway-platform="android">Data: uygulama</button>
      <button data-luxway-data-command="depolamay\u0131 temizle" data-luxway-domain="storage" data-luxway-platform="android">Data: depolama</button>
      <button data-luxway-data-command="bildirimlerimi \u00f6nceliklendir" data-luxway-domain="notifications" data-luxway-platform="android">Data: bildirim</button>
    </div>
    <div class="bar">
      <button data-luxway-safety-command="gereksiz uygulamalar\u0131 sil" data-luxway-platform="android">Safety: uygulama sil</button>
      <button data-luxway-safety-command="bu dosyay\u0131 sil" data-luxway-platform="android">Safety: dosya sil</button>
      <button data-luxway-safety-command="Ali'ye mesaj g\u00f6nder" data-luxway-platform="android">Safety: mesaj g\u00f6nder</button>
      <button data-luxway-safety-command="bu maili g\u00f6nder" data-luxway-platform="android">Safety: mail g\u00f6nder</button>
      <button data-luxway-safety-command="annemi ara" data-luxway-platform="android">Safety: ara</button>
      <button data-luxway-safety-command="ayarlar\u0131 de\u011fi\u015ftir" data-luxway-platform="android">Safety: ayar</button>
      <button data-luxway-safety-command="depolamay\u0131 temizle" data-luxway-platform="android">Safety: depolama</button>
    </div>
    <h2>Model Router Preview</h2>
    <div class="bar">
      <button data-endpoint="/debug/model-router-status">Model Router Status</button>
      <button data-endpoint="/router/model-config">Model Router Config</button>
      <button data-endpoint="/router/cost-privacy-policy">Cost Privacy Policy</button>
      <button data-endpoint="/router/safe-memory-policy">Safe Memory Policy</button>
    </div>
    <div class="bar">
      <button data-model-router-command="normal sohbet" data-model-task="normal_chat">normal sohbet</button>
      <button data-model-router-command="uzun rapor yaz" data-model-task="report_writer" data-model-size="long">uzun rapor yaz</button>
      <button data-model-router-command="CV haz\u0131rla" data-model-task="cv_builder">CV haz\u0131rla</button>
      <button data-model-router-command="r\u00fcya sahnesi promptla" data-model-task="dream_scene">r\u00fcya sahnesi promptla</button>
      <button data-model-router-command="Lux Ambrosia promptu haz\u0131rla" data-model-task="ambrosia_prompt">Lux Ambrosia promptu</button>
      <button data-model-router-command="g\u00f6rsel \u00fcret" data-model-task="image_generation_request">g\u00f6rsel \u00fcret</button>
      <button data-model-router-command="\u00e7izimi oku" data-model-task="sketch_understanding_request">\u00e7izimi oku</button>
      <button data-model-router-command="Luxway telefon raporu" data-model-task="luxway">Luxway telefon raporu</button>
      <button data-model-router-command="hassas g\u00fcvenlik sorusu" data-model-task="safety_sensitive" data-model-sensitivity="safety">hassas g\u00fcvenlik sorusu</button>
      <button data-model-router-command="kritik kod debug" data-model-task="critical_debug" data-model-sensitivity="high">kritik kod debug</button>
      <button data-model-router-command="kod d\u00fczenle" data-model-task="code">kod d\u00fczenle</button>
    </div>
    <div class="bar">
      <button data-model-hint-command="uzun rapor yaz" data-model-source="workspace" data-model-task="report_writer" data-model-size="long">Hint: Workspace rapor</button>
      <button data-model-hint-command="r\u00fcya sahnesi promptla" data-model-source="visual" data-model-task="dream_scene">Hint: Visual r\u00fcya</button>
      <button data-model-hint-command="g\u00f6rsel \u00fcret" data-model-source="visual" data-model-task="image_generation_request">Hint: Image \u00fcret</button>
      <button data-model-hint-command="\u00e7izimi oku" data-model-source="visual" data-model-task="sketch_understanding_request">Hint: Mini \u00e7izim</button>
      <button data-model-hint-command="kritik kod debug" data-model-source="codex" data-model-task="critical_debug" data-model-sensitivity="high">Hint: GPT fallback</button>
      <button data-model-hint-command="Luxway telefon raporu" data-model-source="luxway" data-model-task="luxway">Hint: Luxway</button>
    </div>
    <div class="bar">
      <button data-cost-privacy-command="normal sohbet maliyet preview" data-cost-task="normal_chat">Cost: normal sohbet</button>
      <button data-cost-privacy-command="\u00f6zel mesaj\u0131m\u0131 \u00f6zetle" data-cost-task="permission_boundary" data-cost-sensitivity="privacy">Cost: \u00f6zel mesaj</button>
      <button data-cost-privacy-command="ses kayd\u0131m\u0131 analiz et" data-cost-task="audio_voice" data-cost-sensitivity="privacy">Cost: ses kayd\u0131</button>
      <button data-cost-privacy-command="dosyam\u0131 oku" data-cost-task="workspace" data-cost-sensitivity="privacy">Cost: dosya</button>
      <button data-cost-privacy-command="hassas g\u00fcvenlik sorusu" data-cost-task="safety_sensitive" data-cost-sensitivity="safety">Cost: hassas g\u00fcvenlik</button>
    </div>
    <div class="bar">
      <button data-safe-memory-command="g\u00f6rsel tarz\u0131m\u0131 hat\u0131rla" data-safe-memory-task="visual_prompt" data-safe-memory-type="lux_visual_style">Memory: g\u00f6rsel tarz</button>
      <button data-safe-memory-command="workspace proje notlar\u0131m\u0131 kullan" data-safe-memory-task="workspace" data-safe-memory-type="workspace_context">Memory: workspace notlar</button>
      <button data-safe-memory-command="Luxeph ge\u00e7mi\u015fini getir" data-safe-memory-task="privacy_sensitive" data-safe-memory-type="emotional_context">Memory: Luxeph block</button>
      <button data-safe-memory-command="ses sinyalimi kullan" data-safe-memory-task="audio_voice" data-safe-memory-type="audio_signal">Memory: ses sinyali</button>
      <button data-safe-memory-command="\u00f6zel mesaj ge\u00e7mi\u015fimi getir" data-safe-memory-task="permission_boundary" data-safe-memory-sensitivity="privacy" data-safe-memory-type="safety_boundary">Memory: \u00f6zel mesaj block</button>
      <button data-safe-memory-command="Ambrosia tarz\u0131m\u0131 kullan" data-safe-memory-task="ambrosia_prompt" data-safe-memory-type="lux_ambrosia_reference">Memory: Ambrosia tarz</button>
    </div>
    <div class="bar">
      <button data-endpoint="/debug/agent/sample-email">Email Sample</button>
      <button data-endpoint="/debug/agent/sample-luxway">Luxway Sample</button>
      <button data-endpoint="/debug/agent/sample-visual">Visual Memory Sample</button>
      <button data-endpoint="/debug/agent/sample-dream">Dream Scene Sample</button>
      <button data-endpoint="/debug/router/sample-cv">CV Router Sample</button>
    </div>
    <h2>Mode Registry</h2>
    <div class="bar">
      <button data-mode-command="Luxeph'e ge\u00e7">Luxeph'e ge\u00e7</button>
      <button data-mode-command="CV haz\u0131rla">CV haz\u0131rla</button>
      <button data-mode-command="r\u00fcyam\u0131 g\u00f6rsele \u00e7evir">r\u00fcyam\u0131 g\u00f6rsele \u00e7evir</button>
      <button data-mode-command="gece radyosu modu">gece radyosu modu</button>
      <button data-mode-command="tek ad\u0131m s\u00f6yle">tek ad\u0131m s\u00f6yle</button>
      <button data-mode-command="Codex modu">Codex modu</button>
    </div>
    <h2>Permission Boundary</h2>
    <div class="bar">
      <button data-permission-command="CV haz\u0131rla">CV haz\u0131rla</button>
      <button data-permission-command="Luxeph'e ge\u00e7">Luxeph'e ge\u00e7</button>
      <button data-permission-command="mailimi oku">mailimi oku</button>
      <button data-permission-command="bu maili g\u00f6nder">bu maili g\u00f6nder</button>
      <button data-permission-command="telefonumdaki gereksiz uygulamalar\u0131 sil">telefonumdaki gereksiz uygulamalar\u0131 sil</button>
      <button data-permission-command="raporu PDF olarak indir">raporu PDF olarak indir</button>
      <button data-permission-command="tek ad\u0131m s\u00f6yle">tek ad\u0131m s\u00f6yle</button>
    </div>
    <h2>Agent Decision Trace</h2>
    <div class="bar">
      <button data-trace-command="CV haz\u0131rla">CV haz\u0131rla</button>
      <button data-trace-command="Luxeph'e ge\u00e7">Luxeph'e ge\u00e7</button>
      <button data-trace-command="mailimi oku">mailimi oku</button>
      <button data-trace-command="bu maili g\u00f6nder">bu maili g\u00f6nder</button>
      <button data-trace-command="telefonumdaki gereksiz uygulamalar\u0131 sil">telefonumdaki gereksiz uygulamalar\u0131 sil</button>
      <button data-trace-command="raporu PDF olarak indir">raporu PDF olarak indir</button>
      <button data-trace-command="tek ad\u0131m s\u00f6yle">tek ad\u0131m s\u00f6yle</button>
      <button data-trace-command="Codex modu">Codex modu</button>
    </div>
    <p class="status" id="status">Choose a sample.</p>
    <pre id="output">{}</pre>
  </main>
  <script>
    const output = document.getElementById("output");
    const statusEl = document.getElementById("status");
    async function loadSample(endpoint) {
      statusEl.textContent = "Loading " + endpoint;
      output.textContent = "{}";
      try {
        const response = await fetch(endpoint, { headers: { "Accept": "application/json" } });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded " + endpoint : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadWorkspace(command) {
      statusEl.textContent = "Loading workspace preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/workspace/preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, content: "" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded workspace preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadWorkspaceSeparation(command) {
      statusEl.textContent = "Loading workspace separation preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/workspace/separation-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, content: "Ornek belge icerigi; sadece read-only ayrim onizlemesi icin kullanilir." })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded workspace separation preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadWorkspaceParser(command) {
      statusEl.textContent = "Loading workspace command parser";
      output.textContent = "{}";
      try {
        const response = await fetch("/workspace/parse-command", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, current_blocks: [] })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded workspace command parser" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadWorkspaceExport(exportType) {
      statusEl.textContent = "Loading workspace export preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/workspace/export-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ export_type: exportType, blocks: [] })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded workspace export preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadWorkspaceContext(contextNote) {
      statusEl.textContent = "Loading workspace context preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/workspace/context-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ context_note: contextNote, project_type: "debug_sample", current_blocks: [] })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded workspace context preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadWorkspaceBuilder(command) {
      statusEl.textContent = "Loading workspace builder preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/workspace/builder-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, content: "", context_note: "", project_type: "debug_sample" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded workspace builder preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadVisualStyle(prompt) {
      statusEl.textContent = "Loading visual style preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/visual/style-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, requested_styles: [], mode: "debug_panel" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded visual style preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadVisualRatio(prompt) {
      statusEl.textContent = "Loading visual ratio preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/visual/ratio-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, ratio_text: "", requested_styles: [], mode: "debug_panel" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded visual ratio preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadAmbrosia(feelingText) {
      statusEl.textContent = "Loading Ambrosia state preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/visual/ambrosia-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ feeling_text: feelingText, intensity: 0.55, style_ratio: {} })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded Ambrosia state preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadDreamScene(sceneText) {
      statusEl.textContent = "Loading dream scene preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/visual/dream-scene-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ scene_text: sceneText, style_hint: "dream scene low line density", locked_elements: [] })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded dream scene preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadSceneLock(newDetail) {
      statusEl.textContent = "Loading scene lock preview";
      output.textContent = "{}";
      const currentSceneState = {
        locked_elements: ["dream_self", "bowl", "amber_light"],
        subjects: [{ id: "dream_self", type: "self_presence", locked_candidate: true }],
        objects: [
          { id: "bowl", type: "object_or_environment", locked_candidate: true },
          { id: "amber_light", type: "object_or_environment", locked_candidate: true }
        ],
        spatial_relations: [{ relation: "held_by_subject", target: "bowl" }]
      };
      try {
        const response = await fetch("/visual/scene-lock-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ current_scene_state: currentSceneState, new_detail: newDetail, lock_strength: 1.0 })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded scene lock preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadVisualPrompt(prompt) {
      statusEl.textContent = "Loading visual prompt preview";
      output.textContent = "{}";
      const sceneState = {
        locked_elements: ["boat", "amber_light"],
        objects: [
          { id: "boat", type: "object_or_environment", locked_candidate: true },
          { id: "amber_light", type: "object_or_environment", locked_candidate: true }
        ],
        lighting: { key_light: "distant_amber_light", color: "#AB6B0C" }
      };
      try {
        const response = await fetch("/visual/prompt-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, mode: "", style_ratios: {}, scene_state: sceneState, ambrosia_state: {}, locked_elements: sceneState.locked_elements })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded visual prompt preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadVoicePreview(command, responseSize) {
      statusEl.textContent = "Loading voice / speed preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/voice/preview-mode", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, context: "debug panel read-only sample", response_size: responseSize || "medium", input_modality: "text" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded voice / speed preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadNightRadioPreview(text, responseSize) {
      statusEl.textContent = "Loading night radio voice preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/voice/night-radio-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ text, mood: "debug panel read-only sample", response_size: responseSize || "medium", mode: "" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded night radio voice preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadAudioSignal(description) {
      statusEl.textContent = "Loading audio signal preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/audio/preview-signal", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ description, simulated_voice_note: "debug panel simulated metadata only", context: "read-only scaffold sample" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded audio signal preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadAudioBoundary(command) {
      statusEl.textContent = "Loading audio privacy boundary preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/audio/privacy-boundary-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, audio_context: "debug panel simulated boundary check", consent_state: "not_granted" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded audio privacy boundary preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadLuxwayPreview(command) {
      statusEl.textContent = "Loading Luxway preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/luxway/preview-command", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, platform: "android", context: "debug panel read-only Luxway sample" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded Luxway preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadLuxwayPermission(command, platform) {
      statusEl.textContent = "Loading Luxway permission preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/luxway/permission-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, platform: platform || "unknown" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded Luxway permission preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadLuxwayWeeklyReport(reportFocus, platform) {
      statusEl.textContent = "Loading Luxway weekly report preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/luxway/weekly-report-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ report_focus: reportFocus, platform: platform || "unknown", context: "debug panel read-only weekly report sample" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded Luxway weekly report preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadLuxwayDataPreview(command, domain, platform) {
      statusEl.textContent = "Loading Luxway data preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/luxway/data-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, domain: domain || "", platform: platform || "unknown" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded Luxway data preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadLuxwayDeviceSafety(command, platform) {
      statusEl.textContent = "Loading Luxway device safety preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/luxway/device-safety-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ command, platform: platform || "unknown" })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded Luxway device safety preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadModelRouterPreview(command, taskType, sensitivity, responseSize) {
      statusEl.textContent = "Loading model router preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/router/model-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({
            command,
            task_type: taskType || "",
            sensitivity: sensitivity || "normal",
            response_size: responseSize || "medium"
          })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded model router preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadModelHintPreview(command, sourceArea, taskType, sensitivity, responseSize) {
      statusEl.textContent = "Loading model hint preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/router/hint-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({
            command,
            source_area: sourceArea || "general",
            task_type: taskType || "",
            sensitivity: sensitivity || "normal",
            response_size: responseSize || "medium"
          })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded model hint preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadCostPrivacyPreview(command, taskType, sensitivity) {
      statusEl.textContent = "Loading cost privacy preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/router/cost-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({
            command,
            task_type: taskType || "",
            sensitivity: sensitivity || "normal",
            estimated_tokens_bucket: "medium"
          })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded cost privacy preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    async function loadSafeMemoryPreview(command, taskType, sensitivity, memoryType) {
      statusEl.textContent = "Loading safe memory preview";
      output.textContent = "{}";
      try {
        const response = await fetch("/router/memory-retrieval-preview", {
          method: "POST",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({
            command,
            task_type: taskType || "",
            sensitivity: sensitivity || "normal",
            requested_memory_type: memoryType || ""
          })
        });
        const data = await response.json();
        statusEl.textContent = response.ok ? "Loaded safe memory preview" : "Request failed: " + response.status;
        output.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        statusEl.textContent = "Request error";
        output.textContent = String(err);
      }
    }
    document.querySelectorAll("button[data-endpoint]").forEach((button) => {
      button.addEventListener("click", () => loadSample(button.dataset.endpoint));
    });
    document.querySelectorAll("button[data-mode-command]").forEach((button) => {
      button.addEventListener("click", () => loadSample("/debug/mode-preview?q=" + encodeURIComponent(button.dataset.modeCommand)));
    });
    document.querySelectorAll("button[data-permission-command]").forEach((button) => {
      button.addEventListener("click", () => loadSample("/debug/permission-preview?q=" + encodeURIComponent(button.dataset.permissionCommand)));
    });
    document.querySelectorAll("button[data-trace-command]").forEach((button) => {
      button.addEventListener("click", () => loadSample("/debug/agent-decision-trace?q=" + encodeURIComponent(button.dataset.traceCommand)));
    });
    document.querySelectorAll("button[data-workspace-command]").forEach((button) => {
      button.addEventListener("click", () => loadWorkspace(button.dataset.workspaceCommand));
    });
    document.querySelectorAll("button[data-workspace-separation-command]").forEach((button) => {
      button.addEventListener("click", () => loadWorkspaceSeparation(button.dataset.workspaceSeparationCommand));
    });
    document.querySelectorAll("button[data-workspace-parse-command]").forEach((button) => {
      button.addEventListener("click", () => loadWorkspaceParser(button.dataset.workspaceParseCommand));
    });
    document.querySelectorAll("button[data-workspace-export-type]").forEach((button) => {
      button.addEventListener("click", () => loadWorkspaceExport(button.dataset.workspaceExportType));
    });
    document.querySelectorAll("button[data-workspace-context-note]").forEach((button) => {
      button.addEventListener("click", () => loadWorkspaceContext(button.dataset.workspaceContextNote));
    });
    document.querySelectorAll("button[data-workspace-builder-command]").forEach((button) => {
      button.addEventListener("click", () => loadWorkspaceBuilder(button.dataset.workspaceBuilderCommand));
    });
    document.querySelectorAll("button[data-visual-style-prompt]").forEach((button) => {
      button.addEventListener("click", () => loadVisualStyle(button.dataset.visualStylePrompt));
    });
    document.querySelectorAll("button[data-visual-ratio-prompt]").forEach((button) => {
      button.addEventListener("click", () => loadVisualRatio(button.dataset.visualRatioPrompt));
    });
    document.querySelectorAll("button[data-ambrosia-feeling]").forEach((button) => {
      button.addEventListener("click", () => loadAmbrosia(button.dataset.ambrosiaFeeling));
    });
    document.querySelectorAll("button[data-dream-scene]").forEach((button) => {
      button.addEventListener("click", () => loadDreamScene(button.dataset.dreamScene));
    });
    document.querySelectorAll("button[data-scene-lock-detail]").forEach((button) => {
      button.addEventListener("click", () => loadSceneLock(button.dataset.sceneLockDetail));
    });
    document.querySelectorAll("button[data-visual-prompt]").forEach((button) => {
      button.addEventListener("click", () => loadVisualPrompt(button.dataset.visualPrompt));
    });
    document.querySelectorAll("button[data-voice-command]").forEach((button) => {
      button.addEventListener("click", () => loadVoicePreview(button.dataset.voiceCommand, button.dataset.voiceSize));
    });
    document.querySelectorAll("button[data-night-radio-text]").forEach((button) => {
      button.addEventListener("click", () => loadNightRadioPreview(button.dataset.nightRadioText, button.dataset.nightRadioSize));
    });
    document.querySelectorAll("button[data-audio-description]").forEach((button) => {
      button.addEventListener("click", () => loadAudioSignal(button.dataset.audioDescription));
    });
    document.querySelectorAll("button[data-audio-boundary-command]").forEach((button) => {
      button.addEventListener("click", () => loadAudioBoundary(button.dataset.audioBoundaryCommand));
    });
    document.querySelectorAll("button[data-luxway-command]").forEach((button) => {
      button.addEventListener("click", () => loadLuxwayPreview(button.dataset.luxwayCommand));
    });
    document.querySelectorAll("button[data-luxway-permission-command]").forEach((button) => {
      button.addEventListener("click", () => loadLuxwayPermission(button.dataset.luxwayPermissionCommand, button.dataset.luxwayPlatform));
    });
    document.querySelectorAll("button[data-luxway-weekly-focus]").forEach((button) => {
      button.addEventListener("click", () => loadLuxwayWeeklyReport(button.dataset.luxwayWeeklyFocus, button.dataset.luxwayPlatform));
    });
    document.querySelectorAll("button[data-luxway-data-command]").forEach((button) => {
      button.addEventListener("click", () => loadLuxwayDataPreview(button.dataset.luxwayDataCommand, button.dataset.luxwayDomain, button.dataset.luxwayPlatform));
    });
    document.querySelectorAll("button[data-luxway-safety-command]").forEach((button) => {
      button.addEventListener("click", () => loadLuxwayDeviceSafety(button.dataset.luxwaySafetyCommand, button.dataset.luxwayPlatform));
    });
    document.querySelectorAll("button[data-model-router-command]").forEach((button) => {
      button.addEventListener("click", () => loadModelRouterPreview(
        button.dataset.modelRouterCommand,
        button.dataset.modelTask,
        button.dataset.modelSensitivity,
        button.dataset.modelSize
      ));
    });
    document.querySelectorAll("button[data-model-hint-command]").forEach((button) => {
      button.addEventListener("click", () => loadModelHintPreview(
        button.dataset.modelHintCommand,
        button.dataset.modelSource,
        button.dataset.modelTask,
        button.dataset.modelSensitivity,
        button.dataset.modelSize
      ));
    });
    document.querySelectorAll("button[data-cost-privacy-command]").forEach((button) => {
      button.addEventListener("click", () => loadCostPrivacyPreview(
        button.dataset.costPrivacyCommand,
        button.dataset.costTask,
        button.dataset.costSensitivity
      ));
    });
    document.querySelectorAll("button[data-safe-memory-command]").forEach((button) => {
      button.addEventListener("click", () => loadSafeMemoryPreview(
        button.dataset.safeMemoryCommand,
        button.dataset.safeMemoryTask,
        button.dataset.safeMemorySensitivity,
        button.dataset.safeMemoryType
      ));
    });
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_doc)


@app.get("/digest")
async def digest(user_id: str = "default_user"):
    user_id = safe_user_id(user_id)
    profile, notes, garden = load_user_state(user_id)
    session = load_current_session(user_id)
    digest_data = build_weekly_digest(profile, session, garden)
    save_user_state(user_id, profile, notes, garden)
    return {"weekly_report": digest_data}


@app.get("/summary")
async def summary(user_id: str = "default_user"):
    user_id = safe_user_id(user_id)
    session = load_current_session(user_id)
    return {"summary": generate_session_summary(session)}


@app.get("/search")
async def search(user_id: str = "default_user", q: str = Query("", max_length=200)):
    return search_structured(user_id, q)


@app.post("/translate")
async def translate(payload: TranslateRequest, auth: Optional[str] = Header(None)):
    check_auth(auth)
    result = deepl_translate_text(payload.text, payload.target_lang, payload.source_lang)
    translated = str(result.get("translated_text", payload.text) or payload.text).strip()
    if translated.lower() == (payload.text or "").strip().lower():
        local_hit = local_phrase_translate(payload.text, payload.target_lang)
        if local_hit:
            translated = local_hit
            result["ok"] = True
            result["detected_source_language"] = result.get("detected_source_language") or "EN"
    return {
        "ok": result.get("ok", False),
        "translated_text": translated,
        "detected_source_language": result.get("detected_source_language"),
        "error": result.get("error"),
    }


@app.post("/explain")
async def explain(payload: ExplainRequest, auth: Optional[str] = Header(None)):
    check_auth(auth)
    text = (payload.text or "").strip()
    if not text:
        return {"ok": False, "text": "", "kind": "none"}

    user_lang = (payload.user_lang or "tr").lower()
    target_lang = user_lang_to_deepl_target(user_lang)

    if payload.force_translate:
        out = deepl_translate_text(text, target_lang)
        translated = str(out.get("translated_text", "")).strip()
        if translated and translated.lower() != text.lower():
            return {"ok": True, "text": translated, "kind": "translation"}
        return {
            "ok": False,
            "text": (
                f"\"{text}\" için çeviri bulunamadı."
                if user_lang.startswith("tr")
                else f"No translation found for \"{text}\"."
            ),
            "kind": "fallback",
            "open_external_url": f"https://translate.google.com/?sl=auto&tl={quote(user_lang)}&text={quote(text)}&op=translate",
        }

    normalized = normalize_keyword_token(text) or fold_turkish_ascii(text)
    direct = TERM_EXPLANATIONS_TR.get(normalized) or TERM_EXPLANATIONS_TR.get(fold_turkish_ascii(text))
    if direct:
        return {"ok": True, "text": translate_if_needed(direct, target_lang), "kind": "definition"}

    if looks_turkish_text(text):
        tdk_hit = tdk_define_once(text)
        if tdk_hit:
            return {"ok": True, "text": translate_if_needed(tdk_hit, target_lang), "kind": "definition"}

    foreign_text = looks_foreign_word(text)
    if foreign_text:
        local_hit = local_phrase_translate(text, target_lang)
        if local_hit:
            return {"ok": True, "text": local_hit, "kind": "translation"}
        tr = deepl_translate_text(text, target_lang)
        translated = str(tr.get("translated_text", text)).strip()
        if translated and translated.lower() != text.lower():
            return {"ok": True, "text": translated, "kind": "translation"}
        return {
            "ok": False,
            "text": (
                f"\"{text}\" için çeviri bulunamadı."
                if user_lang.startswith("tr")
                else f"No translation found for \"{text}\"."
            ),
            "kind": "fallback",
            "open_external_url": f"https://translate.google.com/?sl=auto&tl={quote(user_lang)}&text={quote(text)}&op=translate",
        }

    model_exp = explain_with_model_tr(text)
    if model_exp:
        return {"ok": True, "text": translate_if_needed(model_exp, target_lang), "kind": "definition"}

    fallback = (
        f"\"{text}\" için kısa bir açıklama üretemedim."
        if user_lang.startswith("tr")
        else f"No short explanation produced for \"{text}\"."
    )
    return {"ok": False, "text": fallback, "kind": "fallback"}


@app.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks, auth: Optional[str] = Header(None)):
    request_start = perf_counter()
    check_auth(auth)

    msg = (request.message or "").strip()
    if not msg:
        log_latency("chat_empty", total_ms=ms_since(request_start), message_chars=0)
        return {"response": "Boş mesaj alamam."}

    if len(msg) > 4000:
        log_latency("chat_rejected", total_ms=ms_since(request_start), message_chars=len(msg), reason="too_long")
        return {"response": "Mesajın biraz uzun. Biraz kısaltıp tekrar dener misin?"}

    plan_start = perf_counter()
    plan = prepare_chat_plan(
        request.user_id,
        msg,
        request.mode,
        request.ghost_hesitation,
        request.location,
        request.client_signals,
    )
    plan_ms = ms_since(plan_start)

    if plan["kind"] == "command":
        command_budget = safe_token_budget_decision(msg, plan.get("mode", request.mode), {}, extract_count_constraints(msg))
        log_latency(
            "chat_command",
            total_ms=ms_since(request_start),
            plan_ms=plan_ms,
            message_chars=len(msg),
            mode=plan.get("mode", request.mode),
        )
        record_cost_event(
            endpoint="/chat",
            route="command",
            plan={
                "message": msg,
                "mode": plan.get("mode", request.mode),
                "token_budget": command_budget,
                "count_constraints": extract_count_constraints(msg),
            },
            mode=plan.get("mode", request.mode),
            total_ms=ms_since(request_start),
            success=True,
        )
        return {
            "response": plan["response"],
            "meta": plan["meta"],
        }

    if plan["kind"] == "crisis":
        log_latency(
            "chat_crisis",
            total_ms=ms_since(request_start),
            plan_ms=plan_ms,
            message_chars=len(msg),
            mode=plan.get("mode", request.mode),
        )
        record_cost_event(
            endpoint="/chat",
            route="crisis",
            plan=plan,
            mode=plan.get("mode", request.mode),
            total_ms=ms_since(request_start),
            success=True,
        )
        return {
            "response": plan["response"],
            "weekly_report": plan.get("weekly_report", {}),
            "memory_preview": plan.get("memory_preview", []),
            "meta": plan.get("meta", {}),
        }

    model_start = perf_counter()
    finish_reason = ""
    auto_parts = 0
    model_error_type = ""
    try:
        response_text, finish_reason = call_model_with_finish(
            plan["openai_messages"],
            model=plan["model"],
            temperature=plan["temperature"],
            max_tokens=plan["max_tokens"],
        )
        if not response_text:
            response_text = chat_fallback_response(plan)
        else:
            response_text, finish_reason, auto_parts = auto_continue_text(plan, response_text, finish_reason)
    except Exception as e:
        logging.warning(f"Model error fallback used: {e}")
        model_error_type = type(e).__name__
        if is_model_auth_error(e):
            response_text = auth_error_response()
        else:
            response_text = chat_fallback_response(plan)
    model_ms = ms_since(model_start)

    response_text = sanitize_false_addressing(response_text, plan)
    response_text = trim_self_answer_after_question(response_text)
    response_text = enforce_count_guard(plan, response_text)
    response_text = enforce_line_format_guard(plan, response_text)
    if not plan.get("count_constraints"):
        response_text = apply_background_nudges(plan, response_text)
    finalize_start = perf_counter()
    digest_data = finalize_chat(plan, response_text)
    finalize_ms = ms_since(finalize_start)
    live_ctx_text = str(safe_dict(plan.get("learning_context")).get("context_text", "")).strip()
    history_count, history_chars = history_metrics_from_messages(safe_list(plan.get("openai_messages")))
    log_latency(
        "chat_model",
        total_ms=ms_since(request_start),
        plan_ms=plan_ms,
        model_ms=model_ms,
        finalize_ms=finalize_ms,
        message_chars=len(msg),
        prompt_chars=len(str(plan.get("prompt", ""))),
        context_chars=len(live_ctx_text),
        mode=plan.get("mode", request.mode),
        max_tokens=plan.get("max_tokens"),
        finish_reason=finish_reason,
        auto_continue_parts=auto_parts,
    )
    record_cost_event(
        endpoint="/chat",
        route="model" if not model_error_type else "model_fallback",
        plan=plan,
        mode=plan.get("mode", request.mode),
        model=plan.get("model", ""),
        prompt_chars=len(str(plan.get("prompt", ""))),
        context_chars=len(live_ctx_text),
        history_message_count=history_count,
        history_chars=history_chars,
        max_tokens=clamp_int(plan.get("max_tokens"), 0, 100000, 0),
        finish_reason=finish_reason,
        auto_continue_parts=auto_parts,
        model_ms=model_ms,
        total_ms=ms_since(request_start),
        response_text=response_text,
        success=not bool(model_error_type),
        error_type=model_error_type,
    )
    if plan.get("kind") == "model" and not plan.get("skip_save"):
        background_tasks.add_task(
            learning_pipeline.run_background_learning_safe,
            user_id=plan.get("user_id", "default_user"),
            user_message=plan.get("message", ""),
            assistant_response=response_text,
            mode=plan.get("mode", "luxviai"),
            analysis=safe_dict(plan.get("analysis")),
            session_id=safe_dict(plan.get("session")).get("session_id"),
            learning_context=safe_dict(plan.get("learning_context")),
        )
    return {
        "response": response_text,
        "weekly_report": digest_data if not plan.get("skip_save") else {},
        "memory_preview": plan.get("memory_preview", []),
        "meta": {
            "mode": plan["mode"],
            "session_id": None if plan.get("skip_save") else plan["session"]["session_id"],
            "dominant_emotion": plan["analysis"].get("primary_emotion"),
            "dominant_theme": plan["analysis"].get("theme"),
            "cognitive_load": plan["analysis"].get("cognitive_load"),
            "crisis_context": safe_dict(plan["analysis"].get("safety_layer")).get("crisis_context"),
            "ephemeral": bool(plan.get("skip_save")),
        },
    }


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            turn_start = perf_counter()
            payload = await websocket.receive_json()
            request = ChatRequest(**payload)

            msg = (request.message or "").strip()
            if not msg:
                log_latency("ws_empty", total_ms=ms_since(turn_start), message_chars=0)
                await websocket.send_json({"type": "done", "response": "Boş mesaj alamam."})
                continue

            if len(msg) > 4000:
                log_latency("ws_rejected", total_ms=ms_since(turn_start), message_chars=len(msg), reason="too_long")
                await websocket.send_json({"type": "done", "response": "Mesajın biraz uzun. Biraz kısaltıp tekrar dener misin?"})
                continue

            typing_sent = False
            typing_ms = None
            requested_mode = (request.mode or "luxviai").lower().strip()
            if requested_mode not in ALLOWED_MODES:
                requested_mode = "luxviai"
            await websocket.send_json({
                "type": "typing",
                "meta": {
                    "mode": requested_mode,
                    "session_id": None,
                    "ephemeral": requested_mode == "luxeph",
                },
            })
            typing_sent = True
            typing_ms = ms_since(turn_start)

            plan_start = perf_counter()
            plan = prepare_chat_plan(
                request.user_id,
                msg,
                request.mode,
                request.ghost_hesitation,
                request.location,
                request.client_signals,
            )
            plan_ms = ms_since(plan_start)

            if plan["kind"] == "command":
                command_budget = safe_token_budget_decision(msg, plan.get("mode", request.mode), {}, extract_count_constraints(msg))
                log_latency(
                    "ws_command",
                    total_ms=ms_since(turn_start),
                    plan_ms=plan_ms,
                    typing_ms=typing_ms,
                    message_chars=len(msg),
                    mode=plan.get("mode", request.mode),
                )
                record_cost_event(
                    endpoint="/ws/chat",
                    route="command",
                    plan={
                        "message": msg,
                        "mode": plan.get("mode", request.mode),
                        "token_budget": command_budget,
                        "count_constraints": extract_count_constraints(msg),
                    },
                    mode=plan.get("mode", request.mode),
                    total_ms=ms_since(turn_start),
                    success=True,
                )
                await websocket.send_json({
                    "type": "done",
                    "response": plan["response"],
                    "meta": plan["meta"],
                })
                continue

            if plan["kind"] == "crisis":
                log_latency(
                    "ws_crisis",
                    total_ms=ms_since(turn_start),
                    plan_ms=plan_ms,
                    typing_ms=typing_ms,
                    message_chars=len(msg),
                    mode=plan.get("mode", request.mode),
                )
                record_cost_event(
                    endpoint="/ws/chat",
                    route="crisis",
                    plan=plan,
                    mode=plan.get("mode", request.mode),
                    total_ms=ms_since(turn_start),
                    success=True,
                )
                await websocket.send_json({
                    "type": "done",
                    "response": plan["response"],
                    "weekly_report": plan.get("weekly_report", {}),
                    "memory_preview": plan.get("memory_preview", []),
                    "meta": plan.get("meta", {}),
                })
                continue

            full = []
            first_chunk_ms = None
            stream_ms = 0
            finalize_ms = 0
            finish_reason = ""
            auto_parts = 0
            count_guarded = False
            try:
                if not typing_sent:
                    await websocket.send_json({
                        "type": "typing",
                        "meta": {
                            "mode": plan["mode"],
                            "session_id": None if plan.get("skip_save") else plan["session"]["session_id"],
                            "ephemeral": bool(plan.get("skip_save")),
                        },
                    })
                    typing_ms = ms_since(turn_start)

                count_guarded = bool(safe_list(plan.get("count_constraints")))
                if client:
                    stream_start = perf_counter()
                    for event in stream_model(
                        plan["openai_messages"],
                        model=plan["model"],
                        temperature=plan["temperature"],
                        max_tokens=plan["max_tokens"],
                    ):
                        chunk = str(safe_dict(event).get("text", ""))
                        event_finish = str(safe_dict(event).get("finish_reason", "") or "")
                        if event_finish:
                            finish_reason = event_finish
                        if chunk:
                            if first_chunk_ms is None:
                                first_chunk_ms = ms_since(turn_start)
                            full.append(chunk)
                            if not count_guarded:
                                await websocket.send_json({"type": "chunk", "text": chunk})
                            if not count_guarded and STREAM_CHUNK_DELAY > 0:
                                await asyncio.sleep(STREAM_CHUNK_DELAY)
                    stream_ms = ms_since(stream_start)

                    response_text = "".join(full).strip() or chat_fallback_response(plan)
                    continuation_limit = auto_continuation_part_limit(plan)
                    while auto_parts < continuation_limit and should_auto_continue_response(finish_reason, response_text, plan):
                        auto_parts += 1
                        continuation_full = []
                        continuation_reason = ""
                        for event in stream_model(
                            build_guarded_continuation_messages(plan["openai_messages"], response_text, safe_list(plan.get("count_constraints"))),
                            model=plan["model"],
                            temperature=plan["temperature"],
                            max_tokens=auto_continuation_max_tokens(plan),
                        ):
                            chunk = str(safe_dict(event).get("text", ""))
                            event_finish = str(safe_dict(event).get("finish_reason", "") or "")
                            if event_finish:
                                continuation_reason = event_finish
                            if chunk:
                                continuation_full.append(chunk)
                        continuation_text = "".join(continuation_full).strip()
                        if not continuation_text:
                            break
                        merged = merge_continuation_text(response_text, continuation_text)
                        suffix = merged[len(response_text):] if merged.startswith(response_text) else merged
                        if not suffix or merged == response_text:
                            break
                        response_text = merged.strip()
                        full.append(suffix)
                        if not count_guarded:
                            await websocket.send_json({"type": "chunk", "text": suffix})
                        finish_reason = continuation_reason
                else:
                    response_text = chat_fallback_response(plan)

                streamed_response_text = response_text
                response_text = sanitize_false_addressing(response_text, plan)
                response_text = trim_self_answer_after_question(response_text)
                response_text = enforce_count_guard(plan, response_text)
                response_text = enforce_line_format_guard(plan, response_text)
                if not count_guarded:
                    response_text = apply_background_nudges(plan, response_text)
                if count_guarded:
                    await websocket.send_json({"type": "chunk", "text": response_text})
                elif response_text != streamed_response_text and response_text.startswith(streamed_response_text):
                    suffix = response_text[len(streamed_response_text):]
                    if suffix:
                        full.append(suffix)
                        await websocket.send_json({"type": "chunk", "text": suffix})
                finalize_start = perf_counter()
                digest_data = finalize_chat(plan, response_text)
                finalize_ms = ms_since(finalize_start)
                live_ctx_text = str(safe_dict(plan.get("learning_context")).get("context_text", "")).strip()
                history_count, history_chars = history_metrics_from_messages(safe_list(plan.get("openai_messages")))
                log_latency(
                    "ws_model",
                    total_ms=ms_since(turn_start),
                    plan_ms=plan_ms,
                    typing_ms=typing_ms,
                    first_chunk_ms=first_chunk_ms,
                    stream_ms=stream_ms,
                    finalize_ms=finalize_ms,
                    message_chars=len(msg),
                    prompt_chars=len(str(plan.get("prompt", ""))),
                    context_chars=len(live_ctx_text),
                    mode=plan.get("mode", request.mode),
                    max_tokens=plan.get("max_tokens"),
                    finish_reason=finish_reason,
                    auto_continue_parts=auto_parts,
                )
                record_cost_event(
                    endpoint="/ws/chat",
                    route="model",
                    plan=plan,
                    mode=plan.get("mode", request.mode),
                    model=plan.get("model", ""),
                    prompt_chars=len(str(plan.get("prompt", ""))),
                    context_chars=len(live_ctx_text),
                    history_message_count=history_count,
                    history_chars=history_chars,
                    max_tokens=clamp_int(plan.get("max_tokens"), 0, 100000, 0),
                    finish_reason=finish_reason,
                    auto_continue_parts=auto_parts,
                    model_ms=stream_ms,
                    first_chunk_ms=first_chunk_ms,
                    total_ms=ms_since(turn_start),
                    response_text=response_text,
                    success=True,
                )

                await websocket.send_json({
                    "type": "done",
                    "response": response_text,
                    "weekly_report": digest_data if not plan.get("skip_save") else {},
                    "memory_preview": plan.get("memory_preview", []),
                    "meta": {
                        "mode": plan["mode"],
                        "session_id": None if plan.get("skip_save") else plan["session"]["session_id"],
                        "dominant_emotion": plan["analysis"].get("primary_emotion"),
                        "dominant_theme": plan["analysis"].get("theme"),
                        "cognitive_load": plan["analysis"].get("cognitive_load"),
                        "crisis_context": safe_dict(plan["analysis"].get("safety_layer")).get("crisis_context"),
                        "ephemeral": bool(plan.get("skip_save")),
                        "finish_reason": finish_reason,
                        "auto_continue_parts": auto_parts,
                    },
                })
            except Exception as e:
                logging.error(f"WS error: {e}")
                if is_model_auth_error(e):
                    response_text = auth_error_response()
                else:
                    response_text = chat_fallback_response(plan)
                response_text = sanitize_false_addressing(response_text, plan)
                response_text = trim_self_answer_after_question(response_text)
                response_text = enforce_count_guard(plan, response_text)
                response_text = enforce_line_format_guard(plan, response_text)
                if not plan.get("count_constraints"):
                    response_text = apply_background_nudges(plan, response_text)
                finalize_start = perf_counter()
                digest_data = finalize_chat(plan, response_text)
                finalize_ms = ms_since(finalize_start)
                live_ctx_text = str(safe_dict(plan.get("learning_context")).get("context_text", "")).strip()
                history_count, history_chars = history_metrics_from_messages(safe_list(plan.get("openai_messages")))
                log_latency(
                    "ws_fallback",
                    total_ms=ms_since(turn_start),
                    plan_ms=plan_ms,
                    typing_ms=typing_ms,
                    first_chunk_ms=first_chunk_ms,
                    stream_ms=stream_ms,
                    finalize_ms=finalize_ms,
                    message_chars=len(msg),
                    mode=plan.get("mode", request.mode),
                )
                record_cost_event(
                    endpoint="/ws/chat",
                    route="model_fallback",
                    plan=plan,
                    mode=plan.get("mode", request.mode),
                    model=plan.get("model", ""),
                    prompt_chars=len(str(plan.get("prompt", ""))),
                    context_chars=len(live_ctx_text),
                    history_message_count=history_count,
                    history_chars=history_chars,
                    max_tokens=clamp_int(plan.get("max_tokens"), 0, 100000, 0),
                    finish_reason=finish_reason,
                    auto_continue_parts=auto_parts,
                    model_ms=stream_ms,
                    first_chunk_ms=first_chunk_ms,
                    total_ms=ms_since(turn_start),
                    response_text=response_text,
                    success=False,
                    error_type=type(e).__name__,
                )
                await websocket.send_json({
                    "type": "done",
                    "response": response_text,
                    "weekly_report": digest_data if not plan.get("skip_save") else {},
                    "memory_preview": plan.get("memory_preview", []),
                    "meta": {
                        "mode": plan["mode"],
                        "session_id": None if plan.get("skip_save") else plan["session"]["session_id"],
                        "ephemeral": bool(plan.get("skip_save")),
                    },
                })
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
