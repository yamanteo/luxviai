from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_render_execution_gateway import (  # noqa: E402
    AUDIT_EVENTS,
    BLOCKED_STATES,
    CREDENTIAL_STATES,
    FEATURE_FLAGS,
    LIFECYCLE_EVENTS,
    TRANSPORT_TYPES,
    build_gateway_plan_for_fixture,
    build_render_execution_request,
    build_render_gateway_rollback,
    cancel_render_gateway,
    evaluate_render_execution_authority,
    execute_render_gateway,
    execute_render_gateway_rollback,
    get_render_gateway_policy,
    get_render_gateway_registry,
    get_render_gateway_schema,
    get_render_gateway_status,
    poll_render_gateway,
    restore_render_gateway_record,
    verify_render_gateway_url,
)
from luxcode_task_persistence import sanitize_render_gateway_metadata  # noqa: E402


CHECKS = 0


def check(condition: bool, message: str, detail: Any = None) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(f"{message}: {detail!r}")


def make_render_project(service_type: str = "web") -> Path:
    root = Path(tempfile.mkdtemp(prefix="luxrender_gateway_validate_"))
    if service_type == "static":
        service_lines = [
            "services:",
            "  - type: static",
            "    name: lux-static",
            "    buildCommand: python -m py_compile app.py",
            "    staticPublishPath: dist",
        ]
    else:
        service_lines = [
            "services:",
            "  - type: web",
            "    name: lux-web",
            "    runtime: python",
            "    buildCommand: python -m py_compile app.py",
            "    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT",
            "    healthCheckPath: /health",
            "    envVars:",
            "      - key: DATABASE_URL",
            "        sync: false",
        ]
    (root / "render.yaml").write_text("\n".join(service_lines), encoding="utf-8")
    (root / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef h(): return {'ok': True}\n", encoding="utf-8")
    return root


def build_request(root: Path, fixture: str = "success_web_service", transport: str = "fake_render_transport") -> Dict[str, Any]:
    plan_result = build_gateway_plan_for_fixture("gateway-validator", str(root))
    check(plan_result.get("ok") is True, "fixture Render plan builds", plan_result)
    plan = plan_result["plan"]
    authority = evaluate_render_execution_authority(
        plan=plan,
        expected_plan_digest=plan["plan_digest"],
        task_id="gateway-validator",
        selected_service_id=plan["service_candidate_id"],
        deployment_intent=True,
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        transport_type=transport,
        final_confirmation=True,
    )["authority"]
    request = build_render_execution_request(
        plan=plan,
        expected_plan_digest=plan["plan_digest"],
        task_id="gateway-validator",
        selected_service_id=plan["service_candidate_id"],
        transport_type=transport,
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        deployment_intent=True,
        permission_decision=authority,
        final_confirmation=True,
        fake_fixture=fixture,
    )
    check(request.get("ok") is True, "structured gateway request builds", request)
    return request["request"]


def validate_schema_registry_policy() -> None:
    schema = get_render_gateway_schema()
    registry = get_render_gateway_registry()
    policy = get_render_gateway_policy()
    status = get_render_gateway_status()
    check(schema.get("ok") is True, "schema endpoint ok")
    check(registry.get("ok") is True, "registry endpoint ok")
    check(policy.get("ok") is True, "policy endpoint ok")
    check(status.get("default_transport") == "disabled_transport", "default transport disabled", status)
    for transport in ["fake_render_transport", "render_http_transport", "render_cli_transport", "disabled_transport", "unknown_transport"]:
        check(transport in TRANSPORT_TYPES, f"transport registered {transport}")
        check(transport in registry.get("transports", {}), f"transport registry has {transport}")
    check(FEATURE_FLAGS["gateway_enabled"] is True, "gateway enabled by default")
    check(FEATURE_FLAGS["fake_transport_enabled"] is True, "fake transport enabled")
    for flag in ["real_render_execution_enabled", "http_transport_enabled", "cli_transport_enabled", "external_network_enabled", "production_deployment_enabled", "rollback_execution_enabled"]:
        check(FEATURE_FLAGS[flag] is False, f"{flag} disabled")
    check(FEATURE_FLAGS["final_confirmation_required"] is True, "final confirmation required")
    for event in ["deployment_fully_verified", "deployment_cleanup_completed", "deployment_manual_review_required"]:
        check(event in LIFECYCLE_EVENTS, f"lifecycle event {event}")
    for event in ["render_execution_started", "render_url_collected", "render_restore_requires_user_action"]:
        check(event in AUDIT_EVENTS, f"audit event {event}")
    for state in ["reference_available", "resolution_disabled", "verification_required"]:
        check(state in CREDENTIAL_STATES, f"credential state {state}")
    for state in ["blocked_plan_mismatch", "blocked_transport_disabled", "blocked_final_confirmation"]:
        check(state in BLOCKED_STATES, f"blocked state {state}")


def validate_authority_blocks(root: Path) -> Dict[str, Any]:
    plan = build_gateway_plan_for_fixture("authority-validator", str(root))["plan"]
    base = {
        "plan": plan,
        "expected_plan_digest": plan["plan_digest"],
        "task_id": "authority-validator",
        "selected_service_id": plan["service_candidate_id"],
        "deployment_intent": True,
        "credential_reference": {"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        "transport_type": "fake_render_transport",
        "final_confirmation": True,
    }
    scenarios = [
        ("missing intent", {**base, "deployment_intent": False, "plan": {**plan, "deployment_intent": False}}, "blocked_missing_deployment_intent"),
        ("scope mismatch", {**base, "selected_service_id": "wrong-service"}, "blocked_scope_mismatch"),
        ("plan mismatch", {**base, "expected_plan_digest": "wrong"}, "blocked_plan_mismatch"),
        ("missing service", {**base, "plan": {**plan, "service_candidate_id": ""}, "selected_service_id": ""}, "blocked_plan_mismatch"),
        ("permission denied", {**base, "access_mode": "approval_required", "final_confirmation": False}, "blocked_permission_denied"),
        ("credential reference", {**base, "transport_type": "render_http_transport", "credential_reference": {"provider": "render", "availability": "reference_missing"}}, "blocked_credential_reference"),
        ("external network", {**base, "transport_type": "render_http_transport"}, "blocked_external_network"),
        ("transport disabled", {**base, "transport_type": "render_cli_transport"}, "blocked_external_network"),
        ("production disabled", {**base, "production_deployment": True}, "blocked_production_disabled"),
        ("final confirmation", {**base, "final_confirmation": False}, "blocked_final_confirmation"),
        ("full access still blocked real", {**base, "access_mode": "full_access", "transport_type": "render_http_transport"}, "blocked_external_network"),
    ]
    for name, payload, expected in scenarios:
        result = evaluate_render_execution_authority(**payload)
        authority = result.get("authority", {})
        check(authority.get("allowed") is False, f"authority blocks {name}", authority)
        check(authority.get("blocked_state") == expected, f"authority blocked state {name}", authority)
        check(bool(authority.get("next_safe_action")), f"next safe action for {name}", authority)
    allowed = evaluate_render_execution_authority(**base)
    check(allowed.get("authority", {}).get("allowed") is True, "fake transport authority allowed", allowed)
    return plan


def validate_request_contract(plan: Dict[str, Any]) -> Dict[str, Any]:
    authority = evaluate_render_execution_authority(
        plan=plan,
        expected_plan_digest=plan["plan_digest"],
        task_id=plan["task_id"],
        selected_service_id=plan["service_candidate_id"],
        deployment_intent=True,
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        transport_type="fake_render_transport",
        final_confirmation=True,
    )["authority"]
    result = build_render_execution_request(
        plan=plan,
        expected_plan_digest=plan["plan_digest"],
        task_id=plan["task_id"],
        selected_service_id=plan["service_candidate_id"],
        transport_type="fake_render_transport",
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        deployment_intent=True,
        permission_decision=authority,
        final_confirmation=True,
    )
    request = result["request"]
    for key in ["gateway_runtime_id", "task_id", "project_scope_digest", "render_plan_id", "render_plan_digest", "selected_service_id", "transport_type", "credential_reference", "polling_policy", "timeout_policy", "rollback_policy", "cleanup_policy", "evidence_policy"]:
        check(key in request, f"request contains {key}")
    check(request.get("raw_http_body") is None, "no raw HTTP body")
    check(request.get("raw_cli_command") is None, "no raw CLI command")
    check(request.get("arbitrary_url") is None, "no arbitrary URL")
    check(request["retry_budget"] <= 3, "bounded retry")
    check(request["polling_policy"]["max_attempts"] <= 20, "bounded polling")
    check(request["credential_reference"]["redaction_policy"] == "never_log_or_persist_secret_value", "credential redaction policy")
    return request


def validate_fake_transport(root: Path) -> None:
    request = build_request(root)
    result = execute_render_gateway(request)
    runtime = result.get("runtime", {})
    check(result.get("ok") is True, "fake gateway executes", result)
    check(runtime.get("state") == "fake_render_gateway_verified", "fake gateway fully verified", runtime)
    check(runtime.get("simulation") is True, "simulation true")
    check(runtime.get("real_cloud_deployment") is False, "not real deployment")
    check(runtime.get("public_production_url") is False, "not public production URL")
    check(runtime.get("url_metadata", {}).get("trusted") is True, "URL trust true", runtime.get("url_metadata"))
    check(runtime.get("url_metadata", {}).get("url", "").startswith("http://127.0.0.1:"), "localhost URL only", runtime.get("url_metadata"))
    check(runtime.get("health_state") == "deployment_health_verified", "health verified")
    check(runtime.get("browser_state") == "deployment_scenario_verified", "browser scenario verified")
    check("deployment_cleanup_completed" in runtime.get("event_sequence", []), "cleanup event")
    poll = poll_render_gateway(runtime.get("gateway_runtime_id", ""))
    check(poll.get("ok") is True, "poll succeeds")
    check(poll.get("runtime", {}).get("polling", {}).get("terminal_state_detected") is True, "terminal state detected")
    verify = verify_render_gateway_url(runtime.get("gateway_runtime_id", ""))
    check(verify.get("ok") is True, "verify runtime URL succeeds")
    check(verify.get("fully_verified") is True, "verify fully verified")
    arbitrary = verify_render_gateway_url(runtime.get("gateway_runtime_id", ""), "https://example.com")
    check(arbitrary.get("ok") is False, "arbitrary URL blocked")
    cancel = cancel_render_gateway(runtime.get("gateway_runtime_id", ""), task_id=request["task_id"])
    check(cancel.get("ok") is False, "terminal cancel blocked")
    rollback = build_render_gateway_rollback(runtime.get("gateway_runtime_id", ""), explicit_rollback_intent=True, final_confirmation=True)
    check(rollback.get("rollback", {}).get("real_render_rollback_execution_enabled") is False, "real rollback disabled")
    rollback_exec = execute_render_gateway_rollback(rollback.get("rollback", {}))
    check(rollback_exec.get("ok") is False, "rollback execution disabled")


def validate_failure_fixtures(root: Path) -> None:
    for fixture in [
        "build_failure",
        "deployment_failure",
        "deployment_timeout",
        "polling_timeout",
        "malformed_provider_response",
        "missing_deployment_id",
        "missing_url",
        "health_failure",
        "browser_scenario_failure",
        "cancellation",
        "rollback_recommended",
        "transport_cleanup_failure",
    ]:
        request = build_request(root, fixture=fixture)
        result = execute_render_gateway(request)
        runtime = result.get("runtime", {})
        check(result.get("ok") is True, f"fixture returns structured result {fixture}", runtime)
        check(runtime.get("real_cloud_deployment") is False, f"fixture not real {fixture}")
        check(runtime.get("cleanup_state") == "deployment_cleanup_completed", f"fixture cleanup {fixture}")


def validate_real_transport_disabled(root: Path) -> None:
    for transport, expected in [("render_http_transport", "render_http_transport_disabled"), ("render_cli_transport", "render_cli_transport_disabled"), ("disabled_transport", "transport_disabled")]:
        request = build_request(root, transport=transport)
        result = execute_render_gateway(request)
        runtime = result.get("runtime", {})
        check(result.get("ok") is False, f"{transport} blocked", result)
        check(runtime.get("failure_category") in {expected, "transport_disabled", "blocked_external_network"}, f"{transport} disabled category", runtime)
        check(runtime.get("render_api_used") is False, f"{transport} no Render API")
        check(runtime.get("render_cli_used") is False, f"{transport} no Render CLI")


def validate_integration_and_security() -> None:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    coverage_text = (ROOT / "endpoint_coverage_matrix.py").read_text(encoding="utf-8")
    gateway_text = (ROOT / "luxcode_render_execution_gateway.py").read_text(encoding="utf-8")
    orchestrator_text = (ROOT / "luxcode_task_orchestrator.py").read_text(encoding="utf-8")
    persistence_text = (ROOT / "luxcode_task_persistence.py").read_text(encoding="utf-8")
    smoke_text = (ROOT / "scripts" / "smoke_check.py").read_text(encoding="utf-8")
    for route in [
        "/luxcode-render-gateway/schema",
        "/luxcode-render-gateway/registry",
        "/luxcode-render-gateway/policy",
        "/luxcode-render-gateway/authority",
        "/luxcode-render-gateway/request",
        "/luxcode-render-gateway/execute",
        "/luxcode-render-gateway/poll",
        "/luxcode-render-gateway/verify",
        "/luxcode-render-gateway/cancel",
        "/debug/luxcode-render-gateway-status",
    ]:
        check(route in app_text, f"app route {route}")
        check(route in coverage_text, f"coverage route {route}")
    check(coverage_text.count("render_gateway") >= 10, "coverage has gateway records")
    check("luxcode_render_execution_gateway_local" in smoke_text, "targeted smoke registered")
    check("build_render_execution_request" in orchestrator_text, "orchestrator request hook")
    check("execute_render_gateway" in orchestrator_text, "orchestrator execute hook")
    check("sanitize_render_gateway_metadata" in persistence_text, "persistence gateway sanitizer")
    check("execute_render_dry_run" in gateway_text, "gateway delegates fake transport to adapter")
    check("verify_deployment_url" in gateway_text, "gateway delegates URL verification to deployment core")
    forbidden = ["requests.", "urllib.request", "subprocess.run", "os.system", "Render token", "read_dotenv", "load_dotenv", "git add", "Layer 42"]
    for item in forbidden:
        check(item not in gateway_text, f"forbidden token absent: {item}")
    restored = restore_render_gateway_record({"gateway_runtime_id": "x", "token": "secret-token-value"})
    check(restored.get("runtime", {}).get("transport_started") is False, "restore does not start transport")
    check(restored.get("runtime", {}).get("api_cli_called") is False, "restore no API/CLI")
    check(restored.get("runtime", {}).get("url_probe_started") is False, "restore no URL probe")
    safe = sanitize_render_gateway_metadata({"gateway_runtime_id": "x", "raw_provider_response": {"secret": "value"}, "url_metadata": {"url": "http://127.0.0.1:1/?token=abc"}})
    check(safe.get("secrets_persisted") is False, "persistence no secrets")
    check(safe.get("raw_provider_payload_persisted") is False, "persistence no raw provider payload")
    check("?" not in safe.get("gateway_metadata", {}).get("url_metadata", {}).get("url", ""), "URL query token stripped")


def main() -> None:
    root = make_render_project("web")
    static_root = make_render_project("static")
    live_paths = [ROOT / ".luxcode_render_gateway", ROOT / ".luxcode_render", ROOT / ".luxcode_deployment", ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_network_access", ROOT / ".luxcode_browser_launch", ROOT / ".luxcode_snapshots", ROOT / "luxcode_tasks.db", ROOT / "luxcode_backups"]
    before = {str(path): path.exists() for path in live_paths}
    try:
        validate_schema_registry_policy()
        plan = validate_authority_blocks(root)
        validate_request_contract(plan)
        validate_fake_transport(root)
        validate_fake_transport(static_root)
        validate_failure_fixtures(root)
        validate_real_transport_disabled(root)
        validate_integration_and_security()
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(static_root, ignore_errors=True)
    for path in live_paths:
        check(path.exists() is before[str(path)], f"live artifact unchanged {path}")
    print(f"PASS validate_luxcode_render_execution_gateway checks={CHECKS}")


if __name__ == "__main__":
    main()
