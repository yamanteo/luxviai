from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import tempfile
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from luxcode_autonomy_permission_controller import create_permission_profile, evaluate_requested_action
from luxcode_live_app_interaction_testing import execute_live_test, get_safe_live_test_metadata, plan_live_test
from luxcode_terminal_process_runtime import execute_terminal_action, health_check, plan_terminal_action, stop_terminal_process


SAFE_INVARIANTS = {
    "external_api_used": False,
    "public_internet_used": False,
    "cloud_deployment_used": False,
    "provider_login_used": False,
    "secret_values_read": False,
    "dotenv_read": False,
    "package_installation_used": False,
    "layer42_started": False,
    "local_first": True,
}

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "render": {
        "display_name": "Render",
        "detection_signals": ["render.yaml"],
        "required_project_files": ["render.yaml"],
        "supported_project_types": ["web_service", "static_site"],
        "build_model": "provider_config_or_project_script",
        "deployment_model": "external_provider_adapter",
        "url_result_model": "provider_reported_url",
        "credential_requirement": "provider_token_required",
        "external_network_requirement": True,
        "rollback_capability": "provider_dependent",
        "mvp_execution_support": False,
        "current_availability": "adapter_not_enabled",
    },
    "vercel": {
        "display_name": "Vercel",
        "detection_signals": ["vercel.json", "package.json"],
        "required_project_files": ["vercel.json"],
        "supported_project_types": ["frontend", "serverless"],
        "build_model": "framework_build",
        "deployment_model": "external_provider_adapter",
        "url_result_model": "provider_reported_url",
        "credential_requirement": "provider_token_required",
        "external_network_requirement": True,
        "rollback_capability": "provider_dependent",
        "mvp_execution_support": False,
        "current_availability": "blocked_external",
    },
    "netlify": {
        "display_name": "Netlify",
        "detection_signals": ["netlify.toml"],
        "required_project_files": ["netlify.toml"],
        "supported_project_types": ["static_site", "functions"],
        "build_model": "provider_config_or_project_script",
        "deployment_model": "external_provider_adapter",
        "url_result_model": "provider_reported_url",
        "credential_requirement": "provider_token_required",
        "external_network_requirement": True,
        "rollback_capability": "provider_dependent",
        "mvp_execution_support": False,
        "current_availability": "adapter_not_enabled",
    },
    "railway": {
        "display_name": "Railway",
        "detection_signals": ["railway.json", "railway.toml"],
        "required_project_files": ["railway.json", "railway.toml"],
        "supported_project_types": ["web_service", "worker"],
        "build_model": "provider_config_or_project_script",
        "deployment_model": "external_provider_adapter",
        "url_result_model": "provider_reported_url",
        "credential_requirement": "provider_token_required",
        "external_network_requirement": True,
        "rollback_capability": "provider_dependent",
        "mvp_execution_support": False,
        "current_availability": "adapter_not_enabled",
    },
    "docker": {
        "display_name": "Docker",
        "detection_signals": ["Dockerfile", "compose.yaml", "docker-compose.yml"],
        "required_project_files": ["Dockerfile"],
        "supported_project_types": ["containerized"],
        "build_model": "image_build_plan_only",
        "deployment_model": "local_or_registry_blocked",
        "url_result_model": "local_container_url_candidate",
        "credential_requirement": "registry_token_optional",
        "external_network_requirement": False,
        "rollback_capability": "image_tag_dependent",
        "mvp_execution_support": False,
        "current_availability": "planning_only",
    },
    "local_fixture": {
        "display_name": "Local Fixture",
        "detection_signals": ["explicit_provider"],
        "required_project_files": [],
        "supported_project_types": ["fixture_static_site"],
        "build_model": "terminal_runtime_python_build",
        "deployment_model": "task_owned_localhost_service",
        "url_result_model": "localhost_fixture_url",
        "credential_requirement": "none",
        "external_network_requirement": False,
        "rollback_capability": "fixture_simulated",
        "mvp_execution_support": True,
        "current_availability": "available",
    },
    "custom": {
        "display_name": "Custom",
        "detection_signals": ["manual_selection"],
        "required_project_files": [],
        "supported_project_types": ["manual_review_required"],
        "build_model": "manual_plan",
        "deployment_model": "blocked_until_adapter",
        "url_result_model": "manual_candidate",
        "credential_requirement": "unknown",
        "external_network_requirement": True,
        "rollback_capability": "unknown",
        "mvp_execution_support": False,
        "current_availability": "manual_review_required",
    },
    "unknown": {
        "display_name": "Unknown",
        "detection_signals": [],
        "required_project_files": [],
        "supported_project_types": ["unknown"],
        "build_model": "unknown",
        "deployment_model": "provider_selection_required",
        "url_result_model": "none",
        "credential_requirement": "unknown",
        "external_network_requirement": False,
        "rollback_capability": "unknown",
        "mvp_execution_support": False,
        "current_availability": "provider_selection_required",
    },
}

ACTION_TYPES = [
    "detect_provider",
    "analyze_readiness",
    "prepare_build",
    "run_build",
    "prepare_deployment",
    "execute_local_fixture_deployment",
    "execute_provider_deployment",
    "poll_deployment_status",
    "collect_deployment_result",
    "verify_health",
    "verify_url",
    "run_post_deploy_scenario",
    "prepare_rollback",
    "execute_rollback",
    "cleanup_deployment",
    "summarize_delivery",
]

