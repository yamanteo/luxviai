from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def desktop_dir() -> Path:
    candidates = [
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "Desktop",
    ]
    for item in candidates:
        if item.is_dir():
            return item
    return candidates[0]


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    if os.name != "nt":
        print(json.dumps({"ok": False, "reason": "windows_required"}))
        return 1

    pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.is_file():
        print(json.dumps({"ok": False, "reason": "pythonw_missing"}))
        return 1

    shortcut = desktop_dir() / "LuxCode.lnk"
    command = "\n".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({ps_quote(str(shortcut))})",
            f"$shortcut.TargetPath = {ps_quote(str(pythonw))}",
            "$shortcut.Arguments = '-m luxcode_desktop.main'",
            f"$shortcut.WorkingDirectory = {ps_quote(str(ROOT))}",
            "$shortcut.Description = 'LuxCode Desktop'",
            f"$shortcut.IconLocation = {ps_quote(str(pythonw) + ',0')}",
            "$shortcut.Save()",
        ]
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    payload = {
        "ok": result.returncode == 0 and shortcut.is_file(),
        "shortcut": str(shortcut),
        "returncode": result.returncode,
        "stderr": (result.stderr or "")[-1000:],
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
