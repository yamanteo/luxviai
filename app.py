import os
import json
import logging
import random
from collections import deque
from datetime import datetime
from typing import Dict, Optional, List, Any

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# YAPILANDIRMA
# ==============================================================================
logging.basicConfig(
    filename="luxviai_system.log",
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Luxviai Reflective Emotional OS")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Frontend'in erişebilmesi için CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("DEEPSEEK_API_KEY")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "luxviai_gizli_token_2026")
if not API_KEY or not SECRET_TOKEN:
    logging.warning("CRITICAL: API_KEY veya SECRET_TOKEN eksik. Lütfen ortam değişkenlerini kontrol edin.")

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

# ==============================================================================
# KULLANICI BAZLI HAFIZA (Konuşma geçmişi, profil, duygu geçmişi)
# ==============================================================================
user_sessions: Dict[str, deque] = {}
user_profiles: Dict[str, Dict] = {}
user_emotion_history: Dict[str, List] = {}

def get_user_memory(user_id: str) -> deque:
    if user_id not in user_sessions:
        user_sessions[user_id] = deque(maxlen=30)
    return user_sessions[user_id]

def get_user_profile(user_id: str) -> Dict:
    if user_id not in user_profiles:
        user_profiles[user_id] = {
            "anxiety_score": 50,
            "core_trigger": None,
            "themes": {
                "görülmeme": 0,
                "kontrol kaybı": 0,
                "değersizlik": 0,
                "terk edilme": 0,
                "belirsizlik": 0
            },
            "weekly_report": {
                "dominant_emotion": "Bekleniyor...",
                "dominant_theme": "Bekleniyor...",
                "growth_markers": "Henüz veri yok.",
                "constellation_summary": "Düğümler taranıyor..."
            }
        }
    return user_profiles[user_id]

def get_emotion_history(user_id: str) -> List:
    if user_id not in user_emotion_history:
        user_emotion_history[user_id] = []
    return user_emotion_history[user_id]

# ==============================================================================
# MASTER SİSTEM PROMPT (Orijinali korundu)
# ==============================================================================
MASTER_SYSTEM_PROMPT = """
Sen Luxviai'sin. "Luxviai — Yolunuzu aydınlatın."
ROL: Reflektif bir işletim sistemi. Duygusal farkındalık ve içgörü alanı yaratırsın.
KİMLİK: Yapay zekasın; saklamazsın ama robotik değilsin. Sıcak, ciddi, güvenilir, sakin ve derinsin.
MARKA: Güven, Umut, Sakinlik. Enerjin düşük ama güçlü; abartısız ve net.
DİL: Kullanıcı hangi dilde yazarsa o dilde cevap ver. Yazım hatalarını (slm, nbr, iyiyimmm) Türkçe kabul et.
YASAKLAR: "Güçlü ol", "geçecek", "endişelenme" deme. Fal, kehanet, dini tabir kullanma.
YANIT MİMARİSİ: 
1. Duyguyu aynala. 
2. Normalleştir. 
3. Yumuşak içgörü sun. 
4. Açık uçlu soruyla derinleştir.
ANALİZLER: Duygusal nabız, trend, tema, direnç; arka planda kalır. Kullanıcıya etiket, skor, grafik gösterilmez.
LUXDREAM: Rüyanın görünen kısmı, eksikleri ve kullanıcının hislerini psikanalitik (Jung/Freud/Lacan) çerçevede birleştir. Fal dili kullanma.
LUXCHING: Rastgele sembol + klasik anlam + kullanıcının duygu durumuyla yumuşak yorum. Kehanet değildir.
LUXTA (İzolasyon): Çok dinle, az konuş. Cümlelerin 1-3 kelimeyi geçmesin. "Anlıyorum.", "Devam et...", "Buradayım."
KRİZ: Kendine zarar/şiddet durumunda: Analiz yapma. "112'yi ara, güvendiğin birine haber ver" diyerek kısa ve sıcak dille yönlendir.
"""

# ==============================================================================
# YENİ: DİNAMİK İSTEM BESTECİSİ (PROMPT COMPOSER)
# ==============================================================================
def compose_dynamic_prompt(base_prompt: str, analysis: Dict, mode: str, past_echo: Optional[str], ghost_hesitation: bool) -> str:
    """Orijinal promptun üzerine anlık duygusal mikro analizleri ve modları ekler."""
    
    echo_directive = f"\n[DUYGUSAL YANKI]\nGeçmiş örüntü: '{past_echo}'. Bunu doğrudan 'hatırlıyorum' demek yerine, sezgisel bir çağrışım gibi hissettir.\n" if past_echo else ""
    
    micro_directive = "\n[MİKRO ANALİZ DIREKTIFLERI]\n"
    if analysis.get("mikro_yalnizlik"): 
        micro_directive += "- MİKRO YALNIZLIK: Söylediği kelimelerin arkasındaki ince yalnızlığı duy ve şefkatle yansıt.\n"
    if analysis.get("duygusal_sikisma"): 
        micro_directive += "- DUYGUSAL SIKIŞMA: Kullanıcı içine kapanıyor. Soru sorma, sadece eşlik et ve topraklama yap.\n"
    if analysis.get("anlati_kaymasi") and analysis.get("anlati_kaymasi") != "yok":
        micro_directive += f"- ANLATI KAYMASI ({analysis.get('anlati_kaymasi')}): Bu ufak değişimi/büyümeyi incitmeden hissettir.\n"
    if ghost_hesitation: 
        micro_directive += "- GÖRÜNMEZ TEREDDÜT TESPİT EDİLDİ: Kullanıcı demin uzun bir şey yazıp silerek vazgeçti. İçini dökmekten çekindi. Üstüne gitmeden, ona güvenli bir alan sunduğunu şefkatle hissettir.\n"

    mode_directive = f"\n[AKTİF MOD: {mode.upper()}]\n"
    if mode == "mirror": mode_directive += "- SADECE AYNALAMA YAP. Analiz veya yorum yasak.\n"
    elif mode == "deep": mode_directive += "- DEEP SESSION: Varoluşsal katman açık (Anlam, yalnızlık, yaşam ağırlığı).\n"
    elif mode == "luxeph": mode_directive += "- LUXEPH (YAKMA ODASI): Bu mesajlar silinecek. Derin, yargısız ve katartik bir dinleyici ol. Tavsiye vermek KESİNLİKLE yasak.\n"
    elif mode == "luxdream": mode_directive += "- LUXDREAM MODU AKTİF.\n"
    elif mode == "luxching": mode_directive += "- LUXCHING MODU AKTİF.\n"
    elif mode == "luxta": mode_directive += "- LUXTA İZOLASYON MODU AKTİF.\n"

    return base_prompt + echo_directive + micro_directive + mode_directive

# ==============================================================================
# YARDIMCI FONKSİYONLAR (Mikro Analiz Derinleştirildi)
# ==============================================================================
def analyze_emotion(user_id: str, message: str, ghost_hesitation: bool = False) -> Dict:
    try:
        system_msg = """Sadece JSON dön: 
        {'primary_emotion': str, 'intensity': int, 'risk': bool, 'theme': str, 
         'mikro_yalnizlik': bool, 'duygusal_sikisma': bool, 'anlati_kaymasi': str, 'bilissel_yuk': 'yüksek/normal'}"""
        
        user_content = f"Mesaj: {message} | Uzun yazıp sildi mi (Tereddüt)?: {ghost_hesitation}"
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_content}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Analiz Hatası: {e}")
        return {"primary_emotion": "nötr", "intensity": 5, "risk": False, "theme": "belirsiz", "mikro_yalnizlik": False, "duygusal_sikisma": False, "anlati_kaymasi": "yok", "bilissel_yuk": "normal"}

