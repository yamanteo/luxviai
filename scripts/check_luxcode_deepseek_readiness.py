from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from luxcode_direct_deepseek_task_bridge import (
        EXACT_APPROVAL_TEXT,
        build_direct_deepseek_runtime_configuration,
    )

    runtime = build_direct_deepseek_runtime_configuration()
    report = {
        "status": runtime["status"],
        "blockers": runtime["blockers"],
        "api_key_present": runtime["api_key_present"],
        "selected_key_name": runtime["selected_key_name"],
        "model_id": runtime["model_id"],
        "maximum_cost_usd": runtime["maximum_cost_usd"],
        "pricing_snapshot_version": runtime[
            "pricing_snapshot_version"
        ],
        "pricing": runtime["pricing"],
        "task_approval_required": True,
        "exact_confirmation_text": EXACT_APPROVAL_TEXT,
        "automatic_purchase_allowed": False,
        "automatic_upgrade_allowed": False,
        "auto_apply_allowed": False,
        "paid_call_performed": False,
        "secret_persisted": False,
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "READY_FOR_TASK_APPROVAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
