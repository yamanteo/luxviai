from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _enabled_env(api_key: str = "fixture-gemini-key") -> dict[str, str]:
    return {
        "GEMINI_API_KEY": api_key,
        "LUXCODE_GEMINI_ENABLED": "1",
        "LUXCODE_GEMINI_TRANSPORT_ENABLED": "1",
        "LUXCODE_GEMINI_REAL_REQUESTS": "1",
        "LUXCODE_GEMINI_NETWORK_ALLOWED": "1",
        "LUXCODE_GEMINI_FREE_TIER_CONFIRMED": "1",
        "LUXCODE_GEMINI_BILLING_DISABLED_CONFIRMED": "1",
        "LUXCODE_GEMINI_MODEL_ACCESS_VERIFIED": "1",
        "LUXCODE_GEMINI_KEY_TYPE": "auth_key",
        "LUXCODE_GEMINI_QUOTA_STATE": "available",
        "LUXCODE_GEMINI_MODEL_ID": "gemini-3.5-flash",
    }


def _candidate_json() -> str:
    return json.dumps(
        {
            "status": "completed",
            "analysis_summary": "Gemini produced one exact safe preview replacement.",
            "completed_scope": ["free_gemini"],
            "remaining_gap": "",
            "target_files": ["src/app.py"],
            "target_symbols": [],
            "patch_operations": [
                {
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "old_text": "def greet():\n    return 1\n",
                    "new_text": "def greet():\n    return 2\n",
                    "expected_occurrences": 1,
                    "reason": "safe fixture replacement",
                    "confidence": 0.98,
                }
            ],
            "validation_recommendations": ["py_compile"],
            "assumptions": [],
            "uncertainties": [],
            "risk_flags": [],
        },
        sort_keys=True,
    )


def _mock_http(url, payload, api_key, *, timeout_seconds):
    assert url.startswith("https://generativelanguage.googleapis.com/")
    assert api_key == "fixture-gemini-key"
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert "systemInstruction" in payload
    return {
        "ok": True,
        "status": "success",
        "response_id": "gemini-bridge-offline",
        "latency_ms": 4,
        "response": {
            "modelVersion": "gemini-3.5-flash",
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": _candidate_json()}]},
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50,
                "totalTokenCount": 150,
            },
        },
    }


def _run_offline() -> dict:
    from luxcode_gemini_task_bridge import execute_gemini_task_bridge

    with tempfile.TemporaryDirectory(prefix="luxcode_gemini_bridge_") as tmp:
        repo = Path(tmp) / "repo"
        target = repo / "src" / "app.py"
        target.parent.mkdir(parents=True)
        original = "def greet():\n    return 1\n"
        target.write_text(original, encoding="utf-8")
        before = hashlib.sha256(target.read_bytes()).hexdigest()

        result = execute_gemini_task_bridge(
            task_id="task-gemini-bridge-offline",
            repository_root=str(repo),
            task_summary="Change greet return from 1 to 2, preview only.",
            target_files=["src/app.py"],
            target_symbols=[],
            minimum_context={"src/app.py": original},
            previous_engine_state="tier1_inference_failed",
            environ=_enabled_env(),
            http_call=_mock_http,
        )
        after = hashlib.sha256(target.read_bytes()).hexdigest()

        blocked_calls = {"count": 0}

        def should_not_call(*args, **kwargs):
            blocked_calls["count"] += 1
            raise AssertionError("HTTP should not be called while gates are closed")

        blocked = execute_gemini_task_bridge(
            task_id="task-gemini-bridge-blocked",
            repository_root=str(repo),
            task_summary="blocked",
            target_files=["src/app.py"],
            target_symbols=[],
            minimum_context={"src/app.py": original},
            previous_engine_state="tier1_unavailable",
            environ={},
            http_call=should_not_call,
        )

        checks = {
            "bridge_ok": result.get("ok") is True,
            "engine_selected": result.get("engine_id") == "free_gemini",
            "model_selected": result.get("model_id") == "gemini-3.5-flash",
            "transport_called": result.get("transport_called") is True,
            "patch_step_present": len(result.get("patch_steps", [])) == 1,
            "replace_exact": result.get("patch_steps", [{}])[0].get("change_type") == "replace_exact",
            "hash_precondition": result.get("expected_file_hashes", {}).get("src/app.py") == before,
            "no_file_write": before == after,
            "external_api_recorded": result.get("external_api_used") is True,
            "free_cost_recorded": result.get("provider_cost") == "0.0_free_tier_confirmed",
            "token_usage_recorded": result.get("token_usage", {}).get("total_tokens") == 150,
            "blocked_gate_no_http": blocked.get("transport_called") is False and blocked_calls["count"] == 0,
            "secret_not_returned": "fixture-gemini-key" not in json.dumps(result, default=str),
        }
        return {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
        }