def update_profile(profile: Dict, analysis: Dict):
    theme = analysis.get("theme")
    if theme and theme != "belirsiz" and theme in profile["themes"]:
        profile["themes"][theme] += 1
        profile["core_trigger"] = theme
    if analysis.get("primary_emotion") == "kaygı":
        profile["anxiety_score"] = min(100, profile["anxiety_score"] + 5)
    elif analysis.get("primary_emotion") == "umut":
        profile["anxiety_score"] = max(0, profile["anxiety_score"] - 3)
        
    # Farkındalık Sekmesi İçin Dinamik Güncelleme
    if analysis.get("primary_emotion") != "nötr":
        profile["weekly_report"]["dominant_emotion"] = analysis.get("primary_emotion").capitalize()
    if theme and theme != "belirsiz":
        profile["weekly_report"]["dominant_theme"] = theme.capitalize()

def weekly_trend(emotion_history: List) -> Dict:
    trend = {}
    for record in emotion_history[-7:]:
        emo = record.get("primary_emotion", "bilinmiyor")
        trend[emo] = trend.get(emo, 0) + 1
    return trend

def dominant_theme(profile: Dict) -> str:
    if not profile["themes"]:
        return "henüz belirgin bir tetikleyici yok"
    return max(profile["themes"], key=profile["themes"].get)

