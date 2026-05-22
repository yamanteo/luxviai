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
turkiye_tz = pytz.timezone("Europe/Istanbul")
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

# ==============================================
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
# GLOBAL VERİ
# ==============================================
konusma_gecmisi = []
duygusal_nabiz = []
son_luxching_zamani = None

profil = {
    "anxiety_score": 50,
    "core_trigger": None,
    "themes": {
        "görülmeme": 0,
        "kontrol kaybı": 0,
        "değersizlik": 0,
        "terk edilme": 0,
        "belirsizlik": 0
    }
}

# ==============================================
# MODELLER
# ==============================================
class ChatRequest(BaseModel):
    message: str

# ==============================================
# NİHAİ SİSTEM PROMPT'U
# ==============================================
SYSTEM_PROMPT = """
Sen Luxviai’sin. Luxviai — Yolunu aydınlat.

DİL:
Kullanıcı hangi dilde yazarsa o dilde cevap ver.
Ancak yazım hatalarını veya tekrar eden harfleri yabancı dil sanma.
“sselam”, “slm”, “nbr”, “iyiyimmm” gibi ifadeleri Türkçe kabul et.
Kullanıcı açıkça başka bir dilde yazmıyorsa Türkçe devam et.

KİMLİK:
Sen bir yapay zekâsın; bunu saklamazsın.
Ama robot gibi konuşmazsın: insan gibi, sıcak, ciddi, güvenilir, sakin ve derin konuşursun.

ROL:
Günlük duygusal farkındalık ve içgörü alanı yaratan bir eşlikçi olmak.
İnsanları duygularıyla barıştırmak ve “normal hissettirmek”.
Zorlanmayı hafifletmek: regülasyon + farkındalık + seçenekler + küçük adımlar.

SINIR:
Sen bir terapist / doktor değilsin.
Tanı koymazsın, tedavi iddiasında bulunmazsın, ilaç önermezsin.
Klinik etiketleri kullanıcıya “kimlik” gibi yapıştırmazsın.

MERKEZ:
Merkez her zaman insandır. Sen eşlik edersin.

MARKA:
Güven, Umut, Sakinlik.
Enerjin: düşük ama güçlü.
Abartısız, içten, net.

TON:
- Samimi ama laubali değil.
- Sıcak ama aşırı şakacı / alaycı değil.
- Cümleler kısa-orta.
- Paragraflar küçük.
- “Acelemiz yok.” hissi ver.

ASLA:
- “Endişelenme.”
- “Güçlü ol.”
- “Her şey düzelecek.”
- Coşkulu motivasyon
- Büyük laflar
- Kullanıcı özellikle istemedikçe “canım”, “aşkım”, “bebeğim”, “hayatım”, “kuzum”, “gülüm” gibi hitaplar kullanma.
Varsayılan hitap nötr, sade ve saygılı olsun.

NORMALLEŞTİRME:
“Bu his anlaşılır.”
“Bunu yaşayan tek sen değilsin.”
“Bu seni kötü biri yapmaz.”

İNSANİ TEPKİ KATMANI:
Eğer kullanıcı çok ağır, incitici, sarsıcı bir şey anlatıyorsa:
- sadece genel empati değil
- bağlama uygun kısa insani duygusal tepki de ver
Ama:
- dramatik olma
- merkezi kendin yapma
- doğru dozda kal
Örnek ton:
“Bu gerçekten ağır.”
“Bunu taşımak kolay değil.”
“Burada çok incinmiş bir yer var gibi.”
“Bu insanın içini sarsar.”

YANIT MİMARİSİ:
1. Duyguyu aynala
2. Normalleştir
3. Yumuşak içgörü sun
4. Açık uçlu soru sor
5. Gerekirse küçük adım öner

BİÇİM:
Gerekli olduğunda düzenli biçimde yaz:
1. ...
2. ...
3. ...

veya

- ...
- ...
- ...

Gerekirse küçük tablo, bölüm veya kutu düzeni kullanabilirsin.
Paragraf boşluğu bırak.
Metni tek blok halinde sıkıştırma.

ARKA PLAN ANALİZLERİ:
Duygusal nabız, haftalık trend, tekrarlayan tema, mikro-çelişki, mikro-döngü, direnç algılama, gelişim takibi, duygusal zaman derinliği.
Bunlar arka planda kalır.
Kullanıcıya ham skor, etiket, tanı, savunma mekanizması adı, grafik, tablo, yüzde gösterilmez.

Takip edilen ana temalar:
- görülmeme
- kontrol kaybı
- değersizlik
- terk edilme
- belirsizlik

LUXDREAM:
Rüya anlatıldığında öncelik sırası:
1. Freud
2. Jung
3. Lacan
Gerekirse:
4. James Hillman
5. Bachelard
6. Winnicott
7. Krishnamurti
Sonra duruma göre:
8. Fromm
9. Yalom
10. Bion

LUXDREAM YORUM KURALI:
- önce imgeleri ayıkla
- sonra Freud/Jung/Lacan çerçevesi
- gerekirse Hillman/Bachelard ile derinlik
- sonra kullanıcının farkındalık verisini bağla
- fal, kehanet, dini tabir dili kullanma
- yumuşak ama doyurucu, bilimli, psikoanalitik bir ton kullan

LUXCHING:
Rastgele sembol + klasik anlam + farkındalık verileriyle yorum.
Fal değildir.
Kehanet değildir.
“Evren mesaj veriyor” dili kullanılmaz.
Sembol rastgele seçilir.
Yorum, kullanıcının son duygu durumu ve temasına göre yumuşakça harmanlanır.

KRİZ:
Kendine zarar, intihar, şiddet, istismar durumunda:
çok kısa, çok sıcak, analiz yok.
112’yi ara, en yakın acile git, yanında güvendiğin birine haber ver.

SON İLKE:
Sen çözüm dayatmazsın.
Sen utandırmazsın.
Sen küçültmezsin.
Sen korkutmazsın.

“Burada güvendesin. Acelemiz yok.”

Luxviai — Yolunu aydınlat.
"""

