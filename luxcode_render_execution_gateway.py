from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from luxcode_deployment_execution_url_verification import verify_deployment_url
from luxcode_render_provider_adapter import (
    build_render_deployment_plan,
    execute_render_dry_run,
    validate_render_deployment_plan,
)


SAFE_INVARIANTS = {
    "external_api_used": False,
    "external_network_used": False,
    "public_internet_used": False,
    "render_api_used": False,
    "render_cli_used": False,
    "render_login_used": False,
    "render_token_read": False,
    "secret_values_read": False,
    "dotenv_read": False,
    "cloud_deployment_used": False,
    "package_installation_used": False,
    "layer42_started": False,
    "local_first": True,
}

TRANSPORT_TYPES = [
    "fake_render_transport",
    "render_http_transport",
    "render_cli_transport",
    "disabled_transport",
    "unknown_transport",
]

FEATURE_FLAGS = {
    "gateway_enabled": True,
    "fake_transport_enabled": True,
    "real_render_execution_enabled": False,
    "http_transport_enabled": False,
    "cli_transport_enabled": False,
    "external_network_enabled": False,
    "credential_resolution_enabled": False,
    "production_deployment_enabled": False,
    "rollback_execution_enabled": False,
    "url_verification_enabled": True,
    "final_confirmation_required": True,
}

LIFECYCLE_EVENTS = [
    "gateway_created",
    "gateway_authority_checking",
    "gateway_authority_blocked",
    "gateway_ready",
    "transport_selected",
    "transport_disabled",
    "deployment_request_prepared",
    "deployment_started",
    "deployment_queued",
    "deployment_building",
    "deployment_uploading",
    "deployment_live",
    "deployment_failed",
    "deployment_cancel_requested",
    "deployment_cancelled",
    "deployment_timed_out",
    "deployment_url_received",
    "deployment_health_checking",
    "deployment_health_verified",
    "deployment_health_failed",
    "deployment_scenario_verifying",
    "deployment_scenario_verified",
    "deployment_scenario_failed",
    "deployment_fully_verified",
    "deployment_partially_verified",
    "deployment_rollback_recommended",
    "deployment_rollback_started",
    "deployment_rollback_completed",
    "deployment_cleanup_started",
    "deployment_cleanup_completed",
    "deployment_manual_review_required",
]

AUDIT_EVENTS = [
    "render_gateway_created",
    "render_gateway_authority_checked",
    "render_gateway_blocked",
    "render_transport_selected",
    "render_transport_disabled",
    "render_execution_request_created",
    "render_execution_request_validated",
    "render_execution_started",
    "render_execution_polled",
    "render_execution_event_received",
    "render_execution_completed",
    "render_execution_failed",
    "render_url_collected",
    "render_url_trust_checked",
    "render_health_verified",
    "render_scenario_verified",
    "render_cancel_requested",
    "render_cancelled",
    "render_rollback_recommended",
    "render_cleanup_completed",
    "render_restore_requires_user_action",
]

BLOCKED_STATES = [
    "blocked_missing_deployment_intent",
    "blocked_scope_mismatch",
    "blocked_plan_mismatch",
    "blocked_service_not_selected",
    "blocked_permission_denied",
    "blocked_credential_reference",
    "blocked_external_network",
    "blocked_transport_disabled",
    "blocked_production_disabled",
    "blocked_final_confirmation",
    "blocked_rollback_unavailable",
    "blocked_irreversible_operation",
]

CREDENTIAL_STATES = [
    "reference_available",
    "reference_missing",
    "reference_expired",
    "scope_insufficient",
    "resolution_disabled",
    "manual_setup_required",
    "verification_required",
]

FAILURE_FIXTURES = {
    "success_web_service": "success",
    "success_static_site": "success",
    "build_failure": "build_failure",
    "deployment_failure": "deployment_failure",
    "deployment_timeout": "timeout",
    "polling_timeout": "timeout",
    "malformed_provider_response": "deployment_failure",
    "missing_deployment_id": "deployment_failure",
    "missing_url": "url_missing",
    "health_failure": "health_failure",
    "browser_scenario_failure": "scenario_failure",
    "cancellation": "cancel",
    "rollback_recommended": "deployment_failure",
    "transport_cleanup_failure": "deployment_failure",
}