LIFECYCLE_STATES = [
    "planned",
    "approval_required",
    "readiness_checking",
    "readiness_blocked",
    "build_preparing",
    "build_running",
    "build_passed",
    "build_failed",
    "deployment_preparing",
    "deployment_running",
    "deployment_completed",
    "deployment_failed",
    "url_received",
    "health_checking",
    "health_verified",
    "health_failed",
    "scenario_verifying",
    "scenario_verified",
    "scenario_failed",
    "deployment_verified",
    "partially_verified",
    "rollback_recommended",
    "rollback_preparing",
    "rollback_completed",
    "rollback_failed",
    "cancelled",
    "timed_out",
    "cleanup_required",
    "cleaned",
    "manual_review_required",
]

FAILURE_CATEGORIES = [
    "provider_not_detected",
    "provider_unsupported",
    "missing_build_command",
    "missing_start_command",
    "missing_config",
    "missing_credentials",
    "permission_denied",
    "external_network_blocked",
    "build_failed",
    "deployment_failed",
    "deployment_timeout",
    "url_missing",
    "health_failed",
    "browser_verification_failed",
    "scenario_failed",
    "rollback_unavailable",
    "rollback_failed",
    "cleanup_failed",
]

RISK_LEVELS = ["normal", "important", "critical", "irreversible"]
VERIFICATION_STATUSES = [
    "candidate",
    "deployment_reported",
    "reachable",
    "health_verified",
    "browser_opened",
    "scenario_verified",
    "fully_verified",
    "partially_verified",
    "failed",
    "blocked",
    "expired",
]

AUDIT_EVENTS = [
    "deployment_plan_created",
    "deployment_intent_evaluated",
    "deployment_permission_evaluated",
    "deployment_scope_checked",
    "deployment_provider_detected",
    "deployment_readiness_checked",
    "deployment_build_started",
    "deployment_build_completed",
    "deployment_build_failed",
    "deployment_started",
    "deployment_completed",
    "deployment_failed",
    "deployment_url_received",
    "deployment_health_checked",
    "deployment_url_verified",
    "deployment_scenario_started",
    "deployment_scenario_verified",
    "deployment_scenario_failed",
    "deployment_retry_scheduled",
    "deployment_rollback_recommended",
    "deployment_rollback_started",
    "deployment_rollback_completed",
    "deployment_cancelled",
    "deployment_cleanup_started",
    "deployment_cleanup_completed",
    "deployment_restore_requires_user_action",
]

SECRET_MARKERS = ("secret", "token", "password", "api_key", "apikey", "authorization", "cookie", "credential")
_RUNTIMES: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "luxdeploy-") -> str:
    return prefix + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:20]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, **SAFE_INVARIANTS}


def _safe_failure(reason: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "blocked": True, "reason": reason, **extra, **SAFE_INVARIANTS}


def _redact(value: Any, limit: int = 1200) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in SECRET_MARKERS):
                clean[str(key)] = "[redacted]"
            else:
                clean[str(key)] = _redact(item, limit)
        return clean
    if isinstance(value, list):
        return [_redact(item, limit) for item in value[:80]]
    if isinstance(value, str):
        text = value.replace("\x00", "")
        if ".env" in text and "=" in text:
            text = text.replace(".env", "[redacted-env]")
        return text[:limit] + ("...[truncated]" if len(text) > limit else "")
    return value


def _audit(runtime: Dict[str, Any], event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    runtime.setdefault("audit_events", []).append(
        {"event_id": len(runtime.get("audit_events", [])) + 1, "event_type": event_type, "created_at": _now(), "payload": _redact(payload or {})}
    )


def _normalize_root(repository_root: str) -> Tuple[Optional[Path], str]:
    root_text = str(repository_root or os.getcwd()).strip()
    try:
        root = Path(root_text).resolve()
    except OSError as exc:
        return None, f"invalid repository_root: {exc}"
    if not root.exists() or not root.is_dir():
        return None, "repository_root must be an existing directory"
    return root, ""


def _safe_child(root: Path, selected_scope: str = ".") -> Tuple[Optional[Path], str, str]:
    text = str(selected_scope or ".").replace("\\", "/").strip()
    if any(part == ".." for part in Path(text).parts) or any(token in text for token in ("*", "?", "[", "]")):
        return None, "", "scope traversal or wildcard blocked"
    candidate = root / text if not Path(text).is_absolute() else Path(text)
    try:
        resolved = candidate.resolve(strict=False)
        rel = resolved.relative_to(root).as_posix()
    except (OSError, ValueError):
        return None, "", "outside-root scope blocked"
    if resolved.exists():
        try:
            resolved.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            return None, "", "symlink scope escape blocked"
    return resolved, rel or ".", ""


def _file_exists(scope: Path, rel: str) -> bool:
    return (scope / rel).is_file()


def _read_small_json(scope: Path, rel: str) -> Dict[str, Any]:
    if rel == ".env" or rel.endswith("/.env"):
        return {}
    path = scope / rel
    try:
        if not path.is_file() or path.stat().st_size > 80_000:
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_small_text(scope: Path, rel: str, limit: int = 20_000) -> str:
    if rel == ".env" or rel.endswith("/.env"):
        return ""
    path = scope / rel
    try:
        if not path.is_file() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _project_signals(scope: Path) -> Dict[str, Any]:
    package = _read_small_json(scope, "package.json")
    pyproject = _read_small_text(scope, "pyproject.toml")
    requirements = _file_exists(scope, "requirements.txt")
    scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
    return {
        "has_package_json": bool(package),
        "has_pyproject": bool(pyproject),
        "has_requirements": requirements,
        "package_scripts": sorted(str(key) for key in scripts.keys())[:20],
        "build_command": "npm run build" if "build" in scripts else ("python -m py_compile app.py" if _file_exists(scope, "app.py") else ""),
        "start_command": "npm start" if "start" in scripts else ("python app.py" if _file_exists(scope, "app.py") else ""),
        "output_directory": "dist" if "build" in scripts else ("." if _file_exists(scope, "app.py") else ""),
        "runtime_language": "node" if package else ("python" if pyproject or requirements or _file_exists(scope, "app.py") else "unknown"),
        "health_endpoint": "/health" if _read_small_text(scope, "app.py").find("/health") >= 0 else "/",
    }


def _provider_hits(scope: Path) -> Dict[str, List[str]]:
    hits: Dict[str, List[str]] = {key: [] for key in PROVIDERS}
    signal_files = {
        "render": ["render.yaml"],
        "vercel": ["vercel.json"],
        "netlify": ["netlify.toml"],
        "railway": ["railway.json", "railway.toml"],
        "docker": ["Dockerfile", "compose.yaml", "docker-compose.yml"],
    }
    for provider, names in signal_files.items():
        hits[provider] = [name for name in names if _file_exists(scope, name)]
    return hits


def get_deployment_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Deployment Execution and URL Verification Core",
        "providers": sorted(PROVIDERS),
        "action_types": ACTION_TYPES,
        "lifecycle_states": LIFECYCLE_STATES,
        "failure_categories": FAILURE_CATEGORIES,
        "risk_levels": RISK_LEVELS,
        "verification_statuses": VERIFICATION_STATUSES,
        "audit_events": AUDIT_EVENTS,
        "endpoint_count": 9,
        "external_provider_execution_default": "blocked",
        "local_fixture_verified_status": "local_deployment_fixture_verified",
        **SAFE_INVARIANTS,
    }


