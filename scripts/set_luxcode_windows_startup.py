from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def startup_dir() -> Path:
    appdata = Path(os.environ.get("APPDATA", ""))
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    args = parser.parse_args()

    if os.name != "nt":
        print(json.dumps({"ok": False, "reason": "windows_required"}))
        return 1

    shortcut = startup_dir() / "LuxCode.lnk"
    if args.disable:
        shortcut.unlink(missing_ok=True)
        print(json.dumps({"ok": True, "enabled": False, "shortcut": str(shortcut)}))
        return 0

    pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.is_file():
        print(json.dumps({"ok": False, "reason": "pythonw_missing"}))
        return 1

    shortcut.parent.mkdir(parents=True, exist_ok=True)
    command = "\n".join(
        [
            "$shell = New-Object -ComObject WScript.Shell",
            f"$shortcut = $shell.CreateShortcut({ps_quote(str(shortcut))})",
            f"$shortcut.TargetPath = {ps_quote(str(pythonw))}",
            "$shortcut.Arguments = '-m luxcode_desktop.main'",
            f"$shortcut.WorkingDirectory = {ps_quote(str(ROOT))}",
            "$shortcut.Description = 'LuxCode Desktop Startup'",
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
        "enabled": result.returncode == 0 and shortcut.is_file(),
        "shortcut": str(shortcut),
        "stderr": (result.stderr or "")[-1000:],
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
