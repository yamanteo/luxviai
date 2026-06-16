from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _reason(decision, engine_id):
    for item in decision.get("rejected_candidates", []):
        if item.get("engine_id") == engine_id:
            return str(item.get("reason", ""))
    return ""


def main() -> int:
    from luxcode_first_usable_registry import ENGINE_ORDER, get_unified_engine_registry, select_engine_preview
    from luxcode_free_gemini_worker import (
        DEFAULT_MODEL_ID,
        GEMINI_API_VERSION,
        GEMINI_BASE_URL,
        GeminiGatePolicy,
        build_gemini_evidence,
        build_gemini_restore_policy,
        build_gemini_request_contract,
        choose_gemini_key_reference,
        choose_gemini_api_key,
        engine_order_compatible,
        evaluate_gemini_gates,
        execute_gemini_generate_content,
        execute_free_gemini_handoff,
        normalize_gemini_result_envelope,
        official_gemini_endpoint,
        parse_gemini_fixture_response,
        validate_gemini_endpoint,
        validate_gemini_response,
    )

    checks = []
    registry = get_unified_engine_registry()
    checks.extend(
        [
            registry["free_gemini"]["enabled"] is False,
            registry["free_gemini"]["verified"] is False,
            ENGINE_ORDER.index("free_gemini") < ENGINE_ORDER.index("direct_deepseek"),
            engine_order_compatible() is True,
        ]
    )
    endpoint = official_gemini_endpoint()
    checks.extend(
        [
            endpoint["base_url"] == GEMINI_BASE_URL,
            endpoint["api_version"] == GEMINI_API_VERSION,
            endpoint["method"] == f"models/{DEFAULT_MODEL_ID}:generateContent",
        ]
    )

    enabled_unverified = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "gemini candidate"},
        registry_overrides={"free_gemini": {"enabled": True, "verified": False, "availability": "available"}},
    )
    checks.extend([enabled_unverified["selected_engine"] is None, "engine_unverified" in _reason(enabled_unverified, "free_gemini")])

    gates = [
        evaluate_gemini_gates(GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=False, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard")),
        evaluate_gemini_gates(GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=False, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard")),
        evaluate_gemini_gates(GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=False, key_type="restricted_standard")),
    ]
    checks.extend(
        [
            gates[0]["allowed"] is False and "free_tier_unverified" in gates[0]["blockers"],
            gates[1]["allowed"] is False and "billing_status_unknown" in gates[1]["blockers"],
            gates[2]["allowed"] is False and "auth_key_unconfirmed" in gates[2]["blockers"],
        ]
    )
    safe_gate = evaluate_gemini_gates(
        GeminiGatePolicy(
            enabled=True,
            verified=True,
            transport_enabled=True,
            real_requests_enabled=True,
            network_allowed=True,
            free_tier_confirmed=True,
            billing_disabled_confirmed=True,
            billing_allowed=False,
            quota_state="available",
            quota_available=True,
            model_access_verified=True,
            auth_key_confirmed=True,
            key_type="restricted_standard",
        )
    )
    checks.extend([safe_gate["allowed"] is True, safe_gate["real_http_call_permitted"] is False])
    network_block = evaluate_gemini_gates(
        GeminiGatePolicy(
            enabled=True,
            verified=True,
            transport_enabled=True,
            real_requests_enabled=True,
            network_allowed=False,
            free_tier_confirmed=True,
            billing_disabled_confirmed=True,
            quota_state="available",
            quota_available=True,
            model_access_verified=True,
            auth_key_confirmed=True,
            key_type="restricted_standard",
        )
    )
    checks.extend([network_block["allowed"] is False, "network_disabled" in network_block["blockers"]])

    quota = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "quota exhausted"},
        registry_overrides={
            "free_gemini": {"enabled": True, "verified": True, "availability": "available"},
            "free_32b": {"enabled": True, "verified": True, "availability": "available"},
        },
        provider_health={"free_gemini": "quota_exhausted"},
    )
    checks.extend([quota["selected_engine"] == "free_32b", "health_quota_exhausted" in _reason(quota, "free_gemini")])

    empty = build_gemini_request_contract(
        task_id="task-empty",
        session_id="session-empty",
        task_summary="empty",
        remaining_gap="",
        completed_scope=[],
        target_files=[],
        target_symbols=[],
        minimum_context={},
    )
    full_repo = build_gemini_request_contract(
        task_id="task-full",
        session_id="session-full",
        task_summary="full",
        remaining_gap={"remaining_gap": "x"},
        completed_scope=[],
        target_files=[],
        target_symbols=[],
        minimum_context={"__FULL_REPOSITORY__": "all files"},
    )
    checks.extend([empty["ok"] is False and empty["reason"] == "empty_remaining_gap", full_repo["ok"] is False and full_repo["reason"] == "full_repository_context_rejected"])

    seen: set[str] = set()
    request_result = build_gemini_request_contract(
        task_id="task-gemini",
        session_id="session-gemini",
        task_summary="Patch greet sk-secret-value",
        remaining_gap={"remaining_gap": "replace greet"},
        completed_scope=["tier0_deterministic"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "def greet():\n    return 1\n", ".env": "GEMINI_API_KEY=sk-secret-value"},
        seen_request_digests=seen,
    )
    duplicate = build_gemini_request_contract(
        task_id="task-gemini",
        session_id="session-gemini",
        task_summary="Patch greet sk-secret-value",
        remaining_gap={"remaining_gap": "replace greet"},
        completed_scope=["tier0_deterministic"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "def greet():\n    return 1\n", ".env": "GEMINI_API_KEY=sk-secret-value"},
        seen_request_digests=seen,
    )
    request = request_result["request"]
    checks.extend(
        [
            request_result["ok"] is True,
            duplicate["ok"] is False,
            request["provider_id"] == "google_gemini",
            request["engine_id"] == "free_gemini",
            request["model_id"] == DEFAULT_MODEL_ID,
            request["streaming_enabled"] is False,
            request["tools_enabled"] is False,
            request["file_upload_enabled"] is False,
            request["search_grounding_enabled"] is False,
            request["code_execution_enabled"] is False,
            "completed_scope" not in request,
            "completed_scope_digest" in request,
            ".env" not in request["minimum_context"],
            "sk-secret-value" not in json.dumps(request),
        ]
    )

    raw = json.dumps(
        {
            "status": "completed",
            "analysis_summary": "fixture result",
            "completed_scope": ["free_gemini"],
            "remaining_gap": "",
            "target_files": ["src/app.py"],
            "target_symbols": ["greet"],
            "patch_operations": [{"operation_type": "replace_text", "file_path": "src/app.py", "old_text": "1", "new_text": "2"}],
            "validation_recommendations": ["preview"],
            "assumptions": [],
            "uncertainties": [],
            "risk_flags": [],
        },
        sort_keys=True,
    )
    parsed = parse_gemini_fixture_response(raw)
    validation = validate_gemini_response(parsed, request=request)
    normalized = normalize_gemini_result_envelope(parsed, request=request)
    checks.extend(
        [
            validation["valid"] is True,
            normalized["status"] == "completed",
            normalized["provider_id"] == "google_gemini",
            normalized["validation"]["valid"] is True,
            normalized["result_digest"].startswith("gemini-result-"),
        ]
    )

    partial = normalize_gemini_result_envelope(
        parse_gemini_fixture_response(
            json.dumps(
                {
                    "status": "partial",
                    "analysis_summary": "partial",
                    "completed_scope": ["free_gemini_analysis"],
                    "remaining_gap": "needs patch details",
                    "target_files": ["src/app.py"],
                    "target_symbols": ["greet"],
                    "patch_operations": [],
                    "validation_recommendations": [],
                    "assumptions": [],
                    "uncertainties": [],
                    "risk_flags": [],
                }
            )
        ),
        request=request,
    )
    invalid = normalize_gemini_result_envelope(
        {"status": "completed", "analysis_summary": "bad", "remaining_gap": "still open", "target_files": ["outside.py"], "patch_operations": [], "chain_of_thought": "hidden"},
        request=request,
    )
    checks.extend([partial["status"] == "partial", partial["completed_scope"] == ["free_gemini_analysis"], invalid["status"] == "invalid"])

    evidence = build_gemini_evidence(request=request, gate=safe_gate, result=normalized, stop_reason="fixture_validated")
    checks.extend(
        [
            evidence["engine_id"] == "free_gemini",
            evidence["provider_id"] == "google_gemini",
            evidence["completed"] is True,
            evidence["estimated_cost"] is None,
            "sk-secret-value" not in json.dumps(evidence),
        ]
    )
    key_ref = choose_gemini_key_reference({"GOOGLE_API_KEY_present": True, "GEMINI_API_KEY_present": True, "key_type": "restricted_standard"})
    bad_key_ref = choose_gemini_key_reference({"GEMINI_API_KEY_present": True, "key_type": "unrestricted_standard"})
    key_value = choose_gemini_api_key({"GOOGLE_API_KEY": "google-secret", "GEMINI_API_KEY": "gemini-secret"})
    checks.extend([key_ref["selected_key_name"] == "GOOGLE_API_KEY", key_ref["auth_key_confirmed"] is True, bad_key_ref["auth_key_confirmed"] is False, key_value["selected_key_name"] == "GOOGLE_API_KEY"])

    checks.extend(
        [
            validate_gemini_endpoint(official_gemini_endpoint()["url"])["ok"] is True,
            validate_gemini_endpoint("http://generativelanguage.googleapis.com/v1beta/models/x:generateContent")["ok"] is False,
            validate_gemini_endpoint("https://example.com/v1beta/models/x:generateContent")["ok"] is False,
            validate_gemini_endpoint("https://generativelanguage.googleapis.com/v1beta/models/x:generateContent?key=sk-secret-value")["ok"] is False,
        ]
    )

    def _candidate_payload(status="completed", remaining_gap="", target_files=None):
        return json.dumps(
            {
                "status": status,
                "analysis_summary": "mocked transport result",
                "completed_scope": ["free_gemini"],
                "remaining_gap": remaining_gap,
                "target_files": target_files or ["src/app.py"],
                "target_symbols": ["greet"],
                "patch_operations": [{"operation_type": "replace_text", "file_path": "src/app.py", "old_text": "1", "new_text": "2"}],
                "validation_recommendations": ["preview"],
                "assumptions": [],
                "uncertainties": [],
                "risk_flags": [],
            },
            sort_keys=True,
        )

    def mock_200(url, payload, api_key, *, timeout_seconds):
        return {
            "ok": True,
            "status": "success",
            "response_id": "gemini-mock-200",
            "latency_ms": 7,
            "response": {
                "modelVersion": "gemini-fixture-version",
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": _candidate_payload()}]}}],
                "usageMetadata": {"promptTokenCount": None, "candidatesTokenCount": None},
            },
        }

    transport_200 = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_200)
    checks.extend([transport_200["ok"] is True, transport_200["result"]["status"] == "completed", transport_200["model_version"] == "gemini-fixture-version", transport_200["retry_state"] == "no_retry", "sk-secret-value" not in json.dumps(transport_200)])

    no_key = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key=None, network_allowed=True, http_call=mock_200)
    checks.extend([no_key["status"] == "blocked_by_policy", "api_key_missing" in no_key["gate"]["blockers"]])

    def mock_status(code):
        def inner(url, payload, api_key, *, timeout_seconds):
            return {"ok": False, "status": "http_error", "http_status": code, "retryable": code == 429 or 500 <= code <= 599, "error": "bad sk-secret-value"}
        return inner

    for code in (400, 401, 403):
        item = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_status(code))
        checks.extend([item["ok"] is False, item["retry_state"] == "no_retry_permanent_http_status", "sk-secret-value" not in json.dumps(item)])

    attempts = {"count": 0}

    def mock_429_then_200(url, payload, api_key, *, timeout_seconds):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return {"ok": False, "status": "http_error", "http_status": 429, "retryable": True}
        return mock_200(url, payload, api_key, timeout_seconds=timeout_seconds)

    retry = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_429_then_200)
    checks.extend([retry["ok"] is True, retry["retry_state"] == "bounded_retry_once", attempts["count"] == 2])

    attempts_5xx = {"count": 0}

    def mock_500_then_200(url, payload, api_key, *, timeout_seconds):
        attempts_5xx["count"] += 1
        if attempts_5xx["count"] == 1:
            return {"ok": False, "status": "http_error", "http_status": 500, "retryable": True}
        return mock_200(url, payload, api_key, timeout_seconds=timeout_seconds)

    retry_5xx = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_500_then_200)
    checks.extend([retry_5xx["ok"] is True, retry_5xx["retry_state"] == "bounded_retry_once", attempts_5xx["count"] == 2])

    def mock_timeout(url, payload, api_key, *, timeout_seconds):
        return {"ok": False, "status": "timeout", "retryable": False}

    timeout_result = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_timeout)
    checks.extend([timeout_result["ok"] is False, timeout_result["status"] == "timeout", timeout_result["retry_state"] == "no_retry"])

    def mock_blocked_candidate(url, payload, api_key, *, timeout_seconds):
        return {"ok": True, "status": "success", "response": {"candidates": [{"finishReason": "SAFETY", "content": {"parts": [{"text": "{}"}]}}]}}

    safety = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_blocked_candidate)
    checks.extend([safety["ok"] is False, safety["status"] == "safety_blocked"])

    def mock_missing_candidate(url, payload, api_key, *, timeout_seconds):
        return {"ok": True, "status": "success", "response": {"candidates": []}}

    missing = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_missing_candidate)
    checks.extend([missing["ok"] is False, missing["status"] == "missing_candidate"])

    def mock_large(url, payload, api_key, *, timeout_seconds):
        return {"ok": False, "status": "response_too_large", "retryable": False}

    large = execute_gemini_generate_content(request=request, policy=GeminiGatePolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True, billing_disabled_confirmed=True, quota_state="available", quota_available=True, model_access_verified=True, auth_key_confirmed=True, key_type="restricted_standard"), api_key="sk-secret-value", network_allowed=True, http_call=mock_large)
    checks.extend([large["ok"] is False, large["status"] == "response_too_large"])

    deterministic_request = build_gemini_request_contract(
        task_id="task-gemini",
        session_id="session-gemini",
        task_summary="Patch greet sk-secret-value",
        remaining_gap={"remaining_gap": "replace greet"},
        completed_scope=["tier0_deterministic"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "def greet():\n    return 1\n", ".env": "GEMINI_API_KEY=sk-secret-value"},
    )["request"]
    deterministic_result = normalize_gemini_result_envelope(parsed, request=request)
    checks.extend([deterministic_request["request_digest"] == request["request_digest"], deterministic_result["result_digest"] == normalized["result_digest"]])

    live_policy = GeminiGatePolicy(
        enabled=True,
        verified=True,
        transport_enabled=True,
        real_requests_enabled=True,
        network_allowed=True,
        free_tier_confirmed=True,
        billing_disabled_confirmed=True,
        quota_state="available",
        quota_available=True,
        model_access_verified=True,
        auth_key_confirmed=True,
        key_type="restricted_standard",
    )

    lower_completed = execute_free_gemini_handoff(
        task_id="task-gemini-chain-completed",
        session_id="session-gemini-chain-completed",
        task_summary="already done",
        previous_result={"completed": True, "remaining_gap": ""},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=GeminiGatePolicy(),
    )
    checks.extend([lower_completed["completed"] is True, lower_completed["transport_called"] is False, lower_completed["stop_reason"] == "completed_by_lower_tier"])

    disabled = execute_free_gemini_handoff(
        task_id="task-gemini-disabled",
        session_id="session-gemini-disabled",
        task_summary="disabled",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "needs free model"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=GeminiGatePolicy(enabled=False, verified=False),
        registry_overrides={"free_32b": {"enabled": True, "verified": True, "availability": "available"}},
    )
    checks.extend([disabled["transport_called"] is False, disabled["next_candidate"] == "free_32b"])

    quota_handoff = execute_free_gemini_handoff(
        task_id="task-gemini-quota",
        session_id="session-gemini-quota",
        task_summary="quota",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "quota"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=live_policy,
        provider_health="quota_exhausted",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}, "free_32b": {"enabled": True, "verified": True, "availability": "available"}},
    )
    checks.extend([quota_handoff["transport_called"] is False, quota_handoff["next_candidate"] == "free_32b", "health_quota_exhausted" in quota_handoff["blockers"]])

    auth_fail = execute_free_gemini_handoff(
        task_id="task-gemini-auth",
        session_id="session-gemini-auth",
        task_summary="auth",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "auth"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=live_policy,
        provider_health="authentication_failed",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}, "free_32b": {"enabled": True, "verified": True, "availability": "available"}},
    )
    checks.extend([auth_fail["transport_called"] is False, auth_fail["next_candidate"] == "free_32b", "health_authentication_failed" in auth_fail["blockers"]])

    def mock_completed(url, payload, api_key, *, timeout_seconds):
        return {
            "ok": True,
            "status": "success",
            "response_id": "gemini-chain-completed",
            "latency_ms": 5,
            "response": {
                "modelVersion": "gemini-fixture-version",
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": _candidate_payload()}]}}],
                "usageMetadata": {},
            },
        }

    completed_handoff = execute_free_gemini_handoff(
        task_id="task-gemini-completed",
        session_id="session-gemini-completed",
        task_summary="complete",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "complete"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x", ".env": "GEMINI_API_KEY=sk-secret-value"},
        policy=live_policy,
        api_key="sk-secret-value",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}},
        http_call=mock_completed,
        persist=True,
    )
    checks.extend([completed_handoff["completed"] is True, completed_handoff["transport_called"] is True, completed_handoff["next_candidate"] is None, completed_handoff["persistence"].get("ok") is True, "sk-secret-value" not in json.dumps(completed_handoff)])

    from luxcode_task_persistence import load_task_state

    loaded = load_task_state("task-gemini-completed", mode="memory_only")
    restore_policy = build_gemini_restore_policy(loaded.get("task", {}))
    checks.extend([loaded.get("found") is True, restore_policy["http_auto_restart"] is False, restore_policy["request_auto_resend"] is False, "sk-secret-value" not in json.dumps(loaded)])

    def mock_partial(url, payload, api_key, *, timeout_seconds):
        return {
            "ok": True,
            "status": "success",
            "response_id": "gemini-chain-partial",
            "latency_ms": 5,
            "response": {
                "modelVersion": "gemini-fixture-version",
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": _candidate_payload(status="partial", remaining_gap="needs free_32b", target_files=["src/app.py"])}]}}],
                "usageMetadata": {},
            },
        }

    partial_handoff = execute_free_gemini_handoff(
        task_id="task-gemini-partial",
        session_id="session-gemini-partial",
        task_summary="partial",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "partial"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=live_policy,
        api_key="sk-secret-value",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}, "free_32b": {"enabled": True, "verified": True, "availability": "available"}},
        http_call=mock_partial,
    )
    checks.extend([partial_handoff["completed"] is False, partial_handoff["next_candidate"] == "free_32b", "free_gemini" in partial_handoff["session_state"]["completed_scope"], partial_handoff["session_state"]["remaining_gap"] == "needs free_32b"])

    seen_chain: set[str] = set()
    first = execute_free_gemini_handoff(
        task_id="task-gemini-dup",
        session_id="session-gemini-dup",
        task_summary="dup",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "dup"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=live_policy,
        api_key="sk-secret-value",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}},
        http_call=mock_completed,
        seen_request_digests=seen_chain,
    )
    second = execute_free_gemini_handoff(
        task_id="task-gemini-dup",
        session_id="session-gemini-dup",
        task_summary="dup",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "dup"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=live_policy,
        api_key="sk-secret-value",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}},
        http_call=mock_completed,
        seen_request_digests=seen_chain,
    )
    checks.extend([first["transport_called"] is True, second["transport_called"] is False, second["stop_reason"] == "request_blocked"])

    attempts_chain = {"count": 0}

    def mock_429_chain(url, payload, api_key, *, timeout_seconds):
        attempts_chain["count"] += 1
        if attempts_chain["count"] == 1:
            return {"ok": False, "status": "http_error", "http_status": 429, "retryable": True}
        return mock_completed(url, payload, api_key, timeout_seconds=timeout_seconds)

    retry_handoff = execute_free_gemini_handoff(
        task_id="task-gemini-retry",
        session_id="session-gemini-retry",
        task_summary="retry",
        previous_result={"completed": False, "remaining_gap": {"remaining_gap": "retry"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        target_files=["src/app.py"],
        target_symbols=["greet"],
        minimum_context={"src/app.py": "x"},
        policy=live_policy,
        api_key="sk-secret-value",
        registry_overrides={"free_gemini": {"enabled": True, "verified": True, "availability": "available"}},
        http_call=mock_429_chain,
    )
    checks.extend([retry_handoff["completed"] is True, attempts_chain["count"] == 2, retry_handoff["transport"]["retry_state"] == "bounded_retry_once"])

    deepseek_block = select_engine_preview(
        completed=False,
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        remaining_gap={"remaining_gap": "do not pay yet"},
        registry_overrides={"direct_deepseek": {"enabled": True, "availability": "available"}},
        free_tier_exhaustion_confirmed=False,
        paid_escalation_approved=False,
    )
    checks.extend([deepseek_block["selected_engine"] is None, "free_tiers_not_exhausted" in _reason(deepseek_block, "direct_deepseek")])

    whale_codex = select_engine_preview(completed=False, completed_scope=list(ENGINE_ORDER[:-2]), remaining_gap={"remaining_gap": "manual only"})
    checks.extend([whale_codex["selected_engine"] is None, "manual_request_required" in _reason(whale_codex, "whale"), "emergency_manual_request_required" in _reason(whale_codex, "codex")])

    passed = sum(1 for item in checks if item)
    if passed != len(checks):
        print(f"validation_failed passed={passed} checks={len(checks)}")
        return 1
    print(f"checks={len(checks)}")
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
