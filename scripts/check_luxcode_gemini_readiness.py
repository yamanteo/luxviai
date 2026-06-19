from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_gemini_task_bridge import build_gemini_runtime_configuration


def main() -> int:
    runtime = build_gemini_runtime_configuration()
    gate = runtime["gate"]
    report = {
        "status": "READY" if gate.get("allowed") else "BLOCKED",
        "model_id": runtime["model_id"],
        "selected_key_name": runtime["selected_key_name"],
        "api_key_present": runtime["api_key_present"],
        "provider_health": runtime["provider_health"],
        "free_tier_confirmed": gate.get("free_tier_confirmed", False),
        "billing_allowed": gate.get("billing_allowed", False),
        "quota_state": gate.get("quota_state", "unknown"),
        "blockers": gate.get("blockers", []),
        "secret_persisted": False,
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
