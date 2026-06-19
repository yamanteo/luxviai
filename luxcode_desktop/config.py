from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BACKEND_URL = "http://127.0.0.1:5000"
DEFAULT_MAIN_REPOSITORY = Path(__file__).resolve().parents[1]
RUNTIME_DIR = DEFAULT_MAIN_REPOSITORY / ".luxcode_runtime"
LAYOUT_FILE = RUNTIME_DIR / "desktop_layout.json"
PERSISTENT_RUNTIME_FILE = RUNTIME_DIR / "persistent_runtime.json"
SECURE_CREDENTIAL_DIR = RUNTIME_DIR / "secure_credentials"
LOG_DIR = RUNTIME_DIR / "logs"
INSTANCE_LOCK_FILE = RUNTIME_DIR / "desktop_instance.lock"


LEFT_TABS = ("Dosyalar", "Modeller", "Görevler", "Alan")
CENTER_TABS = (
    "Çalışma",
    "Yapılan/Kalan",
    "Araçlar",
    "Plan",
    "Ayarlar",
    "Yama",
    "Test",
    "Geçmiş",
)
RIGHT_TABS = ("Durum", "İzinler", "Yama", "Test", "Entegrasyon", "Kanıt")


@dataclass(frozen=True)
class LayoutConfig:
    left_visible: bool = True
    right_visible: bool = True
    left_width: int = 240
    right_width: int = 360
    window_geometry: str = "1440x860"

    def bounded(self) -> "LayoutConfig":
        return LayoutConfig(
            left_visible=self.left_visible,
            right_visible=self.right_visible,
            left_width=max(220, int(self.left_width)),
            right_width=max(320, int(self.right_width)),
            window_geometry=self.window_geometry or "1440x860",
        )


def load_layout() -> LayoutConfig:
    try:
        data = json.loads(LAYOUT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return LayoutConfig()
    return LayoutConfig(
        left_visible=bool(data.get("left_visible", True)),
        right_visible=bool(data.get("right_visible", True)),
        left_width=int(data.get("left_width", 240)),
        right_width=int(data.get("right_width", 360)),
        window_geometry=str(data.get("window_geometry", "1440x860")),
    ).bounded()


def save_layout(config: LayoutConfig) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    LAYOUT_FILE.write_text(json.dumps(config.bounded().__dict__, indent=2), encoding="utf-8")
