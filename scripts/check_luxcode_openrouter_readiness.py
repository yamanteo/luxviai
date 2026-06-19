
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from luxcode_free_cloud_task_bridge import (
        build_free_cloud_runtime_configuration,
    )

    runtime = build_free_cloud_runtime_configuration(os.environ)
    gate = runtime.get("gate", {})
    report = {
        "status": "READY" if gate.get("allowed") else "BLOCKED",
        "selected_key_name": runtime.get("selected_key_name"),
        "api_key_present": runtime.get("api_key_present", False),
        "provider_health": runtime.get("provider_health"),
        "quota_state": runtime.get("quota_state"),
        "free_tier_confirmed": runtime.get(
            "free_tier_confirmed",
            False,
        ),
        "billing_allowed": runtime.get("billing_allowed", False),
        "paid_fallback_allowed": runtime.get(
            "paid_fallback_allowed",
            False,
        ),
        "models": runtime.get("models", []),
        "blockers": gate.get("blockers", []),
        "secret_persisted": runtime.get("secret_persisted", False),
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
