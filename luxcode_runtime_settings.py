from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping


RUNTIME_VERSION = 1
DEFAULT_REPOSITORY_ROOT = Path(__file__).resolve().parent
DEFAULT_RUNTIME_DIR = DEFAULT_REPOSITORY_ROOT / ".luxcode_runtime"
SETTINGS_FILENAME = "persistent_runtime.json"
CREDENTIAL_DIRNAME = "secure_credentials"
LOCK_FILENAME = "desktop_instance.lock"

SECRET_NAME_PATTERN = re.compile(r"^[a-z0-9_]{3,80}$")

GEMINI_GATE_KEYS = (
    "LUXCODE_GEMINI_ENABLED",
    "LUXCODE_GEMINI_VERIFIED",
    "LUXCODE_GEMINI_TRANSPORT_ENABLED",
    "LUXCODE_GEMINI_REAL_REQUESTS_ENABLED",
    "LUXCODE_GEMINI_NETWORK_ALLOWED",
    "LUXCODE_GEMINI_FREE_TIER_CONFIRMED",
    "LUXCODE_GEMINI_BILLING_DISABLED_CONFIRMED",
    "LUXCODE_GEMINI_QUOTA_STATE",
    "LUXCODE_GEMINI_QUOTA_AVAILABLE",
    "LUXCODE_GEMINI_MODEL_ACCESS_VERIFIED",
    "LUXCODE_GEMINI_AUTH_KEY_CONFIRMED",
    "LUXCODE_GEMINI_KEY_TYPE",
)

OPENROUTER_GATE_KEYS = (
    "LUXCODE_OPENROUTER_ENABLED",
    "LUXCODE_OPENROUTER_TRANSPORT_ENABLED",
    "LUXCODE_OPENROUTER_REAL_REQUESTS",
    "LUXCODE_OPENROUTER_NETWORK_ALLOWED",
    "LUXCODE_OPENROUTER_FREE_TIER_CONFIRMED",
    "LUXCODE_OPENROUTER_MODEL_ACCESS_VERIFIED",
    "LUXCODE_OPENROUTER_QUOTA_STATE",
)

CODEWHALE_GATE_KEYS = (
    "LUXCODE_CODEWHALE_ENABLED",
    "LUXCODE_CODEWHALE_REAL_REQUESTS_ENABLED",
    "LUXCODE_CODEWHALE_MANUAL_ONLY_CONFIRMED",
    "LUXCODE_CODEWHALE_PAID_MODEL_ACKNOWLEDGED",
)

CODEX_GATE_KEYS = (
    "LUXCODE_CODEX_ENABLED",
    "LUXCODE_CODEX_REAL_REQUESTS_ENABLED",
    "LUXCODE_CODEX_MANUAL_ONLY_CONFIRMED",
    "LUXCODE_CODEX_EMERGENCY_ONLY_CONFIRMED",
    "LUXCODE_CODEX_CREDIT_USAGE_ACKNOWLEDGED",
)

DIRECT_DEEPSEEK_GATE_KEYS = (
    "LUXCODE_DEEPSEEK_TRANSPORT_ENABLED",
    "LUXCODE_DEEPSEEK_BILLING_ENABLED",
    "LUXCODE_DEEPSEEK_REAL_REQUESTS_ENABLED",
)

