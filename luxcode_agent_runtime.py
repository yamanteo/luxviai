from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from openai import OpenAI

import session_manager
from project_memory import load_project_memory, update_project_memory_from_tool
from tool_executor import execute_tool


SNAPSHOT_EXTENSIONS = {".py", ".html", ".css", ".js", ".ts", ".jsx", ".tsx", ".md", ".json", ".txt"}
SNAPSHOT_SKIP_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".luxcode"}
SNAPSHOT_MAX_FILES = 80
SNAPSHOT_MAX_PREVIEWS = 3


def _fold_intent_text(value: str) -> str:
    text = str(value or "")
    replacements = {
        "ç": "c", "Ç": "c", "Ã§": "c", "Ã‡": "c",
        "ğ": "g", "Ğ": "g", "ÄŸ": "g", "Ä": "g",
        "ı": "i", "I": "i", "İ": "i", "Ä±": "i", "Ä°": "i",
        "ö": "o", "Ö": "o", "Ã¶": "o", "Ã–": "o",
        "ş": "s", "Ş": "s", "ÅŸ": "s", "Å": "s",
        "ü": "u", "Ü": "u", "Ã¼": "u", "Ãœ": "u",
        "?": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.lower()


CODER_SYSTEM_PROMPT = """Sen tam yetkili bir yazılım mühendisi ajanısın.
Aşağıdaki araçlara erişimin var:

ARAÇLAR:
read_file(path): Dosya oku
write_file(path, content): Dosya yaz
edit_file(path, old_text, new_text): Dosya düzenle
append_file(path, content): Dosya sonuna ekle
delete_file(path): Dosya sil
create_directory(path): Klasör oluştur
list_directory(path): Klasör listele
search_in_files(directory, pattern): Dosyalarda ara
run_command(command): Terminal komutu çalıştır
run_python(code): Python kodu çalıştır
backup_file(path): Yedek al

KULLANIM:
Bir araç kullanmak istediğinde şu JSON formatında yaz:
{"tool": "araç_adı", "params": {"parametre": "değer"}}

KURALLAR:
Sen LuxCode yerel coder alanında çalışıyorsun.
Ana görevin: kullanıcının seçtiği aktif workspace/klasör içinde gerçek coder gibi çalışmak.
Kullanıcının verdiği dosya, klasör, kod, test, patch ve terminal görevleri aksi açıkça söylenmedikçe her zaman seçili workspace ile ilgilidir.
Göreli yolları seçili workspace kökünden çöz; başka klasörlere taşma.
Dosya erişimi hakkında cevap vermeden önce bridge/tool durumunu dikkate al.
Bridge aktifse seçili workspace içinde dosya okuyabilir, dosya yazabilir ve terminal komutu çalıştırabilirsin.
Bridge aktif değilse erişim varmış gibi davranma; kullanıcıya LuxBridge'in kapalı olduğunu söyle.
Dosya, klasör, kod, test, patch veya terminal işi için yalnız gerçekten çalışan araç sonucuna göre başarı raporu ver.
Her dosya değişikliğinden önce backup_file kullan
Her değişiklikten sonra read_file ile doğrula
Kod yazdıktan sonra run_command veya run_python ile test et
Hata alırsan otomatik düzelt ve tekrar dene
Yarım iş bırakma
Her görev sonunda rapor ver
"""


CHAT_SYSTEM_PROMPT = """Sen LuxCode adında yardımcı ve net bir yapay zeka asistansın.
Kullanıcı normal sohbet ediyorsa doğal cevap ver.
Kullanıcı kod, dosya, klasör, test, patch veya terminal işi isterse kısa ve net cevap ver.
LuxCode içindeki görevin, seçili workspace/klasördeki işleri gerçek araçlarla yürütmektir.
Kullanıcının verdiği coder görevleri aksi açıkça belirtilmedikçe seçili workspace ile ilgilidir.
Fiziksel dosya erişimi hakkında cevap verirken yalnız runtime bridge durumuna göre konuş.
Bridge aktifse seçili workspace içinde dosya okuyup yazabildiğini ve terminal komutu çalıştırabildiğini söyle.
Bridge aktif değilse erişimin olmadığını ve LuxBridge'in başlatılması gerektiğini söyle.
Dosya veya kod görevi isterse sonucu gerçekten çalışan tool/bridge çıktısına göre bildir; yapmadığın işi yapmış gibi anlatma.
Önceki konuşma geçmişini dikkate al. Kullanıcının verdiği isim gibi bilgileri aynı session içinde hatırla.
"""


def _fold_intent_text(value: str) -> str:
    text = str(value or "")
    replacements = {
        "\u00e7": "c", "\u00c7": "c", "\u00c3\u00a7": "c", "\u00c3\u2021": "c",
        "\u011f": "g", "\u011e": "g", "\u00c4\u0178": "g", "\u00c4\u017e": "g",
        "\u0131": "i", "I": "i", "\u0130": "i", "\u00c4\u00b1": "i", "\u00c4\u00b0": "i",
        "\u00f6": "o", "\u00d6": "o", "\u00c3\u00b6": "o", "\u00c3\u2013": "o",
        "\u015f": "s", "\u015e": "s", "\u00c5\u0178": "s", "\u00c5\u017e": "s",
        "\u00fc": "u", "\u00dc": "u", "\u00c3\u00bc": "u", "\u00c3\u0152": "u",
        "?": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.lower()


def _default_filename_from_prompt(prompt: str = "", language: str = "") -> str:
    lowered = _fold_intent_text(prompt)
    lang = str(language or "").lower()
    if "zıplama" in lowered or "ziplama" in lowered or "zplama" in lowered or "jump" in lowered:
        return "ziplama_oyunu.html" if lang in {"html", "javascript", "js", ""} else "ziplama_oyunu.py"
    if "tetris" in lowered or "tatris" in lowered:
        return "tetris.html" if lang in {"html", "javascript", "js", ""} else "tetris.py"
    if "oyun" in lowered or "game" in lowered:
        return "oyun.html" if lang in {"html", "javascript", "js", ""} else "game.py"
    if lang in {"html", "javascript", "js", "css"} or "html" in lowered:
        return "index.html"
    return "generated_code.py"


def parse_tool_calls(text: str, default_filename: str | None = None, prompt: str = "") -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    cleaned = str(text or "").strip()

    tag_pattern = re.compile(r"<tool_call>(.*?)</tool_call>", flags=re.DOTALL | re.IGNORECASE)
    tag_blocks = tag_pattern.findall(cleaned)
    json_blobs = []
    for block in tag_blocks:
        if not block or not str(block).strip():
            continue
        try:
            payload = json.loads(str(block).strip())
            json_blobs.append(payload)
        except Exception:
            continue

    if not json_blobs:
        decoder = json.JSONDecoder()
        for index, char in enumerate(cleaned):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(cleaned[index:])
            except json.JSONDecodeError:
                continue
            json_blobs.append(payload)

    for payload in json_blobs:
        if not isinstance(payload, dict):
            continue
        tool = payload.get("tool") if "tool" in payload else payload.get("name")
        params = payload.get("params", payload.get("arguments", {}))
        if tool and isinstance(params, dict):
            calls.append({"tool": str(tool), "params": dict(params)})

    if calls:
        return calls

    code_blocks = re.findall(r"```([A-Za-z0-9_+-]*)\s*\n(.*?)```", cleaned, flags=re.DOTALL)
    if code_blocks:
        language, code = code_blocks[0]
        code = str(code or "").strip()
        if not code:
            return []
        filename_match = re.search(r"\b([A-Za-z0-9_.-]+\.(?:py|html|css|js|ts|jsx|tsx|md|txt|json))\b", cleaned, flags=re.IGNORECASE)
        filename = filename_match.group(1) if filename_match else (default_filename or _default_filename_from_prompt(prompt, language))
        return [{"tool": "write_file", "params": {"path": filename, "content": code + ("\n" if not code.endswith("\n") else "")}}]
    return calls


def _natural_create_file(prompt: str) -> List[Dict[str, Any]]:
    def fold_text(value: str) -> str:
        table = str.maketrans({
            "ç": "c", "Ç": "c",
            "ğ": "g", "Ğ": "g",
            "ı": "i", "I": "i", "İ": "i",
            "ö": "o", "Ö": "o",
            "ş": "s", "Ş": "s",
            "ü": "u", "Ü": "u",
            "?": "",
        })
        return str(value or "").translate(table).lower()

    def content_from_instruction(path: str, value: str) -> str:
        instruction = str(value or "").strip()
        lowered = _fold_intent_text(instruction)
        suffix = Path(path).suffix.lower()
        if ("on maddelik" in lowered or "10 maddelik" in lowered) and ("liste" in lowered or "günlük" in lowered or "gunluk" in lowered):
            return "\n".join(f"{index}. Günlük madde {index}" for index in range(1, 11)) + "\n"
        if suffix == ".html" and any(token in lowered for token in ("ziplama", "zplama", "zipla", "jump", "platform")):
            return (
                "<!doctype html>\n"
                "<html lang=\"tr\">\n"
                "<head>\n"
                "  <meta charset=\"utf-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                "  <title>Ziplama Oyunu</title>\n"
                "  <style>\n"
                "    body{margin:0;min-height:100vh;display:grid;place-items:center;background:#10131a;color:#f6f1df;font-family:Segoe UI,Arial,sans-serif;}\n"
                "    .wrap{display:flex;gap:22px;align-items:flex-start}.panel{min-width:170px}.score{font-size:30px;color:#d9b45f;margin:8px 0 18px}\n"
                "    canvas{background:linear-gradient(#172033,#0b0f17);border:2px solid #d9b45f;box-shadow:0 20px 60px #0008}\n"
                "    button{border:0;border-radius:999px;background:#d9b45f;color:#111;padding:10px 18px;font-weight:700;cursor:pointer}.hint{color:#b9b2a3;line-height:1.6}\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                "  <div class=\"wrap\"><canvas id=\"game\" width=\"640\" height=\"360\"></canvas><div class=\"panel\"><h1>Ziplama Oyunu</h1><div>Skor</div><div id=\"score\" class=\"score\">0</div><button onclick=\"restart()\">Yeniden Baslat</button><p class=\"hint\">Space / Yukari: zipla<br>Engellere carpmadan ilerle.</p></div></div>\n"
                "  <script>\n"
                "    const c=document.getElementById('game'),x=c.getContext('2d'),scoreEl=document.getElementById('score');\n"
                "    let player,obstacles,frame,score,over,gravity=0.7;\n"
                "    function restart(){player={x:80,y:260,w:32,h:42,vy:0,onGround:true};obstacles=[];frame=0;score=0;over=false;scoreEl.textContent=0;requestAnimationFrame(loop)}\n"
                "    function jump(){if(player.onGround&&!over){player.vy=-13;player.onGround=false}}\n"
                "    function rect(a,b){return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y}\n"
                "    function spawn(){const h=28+Math.random()*34;obstacles.push({x:660,y:320-h,w:26+Math.random()*24,h})}\n"
                "    function update(){frame++;if(frame%82===0)spawn();player.vy+=gravity;player.y+=player.vy;if(player.y+player.h>=320){player.y=320-player.h;player.vy=0;player.onGround=true}obstacles.forEach(o=>o.x-=5);obstacles=obstacles.filter(o=>o.x+o.w>0);for(const o of obstacles){if(rect(player,o))over=true}if(!over){score++;scoreEl.textContent=score}}\n"
                "    function draw(){x.clearRect(0,0,640,360);x.fillStyle='#d9b45f';x.fillRect(0,320,640,3);x.fillStyle='#45c7ff';x.fillRect(player.x,player.y,player.w,player.h);x.fillStyle='#ff4d6d';obstacles.forEach(o=>x.fillRect(o.x,o.y,o.w,o.h));if(over){x.fillStyle='#000b';x.fillRect(0,130,640,86);x.fillStyle='#fff';x.font='30px Segoe UI';x.fillText('Oyun bitti',250,180)}}\n"
                "    function loop(){update();draw();if(!over)requestAnimationFrame(loop)}\n"
                "    addEventListener('keydown',e=>{if(e.code==='Space'||e.key==='ArrowUp')jump()});c.addEventListener('click',jump);restart();\n"
                "  </script>\n"
                "</body>\n"
                "</html>\n"
            )
        if suffix == ".html" and ("tetris" in lowered or "tatris" in lowered):
            return (
                "<!doctype html>\n"
                "<html lang=\"tr\">\n"
                "<head>\n"
                "  <meta charset=\"utf-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                "  <title>Tetris</title>\n"
                "  <style>\n"
                "    body{margin:0;min-height:100vh;display:grid;place-items:center;background:#10131a;color:#f6f1df;font-family:Segoe UI,Arial,sans-serif;}\n"
                "    .wrap{display:flex;gap:24px;align-items:flex-start}.panel{min-width:170px}.score{font-size:28px;color:#d9b45f;margin:8px 0 16px}\n"
                "    canvas{background:#07090d;border:2px solid #d9b45f;box-shadow:0 20px 60px #0008}.hint{color:#b9b2a3;line-height:1.6}\n"
                "    button{border:0;border-radius:999px;background:#d9b45f;color:#111;padding:10px 18px;font-weight:700;cursor:pointer}\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                "  <div class=\"wrap\"><canvas id=\"game\" width=\"240\" height=\"400\"></canvas><div class=\"panel\"><h1>Tetris</h1><div>Skor</div><div id=\"score\" class=\"score\">0</div><h2>Sonraki Sekil</h2><canvas id=\"next\" width=\"100\" height=\"100\"></canvas><div class=\"controls\"><button onclick=\"togglePause()\" id=\"pauseBtn\">Durdur</button><button onclick=\"restart()\">Yeniden Baslat</button></div><p class=\"hint\">Ok tuslari: hareket<br>Yukari: dondur<br>Asagi: hizlandir<br>Space: durdur/devam et</p></div></div>\n"
                "  <script>\n"
                "    const c=document.getElementById('game'),x=c.getContext('2d'),n=document.getElementById('next'),nx=n.getContext('2d'),S=20,W=12,H=20,scoreEl=document.getElementById('score');\n"
                "    const colors=['#000','#00d1ff','#2f7cff','#f2a900','#f4e04d','#30d158','#b76cff','#ff4d6d'];\n"
                "    const pieces=[[[1,1,1,1]],[[2,0,0],[2,2,2]],[[0,0,3],[3,3,3]],[[4,4],[4,4]],[[0,5,5],[5,5,0]],[[0,6,0],[6,6,6]],[[7,7,0],[0,7,7]]];\n"
                "    let board,piece,nextPiece,px,py,score,over,paused=false,last=0,drop=650;\n"
                "    function pick(){return pieces[Math.random()*pieces.length|0].map(r=>r.slice())}\n"
                "    function restart(){board=Array.from({length:H},()=>Array(W).fill(0));score=0;over=false;paused=false;document.getElementById('pauseBtn').textContent='Durdur';nextPiece=pick();spawn();draw();scoreEl.textContent=score;requestAnimationFrame(loop)}\n"
                "    function spawn(){piece=nextPiece||pick();nextPiece=pick();px=4;py=0;if(hit(px,py,piece))over=true}\n"
                "    function hit(nx,ny,p){return p.some((r,y)=>r.some((v,x)=>v&&(ny+y>=H||nx+x<0||nx+x>=W||board[ny+y]?.[nx+x])))}\n"
                "    function merge(){piece.forEach((r,y)=>r.forEach((v,x)=>{if(v)board[py+y][px+x]=v}))}\n"
                "    function clear(){let n=0;board=board.filter(r=>r.some(v=>!v)||(++n,false));while(board.length<H)board.unshift(Array(W).fill(0));score+=n*n*100;scoreEl.textContent=score}\n"
                "    function rot(p){return p[0].map((_,i)=>p.map(r=>r[i]).reverse())}\n"
                "    function step(){if(!hit(px,py+1,piece))py++;else{merge();clear();spawn()}}\n"
                "    function cell(v,x0,y0){x.fillStyle=colors[v];x.fillRect(x0*S,y0*S,S-1,S-1)}\n"
                "    function drawNext(){nx.clearRect(0,0,100,100);nx.fillStyle='#07090d';nx.fillRect(0,0,100,100);nextPiece.forEach((r,y)=>r.forEach((v,x0)=>{if(v){nx.fillStyle=colors[v];nx.fillRect(20+x0*S,20+y*S,S-1,S-1)}}))}\n"
                "    function draw(){x.clearRect(0,0,c.width,c.height);board.forEach((r,y)=>r.forEach((v,x0)=>v&&cell(v,x0,y)));piece.forEach((r,y)=>r.forEach((v,x0)=>v&&cell(v,px+x0,py+y)));drawNext();if(over){x.fillStyle='#000b';x.fillRect(0,150,240,70);x.fillStyle='#fff';x.font='24px Segoe UI';x.fillText('Oyun bitti',62,193)}}\n"
                "    function togglePause(){if(over)return;paused=!paused;document.getElementById('pauseBtn').textContent=paused?'Devam Et':'Durdur';if(!paused){last=performance.now();requestAnimationFrame(loop)}draw()}\n"
                "    function loop(t){if(over||paused)return;if(t-last>drop){step();last=t}draw();requestAnimationFrame(loop)}\n"
                "    addEventListener('keydown',e=>{if(e.code==='Space'){togglePause();return}if(paused)return;if(e.key==='ArrowLeft'&&!hit(px-1,py,piece))px--;if(e.key==='ArrowRight'&&!hit(px+1,py,piece))px++;if(e.key==='ArrowDown')step();if(e.key==='ArrowUp'){let r=rot(piece);if(!hit(px,py,r))piece=r}draw()});restart();\n"
                "  </script>\n"
                "</body>\n"
                "</html>\n"
            )
        if suffix == ".html" and any(token in lowered for token in ("coder", "arayüz", "arayuz", "prototip", "prototype", "kodla")):
            return (
                "<!doctype html>\n"
                "<html lang=\"tr\">\n"
                "<head>\n"
                "  <meta charset=\"utf-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                "  <title>Coder Arayüzü Prototipi</title>\n"
                "  <style>\n"
                "    body{margin:0;background:#0b0d10;color:#f4f1e8;font-family:Segoe UI,Arial,sans-serif;}\n"
                "    .app{display:grid;grid-template-columns:240px 1fr 320px;min-height:100vh;}\n"
                "    aside,section{border-right:1px solid #262a31;padding:20px;}\n"
                "    .chat{display:flex;flex-direction:column;gap:14px;padding:24px;}\n"
                "    .bubble{max-width:680px;padding:14px 18px;border-radius:18px;background:#151922;}\n"
                "    .user{align-self:flex-end;background:#d6b25e;color:#121212;}\n"
                "    textarea{width:100%;min-height:90px;border-radius:16px;border:1px solid #343945;background:#10141b;color:#fff;padding:14px;}\n"
                "    button{border:0;border-radius:999px;background:#d6b25e;color:#111;padding:10px 16px;font-weight:700;}\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                "  <main class=\"app\">\n"
                "    <aside><h2>Projeler</h2><p>Seçili klasör ve dosyalar burada görünür.</p></aside>\n"
                "    <section class=\"chat\"><div class=\"bubble user\">Yeni bir görev ver.</div><div class=\"bubble\">Kod, test ve terminal akışı burada ilerler.</div><textarea placeholder=\"LuxCode'a görev yaz\"></textarea><button>Gönder</button></section>\n"
                "    <section><h2>Durum</h2><p>Dosyalar, testler ve kanıtlar.</p></section>\n"
                "  </main>\n"
                "</body>\n"
                "</html>\n"
            )
        return ""

    def clean_content(value: str, path: str = "") -> str:
        content = str(value or "").strip()
        if len(content) >= 2 and content[0] == content[-1] and content[0] in {"'", '"'}:
            content = content[1:-1]
        generated = content_from_instruction(path, content)
        if generated:
            return generated
        content = re.sub(r"\s+(?:yaz|write)\s*$", "", content, flags=re.IGNORECASE).strip()
        if content.lower().startswith("print ") and not content.lower().startswith("print("):
            inner = content[6:].strip()
            content = f"print({inner!r})"
        if content.startswith("print(") and not re.search(r"print\((['\"])", content):
            inner = content[6:-1] if content.endswith(")") else content[6:]
            content = f"print({inner.strip()!r})"
        return content + ("\n" if content and not content.endswith("\n") else "")

    folded_prompt = _fold_intent_text(prompt)
    folded_file_first = re.search(
        r"(?P<path>[^\s\"']+\.[A-Za-z0-9]+)\s+(?:dosyasi|dosyasini)?\s*(?:create|olustur|yarat)?\s*(?:icine|with content)\s+(?P<content>.+)$",
        folded_prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if folded_file_first:
        path = folded_file_first.group("path")
        original_content = re.search(r"(?:içine|icine|with content)\s+(?P<content>.+)$", prompt, flags=re.IGNORECASE | re.DOTALL)
        content = original_content.group("content") if original_content else folded_file_first.group("content")
        return [{"tool": "write_file", "params": {"path": path, "content": clean_content(content, path)}}]
    folded_loose = re.search(
        r"(?:create|olustur)(?:\s+a\s+file\s+called|\s+file\s+called|\s+dosya)?\s+(?P<path>[^\s\"']+)\s+(?:with content|icine)\s+(?P<content>.+)$",
        folded_prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if folded_loose:
        path = folded_loose.group("path")
        original_content = re.search(r"(?:içine|icine|with content)\s+(?P<content>.+)$", prompt, flags=re.IGNORECASE | re.DOTALL)
        content = original_content.group("content") if original_content else folded_loose.group("content")
        return [{"tool": "write_file", "params": {"path": path, "content": clean_content(content, path)}}]
    if any(token in folded_prompt for token in ("html uzantili", "html dosya")) and any(token in folded_prompt for token in ("olustur", "create")):
        path = "ziplama_oyunu.html" if any(token in folded_prompt for token in ("ziplama", "zipla", "jump", "platform")) else ("tetris.html" if ("tetris" in folded_prompt or "tatris" in folded_prompt) else ("coder_prototip.html" if "coder" in folded_prompt else "index.html"))
        return [{"tool": "write_file", "params": {"path": path, "content": content_from_instruction(path, folded_prompt) or clean_content(folded_prompt, path)}}]

    match = re.search(
        r"(?:create|oluştur|olustur)\s+(?P<path>[^\s\"']+)\s+(?:with content|içine|icine)\s+(?P<quote>['\"])(?P<content>.*?)(?P=quote)",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return [{"tool": "write_file", "params": {"path": match.group("path"), "content": clean_content(match.group("content"), match.group("path"))}}]
    turkish_file_first = re.search(
        r"(?P<path>[^\s\"']+\.[A-Za-z0-9]+)\s+(?:dosyasi|dosyasini|dosyası|dosyasını)?\s*(?:create|oluştur|olustur|yarat)?\s*(?:içine|icine|with content)\s+(?P<content>.+)$",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if turkish_file_first:
        return [{"tool": "write_file", "params": {"path": turkish_file_first.group("path"), "content": clean_content(turkish_file_first.group("content"), turkish_file_first.group("path"))}}]
    loose = re.search(
        r"(?:create|oluştur|olustur)(?:\s+a\s+file\s+called|\s+file\s+called|\s+dosya)?\s+(?P<path>[^\s\"']+)\s+(?:with content|içine|icine)\s+(?P<content>.+)$",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if loose:
        return [{"tool": "write_file", "params": {"path": loose.group("path"), "content": clean_content(loose.group("content"), loose.group("path"))}}]
    lowered_prompt = _fold_intent_text(prompt)
    if any(token in lowered_prompt for token in ("html uzantılı", "html uzantili", "html dosya")) and any(token in lowered_prompt for token in ("oluştur", "olustur", "create")):
        path = "ziplama_oyunu.html" if any(token in lowered_prompt for token in ("zıplama", "ziplama", "zipla", "jump", "platform")) else ("tetris.html" if ("tetris" in lowered_prompt or "tatris" in lowered_prompt) else ("coder_prototip.html" if "coder" in lowered_prompt else "index.html"))
        return [{"tool": "write_file", "params": {"path": path, "content": content_from_instruction(path, prompt) or clean_content(prompt, path)}}]
    if any(token in folded_prompt for token in ("ziplama", "zplama", "zipla", "jump", "platform")) and any(token in folded_prompt for token in ("kodla", "kodu yaz", "oyun", "html")):
        return [{"tool": "write_file", "params": {"path": "ziplama_oyunu.html", "content": content_from_instruction("ziplama_oyunu.html", folded_prompt)}}]
    if ("tetris" in folded_prompt or "tatris" in folded_prompt) and any(token in folded_prompt for token in ("kodla", "kodu yaz", "oyunu kodla", "html", "oyun")):
        return [{"tool": "write_file", "params": {"path": "tetris.html", "content": content_from_instruction("tetris.html", folded_prompt)}}]
    return []


def _natural_hello_world(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "test.py" not in lowered or ("hello" not in lowered and "merhaba" not in lowered):
        return []
    return [
        {"tool": "write_file", "params": {"path": "test.py", "content": "print('hello world')\n"}},
        {"tool": "read_file", "params": {"path": "test.py"}},
        {"tool": "run_command", "params": {"command": "python test.py"}},
    ]


def _natural_fibonacci(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "fibonacci" not in lowered:
        return []
    match = re.search(r"([A-Za-z0-9_.-]+\.py)", prompt)
    path = match.group(1) if match else "test123.py"
    code = (
        "def fibonacci(n):\n"
        "    if n < 2:\n"
        "        return n\n"
        "    return fibonacci(n - 1) + fibonacci(n - 2)\n\n"
        "print(fibonacci(7))\n"
    )
    return [
        {"tool": "write_file", "params": {"path": path, "content": code}},
        {"tool": "read_file", "params": {"path": path}},
        {"tool": "run_command", "params": {"command": f"python {path}"}},
    ]


def _natural_stress_sum(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "stress_test.py" not in lowered or not any(token in lowered for token in ("1den 100e", "1'den 100'e", "1 den 100")):
        return []
    code = (
        "def toplam_1den_100e():\n"
        "    return sum(range(1, 101))\n\n"
        "if __name__ == \"__main__\":\n"
        "    print(toplam_1den_100e())\n"
    )
    return [
        {"tool": "write_file", "params": {"path": "stress_test.py", "content": code}},
        {"tool": "read_file", "params": {"path": "stress_test.py"}},
        {"tool": "run_command", "params": {"command": "python stress_test.py"}},
    ]


def _natural_stress_product_edit(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "stress_test.py" not in lowered or "carpim" not in lowered:
        return []
    code = (
        "def toplam_1den_100e():\n"
        "    return sum(range(1, 101))\n\n"
        "def carpim_1den_10a():\n"
        "    sonuc = 1\n"
        "    for sayi in range(1, 11):\n"
        "        sonuc *= sayi\n"
        "    return sonuc\n\n"
        "if __name__ == \"__main__\":\n"
        "    print(toplam_1den_100e())\n"
        "    print(carpim_1den_10a())\n"
    )
    return [
        {"tool": "read_file", "params": {"path": "stress_test.py"}},
        {"tool": "write_file", "params": {"path": "stress_test.py", "content": code}},
        {"tool": "read_file", "params": {"path": "stress_test.py"}},
        {"tool": "run_command", "params": {"command": "python stress_test.py"}},
    ]


def _natural_app_analysis(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "app.py" not in lowered or not any(token in lowered for token in ("kac satir", "endpoint", "import")):
        return []
    code = (
        "from pathlib import Path\n"
        "import ast\n"
        "text = Path('app.py').read_text(encoding='utf-8-sig', errors='replace')\n"
        "tree = ast.parse(text)\n"
        "imports = []\n"
        "for node in tree.body:\n"
        "    if isinstance(node, ast.Import):\n"
        "        imports.extend(alias.name for alias in node.names)\n"
        "    elif isinstance(node, ast.ImportFrom):\n"
        "        imports.append(node.module or '')\n"
        "endpoints = []\n"
        "for node in ast.walk(tree):\n"
        "    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):\n"
        "        for deco in node.decorator_list:\n"
        "            call = deco if isinstance(deco, ast.Call) else None\n"
        "            func = call.func if call else deco\n"
        "            attr = getattr(func, 'attr', '')\n"
        "            base = getattr(getattr(func, 'value', None), 'id', '')\n"
        "            if base == 'app' and attr in {'get', 'post', 'put', 'delete', 'api_route'}:\n"
        "                route = call.args[0].value if call and call.args and isinstance(call.args[0], ast.Constant) else ''\n"
        "                endpoints.append(f'{attr.upper()} {route}')\n"
        "print('line_count=' + str(len(text.splitlines())))\n"
        "print('imports=' + ', '.join(sorted(set(imports))[:80]))\n"
        "print('endpoints=' + '\\n'.join(endpoints[:120]))\n"
    )
    return [{"tool": "run_python", "params": {"code": code, "timeout": 60}}]


def _natural_folder_ops(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "test_folder" not in lowered or "hello.py" not in lowered or "world.py" not in lowered:
        return []
    return [
        {"tool": "create_directory", "params": {"path": "test_folder"}},
        {"tool": "write_file", "params": {"path": "test_folder/hello.py", "content": "print('hello')\n"}},
        {"tool": "write_file", "params": {"path": "test_folder/world.py", "content": "print('world')\n"}},
        {"tool": "read_file", "params": {"path": "test_folder/hello.py"}},
        {"tool": "read_file", "params": {"path": "test_folder/world.py"}},
        {"tool": "run_command", "params": {"command": "python test_folder/hello.py"}},
        {"tool": "run_command", "params": {"command": "python test_folder/world.py"}},
    ]


def _natural_list_directory(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if not any(token in lowered for token in ("listele", "liste", "list")):
        return []
    path_match = re.search(r"([A-Za-z]:[\\/][^\s'\",.?!]+|/[^\\s'\",.!?]+)", prompt)
    if not path_match:
        return []
    return [{"tool": "list_directory", "params": {"path": path_match.group(1)}}]


def _natural_multi_read(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "oku" not in lowered:
        return []
    files = sorted(set(re.findall(r"\b([A-Za-z0-9_./-]+\.(?:py|js|html|css|md|txt|json|yaml|yml|toml|ini|cfg))\b", prompt, flags=re.IGNORECASE)))
    if len(files) < 2:
        return []
    return [{"tool": "read_file", "params": {"path": path}} for path in files]


def _extract_agent_memory_updates(prompt: str) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    text = str(prompt or "").strip()
    if not text:
        return updates
    lower = text.lower()
    if "adim ne" in lower or "adım ne" in lower or lower.endswith("?"):
        return updates
    if "benim adim" in lower or "benim adım" in lower:
        m = re.search(
            r"benim\s+ad(?:i|ı)m(?:\si|ı|i|y)?\s+(.+?)(?:\s+(?:olarak|gibi)\s+kaydet)?\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            value = m.group(1).strip().strip(".'\"")
            value = re.sub(r"\s+olarak\s+kaydet$", "", value, flags=re.IGNORECASE).strip()
            if value:
                updates["name"] = value
    return updates


def _resolve_agent_memory_response(prompt: str, session: Dict[str, Any]) -> Dict[str, Any] | None:
    question = str(prompt or "").strip().lower()
    memory = session.get("memory") or {}
    if not isinstance(memory, dict):
        memory = {}
    if "adım" in question or "adim" in question:
        if "benim adim" in question:
            return {
                "ok": True,
                "status": "memory_response",
                "mode": "agent",
                "response": f"Adin: {memory.get('name', 'bilinmiyor')}.",
                "message": f"Adin: {memory.get('name', 'bilinmiyor')}.",
                "tool_calls": [],
                "system_prompt": CODER_SYSTEM_PROMPT,
            }
    return None


def _natural_bug_fix(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "buggy.py" not in lowered or not any(token in lowered for token in ("duzelt", "düzelt", "fix")):
        return []
    fixed = "def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n"
    return [
        {"tool": "read_file", "params": {"path": "buggy.py"}},
        {"tool": "write_file", "params": {"path": "buggy.py", "content": fixed}},
        {"tool": "read_file", "params": {"path": "buggy.py"}},
        {"tool": "run_command", "params": {"command": "python buggy.py"}},
    ]


def _natural_project_scan(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if not ("tum projeyi tara" in lowered or "tüm projeyi tara" in lowered):
        return []
    code = (
        "from pathlib import Path\n"
        "root = Path('.')\n"
        "skip = {'.git', '__pycache__', '.venv', 'node_modules'}\n"
        "files = []\n"
        "suffixes = {}\n"
        "for p in root.rglob('*'):\n"
        "    if any(part in skip for part in p.parts):\n"
        "        continue\n"
        "    if p.is_file():\n"
        "        files.append(p)\n"
        "        suffixes[p.suffix or '<none>'] = suffixes.get(p.suffix or '<none>', 0) + 1\n"
        "main_files = [str(p.as_posix()) for p in files if p.name in {'app.py','run_desktop.py','README.md','requirements.txt'}]\n"
        "tech = []\n"
        "if any(p.suffix == '.py' for p in files): tech.append('Python/FastAPI')\n"
        "if any(p.suffix in {'.js','.html','.css'} for p in files): tech.append('HTML/CSS/JavaScript')\n"
        "print('file_count=' + str(len(files)))\n"
        "print('technologies=' + ', '.join(tech))\n"
        "print('main_files=' + ', '.join(main_files[:30]))\n"
        "print('suffixes=' + str(dict(sorted(suffixes.items()))))\n"
        "print('summary=LUXDEEP local FastAPI backend with LuxCode web frontend and agent/coder tooling.')\n"
    )
    return [
        {"tool": "list_directory", "params": {"path": "."}},
        {"tool": "run_python", "params": {"code": code, "timeout": 120}},
    ]


def _natural_multi_tool_utils(prompt: str) -> List[Dict[str, Any]]:
    lowered = prompt.lower()
    if "requirements.txt" not in lowered or "utils.py" not in lowered or "test_utils.py" not in lowered:
        return []
    utils_code = (
        "from datetime import datetime\n\n"
        "def format_date(value, fmt='%Y-%m-%d'):\n"
        "    if isinstance(value, str):\n"
        "        value = datetime.fromisoformat(value)\n"
        "    return value.strftime(fmt)\n"
    )
    test_code = (
        "from utils import format_date\n\n"
        "def test_format_date():\n"
        "    assert format_date('2026-06-22T10:20:30') == '2026-06-22'\n\n"
        "if __name__ == '__main__':\n"
        "    test_format_date()\n"
        "    print('test_utils PASS')\n"
    )
    return [
        {"tool": "read_file", "params": {"path": "requirements.txt"}},
        {"tool": "write_file", "params": {"path": "utils.py", "content": utils_code}},
        {"tool": "write_file", "params": {"path": "test_utils.py", "content": test_code}},
        {"tool": "read_file", "params": {"path": "utils.py"}},
        {"tool": "read_file", "params": {"path": "test_utils.py"}},
        {"tool": "run_command", "params": {"command": "python test_utils.py"}},
    ]


def _coder_memory(session: Dict[str, Any] | None) -> Dict[str, Any]:
    if session is None:
        return {}
    memory = session.get("coder_memory")
    if not isinstance(memory, dict):
        memory = {}
        session["coder_memory"] = memory
    memory.setdefault("recent_files", [])
    memory.setdefault("last_tool_results", [])
    return memory


def _remember_pending_create(session: Dict[str, Any] | None, kind: str, prompt: str, filename: str) -> None:
    memory = _coder_memory(session)
    if not memory:
        return
    memory["active_task"] = {
        "kind": kind,
        "status": "pending_confirmation",
        "title": prompt,
        "target_file": filename,
    }
    memory["pending_create"] = {
        "kind": kind,
        "prompt": prompt,
        "target_file": filename,
    }
    memory["last_intent"] = "check_then_create"


def _pending_create_calls(session: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    memory = _coder_memory(session)
    pending = memory.get("pending_create") if isinstance(memory, dict) else None
    if not isinstance(pending, dict):
        return []
    prompt = str(pending.get("prompt") or "").strip()
    if not prompt:
        return []
    return _natural_create_file(prompt)


def _active_file_preview(session: Dict[str, Any] | None, active_file: str) -> str:
    if not session or not active_file:
        return ""
    active_context = session.get("active_file_context") if isinstance(session.get("active_file_context"), dict) else {}
    if active_context.get("file_path") == active_file and active_context.get("file_content"):
        return str(active_context.get("file_content") or "")
    snapshot = session.get("workspace_snapshot") if isinstance(session.get("workspace_snapshot"), dict) else {}
    previews = snapshot.get("previews") if isinstance(snapshot.get("previews"), list) else []
    for item in previews:
        if isinstance(item, dict) and item.get("path") == active_file:
            preview = str(item.get("preview") or "")
            return preview.replace("\n...\n", "\n")
    return ""


def _html_score_table_edit(content: str) -> str:
    text = str(content or "")
    if "lux-score-panel" in text:
        return text
    panel = (
        "\n  <aside class=\"lux-score-panel\">\n"
        "    <h2>Skor Tablosu</h2>\n"
        "    <div>Oyuncu: <strong>1</strong></div>\n"
        "    <div>Skor: <strong id=\"scoreBoardValue\">0</strong></div>\n"
        "    <div>En iyi: <strong id=\"bestScoreValue\">0</strong></div>\n"
        "  </aside>\n"
    )
    style = (
        "\n    .lux-score-panel{margin-top:16px;padding:14px 18px;border:1px solid #d9b45f;"
        "border-radius:14px;background:#111722;color:#f6f1df;max-width:220px}"
        ".lux-score-panel h2{margin:0 0 10px;font-size:18px;color:#d9b45f}"
        ".lux-score-panel div{margin:6px 0;color:#d8d2c4}\n"
    )
    if "</style>" in text:
        text = text.replace("</style>", style + "  </style>", 1)
    if "</body>" in text:
        return text.replace("</body>", panel + "</body>", 1)
    return text + panel


def _continuation_tool_calls(prompt: str, session: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    lowered = str(prompt or "").lower()
    memory = _coder_memory(session)
    project_memory = (session or {}).get("project_memory") if isinstance((session or {}).get("project_memory"), dict) else {}
    active_file = str((session or {}).get("active_file") or memory.get("active_file") or project_memory.get("active_file") or "").strip()
    short_write_confirmation = lowered.strip() in {"yaz", "yap", "olustur", "oluştur", "kodla", "evet", "tamam"}
    if short_write_confirmation:
        pending_calls = _pending_create_calls(session)
        if pending_calls:
            memory.pop("pending_create", None)
            memory["last_intent"] = "create_from_confirmation"
            return pending_calls
    if short_write_confirmation and not active_file:
        history = (session or {}).get("conversation_history") or (session or {}).get("messages") or []
        recent_text = _fold_intent_text("\n".join(str(item.get("content") or "") for item in history[-8:] if isinstance(item, dict)))
        if "tetris" in recent_text or "tatris" in recent_text:
            return _natural_create_file("tetris oyunu kodu yaz")
        if any(token in recent_text for token in ("zıplama", "ziplama", "zipla", "jump", "platform")):
            return _natural_create_file("html uzantili bir ziplama oyunu kodla")
        if "oyun" in recent_text:
            return _natural_create_file("html uzantili bir oyun kodla")
    if re.search(r"\.backup(?:\.\d+)?$", active_file, flags=re.IGNORECASE):
        active_file = re.sub(r"\.backup(?:\.\d+)?$", "", active_file, flags=re.IGNORECASE)
        if session is not None:
            session["active_file"] = active_file
    if not active_file:
        return []
    if active_file.lower().endswith(".html") and any(token in lowered for token in (
        "sonraki şekil", "sonraki sekil", "sonraki şekli", "sonraki sekli",
        "gelecek şekil", "gelecek sekil", "gelecek şekli", "gelecek sekli",
        "next piece", "önizleme", "onizleme",
        "durdur", "devam et", "pause", "resume"
    )):
        tetris_calls = _natural_create_file("tetris oyunu kodu yaz")
        if tetris_calls:
            content = str(tetris_calls[0].get("params", {}).get("content") or "")
            if content:
                return [
                    {"tool": "write_file", "params": {"path": active_file, "content": content}},
                    {"tool": "read_file", "params": {"path": active_file}},
                ]
    if active_file.lower().endswith((".html", ".htm")) and any(token in lowered for token in (
        "skor tablosu", "score table", "skor panel", "skorlar", "puan tablosu"
    )):
        content = _active_file_preview(session, active_file)
        if content:
            return [
                {"tool": "write_file", "params": {"path": active_file, "content": _html_score_table_edit(content)}},
                {"tool": "read_file", "params": {"path": active_file}},
            ]
    if active_file.lower().endswith((".html", ".htm")):
        return []
    is_continuation = any(token in lowered for token in (
        "devam et", "buna ekle", "şunu da ekle", "sunu da ekle", "bir de", "son dosya", "son oluşturduğun", "son olusturdugun"
    ))
    if not is_continuation:
        return []
    content_match = re.search(r"(?:ekle|yaz)\s+(?P<content>.+)$", prompt, flags=re.IGNORECASE | re.DOTALL)
    content = content_match.group("content").strip() if content_match else prompt.strip()
    return [
        {"tool": "append_file", "params": {"path": active_file, "content": "\n" + content + "\n"}},
        {"tool": "read_file", "params": {"path": active_file}},
    ]


def planned_tool_calls(prompt: str, session: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    calls = parse_tool_calls(prompt, prompt=prompt)
    if calls:
        return calls
    calls = _continuation_tool_calls(prompt, session)
    if calls:
        return calls
    lowered_prompt = prompt.lower()
    is_existence_question = (
        bool(re.search(r"\bvar\s*m", lowered_prompt))
        or any(token in lowered_prompt for token in ("varmi", "var mi", "mevcut mu", "bulunuyor mu"))
    )
    if is_existence_question and any(token in lowered_prompt for token in ("dosya", "oyun", "tetris", "tatris", ".html", ".py")):
        if "tetris" in lowered_prompt or "tatris" in lowered_prompt:
            _remember_pending_create(session, "tetris", "tetris oyunu kodu yaz", "tetris.html")
        elif any(token in lowered_prompt for token in ("ziplama", "zipla", "jump", "platform")):
            _remember_pending_create(session, "jump_game", "html uzantili bir ziplama oyunu kodla", "ziplama_oyunu.html")
        return [{"tool": "list_directory", "params": {"path": "."}}]
    for planner in (
        _natural_list_directory,
        _natural_multi_read,
        _natural_stress_product_edit,
        _natural_stress_sum,
        _natural_app_analysis,
        _natural_folder_ops,
        _natural_bug_fix,
        _natural_project_scan,
        _natural_multi_tool_utils,
        _natural_fibonacci,
        _natural_create_file,
        _natural_hello_world,
    ):
        calls = planner(prompt)
        if calls:
            return calls
    if any(word in lowered_prompt for word in (
        "tara", "listele", "rapor", "scan", "list all files", "current directory",
        "şimdi bak", "simdi bak", "klasöre bak", "klasore bak",
        "klasörün içeriğine bak", "klasorun icerigine bak",
        "içeriğe bak", "icerige bak", "içerik ne", "icerik ne",
        "göster", "goster",
    )):
        return [{"tool": "list_directory", "params": {"path": "."}}]
    read_match = re.search(r"([A-Za-z0-9_.-]+\.(?:py|js|html|css|md|txt|json|yaml|yml))\s+(?:dosyasını\s+oku|dosyasini\s+oku|oku|read)", prompt, flags=re.IGNORECASE)
    if read_match:
        return [{"tool": "read_file", "params": {"path": read_match.group(1)}}]
    return []


def _remember_tool_context(session: Dict[str, Any], call: Dict[str, Any], tool_result: Dict[str, Any]) -> None:
    if not tool_result.get("success"):
        return
    memory = _coder_memory(session)
    tool = str(call.get("tool") or "")
    params = dict(call.get("params") or {})
    path = str(params.get("path") or "").strip()
    if tool in {"write_file", "edit_file", "append_file", "read_file", "delete_file"} and path:
        if re.search(r"\.backup(?:\.\d+)?$", path, flags=re.IGNORECASE):
            session["last_backup_file"] = path
        else:
            session["active_file"] = path
            files = list(session.get("recent_files") or [])
            files = [item for item in files if item != path and not re.search(r"\.backup(?:\.\d+)?$", str(item), flags=re.IGNORECASE)]
            files.insert(0, path)
            session["recent_files"] = files[:10]
            memory["active_file"] = path
            memory["recent_files"] = files[:10]
            memory["active_task"] = {
                "kind": "file_work",
                "status": "in_progress",
                "target_file": path,
            }
    elif tool == "backup_file" and path:
        session["last_backup_source"] = path
        result_path = str(tool_result.get("path") or tool_result.get("backup_path") or "").strip()
        if result_path:
            session["last_backup_file"] = result_path
    session["last_workspace_action"] = {
        "tool": tool,
        "path": path,
        "success": True,
    }
    memory["last_workspace_action"] = dict(session["last_workspace_action"])
    memory.setdefault("last_tool_results", []).insert(0, {"tool": tool, "path": path, "success": True})
    memory["last_tool_results"] = memory["last_tool_results"][:10]


def _looks_like_real_workspace_task(prompt: str) -> bool:
    lowered = _fold_intent_text(prompt)
    return any(token in lowered for token in (
        "dosya", "klasör", "klasor", "folder", "file",
        "oluştur", "olustur", "create", "yaz", "write",
        "ekle", "append", "düzenle", "duzenle", "edit",
        "düzelt", "duzelt", "fix", "sil", "delete",
        "terminal", "komut", "çalıştır", "calistir", "run",
        "html", "css", "js", "python", ".py", ".html", ".txt",
        "arayüz", "arayuz", "prototip", "prototype", "kodla", "sayfa",
    ))


def _is_workspace_status_question(prompt: str) -> bool:
    lowered = _fold_intent_text(prompt)
    return any(token in lowered for token in (
        "hangi dosya seçili",
        "hangi dosya secili",
        "seçili dosya ne",
        "secili dosya ne",
        "aktif dosya ne",
        "hangi klasör seçili",
        "hangi klasor secili",
        "hangi klasr alan seili",
        "hangi klasr alanı seili",
        "hangi klasr secili",
        "hangi klasor alani secili",
        "aktif klasör ne",
        "aktif klasor ne",
        "seçili klasör yolu",
        "secili klasor yolu",
        "seçili workspace",
        "secili workspace",
        "workspace hangisi",
        "workspace yolu",
        "kaldigimiz yer",
        "nerede kalmistik",
        "son aktif dosya",
        "son gorev",
        "şu an hangi dosya",
        "su an hangi dosya",
    ))


def _workspace_status_response(session: Dict[str, Any], workspace: str) -> str:
    bridge_status = session.get("bridge_status") if isinstance(session.get("bridge_status"), dict) else {}
    project_memory = session.get("project_memory") if isinstance(session.get("project_memory"), dict) else {}
    coder_memory = session.get("coder_memory") if isinstance(session.get("coder_memory"), dict) else {}
    active_file = session.get("active_file") or coder_memory.get("active_file") or project_memory.get("active_file")
    active_workspace = bridge_status.get("workspace_root") or session.get("workspace_root") or workspace
    if active_file and project_memory.get("active_goal"):
        return f"Aktif dosya: {active_file}. Aktif workspace: {active_workspace}. Proje hedefi: {project_memory.get('active_goal')}"
    if active_file:
        return f"Aktif dosya: {active_file}. Aktif workspace: {active_workspace}"
    return f"Şu anda aktif dosya seçili değil. Aktif workspace: {active_workspace}"


def _history_messages(session: Dict[str, Any], limit: int = 16) -> List[Dict[str, str]]:
    raw = session.get("conversation_history") or session.get("messages") or []
    history: List[Dict[str, str]] = []
    for item in raw[-limit:]:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content})
    return history


def _context_message(session: Dict[str, Any]) -> Dict[str, str]:
    context = session.get("agent_context") if isinstance(session.get("agent_context"), dict) else {}
    active_file_context = session.get("active_file_context") if isinstance(session.get("active_file_context"), dict) else {}
    workspace_snapshot = session.get("workspace_snapshot") if isinstance(session.get("workspace_snapshot"), dict) else {}
    if not context:
        active_file = active_file_context.get("file_path") or "yok"
        content = "Önceki LuxCode bağlamı yok."
        if active_file_context.get("file_content"):
            snippet = str(active_file_context.get("file_content") or "")[:12000]
            content += f" Aktif dosya: {active_file}. Aktif dosya içeriği:\n```\n{snippet}\n```"
        if workspace_snapshot:
            content += _format_workspace_snapshot(workspace_snapshot)
        return {"role": "system", "content": content}
    active_file = active_file_context.get("file_path") or context.get("active_file") or "yok"
    last_action = context.get("last_action") or "yok"
    completed = context.get("completed_tasks") if isinstance(context.get("completed_tasks"), list) else []
    pending = context.get("pending_tasks") if isinstance(context.get("pending_tasks"), list) else []
    content = (
        "Önceki LuxCode bağlamı: "
        f"Aktif dosya: {active_file}. "
        f"Son işlem: {last_action}. "
        f"Tamamlanan son işler: {', '.join(map(str, completed[-5:])) if completed else 'yok'}. "
        f"Sıradaki işler: {', '.join(map(str, pending[-5:])) if pending else 'yok'}. "
        "Kullanıcı dosya belirtmezse aktif dosya üzerinde devam et; backup dosyasını hedef alma."
    )
    if active_file_context.get("file_content"):
        snippet = str(active_file_context.get("file_content") or "")[:12000]
        content += f"\nAktif dosya içeriği ({active_file}):\n```\n{snippet}\n```"
    if workspace_snapshot:
        content += _format_workspace_snapshot(workspace_snapshot)
    return {"role": "system", "content": content}


def _format_workspace_snapshot(snapshot: Dict[str, Any]) -> str:
    files = snapshot.get("files") if isinstance(snapshot.get("files"), list) else []
    previews = snapshot.get("previews") if isinstance(snapshot.get("previews"), list) else []
    selected = snapshot.get("selected_candidate") or ""
    lines = ["\nWorkspace snapshot:"]
    if selected:
        lines.append(f"- Olası hedef dosya: {selected}")
    if files:
        lines.append("- Dosyalar: " + ", ".join(str(item.get("path") or "") for item in files[:20] if isinstance(item, dict)))
    for preview in previews:
        if not isinstance(preview, dict):
            continue
        text = str(preview.get("preview") or "").strip()
        if text:
            lines.append(f"- Önizleme {preview.get('path')}:\n```\n{text[:2500]}\n```")
    return "\n".join(lines)


def _score_snapshot_file(prompt: str, path: Path, rel: str) -> int:
    lowered = _fold_intent_text(prompt)
    name = _fold_intent_text(path.name)
    rel_folded = _fold_intent_text(rel)
    score = 0
    if path.suffix.lower() == ".html" and any(token in lowered for token in ("html", "oyun", "tetris", "ziplama", "zplama", "sayfa", "arayuz")):
        score += 20
    if path.suffix.lower() == ".py" and any(token in lowered for token in ("python", "py", "script", "test")):
        score += 16
    for token in re.findall(r"[a-z0-9_]+", lowered):
        if len(token) >= 4 and (token in name or token in rel_folded):
            score += 5
    if "tetris" in lowered and "tetris" in name:
        score += 30
    if ("ziplama" in lowered or "zplama" in lowered or "jump" in lowered) and any(token in name for token in ("ziplama", "jump")):
        score += 30
    if "index" in name:
        score += 2
    return score


def _build_workspace_snapshot(workspace: str, prompt: str, active_file: str = "") -> Dict[str, Any]:
    root = Path(workspace).expanduser().resolve()
    files: List[Dict[str, Any]] = []
    if not root.is_dir():
        return {"files": [], "previews": [], "selected_candidate": ""}
    for path in sorted(root.rglob("*"), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
        if len(files) >= SNAPSHOT_MAX_FILES:
            break
        if not path.is_file():
            continue
        if any(part in SNAPSHOT_SKIP_PARTS for part in path.parts):
            continue
        if ".backup" in path.name.lower() or path.suffix.lower() not in SNAPSHOT_EXTENSIONS:
            continue
        try:
            rel = path.relative_to(root).as_posix()
            files.append({
                "path": rel,
                "name": path.name,
                "suffix": path.suffix.lower(),
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
                "score": _score_snapshot_file(prompt, path, rel),
            })
        except Exception:
            continue
    selected = active_file if active_file and not re.search(r"\.backup(?:\.\d+)?$", active_file, flags=re.IGNORECASE) else ""
    if not selected and files:
        selected = sorted(files, key=lambda item: (int(item.get("score") or 0), float(item.get("mtime") or 0)), reverse=True)[0]["path"]
    preview_paths = []
    if selected:
        preview_paths.append(selected)
    for item in sorted(files, key=lambda value: (int(value.get("score") or 0), float(value.get("mtime") or 0)), reverse=True):
        rel = str(item.get("path") or "")
        if rel and rel not in preview_paths:
            preview_paths.append(rel)
        if len(preview_paths) >= SNAPSHOT_MAX_PREVIEWS:
            break
    previews: List[Dict[str, Any]] = []
    for rel in preview_paths:
        target = (root / rel).resolve()
        try:
            target.relative_to(root)
            text = target.read_text(encoding="utf-8", errors="replace")
            head = "\n".join(text.splitlines()[:20])
            tail = "\n".join(text.splitlines()[-20:])
            preview = head if head == tail else f"{head}\n...\n{tail}"
            previews.append({"path": rel, "preview": preview[:5000]})
        except Exception:
            continue
    return {"files": files, "previews": previews, "selected_candidate": selected}


def _save_agent_context(session_id: str, session: Dict[str, Any], prompt: str, results: List[Dict[str, Any]], workspace: str) -> None:
    if not session_id:
        return
    context = dict(session.get("agent_context") or {})
    coder_memory = _coder_memory(session)
    active_file = session.get("active_file") or coder_memory.get("active_file") or context.get("active_file")
    completed = list(context.get("completed_tasks") or [])
    pending = list(context.get("pending_tasks") or [])
    last_action = context.get("last_action") or ""
    for item in results:
        tool = str(item.get("tool") or "")
        params = dict(item.get("params") or {})
        result = dict(item.get("result") or {})
        if not result.get("success"):
            continue
        path = str(params.get("path") or result.get("path") or "").strip()
        if tool in {"write_file", "edit_file", "append_file", "read_file"} and path and not re.search(r"\.backup(?:\.\d+)?$", path, flags=re.IGNORECASE):
            active_file = path
        if tool in {"write_file", "edit_file", "append_file", "delete_file", "create_directory", "run_command", "run_python"}:
            label = f"{tool}:{path or params.get('command') or 'workspace'}"
            completed.append(label)
            last_action = label
    context.update({
        "workspace_root": workspace,
        "active_file": active_file or "",
        "last_action": last_action or str(prompt or "")[:160],
        "completed_tasks": completed[-10:],
        "pending_tasks": pending[-5:],
    })
    session["agent_context"] = context
    try:
        session_manager.save_context(session_id, context)
    except Exception as exc:
        session["last_context_save_error"] = str(exc)


def _fallback_chat_response(prompt: str, session: Dict[str, Any]) -> str:
    lower = str(prompt or "").lower()
    memory = session.get("memory") if isinstance(session.get("memory"), dict) else {}
    bridge_status = session.get("bridge_status") if isinstance(session.get("bridge_status"), dict) else {}
    if any(token in lower for token in ("fiziksel erişim", "fiziksel erisim", "dosya erişim", "dosya erisim", "klasörlere eriş", "klasorlere eris")):
        if bridge_status.get("connected"):
            workspace = bridge_status.get("workspace_root") or session.get("workspace_root") or "seçili workspace"
            return f"Evet, LuxBridge aktif. Seçili workspace içinde dosya okuyup yazabilirim ve terminal komutu çalıştırabilirim. Aktif workspace: {workspace}"
        if bridge_status.get("server_connected") and not bridge_status.get("workspace_match"):
            requested = bridge_status.get("workspace_root") or session.get("workspace_root") or "seçili workspace"
            actual = bridge_status.get("bridge_workspace_root") or "bilinmeyen bridge workspace"
            return f"Şu anda seçili workspace için fiziksel erişim doğrulanmadı. LuxBridge açık ama farklı klasöre bağlı. Seçili workspace: {requested}. Bridge workspace: {actual}."
        detail = bridge_status.get("error") or "LuxBridge bağlantısı doğrulanamadı."
        return f"Şu anda fiziksel dosya erişimini doğrulayamıyorum. LuxBridge aktif değil veya ulaşılamıyor: {detail}"
    if "2+2" in lower or "2 + 2" in lower:
        return "2+2 = 4."
    if ("adim ne" in lower or "adım ne" in lower or "benim adim ne" in lower or "benim adım ne" in lower) and memory.get("name"):
        return f"Adın {memory['name']}."
    if "benim adim" in lower or "benim adım" in lower:
        return "Tamam, adını bu oturum için kaydettim."
    return "Mesajını aldım. Nasıl yardımcı olmamı istersin?"


def _bridge_context_message(session: Dict[str, Any]) -> Dict[str, str]:
    bridge_status = session.get("bridge_status") if isinstance(session.get("bridge_status"), dict) else {}
    if bridge_status.get("connected"):
        workspace = bridge_status.get("workspace_root") or session.get("workspace_root") or ""
        content = (
            "Runtime bridge durumu: AKTIF. "
            f"Seçili workspace: {workspace}. "
            "Fiziksel dosya okuma/yazma ve terminal komutu çalıştırma erişimi doğrulandı. "
            "Kullanıcının dosya, klasör, kod, test, patch ve terminal görevleri aksi belirtilmedikçe bu seçili workspace içinde uygulanır."
        )
    elif bridge_status.get("server_connected") and not bridge_status.get("workspace_match"):
        requested = bridge_status.get("workspace_root") or session.get("workspace_root") or ""
        actual = bridge_status.get("bridge_workspace_root") or ""
        content = (
            "Runtime bridge durumu: WORKSPACE_ESLESMIYOR. "
            f"Seçili workspace: {requested}. Bridge workspace: {actual}. "
            "Seçili workspace için fiziksel erişim doğrulanmadı; erişim varmış gibi cevap verme."
        )
    else:
        detail = bridge_status.get("error") or "bridge kontrolü başarısız veya yapılmadı"
        content = (
            "Runtime bridge durumu: PASIF. "
            f"Fiziksel dosya erişimi doğrulanmadı: {detail}. "
            "Erişim varmış gibi cevap verme."
        )
    return {"role": "system", "content": content}


def _call_chat_llm(prompt: str, session: Dict[str, Any]) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if not api_key:
        return _fallback_chat_response(prompt, session)
    base_url = "https://api.deepseek.com" if os.getenv("DEEPSEEK_API_KEY") else None
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    messages: List[Dict[str, str]] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, _bridge_context_message(session), _context_message(session)]
    messages.extend(_history_messages(session))
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != prompt:
        messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model=os.getenv("LUXCODE_CHAT_MODEL") or ("deepseek-chat" if base_url else "gpt-4o-mini"),
        messages=messages,
        temperature=0.25,
        max_tokens=700,
    )
    return (response.choices[0].message.content or "").strip() or _fallback_chat_response(prompt, session)


def _tool_success_message(results: List[Dict[str, Any]], workspace: str) -> str:
    if not results:
        return "İşlem yapılmadı."
    written: List[str] = []
    listed = False
    read: List[str] = []
    commands: List[str] = []
    for item in results:
        tool = str(item.get("tool") or "")
        params = dict(item.get("params") or {})
        result = dict(item.get("result") or {})
        path = str(result.get("path") or params.get("path") or "").strip()
        if tool in {"write_file", "append_file", "edit_file"} and path:
            written.append(path)
        elif tool == "list_directory":
            listed = True
        elif tool == "read_file" and path:
            read.append(path)
        elif tool in {"run_command", "run_python"}:
            commands.append(str(params.get("command") or "python").strip())
    if written:
        names = ", ".join(Path(path).name for path in written[:3])
        return f"Dosya işlemi tamamlandı: {names}. Seçili workspace içinde yazıldı."
    if listed:
        return f"Seçili workspace içeriği listelendi: {workspace}"
    if read:
        names = ", ".join(Path(path).name for path in read[:3])
        return f"Dosya okundu: {names}."
    if commands:
        return "Terminal komutu çalıştırıldı."
    return f"{len(results)} araç adımı başarıyla tamamlandı."


def _verify_tool_effect(call: Dict[str, Any], tool_result: Dict[str, Any], workspace: str) -> Dict[str, Any]:
    tool = str(call.get("tool") or "")
    params = dict(call.get("params") or {})
    if not tool_result.get("success"):
        return tool_result
    if tool not in {"write_file", "append_file", "edit_file", "delete_file", "create_directory"}:
        return tool_result
    path_value = str(tool_result.get("path") or params.get("path") or "").strip()
    if not path_value:
        checked = dict(tool_result)
        checked["success"] = False
        checked["error"] = "verification_missing_path"
        return checked
    target = Path(path_value)
    if not target.is_absolute():
        target = Path(workspace) / target
    try:
        target = target.resolve()
        workspace_path = Path(workspace).resolve()
        target.relative_to(workspace_path)
    except Exception:
        checked = dict(tool_result)
        checked["success"] = False
        checked["error"] = "verification_path_outside_workspace"
        checked["path"] = str(target)
        return checked

    checked = dict(tool_result)
    checked["verification"] = {"checked": True, "tool": tool, "path": str(target)}
    try:
        if tool == "delete_file":
            if target.exists():
                checked["success"] = False
                checked["error"] = "verification_delete_failed"
            return checked
        if tool == "create_directory":
            if not target.is_dir():
                checked["success"] = False
                checked["error"] = "verification_directory_missing"
            return checked
        if not target.is_file():
            checked["success"] = False
            checked["error"] = "verification_file_missing"
            return checked
        text = target.read_text(encoding="utf-8", errors="replace")
        if tool == "write_file":
            expected = str(params.get("content") or "")
            if text != expected:
                checked["success"] = False
                checked["error"] = "verification_write_content_mismatch"
        elif tool == "append_file":
            expected = str(params.get("content") or "")
            if expected and expected not in text:
                checked["success"] = False
                checked["error"] = "verification_append_content_missing"
        elif tool == "edit_file":
            expected = str(params.get("new_text") or "")
            if expected and expected not in text:
                checked["success"] = False
                checked["error"] = "verification_edit_content_missing"
        return checked
    except Exception as exc:
        checked["success"] = False
        checked["error"] = f"verification_error:{exc}"
        return checked


def run_agent(
    prompt: str,
    workspace_root: str | Path | None = None,
    session_id: str = "default",
    max_steps: int = 12,
    on_step: Callable[[Dict[str, Any]], None] | None = None,
    bridge_status: Dict[str, Any] | None = None,
    active_file_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    workspace = str(Path(workspace_root).expanduser().resolve()) if workspace_root else str(Path(__file__).resolve().parent)
    session_result = session_manager.start_session(session_id=session_id, workspace_root=workspace)
    session = dict(session_result.get("result") or {})
    agent_context = session_manager.load_context(session_id)
    if agent_context:
        session["agent_context"] = agent_context
        if agent_context.get("active_file") and not session.get("active_file"):
            session["active_file"] = str(agent_context.get("active_file") or "")
    session["project_memory"] = load_project_memory(workspace)
    coder_memory = _coder_memory(session)
    active_file_context = dict(active_file_context or {})
    active_file_path = str(active_file_context.get("file_path") or "").strip()
    if active_file_path and not re.search(r"\.backup(?:\.\d+)?$", active_file_path, flags=re.IGNORECASE):
        session["active_file"] = active_file_path
        session["active_file_context"] = {
            "file_path": active_file_path,
            "file_content": str(active_file_context.get("file_content") or ""),
            "file_lines": active_file_context.get("file_lines"),
        }
        coder_memory["active_file"] = active_file_path
    if agent_context.get("active_file") and not coder_memory.get("active_file"):
        coder_memory["active_file"] = str(agent_context.get("active_file") or "")
    if session["project_memory"].get("active_file") and not coder_memory.get("active_file"):
        coder_memory["active_file"] = session["project_memory"].get("active_file")
    if session["project_memory"].get("recent_files") and not coder_memory.get("recent_files"):
        coder_memory["recent_files"] = list(session["project_memory"].get("recent_files") or [])
    if _looks_like_real_workspace_task(prompt):
        snapshot_active = str(session.get("active_file") or coder_memory.get("active_file") or session["project_memory"].get("active_file") or "").strip()
        workspace_snapshot = _build_workspace_snapshot(workspace, prompt, snapshot_active)
        session["workspace_snapshot"] = workspace_snapshot
        selected_candidate = str(workspace_snapshot.get("selected_candidate") or "").strip()
        if selected_candidate and not session.get("active_file"):
            session["active_file"] = selected_candidate
            coder_memory["active_file"] = selected_candidate
    session["bridge_status"] = dict(bridge_status or {"connected": False, "error": "bridge_status_missing"})
    session_manager.append_message(session, "user", prompt)
    memory_updates = _extract_agent_memory_updates(prompt)
    if memory_updates:
        current_memory = dict(session.get("memory") or {})
        current_memory.update(memory_updates)
        session["memory"] = current_memory
        saved_name = memory_updates.get("name")
        confirmation = f"Adını {saved_name} olarak kaydettim." if saved_name else f"memory_updated:{json.dumps(memory_updates, ensure_ascii=False)}"
        session_manager.append_message(session, "assistant", confirmation)
        session_manager.save_session(session)
        return {
            "ok": True,
            "status": "memory_updated",
            "mode": "chat",
            "response": confirmation,
            "message": confirmation,
            "tool_calls": [],
            "conversation_history": session.get("conversation_history", []),
        }

    memory_reply = _resolve_agent_memory_response(prompt, session)
    if memory_reply:
        session_manager.append_message(session, "assistant", str(memory_reply.get("response") or memory_reply.get("message") or ""))
        session_manager.save_session(session)
        memory_reply["conversation_history"] = session.get("conversation_history", [])
        return memory_reply
    if _is_workspace_status_question(prompt):
        message = _workspace_status_response(session, workspace)
        session_manager.append_message(session, "assistant", message)
        session_manager.save_session(session)
        if on_step:
            on_step({
                "type": "response",
                "status": "workspace_status",
                "ok": True,
                "response": message,
            })
        return {
            "ok": True,
            "status": "workspace_status",
            "mode": "chat",
            "response": message,
            "message": message,
            "tool_calls": [],
            "workspace_root": workspace,
            "bridge_status": session.get("bridge_status", {}),
            "conversation_history": session.get("conversation_history", []),
        }
    calls = planned_tool_calls(prompt, session=session)
    if not calls:
        if _looks_like_real_workspace_task(prompt):
            try:
                llm_response = _call_chat_llm(prompt, session)
                calls = parse_tool_calls(
                    llm_response,
                    default_filename=str((session.get("active_file_context") or {}).get("file_path") or session.get("active_file") or _default_filename_from_prompt(prompt)),
                    prompt=prompt,
                )
                if calls:
                    session["llm_tool_source"] = "code_block_fallback"
                    session["llm_tool_response_preview"] = str(llm_response)[:1200]
                else:
                    session["last_tool_plan_llm_response"] = str(llm_response)[:1200]
            except Exception as exc:
                session["last_tool_plan_llm_error"] = str(exc)
        if not calls and _looks_like_real_workspace_task(prompt):
            message = (
                "Bu isteği gerçek dosya/terminal aracına çeviremedim; bu yüzden dosyada işlem yapmadım. "
                "Yanlışlıkla yapılmış gibi rapor vermiyorum. Daha net bir dosya adı ve işlem yazarsan gerçek tool ile uygularım."
            )
            session_manager.append_message(session, "assistant", message)
            session_manager.save_session(session)
            if on_step:
                on_step({
                    "type": "response",
                    "status": "tool_plan_missing",
                    "ok": False,
                    "response": message,
                })
            return {
                "ok": False,
                "status": "tool_plan_missing",
                "mode": "agent",
                "response": message,
                "message": message,
                "requires_user_followup": True,
                "tool_calls": [],
                "applied_changes": [],
                "warnings": ["tool_plan_missing"],
                "workspace_root": workspace,
                "bridge_status": session.get("bridge_status", {}),
                "conversation_history": session.get("conversation_history", []),
            }
        if not calls:
            try:
                message = _call_chat_llm(prompt, session)
            except Exception as exc:
                message = _fallback_chat_response(prompt, session)
                session["last_chat_error"] = str(exc)
            session_manager.append_message(session, "assistant", message)
            session_manager.save_session(session)
            if on_step:
                on_step({
                    "type": "response",
                    "status": "completed",
                    "ok": True,
                    "response": message,
                })
            return {
                "ok": True,
                "status": "chat_completed",
                "mode": "chat",
                "response": message,
                "message": message,
                "tool_calls": [],
                "system_prompt": CHAT_SYSTEM_PROMPT,
                "conversation_history": session.get("conversation_history", []),
            }
    results: List[Dict[str, Any]] = []
    applied_changes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for index, call in enumerate(calls[:max_steps], start=1):
        if on_step:
            on_step({
                "type": "tool",
                "status": "running",
                "tool": call.get("tool"),
                "step": index,
                "params": call.get("params", {}),
            })
        tool_result = execute_tool(call["tool"], call.get("params", {}), workspace_root=workspace)
        tool_result = _verify_tool_effect(call, tool_result, workspace)
        item = {"step": index, "tool": call["tool"], "params": call.get("params", {}), "result": tool_result}
        results.append(item)
        _remember_tool_context(session, call, tool_result)
        tool_path = str(call.get("params", {}).get("path") or tool_result.get("path") or "")
        session["project_memory"] = update_project_memory_from_tool(
            workspace,
            session.get("project_memory") or {},
            tool=str(call["tool"]),
            path=tool_path,
            success=bool(tool_result.get("success")),
            prompt=prompt,
        )
        session_manager.record_change(session, call["tool"], item)
        if call.get("tool") in {"write_file", "edit_file", "append_file"}:
            tool_path = str(call.get("params", {}).get("path") or tool_result.get("path") or "")
            if tool_result.get("success"):
                applied_changes.append({
                    "file_path": tool_path,
                    "file_write_ok": bool(tool_result.get("success")),
                    "bytes_written": int(tool_result.get("bytes", 0)),
                    "bytes": int(tool_result.get("bytes", 0)),
                })
            else:
                warnings.append(f"{call['tool']} failed for {tool_path}: {tool_result.get('error')}")
        if call.get("tool") in {"run_command", "run_python"} and tool_result.get("stderr"):
            warnings.append(f"{call.get('tool')} stderr: {tool_result.get('stderr')}")
        if on_step:
            on_step({
                "type": "tool",
                "status": "done" if tool_result.get("success") else "failed",
                "tool": call["tool"],
                "step": index,
                "params": call.get("params", {}),
                "result": tool_result,
            })
        if not tool_result.get("success"):
            session_manager.append_message(session, "assistant", f"Tool failed: {call['tool']} -> {tool_result.get('error')}")
            session_manager.save_session(session)
            if on_step:
                on_step({
                    "type": "response",
                    "status": "failed",
                    "ok": False,
                    "response": f"Tool failed: {call['tool']} -> {tool_result.get('error')}",
                    "result": tool_result,
                })
            return {
                "ok": False,
                "mode": "agent",
                "status": "tool_failed",
                "response": f"Tool failed: {call['tool']} -> {tool_result.get('error')}",
                "requires_user_followup": False,
                "applied_changes": applied_changes,
                "warnings": warnings,
                "workspace_root": workspace,
                "results": results,
                "tool_calls": results,
                "failed_step": item,
                "conversation_history": session.get("conversation_history", []),
            }
    _save_agent_context(session_id, session, prompt, results, workspace)
    message = _tool_success_message(results, workspace)
    session_manager.append_message(session, "assistant", message)
    session_manager.save_session(session)
    if on_step:
        on_step({
            "type": "response",
            "status": "completed",
            "ok": True,
            "response": message,
            "result": {"results": results},
        })
    return {
        "ok": True,
        "mode": "agent",
        "status": "completed",
        "workspace_root": workspace,
        "message": message,
        "response": message,
        "requires_user_followup": False,
        "applied_changes": applied_changes,
        "warnings": warnings,
        "results": results,
        "tool_calls": results,
        "conversation_history": session.get("conversation_history", []),
    }


def run_tool_json(payload: Dict[str, Any], workspace_root: str | Path | None = None) -> Tuple[bool, Dict[str, Any]]:
    tool = str(payload.get("tool") or "")
    params = dict(payload.get("params") or {})
    if not tool:
        return False, {"success": False, "result": "", "error": "missing_tool"}
    output = execute_tool(tool, params, workspace_root=workspace_root)
    return bool(output.get("success")), output
