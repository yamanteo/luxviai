from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _mock_response(url, payload, api_key, *, timeout_seconds):
    user_message = payload["messages"][-1]["content"]
    prompt = json.loads(user_message)
    request_id = prompt["request_id"]
    target_file = prompt["target_files"][0]
    content = json.dumps(
        {
            "response_id": "rsp-deepseek-task-bridge-1",
            "request_id": request_id,
            "response_status": "completed",
            "analysis_summary": "mocked paid DeepSeek safe patch",
            "completed_scope": ["direct_deepseek_task_bridge"],
            "remaining_gap": "",
            "target_files": [target_file],
            "target_symbols": [],
            "patch_operations": [
                {
                    "operation_id": "op-deepseek-task-1",
                    "operation_type": "replace_text",
                    "file_path": target_file,
                    "anchor_text": "",
                    "old_text": "def greet():\n    return 1\n",
                    "new_text": "def greet():\n    return 2\n",
                    "expected_occurrences": 1,
                    "reason": "mocked exact replacement",
                    "confidence": 0.98,
                }
            ],
            "validation_recommendations": ["py_compile"],
            "assumptions": [],
            "uncertainties": [],
            "risk_flags": [],
            "scope_violations": [],
            "unsupported_requests": [],
            "usage_metadata": {
                "input_tokens": 120,
                "output_tokens": 90,
                "estimated_cost": 0.00005,
            },
        },
        sort_keys=True,
    )
    return {
        "ok": True,
        "status": "success",
        "http_status": 200,
        "provider_request_id": "req-deepseek-mock-1",
        "latency_ms": 11,
        "response": {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 90,
            },
        },
    }


def _run_offline() -> dict:
    from luxcode_direct_deepseek_task_bridge import (
        DIRECT_DEEPSEEK_MODEL_ID,
        EXACT_APPROVAL_TEXT,
        build_direct_deepseek_runtime_configuration,
        build_direct_deepseek_task_approval,
        execute_direct_deepseek_task_bridge,
    )

    with tempfile.TemporaryDirectory(
        prefix="lux_deepseek_task_bridge_"
    ) as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        target = repo / "src" / "app.py"
        target.write_text(
            "def greet():\n    return 1\n",
            encoding="utf-8",
        )
        before = target.read_bytes()
        approval = build_direct_deepseek_task_approval(
            task_id="task-deepseek-bridge",
            repository_root=str(repo),
            target_files=["src/app.py"],
            maximum_cost_usd=0.001,
        )
        approval.update(
            {
                "approved": True,
                "consumed": False,
                "confirmation_text": EXACT_APPROVAL_TEXT,
            }
        )
        env = {
            "DEEPSEEK_API_KEY": "sk-test-secret",
            "LUXCODE_DEEPSEEK_ENABLED": "1",
            "LUXCODE_DEEPSEEK_TRANSPORT_ENABLED": "1",
            "LUXCODE_DEEPSEEK_REAL_REQUESTS_ENABLED": "1",
            "LUXCODE_DEEPSEEK_NETWORK_ALLOWED": "1",
            "LUXCODE_DEEPSEEK_BILLING_ENABLED": "1",
            "LUXCODE_DEEPSEEK_MODEL_ACCESS_VERIFIED": "1",
            "LUXCODE_DEEPSEEK_PRICING_VERIFIED": "1",
            "LUXCODE_DEEPSEEK_ACCOUNT_BALANCE_CONFIRMED": "1",
            "LUXCODE_DEEPSEEK_MAX_COST_USD": "0.001",
        }
        readiness = build_direct_deepseek_runtime_configuration(env)
        blocked = execute_direct_deepseek_task_bridge(
            task_id="task-deepseek-blocked",
            repository_root=str(repo),
            task_summary="blocked without approval",
            target_files=["src/app.py"],
            target_symbols=[],
            minimum_context={
                "src/app.py": "def greet():\n    return 1\n"
            },
            previous_result={
                "free_tier_exhaustion_confirmed": True,
                "remaining_gap": {"remaining_gap": "needs paid patch"},
            },
            approval=None,
            environ=env,
            http_call=_mock_response,
        )
        result = execute_direct_deepseek_task_bridge(
            task_id="task-deepseek-bridge",
            repository_root=str(repo),
            task_summary="Change greet return value",
            target_files=["src/app.py"],
            target_symbols=[],
            minimum_context={
                "src/app.py": "def greet():\n    return 1\n"
            },
            previous_result={
                "free_tier_exhaustion_confirmed": True,
                "remaining_gap": {"remaining_gap": "needs paid patch"},
            },
            approval=approval,
            environ=env,
            http_call=_mock_response,
        )
        after = target.read_bytes()
        checks = {
            "readiness_open": (
                readiness["status"] == "READY_FOR_TASK_APPROVAL"
            ),
            "blocked_without_task_approval": (
                blocked.get("state")
                == "deepseek_paid_approval_required"
                and blocked.get("external_api_used") is False
            ),
            "bridge_ok": result.get("ok") is True,
            "model_selected": (
                result.get("model_id") == DIRECT_DEEPSEEK_MODEL_ID
            ),
            "external_api_recorded": (
                result.get("external_api_used") is True
            ),
            "patch_step_present": bool(result.get("patch_steps")),
            "no_file_write": before == after,
            "apply_blocked": result.get("can_apply_now") is False,
            "cost_cap_enforced": (
                float(result.get("maximum_cost_usd", 1)) <= 0.001
            ),
            "secret_not_persisted": (
                "sk-test-secret" not in json.dumps(result)
            ),
        }
        return {
            "status": (
                "PASS" if all(checks.values()) else "FAIL"
            ),
            "checks": checks,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": (
                        "Paid live DeepSeek tests require a separate "
                        "task-scoped approval. No request was sent."
                    ),
                    "external_api_used": False,
                },
                sort_keys=True,
            )
        )
        return 2
    report = _run_offline()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
