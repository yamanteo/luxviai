from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_runtime_settings import (
    capture_current_environment,
    get_runtime_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure LuxCode persistent runtime without plaintext secrets."
    )
    parser.add_argument(
        "--capture-current",
        action="store_true",
        help="Capture Gemini/OpenRouter keys from this process into Windows DPAPI.",
    )
    parser.add_argument(
        "--capture-deepseek-chat",
        action="store_true",
        help="Also capture DEEPSEEK_API_KEY for the existing chat backend.",
    )
    parser.add_argument(
        "--enable-manual-agents",
        action="store_true",
        help="Keep CodeWhale and Codex ready, but still task-scoped and manual-only.",
    )
    args = parser.parse_args()

    if args.capture_current or args.capture_deepseek_chat or args.enable_manual_agents:
        report = capture_current_environment(
            ROOT,
            capture_free_providers=args.capture_current,
            capture_deepseek_chat=args.capture_deepseek_chat,
            enable_manual_agents=args.enable_manual_agents,
        )
    else:
        report = {
            "ok": True,
            "message": "No changes requested.",
        }

    report["runtime_status"] = get_runtime_status(ROOT)
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
