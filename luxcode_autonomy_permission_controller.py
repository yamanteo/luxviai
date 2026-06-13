from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PERMISSION_MODES = {
    "approval_required": "Onayli Erisim",
    "controlled_access": "Kontrollu Erisim",
    "full_access": "Tam Erisim",
}
DEFAULT_MODE = "approval_required"
INFO_TEXT = (
    "LuxCode yalnizca sectiginiz dosya ve klasorlerde calisir. Gorevi tamamlamak icin kapsam disindaki "
    "bir alana ihtiyac duyarsa, erismeden once neden gerekli oldugunu ve hangi islemi yapacagini aciklayarak "
    "sizden izin ister."
)
SUPPORTED_OPERATIONS = {
    "inspect",
    "read",
    "create_file",
    "edit_file",
    "delete_file",
    "rename_file",
    "move_file",
    "refactor",
    "run_tests",
    "run_validator",
    "run_smoke",
    "install_dependency",
    "modify_dependency",
    "commit",
    "push",
    "deploy",
    "rollback",
    "database_migration",
    "modify_configuration",
    "modify_secrets",
    "modify_authentication",
    "modify_security_policy",
}
READ_OPS = {"inspect", "read"}
WRITE_OPS = {
    "create_file",
    "edit_file",
    "rename_file",
    "move_file",
    "refactor",
    "modify_dependency",
    "modify_configuration",
    "modify_secrets",
    "modify_authentication",
    "modify_security_policy",
}
DELETE_OPS = {"delete_file"}
EXECUTION_OPS = {"run_tests", "run_validator", "run_smoke", "install_dependency", "deploy", "database_migration", "rollback"}
HIGH_RISK_OPS = {"commit", "push", "deploy", "install_dependency", "database_migration", "rollback", "modify_secrets"}
IRREVERSIBLE_OPS = {"database_migration", "push", "delete_file"}
VALID_DURATIONS = {"one_action", "current_task", "current_session", "current_project"}
SCOPE_EXPANSION_OPTIONS = {
    "allow_read_once",
    "allow_write_once",
    "allow_delete_once",
    "allow_for_task",
    "allow_for_session",
    "allow_for_project",
    "deny",
}
DEFAULT_BUDGETS = {
    "max_files_changed": 8,
    "max_files_created": 4,
    "max_files_deleted": 1,
    "max_retry_count": 2,
    "max_validation_runs": 3,
    "max_task_duration_seconds": 1800,
    "max_patch_bytes": 80_000,
    "max_scope_expansions": 3,
    "max_commits": 1,
    "max_pushes": 1,
    "dependency_install_allowed": False,
    "deployment_allowed": False,
    "migration_allowed": False,
}
SAFE_INVARIANTS = {
    "external_api_used": False,
    "network_access_used": False,
    "live_commit_push_deploy_used": False,
    "live_patch_used": False,
    "local_first": True,
}

_PROFILES: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any, prefix: str = "luxperm-") -> str:
    return prefix + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:32]


