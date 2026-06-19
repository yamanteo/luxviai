from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(condition: bool, label: str, payload=None) -> None:
    if not condition:
        raise AssertionError(f"{label}: {payload!r}")


def main() -> int:
    from luxcode_runtime_settings import (
        apply_persistent_runtime_environment,
        build_runtime_environment,
        capture_current_environment,
        get_runtime_status,
        load_runtime_settings,
        load_secret,
        save_runtime_settings,
        store_secret,
    )

    checks = 0
    with tempfile.TemporaryDirectory(prefix="lux_runtime_validator_") as tmp:
        repo = Path(tmp)
        fake_protect = lambda raw: b"fixture-encrypted:" + raw[::-1]
        fake_unprotect = lambda raw: raw.split(b":", 1)[1][::-1]

        settings = load_runtime_settings(repo)
        check(settings["version"] == 1, "default settings")
        checks += 1

        save_runtime_settings(settings, repo)
        check((repo / ".luxcode_runtime" / "persistent_runtime.json").is_file(), "settings saved")
        checks += 1

        secret = "fixture-secret-value"
        secret_path = store_secret(
            "gemini_api_key",
            secret,
            repo,
            protector=fake_protect,
        )
        check(secret_path.is_file(), "secret file")
        check(secret.encode("utf-8") not in secret_path.read_bytes(), "secret encrypted")
        check(
            load_secret(
                "gemini_api_key",
                repo,
                unprotector=fake_unprotect,
            )
            == secret,
            "secret roundtrip",
        )
        checks += 3

        source_env = {
            "GOOGLE_API_KEY": "google-fixture-secret",
            "OPENROUTER_API_KEY": "openrouter-fixture-secret",
            "LUXCODE_GEMINI_ENABLED": "1",
            "LUXCODE_GEMINI_VERIFIED": "1",
            "LUXCODE_GEMINI_TRANSPORT_ENABLED": "1",
            "LUXCODE_GEMINI_REAL_REQUESTS_ENABLED": "1",
            "LUXCODE_GEMINI_NETWORK_ALLOWED": "1",
            "LUXCODE_GEMINI_FREE_TIER_CONFIRMED": "1",
            "LUXCODE_GEMINI_BILLING_DISABLED_CONFIRMED": "1",
            "LUXCODE_GEMINI_QUOTA_STATE": "available",
            "LUXCODE_GEMINI_QUOTA_AVAILABLE": "1",
            "LUXCODE_GEMINI_MODEL_ACCESS_VERIFIED": "1",
            "LUXCODE_GEMINI_AUTH_KEY_CONFIRMED": "1",
            "LUXCODE_GEMINI_KEY_TYPE": "restricted_standard",
            "LUXCODE_OPENROUTER_ENABLED": "1",
            "LUXCODE_OPENROUTER_TRANSPORT_ENABLED": "1",
            "LUXCODE_OPENROUTER_REAL_REQUESTS": "1",
            "LUXCODE_OPENROUTER_NETWORK_ALLOWED": "1",
            "LUXCODE_OPENROUTER_FREE_TIER_CONFIRMED": "1",
            "LUXCODE_OPENROUTER_MODEL_ACCESS_VERIFIED": "1",
            "LUXCODE_OPENROUTER_QUOTA_STATE": "available",
        }
        report = capture_current_environment(
            repo,
            environ=source_env,
            capture_free_providers=True,
            enable_manual_agents=True,
            protector=fake_protect,
        )
        check(report["ok"] is True, "capture report", report)
        check(report["secret_values_returned"] is False, "no secret response")
        checks += 2

        settings = load_runtime_settings(repo)
        check(settings["providers"]["gemini"]["enabled"] is True, "gemini enabled")
        check(settings["providers"]["openrouter"]["enabled"] is True, "openrouter enabled")
        check(settings["providers"]["codewhale"]["enabled"] is True, "codewhale ready")
        check(settings["providers"]["codex"]["enabled"] is True, "codex ready")
        checks += 4

        def fixture_loader(name, _root):
            return {
                "gemini_api_key": "google-fixture-secret",
                "openrouter_api_key": "openrouter-fixture-secret",
            }.get(name)

        built = build_runtime_environment(
            {},
            repo,
            secret_loader=fixture_loader,
        )
        check(built["GOOGLE_API_KEY"] == "google-fixture-secret", "gemini applied")
        check(built["OPENROUTER_API_KEY"] == "openrouter-fixture-secret", "openrouter applied")
        check(built["LUXCODE_CODEWHALE_ENABLED"] == "1", "codewhale gates")
        check(built["LUXCODE_CODEX_ENABLED"] == "1", "codex gates")
        check(built["LUXVIAI_RELOAD"] == "0", "reload disabled")
        checks += 5

        target = {}
        # Only settings/status behavior is checked here; fake credentials cannot
        # be decrypted through the production DPAPI loader.
        applied = apply_persistent_runtime_environment(repo, target=target)
        check(applied["secret_values_returned"] is False, "apply redacted")
        checks += 1

        status = get_runtime_status(repo)
        encoded_status = json.dumps(status)
        check(status["settings_present"] is True, "status settings")
        check("google-fixture-secret" not in encoded_status, "status no gemini secret")
        check("openrouter-fixture-secret" not in encoded_status, "status no openrouter secret")
        check(status["plaintext_secrets_allowed"] is False, "plaintext forbidden")
        checks += 4

        if os.name == "nt":
            dpapi_path = store_secret(
                "dpapi_validator",
                "dpapi-fixture-secret",
                repo,
            )
            check(
                b"dpapi-fixture-secret" not in dpapi_path.read_bytes(),
                "dpapi ciphertext",
            )
            check(
                load_secret("dpapi_validator", repo)
                == "dpapi-fixture-secret",
                "dpapi roundtrip",
            )
            checks += 2

    print(json.dumps({"status": "PASS", "checks": checks}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
