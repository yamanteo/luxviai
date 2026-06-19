
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


def _model_response(file_path: str, old_text: str, new_text: str) -> dict:
    return {
        "status": "completed",
        "summary": "safe free-model patch preview",
        "completed_scope": ["free_cloud_patch_draft"],
        "remaining_gap": "",
        "patch_operations": [
            {
                "operation_type": "replace_text",
                "file_path": file_path,
                "old_text": old_text,
                "new_text": new_text,
                "expected_occurrences": 1,
                "reason": "fixture safe replacement",
                "confidence": 0.98,
            }
        ],
        "validation_suggestions": ["py_compile"],
        "test_suggestions": ["targeted fixture test"],
        "failure_reason": "",
    }


def _success_http(url, payload, api_key, *, timeout_seconds):
    content = _model_response(
        "fixture.py",
        "def last_index(items):\n    return len(items)\n",
        "def last_index(items):\n    return len(items) - 1\n",
    )
    return {
        "ok": True,
        "status": "success",
        "http_status": 200,
        "response": {
            "choices": [
                {"message": {"content": json.dumps(content, sort_keys=True)}}
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 80,
                "total_tokens": 180,
                "cost": 0,
            },
        },
        "latency_ms": 5,
        "provider_request_id": "fixture-openrouter-request",
    }


def _fallback_http(url, payload, api_key, *, timeout_seconds):
    model = str(payload.get("model") or "")
    if model.endswith("nex-n2-pro:free"):
        return {
            "ok": False,
            "status": "http_error",
            "http_status": 503,
            "failure_category": "provider_unavailable",
            "retryable": True,
            "retry_after_seconds": 1,
            "error": "fixture provider unavailable",
        }
    return _success_http(
        url,
        payload,
        api_key,
        timeout_seconds=timeout_seconds,
    )


def _env() -> dict[str, str]:
    return {
        "OPENROUTER_API_KEY": "sk-or-fixture-not-persisted",
        "LUXCODE_OPENROUTER_ENABLED": "1",
        "LUXCODE_OPENROUTER_TRANSPORT_ENABLED": "1",
        "LUXCODE_OPENROUTER_REAL_REQUESTS": "1",
        "LUXCODE_OPENROUTER_NETWORK_ALLOWED": "1",
        "LUXCODE_OPENROUTER_FREE_TIER_CONFIRMED": "1",
        "LUXCODE_OPENROUTER_MODEL_ACCESS_VERIFIED": "1",
        "LUXCODE_OPENROUTER_QUOTA_STATE": "available",
    }