def _run_live() -> dict:
    from luxcode_gemini_task_bridge import execute_gemini_task_bridge

    with tempfile.TemporaryDirectory(prefix="luxcode_gemini_live_") as tmp:
        repo = Path(tmp) / "repo"
        target = repo / "src" / "app.py"
        target.parent.mkdir(parents=True)
        original = "def greet():\n    return 1\n"
        target.write_text(original, encoding="utf-8")
        before = hashlib.sha256(target.read_bytes()).hexdigest()

        result = execute_gemini_task_bridge(
            task_id="task-gemini-bridge-live",
            repository_root=str(repo),
            task_summary=(
                "Preview only: replace the exact greet function so it returns 2. "
                "Do not write files or execute commands."
            ),
            target_files=["src/app.py"],
            target_symbols=[],
            minimum_context={"src/app.py": original},
            previous_engine_state="tier1_inference_failed",
            environ=os.environ,
        )
        after = hashlib.sha256(target.read_bytes()).hexdigest()
        transport = result.get("transport", {})
        if not isinstance(transport, dict):
            transport = {}
        final_transport = transport.get("transport", {})
        if not isinstance(final_transport, dict):
            final_transport = {}
        attempts = transport.get("attempts", [])
        if not isinstance(attempts, list):
            attempts = []
        next_candidate = result.get("handoff", {}).get("next_candidate")
        transient_states = {"provider_busy", "provider_unavailable", "rate_limited"}
        state = str(result.get("state") or "")
        checks = {
            "bridge_ok": result.get("ok") is True,
            "transport_called": result.get("transport_called") is True,
            "model_selected": result.get("model_id") == str(
                os.getenv("LUXCODE_GEMINI_MODEL_ID") or "gemini-3.5-flash"
            ),
            "patch_step_present": bool(result.get("patch_steps")),
            "no_file_write": before == after,
            "external_api_recorded": result.get("external_api_used") is True,
            "fallback_ready": next_candidate == "free_cloud_worker",
        }
        full_success = all(
            checks[key]
            for key in (
                "bridge_ok",
                "transport_called",
                "model_selected",
                "patch_step_present",
                "no_file_write",
                "external_api_recorded",
            )
        )
        safe_transient_fallback = (
            state in transient_states
            and checks["transport_called"]
            and checks["model_selected"]
            and checks["no_file_write"]
            and checks["external_api_recorded"]
            and checks["fallback_ready"]
        )
        status = "PASS" if full_success else "PASS_WITH_FALLBACK" if safe_transient_fallback else "FAIL"
        return {
            "status": status,
            "checks": checks,
            "state": state,
            "http_status": final_transport.get("http_status"),
            "provider_status": final_transport.get("provider_status", ""),
            "provider_message": final_transport.get("error", ""),
            "retry_state": transport.get("retry_state", ""),
            "attempt_count": len(attempts),
            "next_candidate": next_candidate,
            "gate_blockers": result.get("gate", {}).get("blockers", []),
            "error": result.get("error", ""),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    report = _run_live() if args.live else _run_offline()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] in {"PASS", "PASS_WITH_FALLBACK"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
