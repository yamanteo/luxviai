from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_render_credential_readiness_broker import (  # noqa: E402
    AUDIT_EVENTS,
    BLOCKER_CATEGORIES,
    CONFIRMATION_STATES,
    MINIMUM_DEPLOYMENT_SCOPE,
    REFERENCE_PROVIDERS,
    REFERENCE_STATES,
    SCOPE_TYPES,
    SEAL_STATES,
    WARNING_CATEGORIES,
    authorize_gateway_execution_with_seal,
    bind_render_final_confirmation,
    build_render_readiness_package,
    evaluate_credential_expiration,
    evaluate_credential_scope,
    evaluate_network_authority,
    get_render_credential_broker_registry,
    get_render_credential_broker_schema,
    get_render_credential_broker_status,
    get_render_readiness_policy,
    issue_render_readiness_seal,
    normalize_credential_reference,
    restore_render_readiness_record,
    validate_credential_reference,
    validate_render_readiness_package,
    validate_render_readiness_seal,
    invalidate_render_readiness_seal,
)
from luxcode_render_execution_gateway import build_render_execution_request, evaluate_render_execution_authority, execute_render_gateway  # noqa: E402
from luxcode_render_provider_adapter import build_render_deployment_plan  # noqa: E402
from luxcode_task_persistence import sanitize_render_readiness_metadata  # noqa: E402


CHECKS = 0


def check(condition: bool, message: str, detail: Any = None) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(f"{message}: {detail!r}")


def iso(hours: int = 0) -> str:
    return (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)).isoformat()


def make_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="luxrender_readiness_validate_"))
    (root / "render.yaml").write_text(
        "\n".join(
            [
                "services:",
                "  - type: web",
                "    name: lux-readiness",
                "    runtime: python",
                "    buildCommand: python -m py_compile app.py",
                "    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT",
                "    healthCheckPath: /health",
            ]
        ),
        encoding="utf-8",
    )
    (root / "app.py").write_text("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef h(): return {'ok': True}\n", encoding="utf-8")
    return root


def credential(service_id: str, environment: str = "preview", scopes: list[str] | None = None) -> Dict[str, Any]:
    return {
        "reference_id": "fixture-render-reference",
        "provider": "fixture_reference",
        "target_service": service_id,
        "environment": environment,
        "scope": scopes or list(MINIMUM_DEPLOYMENT_SCOPE),
        "allowed_operations": scopes or list(MINIMUM_DEPLOYMENT_SCOPE),
        "created_time": iso(-48),
        "issued_time": iso(-48),
        "valid_from": iso(-24),
        "expires_at": iso(48),
        "last_verified_time": iso(-1),
        "status": "reference_available",
        "owner_category": "user_managed",
        "rotation_required": False,
        "resolver_type": "metadata_only_no_secret_resolution",
        "allowed_branch": "main",
        "allowed_deployment_type": "render_deployment",
    }


def network(scope_digest: str) -> Dict[str, Any]:
    return {
        "requested": True,
        "origin": "https://api.render.com",
        "methods": ["GET", "POST"],
        "task_id": "readiness-validator",
        "project_scope_digest": scope_digest,
        "request_budget": 3,
        "expires_at": iso(3),
    }


def fixture_plan(root: Path) -> Dict[str, Any]:
    plan_result = build_render_deployment_plan(
        task_id="readiness-validator",
        repository_root=str(root),
        deployment_intent=True,
        final_confirmation=True,
        credential_reference={"reference_id": "adapter-ref", "availability": "reference_available", "scope": "deploy"},
    )
    check(plan_result.get("ok") is True, "Render plan builds", plan_result)
    return plan_result["plan"]


