from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from luxcode_deployment_execution_url_verification import (
    build_deployment_plan,
    build_rollback_plan,
    execute_deployment,
    verify_deployment_url,
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

SERVICE_TYPES: Dict[str, Dict[str, Any]] = {
    "web_service": {
        "runtime_model": "long_running_http",
        "required_config": ["name", "type", "buildCommand", "startCommand"],
        "build_command_policy": "required",
        "start_command_policy": "required",
        "output_directory_policy": "optional",
        "health_policy": "http_path_required_or_default",
        "url_expectation": "service_url",
        "environment_requirement_model": "key_names_only",
        "deployment_support": "fake_execution",
        "rollback_expectation": "previous_deploy_or_manual",
        "current_mvp_availability": "readiness_and_fake_execution",
    },
    "static_site": {
        "runtime_model": "static_publish",
        "required_config": ["name", "type", "buildCommand", "staticPublishPath"],
        "build_command_policy": "recommended",
        "start_command_policy": "not_applicable",
        "output_directory_policy": "required",
        "health_policy": "root_path",
        "url_expectation": "static_site_url",
        "environment_requirement_model": "key_names_only",
        "deployment_support": "fake_execution",
        "rollback_expectation": "previous_static_release",
        "current_mvp_availability": "readiness_and_fake_execution",
    },
    "background_worker": {"runtime_model": "worker", "deployment_support": "blocked_unsupported", "current_mvp_availability": "planning_only"},
    "cron_job": {"runtime_model": "scheduled_job", "deployment_support": "blocked_unsupported", "current_mvp_availability": "planning_only"},
    "private_service": {"runtime_model": "private_network_service", "deployment_support": "blocked_unsupported", "current_mvp_availability": "planning_only"},
    "postgres": {"runtime_model": "managed_database", "deployment_support": "blocked_unsupported", "current_mvp_availability": "planning_only"},
    "redis": {"runtime_model": "managed_cache", "deployment_support": "blocked_unsupported", "current_mvp_availability": "planning_only"},
    "unknown": {"runtime_model": "unknown", "deployment_support": "blocked_selection_required", "current_mvp_availability": "manual_review_required"},
}

READINESS_STATES = [
    "render_detected",
    "render_service_selection_required",
    "render_config_invalid",
    "render_build_unresolved",
    "render_start_unresolved",
    "render_environment_incomplete",
    "render_credentials_required",
    "render_external_network_permission_required",
    "render_final_confirmation_required",
    "render_ready_for_dry_run",
    "render_ready_for_controlled_deployment",
    "render_execution_blocked",
]

LIFECYCLE_STATES = [
    "render_plan_created",
    "render_service_selected",
    "render_readiness_checking",
    "render_readiness_blocked",
    "render_dry_run_ready",
    "render_dry_run_running",
    "render_dry_run_completed",
    "render_deployment_preparing",
    "render_deployment_waiting_confirmation",
    "render_deployment_running",
    "render_deployment_building",
    "render_deployment_live",
    "render_deployment_failed",
    "render_url_received",
    "render_health_checking",
    "render_health_verified",
    "render_health_failed",
    "render_scenario_verifying",
    "render_scenario_verified",
    "render_scenario_failed",
    "render_fully_verified",
    "render_partially_verified",
    "render_cancelled",
    "render_timed_out",
    "render_rollback_recommended",
    "render_cleanup_completed",
    "render_manual_review_required",
]

ACTION_TYPES = [
    "detect_render",
    "parse_render_config",
    "select_render_service",
    "analyze_render_readiness",
    "build_render_plan",
    "validate_render_plan",
    "prepare_render_dry_run",
    "execute_render_dry_run",
    "prepare_render_deployment",
    "execute_render_deployment",
    "poll_render_deployment",
    "collect_render_url",
    "verify_render_health",
    "verify_render_url",
    "prepare_render_rollback",
    "cancel_render_deployment",
    "cleanup_render_runtime",
    "summarize_render_result",
]

FAILURE_CATEGORIES = [
    "render_not_detected",
    "render_config_invalid",
    "render_service_unsupported",
    "render_service_selection_required",
    "render_build_unresolved",
    "render_start_unresolved",
    "render_environment_incomplete",
    "blocked_by_missing_credentials",
    "blocked_by_external_network_policy",
    "blocked_by_final_confirmation",
    "plan_digest_mismatch",
    "adapter_execution_not_enabled",
    "fake_build_failed",
    "fake_deployment_failed",
    "fake_deployment_timeout",
    "fake_url_missing",
    "fake_health_failed",
    "fake_scenario_failed",
    "render_cancelled",
    "render_rollback_recommended",
]

CREDENTIAL_STATES = [
    "not_configured",
    "reference_available",
    "reference_expired",
    "scope_insufficient",
    "manual_setup_required",
    "verification_required",
]

AUDIT_EVENTS = [
    "render_detection_started",
    "render_detected",
    "render_config_parsed",
    "render_service_candidates_created",
    "render_service_selected",
    "render_readiness_checked",
    "render_readiness_blocked",
    "render_plan_created",
    "render_plan_validated",
    "render_permission_evaluated",
    "render_credential_reference_checked",
    "render_network_permission_checked",
    "render_final_confirmation_requested",
    "render_dry_run_started",
    "render_dry_run_completed",
    "render_deployment_blocked",
    "render_deployment_started",
    "render_deployment_status_polled",
    "render_url_received",
    "render_health_verified",
    "render_scenario_verified",
    "render_deployment_failed",
    "render_cancelled",
    "render_rollback_recommended",
    "render_cleanup_completed",
    "render_restore_requires_user_action",
]

SECRET_MARKERS = ("secret", "token", "password", "api_key", "apikey", "authorization", "cookie", "credential", "private_key")
_RUNTIMES: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "luxrender-") -> str:
    return prefix + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:20]


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, **SAFE_INVARIANTS}