ALLOWED_PERSISTENT_ENV_KEYS = frozenset(
    GEMINI_GATE_KEYS
    + OPENROUTER_GATE_KEYS
    + CODEWHALE_GATE_KEYS
    + CODEX_GATE_KEYS
    + DIRECT_DEEPSEEK_GATE_KEYS
    + (
        "LUXCODE_DESKTOP_AUTO_BACKEND",
        "LUXCODE_DESKTOP_WATCHDOG",
        "LUXCODE_DESKTOP_BUILD",
        "PORT",
        "LUXVIAI_RELOAD",
    )
)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "version": RUNTIME_VERSION,
    "backend": {
        "auto_start": True,
        "watchdog_enabled": True,
        "watchdog_interval_seconds": 10,
        "maximum_restarts_per_window": 3,
        "restart_window_seconds": 600,
    },
    "providers": {
        "gemini": {
            "enabled": False,
            "secret_reference": "gemini_api_key",
            "secret_environment_name": "GOOGLE_API_KEY",
            "environment": {},
        },
        "openrouter": {
            "enabled": False,
            "secret_reference": "openrouter_api_key",
            "secret_environment_name": "OPENROUTER_API_KEY",
            "environment": {},
        },
        "deepseek_chat": {
            "enabled": False,
            "secret_reference": "deepseek_api_key",
            "secret_environment_name": "DEEPSEEK_API_KEY",
            "environment": {},
        },
        "codewhale": {
            "enabled": False,
            "environment": {},
            "manual_only": True,
        },
        "codex": {
            "enabled": False,
            "environment": {},
            "manual_only": True,
            "emergency_only": True,
        },
        "direct_deepseek": {
            "enabled": False,
            "environment": {},
            "paid": True,
        },
    },
    "metadata": {
        "storage": "windows_dpapi_current_user",
        "plaintext_secrets_allowed": False,
        "created_by": "luxcode_persistent_runtime_v1",
    },
}


class RuntimeSettingsError(RuntimeError):
    pass


if os.name == "nt":
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]


def _runtime_dir(repository_root: str | Path | None = None) -> Path:
    if repository_root is None:
        return DEFAULT_RUNTIME_DIR
    root = Path(repository_root).expanduser().resolve()
    if root.name == ".luxcode_runtime":
        return root
    return root / ".luxcode_runtime"


def _settings_path(repository_root: str | Path | None = None) -> Path:
    return _runtime_dir(repository_root) / SETTINGS_FILENAME


def _credential_dir(repository_root: str | Path | None = None) -> Path:
    return _runtime_dir(repository_root) / CREDENTIAL_DIRNAME