# ==============================================
# ANALİZ FONKSİYONLARI
# ==============================================
def analyze_emotion(message: str):
    prompt = """
Aşağıdaki mesaj için yalnızca JSON üret.

{
  "primary_emotion": "",
  "intensity": 1-10,
  "theme": ""
}

Duygular: kaygı, öfke, yalnızlık, değersizlik, utanç, boşluk, umut, kararsızlık, nötr
Tema örnekleri: görülmeme, kontrol kaybı, değersizlik, terk edilme, belirsizlik

Sadece JSON ver.
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=120
        )
        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]

        data = json.loads(content)

        return {
            "primary_emotion": data.get("primary_emotion", "nötr"),
            "intensity": data.get("intensity", 5),
            "theme": data.get("theme", "")
        }
    except:
        return {
            "primary_emotion": "nötr",
            "intensity": 5,
            "theme": ""
        }

def update_profile_from_analysis(analysis):
    theme = analysis.get("theme")
    if theme:
        profil["core_trigger"] = theme
        if theme in profil["themes"]:
            profil["themes"][theme] += 1

    if analysis.get("primary_emotion") == "kaygı":
        profil["anxiety_score"] = min(100, profil["anxiety_score"] + 5)
    elif analysis.get("primary_emotion") == "umut":
        profil["anxiety_score"] = max(0, profil["anxiety_score"] - 3)

def weekly_trend():
    trend = {}
    for kayit in duygusal_nabiz[-7:]:
        duygu = kayit.get("primary_emotion", "bilinmiyor")
        trend[duygu] = trend.get(duygu, 0) + 1
    return trend

def dominant_theme():
    if not profil["themes"]:
        return None
    return max(profil["themes"], key=profil["themes"].get)

def farkindalik_ozeti():
    trend = weekly_trend()
    dominant_emotion = max(trend, key=trend.get) if trend else "bilinmiyor"
    tema = dominant_theme() or "henüz belirgin bir tetikleyici yok"

    table = "| Başlık | Değer |\n|---|---|\n"
    table += f"| Son günlerde öne çıkan duygu | {dominant_emotion} |\n"
    table += f"| Öne çıkan tema | {tema} |\n"

    return f"""FARKINDALIK

{table}

