from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from luxcode_render_execution_gateway import get_render_gateway_policy
from luxcode_render_provider_adapter import validate_render_deployment_plan


SAFE_INVARIANTS = {
    "external_api_used": False,
    "external_network_used": False,
    "public_internet_used": False,
    "render_api_used": False,
    "render_cli_used": False,
    "render_token_read": False,
    "credential_value_read": False,
    "secret_values_read": False,
    "dotenv_read": False,
    "credential_manager_read": False,
    "keyring_read": False,
    "cloud_deployment_used": False,
    "package_installation_used": False,
    "layer42_started": False,
    "local_first": True,
}

REFERENCE_PROVIDERS = [
    "render_credential_reference",
    "os_secure_store_reference",
    "user_managed_reference",
    "workspace_reference",
    "fixture_reference",
    "missing_reference",
    "unknown_reference",
]

REFERENCE_STATES = [
    "reference_available",
    "reference_missing",
    "reference_expired",
    "reference_not_yet_valid",
    "reference_scope_insufficient",
    "reference_operation_not_allowed",
    "reference_environment_mismatch",
    "reference_service_mismatch",
    "reference_owner_mismatch",
    "reference_rotation_required",
    "reference_verification_required",
    "reference_resolution_disabled",
    "manual_setup_required",
    "reference_ready_for_dry_run",
    "reference_ready_for_controlled_execution",
]

SCOPE_TYPES = [
    "read_service_metadata",
    "read_deployment_status",
    "create_deployment",
    "cancel_deployment",
    "read_logs",
    "manage_environment",
    "rollback_deployment",
    "delete_service",
    "admin",
]

MINIMUM_DEPLOYMENT_SCOPE = ["read_service_metadata", "read_deployment_status", "create_deployment"]
HIGH_RISK_SCOPES = {"manage_environment", "delete_service", "admin"}

NETWORK_STATES = [
    "network_not_requested",
    "network_permission_missing",
    "network_origin_not_allowed",
    "network_method_not_allowed",
    "network_scope_mismatch",
    "network_duration_expired",
    "network_budget_exceeded",
    "network_ready_for_dry_run",
    "network_ready_for_controlled_execution",
]

BLOCKER_CATEGORIES = [
    "missing_render_plan",
    "invalid_render_plan_digest",
    "missing_service",
    "service_mismatch",
    "missing_deployment_intent",
    "permission_denied",
    "missing_credential_reference",
    "credential_reference_invalid",
    "credential_expired",
    "credential_scope_insufficient",
    "credential_environment_mismatch",
    "credential_service_mismatch",
    "credential_verification_required",
    "network_permission_missing",
    "network_origin_not_allowed",
    "network_scope_mismatch",
    "final_confirmation_missing",
    "rollback_unavailable",
    "verification_policy_incomplete",
    "cleanup_policy_incomplete",
    "production_execution_disabled",
    "seal_expired",
    "manual_review_required",
]

WARNING_CATEGORIES = [
    "overprivileged_credential",
    "credential_expires_soon",
    "credential_verification_stale",
    "rollback_not_recently_tested",
    "health_path_inferred",
    "browser_scenario_minimal",
    "branch_not_protected",
    "commit_not_pinned",
    "production_environment_selected",
    "network_budget_narrow",
    "cleanup_evidence_incomplete",
    "fake_transport_only",
]

SEAL_STATES = [
    "seal_not_issued",
    "seal_blocked",
    "seal_issued_for_dry_run",
    "seal_issued_for_controlled_execution",
    "seal_expired",
    "seal_revoked",
    "seal_invalidated",
    "seal_consumed",
    "seal_manual_review_required",
]

CONFIRMATION_STATES = [
    "confirmation_missing",
    "confirmation_requested",
    "confirmation_granted",
    "confirmation_expired",
    "confirmation_revoked",
    "confirmation_scope_mismatch",
    "confirmation_digest_mismatch",
]

AUDIT_EVENTS = [
    "render_credential_reference_received",
    "render_credential_reference_validated",
    "render_credential_reference_blocked",
    "render_credential_scope_checked",
    "render_credential_expiration_checked",
    "render_network_authority_checked",
    "render_readiness_package_created",
    "render_readiness_blocker_added",
    "render_readiness_warning_added",
    "render_readiness_package_validated",
    "render_readiness_seal_issued",
    "render_readiness_seal_blocked",
    "render_readiness_seal_invalidated",
    "render_readiness_seal_expired",
    "render_final_confirmation_bound",
    "render_final_confirmation_invalidated",
    "render_gateway_execution_blocked_by_seal",
    "render_restore_requires_revalidation",
]

SECRET_FIELD_MARKERS = ("token", "api_key", "secret", "password", "authorization", "credential_value", "raw_credential")
ALLOWED_RENDER_ORIGIN = "https://api.render.com"
ALLOWED_METHODS = {"GET", "POST", "PATCH"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str) -> str:
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
            elif any(marker in lowered for marker in SECRET_FIELD_MARKERS):
                clean[str(key)] = "[blocked-secret-field]"
            else:
                clean[str(key)] = _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and ("Bearer " in value or "sk-" in value):
        return "[redacted]"
    return value


