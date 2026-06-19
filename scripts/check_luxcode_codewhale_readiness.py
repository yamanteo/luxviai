from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_codewhale_task_bridge import inspect_codewhale_readiness


def main() -> int:
    report = inspect_codewhale_readiness(repository_root=str(ROOT))
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("status") == "READY_FOR_TASK_APPROVAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