def offline() -> int:
    from luxcode_free_cloud_task_bridge import (
        FREE_CLOUD_PRIMARY_MODEL_ID,
        build_free_cloud_runtime_configuration,
        execute_free_cloud_task_bridge,
    )

    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="luxcode_free_cloud_bridge_") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        target = repo / "fixture.py"
        original = "def last_index(items):\n    return len(items)\n"
        target.write_text(original, encoding="utf-8")
        before = hashlib.sha256(target.read_bytes()).hexdigest()

        result = execute_free_cloud_task_bridge(
            task_id="task-free-cloud-bridge",
            repository_root=str(repo),
            task_summary="Fix last_index without writing files.",
            target_files=["fixture.py"],
            target_symbols=["last_index"],
            minimum_context={"fixture.py": original},
            previous_engine_state="provider_busy",
            environ=_env(),
            http_call=_success_http,
        )
        after = hashlib.sha256(target.read_bytes()).hexdigest()

        checks.update(
            {
                "bridge_ok": result.get("ok") is True,
                "primary_model_selected": result.get("selected_model")
                == FREE_CLOUD_PRIMARY_MODEL_ID,
                "patch_step_present": bool(result.get("patch_steps")),
                "awaits_approval": result.get("approval_required") is True,
                "no_file_write": before == after,
                "changed_files_empty": target.read_text(encoding="utf-8") == original,
                "external_api_recorded": result.get("external_api_used") is True,
                "reported_cost_zero": float(result.get("reported_cost", 1)) == 0,
                "token_usage_preserved": int(
                    result.get("token_usage", {}).get("total_tokens", 0)
                )
                == 180,
            }
        )

        fallback = execute_free_cloud_task_bridge(
            task_id="task-free-cloud-fallback",
            repository_root=str(repo),
            task_summary="Fix last_index using free fallback.",
            target_files=["fixture.py"],
            target_symbols=["last_index"],
            minimum_context={"fixture.py": original},
            previous_engine_state="provider_busy",
            environ=_env(),
            http_call=_fallback_http,
        )
        fallback_models = [
            str(item.get("model_id") or "")
            for item in fallback.get("model_attempts", [])
        ]
        checks.update(
            {
                "fallback_ok": fallback.get("ok") is True,
                "fallback_used": len(fallback_models) == 2,
                "fallback_model_is_free": bool(fallback_models)
                and all(model.endswith(":free") for model in fallback_models),
                "fallback_no_file_write": hashlib.sha256(
                    target.read_bytes()
                ).hexdigest()
                == before,
            }
        )

        calls = {"count": 0}

        def should_not_call(*args, **kwargs):
            calls["count"] += 1
            return _success_http(*args, **kwargs)

        blocked_env = _env()
        blocked_env["LUXCODE_OPENROUTER_NETWORK_ALLOWED"] = "0"
        blocked = execute_free_cloud_task_bridge(
            task_id="task-free-cloud-blocked",
            repository_root=str(repo),
            task_summary="blocked fixture",
            target_files=["fixture.py"],
            target_symbols=["last_index"],
            minimum_context={"fixture.py": original},
            environ=blocked_env,
            http_call=should_not_call,
        )
        checks.update(
            {
                "closed_gate_blocks": blocked.get("state")
                == "free_cloud_gate_blocked",
                "closed_gate_no_http": calls["count"] == 0,
                "secret_not_persisted": "sk-or-fixture-not-persisted"
                not in json.dumps(result, sort_keys=True),
            }
        )

    source = (ROOT / "luxcode_task_orchestrator.py").read_text(
        encoding="utf-8"
    )
    checks.update(
        {
            "orchestrator_imported": "execute_free_cloud_task_bridge"
            in source,
            "orchestrator_records_engine": '"free_cloud_worker"' in source,
            "free_cloud_before_deterministic": source.find(
                "execute_free_cloud_task_bridge("
            )
            < source.find(
                'task["active_engine"] = "deterministic_local_tools"',
                source.find("def _advance_patch"),
            ),
            "runtime_ready": build_free_cloud_runtime_configuration(
                _env()
            )["gate"]["allowed"]
            is True,
        }
    )

    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def live() -> int:
    from luxcode_free_cloud_task_bridge import (
        execute_free_cloud_task_bridge,
    )

    with tempfile.TemporaryDirectory(prefix="luxcode_free_cloud_live_") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        target = repo / "fixture.py"
        original = "def last_index(items):\n    return len(items)\n"
        target.write_text(original, encoding="utf-8")
        before = hashlib.sha256(target.read_bytes()).hexdigest()

        result = execute_free_cloud_task_bridge(
            task_id="task-free-cloud-live",
            repository_root=str(repo),
            task_summary=(
                "Produce a safe exact replacement preview for the off-by-one "
                "fixture. Do not write files."
            ),
            target_files=["fixture.py"],
            target_symbols=["last_index"],
            minimum_context={"fixture.py": original},
            previous_engine_state="gemini_provider_busy",
            environ=os.environ,
        )
        after = hashlib.sha256(target.read_bytes()).hexdigest()

    state = str(result.get("state") or "")
    transient = state in {
        "provider_unavailable",
        "rate_limited",
        "timeout",
    }
    checks = {
        "gate_open": not result.get("gate", {}).get("blockers"),
        "external_api_recorded": result.get("external_api_used") is True,
        "no_file_write": before == after,
        "reported_cost_zero": float(result.get("reported_cost", 0) or 0)
        == 0,
        "paid_fallback_blocked": result.get("paid_fallback_allowed") is False,
    }
    full_success = (
        result.get("ok") is True
        and bool(result.get("patch_steps"))
        and all(checks.values())
    )
    safe_deferred = (
        transient
        and result.get("external_service_deferred") is True
        and all(checks.values())
    )
    status = (
        "PASS"
        if full_success
        else "PASS_WITH_DEFERRED_RETRY"
        if safe_deferred
        else "FAIL"
    )
    report = {
        "status": status,
        "checks": checks,
        "state": state,
        "selected_model": result.get("selected_model"),
        "model_attempts": result.get("model_attempts", []),
        "external_service_deferred": result.get(
            "external_service_deferred",
            False,
        ),
        "deferred_retry": result.get("deferred_retry", {}),
        "error": result.get("error", ""),
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if status in {"PASS", "PASS_WITH_DEFERRED_RETRY"} else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    raise SystemExit(live() if args.live else offline())