def _secret_field_paths(value: Any, path: str = "") -> List[str]:
    found: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if any(marker == str(key).lower() or marker in str(key).lower() for marker in SECRET_FIELD_MARKERS):
                found.append(current)
            found.extend(_secret_field_paths(item, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_secret_field_paths(item, f"{path}[{index}]"))
    return found


def _audit(target: Dict[str, Any], event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    target.setdefault("audit_events", []).append({"event_type": event_type if event_type in AUDIT_EVENTS else "render_readiness_warning_added", "created_at": _now(), "payload": _redact(payload or {})})


def _blocker(category: str, current: str, required: str, source: str = "readiness_broker", severity: str = "critical", retryable: bool = True) -> Dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "source": source,
        "current_state": current,
        "required_state": required,
        "user_action": _blocker_action(category),
        "retryable": retryable,
        "automatic_resolution_allowed": False,
    }


def _blocker_action(category: str) -> str:
    return {
        "missing_render_plan": "Build and validate a Render plan.",
        "invalid_render_plan_digest": "Use the immutable plan digest produced by the Render adapter.",
        "missing_service": "Select a Render service.",
        "missing_deployment_intent": "Provide explicit deployment intent.",
        "missing_credential_reference": "Provide credential reference metadata only.",
        "credential_expired": "Rotate or replace the credential reference.",
        "credential_scope_insufficient": "Grant minimum deployment scopes to the reference.",
        "credential_environment_mismatch": "Use a reference bound to the selected environment.",
        "credential_service_mismatch": "Use a reference bound to the selected service.",
        "credential_verification_required": "Revalidate credential metadata out of band.",
        "network_permission_missing": "Provide explicit network authority metadata.",
        "network_origin_not_allowed": "Restrict future execution to the official Render API origin.",
        "final_confirmation_missing": "Bind final confirmation to the exact readiness package.",
        "rollback_unavailable": "Prepare rollback readiness metadata.",
        "production_execution_disabled": "Keep real execution blocked until trusted local policy enables it.",
    }.get(category, "Request manual review.")


def _warning(category: str, detail: str, severity: str = "important") -> Dict[str, Any]:
    return {"category": category, "severity": severity, "detail": detail, "automatic_resolution_allowed": False}


def _policy_digest() -> str:
    policy = get_render_gateway_policy().get("policy", {})
    return _digest(policy, "render-gateway-policy-")


def get_render_credential_broker_schema() -> Dict[str, Any]:
    return _safe_success(
        schema={
            "name": "LuxCode Render Credential Reference Broker and Production Readiness Seal",
            "reference_providers": REFERENCE_PROVIDERS,
            "reference_states": REFERENCE_STATES,
            "scope_types": SCOPE_TYPES,
            "network_states": NETWORK_STATES,
            "blocker_categories": BLOCKER_CATEGORIES,
            "warning_categories": WARNING_CATEGORIES,
            "seal_states": SEAL_STATES,
            "confirmation_states": CONFIRMATION_STATES,
            "audit_events": AUDIT_EVENTS,
            "credential_values_allowed": False,
            "secret_field_names_blocked": list(SECRET_FIELD_MARKERS),
        }
    )


def get_render_credential_broker_registry() -> Dict[str, Any]:
    return _safe_success(
        registry={
            "providers": REFERENCE_PROVIDERS,
            "minimum_production_scopes": MINIMUM_DEPLOYMENT_SCOPE,
            "optional_cancel_scope": "cancel_deployment",
            "optional_rollback_scope": "rollback_deployment",
            "high_risk_scopes": sorted(HIGH_RISK_SCOPES),
            "allowed_network_origin": ALLOWED_RENDER_ORIGIN,
            "allowed_network_methods": sorted(ALLOWED_METHODS),
            "real_secret_resolver_enabled": False,
            "real_render_execution_enabled": False,
        }
    )


def get_render_readiness_policy() -> Dict[str, Any]:
    return _safe_success(
        policy={
            "credential_reference_only": True,
            "credential_value_resolution_enabled": False,
            "credential_manager_read_enabled": False,
            "keyring_read_enabled": False,
            "dotenv_read_enabled": False,
            "external_network_enabled": False,
            "production_deployment_enabled": False,
            "real_render_execution_enabled": False,
            "readiness_seal_required_for_real_execution": True,
            "normal_mvp_seal": "seal_issued_for_dry_run",
            "controlled_execution_metadata_seal_note": "metadata ready only; real execution feature disabled",
            "clock_skew_tolerance_seconds": 300,
        }
    )


def normalize_credential_reference(reference: Dict[str, Any], now: str = "") -> Dict[str, Any]:
    secret_fields = _secret_field_paths(reference)
    if secret_fields:
        return _safe_failure("secret-named credential fields are blocked", blocked=True, secret_fields=secret_fields)
    ref = deepcopy(reference or {})
    provider = str(ref.get("provider") or "missing_reference")
    if provider == "render":
        provider = "render_credential_reference"
    if provider not in REFERENCE_PROVIDERS:
        provider = "unknown_reference"
    normalized = {
        "reference_id": str(ref.get("reference_id") or ""),
        "provider": provider,
        "target_service": str(ref.get("target_service") or ref.get("service_id") or ""),
        "environment": str(ref.get("environment") or "preview"),
        "scope": sorted({str(item) for item in ref.get("scope", ref.get("allowed_operations", [])) if str(item)}),
        "allowed_operations": sorted({str(item) for item in ref.get("allowed_operations", ref.get("scope", [])) if str(item)}),
        "created_time": str(ref.get("created_time") or now or _now()),
        "issued_time": str(ref.get("issued_time") or ref.get("created_time") or now or _now()),
        "valid_from": str(ref.get("valid_from") or ref.get("created_time") or now or _now()),
        "expires_at": str(ref.get("expires_at") or ""),
        "last_verified_time": str(ref.get("last_verified_time") or ""),
        "status": str(ref.get("status") or "reference_available"),
        "owner_category": str(ref.get("owner_category") or "user_managed"),
        "rotation_required": bool(ref.get("rotation_required", False)),
        "rotation_due_date": str(ref.get("rotation_due_date") or ""),
        "user_confirmation_required": bool(ref.get("user_confirmation_required", True)),
        "resolver_type": str(ref.get("resolver_type") or "metadata_only_no_secret_resolution"),
        "redaction_policy": "never_store_or_return_credential_value",
        "project_scope_digest": str(ref.get("project_scope_digest") or ""),
        "allowed_branch": str(ref.get("allowed_branch") or ""),
        "allowed_deployment_type": str(ref.get("allowed_deployment_type") or "render_deployment"),
        "workspace_reference": str(ref.get("workspace_reference") or ""),
    }
    normalized["credential_reference_digest"] = _digest(normalized, "render-credential-ref-")
    _audit(normalized, "render_credential_reference_received", {"provider": provider})
    return _safe_success(reference=normalized)


def evaluate_credential_scope(reference: Dict[str, Any], require_cancel: bool = False, require_rollback: bool = False) -> Dict[str, Any]:
    scopes = set(reference.get("scope") or reference.get("allowed_operations") or [])
    required = set(MINIMUM_DEPLOYMENT_SCOPE)
    if require_cancel:
        required.add("cancel_deployment")
    if require_rollback:
        required.add("rollback_deployment")
    missing = sorted(required - scopes)
    warnings = []
    extra_high_risk = sorted(scopes & HIGH_RISK_SCOPES)
    if extra_high_risk:
        warnings.append(_warning("overprivileged_credential", f"High-risk scopes present: {', '.join(extra_high_risk)}"))
    decision = {
        "scope_state": "reference_scope_insufficient" if missing else "reference_ready_for_controlled_execution",
        "required_scopes": sorted(required),
        "provided_scopes": sorted(scopes),
        "missing_scopes": missing,
        "least_privilege": not extra_high_risk,
        "warnings": warnings,
        "scope_digest": _digest({"required": sorted(required), "provided": sorted(scopes)}, "render-scope-"),
    }
    _audit(decision, "render_credential_scope_checked", {"missing": missing})
    return _safe_success(scope_decision=decision)


def evaluate_credential_expiration(reference: Dict[str, Any], now: str = "", max_verification_age_hours: int = 168) -> Dict[str, Any]:
    current = _parse_time(now) or datetime.now(timezone.utc)
    valid_from = _parse_time(reference.get("valid_from"))
    expires_at = _parse_time(reference.get("expires_at"))
    rotation_due = _parse_time(reference.get("rotation_due_date"))
    last_verified = _parse_time(reference.get("last_verified_time"))
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    state = "reference_available"
    if valid_from and current + timedelta(seconds=300) < valid_from:
        state = "reference_not_yet_valid"
        blockers.append(_blocker("credential_reference_invalid", state, "reference_available", source="credential_expiration"))
    if expires_at is None:
        warnings.append(_warning("credential_verification_stale", "Unknown expiration requires manual review."))
    elif current - timedelta(seconds=300) > expires_at:
        state = "reference_expired"
        blockers.append(_blocker("credential_expired", state, "unexpired", source="credential_expiration", retryable=False))
    elif expires_at - current <= timedelta(hours=24):
        warnings.append(_warning("credential_expires_soon", "Credential reference expires within 24 hours."))
    if reference.get("rotation_required"):
        if rotation_due and current > rotation_due:
            state = "reference_rotation_required"
            blockers.append(_blocker("credential_reference_invalid", "rotation_overdue", "rotation_current", source="credential_rotation"))
        else:
            warnings.append(_warning("credential_expires_soon", "Rotation is required soon."))
    if not last_verified or current - last_verified > timedelta(hours=max_verification_age_hours):
        warnings.append(_warning("credential_verification_stale", "Credential reference metadata verification is stale."))
    decision = {
        "expiration_state": state,
        "issued_time": reference.get("issued_time"),
        "valid_from": reference.get("valid_from"),
        "expires_at": reference.get("expires_at"),
        "last_verified_time": reference.get("last_verified_time"),
        "rotation_required": bool(reference.get("rotation_required")),
        "rotation_due_date": reference.get("rotation_due_date"),
        "clock_skew_tolerance_seconds": 300,
        "blockers": blockers,
        "warnings": warnings,
        "expiration_digest": _digest({"state": state, "expires_at": reference.get("expires_at"), "rotation": reference.get("rotation_due_date")}, "render-expiration-"),
    }
    _audit(decision, "render_credential_expiration_checked", {"state": state})
    return _safe_success(expiration_decision=decision)


def validate_credential_reference(
    reference: Dict[str, Any],
    selected_service_id: str = "",
    environment: str = "preview",
    provider: str = "render",
    project_scope_digest: str = "",
    branch: str = "",
    deployment_type: str = "render_deployment",
    now: str = "",
) -> Dict[str, Any]:
    normalized_result = normalize_credential_reference(reference, now=now)
    if not normalized_result.get("ok"):
        return normalized_result
    ref = normalized_result["reference"]
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    if not ref.get("reference_id"):
        blockers.append(_blocker("missing_credential_reference", "missing", "reference_id_present", source="credential_reference"))
    if provider == "render" and ref.get("provider") not in {"render_credential_reference", "fixture_reference"}:
        blockers.append(_blocker("credential_reference_invalid", ref.get("provider", ""), "render_credential_reference", source="credential_reference"))
    if selected_service_id and ref.get("target_service") and selected_service_id != ref.get("target_service"):
        blockers.append(_blocker("credential_service_mismatch", ref.get("target_service", ""), selected_service_id, source="credential_binding"))
    if environment and ref.get("environment") and environment != ref.get("environment"):
        blockers.append(_blocker("credential_environment_mismatch", ref.get("environment", ""), environment, source="credential_binding"))
    if project_scope_digest and ref.get("project_scope_digest") and project_scope_digest != ref.get("project_scope_digest"):
        blockers.append(_blocker("service_mismatch", ref.get("project_scope_digest", ""), project_scope_digest, source="credential_binding"))
    if branch and ref.get("allowed_branch") and branch != ref.get("allowed_branch"):
        blockers.append(_blocker("service_mismatch", ref.get("allowed_branch", ""), branch, source="credential_binding"))
    if deployment_type and ref.get("allowed_deployment_type") and deployment_type != ref.get("allowed_deployment_type"):
        blockers.append(_blocker("service_mismatch", ref.get("allowed_deployment_type", ""), deployment_type, source="credential_binding"))
    scope = evaluate_credential_scope(ref)
    expiration = evaluate_credential_expiration(ref, now=now)
    blockers.extend(scope["scope_decision"].get("missing_scopes") and [_blocker("credential_scope_insufficient", "missing_scope", "minimum_deployment_scope", source="credential_scope")] or [])
    blockers.extend(expiration["expiration_decision"].get("blockers", []))
    warnings.extend(scope["scope_decision"].get("warnings", []))
    warnings.extend(expiration["expiration_decision"].get("warnings", []))
    state = "reference_ready_for_controlled_execution" if not blockers else "credential_reference_invalid"
    result = {"reference": ref, "reference_state": state, "blockers": blockers, "warnings": warnings}
    _audit(result, "render_credential_reference_validated" if not blockers else "render_credential_reference_blocked", {"blocker_count": len(blockers)})
    return _safe_success(validation=result)


def evaluate_network_authority(authority: Dict[str, Any], task_id: str = "", project_scope_digest: str = "", now: str = "") -> Dict[str, Any]:
    data = deepcopy(authority or {})
    requested = bool(data.get("requested", False))
    origin = str(data.get("origin") or "")
    methods = {str(item).upper() for item in data.get("methods", [])}
    current = _parse_time(now) or datetime.now(timezone.utc)
    expires_at = _parse_time(data.get("expires_at"))
    blockers: List[Dict[str, Any]] = []
    state = "network_not_requested"
    if not requested:
        blockers.append(_blocker("network_permission_missing", "network_not_requested", "explicit_network_authority", source="network_authority"))
    elif origin != ALLOWED_RENDER_ORIGIN:
        state = "network_origin_not_allowed"
        blockers.append(_blocker("network_origin_not_allowed", origin, ALLOWED_RENDER_ORIGIN, source="network_authority"))
    elif not methods or not methods <= ALLOWED_METHODS:
        state = "network_method_not_allowed"
        blockers.append(_blocker("network_origin_not_allowed", ",".join(sorted(methods)), ",".join(sorted(ALLOWED_METHODS)), source="network_authority"))
    elif project_scope_digest and data.get("project_scope_digest") and data.get("project_scope_digest") != project_scope_digest:
        state = "network_scope_mismatch"
        blockers.append(_blocker("network_scope_mismatch", str(data.get("project_scope_digest")), project_scope_digest, source="network_authority"))
    elif expires_at and current > expires_at:
        state = "network_duration_expired"
        blockers.append(_blocker("network_permission_missing", "expired", "active_authority", source="network_authority"))
    elif int(data.get("request_budget", 0) or 0) <= 0:
        state = "network_budget_exceeded"
        blockers.append(_blocker("network_permission_missing", "budget_exceeded", "positive_request_budget", source="network_authority"))
    else:
        state = "network_ready_for_controlled_execution"
    decision = {
        "network_state": state if blockers else "network_ready_for_controlled_execution",
        "dry_run_state": "network_ready_for_dry_run",
        "origin": origin,
        "methods": sorted(methods),
        "task_id": task_id or str(data.get("task_id") or ""),
        "project_scope_digest": project_scope_digest or str(data.get("project_scope_digest") or ""),
        "request_budget": int(data.get("request_budget", 0) or 0),
        "duration_expires_at": str(data.get("expires_at") or ""),
        "real_network_request_performed": False,
        "blockers": blockers,
        "warnings": [_warning("network_budget_narrow", "Network request budget is narrow.")] if 0 < int(data.get("request_budget", 0) or 0) <= 2 else [],
    }
    decision["network_authority_digest"] = _digest(decision, "render-network-authority-")
    _audit(decision, "render_network_authority_checked", {"state": decision["network_state"]})
    return _safe_success(network_decision=decision)


def _package_digest(package: Dict[str, Any]) -> str:
    data = {key: value for key, value in package.items() if key not in {"package_digest", "audit_events"}}
    return _digest(data, "render-readiness-package-")


def build_render_readiness_package(
    plan: Dict[str, Any],
    credential_reference: Dict[str, Any],
    network_authority: Optional[Dict[str, Any]] = None,
    task_id: str = "",
    environment: str = "preview",
    branch: str = "main",
    commit_metadata: Optional[Dict[str, Any]] = None,
    access_mode: str = "controlled_access",
    deployment_intent: bool = False,
    final_confirmation_state: str = "confirmation_missing",
    now: str = "",
) -> Dict[str, Any]:
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = [_warning("fake_transport_only", "MVP verifies fake/local transport only.", severity="normal")]
    if not plan:
        blockers.append(_blocker("missing_render_plan", "missing", "render_plan"))
    validation = validate_render_deployment_plan(plan, str(plan.get("plan_digest") or "")) if plan else _safe_failure("missing plan")
    if not validation.get("ok"):
        blockers.append(_blocker("invalid_render_plan_digest", "invalid", "valid_plan_digest", source="render_adapter"))
    if not plan.get("service_candidate_id"):
        blockers.append(_blocker("missing_service", "missing", "selected_service", source="render_adapter"))
    if not (deployment_intent or plan.get("deployment_intent")):
        blockers.append(_blocker("missing_deployment_intent", "missing", "explicit_intent", source="readiness_package"))
    scope_digest = _digest([plan.get("project_root"), plan.get("root_directory"), plan.get("service_candidate_id")], "scope-digest-")
    credential = validate_credential_reference(
        credential_reference,
        selected_service_id=str(plan.get("service_candidate_id") or ""),
        environment=environment,
        provider="render",
        project_scope_digest=scope_digest,
        branch=branch,
        deployment_type="render_deployment",
        now=now,
    )
    if not credential.get("ok"):
        blockers.append(_blocker("credential_reference_invalid", "secret_field_blocked", "metadata_only", source="credential_reference"))
        credential_validation = {"reference": {}, "blockers": blockers[-1:], "warnings": []}
    else:
        credential_validation = credential["validation"]
        blockers.extend(credential_validation.get("blockers", []))
        warnings.extend(credential_validation.get("warnings", []))
    network = evaluate_network_authority(network_authority or {}, task_id=task_id or plan.get("task_id", ""), project_scope_digest=scope_digest, now=now)
    blockers.extend(network["network_decision"].get("blockers", []))
    warnings.extend(network["network_decision"].get("warnings", []))
    if final_confirmation_state != "confirmation_granted":
        blockers.append(_blocker("final_confirmation_missing", final_confirmation_state, "confirmation_granted", source="confirmation_binding"))
    if not plan.get("rollback_policy", {}).get("rollback_supported"):
        blockers.append(_blocker("rollback_unavailable", "unavailable", "rollback_metadata_ready", source="render_adapter"))
    if not plan.get("url_verification_policy", {}).get("health_required", True):
        blockers.append(_blocker("verification_policy_incomplete", "health_not_required", "health_required", source="verification_policy"))
    if not plan.get("cleanup_policy", {}).get("owned_runtime_only", True):
        blockers.append(_blocker("cleanup_policy_incomplete", "unsafe_cleanup", "owned_runtime_only", source="cleanup_policy"))
    blockers.append(_blocker("production_execution_disabled", "feature_disabled", "trusted_policy_enabled", source="gateway_policy", retryable=False))
    commit = deepcopy(commit_metadata or {})
    if not commit.get("commit"):
        warnings.append(_warning("commit_not_pinned", "Commit/reference metadata is not pinned."))
    if branch not in {"main", "master", "production"}:
        warnings.append(_warning("branch_not_protected", "Branch is not a known protected branch."))
    if environment == "production":
        warnings.append(_warning("production_environment_selected", "Production environment selected.", severity="critical"))
    created = _parse_time(now) or datetime.now(timezone.utc)
    package = {
        "readiness_package_id": _digest([task_id or plan.get("task_id"), plan.get("render_plan_id"), created.isoformat()], "render-readiness-pkg-"),
        "task_id": task_id or plan.get("task_id", ""),
        "project_scope_digest": scope_digest,
        "render_plan_id": plan.get("render_plan_id"),
        "render_plan_digest": plan.get("plan_digest"),
        "gateway_policy_digest": _policy_digest(),
        "selected_service_id": plan.get("service_candidate_id"),
        "service_type": plan.get("service_type"),
        "environment": environment,
        "branch": branch,
        "commit_metadata": commit,
        "deployment_intent": bool(deployment_intent or plan.get("deployment_intent")),
        "access_mode": access_mode,
        "risk": "critical",
        "credential_reference_summary": credential_validation.get("reference", {}),
        "credential_scope_decision": evaluate_credential_scope(credential_validation.get("reference", {})).get("scope_decision", {}),
        "credential_expiration_decision": evaluate_credential_expiration(credential_validation.get("reference", {}), now=now).get("expiration_decision", {}),
        "network_authority_decision": network["network_decision"],
        "final_confirmation_state": final_confirmation_state,
        "rollback_readiness": plan.get("rollback_policy", {}),
        "health_verification_policy": plan.get("url_verification_policy", {}),
        "browser_scenario_policy": plan.get("browser_scenario_policy", {}),
        "cleanup_policy": plan.get("cleanup_policy", {}),
        "blocker_list": blockers,
        "warning_list": warnings,
        "next_safe_action": "Resolve blockers; production execution remains disabled in MVP." if blockers else "Issue readiness seal for dry-run.",
        "created_time": created.isoformat(),
        "expires_at": (created + timedelta(hours=2)).isoformat(),
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    package["package_digest"] = _package_digest(package)
    _audit(package, "render_readiness_package_created", {"blockers": len(blockers), "warnings": len(warnings)})
    for blocker in blockers:
        _audit(package, "render_readiness_blocker_added", blocker)
    for warning in warnings:
        _audit(package, "render_readiness_warning_added", warning)
    return _safe_success(readiness_package=package)


def validate_render_readiness_package(package: Dict[str, Any], now: str = "") -> Dict[str, Any]:
    if not isinstance(package, dict) or not package.get("readiness_package_id"):
        return _safe_failure("readiness package required")
    actual = _package_digest(package)
    if actual != package.get("package_digest"):
        return _safe_failure("readiness package digest mismatch", actual_digest=actual, expected_digest=package.get("package_digest"))
    expires = _parse_time(package.get("expires_at"))
    current = _parse_time(now) or datetime.now(timezone.utc)
    if expires and current > expires:
        return _safe_failure("readiness package expired", blocker=_blocker("seal_expired", "expired", "active_package", retryable=False))
    _audit(package, "render_readiness_package_validated", {"package_digest": actual})
    return _safe_success(valid=True, package_digest=actual)


def _seal_digest(seal: Dict[str, Any]) -> str:
    data = {key: value for key, value in seal.items() if key not in {"seal_digest", "audit_events"}}
    return _digest(data, "render-readiness-seal-digest-")


def issue_render_readiness_seal(package: Dict[str, Any], requested_level: str = "dry_run", now: str = "") -> Dict[str, Any]:
    validation = validate_render_readiness_package(package, now=now)
    created = _parse_time(now) or datetime.now(timezone.utc)
    blockers = list(package.get("blocker_list", []))
    non_production_blockers = [item for item in blockers if item.get("category") != "production_execution_disabled"]
    if not validation.get("ok") or non_production_blockers:
        status = "seal_blocked"
    elif requested_level == "controlled_execution":
        status = "seal_issued_for_controlled_execution"
    else:
        status = "seal_issued_for_dry_run"
    seal = {
        "seal_id": _digest([package.get("readiness_package_id"), package.get("package_digest"), created.isoformat()], "render-readiness-seal-"),
        "seal_type": "render_production_readiness_seal",
        "package_id": package.get("readiness_package_id"),
        "package_digest": package.get("package_digest"),
        "render_plan_digest": package.get("render_plan_digest"),
        "gateway_policy_digest": package.get("gateway_policy_digest"),
        "credential_reference_digest": package.get("credential_reference_summary", {}).get("credential_reference_digest"),
        "network_authority_digest": package.get("network_authority_decision", {}).get("network_authority_digest"),
        "service_binding_digest": _digest([package.get("selected_service_id"), package.get("environment"), package.get("branch")], "render-service-binding-"),
        "rollback_policy_digest": _digest(package.get("rollback_readiness", {}), "render-rollback-policy-"),
        "verification_policy_digest": _digest([package.get("health_verification_policy"), package.get("browser_scenario_policy")], "render-verification-policy-"),
        "issued_time": created.isoformat(),
        "expiry_time": (created + timedelta(hours=1)).isoformat(),
        "environment": package.get("environment"),
        "risk": package.get("risk", "critical"),
        "final_confirmation_requirement": "package_bound_confirmation_required",
        "seal_status": status,
        "real_execution_feature_enabled": False,
        "controlled_execution_note": "metadata ready only; real execution feature disabled" if status == "seal_issued_for_controlled_execution" else "",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    seal["seal_digest"] = _seal_digest(seal)
    _audit(seal, "render_readiness_seal_issued" if status.startswith("seal_issued") else "render_readiness_seal_blocked", {"seal_status": status})
    return _safe_success(seal=seal)


def validate_render_readiness_seal(seal: Dict[str, Any], package: Dict[str, Any], now: str = "") -> Dict[str, Any]:
    if not isinstance(seal, dict) or not isinstance(package, dict):
        return _safe_failure("seal and package are required")
    reasons: List[str] = []
    if _seal_digest(seal) != seal.get("seal_digest"):
        reasons.append("seal_digest_mismatch")
    if seal.get("package_digest") != package.get("package_digest"):
        reasons.append("package_digest_mismatch")
    if seal.get("render_plan_digest") != package.get("render_plan_digest"):
        reasons.append("plan_digest_mismatch")
    if seal.get("credential_reference_digest") != package.get("credential_reference_summary", {}).get("credential_reference_digest"):
        reasons.append("credential_reference_changed")
    if seal.get("network_authority_digest") != package.get("network_authority_decision", {}).get("network_authority_digest"):
        reasons.append("network_policy_changed")
    expected_service_binding = _digest([package.get("selected_service_id"), package.get("environment"), package.get("branch")], "render-service-binding-")
    if seal.get("service_binding_digest") != expected_service_binding:
        reasons.append("service_binding_changed")
    current = _parse_time(now) or datetime.now(timezone.utc)
    expiry = _parse_time(seal.get("expiry_time"))
    if expiry and current > expiry:
        reasons.append("seal_expired")
    valid = not reasons and seal.get("seal_status") in {"seal_issued_for_dry_run", "seal_issued_for_controlled_execution"}
    return _safe_success(valid=valid, seal_status=seal.get("seal_status") if valid else "seal_invalidated", invalidation_reasons=reasons)


def invalidate_render_readiness_seal(seal: Dict[str, Any], package: Optional[Dict[str, Any]] = None, changed_fields: Optional[List[str]] = None, now: str = "") -> Dict[str, Any]:
    reasons = list(changed_fields or [])
    if package:
        validation = validate_render_readiness_seal(seal, package, now=now)
        reasons.extend(validation.get("invalidation_reasons", []))
    invalidated = deepcopy(seal or {})
    invalidated["seal_status"] = "seal_invalidated" if reasons else invalidated.get("seal_status", "seal_not_issued")
    invalidated["invalidation_reasons"] = sorted(set(reasons))
    _audit(invalidated, "render_readiness_seal_invalidated", {"reasons": invalidated["invalidation_reasons"]})
    return _safe_success(seal=invalidated)


def bind_render_final_confirmation(package: Dict[str, Any], confirmation: Dict[str, Any], now: str = "") -> Dict[str, Any]:
    current = _parse_time(now) or datetime.now(timezone.utc)
    expires = _parse_time(confirmation.get("expires_at"))
    state = "confirmation_granted"
    if not confirmation.get("granted"):
        state = "confirmation_missing"
    elif confirmation.get("revoked"):
        state = "confirmation_revoked"
    elif expires and current > expires:
        state = "confirmation_expired"
    elif confirmation.get("package_digest") != package.get("package_digest"):
        state = "confirmation_digest_mismatch"
    elif confirmation.get("environment") and confirmation.get("environment") != package.get("environment"):
        state = "confirmation_scope_mismatch"
    binding = {
        "confirmation_state": state,
        "task_id": package.get("task_id"),
        "package_id": package.get("readiness_package_id"),
        "package_digest": package.get("package_digest"),
        "plan_digest": package.get("render_plan_digest"),
        "service_id": package.get("selected_service_id"),
        "environment": package.get("environment"),
        "branch": package.get("branch"),
        "commit_reference": package.get("commit_metadata", {}),
        "credential_reference_digest": package.get("credential_reference_summary", {}).get("credential_reference_digest"),
        "network_authority_digest": package.get("network_authority_decision", {}).get("network_authority_digest"),
        "risk": package.get("risk"),
        "expiration": confirmation.get("expires_at"),
        "binding_digest": _digest([package.get("package_digest"), confirmation.get("expires_at"), confirmation.get("granted")], "render-confirmation-"),
    }
    _audit(binding, "render_final_confirmation_bound" if state == "confirmation_granted" else "render_final_confirmation_invalidated", {"state": state})
    return _safe_success(confirmation=binding)


def authorize_gateway_execution_with_seal(request: Dict[str, Any], package: Dict[str, Any], seal: Dict[str, Any], transport_type: str = "fake_render_transport", now: str = "") -> Dict[str, Any]:
    validation = validate_render_readiness_seal(seal, package, now=now)
    if not validation.get("valid"):
        return _safe_failure("gateway execution blocked by readiness seal", blocked=True, reason="invalid_or_missing_seal", validation=validation)
    if request.get("render_plan_digest") != package.get("render_plan_digest"):
        return _safe_failure("gateway execution blocked by readiness seal", blocked=True, reason="plan_digest_mismatch")
    if transport_type == "fake_render_transport" and seal.get("seal_status") in {"seal_issued_for_dry_run", "seal_issued_for_controlled_execution"}:
        return _safe_success(allowed=True, seal_status=seal.get("seal_status"), real_execution_enabled=False)
    return _safe_failure("real Render execution remains blocked", blocked=True, reason="production_execution_disabled")


def summarize_render_readiness(package: Dict[str, Any], seal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    blockers = package.get("blocker_list", []) if isinstance(package, dict) else []
    warnings = package.get("warning_list", []) if isinstance(package, dict) else []
    return _safe_success(
        summary={
            "readiness_package_id": package.get("readiness_package_id") if isinstance(package, dict) else "",
            "package_digest": package.get("package_digest") if isinstance(package, dict) else "",
            "seal_id": seal.get("seal_id") if isinstance(seal, dict) else "",
            "seal_status": seal.get("seal_status") if isinstance(seal, dict) else "seal_not_issued",
            "credential_readiness": package.get("credential_reference_summary", {}).get("status", "") if isinstance(package, dict) else "",
            "network_readiness": package.get("network_authority_decision", {}).get("network_state", "") if isinstance(package, dict) else "",
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "production_ready": False,
            "next_safe_action": package.get("next_safe_action", "Build readiness package.") if isinstance(package, dict) else "Build readiness package.",
        }
    )


def get_safe_render_readiness_metadata(package: Dict[str, Any], seal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "credential_reference_id": package.get("credential_reference_summary", {}).get("reference_id"),
        "credential_provider": package.get("credential_reference_summary", {}).get("provider"),
        "scope_names": package.get("credential_scope_decision", {}).get("provided_scopes", []),
        "expiration_metadata": {
            "expires_at": package.get("credential_expiration_decision", {}).get("expires_at"),
            "last_verified_time": package.get("credential_expiration_decision", {}).get("last_verified_time"),
        },
        "service_environment_binding": {
            "service": package.get("selected_service_id"),
            "environment": package.get("environment"),
            "branch": package.get("branch"),
        },
        "readiness_package_id": package.get("readiness_package_id"),
        "readiness_package_digest": package.get("package_digest"),
        "blocker_categories": [item.get("category") for item in package.get("blocker_list", [])],
        "warning_categories": [item.get("category") for item in package.get("warning_list", [])],
        "seal_id": seal.get("seal_id") if isinstance(seal, dict) else "",
        "seal_status": seal.get("seal_status") if isinstance(seal, dict) else "seal_not_issued",
        "seal_digest": seal.get("seal_digest") if isinstance(seal, dict) else "",
        "network_authority_summary": package.get("network_authority_decision", {}),
        "final_confirmation_state": package.get("final_confirmation_state"),
        "risk": package.get("risk"),
        "resume_policy": "credential_revalidation_required; readiness_revalidation_required; seal_reissue_required; resume_requires_user_action",
        "safe_metadata_only": True,
    }


def restore_render_readiness_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = _redact(deepcopy(record or {}))
    restored["credential_revalidation_required"] = True
    restored["readiness_revalidation_required"] = True
    restored["seal_reissue_required"] = True
    restored["resume_requires_user_action"] = True
    restored["credential_resolved"] = False
    restored["seal_created"] = False
    restored["network_permission_opened"] = False
    restored["execution_started"] = False
    _audit(restored, "render_restore_requires_revalidation", {})
    return _safe_success(runtime=restored)


def get_render_credential_broker_status() -> Dict[str, Any]:
    return _safe_success(
        name="LuxCode Render Credential Reference Broker and Production Readiness Seal",
        status="ready",
        credential_reference_only=True,
        real_secret_resolver_enabled=False,
        real_render_execution_enabled=False,
        external_network_enabled=False,
        production_deployment_enabled=False,
        supported_reference_providers=REFERENCE_PROVIDERS,
    )
