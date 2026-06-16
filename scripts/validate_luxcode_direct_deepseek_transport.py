from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fixture_response(request) -> str:
    return json.dumps(
        {
            "response_id": "rsp-deepseek-validator-1",
            "request_id": request.request_id,
            "response_status": "completed",
            "analysis_summary": "fixture DeepSeek structured patch response",
            "completed_scope": ["direct_deepseek_fixture"],
            "remaining_gap": "safe_patch_preview_ready",
            "target_files": ["src/app.py"],
            "target_symbols": ["greet"],
            "patch_operations": [
                {
                    "operation_id": "op-deepseek-1",
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "anchor_text": "",
                    "old_text": "def greet():\n    return 1\n",
                    "new_text": "def greet():\n    return 2\n",
                    "expected_occurrences": 1,
                    "reason": "fixture safe patch",
                    "confidence": 0.95,
                }
            ],
            "validation_recommendations": ["preview", "py_compile"],
            "assumptions": [],
            "uncertainties": [],
            "risk_flags": [],
            "scope_violations": [],
            "unsupported_requests": [],
            "usage_metadata": {"input_tokens": 100, "output_tokens": 80, "estimated_cost": 0.0},
        },
        sort_keys=True,
    )


def main() -> int:
    from luxcode_direct_deepseek_transport import (
        DEFAULT_MODEL_ID,
        DeepSeekPricingSnapshot,
        DeepSeekTransportPolicy,
        MAX_LIVE_SMOKE_COST_USD,
        OFFICIAL_ENDPOINT,
        PRICING_SNAPSHOT_VERSION,
        build_deepseek_chat_payload,
        build_deepseek_restore_policy,
        build_deepseek_evidence,
        build_deepseek_remaining_gap,
        build_deepseek_request_from_remaining_gap,
        build_deepseek_safe_patch_contract,
        evaluate_deepseek_gates,
        execute_direct_deepseek_handoff,
        execute_deepseek_chat_completion,
        get_deepseek_pricing_snapshot,
        parse_deepseek_fixture_response,
        preview_deepseek_safe_patch,
        redact_secret,
        validate_deepseek_endpoint,
        validate_deepseek_response,
    )

    checks = []
    with tempfile.TemporaryDirectory(prefix="lux_deepseek_validator_") as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "app.py").write_text("def greet():\n    return 1\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)

        request = build_deepseek_request_from_remaining_gap(
            request_id="req-deepseek-validator-1",
            task_id="task-deepseek-validator-1",
            task_summary="Patch greet return from remaining gap",
            remaining_gap="low_cost_worker_needs_structured_patch",
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            failed_attempt_fingerprints=["fp-old"],
        )
        checks.extend([request.provider_id == "direct_deepseek", request.maximum_cost == 0.0])

        endpoint = validate_deepseek_endpoint(OFFICIAL_ENDPOINT)
        unofficial = validate_deepseek_endpoint("https://example.com/chat/completions?api_key=sk-live")
        checks.extend([endpoint["ok"] is True, unofficial["ok"] is False, "sk-live" not in json.dumps(unofficial)])

        payload = build_deepseek_chat_payload(prompt="Return exactly OK", model_id=DEFAULT_MODEL_ID, max_tokens=8)
        checks.extend([payload["model"] == "deepseek-v4-flash", payload["stream"] is False, payload["thinking"]["type"] == "disabled"])

        known_pricing = get_deepseek_pricing_snapshot(DEFAULT_MODEL_ID)
        pro_pricing = get_deepseek_pricing_snapshot("deepseek-v4-pro")
        unknown_pricing = get_deepseek_pricing_snapshot("deepseek-not-priced")
        live_allowed_policy = DeepSeekTransportPolicy(transport_enabled=True, real_requests_allowed=True, billing_allowed=True, explicit_user_approval=True)
        known_gate = evaluate_deepseek_gates(
            endpoint_url=OFFICIAL_ENDPOINT,
            policy=live_allowed_policy,
            pricing=known_pricing,
            input_tokens=20,
            output_tokens=8,
            hard_cost_cap=MAX_LIVE_SMOKE_COST_USD,
        )
        unknown_gate = evaluate_deepseek_gates(
            endpoint_url=OFFICIAL_ENDPOINT,
            policy=live_allowed_policy,
            pricing=unknown_pricing,
            input_tokens=20,
            output_tokens=8,
            hard_cost_cap=MAX_LIVE_SMOKE_COST_USD,
        )
        checks.extend(
            [
                known_pricing.version == PRICING_SNAPSHOT_VERSION,
                known_pricing.cache_miss_input_per_1m == 0.14,
                pro_pricing.output_per_1m == 0.87,
                known_gate["allowed"] is True,
                unknown_gate["allowed"] is False,
                "unknown_pricing" in unknown_gate["blockers"],
            ]
        )

        blocked_unknown = evaluate_deepseek_gates(
            endpoint_url=OFFICIAL_ENDPOINT,
            policy=DeepSeekTransportPolicy(),
            pricing=DeepSeekPricingSnapshot(model_id="deepseek-chat", input_per_million=None, output_per_million=None),
            input_tokens=100,
            output_tokens=80,
            hard_cost_cap=0.01,
        )
        checks.extend([blocked_unknown["allowed"] is False, "unknown_pricing" in blocked_unknown["blockers"], "billing_disabled" in blocked_unknown["blockers"]])

        response = parse_deepseek_fixture_response(_fixture_response(request), request=request)
        validation = validate_deepseek_response(
            request=request,
            response=response,
            known_files={"src/app.py"},
            known_symbols={"greet"},
            protected_files=set(),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        checks.extend([validation["valid"] is True, validation["status"] == "valid"])

        contract = build_deepseek_safe_patch_contract(
            request=request,
            response=response,
            repository_root=str(repo),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        preview = preview_deepseek_safe_patch(contract)
        checks.extend(
            [
                len(contract.get("operations", [])) == 1,
                preview.get("operation_count") == 1,
                preview.get("files_to_modify") == ["src/app.py"],
                preview.get("approval_required") is True,
                preview.get("apply_allowed") is False,
            ]
        )

        evidence = build_deepseek_evidence(
            request=request,
            response=response,
            patch_contract=contract,
            gate_result=blocked_unknown,
            status="fixture_validated",
            summary="token=sk-secret should be redacted",
        )
        gap = build_deepseek_remaining_gap(request=request, reason="blocked_until_real_transport_approved", evidence=evidence)
        checks.extend(
            [
                evidence["provider_id"] == "direct_deepseek",
                "sk-secret" not in json.dumps(evidence),
                gap["evidence_id"] == evidence["evidence_id"],
            ]
        )

        invalid_json_blocked = False
        try:
            parse_deepseek_fixture_response("{", request=request)
        except ValueError:
            invalid_json_blocked = True
        checks.append(invalid_json_blocked)

        invalid = json.loads(_fixture_response(request))
        invalid["patch_operations"][0]["operation_type"] = "shell_operation"
        invalid_response = parse_deepseek_fixture_response(json.dumps(invalid), request=request)
        invalid_validation = validate_deepseek_response(
            request=request,
            response=invalid_response,
            known_files={"src/app.py"},
            known_symbols={"greet"},
            protected_files=set(),
            file_contents={"src/app.py": "def greet():\n    return 1\n"},
        )
        checks.extend([invalid_validation["valid"] is False, any(item["code"] == "unsupported_operation" for item in invalid_validation["issues"])])
        checks.append(redact_secret({"Authorization": "Bearer sk-test-secret"})["Authorization"] != "Bearer sk-test-secret")

        blocked_call = execute_deepseek_chat_completion(
            prompt="Return exactly OK",
            api_key=None,
            policy=DeepSeekTransportPolicy(),
        )
        checks.extend([blocked_call["status"] == "blocked_by_policy", blocked_call["retry_decision"] == "no_http_call"])

        def mock_200(url, payload, api_key, *, timeout_seconds):
            return {
                "ok": True,
                "status": "success",
                "http_status": 200,
                "provider_request_id": "req-mock-200",
                "latency_ms": 12,
                "response": {
                    "choices": [{"message": {"content": "OK"}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 2},
                },
            }

        mocked_200 = execute_deepseek_chat_completion(
            prompt="Return exactly OK",
            api_key="sk-test-secret",
            policy=live_allowed_policy,
            http_call=mock_200,
        )
        checks.extend(
            [
                mocked_200["ok"] is True,
                mocked_200["content"] == "OK",
                mocked_200["actual_estimated_cost"] is not None,
                mocked_200["actual_estimated_cost"] <= MAX_LIVE_SMOKE_COST_USD,
                "sk-test-secret" not in json.dumps(mocked_200),
            ]
        )

        def mock_400(url, payload, api_key, *, timeout_seconds):
            return {"ok": False, "status": "http_error", "http_status": 400, "retryable": False, "error": "bad request sk-test-secret"}

        mocked_400 = execute_deepseek_chat_completion(
            prompt="Return exactly OK",
            api_key="sk-test-secret",
            policy=live_allowed_policy,
            http_call=mock_400,
        )
        checks.extend(
            [
                mocked_400["ok"] is False,
                mocked_400["retry_decision"] == "no_retry_permanent_http_status",
                "sk-test-secret" not in json.dumps(mocked_400),
            ]
        )

        retry_attempts = {"count": 0}

        def mock_429_then_200(url, payload, api_key, *, timeout_seconds):
            retry_attempts["count"] += 1
            if retry_attempts["count"] == 1:
                return {"ok": False, "status": "http_error", "http_status": 429, "retryable": True}
            return mock_200(url, payload, api_key, timeout_seconds=timeout_seconds)

        mocked_retry = execute_deepseek_chat_completion(
            prompt="Return exactly OK",
            api_key="sk-test-secret",
            policy=live_allowed_policy,
            http_call=mock_429_then_200,
        )
        checks.extend([mocked_retry["ok"] is True, mocked_retry["retry_decision"] == "bounded_retry_once", retry_attempts["count"] == 2])

        timeout_attempts = {"count": 0}

        def mock_timeout(url, payload, api_key, *, timeout_seconds):
            timeout_attempts["count"] += 1
            return {"ok": False, "status": "timeout", "retryable": False}

        mocked_timeout = execute_deepseek_chat_completion(
            prompt="Return exactly OK",
            api_key="sk-test-secret",
            policy=live_allowed_policy,
            http_call=mock_timeout,
        )
        checks.extend([mocked_timeout["ok"] is False, mocked_timeout["status"] == "timeout", mocked_timeout["retry_decision"] == "no_retry", timeout_attempts["count"] == 1])

        def mock_redirect(url, payload, api_key, *, timeout_seconds):
            return {"ok": False, "status": "http_error", "http_status": 302, "retryable": False, "error": "redirect blocked"}

        mocked_redirect = execute_deepseek_chat_completion(
            prompt="Return exactly OK",
            api_key="sk-test-secret",
            policy=live_allowed_policy,
            http_call=mock_redirect,
        )
        checks.extend([mocked_redirect["ok"] is False, mocked_redirect["status"] == "http_error", mocked_redirect["retry_decision"] == "no_retry"])

        lower_completed = execute_direct_deepseek_handoff(
            task_id="task-deepseek-chain-completed",
            task_summary="Already fixed by Tier 1",
            previous_tier="tier1_local_worker",
            previous_result={"completed": True, "remaining_gap": {"remaining_gap": "none"}},
            repository_root=str(repo),
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            free_tier_exhaustion_confirmed=False,
            paid_escalation_approved=False,
            policy=DeepSeekTransportPolicy(),
        )
        checks.extend(
            [
                lower_completed["completed"] is True,
                lower_completed["direct_deepseek_called"] is False,
                lower_completed["stop_reason"] == "completed_by_lower_tier",
            ]
        )

        not_exhausted = execute_direct_deepseek_handoff(
            task_id="task-deepseek-chain-free",
            task_summary="Escalate only if free tiers exhausted",
            previous_tier="tier1_local_worker",
            previous_result={"completed": False, "remaining_gap": {"remaining_gap": "needs paid structured patch"}},
            repository_root=str(repo),
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            free_tier_exhaustion_confirmed=False,
            paid_escalation_approved=True,
            policy=live_allowed_policy,
        )
        checks.extend(
            [
                not_exhausted["direct_deepseek_called"] is False,
                "free_tiers_not_exhausted" in not_exhausted["blockers"],
                "sk-test-secret" not in json.dumps(not_exhausted),
            ]
        )

        no_paid_approval = execute_direct_deepseek_handoff(
            task_id="task-deepseek-chain-paid",
            task_summary="Escalate only if paid approval exists",
            previous_tier="tier1_local_worker",
            previous_result={"completed": False, "remaining_gap": {"remaining_gap": "needs paid structured patch"}},
            repository_root=str(repo),
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            free_tier_exhaustion_confirmed=True,
            paid_escalation_approved=False,
            policy=live_allowed_policy,
        )
        checks.extend(
            [
                no_paid_approval["direct_deepseek_called"] is False,
                "paid_escalation_not_approved" in no_paid_approval["blockers"],
            ]
        )

        def mock_deepseek_structured(url, payload, api_key, *, timeout_seconds):
            prompt_payload = json.loads(payload["messages"][0]["content"])
            request_id = prompt_payload["request_id"]
            content = json.dumps(
                {
                    "response_id": "rsp-deepseek-chain-1",
                    "request_id": request_id,
                    "response_status": "completed",
                    "analysis_summary": "mocked Direct DeepSeek safe patch",
                    "completed_scope": ["direct_deepseek_handoff"],
                    "remaining_gap": "",
                    "target_files": ["src/app.py"],
                    "target_symbols": ["greet"],
                    "patch_operations": [
                        {
                            "operation_id": "op-deepseek-chain-1",
                            "operation_type": "replace_text",
                            "file_path": "src/app.py",
                            "anchor_text": "",
                            "old_text": "def greet():\n    return 1\n",
                            "new_text": "def greet():\n    return 2\n",
                            "expected_occurrences": 1,
                            "reason": "mocked chain preview",
                            "confidence": 0.95,
                        }
                    ],
                    "validation_recommendations": ["preview"],
                    "assumptions": [],
                    "uncertainties": [],
                    "risk_flags": [],
                    "scope_violations": [],
                    "unsupported_requests": [],
                    "usage_metadata": {"input_tokens": 20, "output_tokens": 8, "estimated_cost": 0.0},
                },
                sort_keys=True,
            )
            return {
                "ok": True,
                "status": "success",
                "http_status": 200,
                "provider_request_id": "req-chain-mock",
                "latency_ms": 11,
                "response": {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 20, "completion_tokens": 8}},
            }

        mocked_handoff = execute_direct_deepseek_handoff(
            task_id="task-deepseek-chain-mock",
            task_summary="Escalate after free tier exhaustion",
            previous_tier="free_cloud_tiers",
            previous_result={"completed": False, "remaining_gap": {"remaining_gap": "needs paid structured patch"}},
            repository_root=str(repo),
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            free_tier_exhaustion_confirmed=True,
            paid_escalation_approved=True,
            policy=live_allowed_policy,
            http_call=mock_deepseek_structured,
            persist=True,
            persistence_mode="memory_only",
        )
        checks.extend(
            [
                mocked_handoff["direct_deepseek_called"] is True,
                mocked_handoff["completed"] is True,
                mocked_handoff["validation"]["valid"] is True,
                mocked_handoff["safe_patch_preview"]["operation_count"] == 1,
                mocked_handoff["safe_patch_preview"]["approval_required"] is True,
                mocked_handoff["evidence"]["previous_tier"] == "free_cloud_tiers",
                mocked_handoff["evidence"]["completed"] is True,
                mocked_handoff["persistence"]["ok"] is True,
                "sk-live-placeholder" not in json.dumps(mocked_handoff),
            ]
        )

        def mock_invalid_structured(url, payload, api_key, *, timeout_seconds):
            return {
                "ok": True,
                "status": "success",
                "http_status": 200,
                "provider_request_id": "req-chain-invalid",
                "latency_ms": 9,
                "response": {"choices": [{"message": {"content": "not-json"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 2}},
            }

        invalid_handoff = execute_direct_deepseek_handoff(
            task_id="task-deepseek-chain-invalid",
            task_summary="Invalid response should not complete",
            previous_tier="free_cloud_tiers",
            previous_result={"completed": False, "remaining_gap": {"remaining_gap": "needs paid structured patch"}},
            repository_root=str(repo),
            target_files=["src/app.py"],
            target_symbols=["greet"],
            minimum_context={"src/app.py": "def greet():\n    return 1\n"},
            free_tier_exhaustion_confirmed=True,
            paid_escalation_approved=True,
            policy=live_allowed_policy,
            http_call=mock_invalid_structured,
        )
        checks.extend(
            [
                invalid_handoff["completed"] is False,
                invalid_handoff["stop_reason"] == "validation_failed",
                invalid_handoff["remaining_gap"]["remaining_gap"] == "direct_deepseek_validation_failed",
            ]
        )

        from luxcode_task_persistence import load_task_state

        loaded = load_task_state("task-deepseek-chain-mock", mode="memory_only")
        restore_policy = build_deepseek_restore_policy(loaded.get("task", {}))
        checks.extend(
            [
                loaded["ok"] is True,
                loaded["found"] is True,
                restore_policy["restore_auto_execute"] is False,
                restore_policy["requires_gate_revalidation"] is True,
                restore_policy["paid_call_restarted"] is False,
                "sk-live-placeholder" not in json.dumps(loaded),
            ]
        )

    passed = sum(1 for item in checks if item)
    if passed != len(checks):
        print(f"validation_failed passed={passed} checks={len(checks)}")
        return 1
    print(f"checks={len(checks)}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