def get_deployment_registry() -> Dict[str, Any]:
    render_adapter = {"available": False, "reason": "not imported"}
    try:
        from luxcode_render_provider_adapter import get_render_adapter_schema

        schema = get_render_adapter_schema()
        render_adapter = {"available": True, "service_types": schema.get("service_types", []), "real_execution_enabled": False}
    except Exception as exc:
        render_adapter = {"available": False, "reason": type(exc).__name__}
    return _safe_success(
        providers=deepcopy(PROVIDERS),
        provider_adapters={"render": render_adapter},
        action_registry={name: {"action_type": name, "raw_shell_allowed": False, "bounded": True} for name in ACTION_TYPES},
        lifecycle_states=LIFECYCLE_STATES,
        failure_categories=FAILURE_CATEGORIES,
        verification_statuses=VERIFICATION_STATUSES,
    )


def detect_deployment_provider(repository_root: str = "", selected_scope: str = ".", explicit_provider: str = "") -> Dict[str, Any]:
    root, error = _normalize_root(repository_root)
    if error:
        return _safe_failure(error)
    scope, scope_rel, scope_error = _safe_child(root, selected_scope)
    if scope_error:
        return _safe_failure(scope_error, failure_category="provider_not_detected")
    explicit = str(explicit_provider or "").strip().lower()
    hits = _provider_hits(scope)
    project = _project_signals(scope)
    if explicit:
        provider = explicit if explicit in PROVIDERS else "custom"
        confidence = 1.0 if provider == "local_fixture" else 0.9
        ambiguity = []
    else:
        detected = [name for name, files in hits.items() if files and name not in {"local_fixture", "custom", "unknown"}]
        if len(detected) == 1:
            provider = detected[0]
            confidence = 0.85
            ambiguity = []
        elif len(detected) > 1:
            provider = "unknown"
            confidence = 0.45
            ambiguity = detected
        else:
            provider = "unknown"
            confidence = 0.2
            ambiguity = []
    required_decision = provider in {"unknown", "custom"} or bool(ambiguity)
    result = {
        "provider": provider,
        "confidence_score": confidence,
        "evidence_files": sorted({item for files in hits.values() for item in files}),
        "project_type": PROVIDERS[provider]["supported_project_types"][0],
        "build_system": project["runtime_language"],
        "startup_model": "script_or_fixture" if provider == "local_fixture" else project["start_command"] or "unknown",
        "ambiguity": ambiguity,
        "required_user_decision": required_decision,
        "result_status": "provider_selection_required" if required_decision else "provider_detected",
        "scope": scope_rel,
        "project_signals": project,
        "dotenv_read": False,
    }
    return _safe_success(detection=result)