_RUNTIMES: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "render-gateway-") -> str:
    return prefix + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:24]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, **SAFE_INVARIANTS}


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "error": message, **extra, **SAFE_INVARIANTS}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if isinstance(item, bool):
                clean[str(key)] = item
            elif any(marker in lowered for marker in ("token", "secret", "password", "authorization", "cookie", "api_key", "private_key")):
                clean[str(key)] = "[redacted]"
            else:
                clean[str(key)] = _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and ("Bearer " in value or "sk-" in value):
        return "[redacted]"
    return value


def _audit(target: Dict[str, Any], event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    if event_type not in AUDIT_EVENTS:
        event_type = "render_execution_event_received"
    target.setdefault("audit_events", []).append({"event_type": event_type, "created_at": _now(), "payload": _redact(payload or {})})


def _next_safe_action(blocked_state: str) -> str:
    return {
        "blocked_missing_deployment_intent": "Provide explicit deployment intent before preparing execution.",
        "blocked_scope_mismatch": "Rebuild the Render plan for the selected project scope.",
        "blocked_plan_mismatch": "Use the immutable Render plan digest produced by the adapter.",
        "blocked_service_not_selected": "Select one Render service candidate before execution.",
        "blocked_permission_denied": "Request approval for the current access mode and operation.",
        "blocked_credential_reference": "Configure a Render credential reference; do not provide secret values.",
        "blocked_external_network": "Keep real Render execution disabled or grant external network policy locally.",
        "blocked_transport_disabled": "Use fake_render_transport for local verification; real transports are disabled.",
        "blocked_production_disabled": "Enable production deployment only through trusted local policy.",
        "blocked_final_confirmation": "Provide final confirmation for this exact plan digest.",
        "blocked_rollback_unavailable": "Prepare a rollback plan or keep execution in dry-run mode.",
        "blocked_irreversible_operation": "Remove irreversible operations from the request.",
    }.get(blocked_state, "Stop and request manual review.")


def get_render_gateway_policy() -> Dict[str, Any]:
    return _safe_success(
        policy={
            "feature_flags": deepcopy(FEATURE_FLAGS),
            "default_transport": "disabled_transport",
            "request_body_cannot_enable_real_execution": True,
            "dotenv_read": False,
            "real_render_requires": [
                "trusted_local_policy",
                "credential_reference",
                "external_network_policy",
                "production_enablement",
                "final_confirmation",
                "rollback_plan",
            ],
        }
    )


def get_render_gateway_schema() -> Dict[str, Any]:
    return _safe_success(
        schema={
            "name": "LuxCode Render Controlled Deployment Execution Gateway",
            "transports": TRANSPORT_TYPES,
            "default_transport": "disabled_transport",
            "credential_states": CREDENTIAL_STATES,
            "blocked_states": BLOCKED_STATES,
            "lifecycle_events": LIFECYCLE_EVENTS,
            "audit_events": AUDIT_EVENTS,
            "structured_request_required": True,
            "raw_http_payload_allowed": False,
            "raw_cli_command_allowed": False,
            "arbitrary_url_allowed": False,
        }
    )


def get_render_gateway_registry() -> Dict[str, Any]:
    return _safe_success(
        transports={
            "fake_render_transport": {
                "runtime_enabled": True,
                "real_cloud_deployment": False,
                "operations": ["prepare_request", "validate_request", "start_deployment", "poll_deployment", "collect_result", "cleanup_transport"],
                "fixtures": sorted(FAILURE_FIXTURES),
            },
            "render_http_transport": {
                "runtime_enabled": False,
                "disabled_result": "render_http_transport_disabled",
                "allowed_origin": "https://api.render.com",
                "allowed_methods": ["GET", "POST", "PATCH"],
                "bounded_response_size": 120000,
                "timeout_seconds": 10,
                "redaction": "headers_and_body_secret_markers",
                "external_call_performed": False,
            },
            "render_cli_transport": {
                "runtime_enabled": False,
                "disabled_result": "render_cli_transport_disabled",
                "shell": False,
                "install_allowed": False,
                "login_allowed": False,
                "version_probe_executed": False,
                "external_command_executed": False,
            },
            "disabled_transport": {"runtime_enabled": False, "disabled_result": "transport_disabled"},
            "unknown_transport": {"runtime_enabled": False, "disabled_result": "unknown_transport_disabled"},
        },
        provider="render",
        task_owned_runtime_only=True,
    )


def _credential_state(reference: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ref = deepcopy(reference or {})
    state = str(ref.get("availability") or ref.get("state") or "reference_missing")
    if not FEATURE_FLAGS["credential_resolution_enabled"] and state == "reference_available" and ref.get("reference_id") != "fixture-render-reference":
        state = "resolution_disabled"
    if state not in CREDENTIAL_STATES:
        state = "reference_missing"
    return {
        "provider": "render",
        "reference_id": str(ref.get("reference_id") or ""),
        "scope": str(ref.get("scope") or "deploy"),
        "availability": state,
        "expiration": str(ref.get("expiration") or "not_checked"),
        "allowed_operations": list(ref.get("allowed_operations") or ["deploy"]),
        "environment": str(ref.get("environment") or "non_production"),
        "last_verification": str(ref.get("last_verification") or "not_verified"),
        "resolution_policy": "reference_only_no_secret_resolution",
        "redaction_policy": "never_log_or_persist_secret_value",
    }


def _scope_digest(plan: Dict[str, Any]) -> str:
    return _digest([plan.get("project_root"), plan.get("root_directory"), plan.get("service_candidate_id")], "scope-digest-")


def _request_digest(request: Dict[str, Any]) -> str:
    data = {key: value for key, value in request.items() if key not in {"request_digest", "audit_events"}}
    return _digest(data, "render-gateway-request-")


def evaluate_render_execution_authority(
    plan: Dict[str, Any],
    expected_plan_digest: str = "",
    task_id: str = "",
    selected_service_id: str = "",
    access_mode: str = "controlled_access",
    deployment_intent: bool = False,
    credential_reference: Optional[Dict[str, Any]] = None,
    transport_type: str = "disabled_transport",
    final_confirmation: bool = False,
    rollback_strategy: Optional[Dict[str, Any]] = None,
    production_deployment: bool = False,
) -> Dict[str, Any]:
    events: List[str] = ["gateway_created", "gateway_authority_checking"]
    validation = validate_render_deployment_plan(plan, expected_plan_digest or str(plan.get("plan_digest") or ""))
    credential = _credential_state(credential_reference or plan.get("credential_reference") or {})
    blocked = ""
    if not deployment_intent and not plan.get("deployment_intent"):
        blocked = "blocked_missing_deployment_intent"
    elif not validation.get("ok"):
        blocked = "blocked_plan_mismatch"
    elif task_id and plan.get("task_id") and task_id != plan.get("task_id"):
        blocked = "blocked_scope_mismatch"
    elif selected_service_id and selected_service_id != plan.get("service_candidate_id"):
        blocked = "blocked_scope_mismatch"
    elif not plan.get("service_candidate_id"):
        blocked = "blocked_service_not_selected"
    elif access_mode == "approval_required" and not final_confirmation:
        blocked = "blocked_permission_denied"
    elif credential.get("availability") != "reference_available" and transport_type != "fake_render_transport":
        blocked = "blocked_credential_reference"
    elif transport_type in {"render_http_transport", "render_cli_transport"} and not FEATURE_FLAGS["external_network_enabled"]:
        blocked = "blocked_external_network"
    elif transport_type == "render_http_transport" and not FEATURE_FLAGS["http_transport_enabled"]:
        blocked = "blocked_transport_disabled"
    elif transport_type == "render_cli_transport" and not FEATURE_FLAGS["cli_transport_enabled"]:
        blocked = "blocked_transport_disabled"
    elif transport_type not in TRANSPORT_TYPES:
        blocked = "blocked_transport_disabled"
    elif production_deployment and not FEATURE_FLAGS["production_deployment_enabled"]:
        blocked = "blocked_production_disabled"
    elif FEATURE_FLAGS["final_confirmation_required"] and not final_confirmation:
        blocked = "blocked_final_confirmation"
    elif not (rollback_strategy or plan.get("rollback_policy")):
        blocked = "blocked_rollback_unavailable"
    elif transport_type != "fake_render_transport":
        blocked = "blocked_transport_disabled"

    allowed = not blocked
    events.append("gateway_ready" if allowed else "gateway_authority_blocked")
    authority = {
        "allowed": allowed,
        "authority_state": "gateway_ready" if allowed else blocked,
        "blocked_state": blocked,
        "next_safe_action": "Proceed with fake Render transport." if allowed else _next_safe_action(blocked),
        "task_id": task_id or plan.get("task_id"),
        "scope_digest": _scope_digest(plan),
        "deployment_intent": bool(deployment_intent or plan.get("deployment_intent")),
        "selected_service": plan.get("service_candidate_id"),
        "validated_plan_id": plan.get("render_plan_id"),
        "validated_plan_digest": expected_plan_digest or plan.get("plan_digest"),
        "access_mode": access_mode,
        "risk_decision": "critical" if production_deployment else "controlled_fake_allowed",
        "credential_reference_state": credential,
        "external_network_policy": "disabled_by_local_policy",
        "transport_policy": transport_type,
        "final_confirmation": bool(final_confirmation),
        "rollback_strategy": rollback_strategy or plan.get("rollback_policy", {}),
        "cleanup_strategy": plan.get("cleanup_policy", {}),
        "events": events,
    }
    return _safe_success(authority=authority)


def select_render_transport(authority: Dict[str, Any], requested_transport: str = "disabled_transport") -> Dict[str, Any]:
    requested = requested_transport if requested_transport in TRANSPORT_TYPES else "unknown_transport"
    if requested == "fake_render_transport" and authority.get("allowed") and FEATURE_FLAGS["fake_transport_enabled"]:
        return _safe_success(transport="fake_render_transport", selected=True, event="transport_selected")
    if requested == "render_http_transport":
        return _safe_failure("render_http_transport_disabled", transport=requested, disabled_result="render_http_transport_disabled")
    if requested == "render_cli_transport":
        return _safe_failure("render_cli_transport_disabled", transport=requested, disabled_result="render_cli_transport_disabled")
    return _safe_failure("transport disabled", transport=requested, disabled_result="transport_disabled")


def build_render_execution_request(
    plan: Dict[str, Any],
    expected_plan_digest: str = "",
    task_id: str = "",
    selected_service_id: str = "",
    transport_type: str = "disabled_transport",
    credential_reference: Optional[Dict[str, Any]] = None,
    deployment_intent: bool = False,
    permission_decision: Optional[Dict[str, Any]] = None,
    final_confirmation: bool = False,
    commit_metadata: Optional[Dict[str, Any]] = None,
    branch_metadata: Optional[Dict[str, Any]] = None,
    access_mode: str = "controlled_access",
    fake_fixture: str = "success_web_service",
) -> Dict[str, Any]:
    authority = permission_decision or evaluate_render_execution_authority(
        plan=plan,
        expected_plan_digest=expected_plan_digest,
        task_id=task_id,
        selected_service_id=selected_service_id,
        access_mode=access_mode,
        deployment_intent=deployment_intent,
        credential_reference=credential_reference,
        transport_type=transport_type,
        final_confirmation=final_confirmation,
    ).get("authority", {})
    credential = _credential_state(credential_reference or plan.get("credential_reference") or {})
    request = {
        "gateway_runtime_id": _digest([plan.get("render_plan_id"), transport_type, time.time()], "render-gateway-runtime-"),
        "task_id": task_id or plan.get("task_id"),
        "project_scope_digest": _scope_digest(plan),
        "render_plan_id": plan.get("render_plan_id"),
        "render_plan_digest": expected_plan_digest or plan.get("plan_digest"),
        "render_plan_snapshot": _redact(deepcopy(plan)),
        "selected_service_id": selected_service_id or plan.get("service_candidate_id"),
        "selected_service_type": plan.get("service_type"),
        "environment": credential.get("environment", "non_production"),
        "transport_type": transport_type if transport_type in TRANSPORT_TYPES else "unknown_transport",
        "credential_reference": credential,
        "deployment_intent": bool(deployment_intent or plan.get("deployment_intent")),
        "permission_decision": authority,
        "final_confirmation": bool(final_confirmation),
        "commit_metadata": deepcopy(commit_metadata or {}),
        "branch_metadata": deepcopy(branch_metadata or {"branch": plan.get("branch", "main")}),
        "build_policy": {"structured_only": True, "raw_command_allowed": False},
        "health_policy": {"delegate_to_deployment_core": True, "expected_status": 200},
        "url_verification_policy": {"runtime_derived_url_only": True, "arbitrary_url_allowed": False},
        "browser_scenario_policy": {"delegate_to_deployment_core": True, "visible_assertion_required": True},
        "retry_budget": max(0, min(int(plan.get("retry_budget", 1) or 0), 3)),
        "polling_policy": {"interval_seconds": 0.05, "max_attempts": 5, "global_timeout_seconds": 5, "duplicate_event_suppression": True},
        "timeout_policy": {"deployment_timeout_seconds": max(5, min(int(plan.get("timeout_seconds", 60) or 60), 180))},
        "rollback_policy": deepcopy(plan.get("rollback_policy", {})),
        "cleanup_policy": {"owned_runtime_only": True, "temporary_artifacts_removed": True},
        "evidence_policy": {"structured_metadata_only": True, "raw_provider_payload_persisted": False},
        "fake_fixture": fake_fixture,
        "raw_http_body": None,
        "raw_cli_command": None,
        "arbitrary_url": None,
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    request["request_digest"] = _request_digest(request)
    _audit(request, "render_execution_request_created", {"transport": request["transport_type"]})
    return _safe_success(request=request)


def validate_render_execution_request(request: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(request, dict):
        return _safe_failure("structured execution request required")
    if request.get("raw_http_body") or request.get("raw_cli_command") or request.get("arbitrary_url"):
        return _safe_failure("raw provider payloads, raw commands, and arbitrary URLs are blocked")
    if _request_digest(request) != request.get("request_digest"):
        return _safe_failure("execution request digest mismatch")
    if request.get("transport_type") not in TRANSPORT_TYPES:
        return _safe_failure("unknown transport")
    if request.get("retry_budget", 0) > 3 or request.get("polling_policy", {}).get("max_attempts", 0) > 20:
        return _safe_failure("unbounded retry or polling policy rejected")
    if request.get("credential_reference", {}).get("provider") != "render":
        return _safe_failure("Render credential reference required")
    _audit(request, "render_execution_request_validated", {"request_digest": request.get("request_digest")})
    return _safe_success(valid=True, request_digest=request.get("request_digest"))


def _trust_runtime_url(runtime: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    url = runtime.get("url_result", {}).get("url", "")
    parsed = urlparse(url)
    trusted = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"} and bool(parsed.port)
    return {
        "trusted": trusted,
        "url": url if trusted else "",
        "deployment_runtime_related": bool(runtime.get("deployment_core_runtime", {}).get("deployment_runtime_id")),
        "selected_service_related": runtime.get("render_plan_id") == request.get("render_plan_id"),
        "expected_provider_source": runtime.get("url_result", {}).get("provider") == "fake_render_provider",
        "normalized_scheme": parsed.scheme,
        "normalized_host": parsed.hostname or "",
        "allowed_environment": request.get("environment") in {"fixture", "non_production", "preview"},
        "creation_timestamp": _now(),
        "staleness_state": "fresh_runtime_url",
        "arbitrary_user_url": False,
    }


def execute_render_gateway(request: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_render_execution_request(request)
    runtime = {
        "gateway_runtime_id": request.get("gateway_runtime_id"),
        "task_id": request.get("task_id"),
        "render_plan_id": request.get("render_plan_id"),
        "render_plan_digest": request.get("render_plan_digest"),
        "selected_service_id": request.get("selected_service_id"),
        "transport": request.get("transport_type", "disabled_transport"),
        "provider": "render",
        "state": "gateway_created",
        "event_sequence": [],
        "build_state": "not_started",
        "deployment_state": "not_started",
        "url_metadata": {},
        "failure_category": "",
        "retryable": False,
        "rollback_availability": bool(request.get("rollback_policy", {}).get("rollback_supported")),
        "evidence": {"structured_only": True},
        "cleanup_state": "cleanup_required",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    _audit(runtime, "render_execution_started", {"transport": runtime["transport"]})
    if not validation.get("ok"):
        runtime.update({"state": "deployment_manual_review_required", "failure_category": "invalid_request", "cleanup_state": "deployment_cleanup_completed"})
        _RUNTIMES[str(runtime["gateway_runtime_id"])] = runtime
        return _safe_failure(validation.get("error", "invalid request"), runtime=_public_runtime(runtime))
    authority = request.get("permission_decision", {})
    selected = select_render_transport(authority, request.get("transport_type", "disabled_transport"))
    if not selected.get("ok"):
        runtime.update({"state": "transport_disabled", "failure_category": selected.get("disabled_result", "transport_disabled"), "cleanup_state": "deployment_cleanup_completed"})
        runtime["event_sequence"] = ["gateway_created", "gateway_authority_checking", "gateway_authority_blocked", "transport_disabled", "deployment_cleanup_completed"]
        _audit(runtime, "render_transport_disabled", {"transport": runtime["transport"]})
        _audit(runtime, "render_cleanup_completed", {"owned_runtime_only": True})
        _RUNTIMES[str(runtime["gateway_runtime_id"])] = runtime
        return _safe_failure(selected.get("error", "transport disabled"), runtime=_public_runtime(runtime), failure_category=runtime["failure_category"])

    fixture = FAILURE_FIXTURES.get(str(request.get("fake_fixture") or "success_web_service"), "success")
    adapter_plan = deepcopy(request.get("render_plan_snapshot") or {})
    result = execute_render_dry_run(adapter_plan, fixture=fixture)
    fake_runtime = result.get("runtime", {})
    runtime["deployment_id"] = fake_runtime.get("deployment_id")
    runtime["event_sequence"] = [
        "gateway_created",
        "gateway_authority_checking",
        "gateway_ready",
        "transport_selected",
        "deployment_request_prepared",
        "deployment_started",
        "deployment_queued",
        "deployment_building",
        "deployment_live",
        "deployment_url_received",
        "deployment_health_checking",
        "deployment_health_verified",
        "deployment_scenario_verifying",
        "deployment_scenario_verified",
        "deployment_fully_verified",
        "deployment_cleanup_started",
        "deployment_cleanup_completed",
    ]
    runtime["build_state"] = "build_succeeded" if result.get("ok") and fake_runtime.get("lifecycle_state") == "render_fully_verified" else "build_failed"
    runtime["deployment_state"] = "deployment_live" if runtime["build_state"] == "build_succeeded" else "deployment_failed"
    runtime["url_metadata"] = _trust_runtime_url(fake_runtime, request)
    runtime["health_state"] = "deployment_health_verified" if fake_runtime.get("url_result", {}).get("final_verification_status") == "fully_verified" else "deployment_health_failed"
    runtime["browser_state"] = "deployment_scenario_verified" if runtime["health_state"] == "deployment_health_verified" else "deployment_scenario_failed"
    runtime["state"] = "fake_render_gateway_verified" if runtime["browser_state"] == "deployment_scenario_verified" else "deployment_partially_verified"
    runtime["failure_category"] = fake_runtime.get("failure_category", "")
    runtime["retryable"] = runtime["failure_category"] in {"fake_deployment_timeout"}
    runtime["cleanup_state"] = "deployment_cleanup_completed"
    runtime["adapter_runtime"] = fake_runtime
    runtime["simulation"] = True
    runtime["real_cloud_deployment"] = False
    runtime["public_production_url"] = False
    _audit(runtime, "render_transport_selected", {"transport": "fake_render_transport"})
    _audit(runtime, "render_url_collected", runtime["url_metadata"])
    if runtime["state"] == "fake_render_gateway_verified":
        _audit(runtime, "render_health_verified", {"delegated": True})
        _audit(runtime, "render_scenario_verified", {"delegated": True})
        _audit(runtime, "render_execution_completed", {"state": runtime["state"]})
    else:
        _audit(runtime, "render_execution_failed", {"failure_category": runtime["failure_category"]})
    _audit(runtime, "render_cleanup_completed", {"owned_runtime_only": True})
    _RUNTIMES[str(runtime["gateway_runtime_id"])] = runtime
    return _safe_success(runtime=_public_runtime(runtime), delivery=summarize_render_gateway_result(runtime).get("summary"))


def poll_render_gateway(runtime_id: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("gateway runtime not found")
    runtime.setdefault("polling", {"attempts": 0, "max_attempts": 5, "terminal_state_detected": False})
    runtime["polling"]["attempts"] += 1
    runtime["polling"]["terminal_state_detected"] = runtime.get("state") in {"fake_render_gateway_verified", "deployment_partially_verified", "transport_disabled", "deployment_cancelled"}
    _audit(runtime, "render_execution_polled", runtime["polling"])
    return _safe_success(runtime=_public_runtime(runtime))


def collect_render_gateway_result(runtime_id: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("gateway runtime not found")
    return _safe_success(runtime=_public_runtime(runtime), summary=summarize_render_gateway_result(runtime).get("summary"))


def verify_render_gateway_url(runtime_id: str = "", url: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("gateway runtime not found")
    trusted = runtime.get("url_metadata", {})
    if url and url != trusted.get("url"):
        return _safe_failure("arbitrary URL verification blocked", url_trusted=False)
    core_runtime = runtime.get("adapter_runtime", {}).get("deployment_core_runtime", {}).get("deployment_runtime_id", "")
    if core_runtime:
        delegated = verify_deployment_url(core_runtime, trusted.get("url", ""))
        return _safe_success(url_trust=trusted, delegated_verification=delegated, fully_verified=bool(delegated.get("fully_verified")))
    return _safe_success(url_trust=trusted, delegated_verification={"ok": False, "reason": "no active fixture runtime"}, fully_verified=bool(trusted.get("trusted")))


def cancel_render_gateway(runtime_id: str = "", task_id: str = "", reason: str = "user_requested") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("gateway runtime not found")
    if task_id and task_id != runtime.get("task_id"):
        return _safe_failure("cancel blocked by task ownership mismatch")
    if runtime.get("state") in {"fake_render_gateway_verified", "transport_disabled", "deployment_cancelled"}:
        return _safe_failure("terminal gateway runtime cannot be cancelled again", runtime=_public_runtime(runtime))
    runtime["state"] = "deployment_cancelled"
    runtime["cleanup_state"] = "deployment_cleanup_completed"
    runtime.setdefault("event_sequence", []).extend(["deployment_cancel_requested", "deployment_cancelled", "deployment_cleanup_completed"])
    _audit(runtime, "render_cancel_requested", {"reason": reason})
    _audit(runtime, "render_cancelled", {"owned_runtime_only": True})
    return _safe_success(runtime=_public_runtime(runtime))


def build_render_gateway_rollback(runtime_id: str = "", explicit_rollback_intent: bool = False, final_confirmation: bool = False) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("gateway runtime not found")
    rollback = {
        "rollback_plan_id": _digest([runtime_id, "rollback"], "render-rollback-"),
        "deployment_runtime": runtime_id,
        "rollback_support": bool(runtime.get("rollback_availability")),
        "rollback_risk": "critical_for_real_render",
        "rollback_plan_digest": _digest([runtime_id, runtime.get("deployment_id")], "render-rollback-digest-"),
        "explicit_rollback_intent": bool(explicit_rollback_intent),
        "final_confirmation": bool(final_confirmation),
        "real_render_rollback_execution_enabled": False,
        "recommended_action": "manual review; real Render rollback disabled in MVP",
    }
    if not explicit_rollback_intent or not final_confirmation or not FEATURE_FLAGS["rollback_execution_enabled"]:
        rollback["rollback_state"] = "render_rollback_transport_disabled"
    return _safe_success(rollback=rollback)


def execute_render_gateway_rollback(rollback: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_failure("render_rollback_transport_disabled", rollback=deepcopy(rollback or {}), production_rollback_executed=False)


def cleanup_render_gateway(runtime_id: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("gateway runtime not found")
    runtime["cleanup_state"] = "deployment_cleanup_completed"
    _audit(runtime, "render_cleanup_completed", {"owned_runtime_only": True})
    return _safe_success(runtime=_public_runtime(runtime))


def summarize_render_gateway_result(runtime: Dict[str, Any]) -> Dict[str, Any]:
    metadata = runtime.get("url_metadata", {})
    summary = {
        "provider": "render",
        "transport": runtime.get("transport"),
        "environment": "temporary_fake_render" if runtime.get("simulation") else "blocked_real_render",
        "service": runtime.get("selected_service_id"),
        "deployment_id": runtime.get("deployment_id"),
        "url": metadata.get("url") if metadata.get("trusted") else "",
        "url_source": "runtime_derived_localhost_fixture",
        "health_state": runtime.get("health_state", "blocked"),
        "browser_state": runtime.get("browser_state", "blocked"),
        "final_verification_state": runtime.get("state"),
        "fake_real_classification": "fake_render_gateway_only",
        "simulation": True,
        "real_cloud_deployment": False,
        "public_production_url": False,
        "risk": "controlled_fake_execution",
        "known_limitations": ["not a public Render URL", "real HTTP and CLI transports disabled"],
        "rollback_availability": runtime.get("rollback_availability"),
        "recommended_next_action": "Use final commit/push instructions after validation passes.",
    }
    return _safe_success(summary=summary)


def restore_render_gateway_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = _redact(deepcopy(record or {}))
    restored["restore_state"] = "gateway_resume_requires_user_action"
    restored["external_state"] = "gateway_external_state_revalidation_required"
    restored["review_state"] = "gateway_manual_review_required"
    restored["transport_started"] = False
    restored["api_cli_called"] = False
    restored["polling_started"] = False
    restored["url_probe_started"] = False
    restored["browser_started"] = False
    restored["rollback_started"] = False
    restored.setdefault("audit_events", []).append({"event_type": "render_restore_requires_user_action", "created_at": _now(), "payload": {}})
    return _safe_success(runtime=restored)


def get_safe_render_gateway_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "gateway_runtime_id": runtime.get("gateway_runtime_id"),
        "task_id": runtime.get("task_id"),
        "plan_id": runtime.get("render_plan_id"),
        "plan_digest": runtime.get("render_plan_digest"),
        "selected_service": runtime.get("selected_service_id"),
        "transport_type": runtime.get("transport"),
        "authority_state": runtime.get("permission_decision", {}).get("authority_state"),
        "credential_reference_state": runtime.get("credential_reference", {}).get("availability"),
        "network_policy_state": "disabled_by_local_policy",
        "lifecycle_state": runtime.get("state"),
        "deployment_id_metadata": runtime.get("deployment_id"),
        "url_trust_state": runtime.get("url_metadata", {}).get("trusted"),
        "health_state": runtime.get("health_state"),
        "scenario_state": runtime.get("browser_state"),
        "rollback_metadata": {"available": runtime.get("rollback_availability"), "real_execution_enabled": False},
        "failure_category": runtime.get("failure_category"),
        "cleanup_state": runtime.get("cleanup_state"),
        "resume_policy": "gateway_resume_requires_user_action",
        "safe_metadata_only": True,
    }


def get_render_gateway_status() -> Dict[str, Any]:
    return _safe_success(
        name="LuxCode Render Controlled Deployment Execution Gateway",
        status="ready",
        runtime_count=len(_RUNTIMES),
        active_runtime_count=sum(1 for item in _RUNTIMES.values() if item.get("cleanup_state") != "deployment_cleanup_completed"),
        default_transport="disabled_transport",
        fake_transport_enabled=True,
        real_render_execution_enabled=False,
        http_transport_enabled=False,
        cli_transport_enabled=False,
        external_network_enabled=False,
    )


def build_gateway_plan_for_fixture(task_id: str, repository_root: str, service_candidate_id: str = "") -> Dict[str, Any]:
    return build_render_deployment_plan(
        task_id=task_id,
        repository_root=repository_root,
        selected_scope=".",
        service_candidate_id=service_candidate_id,
        credential_reference={"provider": "render", "reference_id": "fixture-render-reference", "availability": "reference_available", "scope": "deploy", "environment": "fixture"},
        external_network_allowed=False,
        deployment_intent=True,
        final_confirmation=True,
    )


def _public_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return _redact(deepcopy(runtime))