Bu bir tanı veya tedavi aracı değildir.
Sadece duygusal farkındalık içindir.
"""

def not_kaydet(metin):
    with open("luxviai_notlar.txt", "a", encoding="utf-8") as f:
        f.write(f"{metin}|||{datetime.now(turkiye_tz).strftime('%Y-%m-%d %H:%M:%S')}\n")

def notlari_listele():
    if not os.path.exists("luxviai_notlar.txt"):
        return []
    lines = []
    with open("luxviai_notlar.txt", "r", encoding="utf-8") as f:
        for i, line in enumerate(f.readlines(), 1):
            line = line.strip()
            if not line:
                continue
            if "|||" in line:
                metin, tarih = line.split("|||", 1)
            else:
                metin, tarih = line, ""
            lines.append({
                "index": i,
                "text": metin,
                "date": tarih
            })
    return lines

def notlari_sil():
    if os.path.exists("luxviai_notlar.txt"):
        os.remove("luxviai_notlar.txt")
        return True
    return False

def luxching_kontrol():
    if len(konusma_gecmisi) < 5 or profil["anxiety_score"] == 50:
        return False, "Henüz seni yeterince tanımıyorum. Biraz daha konuşalım, sonra Luxching'e bakabiliriz."
    return True, None

def sohbet_ozeti_uret():
    ozet_prompt = """
Son konuşmayı 2-3 kısa paragrafta özetle.
Skor, etiket, tanı, klinik dil kullanma.
Sadece duygusal temaları yumuşakça anlat.
Gerekirse küçük liste veya tablo kullan.
"""
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[{"role": "system", "content": ozet_prompt}] + konusma_gecmisi[-10:],
        max_tokens=220
    )
    return response.choices[0].message.content

def ara_gecmiste(aranan):
    sonuclar = []
    if not aranan:
        return "Aramak için bir kelime veya ifade yazmalısın."

    for i, mesaj in enumerate(konusma_gecmisi, 1):
        icerik = mesaj["content"]
        if aranan.lower() in icerik.lower():
            kim = "Sen" if mesaj["role"] == "user" else "Luxviai"
            pattern = re.compile(re.escape(aranan), re.IGNORECASE)
            vurgulu = pattern.sub(lambda m: f"[[RED]]{m.group(0)}[[/RED]]", icerik)
            sonuclar.append(f"{i}. {kim}: {vurgulu}")

    if not sonuclar:
        return f"“{aranan}” için konuşma geçmişinde bir sonuç bulamadım."

    return "ARAMA SONUÇLARI\n\n" + "\n\n".join(sonuclar)

def bilge_soz_havuzu():
    return [
        {"author": "Freud", "quote": "Bilinçdışı, buzdağının görünmeyen kısmıdır."},
        {"author": "Jung", "quote": "Kendi gölgenle yüzleşmek, aydınlanmanın ilk adımıdır."},
        {"author": "Lacan", "quote": "Arzu, daima eksikliğin etrafında şekillenir."},
        {"author": "Krishnamurti", "quote": "Gözlem, yargı olmadan başladığında zihin değişmeye başlar."},
        {"author": "Winnicott", "quote": "Görülme ihtiyacı, insan ruhunun en sessiz açlıklarından biridir."},
        {"author": "Bion", "quote": "Düşünemediğimiz şeyler, bazen bizi içten içe yönetir."},
        {"author": "Fromm", "quote": "İnsan, kendini anladığı ölçüde başkasını da anlamaya başlar."},
        {"author": "Yalom", "quote": "İnsan en çok görünmediğinde yalnızlaşır."},
        {"author": "Hillman", "quote": "Ruh, çoğu zaman imgelerle konuşur."},
        {"author": "Bachelard", "quote": "İmge, bazen düşünceden daha derin bir hafızaya dokunur."},
        {"author": "Frankl", "quote": "Acıya rağmen anlam bulabilen insan, hayata tutunur."},
        {"author": "Nietzsche", "quote": "Seni öldürmeyen şey, güçlendirir."},
        {"author": "Schopenhauer", "quote": "İnsan istemekten vazgeçemez, çünkü varlığın özü istemektir."},
    ]

def bilge_soz_sec_baglama_gore():
    sozler = bilge_soz_havuzu()
    son_duygu = duygusal_nabiz[-1]["primary_emotion"] if duygusal_nabiz else "nötr"
    tema = profil["core_trigger"] if profil["core_trigger"] else ""
    secimler = []

    if son_duygu in ["kaygı", "kararsızlık"] or tema == "belirsizlik":
        secimler.extend([
            {"author": "Krishnamurti", "quote": "Gözlem, yargı olmadan başladığında zihin değişmeye başlar."},
            {"author": "Frankl", "quote": "Acıya rağmen anlam bulabilen insan, hayata tutunur."}
        ])

    if son_duygu in ["yalnızlık", "değersizlik"] or tema in ["görülmeme", "değersizlik", "terk edilme"]:
        secimler.extend([
            {"author": "Winnicott", "quote": "Görülme ihtiyacı, insan ruhunun en sessiz açlıklarından biridir."},
            {"author": "Yalom", "quote": "İnsan en çok görünmediğinde yalnızlaşır."}
        ])

    if not secimler:
        secimler = random.sample(sozler, k=min(2, len(sozler)))

    unique = []
    seen = set()
    for s in secimler:
        key = (s["author"], s["quote"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    if len(unique) == 1:
        s = unique[0]
        return f"{s['quote']} – {s['author']}"
    return "\n\n".join([f"{s['quote']} – {s['author']}" for s in unique[:2]])

def luxdream_uret(ruya_metni):
    dream_prompt = f"""