def _safe_failure(reason: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "blocked": True, "reason": reason, **extra, **SAFE_INVARIANTS}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            lowered = str(key).lower()
            clean[str(key)] = "[redacted]" if any(marker in lowered for marker in SECRET_MARKERS) else _redact(item)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value[:120]]
    if isinstance(value, str):
        text = value.replace("\x00", "")
        if ".env" in text and "=" in text:
            text = text.replace(".env", "[redacted-env]")
        return text[:1200] + ("...[truncated]" if len(text) > 1200 else "")
    return value


def _audit(target: Dict[str, Any], event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
    target.setdefault("audit_events", []).append({"event_id": len(target.get("audit_events", [])) + 1, "event_type": event_type, "created_at": _now(), "payload": _redact(payload or {})})


def _root(repository_root: str = "") -> Tuple[Optional[Path], str]:
    try:
        root = Path(repository_root or os.getcwd()).resolve()
    except OSError as exc:
        return None, f"invalid repository_root: {exc}"
    if not root.exists() or not root.is_dir():
        return None, "repository_root must be an existing directory"
    return root, ""


def _scope(root: Path, selected_scope: str = ".") -> Tuple[Optional[Path], str, str]:
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


def _file(scope: Path, name: str) -> bool:
    return (scope / name).is_file()


def _read_text(scope: Path, name: str, limit: int = 80_000) -> str:
    if name == ".env" or name.endswith("/.env"):
        return ""
    path = scope / name
    try:
        if not path.is_file() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _read_json(scope: Path, name: str) -> Dict[str, Any]:
    try:
        return json.loads(_read_text(scope, name, 80_000) or "{}")
    except Exception:
        return {}


def _service_type(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {"web": "web_service", "static": "static_site", "pserv": "private_service", "worker": "background_worker", "cron": "cron_job"}
    return aliases.get(normalized, normalized if normalized in SERVICE_TYPES else "unknown")


def _yaml_scalar(value: str) -> Any:
    text = value.strip().strip("\"'")
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if text in {"", "null", "~"}:
        return ""
    return text


def _parse_render_yaml(text: str) -> Dict[str, Any]:
    if not text.strip():
        return {"valid": False, "services": [], "error": "empty render config"}
    if "!!python" in text or "!!" in text:
        return {"valid": False, "services": [], "error": "unsafe yaml tag blocked"}
    if text.count("&") + text.count("*") > 20:
        return {"valid": False, "services": [], "error": "yaml anchor or alias limit exceeded"}
    services: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    in_services = False
    in_env = False
    unknown_fields: Dict[str, Any] = {}
    for raw in text.splitlines()[:500]:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("services:"):
            in_services = True
            continue
        if stripped.startswith("envVars:"):
            in_env = True
            continue
        if in_env and indent > 4 and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item.startswith("key:") and current is not None:
                current.setdefault("environment_key_names", []).append(str(_yaml_scalar(item.split(":", 1)[1])).strip())
            continue
        if in_services and stripped.startswith("- "):
            if current:
                services.append(current)
            current = {"environment_key_names": [], "unknown_fields": {}}
            in_env = False
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                key, value = rest.split(":", 1)
                current[key.strip()] = _yaml_scalar(value)
            continue
        if current is None:
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                unknown_fields[key.strip()] = _yaml_scalar(value)
            continue
        if in_env and stripped.startswith("key:"):
            current.setdefault("environment_key_names", []).append(str(_yaml_scalar(stripped.split(":", 1)[1])).strip())
            continue
        if indent <= 4:
            in_env = False
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            if key in {"name", "type", "runtime", "region", "branch", "rootDir", "buildCommand", "startCommand", "staticPublishPath", "healthCheckPath", "autoDeploy", "plan"}:
                current[key] = _yaml_scalar(value)
            elif key == "key":
                current.setdefault("environment_key_names", []).append(str(_yaml_scalar(value)).strip())
            else:
                current.setdefault("unknown_fields", {})[key] = _yaml_scalar(value)
    if current:
        services.append(current)
    names = [str(service.get("name", "")) for service in services if service.get("name")]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    normalized = []
    for index, service in enumerate(services):
        service_type = _service_type(str(service.get("type", "")))
        normalized.append(
            {
                "service_candidate_id": _digest([service.get("name"), service_type, index], "render-svc-"),
                "service_name": str(service.get("name") or f"service-{index + 1}"),
                "service_type": service_type,
                "runtime": str(service.get("runtime") or ""),
                "region": str(service.get("region") or ""),
                "branch": str(service.get("branch") or ""),
                "root_directory": str(service.get("rootDir") or "."),
                "build_command": str(service.get("buildCommand") or ""),
                "start_command": str(service.get("startCommand") or ""),
                "publish_directory": str(service.get("staticPublishPath") or ""),
                "health_path": str(service.get("healthCheckPath") or ("/" if service_type == "static_site" else "/health")),
                "auto_deploy": service.get("autoDeploy", ""),
                "plan": str(service.get("plan") or ""),
                "environment_key_names": sorted({key for key in service.get("environment_key_names", []) if key}),
                "unknown_fields": _redact(service.get("unknown_fields", {})),
            }
        )
    return {"valid": True, "services": normalized, "duplicate_service_names": duplicates, "unknown_fields": _redact(unknown_fields), "unsafe_loader_used": False, "raw_file_logged": False}


def _project_mapping(scope: Path) -> Dict[str, Any]:
    package = _read_json(scope, "package.json")
    app_py = _read_text(scope, "app.py")
    pyproject = _read_text(scope, "pyproject.toml")
    requirements = _read_text(scope, "requirements.txt")
    docker = _file(scope, "Dockerfile")
    scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
    framework = "unknown"
    service_type = "unknown"
    build = ""
    start = ""
    publish = ""
    health = "/health"
    assumptions: List[str] = []
    missing: List[str] = []
    if "FastAPI" in app_py or "fastapi" in requirements.lower() or "fastapi" in pyproject.lower():
        framework, service_type, build, start = "fastapi", "web_service", "python -m py_compile app.py", "uvicorn app:app --host 0.0.0.0 --port $PORT"
    elif "Flask" in app_py or "flask" in requirements.lower():
        framework, service_type, build, start = "flask", "web_service", "python -m py_compile app.py", "gunicorn app:app"
    elif "django" in requirements.lower() or "django" in pyproject.lower():
        framework, service_type, build, start = "django", "web_service", "python manage.py collectstatic --noinput", "gunicorn project.wsgi"
    elif package:
        deps = " ".join(list((package.get("dependencies") or {}).keys()) + list((package.get("devDependencies") or {}).keys())).lower()
        if "next" in deps:
            framework, service_type = "nextjs", "web_service"
        elif "express" in deps:
            framework, service_type = "express", "web_service"
        elif "vite" in deps or "react" in deps:
            framework, service_type, publish = "static", "static_site", "dist"
        else:
            framework, service_type = "node", "web_service"
        build = "npm run build" if "build" in scripts else ""
        start = "npm start" if "start" in scripts and service_type == "web_service" else ""
    elif _file(scope, "index.html"):
        framework, service_type, publish, health = "plain_static", "static_site", ".", "/"
    elif docker:
        framework, service_type = "docker", "web_service"
        assumptions.append("Dockerfile detected; Render native Docker service plan only")
    if service_type == "web_service" and not start:
        missing.append("start_command")
    if service_type == "static_site" and not publish:
        missing.append("publish_directory")
    return {
        "detected_framework": framework,
        "recommended_service_type": service_type,
        "recommended_build_command": build,
        "recommended_start_command": start,
        "recommended_health_path": health,
        "recommended_root_directory": ".",
        "recommended_publish_directory": publish,
        "confidence": 0.85 if framework != "unknown" else 0.25,
        "assumptions": assumptions,
        "missing_decisions": missing,
        "direct_execution_command": False,
    }


def _environment_requirements(scope: Path, parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    keys = set()
    for service in parsed.get("services", []):
        keys.update(service.get("environment_key_names", []))
    for rel in ["app.py", "settings.py", "config.py", "package.json", "render.yaml", "render.yml"]:
        text = _read_text(scope, rel, 50_000)
        for match in re.findall(r"\b[A-Z][A-Z0-9_]{2,60}\b", text):
            if any(marker.upper() in match for marker in ("KEY", "TOKEN", "SECRET", "DATABASE_URL", "API")):
                keys.add(match)
    return [
        {
            "key_name": key,
            "required": True,
            "source_evidence": "render_config_or_code_key_reference",
            "classification": "secret" if any(marker.upper() in key for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")) else "non_secret_or_provider_managed",
            "provider_managed_possible": key in {"DATABASE_URL", "REDIS_URL"},
            "user_action_required": True,
            "value_status": "unknown",
        }
        for key in sorted(keys)
    ][:50]


def get_render_adapter_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Render Provider Adapter",
        "provider": "render",
        "service_types": sorted(SERVICE_TYPES),
        "readiness_states": READINESS_STATES,
        "lifecycle_states": LIFECYCLE_STATES,
        "action_types": ACTION_TYPES,
        "failure_categories": FAILURE_CATEGORIES,
        "credential_states": CREDENTIAL_STATES,
        "audit_events": AUDIT_EVENTS,
        "endpoint_count": 10,
        "real_render_execution_default": "blocked",
        "fake_result_label": "fake_render_deployment_verified",
        **SAFE_INVARIANTS,
    }


def get_render_adapter_registry() -> Dict[str, Any]:
    return _safe_success(
        provider="render",
        service_types=deepcopy(SERVICE_TYPES),
        action_registry={action: {"action_type": action, "raw_provider_command_allowed": False, "raw_http_request_allowed": False} for action in ACTION_TYPES},
        lifecycle_states=LIFECYCLE_STATES,
        readiness_states=READINESS_STATES,
    )


def parse_render_configuration(repository_root: str = "", selected_scope: str = ".") -> Dict[str, Any]:
    root, error = _root(repository_root)
    if error:
        return _safe_failure(error)
    scope, scope_rel, scope_error = _scope(root, selected_scope)
    if scope_error:
        return _safe_failure(scope_error)
    config_name = "render.yaml" if _file(scope, "render.yaml") else ("render.yml" if _file(scope, "render.yml") else "")
    if not config_name:
        return _safe_success(config_present=False, parsed={"valid": False, "services": [], "error": "render config not found"}, scope=scope_rel)
    parsed = _parse_render_yaml(_read_text(scope, config_name))
    parsed["config_file"] = config_name
    parsed["scope"] = scope_rel
    parsed["environment_requirements"] = _environment_requirements(scope, parsed)
    return _safe_success(config_present=True, parsed=parsed)


def build_render_service_candidates(repository_root: str = "", selected_scope: str = ".") -> Dict[str, Any]:
    root, error = _root(repository_root)
    if error:
        return _safe_failure(error)
    scope, scope_rel, scope_error = _scope(root, selected_scope)
    if scope_error:
        return _safe_failure(scope_error)
    parsed = parse_render_configuration(str(root), scope_rel).get("parsed", {})
    mapping = _project_mapping(scope)
    candidates = list(parsed.get("services", []))
    if not candidates and mapping["recommended_service_type"] != "unknown":
        candidates.append(
            {
                "service_candidate_id": _digest([scope_rel, mapping["detected_framework"]], "render-svc-"),
                "service_name": "detected-project-service",
                "service_type": mapping["recommended_service_type"],
                "runtime": mapping["detected_framework"],
                "region": "",
                "branch": "",
                "root_directory": mapping["recommended_root_directory"],
                "build_command": mapping["recommended_build_command"],
                "start_command": mapping["recommended_start_command"],
                "publish_directory": mapping["recommended_publish_directory"],
                "health_path": mapping["recommended_health_path"],
                "environment_key_names": [],
                "source": "project_mapping",
            }
        )
    return _safe_success(service_candidates=candidates, candidate_count=len(candidates), project_mapping=mapping, scope=scope_rel)


def detect_render_configuration(repository_root: str = "", selected_scope: str = ".") -> Dict[str, Any]:
    root, error = _root(repository_root)
    if error:
        return _safe_failure(error)
    scope, scope_rel, scope_error = _scope(root, selected_scope)
    if scope_error:
        return _safe_failure(scope_error)
    evidence = [name for name in ["render.yaml", "render.yml", "Dockerfile", "package.json", "requirements.txt", "pyproject.toml"] if _file(scope, name)]
    render_text = " ".join(_read_text(scope, rel, 20_000).lower() for rel in ["README.md", "package.json", "pyproject.toml"] if _file(scope, rel))
    detected = bool({"render.yaml", "render.yml"} & set(evidence)) or "render" in render_text
    candidates = build_render_service_candidates(str(root), scope_rel)
    service_candidates = candidates.get("service_candidates", [])
    selected = service_candidates[0] if len(service_candidates) == 1 else {}
    ambiguity = len(service_candidates) > 1
    state = "render_detected" if detected and selected else ("render_service_selection_required" if detected or ambiguity else "render_execution_blocked")
    return _safe_success(
        detection={
            "render_detected": detected,
            "confidence": 0.9 if {"render.yaml", "render.yml"} & set(evidence) else (0.55 if detected else 0.2),
            "evidence_files": evidence,
            "service_candidates": service_candidates,
            "ambiguous_configuration": ambiguity,
            "selected_service_candidate": selected,
            "user_decision_required": ambiguity or not selected,
            "provider_readiness_state": state,
            "scope": scope_rel,
            "dotenv_read": False,
        }
    )


def select_render_service(repository_root: str = "", selected_scope: str = ".", service_candidate_id: str = "", service_name: str = "") -> Dict[str, Any]:
    candidates = build_render_service_candidates(repository_root, selected_scope)
    if not candidates.get("ok"):
        return candidates
    items = candidates.get("service_candidates", [])
    selected = next((item for item in items if service_candidate_id and item.get("service_candidate_id") == service_candidate_id), None)
    selected = selected or next((item for item in items if service_name and item.get("service_name") == service_name), None)
    selected = selected or (items[0] if len(items) == 1 else None)
    if not selected:
        return _safe_failure("render service selection required", service_candidates=items, failure_category="render_service_selection_required")
    return _safe_success(selected_service=selected)


def _credential_reference(reference_id: str = "", availability: str = "not_configured", scope: str = "deploy", **_extra: Any) -> Dict[str, Any]:
    state = availability if availability in CREDENTIAL_STATES else ("reference_available" if reference_id else "not_configured")
    return {
        "credential_provider": "user_managed_reference",
        "reference_id": reference_id,
        "availability": state,
        "scope": scope,
        "expiration_metadata": "unknown",
        "last_verified_time": "",
        "user_confirmation_required": True,
        "secret_value_present": False if reference_id else "unknown",
        "persistence_policy": "reference_metadata_only_no_secret_value",
    }


def analyze_render_readiness(
    repository_root: str = "",
    selected_scope: str = ".",
    service_candidate_id: str = "",
    credential_reference: Optional[Dict[str, Any]] = None,
    external_network_allowed: bool = False,
    deployment_intent: bool = False,
    final_confirmation: bool = False,
) -> Dict[str, Any]:
    selection = select_render_service(repository_root, selected_scope, service_candidate_id)
    detection = detect_render_configuration(repository_root, selected_scope)
    credential = _credential_reference(**(credential_reference or {}))
    if not selection.get("ok"):
        state = "render_service_selection_required"
        blockers = ["service_selection"]
        service = {}
    else:
        service = selection["selected_service"]
        blockers = []
        service_type = service.get("service_type", "unknown")
        if service_type not in {"web_service", "static_site"}:
            blockers.append("unsupported_service_type")
        if service_type == "web_service" and not service.get("start_command"):
            blockers.append("start_command")
        if not service.get("build_command") and service_type in {"web_service", "static_site"}:
            blockers.append("build_command")
        if service_type == "static_site" and not service.get("publish_directory"):
            blockers.append("publish_directory")
        if credential["availability"] != "reference_available":
            blockers.append("credential_reference")
        if not external_network_allowed:
            blockers.append("external_network_permission")
        if not deployment_intent:
            blockers.append("deployment_intent")
        if not final_confirmation:
            blockers.append("final_confirmation")
        if blockers == ["credential_reference", "external_network_permission", "deployment_intent", "final_confirmation"] or blockers == ["credential_reference", "external_network_permission", "final_confirmation"]:
            state = "render_ready_for_dry_run"
        elif "credential_reference" in blockers:
            state = "render_credentials_required"
        elif "external_network_permission" in blockers:
            state = "render_external_network_permission_required"
        elif "final_confirmation" in blockers:
            state = "render_final_confirmation_required"
        elif blockers:
            state = "render_execution_blocked"
        else:
            state = "render_ready_for_controlled_deployment"
    readiness = {
        "render_detected": detection.get("detection", {}).get("render_detected", False),
        "service_selected": bool(service),
        "selected_service": service,
        "service_type_supported": service.get("service_type") in {"web_service", "static_site"} if service else False,
        "project_root_valid": True,
        "root_directory_valid": bool(service.get("root_directory", ".")) if service else False,
        "build_command_resolved": bool(service.get("build_command")),
        "start_command_resolved": bool(service.get("start_command")) if service.get("service_type") == "web_service" else True,
        "publish_directory_resolved": bool(service.get("publish_directory")) if service.get("service_type") == "static_site" else True,
        "health_path_resolved": bool(service.get("health_path")),
        "runtime_resolved": bool(service.get("runtime") or service.get("service_type")),
        "branch_resolved": bool(service.get("branch")),
        "environment_requirements": parse_render_configuration(repository_root, selected_scope).get("parsed", {}).get("environment_requirements", []),
        "credential_reference": credential,
        "external_network_permission": bool(external_network_allowed),
        "deployment_intent": bool(deployment_intent),
        "risk_decision": "critical_for_real_render_deployment",
        "final_confirmation_state": "confirmed" if final_confirmation else "required",
        "rollback_strategy": build_render_rollback_plan(service.get("service_type", "unknown")).get("rollback_plan", {}),
        "url_verification_plan": {"health_required": True, "browser_scenario_required": True, "public_url_verification_blocked_without_permission": True},
        "browser_scenario_plan": {"local_fake_provider_only": True},
        "blockers": blockers,
        "readiness_state": state,
        "controlled_deployment_ready": state == "render_ready_for_controlled_deployment",
        "dry_run_ready": state in {"render_ready_for_dry_run", "render_credentials_required", "render_external_network_permission_required", "render_final_confirmation_required"},
    }
    return _safe_success(readiness=readiness)


def _plan_digest(plan: Dict[str, Any]) -> str:
    data = {key: value for key, value in plan.items() if key not in {"plan_digest", "audit_events"}}
    return _digest(data, "render-plan-digest-")


def build_render_deployment_plan(
    task_id: str = "",
    repository_root: str = "",
    selected_scope: str = ".",
    service_candidate_id: str = "",
    credential_reference: Optional[Dict[str, Any]] = None,
    external_network_allowed: bool = False,
    deployment_intent: bool = False,
    final_confirmation: bool = False,
    timeout_seconds: int = 60,
    retry_budget: int = 1,
) -> Dict[str, Any]:
    root, error = _root(repository_root)
    if error:
        return _safe_failure(error)
    service = select_render_service(str(root), selected_scope, service_candidate_id)
    if not service.get("ok"):
        return service
    selected = service["selected_service"]
    readiness = analyze_render_readiness(str(root), selected_scope, selected.get("service_candidate_id"), credential_reference, external_network_allowed, deployment_intent, final_confirmation)
    plan = {
        "render_plan_id": _digest([task_id, str(root), selected, time.time()], "render-plan-"),
        "task_id": task_id,
        "project_root": str(root),
        "repository_digest": hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16],
        "provider": "render",
        "service_candidate_id": selected.get("service_candidate_id"),
        "service_name": selected.get("service_name"),
        "service_type": selected.get("service_type"),
        "runtime": selected.get("runtime"),
        "branch": selected.get("branch"),
        "region": selected.get("region"),
        "root_directory": selected.get("root_directory"),
        "build_command": selected.get("build_command"),
        "start_command": selected.get("start_command"),
        "publish_directory": selected.get("publish_directory"),
        "health_path": selected.get("health_path"),
        "environment_requirements": readiness.get("readiness", {}).get("environment_requirements", []),
        "credential_reference": readiness.get("readiness", {}).get("credential_reference", {}),
        "network_permission_state": "allowed" if external_network_allowed else "blocked_by_external_network_policy",
        "deployment_intent": bool(deployment_intent),
        "risk": "critical",
        "final_confirmation_state": "confirmed" if final_confirmation else "required",
        "rollback_policy": build_render_rollback_plan(selected.get("service_type")).get("rollback_plan", {}),
        "url_verification_policy": {"health_required": True, "browser_required": True, "unverified_url_ready": False},
        "browser_scenario_policy": {"fake_provider_localhost_only": True},
        "timeout_seconds": max(5, min(int(timeout_seconds or 60), 180)),
        "retry_budget": max(0, min(int(retry_budget or 0), 3)),
        "evidence_policy": {"structured_only": True, "raw_render_body_persisted": False},
        "cleanup_policy": {"fake_provider_artifacts_removed": True, "owned_runtime_only": True},
        "readiness_state": readiness.get("readiness", {}).get("readiness_state"),
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    plan["plan_digest"] = _plan_digest(plan)
    _audit(plan, "render_plan_created", {"service_name": selected.get("service_name"), "service_type": selected.get("service_type")})
    return _safe_success(plan=plan)


def validate_render_deployment_plan(plan: Dict[str, Any], expected_plan_digest: str = "") -> Dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("provider") != "render":
        return _safe_failure("valid Render plan is required")
    actual = _plan_digest(plan)
    expected = expected_plan_digest or plan.get("plan_digest", "")
    if actual != expected:
        return _safe_failure("plan digest mismatch", failure_category="plan_digest_mismatch", expected_digest=expected, actual_digest=actual)
    missing = [key for key in ["service_candidate_id", "service_name", "service_type", "health_path"] if not plan.get(key)]
    if missing:
        return _safe_failure("render plan missing required fields", missing=missing)
    return _safe_success(valid=True, plan_digest=actual)


def evaluate_render_permission(plan: Dict[str, Any], final_confirmation: bool = False, external_network_allowed: bool = False, credential_reference: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    credential = _credential_reference(**(credential_reference or plan.get("credential_reference") or {}))
    if not plan.get("deployment_intent"):
        return _safe_success(allowed=False, reason="deployment intent required", failure_category="blocked_by_final_confirmation")
    if credential["availability"] != "reference_available":
        return _safe_success(allowed=False, reason="credential reference required", failure_category="blocked_by_missing_credentials")
    if not external_network_allowed and plan.get("network_permission_state") != "allowed":
        return _safe_success(allowed=False, reason="external network permission required", failure_category="blocked_by_external_network_policy")
    if not final_confirmation and plan.get("final_confirmation_state") != "confirmed":
        return _safe_success(allowed=False, reason="final confirmation required", failure_category="blocked_by_final_confirmation")
    return _safe_success(allowed=False, reason="real Render execution adapter is not enabled in MVP", failure_category="adapter_execution_not_enabled")


def execute_render_dry_run(plan: Dict[str, Any], fixture: str = "success") -> Dict[str, Any]:
    validation = validate_render_deployment_plan(plan)
    if not validation.get("ok"):
        return validation
    runtime_id = _digest([plan.get("render_plan_id"), fixture, time.time()], "render-runtime-")
    runtime = {
        "render_runtime_id": runtime_id,
        "render_plan_id": plan.get("render_plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "provider": "render",
        "execution_mode": "fake_render_provider",
        "service_name": plan.get("service_name"),
        "service_type": plan.get("service_type"),
        "deployment_id": _digest([runtime_id, "deployment"], "fake-render-deploy-"),
        "lifecycle_state": "render_dry_run_running",
        "events": [],
        "url_result": {"final_verification_status": "candidate"},
        "cleanup_state": "cleanup_required",
        "fake_result_classification": "fake_render_provider_only",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    _audit(runtime, "render_dry_run_started", {"fixture": fixture})
    failure_map = {
        "build_failure": ("render_deployment_failed", "fake_build_failed"),
        "deployment_failure": ("render_deployment_failed", "fake_deployment_failed"),
        "timeout": ("render_timed_out", "fake_deployment_timeout"),
        "url_missing": ("render_deployment_failed", "fake_url_missing"),
        "health_failure": ("render_health_failed", "fake_health_failed"),
        "scenario_failure": ("render_scenario_failed", "fake_scenario_failed"),
        "cancel": ("render_cancelled", "render_cancelled"),
    }
    if fixture in failure_map:
        state, category = failure_map[fixture]
        runtime.update({"lifecycle_state": state, "failure_category": category, "cleanup_state": "render_cleanup_completed", "rollback_state": "render_rollback_recommended"})
        _audit(runtime, "render_deployment_failed" if "failed" in state else "render_cancelled", {"failure_category": category})
        _audit(runtime, "render_rollback_recommended", {"production_rollback_executed": False})
        _audit(runtime, "render_cleanup_completed", {"fake_provider_artifacts_removed": True})
        _RUNTIMES[runtime_id] = runtime
        return _safe_success(runtime=_public_runtime(runtime))
    deployment_plan = build_deployment_plan(
        task_id=plan.get("task_id") or runtime_id,
        repository_root=plan.get("project_root") or os.getcwd(),
        provider="local_fixture",
        command_text="Deploy local fake Render provider and verify localhost URL",
        deploy_intent=True,
        verify_url_intent=True,
    )
    if not deployment_plan.get("ok"):
        runtime.update({"lifecycle_state": "render_deployment_failed", "failure_category": "fake_deployment_failed"})
        return _safe_success(runtime=_public_runtime(runtime))
    executed = execute_deployment(deployment_plan["plan"])
    deployment_runtime = executed.get("runtime", {})
    runtime["deployment_core_runtime"] = deployment_runtime
    runtime["events"] = ["render_deployment_building", "render_deployment_live", "render_url_received", "render_health_verified", "render_scenario_verified"]
    runtime["url_result"] = deepcopy(deployment_runtime.get("url_result", {}))
    runtime["url_result"]["provider"] = "fake_render_provider"
    runtime["url_result"]["environment"] = "temporary_fake_render"
    runtime["url_result"]["fake_result_classification"] = "fake_render_deployment_verified"
    if deployment_runtime.get("url_result", {}).get("final_verification_status") == "fully_verified":
        runtime["lifecycle_state"] = "render_fully_verified"
        runtime["fake_result_classification"] = "fake_render_deployment_verified"
        _audit(runtime, "render_url_received", {"url": runtime["url_result"].get("url")})
        _audit(runtime, "render_health_verified", {"health": True})
        _audit(runtime, "render_scenario_verified", {"scenario": True})
        _audit(runtime, "render_dry_run_completed", {"classification": "fake_render_deployment_verified"})
    else:
        runtime["lifecycle_state"] = "render_partially_verified"
        runtime["failure_category"] = deployment_runtime.get("failure_category", "fake_scenario_failed")
    runtime["cleanup_state"] = "render_cleanup_completed"
    _audit(runtime, "render_cleanup_completed", {"fake_provider_artifacts_removed": True})
    _RUNTIMES[runtime_id] = runtime
    return _safe_success(runtime=_public_runtime(runtime))


def execute_render_deployment(plan: Dict[str, Any], expected_plan_digest: str = "", credential_reference: Optional[Dict[str, Any]] = None, external_network_allowed: bool = False, final_confirmation: bool = False) -> Dict[str, Any]:
    validation = validate_render_deployment_plan(plan, expected_plan_digest)
    if not validation.get("ok"):
        return validation
    permission = evaluate_render_permission(plan, final_confirmation, external_network_allowed, credential_reference)
    runtime_id = _digest([plan.get("render_plan_id"), "blocked"], "render-runtime-")
    runtime = {
        "render_runtime_id": runtime_id,
        "render_plan_id": plan.get("render_plan_id"),
        "provider": "render",
        "execution_mode": "real_render_blocked",
        "lifecycle_state": "render_deployment_waiting_confirmation",
        "failure_category": permission.get("failure_category"),
        "permission": permission,
        "cleanup_state": "render_cleanup_completed",
        "audit_events": [],
        **SAFE_INVARIANTS,
    }
    _audit(runtime, "render_permission_evaluated", permission)
    _audit(runtime, "render_deployment_blocked", {"reason": permission.get("reason")})
    _RUNTIMES[runtime_id] = runtime
    return _safe_failure(permission.get("reason", "real Render execution blocked"), runtime=_public_runtime(runtime), failure_category=permission.get("failure_category"))


def poll_render_deployment(runtime_id: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("render runtime not found")
    _audit(runtime, "render_deployment_status_polled", {"runtime_id": runtime_id})
    return _safe_success(runtime=_public_runtime(runtime))


def collect_render_url(runtime_id: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("render runtime not found")
    url_result = runtime.get("url_result", {})
    if url_result.get("final_verification_status") != "fully_verified":
        return _safe_failure("Render URL is not fully verified", url_result=url_result)
    return _safe_success(url_result=url_result)


def verify_render_result(runtime_id: str = "", url: str = "") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("render runtime not found")
    core = runtime.get("deployment_core_runtime", {})
    if core.get("deployment_runtime_id"):
        return verify_deployment_url(core["deployment_runtime_id"], url or core.get("url_result", {}).get("url", ""))
    return _safe_failure("no owned fake deployment URL available")


def build_render_rollback_plan(service_type: str = "unknown") -> Dict[str, Any]:
    supported = _service_type(service_type) in {"web_service", "static_site"}
    return _safe_success(
        rollback_plan={
            "rollback_supported": supported,
            "rollback_strategy": "fake_provider_previous_release_metadata" if supported else "manual_review_required",
            "previous_release_id": "",
            "rollback_authority": "explicit_final_confirmation_required",
            "rollback_risk": "critical_for_real_render",
            "production_rollback_executed": False,
            "recommended_action": "recommend rollback only; real Render rollback blocked in MVP",
        }
    )


def cancel_render_deployment(runtime_id: str = "", reason: str = "user_requested") -> Dict[str, Any]:
    runtime = _RUNTIMES.get(str(runtime_id or ""))
    if not runtime:
        return _safe_failure("render runtime not found")
    runtime["lifecycle_state"] = "render_cancelled"
    runtime["cleanup_state"] = "render_cleanup_completed"
    _audit(runtime, "render_cancelled", {"reason": reason})
    _audit(runtime, "render_cleanup_completed", {"owned_runtime_only": True})
    return _safe_success(runtime=_public_runtime(runtime))


def summarize_render_result(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_success(
        render_runtime_id=runtime.get("render_runtime_id"),
        lifecycle_state=runtime.get("lifecycle_state"),
        fake_result_classification=runtime.get("fake_result_classification", ""),
        final_verification_status=runtime.get("url_result", {}).get("final_verification_status", "blocked"),
        real_render_deployment=False,
    )


def restore_render_record(record: Dict[str, Any]) -> Dict[str, Any]:
    restored = _redact(deepcopy(record or {}))
    restored["restore_state"] = "render_resume_requires_user_action"
    restored["external_state"] = "render_external_state_revalidation_required"
    restored["lifecycle_state"] = "render_manual_review_required"
    restored["execution_triggered"] = False
    restored["status_poll_triggered"] = False
    restored["url_probe_triggered"] = False
    restored["rollback_triggered"] = False
    restored.setdefault("audit_events", []).append({"event_type": "render_restore_requires_user_action", "created_at": _now(), "payload": {}})
    return _safe_success(runtime=restored)


def get_safe_render_metadata(runtime: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": "render",
        "service_type": runtime.get("service_type"),
        "service_name": runtime.get("service_name"),
        "plan_id": runtime.get("render_plan_id"),
        "plan_digest": runtime.get("plan_digest"),
        "readiness_state": runtime.get("readiness_state"),
        "environment_key_names": sorted({item.get("key_name", "") for item in runtime.get("environment_requirements", []) if item.get("key_name")}),
        "credential_reference_state": runtime.get("credential_reference", {}).get("availability"),
        "lifecycle_state": runtime.get("lifecycle_state"),
        "deployment_id": runtime.get("deployment_id"),
        "url_verification_state": runtime.get("url_result", {}).get("final_verification_status"),
        "failure_category": runtime.get("failure_category"),
        "cleanup_state": runtime.get("cleanup_state"),
        "restore_action": "render_resume_requires_user_action",
        "safe_metadata_only": True,
    }


def get_render_adapter_status() -> Dict[str, Any]:
    render_gateway_available = False
    render_readiness_broker_available = False
    try:
        from luxcode_render_execution_gateway import get_render_gateway_status

        render_gateway_available = bool(get_render_gateway_status().get("ok"))
    except Exception:
        render_gateway_available = False
    try:
        from luxcode_render_credential_readiness_broker import get_render_credential_broker_status

        render_readiness_broker_available = bool(get_render_credential_broker_status().get("ok"))
    except Exception:
        render_readiness_broker_available = False
    return _safe_success(
        name="LuxCode Render Provider Adapter",
        status="ready",
        runtime_count=len(_RUNTIMES),
        active_runtime_count=sum(1 for item in _RUNTIMES.values() if item.get("cleanup_state") != "render_cleanup_completed"),
        real_render_execution_enabled=False,
        fake_render_provider_supported=True,
        render_execution_gateway_available=render_gateway_available,
        render_credential_readiness_broker_available=render_readiness_broker_available,
        service_types=sorted(SERVICE_TYPES),
    )


def _public_runtime(runtime: Dict[str, Any]) -> Dict[str, Any]:
    public = _redact(deepcopy(runtime))
    public["temporary_paths"] = "[cleaned]"
    return public