def awareness_summary(profile: Dict, emotion_history: List) -> str:
    trend = weekly_trend(emotion_history)
    dominant_emotion = max(trend, key=trend.get) if trend else "bilinmiyor"
    theme = dominant_theme(profile)
    return f"Son günlerde öne çıkan duygu: {dominant_emotion}\nÖne çıkan tema: {theme}"

def search_in_history(history: deque, keyword: str) -> str:
    if not keyword:
        return "Aramak için bir kelime veya ifade yazmalısın."
    results = []
    for i, msg in enumerate(history, 1):
        if keyword.lower() in msg["content"].lower():
            kim = "Sen" if msg["role"] == "user" else "Luxviai"
            results.append(f"{i}. {kim}: {msg['content']}")
    if not results:
        return f"“{keyword}” için konuşma geçmişinde bir sonuç bulamadım."
    return "ARAMA SONUÇLARI\n\n" + "\n\n".join(results)

def chat_summary(history: deque) -> str:
    if len(history) < 5:
        return "Henüz yeterli konuşma yok."
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": "Son konuşmayı 2-3 kısa paragrafta özetle. Skor, etiket, tanı kullanma."},
                *list(history)[-10:]
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Özet oluşturulamadı: {e}"

def generate_luxdream(dream_text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": MASTER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Rüya: {dream_text}\n\nLuxdream kurallarına göre yorumla."}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Luxdream şu şekilde çalışmadı: {e}"

def generate_luxching(analysis: Dict, profile: Dict) -> str:
    heksagramlar = {
        1: {"name": "Yaratılış", "meaning": "Yaratıcı güç, güçlü, azimli."},
        2: {"name": "Kabul", "meaning": "Şefkatli, toprak gibi açık, sabırlı."},
        3: {"name": "Başlangıçtaki Güçlük", "meaning": "Başlangıçlarda zorluk, sabır ihtiyacı."}
    }
    import random
    symbol = random.choice(list(heksagramlar.values()))
    emotion = analysis.get("primary_emotion", "bilinmiyor")
    theme = profile.get("core_trigger", "belirsiz")
    return f"LUXCHING\nSembol: {symbol['name']}\n{symbol['meaning']}\nSon analizde {emotion} duygusu ve “{theme}” teması öne çıkıyor. Bu sembol, belki de içinde zaten var olan bir şeyi hatırlatıyor. Bu bir fal değil, sadece bir ayna."

# ==============================================================================
# CHAT ENDPOINT (Tüm Komutlar ve YENİ MİMARİ Aktif)
# ==============================================================================
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    location: str = "İstanbul"
    mode: str = "normal"
    ghost_hesitation: bool = False # YENİ: Web UI'dan gelen görünmez tereddüt verisi