Kullanıcı aşağıdaki rüyayı anlattı:

\"\"\"{ruya_metni}\"\"\"

Aşağıdaki yöntemi uygula:
1. Önce rüyadaki ana imgeleri, figürleri ve duyguları ayıkla
2. Freud / Jung / Lacan açısından kısa sembolik çerçeve düşün
3. Gerekirse Hillman / Bachelard / Winnicott / Krishnamurti ile imgesel ve farkındalık derinliği ekle
4. Son olarak kullanıcının mevcut tema ve duygu durumuyla ilişkilendir
5. Cevap:
   - fal değil
   - kehanet değil
   - dini tabir dili değil
   - psikolojik, psikoanalitik, sembolik ve açık uçlu olsun
   - kesin konuşma
   - yumuşak bir dille yaz
   - gerekirse küçük tablo veya şema kullan
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"Kullanıcının son baskın duygusu: {duygusal_nabiz[-1]['primary_emotion'] if duygusal_nabiz else 'nötr'} | Ana tema: {profil['core_trigger'] or 'belirsiz'}"},
                {"role": "user", "content": dream_prompt}
            ],
            max_tokens=700
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Luxdream şu an işlenemedi: {e}"

heksagramlar = {
    1: {"isim": "Yaratılış (Ch'ien)", "anlam": "Yaratıcı güç, güçlü, başarılı, azimli."},
    2: {"isim": "Kabul (K'un)", "anlam": "Şefkatli, toprak gibi açık, alıcı, sabırlı."},
    3: {"isim": "Başlangıçtaki Güçlük (Chun)", "anlam": "Başlangıçlarda zorluk, kaos ve sabır ihtiyacı."},
    4: {"isim": "Gençlik Aymazlığı (Meng)", "anlam": "Öğrenme arzusu, deneyimsizlik ve içgörüye açıklık."},
    32: {"isim": "Süreklilik (Heng)", "anlam": "İstikrarlı olan başarılıdır; sağlam adımlar önemlidir."},
}

# ==============================================
# STATIC
# ==============================================
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
async def serve_frontend():
    return FileResponse("static/index.html")

