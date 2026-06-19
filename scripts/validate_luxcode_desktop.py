from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    commands = [
        [sys.executable, "-m", "py_compile", "run_desktop.py", "luxcode_desktop/main.py", "luxcode_desktop/app.py", "luxcode_desktop/ui/main_window.py", "luxcode_desktop/services/backend_process_service.py"],
        [sys.executable, "-m", "unittest", "discover", "luxcode_desktop/tests"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
    print("PASS luxcode desktop validator: checks=16")


if __name__ == "__main__":
    main()
