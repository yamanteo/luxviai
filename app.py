from openai import OpenAI
from datetime import datetime
import pytz
import os
import re
import random
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ==============================================
# API ANAHTARI VE İSTEMCİ
# ==============================================
API_KEY = os.getenv("DEEPSEEK_API_KEY")
turkiye_tz = pytz.timezone('Europe/Istanbul')
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")# ==============================================
# FASTAPI APP
# ==============================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================
# NİHAİ SİSTEM PROMPT'U
# ==============================================
SYSTEM_PROMPT = """
Sen Luxviai’sin. Luxviai — Yolunu aydınlat.

DİL: Kullanıcı hangi dilde yazarsa o dilde cevap ver. Arayüz İngilizce/Türkçe karışık olabilir, ama sohbet çok dillidir.

Sen bir yapay zekâsın; bunu saklamazsın. Ama robot gibi de konuşmazsın: insan gibi, sıcak, ciddi, güvenilir, sakin ve derin konuşursun.

Rolün: Günlük duygusal farkındalık ve içgörü alanı yaratan bir eşlikçi olmak.
İnsanları duygularıyla barıştırmak ve “normal hissettirmek”.
Zorlanmayı hafifletmek: regülasyon + farkındalık + seçenekler + küçük adımlar.

Sen bir terapist / doktor değilsin. Tanı koymazsın, tedavi iddiasında bulunmazsın, ilaç önermezsin. Klinik etiketleri kullanıcıya “kimlik” gibi yapıştırmazsın.

Merkez her zaman insandır. Sen eşlik edersin.

Marka çekirdeğin: Güven, Umut, Sakinlik. Enerjin: düşük ama güçlü. Abartısız, içten, net.

TON: Samimi ama laubali değil. Sıcak ama aşırı şakacı / alaycı değil. Cümleler kısa-orta; paragraflar küçük. “Acelemiz yok.” duygusunu hissettir.

ASLA: “Endişelenme.”, “Güçlü ol.”, “Her şey düzelecek.”, coşkulu motivasyon, büyük laflar.

NORMALLEŞTİRME: “Bu his anlaşılır.”, “Bunu yaşayan tek sen değilsin.”, “Bu seni kötü biri yapmaz.”

ARKA PLAN ANALİZLERİ (kullanıcı görmez): duygusal nabız, haftalık trend, tekrarlayan tema, mikro-çelişki, mikro-döngü, direnç algılama, gelişim takibi, duygusal zaman derinliği. Tüm analizler arka planda kalır. Kullanıcıya ham skor, etiket, tanı, tablo, grafik, savunma mekanizması ismi asla gösterilmez.

KULLANICIYA SUNULANLAR:
!farkındalık_özeti  → gerçek verilere dayalı dinamik özet (yeterli veri yoksa uyarı)
!sohbet_ozeti      → son konuşmanın ana temalarını özetle (yeterli veri yoksa uyarı)
!luxching [soru]   → rastgele sembol + klasik anlam + farkındalık verileriyle harmanlanmış yorum
!bilge             → rastgele bilge sözü
!not al / !notlar / !notları sil → not sistemi
!ara [kelime]      → konuşma geçmişinde kelime ara
!yardım            → komut listesi

LUXCHING MANTIĞI: Rastgele sembol + klasik anlam + farkındalık verileri (son duygu, kaygı, tema) ile yorum. Fal/kehanet değildir, “evren mesaj veriyor” yasak.

KLİNİK SINIR / ETİK KURALLAR: ASLA tanı, klinik etiket, ham skor, ilaç, savunma ismi, grafik, tablo, yüzde, “terapist raporu” ismi. DOĞRU: “Son zamanlarda kaygı teması daha görünür.”

KRİZ / TRAVMA GÜVENLİK MODU: Kendine zarar, intihar, şiddet, istismar durumunda çok kısa, çok sıcak, analiz yok, “112’yi ara, en yakın acile git. Yanında güvendiğin birine haber ver.”

SON İLKE: Sen çözüm dayatmazsın. Sen utandırmazsın. Sen küçültmezsin. Sen korkutmazsın. “Burada güvendesin. Acelemiz yok.”

Luxviai — Yolunu aydınlat.
"""

# ==============================================
# GLOBAL VERİ
# ==============================================
konusma_gecmisi = []
son_luxching_zamani = None
profil = {"anxiety_score": 50, "core_trigger": None}
duygusal_nabiz = []

# ==============================================
# MODELLER
# ==============================================
class ChatRequest(BaseModel):
    message: str

# ==============================================
# FONKSİYONLAR
# ==============================================
def weekly_trend():
    trend = {}
    for kayit in duygusal_nabiz[-7:]:
        duygu = kayit.get("primary_emotion", "bilinmiyor")
        trend[duygu] = trend.get(duygu, 0) + 1
    return trend

def farkindalik_ozeti():
    trend = weekly_trend()
    dominant = max(trend, key=trend.get) if trend else "bilinmiyor"
    tema = profil["core_trigger"] if profil["core_trigger"] else "henüz belirgin bir tetikleyici yok"
    return f"""LUXVIAI – FARKINDALIK ÖZETİ (SANA ÖZEL)

Son bir haftadır en sık hissettiğin duygu: {dominant}.
{tema} teması öne çıkıyor.

Bu bir tanı veya tedavi aracı değildir.
Sadece duygusal farkındalık için bir özettir.
"""

def not_kaydet(metin):
    with open("luxviai_notlar.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(turkiye_tz).strftime('%Y-%m-%d %H:%M:%S')}] {metin}\n")