def _unique(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _safe_failure(message: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": False, "allowed": False, "reason": message, **extra, **SAFE_INVARIANTS}


def _safe_success(**extra: Any) -> Dict[str, Any]:
    return {"ok": True, **extra, **SAFE_INVARIANTS}


def _root(repository_root: Optional[str]) -> Tuple[Optional[Path], str]:
    if not repository_root:
        return None, "repository_root is required"
    try:
        return Path(repository_root).resolve(), ""
    except OSError as exc:
        return None, f"invalid repository_root: {exc}"


def _normalize_path(repository_root: Optional[str], raw_path: Optional[str], *, must_exist: bool = False) -> Tuple[Optional[Path], str, str]:
    root, root_error = _root(repository_root)
    if root is None:
        return None, "", root_error
    if not raw_path:
        return root, "", ""
    text = str(raw_path).replace("\\", "/").strip()
    if not text:
        return root, "", ""
    if "*" in text or "?" in text or "[" in text or "]" in text:
        return None, "", "wildcard escalation blocked"
    if any(part == ".." for part in Path(text).parts):
        return None, "", "path traversal blocked"
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None, "", "outside-root or symlink escape blocked"
    if must_exist and not resolved.exists():
        return None, "", "path does not exist"
    try:
        if resolved.exists() and resolved.resolve(strict=True).relative_to(root) is None:
            return None, "", "symlink escape blocked"
    except (OSError, ValueError):
        return None, "", "symlink escape blocked"
    return resolved, resolved.relative_to(root).as_posix(), ""


def _rights_for_operation(operation: str) -> set[str]:
    if operation in READ_OPS or operation in {"run_tests", "run_validator", "run_smoke"}:
        return {"read"}
    if operation in DELETE_OPS:
        return {"delete"}
    return {"write"}


def _normalize_scope_item(repository_root: str, item: Dict[str, Any]) -> Dict[str, Any]:
    path_value = item.get("path") or item.get("target_path") or ""
    resolved, rel, error = _normalize_path(repository_root, path_value)
    if error:
        raise ValueError(error)
    item_type = str(item.get("type") or item.get("scope_type") or ("folder" if resolved and resolved.is_dir() else "file"))
    recursive = bool(item.get("recursive", item_type == "recursive_folder"))
    rights = set(str(right).lower() for right in item.get("rights", []) if right)
    if item.get("read_only"):
        rights.add("read")
    if item.get("write_enabled"):
        rights.update({"read", "write"})
    if item.get("delete_enabled"):
        rights.update({"read", "write", "delete"})
    if not rights:
        rights = {"read"}
    duration = str(item.get("duration") or "current_task")
    if duration not in VALID_DURATIONS:
        duration = "current_task"
    return {
        "path": rel,
        "type": "folder" if item_type in {"folder", "recursive_folder"} else "file",
        "recursive": recursive if item_type in {"folder", "recursive_folder"} else False,
        "rights": sorted(rights),
        "duration": duration,
        "revoked": bool(item.get("revoked", False)),
        "granted_at": item.get("granted_at") or _now(),
    }


def _scope_allows(profile: Dict[str, Any], operation: str, target_path: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    repository_root = profile.get("repository_root", "")
    resolved, rel, error = _normalize_path(repository_root, target_path)
    if error:
        return False, error, None
    required = _rights_for_operation(operation)
    if rel == "":
        return True, "", {"path": "", "rights": sorted(required), "type": "folder", "recursive": False}
    for item in profile.get("scope_items", []):
        if item.get("revoked"):
            continue
        item_path = str(item.get("path", ""))
        rights = set(item.get("rights", []))
        if not required <= rights:
            continue
        if item.get("type") == "file" and rel == item_path:
            return True, "", item
        if item.get("type") == "folder":
            if rel == item_path:
                return True, "", item
            if item.get("recursive") and (rel.startswith(item_path.rstrip("/") + "/") or item_path == ""):
                return True, "", item
    return False, "selected scope does not include requested path or rights", None


def parse_task_authority(command_text: str = "") -> Dict[str, Any]:
    text = (command_text or "").lower()
    operations = {"inspect", "read"}
    if any(word in text for word in ("fix", "duzelt", "düzelt", "edit", "change", "refactor", "guncelle", "güncelle")):
        operations.update({"edit_file", "create_file", "refactor", "run_tests", "run_validator", "run_smoke"})
    if any(word in text for word in ("ekle", "add", "create", "olustur", "oluştur")):
        operations.add("create_file")
    if any(word in text for word in ("sil", "delete", "remove")):
        operations.add("delete_file")
    if any(word in text for word in ("test", "validator", "validate", "smoke", "dogrula", "doğrula")):
        operations.update({"run_tests", "run_validator", "run_smoke"})
    if "commit" in text or "commitle" in text:
        operations.add("commit")
    if "push" in text:
        operations.add("push")
    if "deploy" in text or "yayina al" in text or "yayına al" in text:
        operations.add("deploy")
    if "rollback" in text or "geri al" in text:
        operations.add("rollback")
    if "migration" in text or "migrate" in text:
        operations.add("database_migration")
    if any(word in text for word in ("dependency", "package", "pip install", "npm install", "bagimlilik", "bağımlılık")):
        operations.add("modify_dependency")
        if "install" in text or "kur" in text:
            operations.add("install_dependency")
    if any(word in text for word in ("config", "configuration", "ayar")):
        operations.add("modify_configuration")
    if any(word in text for word in ("secret", ".env", "api key", "token", "sifre", "şifre")):
        operations.add("modify_secrets")
    explicit_high_risk = sorted(operations & HIGH_RISK_OPS)
    return _safe_success(
        command_text=command_text,
        allowed_operations=sorted(operations),
        explicit_high_risk_operations=explicit_high_risk,
        unspecified_high_risk_not_inferred=True,
    )


def classify_risk_level(operation: str = "read", target_path: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = metadata or {}
    path = str(target_path or "").replace("\\", "/").lower()
    op = str(operation or "read")
    risk = "normal"
    reasons: List[str] = []
    if any(name in path for name in (".env", "secret", "credential", "private_key")) or op in {"modify_secrets"}:
        risk = "critical"
        reasons.append("secret-bearing configuration")
    elif any(name in path for name in ("auth", "security", "permission", "policy")) or op in {"modify_authentication", "modify_security_policy"}:
        risk = "critical"
        reasons.append("authentication or security control")
    elif any(name in path for name in ("production", "prod.", "deploy", "ci/", ".github/", "docker", "render.yaml")) or op == "deploy":
        risk = "critical"
        reasons.append("deployment or production configuration")
    elif any(name in path for name in ("requirements", "package.json", "pyproject", "schema", "router", "config")) or op in {"modify_dependency", "install_dependency"}:
        risk = "important"
        reasons.append("shared configuration or dependency")
    if op in {"database_migration"} and metadata.get("destructive", True):
        risk = "irreversible"
        reasons.append("destructive migration")
    if op == "push" and metadata.get("force", False):
        risk = "irreversible"
        reasons.append("force push/history rewrite")
    if op == "delete_file" and (metadata.get("mass_delete") or metadata.get("user_data")):
        risk = "irreversible"
        reasons.append("large-scale or user-data deletion")
    return _safe_success(risk_level=risk, reasons=reasons or ["ordinary scoped action"])


def _approval_digest(payload: Dict[str, Any]) -> str:
    return _digest(payload, "luxscope-approve-")


def request_scope_expansion(
    task_id: str = "",
    requested_path: str = "",
    requested_operation: str = "read",
    why_needed: str = "",
    repository_root: Optional[str] = None,
    read_only_sufficient: bool = True,
) -> Dict[str, Any]:
    risk = classify_risk_level(requested_operation, requested_path)
    write_required = requested_operation in WRITE_OPS or requested_operation in EXECUTION_OPS
    delete_required = requested_operation in DELETE_OPS
    payload = {
        "task_id": task_id,
        "requested_path": str(requested_path),
        "requested_operation": requested_operation,
        "why_needed": why_needed or "The selected scope does not include information needed to complete the task.",
        "risk_level": risk.get("risk_level", "normal"),
    }
    return _safe_success(
        request_type="scope_expansion",
        task_id=task_id,
        requested_path=str(requested_path),
        requested_operation=requested_operation,
        why_needed=payload["why_needed"],
        simple_explanation=f"{requested_path} alanina erisim gerekiyor.",
        technical_reason="Requested path is outside the current selected allowlist scope.",
        risk_level=payload["risk_level"],
        read_only_access_sufficient=bool(read_only_sufficient and not write_required and not delete_required),
        write_access_required=bool(write_required),
        delete_access_required=bool(delete_required),
        suggested_permission_duration="one_action",
        effect_if_approved="The requested path is added to the selected scope for the approved duration.",
        effect_if_denied="LuxCode continues only with the currently selected scope or pauses if the task cannot be completed.",
        approval_options=sorted(SCOPE_EXPANSION_OPTIONS),
        approval_digest=_approval_digest(payload),
    )


def create_permission_profile(
    task_id: str = "",
    permission_mode: str = DEFAULT_MODE,
    repository_root: Optional[str] = None,
    command_text: str = "",
    scope_items: Optional[List[Dict[str, Any]]] = None,
    selected_files: Optional[List[str]] = None,
    selected_folders: Optional[List[str]] = None,
    autonomy_budgets: Optional[Dict[str, Any]] = None,
    duration: str = "current_task",
    explicit_mode_upgrade: bool = False,
    project_identifier: str = "",
) -> Dict[str, Any]:
    if permission_mode not in PERMISSION_MODES:
        return _safe_failure("invalid permission mode", valid_modes=sorted(PERMISSION_MODES))
    root, error = _root(repository_root)
    if error:
        return _safe_failure(error)
    requested_items = deepcopy(scope_items or [])
    for path in selected_files or []:
        requested_items.append({"path": path, "type": "file", "rights": ["read", "write"], "duration": duration})
    for path in selected_folders or []:
        requested_items.append({"path": path, "type": "folder", "recursive": True, "rights": ["read", "write"], "duration": duration})
    normalized_scope = []
    try:
        for item in requested_items:
            normalized_scope.append(_normalize_scope_item(str(root), item))
    except ValueError as exc:
        return _safe_failure(str(exc))
    authority = parse_task_authority(command_text)
    budgets = dict(DEFAULT_BUDGETS)
    budgets.update(autonomy_budgets or {})
    profile_id = _digest([task_id, permission_mode, str(root), normalized_scope, authority.get("allowed_operations")])
    profile = {
        "profile_id": profile_id,
        "task_id": task_id,
        "permission_mode": permission_mode,
        "ui_name": PERMISSION_MODES[permission_mode],
        "repository_root": str(root),
        "repository_root_hash": hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:32],
        "project_identifier_hash": hashlib.sha256((project_identifier or str(root)).encode("utf-8")).hexdigest()[:32],
        "command_text": command_text,
        "operation_authority": authority.get("allowed_operations", ["inspect", "read"]),
        "scope_items": normalized_scope,
        "duration": duration if duration in VALID_DURATIONS else "current_task",
        "autonomy_budgets": budgets,
        "risk_policy": {
            "approval_required_gates": "all writes and execution",
            "controlled_access_gates": "critical and irreversible",
            "full_access_gates": "scope, authority, budgets, irreversible without recovery",
        },
        "revoked": False,
        "scope_expansion_count": 0,
        "audit_log": [],
        "created_at": _now(),
        "updated_at": _now(),
        "revision": 1,
        "integrity_hash": "",
    }
    profile["integrity_hash"] = _digest({key: value for key, value in profile.items() if key != "integrity_hash"}, "luxperm-integrity-")
    _PROFILES[profile_id] = profile
    return _safe_success(profile=deepcopy(profile), info_text=INFO_TEXT)


def _load_profile(profile: Optional[Dict[str, Any]] = None, profile_id: str = "") -> Optional[Dict[str, Any]]:
    if profile:
        return deepcopy(profile)
    if profile_id:
        stored = _PROFILES.get(profile_id)
        return deepcopy(stored) if stored else None
    return None


def _budget_check(profile: Dict[str, Any], operation: str, metadata: Dict[str, Any]) -> Tuple[bool, str]:
    budgets = profile.get("autonomy_budgets", {})
    if operation == "delete_file" and metadata.get("files_deleted", 1) > budgets.get("max_files_deleted", 1):
        return False, "max-delete budget exceeded"
    if metadata.get("files_changed", 1 if operation in WRITE_OPS else 0) > budgets.get("max_files_changed", 8):
        return False, "max-files budget exceeded"
    if metadata.get("files_created", 0) > budgets.get("max_files_created", 4):
        return False, "max-create budget exceeded"
    if metadata.get("patch_bytes", 0) > budgets.get("max_patch_bytes", 80_000):
        return False, "max-patch-size budget exceeded"
    if metadata.get("retry_count", 0) > budgets.get("max_retry_count", 2):
        return False, "retry budget enforced"
    if metadata.get("validation_runs", 0) > budgets.get("max_validation_runs", 3):
        return False, "max-validation budget exceeded"
    if metadata.get("elapsed_seconds", 0) > budgets.get("max_task_duration_seconds", 1800):
        return False, "max-duration budget exceeded"
    if metadata.get("scope_expansions", profile.get("scope_expansion_count", 0)) > budgets.get("max_scope_expansions", 3):
        return False, "max-scope-expansion budget exceeded"
    if operation == "commit" and metadata.get("commits", 1) > budgets.get("max_commits", 1):
        return False, "max-commits budget exceeded"
    if operation == "push" and metadata.get("pushes", 1) > budgets.get("max_pushes", 1):
        return False, "max-pushes budget exceeded"
    if operation == "install_dependency" and not budgets.get("dependency_install_allowed", False):
        return False, "dependency install budget not enabled"
    if operation == "deploy" and not budgets.get("deployment_allowed", False):
        return False, "deployment budget not enabled"
    if operation == "database_migration" and not budgets.get("migration_allowed", False):
        return False, "migration budget not enabled"
    return True, ""


def evaluate_requested_action(
    profile: Optional[Dict[str, Any]] = None,
    profile_id: str = "",
    task_id: str = "",
    operation: str = "read",
    target_path: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    approval_digest: str = "",
    recovery_plan_available: bool = True,
) -> Dict[str, Any]:
    metadata = metadata or {}
    loaded = _load_profile(profile, profile_id)
    if not loaded:
        return _safe_failure("permission profile is required")
    if loaded.get("revoked"):
        return _safe_failure("permission profile revoked", profile_id=loaded.get("profile_id"))
    if operation not in SUPPORTED_OPERATIONS:
        return _safe_failure("unsupported operation", operation=operation)
    if operation not in set(loaded.get("operation_authority", [])):
        return _safe_failure("operation not authorized by user command", operation=operation, requires_scope_expansion=False)
    budget_ok, budget_error = _budget_check(loaded, operation, metadata)
    if not budget_ok:
        return _safe_failure(budget_error, state="budget_exhausted")
    in_scope, scope_error, matched_scope = _scope_allows(loaded, operation, target_path)
    if not in_scope:
        return _safe_failure(
            "out of selected scope",
            state="awaiting_scope_permission",
            scope_request=request_scope_expansion(
                task_id=task_id or loaded.get("task_id", ""),
                requested_path=target_path,
                requested_operation=operation,
                why_needed=metadata.get("why_needed", scope_error),
                repository_root=loaded.get("repository_root"),
                read_only_sufficient=operation in READ_OPS,
            ),
        )
    risk = classify_risk_level(operation, target_path, metadata)
    risk_level = risk.get("risk_level", "normal")
    mode = loaded.get("permission_mode", DEFAULT_MODE)
    requires_approval = False
    reason = ""
    if mode == "approval_required" and operation not in READ_OPS:
        requires_approval = True
        reason = "approval_required mode requires approval for write or execution"
    elif mode == "controlled_access" and risk_level in {"critical", "irreversible"}:
        requires_approval = True
        reason = "controlled_access gates critical or irreversible actions"
    elif mode == "full_access" and risk_level == "irreversible":
        if operation not in set(loaded.get("operation_authority", [])):
            return _safe_failure("irreversible action lacks explicit authority", risk_level=risk_level)
        if not recovery_plan_available:
            return _safe_failure("irreversible action requires final confirmation because no rollback is available", state="awaiting_irreversible_confirmation", risk_level=risk_level)
    allowed = not requires_approval or approval_digest == _approval_digest({"profile_id": loaded.get("profile_id"), "operation": operation, "target_path": target_path})
    audit = {
        "task_id": task_id or loaded.get("task_id", ""),
        "permission_mode": mode,
        "operation": operation,
        "target_path": target_path,
        "risk_level": risk_level,
        "allowed": allowed,
        "requires_approval": requires_approval,
        "reason": reason,
        "scope": matched_scope,
        "safeguards": {
            "snapshot_required_before_write": operation in WRITE_OPS or operation in DELETE_OPS,
            "hash_capture_required": operation in WRITE_OPS or operation in DELETE_OPS,
            "validation_plan_required": operation in WRITE_OPS or operation in DELETE_OPS or operation in EXECUTION_OPS,
            "last_known_working_state_preserved": operation in WRITE_OPS or operation in DELETE_OPS,
            "recovery_prepared_on_failure": operation in WRITE_OPS or operation in DELETE_OPS or operation in EXECUTION_OPS,
        },
    }
    return _safe_success(
        allowed=allowed,
        blocked=not allowed,
        requires_approval=requires_approval,
        reason=reason,
        permission_mode=mode,
        operation=operation,
        target_path=target_path,
        risk_level=risk_level,
        matched_scope=matched_scope,
        approval_digest=_approval_digest({"profile_id": loaded.get("profile_id"), "operation": operation, "target_path": target_path}) if requires_approval else "",
        audit=audit,
        safeguards=audit["safeguards"],
    )


def validate_scope_access(
    profile: Optional[Dict[str, Any]] = None,
    profile_id: str = "",
    operation: str = "read",
    target_path: str = "",
) -> Dict[str, Any]:
    loaded = _load_profile(profile, profile_id)
    if not loaded:
        return _safe_failure("permission profile is required")
    allowed, reason, scope = _scope_allows(loaded, operation, target_path)
    return _safe_success(allowed=allowed, reason=reason, matched_scope=scope)


def approve_scope_expansion(
    profile: Optional[Dict[str, Any]] = None,
    profile_id: str = "",
    requested_path: str = "",
    requested_operation: str = "read",
    approval_option: str = "allow_read_once",
    repository_root: Optional[str] = None,
) -> Dict[str, Any]:
    loaded = _load_profile(profile, profile_id)
    if not loaded:
        return _safe_failure("permission profile is required")
    if approval_option == "deny":
        return _safe_success(profile=loaded, approved=False, denied=True)
    if approval_option not in SCOPE_EXPANSION_OPTIONS:
        return _safe_failure("invalid scope expansion option")
    rights = ["read"]
    if "write" in approval_option or requested_operation in WRITE_OPS:
        rights = ["read", "write"]
    if "delete" in approval_option or requested_operation in DELETE_OPS:
        rights = ["read", "write", "delete"]
    duration = {
        "allow_read_once": "one_action",
        "allow_write_once": "one_action",
        "allow_delete_once": "one_action",
        "allow_for_task": "current_task",
        "allow_for_session": "current_session",
        "allow_for_project": "current_project",
    }.get(approval_option, "one_action")
    item = _normalize_scope_item(repository_root or loaded.get("repository_root"), {"path": requested_path, "type": "file", "rights": rights, "duration": duration})
    existing = [entry for entry in loaded.get("scope_items", []) if entry.get("path") == item["path"] and set(item["rights"]) <= set(entry.get("rights", []))]
    if not existing:
        loaded.setdefault("scope_items", []).append(item)
        loaded["scope_expansion_count"] = int(loaded.get("scope_expansion_count", 0)) + 1
        loaded["revision"] = int(loaded.get("revision", 1)) + 1
        loaded["updated_at"] = _now()
    loaded["integrity_hash"] = _digest({key: value for key, value in loaded.items() if key != "integrity_hash"}, "luxperm-integrity-")
    _PROFILES[loaded["profile_id"]] = deepcopy(loaded)
    return _safe_success(profile=loaded, approved=True, idempotent=bool(existing))


def revoke_scope_access(profile: Optional[Dict[str, Any]] = None, profile_id: str = "", target_path: str = "", operation: str = "") -> Dict[str, Any]:
    loaded = _load_profile(profile, profile_id)
    if not loaded:
        return _safe_failure("permission profile is required")
    revoked = 0
    for item in loaded.get("scope_items", []):
        if not target_path or item.get("path") == target_path:
            item["revoked"] = True
            revoked += 1
    loaded["revision"] = int(loaded.get("revision", 1)) + 1
    loaded["updated_at"] = _now()
    _PROFILES[loaded["profile_id"]] = deepcopy(loaded)
    return _safe_success(profile=loaded, revoked_count=revoked, operation=operation)


def build_plain_language_warning(
    operation: str = "edit_file",
    target_path: str = "",
    risk_level: str = "",
    why_needed: str = "",
    backup_available: bool = True,
    rollback_available: bool = True,
    requires_approval: bool = True,
) -> Dict[str, Any]:
    risk = risk_level or classify_risk_level(operation, target_path).get("risk_level", "normal")
    simple_title = "Dosyada guvenli bir degisiklik yapilacak"
    simple_explanation = "Bu islem secili kapsam icindeki dosya veya ayari degistirir."
    possible_problem = "Beklenmeyen bir hata olursa dogrulama calistirilir ve guvenli geri donus hazirlanir."
    if "database_url" in target_path.lower() or "database" in target_path.lower():
        simple_title = "Uygulamanin baglandigi veritabani degisecek"
        simple_explanation = "Bu ayar uygulamanin hangi veritabanina baglandigini belirler."
        possible_problem = "Yanlis deger girilirse uygulama acilmayabilir veya yanlis veritabanina baglanabilir."
    return _safe_success(
        technical_title=f"{operation} {target_path}".strip(),
        simple_title=simple_title,
        what_will_change=f"{target_path or 'selected scope'} uzerinde {operation} islemi degerlendirilecek.",
        simple_explanation=simple_explanation,
        why_needed=why_needed or "Gorevi tamamlamak icin bu adim gerekli olabilir.",
        risk_level=risk,
        possible_problem=possible_problem,
        backup_status="Mevcut durum degisiklikten once hash ve snapshot ile korunacak." if backup_available else "Hazir yedek bulunmuyor.",
        rollback_status="Geri donus plani hazirlanacak." if rollback_available else "Otomatik geri donus garanti degil.",
        if_approved="Islem uygulanir, sonra dogrulama calistirilir.",
        if_denied="Gorev bu noktada durur veya mevcut kapsamla devam eder.",
        recommended_choice="Onaylamadan once kapsam ve risk seviyesini kontrol edin." if requires_approval else "Islem secili kapsam ve yetki icinde devam edebilir.",
        requires_approval=requires_approval,
    )


def get_safe_permission_metadata(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "permission_mode": profile.get("permission_mode"),
        "scope_items": deepcopy(profile.get("scope_items", [])),
        "operation_authority": list(profile.get("operation_authority", [])),
        "permission_duration": profile.get("duration"),
        "project_identifier_hash": profile.get("project_identifier_hash"),
        "risk_policy": deepcopy(profile.get("risk_policy", {})),
        "autonomy_budgets": deepcopy(profile.get("autonomy_budgets", {})),
        "revoked": bool(profile.get("revoked", False)),
        "revision": int(profile.get("revision", 1)),
        "integrity_hash": profile.get("integrity_hash", ""),
    }


def get_autonomy_permission_schema() -> Dict[str, Any]:
    return {
        "name": "LuxCode Autonomy & Permission Controller",
        "default_mode": DEFAULT_MODE,
        "permission_modes": PERMISSION_MODES,
        "required_information_text": INFO_TEXT,
        "supported_operations": sorted(SUPPORTED_OPERATIONS),
        "scope_model": "strict selected file/folder allowlist; everything else is out of scope",
        "durations": sorted(VALID_DURATIONS),
        "scope_expansion_options": sorted(SCOPE_EXPANSION_OPTIONS),
        "risk_levels": ["normal", "important", "critical", "irreversible"],
        "low_level_writes_performed": False,
        **SAFE_INVARIANTS,
    }


def get_autonomy_permission_status() -> Dict[str, Any]:
    return {
        "name": "LuxCode Autonomy & Permission Controller",
        "status": "ready",
        "profile_count": len(_PROFILES),
        "default_mode": DEFAULT_MODE,
        "visible_modes": PERMISSION_MODES,
        "scope_boundary": "selected_scope_only",
        "layer_42_started": False,
        **SAFE_INVARIANTS,
    }