def scope_digest(plan: Dict[str, Any]) -> str:
    import hashlib
    import json

    return "scope-digest-" + hashlib.sha256(json.dumps([plan.get("project_root"), plan.get("root_directory"), plan.get("service_candidate_id")], sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:24]


def validate_schema_registry_policy() -> None:
    schema = get_render_credential_broker_schema()
    registry = get_render_credential_broker_registry()
    policy = get_render_readiness_policy()
    status = get_render_credential_broker_status()
    check(schema.get("ok") is True, "schema ok")
    check(registry.get("ok") is True, "registry ok")
    check(policy.get("ok") is True, "policy ok")
    check(status.get("credential_reference_only") is True, "broker reference only")
    for provider in ["render_credential_reference", "fixture_reference", "missing_reference"]:
        check(provider in REFERENCE_PROVIDERS, f"provider {provider}")
    for state in ["reference_expired", "reference_ready_for_controlled_execution"]:
        check(state in REFERENCE_STATES, f"reference state {state}")
    for scope in ["create_deployment", "rollback_deployment", "admin"]:
        check(scope in SCOPE_TYPES, f"scope {scope}")
    for category in ["credential_expired", "network_permission_missing", "production_execution_disabled"]:
        check(category in BLOCKER_CATEGORIES, f"blocker {category}")
    for category in ["overprivileged_credential", "fake_transport_only"]:
        check(category in WARNING_CATEGORIES, f"warning {category}")
    for state in ["seal_issued_for_dry_run", "seal_invalidated"]:
        check(state in SEAL_STATES, f"seal state {state}")
    for state in ["confirmation_granted", "confirmation_digest_mismatch"]:
        check(state in CONFIRMATION_STATES, f"confirmation state {state}")
    for event in ["render_credential_reference_received", "render_readiness_seal_issued"]:
        check(event in AUDIT_EVENTS, f"audit event {event}")
    check(policy["policy"]["credential_value_resolution_enabled"] is False, "secret resolution disabled")
    check(policy["policy"]["external_network_enabled"] is False, "external network disabled")
    check(registry["registry"]["real_render_execution_enabled"] is False, "real execution disabled")


def validate_credential_safety(plan: Dict[str, Any]) -> Dict[str, Any]:
    service_id = plan["service_candidate_id"]
    ref = credential(service_id)
    for field in ["token", "api_key", "secret", "password", "authorization", "credential_value", "raw_credential"]:
        blocked = normalize_credential_reference({**ref, field: "do-not-read"}, now=iso())
        check(blocked.get("ok") is False, f"{field} rejected", blocked)
    normalized = normalize_credential_reference(ref, now=iso())
    check(normalized.get("ok") is True, "reference normalizes")
    check("credential_reference_digest" in normalized["reference"], "reference digest")
    valid = validate_credential_reference(ref, selected_service_id=service_id, environment="preview", project_scope_digest=scope_digest(plan), branch="main", now=iso())
    check(valid.get("ok") is True, "reference validation ok", valid)
    check(valid["validation"]["reference_state"] == "reference_ready_for_controlled_execution", "metadata ready state", valid)
    check("do-not-read" not in str(valid), "secret value not returned")
    missing_scope = validate_credential_reference(credential(service_id, scopes=["read_service_metadata"]), selected_service_id=service_id, environment="preview", now=iso())
    check(any(item["category"] == "credential_scope_insufficient" for item in missing_scope["validation"]["blockers"]), "missing scope blocker", missing_scope)
    over = evaluate_credential_scope({**ref, "scope": [*MINIMUM_DEPLOYMENT_SCOPE, "admin"]})
    check(any(item["category"] == "overprivileged_credential" for item in over["scope_decision"]["warnings"]), "overprivileged warning", over)
    env_mismatch = validate_credential_reference(ref, selected_service_id=service_id, environment="production", now=iso())
    check(any(item["category"] == "credential_environment_mismatch" for item in env_mismatch["validation"]["blockers"]), "environment mismatch")
    svc_mismatch = validate_credential_reference(ref, selected_service_id="other", environment="preview", now=iso())
    check(any(item["category"] == "credential_service_mismatch" for item in svc_mismatch["validation"]["blockers"]), "service mismatch")
    provider_mismatch = validate_credential_reference({**ref, "provider": "workspace_reference"}, selected_service_id=service_id, environment="preview", now=iso())
    check(any(item["category"] == "credential_reference_invalid" for item in provider_mismatch["validation"]["blockers"]), "provider mismatch")
    return ref


def validate_expiration(ref: Dict[str, Any]) -> None:
    valid = evaluate_credential_expiration(ref, now=iso())
    check(valid["expiration_decision"]["expiration_state"] == "reference_available", "valid expiration")
    expired = evaluate_credential_expiration({**ref, "expires_at": iso(-1)}, now=iso())
    check(any(item["category"] == "credential_expired" for item in expired["expiration_decision"]["blockers"]), "expired blocked")
    future = evaluate_credential_expiration({**ref, "valid_from": iso(2)}, now=iso())
    check(future["expiration_decision"]["expiration_state"] == "reference_not_yet_valid", "not yet valid")
    soon = evaluate_credential_expiration({**ref, "expires_at": iso(12)}, now=iso())
    check(any(item["category"] == "credential_expires_soon" for item in soon["expiration_decision"]["warnings"]), "expires soon warning")
    rotation = evaluate_credential_expiration({**ref, "rotation_required": True, "rotation_due_date": iso(-1)}, now=iso())
    check(any(item["source"] == "credential_rotation" for item in rotation["expiration_decision"]["blockers"]), "rotation overdue")
    stale = evaluate_credential_expiration({**ref, "last_verified_time": iso(-500)}, now=iso())
    check(any(item["category"] == "credential_verification_stale" for item in stale["expiration_decision"]["warnings"]), "stale verification")


def validate_network(scope: str) -> Dict[str, Any]:
    ok = evaluate_network_authority(network(scope), task_id="readiness-validator", project_scope_digest=scope, now=iso())
    check(ok["network_decision"]["network_state"] == "network_ready_for_controlled_execution", "network metadata ready")
    check(ok["network_decision"]["real_network_request_performed"] is False, "no real network")
    missing = evaluate_network_authority({}, project_scope_digest=scope, now=iso())
    check(any(item["category"] == "network_permission_missing" for item in missing["network_decision"]["blockers"]), "network missing")
    wrong_origin = evaluate_network_authority({**network(scope), "origin": "https://example.com"}, project_scope_digest=scope, now=iso())
    check(wrong_origin["network_decision"]["network_state"] == "network_origin_not_allowed", "wrong origin")
    wrong_method = evaluate_network_authority({**network(scope), "methods": ["DELETE"]}, project_scope_digest=scope, now=iso())
    check(wrong_method["network_decision"]["network_state"] == "network_method_not_allowed", "wrong method")
    wrong_scope = evaluate_network_authority({**network(scope), "project_scope_digest": "bad"}, project_scope_digest=scope, now=iso())
    check(wrong_scope["network_decision"]["network_state"] == "network_scope_mismatch", "scope mismatch")
    expired = evaluate_network_authority({**network(scope), "expires_at": iso(-1)}, project_scope_digest=scope, now=iso())
    check(expired["network_decision"]["network_state"] == "network_duration_expired", "network expired")
    budget = evaluate_network_authority({**network(scope), "request_budget": 0}, project_scope_digest=scope, now=iso())
    check(budget["network_decision"]["network_state"] == "network_budget_exceeded", "network budget")
    return ok["network_decision"]


def validate_package_seal_confirmation(plan: Dict[str, Any], ref: Dict[str, Any], net: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    package_result = build_render_readiness_package(
        plan=plan,
        credential_reference=ref,
        network_authority=network(scope_digest(plan)),
        task_id="readiness-validator",
        environment="preview",
        branch="main",
        commit_metadata={"commit": "fixture"},
        deployment_intent=True,
        final_confirmation_state="confirmation_granted",
        now=iso(),
    )
    package = package_result["readiness_package"]
    check(package_result.get("ok") is True, "package builds")
    check(package["package_digest"].startswith("render-readiness-package-"), "package digest")
    check(package["render_plan_digest"] == plan["plan_digest"], "plan digest binding")
    check(package["gateway_policy_digest"].startswith("render-gateway-policy-"), "gateway policy digest")
    check(package["selected_service_id"] == plan["service_candidate_id"], "service binding")
    check(package["branch"] == "main", "branch binding")
    check(any(item["category"] == "production_execution_disabled" for item in package["blocker_list"]), "production disabled blocker")
    check(any(item["category"] == "fake_transport_only" for item in package["warning_list"]), "fake transport warning")
    check(validate_render_readiness_package(package, now=iso()).get("valid") is True, "package validates")
    dry_seal = issue_render_readiness_seal(package, requested_level="dry_run", now=iso())
    seal = dry_seal["seal"]
    check(seal["seal_status"] == "seal_issued_for_dry_run", "dry-run seal")
    controlled = issue_render_readiness_seal(package, requested_level="controlled_execution", now=iso())
    check(controlled["seal"]["seal_status"] == "seal_issued_for_controlled_execution", "controlled metadata seal")
    check(controlled["seal"]["real_execution_feature_enabled"] is False, "seal cannot enable real execution")
    check(validate_render_readiness_seal(seal, package, now=iso()).get("valid") is True, "seal validates")
    changed_package = {**package, "branch": "feature"}
    invalid = validate_render_readiness_seal(seal, changed_package, now=iso())
    check(invalid.get("valid") is False, "package change invalidates")
    invalidated = invalidate_render_readiness_seal(seal, package, changed_fields=["credential_reference_changed"], now=iso())
    check("credential_reference_changed" in invalidated["seal"]["invalidation_reasons"], "explicit invalidation reason")
    confirmation = bind_render_final_confirmation(package, {"granted": True, "package_digest": package["package_digest"], "environment": "preview", "expires_at": iso(1)}, now=iso())
    check(confirmation["confirmation"]["confirmation_state"] == "confirmation_granted", "confirmation bound")
    mismatch = bind_render_final_confirmation(package, {"granted": True, "package_digest": "bad", "expires_at": iso(1)}, now=iso())
    check(mismatch["confirmation"]["confirmation_state"] == "confirmation_digest_mismatch", "confirmation digest mismatch")
    expired = bind_render_final_confirmation(package, {"granted": True, "package_digest": package["package_digest"], "expires_at": iso(-1)}, now=iso())
    check(expired["confirmation"]["confirmation_state"] == "confirmation_expired", "confirmation expired")
    revoked = bind_render_final_confirmation(package, {"granted": True, "revoked": True, "package_digest": package["package_digest"]}, now=iso())
    check(revoked["confirmation"]["confirmation_state"] == "confirmation_revoked", "confirmation revoked")
    return package, seal


def validate_gateway_and_restore(plan: Dict[str, Any], ref: Dict[str, Any], package: Dict[str, Any], seal: Dict[str, Any]) -> None:
    authority = evaluate_render_execution_authority(
        plan=plan,
        expected_plan_digest=plan["plan_digest"],
        task_id="readiness-validator",
        selected_service_id=plan["service_candidate_id"],
        deployment_intent=True,
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        transport_type="fake_render_transport",
        final_confirmation=True,
    )["authority"]
    request = build_render_execution_request(
        plan=plan,
        expected_plan_digest=plan["plan_digest"],
        task_id="readiness-validator",
        selected_service_id=plan["service_candidate_id"],
        transport_type="fake_render_transport",
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "environment": "fixture"},
        deployment_intent=True,
        permission_decision=authority,
        final_confirmation=True,
        readiness_package=package,
        readiness_seal=seal,
        production_readiness_required=True,
        readiness_validation_time=iso(),
    )["request"]
    allowed = authorize_gateway_execution_with_seal(request, package, seal, "fake_render_transport", now=iso())
    check(allowed.get("allowed") is True, "fake gateway accepts dry-run seal", allowed)
    executed = execute_render_gateway(request)
    check(executed.get("ok") is True, "fake gateway executes with seal", executed)
    no_seal = {**request, "readiness_seal": {}}
    blocked = execute_render_gateway(no_seal)
    check(blocked.get("ok") is False, "no seal blocks required execution")
    real = authorize_gateway_execution_with_seal(request, package, seal, "render_http_transport")
    check(real.get("ok") is False, "real transport remains blocked")
    full_access = {**request, "transport_type": "render_http_transport"}
    full_block = execute_render_gateway(full_access)
    check(full_block.get("ok") is False, "full access cannot bypass seal/real flags")
    safe = sanitize_render_readiness_metadata(package, seal)
    check(safe["secrets_persisted"] is False, "safe metadata no secrets")
    check(safe["raw_provider_payload_persisted"] is False, "safe metadata no raw payload")
    restored = restore_render_readiness_record({"token": "blocked", "readiness_package_id": package["readiness_package_id"]})
    check(restored["runtime"]["credential_resolved"] is False, "restore no credential resolution")
    check(restored["runtime"]["seal_created"] is False, "restore no seal")
    check(restored["runtime"]["network_permission_opened"] is False, "restore no network permission")
    check(restored["runtime"]["execution_started"] is False, "restore no execution")


def validate_app_coverage_security() -> None:
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    coverage_text = (ROOT / "endpoint_coverage_matrix.py").read_text(encoding="utf-8")
    broker_text = (ROOT / "luxcode_render_credential_readiness_broker.py").read_text(encoding="utf-8")
    persistence_text = (ROOT / "luxcode_task_persistence.py").read_text(encoding="utf-8")
    orchestrator_text = (ROOT / "luxcode_task_orchestrator.py").read_text(encoding="utf-8")
    smoke_text = (ROOT / "scripts" / "smoke_check.py").read_text(encoding="utf-8")
    routes = [
        "/luxcode-render-readiness/schema",
        "/luxcode-render-readiness/registry",
        "/luxcode-render-readiness/policy",
        "/luxcode-render-readiness/credential",
        "/luxcode-render-readiness/network",
        "/luxcode-render-readiness/package",
        "/luxcode-render-readiness/seal",
        "/luxcode-render-readiness/validate",
        "/luxcode-render-readiness/invalidate",
        "/debug/luxcode-render-readiness-status",
    ]
    for route in routes:
        check(route in app_text, f"app route {route}")
        check(route in coverage_text, f"coverage route {route}")
    check(coverage_text.count("render_readiness") >= 10, "coverage records present")
    check("luxcode_render_credential_readiness_local" in smoke_text, "targeted smoke registered")
    check("plan_luxcode_task_render_readiness" in orchestrator_text, "orchestrator readiness fields")
    check("sanitize_render_readiness_metadata" in persistence_text, "persistence readiness sanitizer")
    for forbidden in ["requests.", "urllib.request", "subprocess.run", "os.system", "load_dotenv", "read_dotenv", "import keyring", "keyring.", "win32cred", "CredentialManager", "Layer 42"]:
        check(forbidden not in broker_text, f"forbidden token absent {forbidden}")


def main() -> None:
    root = make_project()
    live_paths = [ROOT / ".luxcode_render_credentials", ROOT / ".luxcode_render_readiness", ROOT / ".luxcode_render_gateway", ROOT / ".luxcode_render", ROOT / ".luxcode_deployment", ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_network_access", ROOT / ".luxcode_browser_launch", ROOT / ".luxcode_snapshots", ROOT / "luxcode_tasks.db", ROOT / "luxcode_backups"]
    before = {str(path): path.exists() for path in live_paths}
    try:
        validate_schema_registry_policy()
        plan = fixture_plan(root)
        ref = validate_credential_safety(plan)
        validate_expiration(ref)
        net = validate_network(scope_digest(plan))
        package, seal = validate_package_seal_confirmation(plan, ref, net)
        validate_gateway_and_restore(plan, ref, package, seal)
        validate_app_coverage_security()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for path in live_paths:
        check(path.exists() is before[str(path)], f"live artifact unchanged {path}")
    print(f"PASS validate_luxcode_render_credential_readiness checks={CHECKS}")


if __name__ == "__main__":
    main()
