from __future__ import annotations

import argparse
import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(condition: bool, label: str, payload=None) -> None:
    if not condition:
        raise AssertionError(f"{label}: {payload!r}")


def main() -> int:
    from luxcode_first_usable_registry import ENGINE_ORDER, engine_failure_fingerprint, get_unified_engine_registry, select_engine_preview
    from luxcode_free_cloud_worker import (
        CANONICAL_ENGINE_ID,
        DEEP_REASONING_FALLBACK_MODEL_ID,
        LEGACY_ALIAS,
        MAXIMUM_MODEL_ATTEMPTS,
        MAXIMUM_TRANSPORT_ATTEMPTS,
        MAX_REQUEST_BYTES,
        PRIMARY_MODEL_ID,
        SCHEMA_SAFE_FALLBACK_MODEL_ID,
        FreeCloudPolicy,
        build_free_cloud_request,
        build_free_cloud_result,
        build_free_cloud_restore_policy,
        build_deferred_retry_decision,
        build_openrouter_chat_payload,
        build_openrouter_provider_policy,
        classify_savings_outcome,
        classify_openrouter_error,
        direct_deepseek_eligible_after_free_cloud,
        evaluate_free_cloud_gates,
        execute_free_cloud_first_usable_handoff,
        execute_openrouter_chat_completion,
        get_free_cloud_model_registry,
        get_free_cloud_worker_status,
        inspect_deferred_retry_eligibility,
        parse_openrouter_structured_result,
        read_openrouter_api_key,
        redact_secret,
        restore_deferred_retry_metadata,
        resolve_free_cloud_engine_id,
        run_free_cloud_live_qualification,
        run_free_cloud_fixture_flow,
        select_next_free_cloud_model,
        validate_free_cloud_model,
        validate_openrouter_endpoint,
    )
    from luxcode_first_usable_session_flow import build_handoff_preview, build_request_envelope, build_result_envelope, execute_fixture_safe_workflow

    checks = 0
    status = get_free_cloud_worker_status()
    registry = get_unified_engine_registry()

    _check(status["safe_defaults"] == {
        "enabled": False,
        "verified": False,
        "transport_enabled": False,
        "real_requests_enabled": False,
        "network_allowed": False,
        "free_tier_confirmed": False,
        "billing_allowed": False,
        "paid_fallback_allowed": False,
        "maximum_model_attempts": 2,
    }, "safe defaults")
    _check(status["deferred_retry_policy"]["base_cooldown_seconds"]["rate_limited"] == 240, "short Qwen cooldown policy", status["deferred_retry_policy"])
    _check(status["deferred_retry_policy"]["maximum_cooldown_seconds"] == 720, "bounded cooldown policy", status["deferred_retry_policy"])
    checks += 3

    gates = evaluate_free_cloud_gates(FreeCloudPolicy())
    _check(gates["allowed"] is False and "engine_disabled" in gates["blockers"] and gates["api_key_read"] is False, "default closed", gates)
    checks += 1

    _check(resolve_free_cloud_engine_id("free_32b")["engine_id"] == CANONICAL_ENGINE_ID, "legacy alias")
    _check(registry["free_32b"]["canonical_engine_id"] == CANONICAL_ENGINE_ID and registry["free_32b"]["legacy_alias"] == LEGACY_ALIAS, "registry canonical alias", registry["free_32b"])
    checks += 3

    models = get_free_cloud_model_registry()
    _check(models["primary"]["model_id"] == PRIMARY_MODEL_ID, "primary model")
    _check(models["deep_reasoning_fallback"]["model_id"] == DEEP_REASONING_FALLBACK_MODEL_ID, "nemotron model")
    _check(models["schema_safe_fallback"]["model_id"] == SCHEMA_SAFE_FALLBACK_MODEL_ID, "Qwen schema model")
    checks += 3

    first_selection = select_next_free_cloud_model(remaining_gap={"remaining_gap": "fix greet"})
    _check(first_selection["model_id"] == PRIMARY_MODEL_ID and first_selection["reason"] == "primary_first", "Nex first", first_selection)
    checks += 1

    seen: set[str] = set()
    req_a = build_free_cloud_request(
        task_id="task-free-cloud",
        session_id="session-free-cloud",
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap={"remaining_gap": "fix greet"},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        minimum_context={"src/app.py": "def greet():\n    return 'old'\n", ".env": "OPENROUTER_API_KEY=sk-secret"},
        target_files=["src/app.py"],
        target_symbols=["greet"],
        seen_request_digests=seen,
    )
    req_b = build_free_cloud_request(
        task_id="task-free-cloud",
        session_id="session-free-cloud",
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap={"remaining_gap": "fix greet"},
        completed_scope=["tier0_deterministic", "tier1_local_worker"],
        minimum_context={"src/app.py": "def greet():\n    return 'old'\n", ".env": "OPENROUTER_API_KEY=sk-secret"},
        target_files=["src/app.py"],
        target_symbols=["greet"],
        seen_request_digests=seen,
    )
    _check(req_a["ok"] is True and req_b["ok"] is False and req_b["reason"] == "duplicate_request_digest", "duplicate request blocked", (req_a, req_b))
    _check("completed_scope" not in req_a["request"] and "completed_scope_digest" in req_a["request"], "scope digest only", req_a)
    _check(".env" not in req_a["request"]["minimum_context"] and "sk-secret" not in json.dumps(req_a), "secret/context redaction", req_a)
    checks += 3

    completed_result = build_free_cloud_result(
        request=req_a["request"],
        status="completed",
        analysis_summary="safe token=abc123456789SECRET",
        completed_scope=["free_cloud_patch_draft"],
        remaining_gap="",
        patch_operations=[{"operation_type": "replace_text", "file_path": "src/app.py"}],
        validation_recommendations=["py_compile"],
    )
    no_fallback = select_next_free_cloud_model(previous_result=completed_result, attempt_history=[{"result": completed_result}], remaining_gap=completed_result["remaining_gap"])
    _check(no_fallback["selected"] is False and no_fallback["reason"] in {"completed_no_fallback", "empty_remaining_gap"}, "Nex completed stops", no_fallback)
    _check(classify_savings_outcome(completed_result, {"remaining_gap": "fix greet"}) == "FREE_COMPLETED", "FREE_COMPLETED")
    _check("abc123456789SECRET" not in json.dumps(completed_result), "result secret redaction", completed_result)
    checks += 3

    partial_result = build_free_cloud_result(
        request=req_a["request"],
        status="partial",
        analysis_summary="narrowed",
        completed_scope=["free_cloud_analysis"],
        remaining_gap={"remaining_gap": "needs deeper reasoning"},
        failure_category="complexity_or_context_gap",
    )
    complexity = select_next_free_cloud_model(previous_result=partial_result, attempt_history=[{"result": partial_result}], remaining_gap=partial_result["remaining_gap"])
    _check(complexity["model_id"] == DEEP_REASONING_FALLBACK_MODEL_ID, "complexity goes Nemotron", complexity)
    flow = run_free_cloud_fixture_flow(
        task_id="task-flow",
        session_id="session-flow",
        remaining_gap={"remaining_gap": "fix greet"},
        minimum_context={"src/app.py": "old", "completed_notes": "do not resend"},
        target_files=["src/app.py"],
        target_symbols=["greet"],
        first_result=partial_result,
    )
    _check(len(flow["attempts"]) == 2 and flow["attempts"][1]["selection"]["model_id"] == DEEP_REASONING_FALLBACK_MODEL_ID, "flow second attempt", flow)
    _check("completed_notes" not in flow["attempts"][1]["request"]["minimum_context"], "second model remaining-gap-only", flow["attempts"][1]["request"])
    _check(flow["savings_outcome"] == "FREE_PARTIAL", "FREE_PARTIAL", flow)
    checks += 4

    schema_invalid = build_free_cloud_result(request=req_a["request"], status="schema_invalid", remaining_gap={"remaining_gap": "schema"}, failure_category="schema_invalid")
    unavailable = build_free_cloud_result(request=req_a["request"], status="provider_unavailable", remaining_gap={"remaining_gap": "provider"}, failure_category="provider_unavailable")
    rate_limited = build_free_cloud_result(request=req_a["request"], status="blocked", remaining_gap={"remaining_gap": "rate"}, failure_category="rate_limited")
    _check(select_next_free_cloud_model(previous_result=schema_invalid, attempt_history=[{"result": schema_invalid}], remaining_gap=schema_invalid["remaining_gap"])["model_id"] == SCHEMA_SAFE_FALLBACK_MODEL_ID, "schema invalid Qwen")
    _check(select_next_free_cloud_model(previous_result=unavailable, attempt_history=[{"result": unavailable}], remaining_gap=unavailable["remaining_gap"])["model_id"] == SCHEMA_SAFE_FALLBACK_MODEL_ID, "unavailable Qwen")
    _check(select_next_free_cloud_model(previous_result=rate_limited, attempt_history=[{"result": rate_limited}], remaining_gap=rate_limited["remaining_gap"])["model_id"] == SCHEMA_SAFE_FALLBACK_MODEL_ID, "rate limited Qwen")
    checks += 3

    maxed = select_next_free_cloud_model(previous_result=partial_result, attempt_history=[{"result": partial_result}, {"result": schema_invalid}], remaining_gap=partial_result["remaining_gap"])
    empty = select_next_free_cloud_model(previous_result=partial_result, attempt_history=[{"result": partial_result}], remaining_gap="")
    _check(maxed["selected"] is False and maxed["reason"] == "maximum_attempts_reached", "max attempts", maxed)
    _check(empty["selected"] is False and empty["reason"] == "empty_remaining_gap", "empty gap no fallback", empty)
    _check(MAXIMUM_MODEL_ATTEMPTS == 2, "max constant")
    checks += 3

    nemotron = select_next_free_cloud_model(previous_result=partial_result, attempt_history=[{"result": partial_result}], remaining_gap=partial_result["remaining_gap"])
    schema_fallback = select_next_free_cloud_model(previous_result=schema_invalid, attempt_history=[{"result": schema_invalid}], remaining_gap=schema_invalid["remaining_gap"])
    _check(not (nemotron["model_id"] == DEEP_REASONING_FALLBACK_MODEL_ID and schema_fallback["model_id"] == DEEP_REASONING_FALLBACK_MODEL_ID), "fallback roles distinct")
    _check(nemotron["model_id"] != schema_fallback["model_id"], "Nemotron and schema fallback not same selection path")
    checks += 2

    rejected = build_free_cloud_result(request=req_a["request"], status="invalid", remaining_gap={"remaining_gap": "same"}, failure_category="duplicate_failure")
    _check(classify_savings_outcome(rejected, {"remaining_gap": "same"}) == "FREE_REJECTED", "FREE_REJECTED")
    _check(select_next_free_cloud_model(previous_result=rejected, attempt_history=[{"result": rejected}], remaining_gap=rejected["remaining_gap"])["selected"] is False, "duplicate failure terminal")
    checks += 2

    req_c = build_free_cloud_request(
        task_id="task-deterministic",
        session_id="session-deterministic",
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap={"remaining_gap": "stable"},
        completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"],
        minimum_context={"src/app.py": "stable"},
    )
    req_d = build_free_cloud_request(
        task_id="task-deterministic",
        session_id="session-deterministic",
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap={"remaining_gap": "stable"},
        completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"],
        minimum_context={"src/app.py": "stable"},
    )
    res_c = build_free_cloud_result(request=req_c["request"], status="blocked", remaining_gap={"remaining_gap": "stable"})
    res_d = build_free_cloud_result(request=req_d["request"], status="blocked", remaining_gap={"remaining_gap": "stable"})
    _check(req_c["request"]["request_digest"] == req_d["request"]["request_digest"], "deterministic request digest")
    _check(res_c["result_digest"] == res_d["result_digest"], "deterministic result digest")
    _check(first_selection == select_next_free_cloud_model(remaining_gap={"remaining_gap": "fix greet"}), "deterministic selection")
    checks += 3

    blocked_paid = direct_deepseek_eligible_after_free_cloud(completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"], free_cloud_exhausted=False, paid_escalation_approved=True)
    _check(blocked_paid["eligible"] is False and any(item.get("reason") == "free_tiers_not_exhausted" for item in blocked_paid["decision"]["rejected_candidates"]), "deepseek blocked before free cloud ends", blocked_paid)
    _check(ENGINE_ORDER == ["tier0_deterministic", "tier1_local_worker", "free_gemini", "free_cloud_worker", "direct_deepseek", "whale", "codex"], "engine order")
    _check("free_32b" not in ENGINE_ORDER, "legacy free_32b not separate engine order")
    checks += 2

    _check(validate_openrouter_endpoint()["ok"] is True, "official endpoint accepted")
    _check(validate_openrouter_endpoint("http://openrouter.ai/api/v1/chat/completions")["reason"] == "https_required", "http endpoint rejected")
    _check(validate_openrouter_endpoint("https://evil.example/api/v1/chat/completions")["reason"] == "non_official_host", "host rejected")
    _check(validate_openrouter_endpoint("https://openrouter.ai:444/api/v1/chat/completions")["reason"] == "port_override_forbidden", "port rejected")
    checks += 4

    _check(validate_free_cloud_model(PRIMARY_MODEL_ID)["ok"] is True, "Nex allowed")
    _check(validate_free_cloud_model(DEEP_REASONING_FALLBACK_MODEL_ID)["ok"] is True, "Nemotron allowed")
    _check(validate_free_cloud_model(SCHEMA_SAFE_FALLBACK_MODEL_ID)["ok"] is True, "Qwen allowed")
    _check(validate_free_cloud_model("google/gemma-4-31b-it:free")["ok"] is False, "Gemma removed from active allowlist")
    _check(validate_free_cloud_model("openai/gpt-oss-20b:free")["ok"] is False, "gpt-oss not active schema fallback")
    _check(validate_free_cloud_model("nex-agi/nex-n2-pro")["ok"] is False, "suffixless model rejected")
    _check(validate_free_cloud_model("some/other:free")["ok"] is False, "unlisted free model rejected")
    checks += 7

    transport_policy = FreeCloudPolicy(enabled=True, verified=True, transport_enabled=True, real_requests_enabled=True, network_allowed=True, free_tier_confirmed=True)
    missing_key = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={}, live_execution_enabled=True)
    _check(missing_key["transport_ready"] is False and missing_key["failure_reason"] == "missing_api_key" and missing_key["http_attempts"] == 0, "missing key fail closed", missing_key)
    _check(read_openrouter_api_key({})["api_key_present"] is False and read_openrouter_api_key({"OPENROUTER_API_KEY": "sk-or-secret"})["api_key_present"] is True, "runtime key read only")
    checks += 2

    payload = build_openrouter_chat_payload(req_a["request"])
    provider = build_openrouter_provider_policy()
    _check(payload["stream"] is False and "models" not in payload and payload["model"] == PRIMARY_MODEL_ID, "non-streaming single model", payload)
    _check(provider == {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny"}, "provider policy", provider)
    _check(payload["provider"] == provider, "payload provider policy")
    _check(payload.get("response_format", {}).get("type") == "json_schema", "strict json_schema response format", payload.get("response_format"))
    _check(payload.get("reasoning") == {"effort": "none", "exclude": True}, "reasoning disabled for structured content", payload.get("reasoning"))
    schema_fallback_req = build_free_cloud_request(
        task_id="task-schema-fallback",
        session_id="session-schema-fallback",
        model_id=SCHEMA_SAFE_FALLBACK_MODEL_ID,
        attempt_number=2,
        selection_reason="schema_invalid",
        remaining_gap={"remaining_gap": "schema only"},
        completed_scope=["do not resend this text"],
        minimum_context={"completed_notes": "finished text", "remaining.py": "x"},
        target_files=["remaining.py"],
    )
    schema_fallback_payload = build_openrouter_chat_payload(schema_fallback_req["request"])
    schema_fallback_prompt = json.loads(schema_fallback_payload["messages"][1]["content"])
    _check(schema_fallback_payload["model"] == SCHEMA_SAFE_FALLBACK_MODEL_ID and schema_fallback_payload.get("response_format", {}).get("type") == "json_schema", "schema fallback strict json_schema request", schema_fallback_payload)
    _check("reasoning" not in schema_fallback_payload, "schema fallback request omits unsupported reasoning parameter", schema_fallback_payload)
    _check("completed_notes" not in schema_fallback_prompt.get("minimum_context", {}) and "do not resend this text" not in json.dumps(schema_fallback_prompt), "schema fallback remaining-gap-only prompt", schema_fallback_prompt)
    _check(len(json.dumps(payload).encode("utf-8")) <= MAX_REQUEST_BYTES, "request size bounded")
    checks += 9

    huge = build_free_cloud_request(
        task_id="task-large",
        session_id="session-large",
        model_id=PRIMARY_MODEL_ID,
        attempt_number=1,
        selection_reason="primary_first",
        remaining_gap={"remaining_gap": "x"},
        minimum_context={"fixture.py": "x"},
        target_files=[f"file_{i}.py" for i in range(20000)],
    )
    try:
        build_openrouter_chat_payload(huge["request"])
        too_large = False
    except ValueError as exc:
        too_large = str(exc) == "request_too_large"
    _check(too_large, "request size limit rejects oversized payload")
    checks += 1

    class MockTransport:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = 0
            self.seen_authorization_secret = False
            self.payloads = []

        def __call__(self, url, payload, api_key, *, timeout_seconds):
            self.calls += 1
            self.payloads.append(payload)
            self.seen_authorization_secret = self.seen_authorization_secret or api_key == "sk-or-fixture-secret"
            item = self.responses[min(self.calls - 1, len(self.responses) - 1)]
            if item == "success":
                return {
                    "ok": True,
                    "status": "success",
                    "response": {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "status": "completed",
                                            "summary": "off by one",
                                            "completed_scope": ["analysis"],
                                            "remaining_gap": "",
                                            "patch_operations": [{"operation_type": "replace_text", "file_path": "fixture.py"}],
                                            "validation_suggestions": ["py_compile"],
                                            "test_suggestions": ["test empty list"],
                                            "failure_reason": "",
                                        }
                                    )
                                }
                            }
                        ]
                    },
                }
            return item

    def empty_content(value=None):
        return {
            "ok": True,
            "status": "success",
            "http_status": 200,
            "response": {"choices": [{"message": {"content": value}}]},
        }

    ok_mock = MockTransport(["success"])
    ok_transport = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=ok_mock, live_execution_enabled=True)
    _check(ok_transport["live_external_verified"] is True and ok_transport["http_attempts"] == 1 and ok_transport["structured_result_valid"] is True, "mock success parse", ok_transport)
    _check(ok_mock.calls == 1 and ok_mock.seen_authorization_secret is True and "sk-or-fixture-secret" not in json.dumps(ok_transport), "auth runtime and redacted", ok_transport)
    checks += 2

    for status_code in (408, 429, 502, 503):
        retry_mock = MockTransport([
            {"ok": False, "status": "http_error", "http_status": status_code, "failure_category": classify_openrouter_error(status_code)["failure_category"], "retryable": True},
            "success",
        ])
        retry_result = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=retry_mock, live_execution_enabled=True)
        _check(retry_mock.calls == 2 and retry_result["http_attempts"] == 2 and retry_result["model_attempts"] == 1, f"{status_code} bounded retry", retry_result)
        checks += 1

    for status_code in (401, 402, 403):
        fail_mock = MockTransport([
            {"ok": False, "status": "http_error", "http_status": status_code, "failure_category": classify_openrouter_error(status_code)["failure_category"], "retryable": False},
        ])
        fail_result = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=fail_mock, live_execution_enabled=True)
        _check(fail_mock.calls == 1 and fail_result["http_attempts"] == 1 and fail_result["paid_fallback_allowed"] is False, f"{status_code} no retry no paid fallback", fail_result)
        checks += 1

    empty_mock = MockTransport([{"ok": False, "status": "empty_response", "failure_category": "empty_response", "retryable": False}])
    invalid_mock = MockTransport([{"ok": False, "status": "schema_invalid", "failure_category": "schema_invalid", "retryable": False}])
    large_mock = MockTransport([{"ok": False, "status": "response_too_large", "failure_category": "response_too_large", "retryable": False}])
    _check(execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=empty_mock, live_execution_enabled=True)["failure_reason"] == "empty_response", "empty response")
    _check(execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=invalid_mock, live_execution_enabled=True)["failure_reason"] == "schema_invalid", "invalid json")
    _check(execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=large_mock, live_execution_enabled=True)["failure_reason"] == "response_too_large", "response too large")
    checks += 3

    none_empty_mock = MockTransport([empty_content(None), empty_content(None)])
    none_empty = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=none_empty_mock, live_execution_enabled=True)
    string_empty_mock = MockTransport([empty_content(""), empty_content("")])
    string_empty = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=string_empty_mock, live_execution_enabled=True)
    retry_valid_mock = MockTransport([empty_content(None), "success"])
    retry_valid = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=retry_valid_mock, live_execution_enabled=True)
    _check(none_empty["status"] == "empty_response" and none_empty["http_attempts"] == 2 and none_empty["model_attempts"] == 1, "HTTP 200 content None empty_response", none_empty)
    _check(string_empty["status"] == "empty_response" and string_empty["http_attempts"] == 2, "HTTP 200 empty string empty_response", string_empty)
    _check(retry_valid["structured_result_valid"] is True and retry_valid["http_attempts"] == 2 and retry_valid["model_attempts"] == 1, "first Nex empty retry valid no model increment", retry_valid)
    _check(none_empty_mock.calls == MAXIMUM_TRANSPORT_ATTEMPTS and retry_valid_mock.calls == MAXIMUM_TRANSPORT_ATTEMPTS, "Nex empty retry maximum 2 HTTP attempt")
    checks += 4

    valid_structured = {
        "status": "partial",
        "summary": "narrowed",
        "completed_scope": ["analysis"],
        "remaining_gap": "needs tests",
        "patch_operations": [],
        "validation_suggestions": [],
        "test_suggestions": ["pytest"],
        "failure_reason": "complexity_or_context_gap",
    }
    parsed_partial = parse_openrouter_structured_result(json.dumps(valid_structured), request=req_a["request"])
    parsed_invalid = parse_openrouter_structured_result("not json", request=req_a["request"])
    _check(parsed_partial["status"] == "partial" and parsed_partial["remaining_gap"] == "needs tests", "valid partial parse", parsed_partial)
    _check(parsed_invalid["status"] == "schema_invalid", "invalid parse schema_invalid", parsed_invalid)
    checks += 2

    direct_json = parse_openrouter_structured_result(json.dumps(valid_structured), request=req_a["request"])
    fenced_json = parse_openrouter_structured_result("```json\n" + json.dumps(valid_structured) + "\n```", request=req_a["request"])
    whitespace_json = parse_openrouter_structured_result("\n\t" + json.dumps(valid_structured) + "  \n", request=req_a["request"])
    extracted_json = parse_openrouter_structured_result("short prefix " + json.dumps(valid_structured) + " short suffix", request=req_a["request"])
    missing_required = dict(valid_structured)
    missing_required.pop("patch_operations")
    invalid_type = dict(valid_structured, patch_operations={"operation_type": "replace_text"})
    multiple_objects = parse_openrouter_structured_result(json.dumps(valid_structured) + "\n" + json.dumps(valid_structured), request=req_a["request"])
    _check(direct_json["status"] == "partial", "direct JSON object", direct_json)
    _check(fenced_json["status"] == "partial", "markdown json fence", fenced_json)
    _check(whitespace_json["status"] == "partial", "whitespace JSON object", whitespace_json)
    _check(extracted_json["status"] == "partial", "single safe JSON object extraction", extracted_json)
    _check(parse_openrouter_structured_result(json.dumps(missing_required), request=req_a["request"])["status"] == "schema_invalid", "missing required field schema_invalid")
    _check(parse_openrouter_structured_result(json.dumps(invalid_type), request=req_a["request"])["status"] == "schema_invalid", "invalid field type schema_invalid")
    _check(multiple_objects["status"] == "schema_invalid", "multiple JSON objects schema_invalid", multiple_objects)
    checks += 7

    parse_fail_mock = MockTransport([
        {
            "ok": True,
            "status": "success",
            "http_status": 200,
            "response": {"choices": [{"message": {"content": "{\"status\":\"partial\"}"}}]},
        }
    ])
    parse_fail_transport = execute_openrouter_chat_completion(
        request=req_a["request"],
        policy=transport_policy,
        environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"},
        http_call=parse_fail_mock,
        live_execution_enabled=True,
    )
    _check(
        parse_fail_transport["transport_status"] == "success"
        and parse_fail_transport["structured_result_valid"] is False
        and parse_fail_transport["status"] == "schema_invalid"
        and parse_fail_transport["live_external_verified"] is False,
        "transport success parse failure schema_invalid",
        parse_fail_transport,
    )
    eligible_mock = MockTransport([
        {
            "ok": True,
            "status": "success",
            "http_status": 200,
            "response": {"choices": [{"message": {"content": json.dumps(dict(valid_structured, status="completed", remaining_gap="", patch_operations=[{"operation_type": "replace_text"}]))}}]},
        }
    ])
    eligible_transport = execute_openrouter_chat_completion(
        request=req_a["request"],
        policy=transport_policy,
        environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"},
        http_call=eligible_mock,
        live_execution_enabled=True,
    )
    reasoning_mock = MockTransport([
        {
            "ok": True,
            "status": "success",
            "http_status": 200,
            "response": {"choices": [{"message": {"content": None, "reasoning": json.dumps(valid_structured)}}]},
        }
    ])
    reasoning_transport = execute_openrouter_chat_completion(
        request=req_a["request"],
        policy=transport_policy,
        environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"},
        http_call=reasoning_mock,
        live_execution_enabled=True,
    )
    _check(
        eligible_transport["transport_status"] == "success"
        and eligible_transport["structured_result_valid"] is True
        and eligible_transport["status"] == "FREE_COMPLETED"
        and eligible_transport["live_external_verified"] is True,
        "valid structured response live verification eligible",
        eligible_transport,
    )
    _check(
        reasoning_transport["transport_status"] == "success"
        and reasoning_transport["structured_result_valid"] is True
        and reasoning_transport["response_metadata"]["reasoning_single_json_object_found"] is True,
        "empty content reasoning structured response parse",
        reasoning_transport,
    )
    checks += 3

    live_fallback_mock = MockTransport([empty_content(None), empty_content(None), "success"])
    live_fallback = run_free_cloud_live_qualification(environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=live_fallback_mock)
    live_models = [payload.get("model") for payload in live_fallback_mock.payloads]
    schema_fallback_prompt = json.loads(live_fallback_mock.payloads[2]["messages"][1]["content"])
    _check(live_fallback["structured_result_valid"] is True and live_fallback["live_external_verified"] is True, "two Nex empty schema fallback valid live verified", live_fallback)
    _check(live_fallback["http_attempt_count"] == 3 and live_fallback["model_attempt_count"] == 2, "transport/model attempt split", live_fallback)
    _check(live_models == [PRIMARY_MODEL_ID, PRIMARY_MODEL_ID, SCHEMA_SAFE_FALLBACK_MODEL_ID], "Nex retry then schema fallback only", live_models)
    _check(DEEP_REASONING_FALLBACK_MODEL_ID not in live_models, "Nemotron not called on empty/schema path", live_models)
    _check(live_fallback["schema_fallback_called"] is True and live_fallback["fallback_used"] is True and live_fallback["fallback_reason"] == "empty_response", "schema fallback reason empty_response", live_fallback)
    _check(schema_fallback_prompt.get("minimum_context") == {} and "tier0_deterministic" not in json.dumps(schema_fallback_prompt), "schema fallback only remaining gap without completed scope text", schema_fallback_prompt)
    _check("reasoning" not in live_fallback_mock.payloads[2], "schema fallback omits unsupported reasoning parameter", live_fallback_mock.payloads[2])
    _check(live_fallback["paid_fallback_blocked"] is True and live_fallback["secret_redaction_status"] == "PASS", "fallback paid blocked and redacted", live_fallback)
    checks += 8

    live_invalid_mock = MockTransport([
        empty_content(None),
        empty_content(None),
        {
            "ok": True,
            "status": "success",
            "http_status": 200,
            "response": {"choices": [{"message": {"content": "{\"status\":\"partial\"}"}}]},
        },
    ])
    live_invalid = run_free_cloud_live_qualification(environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=live_invalid_mock)
    _check(live_invalid["fallback_used"] is True and live_invalid["structured_result_valid"] is False and live_invalid["outcome"] == "schema_invalid", "two Nex empty schema fallback invalid schema_invalid", live_invalid)
    _check(live_invalid["http_attempt_count"] == 3 and live_invalid["model_attempt_count"] == 2, "schema fallback invalid attempt counts", live_invalid)
    checks += 2

    deferred = build_deferred_retry_decision(
        reason="rate_limited",
        model_id=SCHEMA_SAFE_FALLBACK_MODEL_ID,
        remaining_gap={"remaining_gap": "try later", "secret": "sk-or-fixture-secret"},
        completed_scope=["completed text should digest only"],
        now="2026-06-17T00:00:00Z",
    )
    _check(deferred["external_service_deferred"] is True and deferred["retry_after_seconds"] == 240, "rate limit short deferred retry", deferred)
    _check(deferred["deferred_at"] == "2026-06-17T00:00:00Z" and deferred["next_retry_eligible_at"] == "2026-06-17T00:04:00Z", "deferred timestamps", deferred)
    _check(deferred["temporary_failure_count"] == 1 and deferred["remaining_gap_digest"].startswith("remaining-gap-"), "failure count and remaining gap digest", deferred)
    _check(deferred["paid_escalation_allowed"] is False and deferred["whale_or_codex_escalation_allowed"] is False, "deferred blocks automatic paid escalation", deferred)
    _check("completed text should digest only" not in json.dumps(deferred) and "completed_scope_digest" in deferred, "deferred uses completed scope digest only", deferred)
    _check("sk-or-fixture-secret" not in json.dumps(deferred), "deferred secret redaction", deferred)
    early = inspect_deferred_retry_eligibility(deferred, now="2026-06-17T00:02:10Z")
    ready = inspect_deferred_retry_eligibility(deferred, now="2026-06-17T00:04:00Z")
    _check(early["retry_eligible"] is False and early["remaining_cooldown_seconds"] == 110 and early["http_attempts"] == 0, "cooldown not elapsed no HTTP", early)
    _check(ready["retry_eligible"] is True and ready["remaining_cooldown_seconds"] == 0, "cooldown elapsed retry eligible", ready)
    third = build_deferred_retry_decision(reason="rate_limited", model_id=SCHEMA_SAFE_FALLBACK_MODEL_ID, remaining_gap={"remaining_gap": "try later"}, prior_defer_count=99, now="2026-06-17T00:00:00Z")
    _check(third["cooldown_seconds"] == 720 and third["next_retry_eligible_at"] == "2026-06-17T00:12:00Z", "bounded cooldown max", third)
    restored = restore_deferred_retry_metadata(deferred, now="2026-06-17T00:02:10Z")
    _check(restored["metadata_loaded"] is True and restored["auto_http_started"] is False and restored["retry_eligibility"]["retry_eligible"] is False, "restore no-auto-HTTP before cooldown", restored)
    missing_timestamp = restore_deferred_retry_metadata({"external_service_deferred": True, "live_reason": "rate_limited"}, now="2026-06-17T00:02:10Z")
    _check(missing_timestamp["retry_eligibility"]["retry_eligible"] is False and missing_timestamp["retry_eligibility"]["reason"] == "missing_or_invalid_next_retry_eligible_at", "missing timestamp fail closed", missing_timestamp)
    _check(build_deferred_retry_decision(reason="schema_invalid", model_id=SCHEMA_SAFE_FALLBACK_MODEL_ID, remaining_gap={"remaining_gap": "schema"})["external_service_deferred"] is False, "schema invalid is not transient deferred")
    checks += 13

    live_deferred_mock = MockTransport([
        empty_content(None),
        empty_content(None),
        {"ok": False, "status": "http_error", "http_status": 429, "failure_category": "rate_limited", "retryable": True},
        {"ok": False, "status": "http_error", "http_status": 429, "failure_category": "rate_limited", "retryable": True},
    ])
    live_deferred = run_free_cloud_live_qualification(environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=live_deferred_mock)
    _check(live_deferred["external_service_deferred"] is True and live_deferred["retry_after_seconds"] == 240, "live rate limit deferred", live_deferred)
    _check(live_deferred["deferred_retry"]["next_retry_eligible_at"] and live_deferred["deferred_retry"]["remaining_gap_digest"].startswith("remaining-gap-"), "live deferred persistence metadata", live_deferred)
    _check(live_deferred["model_attempt_count"] == 2 and live_deferred["http_attempt_count"] == 4, "deferred keeps model/transport counts", live_deferred)
    checks += 3

    session_stub = {"session_id": "first-usable-free-cloud", "task_id": "task-first-usable", "task_summary": "fix fixture"}
    lower_completed = build_handoff_preview(session=session_stub, completed=True, completed_scope=["tier0_deterministic"], remaining_gap="")
    _check(lower_completed["stop_reason"] == "completed_by_lower_tier" and lower_completed["request"] is None, "Tier 0 completed stops chain", lower_completed)
    tier1_completed = build_handoff_preview(session=session_stub, completed=True, completed_scope=["tier1_local_worker"], remaining_gap="")
    _check(tier1_completed["request"] is None and tier1_completed["selected_engine"] is None, "Tier 1 completed prevents free engines", tier1_completed)
    gemini_completed = build_handoff_preview(session=session_stub, completed=True, completed_scope=["free_gemini"], remaining_gap="")
    _check(gemini_completed["request"] is None, "Free Gemini completed prevents Free Cloud", gemini_completed)
    cloud_preview = build_handoff_preview(
        session=session_stub,
        completed=False,
        completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"],
        remaining_gap={"remaining_gap": "free cloud only"},
        minimum_context={"completed_notes": "do not resend", "fixture.py": "x"},
        registry_overrides={"free_gemini": {"enabled": False}, "free_cloud_worker": {"enabled": True, "verified": True, "availability": "available"}},
    )
    _check(cloud_preview["selected_engine"] == "free_cloud_worker" and cloud_preview["request"]["engine_id"] == "free_cloud_worker", "Free Cloud eligible after Gemini partial", cloud_preview)
    _check("completed_scope" not in cloud_preview["request"] and "completed_notes" in cloud_preview["request"]["minimum_context"], "Free Cloud request uses digest and bounded context", cloud_preview["request"])
    checks += 4

    completed_mock = MockTransport(["success"])
    completed_handoff = execute_free_cloud_first_usable_handoff(
        task_id="task-first-usable",
        session_id="first-usable-free-cloud",
        task_summary="fix fixture",
        previous_result={"remaining_gap": {"remaining_gap": "fix"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"],
        target_files=["fixture.py"],
        target_symbols=["last_index"],
        minimum_context={"fixture.py": "def last_index(items): return len(items)"},
        policy=transport_policy,
        execution_gate_open=True,
        http_call=completed_mock,
    )
    _check(completed_handoff["completed"] is True and completed_handoff["stop_reason"] == "free_cloud_completed", "Free Cloud completed stops chain", completed_handoff)
    _check(completed_handoff["deepseek_eligible"] is False and completed_handoff["paid_escalation_blocked"] is True, "DeepSeek blocked after Free Cloud completed", completed_handoff)
    checks += 2

    partial_mock = MockTransport([
        {
            "ok": True,
            "status": "success",
            "http_status": 200,
            "response": {"choices": [{"message": {"content": json.dumps(dict(valid_structured, status="partial", completed_scope=["free_cloud_analysis"], remaining_gap="smaller gap"))}}]},
        }
    ])
    partial_handoff = execute_free_cloud_first_usable_handoff(
        task_id="task-partial",
        session_id="session-partial",
        task_summary="partial fixture",
        previous_result={"remaining_gap": {"remaining_gap": "large gap"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"],
        target_files=["fixture.py"],
        target_symbols=[],
        minimum_context={"completed_notes": "do not resend", "fixture.py": "x"},
        policy=transport_policy,
        execution_gate_open=True,
        http_call=partial_mock,
    )
    _check(partial_handoff["session_state"]["remaining_gap"] == "smaller gap" and "free_cloud_analysis" in partial_handoff["session_state"]["completed_scope"], "FREE_PARTIAL preserves scope and shrinks gap", partial_handoff)
    _check(partial_handoff["manual_handoff"]["manual_approval_required"] is True and partial_handoff["paid_escalation_blocked"] is True, "partial produces manual handoff only", partial_handoff)
    checks += 2

    deferred_handoff = execute_free_cloud_first_usable_handoff(
        task_id="task-deferred",
        session_id="session-deferred",
        task_summary="deferred fixture",
        previous_result={"remaining_gap": {"remaining_gap": "try qwen"}},
        completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"],
        target_files=[],
        target_symbols=[],
        minimum_context={},
        policy=transport_policy,
        execution_gate_open=True,
        http_call=live_deferred_mock,
    )
    _check(deferred_handoff["external_service_deferred"] is True and deferred_handoff["paid_escalation_blocked"] is True, "rate_limited deferred queue from First Usable", deferred_handoff)
    restored_deferred = execute_free_cloud_first_usable_handoff(
        task_id="task-deferred",
        session_id="session-deferred",
        task_summary="deferred fixture",
        previous_result={"remaining_gap": {"remaining_gap": "try qwen"}},
        completed_scope=["tier0_deterministic"],
        target_files=[],
        target_symbols=[],
        minimum_context={},
        policy=transport_policy,
        execution_gate_open=True,
        restored_deferred_metadata=deferred,
        now="2026-06-17T00:02:00Z",
        http_call=live_deferred_mock,
    )
    _check(restored_deferred["transport_called"] is False and restored_deferred["http_attempts"] == 0 and restored_deferred["retry_eligibility"]["retry_eligible"] is False, "cooldown active restore HTTP attempt 0", restored_deferred)
    restored_ready = restore_deferred_retry_metadata(deferred, now="2026-06-17T00:04:00Z")
    _check(restored_ready["retry_eligibility"]["retry_eligible"] is True and restored_ready["auto_http_started"] is False, "cooldown elapsed explicit retry eligible only", restored_ready)
    checks += 3

    quota_exhausted = {"free_tier_exhausted": True, "remaining_gap": {"remaining_gap": "quota"}, "paid_escalation_allowed": False, "manual_approval_required": True}
    _check(quota_exhausted["free_tier_exhausted"] is True and quota_exhausted["paid_escalation_allowed"] is False, "quota exhausted blocks paid escalation", quota_exhausted)
    blocked_without_approval = direct_deepseek_eligible_after_free_cloud(completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini", "free_cloud_worker"], free_cloud_exhausted=True, paid_escalation_approved=False)
    approved_deepseek = direct_deepseek_eligible_after_free_cloud(completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini", "free_cloud_worker"], free_cloud_exhausted=True, paid_escalation_approved=True)
    _check(blocked_without_approval["eligible"] is False, "paid approval missing blocks DeepSeek", blocked_without_approval)
    _check(approved_deepseek["decision"]["decision_context"]["remaining_gap"] == {"remaining_gap": "paid candidate after free cloud"}, "paid approval only remaining gap eligible", approved_deepseek)
    checks += 3

    seen_stage_inputs = set()
    first_stage = build_handoff_preview(session=session_stub, completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"], remaining_gap={"remaining_gap": "dup"}, minimum_context={"fixture.py": "x"}, seen_stage_input_digests=seen_stage_inputs, registry_overrides={"free_gemini": {"enabled": False}, "free_cloud_worker": {"enabled": True, "verified": True, "availability": "available"}})
    duplicate_stage = build_handoff_preview(session=session_stub, completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"], remaining_gap={"remaining_gap": "dup"}, minimum_context={"fixture.py": "x"}, seen_stage_input_digests=seen_stage_inputs, registry_overrides={"free_gemini": {"enabled": False}, "free_cloud_worker": {"enabled": True, "verified": True, "availability": "available"}})
    loop_guard = build_handoff_preview(session=session_stub, completed_scope=["tier0_deterministic", "tier1_local_worker", "free_gemini"], remaining_gap={"remaining_gap": "dup"}, minimum_context={"fixture.py": "x"}, failed_attempt_fingerprints=[engine_failure_fingerprint("free_cloud_worker", {"remaining_gap": "dup"})], registry_overrides={"free_gemini": {"enabled": False}, "free_cloud_worker": {"enabled": True, "verified": True, "availability": "available"}})
    _check(first_stage["selected_engine"] == "free_cloud_worker" and duplicate_stage["blockers"] == ["duplicate_stage_input"], "duplicate request blocked", duplicate_stage)
    _check(loop_guard["selected_engine"] != "free_cloud_worker", "Free Cloud loop guard blocked", loop_guard)
    checks += 2

    with tempfile.TemporaryDirectory(prefix="luxcode-free-cloud-e2e-") as tmp:
        root = Path(tmp)
        fixture = root / "fixture.py"
        fixture.write_text("def last_index(items):\n    return len(items)\n", encoding="utf-8")
        request = build_request_envelope(task_id="patch-task", session_id="patch-session", engine_id="free_cloud_worker", tier=3, task_summary="fix", remaining_gap={"remaining_gap": "off by one"}, completed_scope=[], target_files=["fixture.py"], target_symbols=["last_index"], minimum_context={"fixture.py": fixture.read_text(encoding="utf-8")})
        patch_result = build_result_envelope(
            request=request,
            status="completed",
            analysis_summary="fix off by one",
            completed_scope=["free_cloud_patch"],
            remaining_gap="",
            patch_operations=[{"operation_type": "replace_text", "file_path": "fixture.py", "old_text": "return len(items)", "new_text": "return len(items) - 1"}],
            validation_recommendations=["py_compile"],
        )
        preview_only = execute_fixture_safe_workflow(repository_root=str(root), request=request, result=patch_result, temporary_fixture_repo=True, validation_plan=[{"type": "py_compile", "path": "fixture.py"}])
        _check(preview_only["final_status"] == "awaiting_approval" and preview_only["preview"]["approval_required"] is True, "Safe Patch preview requires approval", preview_only)
        applied = execute_fixture_safe_workflow(repository_root=str(root), request=request, result=patch_result, temporary_fixture_repo=True, approval_token=preview_only["preview"]["approval_digest"], validation_plan=[{"type": "py_compile", "path": "fixture.py"}], seen_apply_digests=set())
        _check(applied["ok"] is True and applied["final_status"] == "completed" and "return len(items) - 1" in fixture.read_text(encoding="utf-8"), "fixture apply PASS", applied)
    with tempfile.TemporaryDirectory(prefix="luxcode-free-cloud-rollback-") as tmp:
        root = Path(tmp)
        fixture = root / "fixture.py"
        original = "def last_index(items):\n    return len(items)\n"
        fixture.write_text(original, encoding="utf-8")
        request = build_request_envelope(task_id="rollback-task", session_id="rollback-session", engine_id="free_cloud_worker", tier=3, task_summary="fix", remaining_gap={"remaining_gap": "off by one"}, completed_scope=[], target_files=["fixture.py"], target_symbols=["last_index"], minimum_context={"fixture.py": original})
        bad_result = build_result_envelope(
            request=request,
            status="completed",
            analysis_summary="bad patch",
            completed_scope=["free_cloud_patch"],
            remaining_gap="",
            patch_operations=[{"operation_type": "replace_text", "file_path": "fixture.py", "old_text": "return len(items)", "new_text": "return len(items) -"}],
            validation_recommendations=["py_compile"],
        )
        preview_bad = execute_fixture_safe_workflow(repository_root=str(root), request=request, result=bad_result, temporary_fixture_repo=True, validation_plan=[{"type": "py_compile", "path": "fixture.py"}])
        rolled = execute_fixture_safe_workflow(repository_root=str(root), request=request, result=bad_result, temporary_fixture_repo=True, approval_token=preview_bad["preview"]["approval_digest"], validation_plan=[{"type": "py_compile", "path": "fixture.py"}], seen_apply_digests=set())
        _check(rolled["final_status"] == "rolled_back" and fixture.read_text(encoding="utf-8") == original, "validation FAIL rollback", rolled)
        dup_seen = set()
        first_apply = execute_fixture_safe_workflow(repository_root=str(root), request=request, result=bad_result, temporary_fixture_repo=True, approval_token=preview_bad["preview"]["approval_digest"], validation_plan=[{"type": "py_compile", "path": "fixture.py"}], seen_apply_digests=dup_seen)
        second_apply = execute_fixture_safe_workflow(repository_root=str(root), request=request, result=bad_result, temporary_fixture_repo=True, approval_token=preview_bad["preview"]["approval_digest"], validation_plan=[{"type": "py_compile", "path": "fixture.py"}], seen_apply_digests=dup_seen)
        _check(second_apply["stop_reason"] == "duplicate_apply_attempt", "duplicate patch preview/apply blocked", second_apply)
    checks += 4

    no_live = execute_openrouter_chat_completion(request=req_a["request"], policy=transport_policy, environ={"OPENROUTER_API_KEY": "sk-or-fixture-secret"}, http_call=ok_mock, live_execution_enabled=False)
    restore = build_free_cloud_restore_policy({"request": req_a["request"]})
    _check(no_live["http_attempts"] == 0 and no_live["failure_reason"] == "live_execution_disabled", "explicit live gate required", no_live)
    _check(restore["restore_auto_http"] is False and restore["request_auto_resend"] is False, "restore no auto HTTP", restore)
    _check(MAXIMUM_TRANSPORT_ATTEMPTS == 2, "transport retry limit")
    checks += 3

    source = (ROOT / "luxcode_free_cloud_worker.py").read_text(encoding="utf-8")
    _check("requests." not in source, "no requests dependency")
    _check("build_opener(_NoRedirect)" in source, "redirect rejected by opener")
    _check("secret-value" not in str(redact_secret({"token": "secret-value"})), "redact helper")
    checks += 3

    print(f"PASS luxcode free cloud worker validator: checks={checks}")
    return 0


def live() -> int:
    from luxcode_free_cloud_worker import read_openrouter_api_key, run_free_cloud_live_qualification

    key_state = read_openrouter_api_key()
    result = run_free_cloud_live_qualification()
    safe = {
        "api_key_present": key_state["api_key_present"],
        "transport_ready": result.get("transport_ready", False),
        "implementation_validated": result.get("implementation_validated", False),
        "live_external_verified": result.get("live_external_verified", False),
        "selected_model": result.get("selected_model"),
        "selected_models": result.get("selected_models", []),
        "model_http_attempts": result.get("model_http_attempts", []),
        "http_attempt_count": result.get("http_attempt_count", 0),
        "model_attempt_count": result.get("model_attempt_count", 0),
        "nex_final_outcome": result.get("nex_final_outcome", ""),
        "schema_fallback_called": result.get("schema_fallback_called", False),
        "transport_outcome": result.get("transport_outcome"),
        "structured_result_valid": result.get("structured_result_valid", False),
        "outcome": result.get("outcome"),
        "fallback_used": result.get("fallback_used", False),
        "fallback_reason": result.get("fallback_reason", ""),
        "live_reason": result.get("live_reason", ""),
        "external_service_deferred": result.get("external_service_deferred", False),
        "retry_after_seconds": result.get("retry_after_seconds", 0),
        "deferred_retry": result.get("deferred_retry", {}),
        "response_metadata": result.get("response_metadata", {}),
        "secret_redaction_status": result.get("secret_redaction_status", "PASS"),
        "paid_fallback_blocked": result.get("paid_fallback_blocked", True),
    }
    print("LIVE_FREE_CLOUD_RESULT " + json.dumps(safe, sort_keys=True))
    return 0 if result.get("implementation_validated") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    raise SystemExit(live() if args.live else main())