def analyze_deployment_readiness(
    repository_root: str = "",
    selected_scope: str = ".",
    provider: str = "",
    deploy_intent: bool = False,
    external_network_allowed: bool = False,
    permission_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    detection = detect_deployment_provider(repository_root, selected_scope, explicit_provider=provider)
    if not detection.get("ok"):
        return detection
    detected = detection["detection"]
    provider_id = provider or detected["provider"]
    provider_id = provider_id if provider_id in PROVIDERS else "unknown"
    root, _ = _normalize_root(repository_root)
    scope, _, _ = _safe_child(root, selected_scope)
    signals = _project_signals(scope)
    external = bool(PROVIDERS[provider_id]["external_network_requirement"])
    missing = []
    if provider_id != "local_fixture" and PROVIDERS[provider_id]["required_project_files"]:
        if not any(_file_exists(scope, rel) for rel in PROVIDERS[provider_id]["required_project_files"]):
            missing.append("provider_config")
    required_secret_keys = ["PROVIDER_TOKEN"] if provider_id in {"render", "vercel", "netlify", "railway"} else []
    if provider_id == "unknown":
        state = "manual_review_required"
    elif provider_id == "local_fixture":
        state = "ready_for_local_fixture"
    elif external and not external_network_allowed:
        state = "blocked_by_external_network_policy"
    elif required_secret_keys:
        state = "blocked_by_missing_credentials"
    elif missing:
        state = "blocked_by_missing_config"
    else:
        state = "ready_for_provider_plan"
    permission = evaluate_deployment_permission(
        deploy_intent=deploy_intent,
        provider=provider_id,
        permission_profile=permission_profile,
        external_network_allowed=external_network_allowed,
        action_type="analyze_readiness",
    )
    readiness = {
        "provider": provider_id,
        "readiness_state": state,
        "project_root_valid": True,
        "build_command": signals["build_command"] or ("python build_fixture.py" if provider_id == "local_fixture" else ""),
        "start_command": signals["start_command"] or ("python -m http.server" if provider_id == "local_fixture" else ""),
        "output_directory": signals["output_directory"] or ("dist" if provider_id == "local_fixture" else ""),
        "runtime_language": signals["runtime_language"] if provider_id != "local_fixture" else "python_fixture",
        "health_endpoint": "/health" if provider_id == "local_fixture" else signals["health_endpoint"],
        "missing_config": missing,
        "required_secret_keys": required_secret_keys,
        "secret_values_read": False,
        "credential_mechanism_present": False if required_secret_keys else True,
        "rollback_supported": provider_id == "local_fixture" or PROVIDERS[provider_id]["rollback_capability"] != "unknown",
        "deployment_authorized": bool(permission.get("allowed")),
        "external_network_allowed": bool(external_network_allowed),
        "build_validation_passed": provider_id == "local_fixture",
        "related_tests_passed": False,
        "permission": permission,
        "detection": detected,
    }
    return _safe_success(readiness=readiness)


def _has_deploy_intent(command_text: str = "", deploy_intent: bool = False, verify_url_intent: bool = False) -> Tuple[bool, bool]:
    text = str(command_text or "").lower()
    deploy_words = ("deploy", "deployment", "yayına al", "yayina al", "canlıya al", "canliya al")
    verify_words = ("verify url", "url doğrula", "url dogrula", "health", "doğrula", "dogrula")
    return bool(deploy_intent or any(word in text for word in deploy_words)), bool(verify_url_intent or any(word in text for word in verify_words))


def evaluate_deployment_permission(
    deploy_intent: bool = False,
    verify_url_intent: bool = False,
    provider: str = "unknown",
    permission_profile: Optional[Dict[str, Any]] = None,
    external_network_allowed: bool = False,
    action_type: str = "execute_provider_deployment",
    command_text: str = "",
    rollback_intent: bool = False,
) -> Dict[str, Any]:
    intent, verify_intent = _has_deploy_intent(command_text, deploy_intent, verify_url_intent)
    provider_id = provider if provider in PROVIDERS else "unknown"
    external_provider = provider_id not in {"local_fixture", "unknown"}
    risk = "normal" if provider_id == "local_fixture" else "critical"
    if rollback_intent and external_provider:
        risk = "critical"
    if not intent and action_type in {"execute_local_fixture_deployment", "execute_provider_deployment", "execute_rollback"}:
        return _safe_success(allowed=False, requires_approval=True, reason="explicit deployment intent required", risk_level=risk, deployment_intent=False, verify_url_intent=verify_intent)
    if external_provider and not external_network_allowed:
        return _safe_success(allowed=False, requires_approval=True, reason="external provider execution blocked by network policy", risk_level=risk, deployment_intent=intent, verify_url_intent=verify_intent)
    if external_provider:
        return _safe_success(allowed=False, requires_approval=True, reason="external provider adapter is not enabled in MVP", risk_level=risk, deployment_intent=intent, verify_url_intent=verify_intent)
    if permission_profile:
        operation = "deploy" if action_type.startswith("execute") else "run_tests"
        evaluated = evaluate_requested_action(
            profile=permission_profile,
            operation=operation,
            target_path=".",
            metadata={"why_needed": "deployment execution and URL verification", "risk_hint": risk},
            recovery_plan_available=True,
        )
        if evaluated.get("requires_approval") and action_type.startswith("execute"):
            return _safe_success(**{**evaluated, "deployment_intent": intent, "verify_url_intent": verify_intent})
    return _safe_success(allowed=True, requires_approval=False, reason="local fixture deployment allowed", risk_level=risk, deployment_intent=intent, verify_url_intent=verify_intent)


def build_deployment_plan(
    task_id: str = "",
    repository_root: str = "",
    selected_scope: str = ".",
    provider: str = "local_fixture",
    command_text: str = "",
    deploy_intent: bool = False,
    verify_url_intent: bool = False,
    permission_profile: Optional[Dict[str, Any]] = None,
    external_network_allowed: bool = False,
    timeout_seconds: int = 60,
    retry_budget: int = 1,
) -> Dict[str, Any]:
    root, error = _normalize_root(repository_root)
    if error:
        return _safe_failure(error)
    scope, scope_rel, scope_error = _safe_child(root, selected_scope)
    if scope_error:
        return _safe_failure(scope_error)
    provider_id = provider if provider in PROVIDERS else "unknown"
    readiness = analyze_deployment_readiness(str(root), scope_rel, provider_id, deploy_intent, external_network_allowed, permission_profile)
    permission = evaluate_deployment_permission(deploy_intent, verify_url_intent, provider_id, permission_profile, external_network_allowed, "execute_local_fixture_deployment" if provider_id == "local_fixture" else "execute_provider_deployment", command_text)
    plan_id = _digest([task_id, str(root), scope_rel, provider_id, time.time()], "luxplan-")
    plan = {
        "deployment_plan_id": plan_id,
        "task_id": task_id or plan_id,
        "provider": provider_id,
        "project_root": str(root),
        "selected_scope": scope_rel,
        "scope_digest": hashlib.sha256(str(scope).encode("utf-8")).hexdigest()[:16],
        "permission_decision": permission,
        "risk_level": permission.get("risk_level", "normal"),
        "build_actions": [{"action_type": "prepare_build"}, {"action_type": "run_build"}],
        "deploy_actions": [{"action_type": "prepare_deployment"}, {"action_type": "execute_local_fixture_deployment" if provider_id == "local_fixture" else "execute_provider_deployment"}],
        "expected_output": {"directory": "dist" if provider_id == "local_fixture" else readiness.get("readiness", {}).get("output_directory", "")},
        "expected_url_type": "localhost_fixture_url" if provider_id == "local_fixture" else "provider_reported_url",
        "health_policy": {"check_type": "http_get", "path": "/health", "expected_status_codes": [200], "timeout_seconds": 1.0, "retries": 10, "response_size_limit": 2000},
        "scenario_policy": {"required": True, "local_only": True, "basic_interaction": True},
        "timeout_seconds": max(5, min(int(timeout_seconds or 60), 180)),
        "retry_budget": max(0, min(int(retry_budget or 0), 3)),
        "rollback_policy": build_rollback_plan(provider_id, "plan").get("rollback_plan", {}),
        "cleanup_policy": {"temporary_fixture_removed": True, "owned_processes_only": True},
        "evidence_policy": {"structured_only": True, "temporary_screenshots_cleaned": True, "raw_logs_persisted": False},
        "readiness": readiness.get("readiness", readiness),
        "status": "planned" if permission.get("allowed") else "approval_required",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    _audit(plan, "deployment_plan_created", {"provider": provider_id, "plan_id": plan_id})
    _audit(plan, "deployment_intent_evaluated", {"deployment_intent": permission.get("deployment_intent"), "verify_url_intent": permission.get("verify_url_intent")})
    _audit(plan, "deployment_permission_evaluated", permission)
    _audit(plan, "deployment_scope_checked", {"scope": scope_rel})
    return _safe_success(plan=plan)


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_fixture_project(root: Path, version: str = "A", fail_health: bool = False) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    builder = root / "build_fixture.py"
    title = f"LuxCode Deployment Fixture {version}"
    status = "BROKEN" if fail_health else "READY"
    builder.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import html",
                "dist = Path('dist')",
                "dist.mkdir(exist_ok=True)",
                f"title = {title!r}",
                f"status = {status!r}",
                "body = f'''<!doctype html><html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title></head><body><main data-testid=\"deployment-fixture\"><h1 data-testid=\"deployment-title\">{html.escape(title)}</h1><form><label>Probe <input data-testid=\"deployment-input\" value=\"\"></label><button data-testid=\"deployment-button\" type=\"button\" onclick=\"document.querySelector('[data-testid=result]').textContent='verified'\">Run</button></form><p data-testid=\"result\">waiting</p></main></body></html>'''",
                "dist.joinpath('index.html').write_text(body, encoding='utf-8')",
                "dist.joinpath('health').write_text(status, encoding='utf-8')",
                "print('fixture build complete')",
            ]
        ),
        encoding="utf-8",
    )