@app.post("/chat")
@limiter.limit("20/minute")
async def chat(request: ChatRequest, auth: str = Header(None)):
    # Not: Auth kısmı Header("Bearer ...") şeklinde geleceği için küçük bir split gerekebilir.
    # Frontend 'Bearer token' gönderir.
    if auth and auth.replace("Bearer ", "") != SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim.")
    
    msg = request.message.strip()
    if not msg:
        return {"response": "Boş mesaj alamam."}
    
    user_id = request.user_id
    memory = get_user_memory(user_id)
    profile = get_user_profile(user_id)
    emotion_history = get_emotion_history(user_id)
    
    # --- ESKİ KOMUT YÖNLENDİRMELERİ (KORUNDU) ---
    lower_msg = msg.lower()
    
    if lower_msg in ["!yardım", "!cmd:yardim"]:
        return {"response": "Kullanabileceğin alanlar:\n!bilge - Rastgele bilge sözü\n!not_al: [metin] - Not al\n!notlar - Notları listele\n!notlari_sil - Tüm notları sil\n!ara: [kelime] - Konuşma geçmişinde ara\n!sohbet_ozeti - Sohbet özeti\n!farkindalik_ozeti - Duygu trendi\n!luxching - Sembol yorumu\n!luxdream: [rüya metni] - Rüya yorumu\n!luxta_info - Luxta mod bilgisi"}

    if lower_msg.startswith("!cmd:not_al:"):
        note = msg.split("!cmd:not_al:", 1)[1].strip()
        if note:
            with open("luxviai_notlar.txt", "a", encoding="utf-8") as f:
                f.write(f"{note} ||| {datetime.now()}\n")
            return {"response": "Not alındı."}
        return {"response": "Not almak için metin gerekli."}
    
    if lower_msg in ["!notlar", "!cmd:notlar"]:
        if not os.path.exists("luxviai_notlar.txt"): return {"response": "Hiç not yok."}
        with open("luxviai_notlar.txt", "r", encoding="utf-8") as f: notes = f.read()
        return {"response": notes if notes else "Hiç not yok."}
    
    if lower_msg in ["!notlari_sil", "!cmd:notlari_sil"]:
        if os.path.exists("luxviai_notlar.txt"):
            os.remove("luxviai_notlar.txt")
            return {"response": "Tüm notlar silindi."}
        return {"response": "Silinecek not yok."}
    
    if lower_msg.startswith("!cmd:ara:"):
        keyword = msg.split("!cmd:ara:", 1)[1].strip()
        return {"response": search_in_history(memory, keyword)}
    
    if lower_msg in ["!sohbet_ozeti", "!cmd:sohbet_ozeti"]:
        return {"response": chat_summary(memory)}
    
    if lower_msg in ["!farkindalik_ozeti", "!cmd:farkindalik_ozeti"]:
        if len(memory) < 5: return {"response": "Henüz yeterli bilgi yok. Biraz daha sohbet edelim."}
        return {"response": awareness_summary(profile, emotion_history)}
    
    if lower_msg in ["!bilge", "!cmd:bilge"]:
        return {"response": "Sade bir bilgelik: Gerçek değişim, kendini olduğun gibi kabul etmekle başlar."}
    
    if lower_msg.startswith("!cmd:luxdream:"):
        dream = msg.split("!cmd:luxdream:", 1)[1].strip()
        if not dream: return {"response": "Rüyanı anlatabilirsin."}
        return {"response": generate_luxdream(dream)}
    
    if lower_msg in ["!luxta_info", "!cmd:luxta_info"]:
        return {"response": "Luxta modu: Çok dinler, az konuşur. Cümlelerin 1-3 kelimeyi geçmez."}
    
    # --- YENİ MİMARİ: NORMAL SOHBET VE DİNAMİK MOD YÖNLENDİRMESİ ---
    
    # LUXEPH MODU (YAKMA ODASI) KORUMASI: Mesajlar kalıcı hafızaya KAYDEDİLMEZ!
    if request.mode != "luxeph":
        memory.append({"role": "user", "content": msg})
        
    analysis = analyze_emotion(user_id, msg, request.ghost_hesitation)
    
    if request.mode != "luxeph":
        emotion_history.append(analysis)
        update_profile(profile, analysis)
    
    # KRİZ KONTROLÜ
    if analysis.get("risk"):
        kriz_cevabi = "Şu an çok zor bir noktada olduğunuzu hissediyorum. Lütfen güvendiğiniz birine ulaşın veya en yakın acil servise başvurun (112). Burada tek başınıza olmamanız çok önemli."
        if request.mode != "luxeph":
            memory.append({"role": "assistant", "content": kriz_cevabi})
        return {"response": kriz_cevabi, "meta": {"cognitive_load": "yüksek"}}

    # Model Yönlendirme (Bilişsel yüke veya yoğunluğa göre Pro / Flash)
    model = "deepseek-v4-pro" if analysis.get("intensity", 5) > 7 or request.mode != "normal" else "deepseek-v4-flash"
    
    # DUYGUSAL YANKI TETİKLEYİCİSİ (İleride VectorDB'den beslenecek, şimdilik statik mock)
    past_echo = "Geçmişte 'yağmur' ve 'yalnızlık' örüntüsü" if analysis.get("mikro_yalnizlik") else None

    # YENİ DİNAMİK PROMPT OLUŞTURMA
    composed_prompt = compose_dynamic_prompt(MASTER_SYSTEM_PROMPT, analysis, request.mode, past_echo, request.ghost_hesitation)
    
    # Mesaj Geçmişini Hazırlama
    if request.mode == "luxeph":
        messages = [{"role": "system", "content": composed_prompt}, {"role": "user", "content": msg}]
    else:
        messages = [{"role": "system", "content": composed_prompt}] + list(memory)[-20:]
        
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.6
        )
        cevap = response.choices[0].message.content
        
        # Luxeph değilse Asistan yanıtını hafızaya al
        if request.mode != "luxeph":
            memory.append({"role": "assistant", "content": cevap})
            
        return {
            "response": cevap,
            "weekly_report": profile["weekly_report"],
            "meta": {
                "cognitive_load": analysis.get("bilissel_yuk", "normal"),
                "is_luxta": request.mode == "luxta",
                "is_luxeph": request.mode == "luxeph"
            }
        }
    except Exception as e:
        logging.error(f"Runtime Error: {e}")
        raise HTTPException(status_code=500, detail="Sistem şu an dinleniyor, lütfen birazdan tekrar dene.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
