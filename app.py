from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

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

app = FastAPI(title="Luxviai — Luxsarısı OS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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
    cutoff = datetime.utcnow() - timedelta(days=days)
    new_index = []

    for sess in index:
        try:
            created_at = parse_iso(sess.get("created_at", now_iso()))
            if created_at.replace(tzinfo=None) > cutoff:
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


def tokenize(text: str) -> List[str]:
    return [
        t.lower()
        for t in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", text or "")
        if len(t) > 2 and t.lower() not in STOPWORDS
    ]


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
    counts = Counter()
    for text in texts:
        counts.update(tokenize(text))
    return [w for w, _ in counts.most_common(limit)]


def compact_text(text: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


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
    return profile


def default_session(mode: str = "luxviai") -> Dict[str, Any]:
    sid = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
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
        if datetime.utcnow() - last_seen.replace(tzinfo=None) > timedelta(hours=12):
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
    has_keyword = contains_any(low, CRISIS_KEYWORDS)
    has_immediate = contains_any(low, IMMEDIATE_RISK_PATTERNS)
    has_contextual = contains_any(low, CONTEXTUAL_CRISIS_MARKERS)
    has_abuse_immediate = contains_any(low, ABUSE_IMMEDIATE_MARKERS)

    question_like = "?" in low or low.startswith(("neden", "nasıl", "ne ", "nedir", "sence"))
    past_like = has_contextual or any(k in low for k in ["olmuştu", "yaşadım", "anlatmıştım", "geçmiş"])
    planning_like = any(k in low for k in ["plan", "not bıraktım", "ilaçları", "bıçak", "silah", "köprü", "ip"])
    alone_like = any(k in low for k in ["yalnızım", "kimse yok", "tek başımayım", "evde yalnız"])
    current_like = any(k in low for k in ["şu an", "şimdi", "hemen", "bu gece", "bugün", "artık", "dayanamıyorum", "yapacağım"])

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
        "night_signal": True if datetime.utcnow().hour >= 22 or datetime.utcnow().hour <= 6 else False,
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


def analyze_emotion(
    message: str,
    profile: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
    location: str = "İstanbul",
    ghost_hesitation: bool = False,
    client_signals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fallback = heuristic_analysis(message, profile, session, location, ghost_hesitation, client_signals)

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
    keywords = top_keywords(user_texts, 10)
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
            f"cultural_mix(japan={round(safe_float(mix.get('japan_silence', 0.5)), 2)}, "
            f"turkish={round(safe_float(mix.get('turkish_imply', 0.5)), 2)}, "
            f"german={round(safe_float(mix.get('german_direct', 0.5)), 2)}, "
            f"latin={round(safe_float(mix.get('latin_warmth', 0.5)), 2)})"
        )

    theory_names = ", ".join([x.get("name", "") for x in theory[:5] if x.get("name")]) or "yok"
    active_layers = ", ".join(digest.get("active_layers", []) or []) or "henüz zayıf"
    return "\n".join(layer_lines + [
        f"- aktif arka plan lensleri: {theory_names}",
        f"- biriken aktif katmanlar: {active_layers}",
    ])


def build_system_prompt(
    profile: Dict[str, Any],
    analysis: Dict[str, Any],
    mode: str,
    memory_snippets: List[str],
    digest: Dict[str, Any],
) -> str:
    memory_block = "\n".join(f"- {s}" for s in memory_snippets[:5]) if memory_snippets else "- Belirgin geri çağırma yok."
    layer_block = build_layer_prompt_summary(analysis, digest)
    policy = safe_dict(analysis.get("response_policy"))
    mix = safe_dict(policy.get("cultural_mix"))
    policy_block = (
        ""
        if not policy
        else (
            "INSANI DERINLIK ADAPTASYONU:\n"
            f"- spontaneite: {policy.get('spontaneity_label', 'orta')}\n"
            f"- pacing: {policy.get('pacing', 'orta')}\n"
            f"- takip sorusu: {policy.get('followup_question_count', 1)} adet\n"
            f"- belirsizlik toleransi: {round(safe_float(policy.get('ambiguity_tolerance', 0.55)), 2)}\n"
            f"- sicaklik kalibrasyonu: {policy.get('warmth_label', 'orta')}\n"
            f"- kultur karisimi: japan={round(safe_float(mix.get('japan_silence', 0.5)), 2)}, "
            f"turkish={round(safe_float(mix.get('turkish_imply', 0.5)), 2)}, "
            f"german={round(safe_float(mix.get('german_direct', 0.5)), 2)}, "
            f"latin={round(safe_float(mix.get('latin_warmth', 0.5)), 2)}\n"
            "- Kullaniciya skor gosterme; bu sinyaller sadece ton, ritim, soru derinligi ve empatiyi ayarlasin.\n"
            "- Asla klinik tani, tedavi, ilac, dini/fal dili veya kesin yargi kullanma.\n"
        )
    )

    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_hour = datetime.now().hour

    if 5 <= current_hour < 11:
        time_context = "Sabah. Günaydın."
    elif 11 <= current_hour < 18:
        time_context = "Öğle / gündüz. İyi günler."
    elif 18 <= current_hour < 23:
        time_context = "Akşam. İyi akşamlar."
    else:
        time_context = "Gece. Gece modu aktif."

    base = f"""
Şu an: {current_datetime} ({time_context})

Sen Luxviai'sin. Luxviai — Light your way! / Yolunu aydınlat!
Sen bir yapay zekâsın; bunu saklamazsın.
Ama robot gibi konuşmazsın: sıcak, sakin, güvenilir, net, içten ve derinsin.
Merkez her zaman insandır.

DİL:
Kullanıcı hangi dilde yazarsa o dilde cevap ver.
Türkçe yazım hatalarını veya tekrarları yabancı dil sanma.

KARAKTER:
- düşük enerji ama güçlü
- abartısız
- hızlı çözümler dayatmayan
- utandırmayan
- küçültmeyen
- korkutmayan

SINIR:
- tanı koyma
- tedavi iddiasında bulunma
- ilaç önerme
- klinik etiket yapıştırma
- fal / kehanet / dini tabir kullanma
- kullanıcının mahremiyetini sömürme
- teorisyen adı sayma; arka plan lenslerini kullanıcıya doğrudan gösterme

CİDDİ DURUMLAR:
Kendine zarar, intihar, şiddet, istismar kelimeleri geçerse bağlama bak.
Geçmiş anlatım, haber, film, soru veya kavramsal konuşmaysa normal sohbet et.
Anlık yardım isteği, plan, şu an güvende olmama veya kendine zarar niyeti varsa analiz yapma.
Çok kısa, çok sıcak ve net yönlendir:
112'yi ara, en yakın acile git, güvendiğin birine haber ver.

YANIT MİMARİSİ:
1. Duyguyu aynala
2. Normalleştir
3. Yumuşak içgörü sun
4. Gerekirse açık uçlu soru sor
5. Gerekirse küçük bir adım öner

BİÇİM:
- Paragraflar kısa olsun
- Gerektiğinde liste kullan
- Tek blok halinde sıkıştırma
- Gereksiz teknik dil kullanma

HAFIZA İPUÇLARI:
{memory_block}

ARKA PLAN ANALİZİ:
Bu bölüm kullanıcıya doğrudan gösterilmez; sadece tonu, ritmi, soru derinliğini ve hafıza çağrışımını ayarlar.
{layer_block}

{policy_block}
"""

    mode_block = "\n[AKTİF MOD]\n"
    if mode == "luxviai":
        mode_block += "- Dengeli, sıcak ve net kal.\n"
    elif mode == "luxching":
        mode_block += (
            "- Sembolik, yorumlayıcı, kesinlik yok.\n"
            "- Yanıt mutlaka LUXCHING başlığıyla başlasın.\n"
            "- Bir sembol, kısa anlam, kişisel bağlam ve tek yumuşak soru içersin.\n"
            "- I Ching mantığı, fal değil, ayna.\n"
        )
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
            f"- {policy.get('followup_question_count', 1)} adet acik uclu takip sorusu ekleyebilirsin (zorlamadan).\n"
            "- Belirsizlik toleransini koru; kesin hukumlerden kacin.\n"
            f"- Sicaklik tonunu {policy.get('warmth_label', 'orta')} seviyede tut.\n"
        )

    return base + mode_block


def fallback_reply(mode: str, analysis: Dict[str, Any]) -> str:
    emotion = analysis.get("primary_emotion", "nötr")
    theme = analysis.get("theme", "belirsiz")

    if mode == "luxta":
        return random.choice(LUXTA_REPLIES)
    if mode == "luxeph":
        return f"Buradayım. {emotion} tarafını duyuyorum; bunu bu anın içinde, kayıt tutmadan taşıyabiliriz."
    if mode == "luxching":
        return generate_luxching(default_profile(), analysis)
    if mode == "luxdream":
        return "Rüya analizi… İmgeler, bilinçdışı, çağrışımlar. Anlatmaya devam edebilirsin."
    return f"Bunu duyuyorum. {emotion} tarafı ve {theme} teması biraz öne çıkıyor gibi."


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


def choose_generation_params(mode: str, analysis: Dict[str, Any]) -> tuple[str, float, int]:
    intensity = clamp_int(analysis.get("intensity", 5), 1, 10, 5)
    policy = safe_dict(analysis.get("response_policy"))
    spontaneity = clamp_float(policy.get("spontaneity"), 0.0, 1.0, 0.45)
    pacing = str(policy.get("pacing", "orta"))
    temp_shift = (spontaneity - 0.45) * 0.2

    if mode == "luxta":
        return ("deepseek-chat", clamp_float(0.22 + temp_shift * 0.3, 0.15, 0.35, 0.25), 120)
    if mode == "luxeph":
        return ("deepseek-chat", clamp_float(0.42 + temp_shift * 0.4, 0.3, 0.58, 0.45), 320)
    if mode in {"luxdream", "luxching"} or intensity >= 8:
        tokens = 760 if pacing == "akışkan" else 700
        return ("deepseek-chat", clamp_float(0.62 + temp_shift, 0.5, 0.75, 0.65), tokens)
    tokens = 420 if pacing == "yavaş" else 500 if pacing == "akışkan" else 450
    return ("deepseek-chat", clamp_float(0.52 + temp_shift, 0.42, 0.64, 0.55), tokens)


def call_model(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    if not client:
        raise RuntimeError("DeepSeek API key missing")

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


def stream_model(messages: List[Dict[str, str]], model: str, temperature: float, max_tokens: int):
    if not client:
        raise RuntimeError("DeepSeek API key missing")

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for part in stream:
        try:
            chunk = part.choices[0].delta.content or ""
            if chunk:
                yield chunk
        except Exception:
            continue


def generate_session_summary(session: Dict[str, Any]) -> str:
    msgs = session.get("messages", [])[-18:]
    user_texts = [m.get("content", "") for m in msgs if m.get("role") == "user"]
    if not msgs or len(user_texts) < 1:
        return "Henüz yeterli konuşma yok."

    keywords = top_keywords(user_texts, 8)
    key_sentences = [compact_text(t, 120) for t in user_texts[-3:] if t.strip()]

    if client and len(user_texts) >= 2:
        try:
            prompt = (
                "Sadece bu aktif konuşmayı özetle. "
                "2 kısa paragraf yaz. "
                "Sonunda 'Başlıca kelimeler:' ve 'Başlıca cümleler:' alanları ekle. "
                "Skor, tanı, klinik etiket kullanma."
            )
            return call_model(
                [{"role": "system", "content": prompt}] + [
                    {"role": m["role"], "content": m["content"]}
                    for m in msgs
                    if m.get("role") in {"user", "assistant"} and m.get("content")
                ],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=320,
            )
        except Exception as e:
            logging.warning(f"Session summary fallback: {e}")

    return (
        "Bu konuşmada henüz kısa bir iz oluştu.\n\n"
        "Başlıca kelimeler: " + (", ".join(keywords) if keywords else "Henüz belirgin değil") + "\n"
        "Başlıca cümleler:\n- " + "\n- ".join(key_sentences or ["Henüz belirgin değil"])
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
            {"role": "system", "content": build_system_prompt(profile, analysis, "luxdream", [dream_text[:250]], profile.get("weekly_report", {}))},
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
        analysis = heuristic_analysis(question_text or message, profile, session)
        return generate_luxching(profile, analysis, question_text)

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
    prompt = build_system_prompt(profile, analysis, "luxeph", [], digest)
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

    if location:
        locs = profile["ecological_context"].setdefault("locations", {})
        locs[location] = int(locs.get(location, 0)) + 1

    if mode == "luxching":
        if not is_luxching_question(message):
            return {
                "kind": "command",
                "response": "Lütfen sorunuzu sorunuz.",
                "meta": {"mode": mode, "session_id": None},
            }
        ok, msg = check_luxching_limit(profile)
        if not ok:
            return {
                "kind": "command",
                "response": msg,
                "meta": {"mode": mode, "session_id": None},
            }
        profile["luxching_last_used"] = now_iso()
        save_user_state(user_id, profile, notes, garden)

    active, session = load_or_create_session(user_id, mode)

    add_message(session, "user", message, {"mode": mode})
    analysis = analyze_emotion(message, profile, session, location, ghost_hesitation, client_signals)

    if ghost_hesitation and analysis.get("intensity", 5) < 7:
        analysis["needs_presence"] = True
        analysis["narrative_marker"] = "geri çekilme"
        analysis.setdefault("layers", {}).setdefault("hidden", {})["ghost_hesitation"] = True

    analysis = enrich_analysis_with_human_policy(message, analysis, profile, session, client_signals)

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
        }

    add_analysis(session, analysis)
    update_profile_from_analysis(profile, analysis)
    append_memory_garden_anchor(garden, message, analysis)
    digest = build_weekly_digest(profile, session, garden)
    profile["weekly_report"] = digest
    profile["last_mode"] = mode

    memory_snippets = retrieve_memory_snippets(message, session, notes, garden, profile, limit=5)
    if mode == "luxching":
        symbol = random.choice(LUXCHING_SYMBOLS)
        memory_snippets = [f"LUXCHING sembolü: {symbol['name']} - {symbol['meaning']}"] + memory_snippets
        analysis["luxching_symbol"] = symbol
    prompt = build_system_prompt(profile, analysis, mode, memory_snippets, digest)
    openai_messages = build_openai_messages(session, prompt)
    if mode == "luxching":
        symbol = analysis.get("luxching_symbol", random.choice(LUXCHING_SYMBOLS))
        openai_messages.append({
            "role": "user",
            "content": (
                f"Bu soru için LUXCHING yanıtı ver. "
                f"Sembol: {symbol['name']} ({symbol['meaning']}). "
                "Kişisel bağlamı duygu ve tema üzerinden kur. Fal gibi konuşma."
            ),
        })
    model, temp, max_tokens = choose_generation_params(mode, analysis)

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

    digest = build_weekly_digest(profile, session, garden)
    profile["weekly_report"] = digest

    save_user_state(user_id, profile, notes, garden)
    save_session(user_id, active, session)
    return digest


def chat_fallback_response(plan: Dict[str, Any]) -> str:
    if plan.get("mode") == "luxching":
        return generate_luxching(plan.get("profile", default_profile()), plan.get("analysis", {}), plan.get("message", ""))
    return fallback_reply(plan["mode"], plan["analysis"])


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
        items.append({
            "source": "memory",
            "text": item.get("text", ""),
            "theme": item.get("theme", "belirsiz"),
            "emotion": item.get("emotion", "nötr"),
            "layers": item.get("layers", {}),
            "ts": item.get("ts", ""),
        })

    for msg in reversed(session.get("messages", [])[-10:]):
        if msg.get("role") == "user":
            items.append({
                "source": "session",
                "text": msg.get("content", ""),
                "theme": profile.get("core_trigger", "belirsiz") or "belirsiz",
                "emotion": "nötr",
                "ts": msg.get("ts", ""),
            })

    return {
        "items": items[:20],
        "analysis": build_memory_overview(profile, session, garden),
    }


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
    return {
        "ok": result.get("ok", False),
        "translated_text": result.get("translated_text", payload.text),
        "detected_source_language": result.get("detected_source_language"),
        "error": result.get("error"),
    }


@app.post("/chat")
async def chat(request: ChatRequest, auth: Optional[str] = Header(None)):
    check_auth(auth)

    msg = (request.message or "").strip()
    if not msg:
        return {"response": "Boş mesaj alamam."}

    if len(msg) > 4000:
        return {"response": "Mesajın biraz uzun. Biraz kısaltıp tekrar dener misin?"}

    plan = prepare_chat_plan(
        request.user_id,
        msg,
        request.mode,
        request.ghost_hesitation,
        request.location,
        request.client_signals,
    )

    if plan["kind"] == "command":
        return {
            "response": plan["response"],
            "meta": plan["meta"],
        }

    if plan["kind"] == "crisis":
        return {
            "response": plan["response"],
            "weekly_report": plan.get("weekly_report", {}),
            "memory_preview": plan.get("memory_preview", []),
            "meta": plan.get("meta", {}),
        }

    try:
        response_text = call_model(
            plan["openai_messages"],
            model=plan["model"],
            temperature=plan["temperature"],
            max_tokens=plan["max_tokens"],
        )
        if not response_text:
            response_text = chat_fallback_response(plan)
    except Exception as e:
        logging.warning(f"Model error fallback used: {e}")
        if is_model_auth_error(e):
            response_text = auth_error_response()
        else:
            response_text = chat_fallback_response(plan)

    digest_data = finalize_chat(plan, response_text)
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
            payload = await websocket.receive_json()
            request = ChatRequest(**payload)

            msg = (request.message or "").strip()
            if not msg:
                await websocket.send_json({"type": "done", "response": "Boş mesaj alamam."})
                continue

            if len(msg) > 4000:
                await websocket.send_json({"type": "done", "response": "Mesajın biraz uzun. Biraz kısaltıp tekrar dener misin?"})
                continue

            plan = prepare_chat_plan(
                request.user_id,
                msg,
                request.mode,
                request.ghost_hesitation,
                request.location,
                request.client_signals,
            )

            if plan["kind"] == "command":
                await websocket.send_json({
                    "type": "done",
                    "response": plan["response"],
                    "meta": plan["meta"],
                })
                continue

            if plan["kind"] == "crisis":
                await websocket.send_json({
                    "type": "done",
                    "response": plan["response"],
                    "weekly_report": plan.get("weekly_report", {}),
                    "memory_preview": plan.get("memory_preview", []),
                    "meta": plan.get("meta", {}),
                })
                continue

            full = []
            try:
                await websocket.send_json({
                    "type": "typing",
                    "meta": {
                        "mode": plan["mode"],
                        "session_id": None if plan.get("skip_save") else plan["session"]["session_id"],
                        "ephemeral": bool(plan.get("skip_save")),
                    },
                })

                if client:
                    for chunk in stream_model(
                        plan["openai_messages"],
                        model=plan["model"],
                        temperature=plan["temperature"],
                        max_tokens=plan["max_tokens"],
                    ):
                        full.append(chunk)
                        await websocket.send_json({"type": "chunk", "text": chunk})
                        await asyncio.sleep(0.07)

                    response_text = "".join(full).strip() or chat_fallback_response(plan)
                else:
                    response_text = chat_fallback_response(plan)

                digest_data = finalize_chat(plan, response_text)

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
                    },
                })
            except Exception as e:
                logging.error(f"WS error: {e}")
                if is_model_auth_error(e):
                    response_text = auth_error_response()
                else:
                    response_text = chat_fallback_response(plan)
                digest_data = finalize_chat(plan, response_text)
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