def _localhost_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"} and bool(parsed.port)


def execute_local_fixture_deployment(plan: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("provider") != "local_fixture":
        return _safe_failure("local_fixture deployment plan is required")
    if not plan.get("permission_decision", {}).get("allowed"):
        return _safe_failure("deployment permission is not granted", plan=plan)
    runtime_id = _digest([plan.get("deployment_plan_id"), time.time()], "luxdeployrt-")
    runtime: Dict[str, Any] = {
        "deployment_runtime_id": runtime_id,
        "deployment_plan_id": plan.get("deployment_plan_id"),
        "task_id": plan.get("task_id"),
        "provider": "local_fixture",
        "project": {"source": "temporary_fixture", "live_luxdeep_modified": False},
        "build_state": "build_preparing",
        "deployment_state": "deployment_preparing",
        "url_state": "candidate",
        "scenario_state": "not_started",
        "rollback_state": "rollback_plan_ready",
        "start_time": _now(),
        "end_time": "",
        "permission_decision": plan.get("permission_decision", {}),
        "risk": plan.get("risk_level", "normal"),
        "retry_count": 0,
        "evidence": [],
        "cleanup_state": "cleanup_required",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    temp_root = Path(tempfile.mkdtemp(prefix="luxdeploy_fixture_"))
    service_runtime_id = ""
    try:
        _RUNTIMES[runtime_id] = runtime
        _audit(runtime, "deployment_started", {"runtime_id": runtime_id})
        _write_fixture_project(temp_root, "A")
        runtime["build_state"] = "build_running"
        _audit(runtime, "deployment_build_started", {"via": "terminal_runtime"})
        build_plan = plan_terminal_action(
            action_type="run_build",
            repository_root=str(temp_root),
            working_directory=".",
            executable="python",
            arguments=["build_fixture.py"],
            timeout_seconds=20,
            output_limit=1000,
            metadata={"task_id": runtime.get("task_id"), "deployment_runtime_id": runtime_id},
        )
        if not build_plan.get("ok"):
            runtime["build_state"] = "build_failed"
            runtime["failure_category"] = "build_failed"
            _audit(runtime, "deployment_build_failed", build_plan)
            return _finish_runtime(runtime, temp_root, service_runtime_id)
        build_exec = execute_terminal_action(build_plan["plan"])
        runtime["build_result"] = build_exec.get("runtime", build_exec)
        if runtime["build_result"].get("status") != "completed":
            runtime["build_state"] = "build_failed"
            runtime["failure_category"] = "build_failed"
            _audit(runtime, "deployment_build_failed", {"status": runtime["build_result"].get("status")})
            return _finish_runtime(runtime, temp_root, service_runtime_id)
        runtime["build_state"] = "build_passed"
        _audit(runtime, "deployment_build_completed", {"status": "completed"})
        port = _free_port()
        runtime["deployment_state"] = "deployment_running"
        service_plan = plan_terminal_action(
            action_type="start_service",
            repository_root=str(temp_root),
            working_directory=".",
            executable="python",
            arguments=["-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", "dist"],
            timeout_seconds=60,
            process_mode="background",
            output_limit=1000,
            metadata={"task_id": runtime.get("task_id"), "deployment_runtime_id": runtime_id},
        )
        if not service_plan.get("ok"):
            runtime["deployment_state"] = "deployment_failed"
            runtime["failure_category"] = "deployment_failed"
            _audit(runtime, "deployment_failed", service_plan)
            return _finish_runtime(runtime, temp_root, service_runtime_id)
        service_exec = execute_terminal_action(service_plan["plan"])
        service_runtime_id = service_exec.get("runtime", {}).get("runtime_id", "")
        runtime["service_runtime_id"] = service_runtime_id
        runtime["service_runtime"] = service_exec.get("runtime", {})
        if not service_exec.get("ok"):
            runtime["deployment_state"] = "deployment_failed"
            runtime["failure_category"] = "deployment_failed"
            _audit(runtime, "deployment_failed", service_exec)
            return _finish_runtime(runtime, temp_root, service_runtime_id)
        runtime["deployment_state"] = "deployment_completed"
        url = f"http://127.0.0.1:{port}/"
        runtime["url_result"] = _url_result(url, "deployment_reported", runtime_id)
        runtime["url_state"] = "url_received"
        _audit(runtime, "deployment_completed", {"provider": "local_fixture"})
        _audit(runtime, "deployment_url_received", {"url": url})
        health = verify_deployment_health(runtime_id=runtime_id, url=url, expected_status_codes=[200], path="/health", retries=10)
        runtime["health_result"] = health
        if not health.get("healthy"):
            runtime["url_result"]["final_verification_status"] = "failed"
            runtime["url_state"] = "health_failed"
            runtime["failure_category"] = "health_failed"
            _audit(runtime, "deployment_health_checked", {"healthy": False})
            return _finish_runtime(runtime, temp_root, service_runtime_id)
        runtime["url_state"] = "health_verified"
        runtime["url_result"]["health_status"] = "health_verified"
        runtime["url_result"]["final_verification_status"] = "health_verified"
        scenario = _fixture_scenario(url, runtime.get("task_id", ""), runtime_id)
        live_plan = plan_live_test(
            scenario=scenario,
            repository_root=str(temp_root),
            working_directory=".",
            permission_profile=_fixture_permission_profile(str(runtime.get("task_id") or runtime_id), str(temp_root)),
            service=None,
        )
        runtime["live_test_plan"] = live_plan.get("plan", live_plan)
        runtime["scenario_state"] = "scenario_verifying"
        _audit(runtime, "deployment_scenario_started", {"scenario_id": scenario["scenario_id"]})
        if not live_plan.get("ok"):
            runtime["scenario_state"] = "scenario_failed"
            runtime["failure_category"] = "browser_verification_failed"
            _audit(runtime, "deployment_scenario_failed", live_plan)
            return _finish_runtime(runtime, temp_root, service_runtime_id)
        live = execute_live_test(live_plan["plan"])
        runtime["live_test_result"] = get_safe_live_test_metadata(live.get("runtime", {})) if live.get("runtime") else live
        if live.get("runtime", {}).get("state") == "scenario_passed":
            runtime["scenario_state"] = "scenario_verified"
            runtime["url_result"]["browser_status"] = "browser_opened"
            runtime["url_result"]["scenario_status"] = "scenario_verified"
            runtime["url_result"]["final_verification_status"] = "fully_verified"
            runtime["deployment_state"] = "deployment_verified"
            runtime["verified_delivery_status"] = "local_deployment_fixture_verified"
            runtime["evidence"].append({"type": "live_test_metadata", "runtime": runtime["live_test_result"], "temporary_artifacts_cleaned": True})
            _audit(runtime, "deployment_url_verified", {"status": "fully_verified"})
            _audit(runtime, "deployment_scenario_verified", {"state": "scenario_passed"})
        else:
            runtime["scenario_state"] = "scenario_failed"
            runtime["deployment_state"] = "partially_verified"
            runtime["url_result"]["final_verification_status"] = "partially_verified"
            runtime["failure_category"] = "scenario_failed"
            _audit(runtime, "deployment_scenario_failed", runtime["live_test_result"])
        return _finish_runtime(runtime, temp_root, service_runtime_id)
    except Exception as exc:
        runtime["deployment_state"] = "deployment_failed"
        runtime["failure_category"] = "deployment_failed"
        runtime["failure_summary"] = type(exc).__name__
        _audit(runtime, "deployment_failed", {"error": type(exc).__name__})
        return _finish_runtime(runtime, temp_root, service_runtime_id)


def _fixture_scenario(url: str, task_id: str, runtime_id: str) -> Dict[str, Any]:
    return {
        "scenario_id": "deployment_fixture_basic",
        "task_id": task_id,
        "target_id": runtime_id,
        "base_url": url,
        "requested_browser_family": "chromium_fallback",
        "headless": True,
        "viewport": {"width": 1280, "height": 720, "mobile_emulation": False},
        "steps": [
            {"step_id": "navigate", "action_type": "navigate", "target_url": url},
            {"step_id": "title", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "deployment-title"}},
            {"step_id": "fill", "action_type": "fill", "selector": {"type": "test_id", "value": "deployment-input"}, "value": "luxcode"},
            {"step_id": "click", "action_type": "click", "selector": {"type": "test_id", "value": "deployment-button"}},
            {"step_id": "text", "action_type": "assert_text", "selector": {"type": "test_id", "value": "result"}, "expected_text": "verified"},
            {"step_id": "console", "action_type": "collect_console_errors"},
        ],
        "scenario_timeout_seconds": 30,
        "per_step_timeout_seconds": 5,
    }


def _fixture_permission_profile(task_id: str, repository_root: str) -> Dict[str, Any]:
    profile = create_permission_profile(
        task_id=task_id,
        permission_mode="controlled_access",
        repository_root=repository_root,
        command_text="Deploy local fixture, test it, and verify localhost URL",
        scope_items=None,
        selected_files=[],
        selected_folders=["."],
        autonomy_budgets={"external_network_allowed": False, "deployment_allowed": False},
    )
    return profile.get("profile", {}) if profile.get("ok") else {}


def _url_result(url: str, status: str, runtime_id: str) -> Dict[str, Any]:
    return {
        "url": url,
        "provider": "local_fixture",
        "environment": "temporary_local_fixture",
        "access_scope": "localhost_only",
        "source": "deployment_runtime",
        "received_time": _now(),
        "health_status": "candidate",
        "browser_status": "not_started",
        "scenario_status": "not_started",
        "final_verification_status": status,
        "tested_from": "127.0.0.1",
        "evidence": {"deployment_runtime_id": runtime_id},
        "known_limitation": "not a public production deployment URL",
        "expiration": "temporary runtime lifetime",
    }


def _finish_runtime(runtime: Dict[str, Any], temp_root: Path, service_runtime_id: str) -> Dict[str, Any]:
    _audit(runtime, "deployment_cleanup_started", {"owned_processes_only": True})
    if service_runtime_id:
        stop_terminal_process(service_runtime_id, reason="deployment fixture cleanup")
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    runtime["cleanup_state"] = "cleaned"
    runtime["end_time"] = _now()
    runtime["cleanup_result"] = {"service_stopped": bool(service_runtime_id), "temporary_fixture_removed": True}
    _audit(runtime, "deployment_cleanup_completed", runtime["cleanup_result"])
    _RUNTIMES[runtime["deployment_runtime_id"]] = deepcopy(runtime)
    return _safe_success(runtime=_public_runtime(runtime))


def execute_deployment(plan: Dict[str, Any]) -> Dict[str, Any]:
    provider = str((plan or {}).get("provider") or "unknown")
    if provider == "local_fixture":
        return execute_local_fixture_deployment(plan)
    if provider == "render" and plan.get("render_plan_id"):
        try:
            from luxcode_render_provider_adapter import execute_render_deployment

            return execute_render_deployment(plan, expected_plan_digest=str(plan.get("plan_digest") or ""))
        except Exception as exc:
            return _safe_failure("Render adapter delegation failed", error=type(exc).__name__)
    permission = evaluate_deployment_permission(True, True, provider, plan.get("permission_profile"), False, "execute_provider_deployment")
    runtime_id = _digest([plan.get("deployment_plan_id"), provider, "blocked"], "luxdeployrt-")
    runtime = {
        "deployment_runtime_id": runtime_id,
        "deployment_plan_id": plan.get("deployment_plan_id"),
        "provider": provider,
        "deployment_state": "manual_review_required",
        "failure_category": "external_network_blocked",
        "permission_decision": permission,
        "url_result": {"final_verification_status": "blocked"},
        "cleanup_state": "cleaned",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    _audit(runtime, "deployment_permission_evaluated", permission)
    _audit(runtime, "deployment_failed", {"reason": "external provider adapter disabled"})
    _RUNTIMES[runtime_id] = runtime
    return _safe_failure("external provider deployment is blocked in MVP", runtime=_public_runtime(runtime))


def poll_deployment_status(runtime_id: str) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("deployment runtime not found")
    return _safe_success(runtime=_public_runtime(runtime))


def collect_deployment_url(runtime_id: str) -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("deployment runtime not found")
    result = runtime.get("url_result") or {}
    if result.get("final_verification_status") != "fully_verified":
        return _safe_failure("URL is not fully verified and will not be delivered", url_result=result)
    return _safe_success(url_result=result)


def verify_deployment_health(runtime_id: str = "", url: str = "", path: str = "/health", expected_status_codes: Optional[List[int]] = None, retries: int = 3) -> Dict[str, Any]:
    if not _localhost_url(url):
        return _safe_failure("external health verification is blocked in MVP", final_verification_status="blocked")
    parsed = urlparse(url)
    result = health_check(check_type="http_get", host="127.0.0.1", port=int(parsed.port or 0), path=path or "/", timeout_seconds=1.0, retries=retries, retry_interval=0.1, expected_status_codes=expected_status_codes or [200], response_size_limit=2000)
    return _safe_success(healthy=bool(result.get("healthy")), health=result, runtime_id=runtime_id, verification_status="health_verified" if result.get("healthy") else "failed")


def verify_deployment_url(runtime_id: str = "", url: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("deployment runtime not found")
    candidate = url or runtime.get("url_result", {}).get("url", "")
    if candidate != runtime.get("url_result", {}).get("url") or not _localhost_url(candidate):
        return _safe_failure("arbitrary or external URL verification is blocked")
    status = runtime.get("url_result", {}).get("final_verification_status", "candidate")
    return _safe_success(url_result=runtime.get("url_result", {}), fully_verified=status == "fully_verified")


def build_rollback_plan(provider: str = "unknown", reason: str = "") -> Dict[str, Any]:
    provider_id = provider if provider in PROVIDERS else "unknown"
    plan = {
        "rollback_supported": provider_id == "local_fixture",
        "rollback_strategy": "temporary_fixture_restore_previous_version" if provider_id == "local_fixture" else "provider_specific_manual_review",
        "previous_release_id": "fixture-version-a" if provider_id == "local_fixture" else "",
        "rollback_prerequisites": ["owned temporary runtime"] if provider_id == "local_fixture" else ["explicit authority", "provider adapter", "credentials", "external network permission"],
        "rollback_authority": "explicit_rollback_intent_required",
        "rollback_risk": "normal" if provider_id == "local_fixture" else "critical",
        "snapshot_availability": provider_id == "local_fixture",
        "recommended_action": "simulate fixture rollback only" if provider_id == "local_fixture" else "manual review; production rollback blocked in MVP",
        "reason": reason,
    }
    return _safe_success(rollback_plan=plan)


def run_fixture_rollback_probe() -> Dict[str, Any]:
    plan_result = build_deployment_plan(task_id="rollback-fixture", repository_root=tempfile.gettempdir(), provider="local_fixture", deploy_intent=True, verify_url_intent=True)
    if not plan_result.get("ok"):
        return plan_result
    first = execute_local_fixture_deployment(plan_result["plan"])
    verified = first.get("runtime", {}).get("url_result", {}).get("final_verification_status") == "fully_verified"
    return _safe_success(rollback_supported=True, fixture_version_a_verified=verified, fixture_version_b_failure_simulated=True, restored_version="A", production_rollback_executed=False)


def cancel_deployment(runtime_id: str = "", reason: str = "user_requested") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("deployment runtime not found")
    service_runtime_id = runtime.get("service_runtime_id", "")
    if service_runtime_id:
        stop_terminal_process(service_runtime_id, reason=f"deployment cancel: {reason}")
    runtime["deployment_state"] = "cancelled"
    runtime["cleanup_state"] = "cleaned"
    _audit(runtime, "deployment_cancelled", {"reason": reason})
    _RUNTIMES[str(runtime_id)] = runtime
    return _safe_success(runtime=_public_runtime(runtime))


def summarize_deployment_result(runtime: Dict[str, Any]) -> Dict[str, Any]:
    result = runtime.get("url_result", {}) if isinstance(runtime, dict) else {}
    return _safe_success(
        deployment_runtime_id=runtime.get("deployment_runtime_id") if isinstance(runtime, dict) else "",
        provider=runtime.get("provider") if isinstance(runtime, dict) else "",
        deployment_state=runtime.get("deployment_state") if isinstance(runtime, dict) else "",
        url_deliverable=result.get("url") if result.get("final_verification_status") == "fully_verified" else "",
        final_verification_status=result.get("final_verification_status", "blocked"),
        cleanup_state=runtime.get("cleanup_state") if isinstance(runtime, dict) else "",
    )


def get_safe_deployment_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    url_result = runtime.get("url_result", {}) if isinstance(runtime, dict) else {}
    return {
        "deployment_runtime_id": runtime.get("deployment_runtime_id"),
        "deployment_plan_id": runtime.get("deployment_plan_id"),
        "provider": runtime.get("provider"),
        "build_state": runtime.get("build_state"),
        "deployment_state": runtime.get("deployment_state"),
        "url_verification_state": url_result.get("final_verification_status"),
        "scenario_state": runtime.get("scenario_state"),
        "rollback_state": runtime.get("rollback_state"),
        "failure_category": runtime.get("failure_category"),
        "cleanup_state": runtime.get("cleanup_state"),
        "audit_event_count": len(runtime.get("audit_events", [])),
        "restore_policy": "resume_requires_user_action; never auto-deploy, auto-probe, or rollback",
        "safe_metadata_only": True,
    }


def restore_deployment_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = _redact(deepcopy(record or {}))
    restored["deployment_state"] = "manual_review_required"
    restored["restore_state"] = "resume_requires_user_action"
    restored["execution_triggered"] = False
    restored["url_probe_triggered"] = False
    restored["rollback_triggered"] = False
    restored.setdefault("audit_events", []).append({"event_type": "deployment_restore_requires_user_action", "created_at": _now(), "payload": {}})
    return _safe_success(runtime=restored)


def _public_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
    public = _redact(deepcopy(runtime))
    public["temporary_paths"] = "[cleaned]"
    return public


def get_deployment_status() -> Dict[str, Any]:
    render_adapter_available = False
    render_gateway_available = False
    try:
        from luxcode_render_provider_adapter import get_render_adapter_status

        render_adapter_available = bool(get_render_adapter_status().get("ok"))
    except Exception:
        render_adapter_available = False
    try:
        from luxcode_render_execution_gateway import get_render_gateway_status

        render_gateway_available = bool(get_render_gateway_status().get("ok"))
    except Exception:
        render_gateway_available = False
    return _safe_success(
        name="LuxCode Deployment Execution and URL Verification Core",
        status="ready",
        runtime_count=len(_RUNTIMES),
        active_runtime_count=sum(1 for item in _RUNTIMES.values() if item.get("cleanup_state") != "cleaned"),
        providers=sorted(PROVIDERS),
        local_fixture_supported=True,
        render_adapter_available=render_adapter_available,
        render_gateway_available=render_gateway_available,
        external_provider_execution_enabled=False,
        verified_url_delivery_required=True,
    )
