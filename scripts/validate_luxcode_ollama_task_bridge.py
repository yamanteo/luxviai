from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from luxcode_task_orchestrator import advance_luxcode_task, create_luxcode_task
    from luxcode_tier1_local_worker import TIER1_OLLAMA_MODEL_ID, check_ollama_model

    model_state = check_ollama_model(TIER1_OLLAMA_MODEL_ID, timeout_seconds=5)
    if not model_state.get("ok") or not model_state.get("model_available"):
        print(json.dumps({"status": "SKIP", "reason": "ollama_model_unavailable", "model_state": model_state}, ensure_ascii=False))
        return 0

    with tempfile.TemporaryDirectory(prefix="luxcode_ollama_bridge_") as temp_dir:
        repo = Path(temp_dir) / "repo"
        source = repo / "src" / "sample.py"
        source.parent.mkdir(parents=True)
        original = "def answer() -> int:\n    return 1\n"
        source.write_text(original, encoding="utf-8")

        created = create_luxcode_task(
            original_request=(
                "Prepare a safe patch preview for src/sample.py so answer() returns 2 instead of 1. "
                "Use the exact existing source text and do not broaden the scope."
            ),
            repository_root=str(repo),
            suspected_files=["src/sample.py"],
            selected_files=["src/sample.py"],
            requested_files=["src/sample.py"],
            forbidden_files=[".env"],
            permission_mode="approval_required",
            mode="plan",
        )
        task_id = str(created.get("task_id") or "")
        if not task_id:
            print("FAIL: task was not created")
            return 1

        routed = advance_luxcode_task(task_id, action="next")
        diagnosed = advance_luxcode_task(task_id, action="next")
        patched = advance_luxcode_task(task_id, action="next")

        checks = {
            "routed": routed.get("current_state") == "routed",
            "diagnosed": diagnosed.get("current_state") == "diagnosis_ready",
            "awaiting_approval": patched.get("current_state") == "awaiting_approval",
            "ollama_selected": patched.get("active_engine") == "tier1_local_worker",
            "model_selected": patched.get("active_model") == TIER1_OLLAMA_MODEL_ID,
            "real_attempt_recorded": bool(patched.get("real_attempts")),
            "evidence_recorded": bool(patched.get("evidence")),
            "patch_steps_present": bool((patched.get("patch_summary") or {}).get("patch_steps")),
            "no_file_write": source.read_text(encoding="utf-8") == original,
            "changed_files_empty": not patched.get("changed_files"),
            "external_api_not_used": patched.get("external_api_used") is False,
        }
        if not all(checks.values()):
            print(json.dumps({"status": "FAIL", "checks": checks, "patched": patched}, ensure_ascii=False, default=str))
            return 1

        print(json.dumps({"status": "PASS", "checks": checks, "task_id": task_id}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