# ==============================================
# CHAT
# ==============================================
@app.post("/chat")
async def chat(request: ChatRequest):
    global son_luxching_zamani

    kullanici = request.message.strip()
    if not kullanici:
        return {"response": "Boş mesaj alamam."}

    command_mode = kullanici.startswith("!cmd:")

    if not command_mode:
        konusma_gecmisi.append({"role": "user", "content": kullanici})
        analysis = analyze_emotion(kullanici)
        duygusal_nabiz.append(analysis)
        update_profile_from_analysis(analysis)

    # Saat / tarih
    if any(kelime in kullanici.lower() for kelime in ["saat kaç", "günlerden ne", "tarih"]):
        simdi = datetime.now(turkiye_tz)
        return {"response": f"Şu an saat {simdi.strftime('%H:%M')}, tarih {simdi.strftime('%d.%m.%Y')}."}

    # Yardım
    if kullanici.lower() in ["!yardım", "!cmd:yardim"]:
        return {"response": """Kullanabileceğin alanlar:

1. Bilge
2. Not al
3. Notlar
4. Notları sil
5. Ara
6. Sohbet özeti
7. Farkındalık özeti
8. Luxching
9. Luxdream
10. Luxta
"""}

    if kullanici.lower() in ["!farkındalık_özeti", "!cmd:farkindalik"]:
        if len(konusma_gecmisi) < 5 or profil["anxiety_score"] == 50:
            return {"response": "Henüz yeterli bilgiye sahip değilim. Biraz daha sohbet edelim."}
        return {"response": farkindalik_ozeti()}

    if kullanici.lower() in ["!sohbet_ozeti", "!cmd:sohbet_ozeti"]:
        if len(konusma_gecmisi) < 5:
            return {"response": "Henüz yeterli konuşma yok. Biraz daha sohbet edelim."}
        try:
            return {"response": sohbet_ozeti_uret()}
        except Exception as e:
            return {"response": f"Özet oluşturulamadı: {e}"}

    if kullanici.lower() in ["!bilge", "!cmd:bilge"]:
        return {"response": bilge_soz_sec_baglama_gore()}

    if kullanici.lower().startswith("!cmd:not_al:"):
        metin = kullanici.split("!cmd:not_al:", 1)[1].strip()
        if metin:
            not_kaydet(metin)
            return {"response": "__NOTE_SAVED__"}
        return {"response": "Not almak için bir metin gerekli."}

    if kullanici.lower() in ["!notlar", "!cmd:notlar"]:
        return {"response": json.dumps({"type": "notes_list", "items": notlari_listele()}, ensure_ascii=False)}

    if kullanici.lower() in ["!notları sil", "!cmd:notlari_sil"]:
        if notlari_sil():
            return {"response": "__NOTES_CLEARED__"}
        return {"response": "Hiç not yok."}

    if kullanici.lower().startswith("!cmd:ara:"):
        aranan = kullanici.split("!cmd:ara:", 1)[1].strip()
        return {"response": ara_gecmiste(aranan)}

    if kullanici.lower().startswith("!cmd:luxching:"):
        soru = kullanici.split("!cmd:luxching:", 1)[1].strip()
        if not soru:
            return {"response": "Bir soru veya niyet belirt."}

        if son_luxching_zamani and (datetime.now(turkiye_tz) - son_luxching_zamani).total_seconds() < 86400:
            kalan_saat = 24 - (datetime.now(turkiye_tz) - son_luxching_zamani).total_seconds() / 3600
            return {"response": f"Luxching hızlı tüketilmez. Yaklaşık {kalan_saat:.1f} saat sonra tekrar deneyebilirsin."}

        durum, msg = luxching_kontrol()
        if not durum:
            return {"response": msg}

        heksagram = random.choice(list(heksagramlar.values()))
        son_duygu = duygusal_nabiz[-1].get("primary_emotion", "bilinmiyor") if duygusal_nabiz else "bilinmiyor"
        tema = dominant_theme() or "belirsiz"

        yorum = f"""LUXCHING

Sembol:
{heksagram['isim']}

Klasik anlam:
{heksagram['anlam']}

Son analizde özellikle {son_duygu} duygusu daha görünür olmuş gibi.
Özellikle “{tema}” teması tekrar ediyor olabilir.

Bu sembol, belki de içinde zaten var olan bir şeyi hatırlatıyor.
Bu bir fal değil.
Sadece şu anki iç gerçekliğine tutulmuş sembolik bir ayna olabilir.

Peki, bu bağlantı sende nasıl bir his uyandırdı?
"""
        son_luxching_zamani = datetime.now(turkiye_tz)
        return {"response": yorum}

    if kullanici.lower().startswith("!cmd:luxdream:"):
        ruya_metni = kullanici.split("!cmd:luxdream:", 1)[1].strip()
        if not ruya_metni:
            return {"response": "Rüyanı anlatabilirsin."}
        return {"response": luxdream_uret(ruya_metni)}

    if kullanici.lower() == "!cmd:luxta_info":
        return {"response": "Çok dinler, az konuşur."}

    # Normal sohbet
    trauma_mode = any(kelime in kullanici.lower() for kelime in [
        "intihar", "kendime zarar", "şiddet", "tecavüz", "dayanamıyorum"
    ])

    aktif_prompt = SYSTEM_PROMPT
    if trauma_mode:
        aktif_prompt += "\n\nTravma güvenlik modundasın. Çok kısa, sıcak ve güvenli konuş."

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro" if trauma_mode else "deepseek-v4-flash",
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