def _deep_merge(base: Dict[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def load_runtime_settings(
    repository_root: str | Path | None = None,
) -> Dict[str, Any]:
    path = _settings_path(repository_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return copy.deepcopy(DEFAULT_SETTINGS)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return copy.deepcopy(DEFAULT_SETTINGS)
    if not isinstance(payload, dict):
        return copy.deepcopy(DEFAULT_SETTINGS)
    merged = _deep_merge(DEFAULT_SETTINGS, payload)
    merged["version"] = RUNTIME_VERSION
    return merged


def save_runtime_settings(
    settings: Mapping[str, Any],
    repository_root: str | Path | None = None,
) -> Path:
    merged = _deep_merge(DEFAULT_SETTINGS, settings)
    merged["version"] = RUNTIME_VERSION
    # Only non-secret metadata and allowlisted environment flags may be saved.
    providers = merged.get("providers", {})
    if isinstance(providers, dict):
        for provider in providers.values():
            if not isinstance(provider, dict):
                continue
            environment = provider.get("environment", {})
            if not isinstance(environment, dict):
                provider["environment"] = {}
                continue
            provider["environment"] = {
                str(key): str(value)
                for key, value in environment.items()
                if str(key) in ALLOWED_PERSISTENT_ENV_KEYS
            }
            for forbidden in ("api_key", "secret", "token", "password", "value"):
                provider.pop(forbidden, None)

    path = _settings_path(repository_root)
    encoded = json.dumps(
        merged,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    _atomic_write(path, encoded)
    return path


def _validate_secret_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if not SECRET_NAME_PATTERN.fullmatch(normalized):
        raise RuntimeSettingsError("invalid secret reference")
    return normalized


def _dpapi_protect(raw: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeSettingsError("Windows DPAPI is required")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_buffer = ctypes.create_string_buffer(raw)
    input_blob = _DataBlob(
        len(raw),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    output_blob = _DataBlob()
    description = "LuxCode Persistent Runtime"
    flags = 0x01  # CRYPTPROTECT_UI_FORBIDDEN
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        flags,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(raw: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeSettingsError("Windows DPAPI is required")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_buffer = ctypes.create_string_buffer(raw)
    input_blob = _DataBlob(
        len(raw),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    output_blob = _DataBlob()
    flags = 0x01
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        flags,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def store_secret(
    name: str,
    value: str,
    repository_root: str | Path | None = None,
    *,
    protector: Callable[[bytes], bytes] | None = None,
) -> Path:
    reference = _validate_secret_name(name)
    secret = str(value or "")
    if not secret:
        raise RuntimeSettingsError("empty secret cannot be stored")
    protect = protector or _dpapi_protect
    encrypted = protect(secret.encode("utf-8"))
    if not encrypted or secret.encode("utf-8") in encrypted:
        raise RuntimeSettingsError("secret protection failed")
    path = _credential_dir(repository_root) / f"{reference}.dpapi"
    _atomic_write(path, encrypted)
    return path


def load_secret(
    name: str,
    repository_root: str | Path | None = None,
    *,
    unprotector: Callable[[bytes], bytes] | None = None,
) -> str | None:
    reference = _validate_secret_name(name)
    path = _credential_dir(repository_root) / f"{reference}.dpapi"
    try:
        encrypted = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeSettingsError("secure credential could not be read") from exc
    unprotect = unprotector or _dpapi_unprotect
    try:
        raw = unprotect(encrypted)
        return raw.decode("utf-8")
    except Exception as exc:
        raise RuntimeSettingsError("secure credential could not be decrypted") from exc


def delete_secret(
    name: str,
    repository_root: str | Path | None = None,
) -> bool:
    reference = _validate_secret_name(name)
    path = _credential_dir(repository_root) / f"{reference}.dpapi"
    existed = path.exists()
    path.unlink(missing_ok=True)
    return existed


def _captured_environment(
    source: Mapping[str, str],
    keys: Iterable[str],
) -> Dict[str, str]:
    return {
        key: str(source[key])
        for key in keys
        if key in source and str(source[key]).strip()
    }


def capture_current_environment(
    repository_root: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    capture_free_providers: bool = True,
    capture_deepseek_chat: bool = False,
    enable_manual_agents: bool = False,
    protector: Callable[[bytes], bytes] | None = None,
) -> Dict[str, Any]:
    source = os.environ if environ is None else environ
    settings = load_runtime_settings(repository_root)
    providers = settings["providers"]
    captured: Dict[str, Any] = {}

    if capture_free_providers:
        gemini_name = (
            "GOOGLE_API_KEY"
            if str(source.get("GOOGLE_API_KEY") or "").strip()
            else "GEMINI_API_KEY"
            if str(source.get("GEMINI_API_KEY") or "").strip()
            else ""
        )
        gemini_value = str(source.get(gemini_name) or "") if gemini_name else ""
        if gemini_value:
            store_secret(
                "gemini_api_key",
                gemini_value,
                repository_root,
                protector=protector,
            )
            providers["gemini"].update(
                {
                    "enabled": True,
                    "secret_reference": "gemini_api_key",
                    "secret_environment_name": gemini_name,
                    "environment": _captured_environment(
                        source,
                        GEMINI_GATE_KEYS,
                    ),
                }
            )
            captured["gemini"] = {
                "captured": True,
                "secret_environment_name": gemini_name,
                "gate_count": len(providers["gemini"]["environment"]),
            }
        else:
            captured["gemini"] = {
                "captured": False,
                "reason": "key_missing_in_current_process",
            }

        openrouter_value = str(source.get("OPENROUTER_API_KEY") or "")
        if openrouter_value.strip():
            store_secret(
                "openrouter_api_key",
                openrouter_value,
                repository_root,
                protector=protector,
            )
            providers["openrouter"].update(
                {
                    "enabled": True,
                    "secret_reference": "openrouter_api_key",
                    "secret_environment_name": "OPENROUTER_API_KEY",
                    "environment": _captured_environment(
                        source,
                        OPENROUTER_GATE_KEYS,
                    ),
                }
            )
            captured["openrouter"] = {
                "captured": True,
                "gate_count": len(
                    providers["openrouter"]["environment"]
                ),
            }
        else:
            captured["openrouter"] = {
                "captured": False,
                "reason": "key_missing_in_current_process",
            }

    if capture_deepseek_chat:
        deepseek_value = str(source.get("DEEPSEEK_API_KEY") or "")
        if deepseek_value.strip():
            store_secret(
                "deepseek_api_key",
                deepseek_value,
                repository_root,
                protector=protector,
            )
            providers["deepseek_chat"].update(
                {
                    "enabled": True,
                    "secret_reference": "deepseek_api_key",
                    "secret_environment_name": "DEEPSEEK_API_KEY",
                    "environment": {},
                }
            )
            captured["deepseek_chat"] = {"captured": True}
        else:
            captured["deepseek_chat"] = {
                "captured": False,
                "reason": "key_missing_in_current_process",
            }

    if enable_manual_agents:
        providers["codewhale"].update(
            {
                "enabled": True,
                "environment": {
                    "LUXCODE_CODEWHALE_ENABLED": "1",
                    "LUXCODE_CODEWHALE_REAL_REQUESTS_ENABLED": "1",
                    "LUXCODE_CODEWHALE_MANUAL_ONLY_CONFIRMED": "1",
                    "LUXCODE_CODEWHALE_PAID_MODEL_ACKNOWLEDGED": "1",
                },
            }
        )
        providers["codex"].update(
            {
                "enabled": True,
                "environment": {
                    "LUXCODE_CODEX_ENABLED": "1",
                    "LUXCODE_CODEX_REAL_REQUESTS_ENABLED": "1",
                    "LUXCODE_CODEX_MANUAL_ONLY_CONFIRMED": "1",
                    "LUXCODE_CODEX_EMERGENCY_ONLY_CONFIRMED": "1",
                    "LUXCODE_CODEX_CREDIT_USAGE_ACKNOWLEDGED": "1",
                },
            }
        )
        captured["manual_agents"] = {
            "codewhale_ready_after_task_approval": True,
            "codex_ready_after_task_approval": True,
            "automatic_call_allowed": False,
        }

    backend = settings.setdefault("backend", {})
    backend.update(
        {
            "auto_start": True,
            "watchdog_enabled": True,
        }
    )
    save_runtime_settings(settings, repository_root)
    return {
        "ok": True,
        "captured": captured,
        "settings_path": str(_settings_path(repository_root)),
        "secret_values_returned": False,
        "plaintext_secret_written": False,
        "storage": "windows_dpapi_current_user",
    }


def build_runtime_environment(
    base_environment: Mapping[str, str] | None = None,
    repository_root: str | Path | None = None,
    *,
    secret_loader: Callable[[str, str | Path | None], str | None]
    | None = None,
) -> Dict[str, str]:
    result: Dict[str, str] = dict(
        os.environ if base_environment is None else base_environment
    )
    settings = load_runtime_settings(repository_root)
    providers = settings.get("providers", {})
    load = secret_loader or (
        lambda name, root: load_secret(name, root)
    )

    if isinstance(providers, dict):
        for provider in providers.values():
            if not isinstance(provider, dict) or not provider.get("enabled"):
                continue

            environment = provider.get("environment", {})
            if isinstance(environment, dict):
                for key, value in environment.items():
                    if key in ALLOWED_PERSISTENT_ENV_KEYS:
                        result[str(key)] = str(value)

            secret_reference = str(
                provider.get("secret_reference") or ""
            ).strip()
            secret_environment_name = str(
                provider.get("secret_environment_name") or ""
            ).strip()
            if secret_reference and secret_environment_name:
                try:
                    secret = load(secret_reference, repository_root)
                except RuntimeSettingsError:
                    secret = None
                if secret:
                    result[secret_environment_name] = secret

    backend = settings.get("backend", {})
    if isinstance(backend, dict):
        result["LUXCODE_DESKTOP_AUTO_BACKEND"] = (
            "1" if backend.get("auto_start", True) else "0"
        )
        result["LUXCODE_DESKTOP_WATCHDOG"] = (
            "1" if backend.get("watchdog_enabled", True) else "0"
        )
    result.setdefault("LUXVIAI_RELOAD", "0")
    result.setdefault("PORT", "5000")
    return result


def apply_persistent_runtime_environment(
    repository_root: str | Path | None = None,
    *,
    target: MutableMapping[str, str] | None = None,
) -> Dict[str, Any]:
    destination = os.environ if target is None else target
    before_keys = set(destination)
    built = build_runtime_environment(destination, repository_root)
    destination.update(built)
    status = get_runtime_status(repository_root)
    return {
        "ok": status.get("status") in {
            "READY",
            "PARTIAL",
            "NOT_CONFIGURED",
        },
        "status": status.get("status"),
        "settings_present": status.get("settings_present"),
        "providers_enabled": [
            name
            for name, item in status.get("providers", {}).items()
            if item.get("enabled")
        ],
        "environment_key_count": len(set(destination) - before_keys),
        "secret_values_returned": False,
        "plaintext_secret_written": False,
    }


def get_backend_runtime_policy(
    repository_root: str | Path | None = None,
) -> Dict[str, Any]:
    settings = load_runtime_settings(repository_root)
    backend = settings.get("backend", {})
    return {
        "auto_start": bool(backend.get("auto_start", True)),
        "watchdog_enabled": bool(
            backend.get("watchdog_enabled", True)
        ),
        "watchdog_interval_seconds": max(
            5,
            min(
                int(backend.get("watchdog_interval_seconds", 10) or 10),
                120,
            ),
        ),
        "maximum_restarts_per_window": max(
            1,
            min(
                int(
                    backend.get(
                        "maximum_restarts_per_window",
                        3,
                    )
                    or 3
                ),
                10,
            ),
        ),
        "restart_window_seconds": max(
            60,
            min(
                int(backend.get("restart_window_seconds", 600) or 600),
                3600,
            ),
        ),
    }


def get_runtime_status(
    repository_root: str | Path | None = None,
) -> Dict[str, Any]:
    settings_path = _settings_path(repository_root)
    settings = load_runtime_settings(repository_root)
    provider_status: Dict[str, Any] = {}
    blockers = []

    providers = settings.get("providers", {})
    if isinstance(providers, dict):
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            enabled = bool(provider.get("enabled"))
            secret_reference = str(
                provider.get("secret_reference") or ""
            ).strip()
            secret_present = bool(
                secret_reference
                and (
                    _credential_dir(repository_root)
                    / f"{secret_reference}.dpapi"
                ).is_file()
            )
            requires_secret = bool(secret_reference)
            ready = enabled and (secret_present or not requires_secret)
            if enabled and requires_secret and not secret_present:
                blockers.append(f"{name}_secret_missing")
            environment = provider.get("environment", {})
            provider_status[str(name)] = {
                "enabled": enabled,
                "ready": ready,
                "secret_required": requires_secret,
                "secret_present": secret_present,
                "gate_count": (
                    len(environment)
                    if isinstance(environment, dict)
                    else 0
                ),
                "manual_only": bool(provider.get("manual_only", False)),
                "emergency_only": bool(
                    provider.get("emergency_only", False)
                ),
                "paid": bool(provider.get("paid", False)),
            }

    enabled_count = sum(
        1 for item in provider_status.values() if item["enabled"]
    )
    ready_count = sum(
        1 for item in provider_status.values() if item["ready"]
    )
    if not settings_path.is_file():
        status = "NOT_CONFIGURED"
    elif blockers:
        status = "PARTIAL"
    else:
        status = "READY"

    return {
        "status": status,
        "version": RUNTIME_VERSION,
        "settings_present": settings_path.is_file(),
        "settings_path": str(settings_path),
        "runtime_dir": str(_runtime_dir(repository_root)),
        "storage": "windows_dpapi_current_user",
        "platform_supported": os.name == "nt",
        "plaintext_secrets_allowed": False,
        "plaintext_secret_written": False,
        "secret_values_returned": False,
        "providers": provider_status,
        "enabled_provider_count": enabled_count,
        "ready_provider_count": ready_count,
        "blockers": sorted(set(blockers)),
        "backend": get_backend_runtime_policy(repository_root),
    }


def acquire_single_instance_lock(
    repository_root: str | Path | None = None,
):
    runtime_dir = _runtime_dir(repository_root)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / LOCK_FILENAME
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except (OSError, IOError):
        handle.close()
        return None


def release_single_instance_lock(handle: Any) -> None:
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        handle.close()
    except Exception:
        pass


def show_single_instance_notice() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                "LuxCode zaten açık.",
                "LuxCode",
                0x40,
            )
            return
        except Exception:
            pass
    print("LuxCode zaten açık.")
