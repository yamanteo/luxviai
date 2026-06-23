/**
 * LuxCode Bridge — v1
 * Mevcut LuxCode arayüzüne ekle, fiziksel dosya erişimi kazanırsın.
 * 
 * Kullanım: HTML dosyanda şunu ekle:
 * <script src="luxcode_bridge.js"></script>
 */

const LuxBridge = {
  base: "http://localhost:8765",

  // ─── DOSYA İŞLEMLERİ ───────────────────────────────────────

  async listFiles(path = "") {
    const r = await fetch(`${this.base}/files?path=${encodeURIComponent(path)}`);
    return r.json();
  },

  async readFile(path) {
    const r = await fetch(`${this.base}/file/read?path=${encodeURIComponent(path)}`);
    if (!r.ok) throw new Error(`Dosya okunamadı: ${path}`);
    return r.json(); // { path, content, lines }
  },

  async writeFile(path, content) {
    const r = await fetch(`${this.base}/file/write`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content })
    });
    return r.json(); // { ok, path, bytes }
  },

  async deleteFile(path) {
    const r = await fetch(`${this.base}/file/delete?path=${encodeURIComponent(path)}`, {
      method: "DELETE"
    });
    return r.json();
  },

  async createDir(path) {
    const r = await fetch(`${this.base}/file/create_dir`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path })
    });
    return r.json();
  },

  async searchFiles(query, ext = "") {
    const r = await fetch(`${this.base}/file/search?query=${encodeURIComponent(query)}&ext=${ext}`);
    return r.json(); // { results: [{file, matches}] }
  },

  // ─── TERMINAL ──────────────────────────────────────────────

  async runCommand(command, cwd = "") {
    const r = await fetch(`${this.base}/shell/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, cwd })
    });
    return r.json(); // { ok, stdout, stderr, code }
  },

  // ─── AI CASCADE ────────────────────────────────────────────

  async ask(prompt, context = "", filePath = "") {
    const r = await fetch(`${this.base}/ai/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, context, file_path: filePath })
    });
    return r.json(); // { ok, model, response }
  },

  // ─── BAĞLANTI KONTROLÜ ─────────────────────────────────────

  async isConnected() {
    try {
      const r = await fetch(`${this.base}/files`, { signal: AbortSignal.timeout(2000) });
      return r.ok;
    } catch {
      return false;
    }
  }
};

// Sayfa yüklenince bağlantıyı kontrol et
window.addEventListener("DOMContentLoaded", async () => {
  const connected = await LuxBridge.isConnected();
  if (connected) {
    console.log("✅ LuxCode Bridge bağlı — dosya erişimi aktif");
    document.dispatchEvent(new CustomEvent("luxbridge:ready"));
  } else {
    console.warn("⚠️ LuxCode Bridge bağlı değil. luxcode_server.py çalışıyor mu?");
    document.dispatchEvent(new CustomEvent("luxbridge:offline"));
  }
});

window.LuxBridge = LuxBridge;