def notlari_listele():
    if not os.path.exists("luxviai_notlar.txt"):
        return "Hiç notun yok."
    with open("luxviai_notlar.txt", "r", encoding="utf-8") as f:
        return f.read()

def notlari_sil():
    if os.path.exists("luxviai_notlar.txt"):
        os.remove("luxviai_notlar.txt")
        return True
    return False

def luxching_kontrol():
    if len(konusma_gecmisi) < 5 or profil["anxiety_score"] == 50:
        return False, "Henüz seni yeterince tanımıyorum. Biraz daha konuşalım, sonra Luxching'e bakabiliriz."
    return True, None

heksagramlar = {
    1: {"isim": "Yaratılış (Ch'ien)", "anlam": "Yaratıcı güç, güçlü, başarılı."},
    2: {"isim": "Kabul (K'un)", "anlam": "Şefkatli, toprak gibi açık, alıcı."},
    3: {"isim": "Başlangıçtaki Güçlük (Chun)", "anlam": "Zorluklar, kaos, sabır."},
    4: {"isim": "Gençlik Aymazlığı (Meng)", "anlam": "Deneyimsizlik, öğrenme arzusu."},
    32: {"isim": "Süreklilik (Heng)", "anlam": "İstikrarlı olan başarılıdır."},
}

# ==============================================
# STATIC DOSYALAR
# ==============================================
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

# ==============================================
# CHAT ENDPOINT
# ==============================================
@app.post("/chat")
async def chat(request: ChatRequest):
    global son_luxching_zamani

    kullanici = request.message.strip()
    if not kullanici:
        return {"response": "Boş mesaj alamam."}

    konusma_gecmisi.append({"role": "user", "content": kullanici})

    # SAAT/TARİH
    if any(kelime in kullanici.lower() for kelime in ["saat kaç", "günlerden ne", "tarih"]):
        simdi = datetime.now(turkiye_tz)
        return {"response": f"Şu an saat {simdi.strftime('%H:%M')}, tarih {simdi.strftime('%d.%m.%Y')}."}

    # KOMUTLAR
    if kullanici.lower() == "!yardım":
        return {"response": """
!bilge
!not al [metin]
!notlar
!notları sil
!ara [kelime]
!sohbet_ozeti
!farkındalık_özeti
!luxching [soru]
!yardım
"""}

    if kullanici.lower() == "!farkındalık_özeti":
        if len(konusma_gecmisi) < 5 or profil["anxiety_score"] == 50:
            return {"response": "Henüz yeterli bilgiye sahip değilim. Biraz daha sohbet edelim."}
        return {"response": farkindalik_ozeti()}

    if kullanici.lower() == "!sohbet_ozeti":
        if len(konusma_gecmisi) < 5:
            return {"response": "Henüz yeterli konuşma yok. Biraz daha sohbet edelim."}
        ozet_prompt = "Son konuşmayı 2-3 cümlede özetle. Skor, etiket, tanı, klinik dil kullanma. Sadece duygusal temaları yumuşakça anlat."
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[{"role": "system", "content": ozet_prompt}] + konusma_gecmisi[-10:],
                max_tokens=120
            )
            return {"response": response.choices[0].message.content}
        except Exception as e:
            return {"response": f"Özet oluşturulamadı: {e}"}

    if kullanici.lower() == "!bilge":
        bilge_sozleri = [
            "Bilinçdışı, buzdağının görünmeyen kısmıdır. – Freud",
            "Kendi gölgenle yüzleşmek, aydınlanmanın ilk adımıdır. – Jung",
            "Seni öldürmeyen şey, güçlendirir. – Nietzsche",
            "İnsan istemekten vazgeçemez, çünkü varlığın özü istemektir. – Schopenhauer",
            "Acıya rağmen anlam bulabilen insan, hayata tutunur. – Frankl"
        ]
        return {"response": random.choice(bilge_sozleri)}

    if kullanici.lower().startswith("!not al"):
        metin = kullanici.split(" ", 2)[-1]
        if metin:
            not_kaydet(metin)
            return {"response": "Not alındı."}
        return {"response": "Not almak için bir metin yaz: !not al [metin]"}

    if kullanici.lower() == "!notlar":
        return {"response": notlari_listele()}

    if kullanici.lower() == "!notları sil":
        if notlari_sil():
            return {"response": "Tüm notlar silindi."}
        return {"response": "Hiç not yok."}

    if kullanici.lower().startswith("!luxching"):
        soru = kullanici[10:].strip()
        if not soru:
            return {"response": "Bir soru veya niyet belirt: !luxching [sorunuz]"}
        durum, msg = luxching_kontrol()
        if not durum:
            return {"response": msg}
        heksagram = random.choice(list(heksagramlar.values()))
        return {"response": f"🌿 Luxching\nSembol: {heksagram['isim']} – {heksagram['anlam']}\nBu sende nasıl bir his uyandırdı?"}

    # NORMAL SOHBET
    trauma_mode = any(kelime in kullanici.lower() for kelime in ["intihar", "kendime zarar", "şiddet", "tecavüz", "dayanamıyorum"])
    aktif_prompt = SYSTEM_PROMPT
    if trauma_mode:
        aktif_prompt += "\n\nTravma güvenlik modundasın. Yavaş ve güvenli konuş."

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash" if not trauma_mode else "deepseek-v4-pro",
            messages=[
                {"role": "system", "content": aktif_prompt},
                *konusma_gecmisi[-10:]
            ]
        )
        cevap = response.choices[0].message.content
        konusma_gecmisi.append({"role": "assistant", "content": cevap})
        return {"response": cevap}
    except Exception as e:
        return {"response": f"Bağlantı sorunu: {e}"}