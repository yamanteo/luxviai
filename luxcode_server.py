"""
LuxCode Local Server
--------------------
Çalıştır: python luxcode_server.py
Sonra tarayıcıda: http://localhost:8765
Bu server LuxCode arayüzüne fiziksel dosya erişimi sağlar.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import subprocess, os, json, glob
from pathlib import Path
from typing import Optional

app = FastAPI()

# CORS — tarayıcıdan erişim için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Çalışma dizini — isteğe göre değiştir
WORKSPACE = os.getenv("LUXCODE_WORKSPACE") or str(Path(__file__).resolve().parent)
os.makedirs(WORKSPACE, exist_ok=True)

# ============================================================
# DOSYA İŞLEMLERİ
# ============================================================

class FileRequest(BaseModel):
    path: str
    content: Optional[str] = None

class ShellRequest(BaseModel):
    command: str
    cwd: Optional[str] = None

def safe_path(path: str) -> Path:
    """Güvenli: sadece workspace içine erişim"""
    full = (Path(WORKSPACE) / path).resolve()
    if not str(full).startswith(str(Path(WORKSPACE).resolve())):
        raise HTTPException(400, "Workspace dışına erişim yasak")
    return full

@app.get("/files")
def list_files(path: str = ""):
    """Klasör içeriğini listele"""
    target = safe_path(path)
    if not target.exists():
        return {"files": [], "dirs": []}
    files, dirs = [], []
    for item in sorted(target.iterdir()):
        if item.name.startswith('.'): continue
        if item.is_file():
            files.append({"name": item.name, "path": str(item.relative_to(WORKSPACE)), "size": item.stat().st_size})
        elif item.is_dir():
            dirs.append({"name": item.name, "path": str(item.relative_to(WORKSPACE))})
    return {"files": files, "dirs": dirs, "current": str(target.relative_to(WORKSPACE))}

@app.get("/file/read")
def read_file(path: str):
    """Dosya içeriğini oku"""
    target = safe_path(path)
    if not target.exists():
        raise HTTPException(404, f"Dosya bulunamadı: {path}")
    try:
        content = target.read_text(encoding='utf-8')
        return {"path": path, "content": content, "lines": len(content.splitlines())}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/file/write")
def write_file(req: FileRequest):
    """Dosya yaz/güncelle"""
    target = safe_path(req.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(req.content or "", encoding='utf-8')
    return {"ok": True, "path": req.path, "bytes": len(req.content or "")}

@app.delete("/file/delete")
def delete_file(path: str):
    """Dosya sil"""
    target = safe_path(path)
    if not target.exists():
        raise HTTPException(404, "Dosya bulunamadı")
    target.unlink()
    return {"ok": True}

@app.post("/file/create_dir")
def create_dir(req: FileRequest):
    """Klasör oluştur"""
    target = safe_path(req.path)
    target.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": req.path}

@app.get("/file/search")
def search_files(query: str, ext: str = ""):
    """Dosya içinde metin ara"""
    results = []
    pattern = f"**/*{ext}" if ext else "**/*"
    for f in Path(WORKSPACE).glob(pattern):
        if f.is_file():
            try:
                text = f.read_text(encoding='utf-8', errors='ignore')
                if query.lower() in text.lower():
                    lines = [(i+1, l.strip()) for i,l in enumerate(text.splitlines()) if query.lower() in l.lower()]
                    results.append({"file": str(f.relative_to(WORKSPACE)), "matches": lines[:5]})
            except: pass
    return {"results": results[:20]}

# ============================================================
# TERMINAL / SHELL KOMUTLARI
# ============================================================

@app.post("/shell/run")
def run_shell(req: ShellRequest):
    """Shell komutu çalıştır"""
    cwd = req.cwd or WORKSPACE
    try:
        result = subprocess.run(
            req.command, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Timeout (30s)", "code": -1}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "code": -1}

# ============================================================
# MODEL CASCADE SİSTEMİ
# ============================================================

class AIRequest(BaseModel):
    prompt: str
    context: Optional[str] = None  # açık dosya içeriği
    file_path: Optional[str] = None

@app.post("/ai/ask")
def ai_ask(req: AIRequest):
    """
    Cascade: Ollama → Gemini → Deepseek → Whale → Codex
    Her model başarısız olursa bir sonrakine geçer.
    """
    errors = []

    # 1. Ollama (tamamen ücretsiz, local)
    try:
        import requests
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": "codellama",  # veya hangi model kuruluysa
            "prompt": build_prompt(req),
            "stream": False
        }, timeout=30)
        if r.ok:
            return {"ok": True, "model": "ollama/codellama", "response": r.json().get("response", "")}
    except Exception as e:
        errors.append(f"Ollama: {e}")

    # 2. Gemini Flash (ücretsiz tier)
    try:
        import requests
        GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
        if GEMINI_KEY:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": build_prompt(req)}]}]},
                timeout=30
            )
            if r.ok:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return {"ok": True, "model": "gemini-flash", "response": text}
    except Exception as e:
        errors.append(f"Gemini: {e}")

    # 3. Deepseek (çok ucuz / neredeyse bedava)
    try:
        import requests
        DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
        if DS_KEY:
            r = requests.post("https://api.deepseek.com/v1/chat/completions", 
                headers={"Authorization": f"Bearer {DS_KEY}"},
                json={"model": "deepseek-coder", "messages": [{"role":"user","content": build_prompt(req)}]},
                timeout=30
            )
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                return {"ok": True, "model": "deepseek", "response": text}
    except Exception as e:
        errors.append(f"Deepseek: {e}")

    # 4. Tüm ücretsizler başarısız
    return {"ok": False, "errors": errors, "response": "Tüm modeller başarısız. Ücretli modeli dene."}

def build_prompt(req: AIRequest) -> str:
    parts = []
    if req.context:
        parts.append(f"Açık dosya ({req.file_path or 'bilinmiyor'}):\n```\n{req.context[:3000]}\n```\n")
    parts.append(req.prompt)
    return "\n".join(parts)

# ============================================================
# ÇALIŞTIR
# ============================================================
if __name__ == "__main__":
    import uvicorn
    print(f"""
╔══════════════════════════════════════╗
║       LuxCode Local Server           ║
║  Workspace: {WORKSPACE}
║  Arayüz: http://localhost:8765       ║
╚══════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8765)
