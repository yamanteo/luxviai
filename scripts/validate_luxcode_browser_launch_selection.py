from __future__ import annotations

import ast
import hashlib
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from endpoint_coverage_matrix import ENDPOINT_GROUPS
from luxcode_browser_launch_selection import (
    build_browser_launch_request,
    detect_browser_executables,
    get_browser_launch_schema,
    get_browser_launch_status,
    normalize_browser_family,
    select_browser_executable,
    summarize_browser_launch_result,
    launch_selected_browser,
    terminate_selected_browser,
    verify_launched_browser_identity,
)


EXPECTED_FILES = {
    "luxcode_browser_launch_selection.py",
    "scripts/validate_luxcode_browser_launch_selection.py",
    "luxcode_test_matrix_intelligence.py",
    "luxcode_live_app_interaction_testing.py",
    "luxcode_terminal_process_runtime.py",
    "luxcode_task_orchestrator.py",
    "luxcode_task_persistence.py",
    "app.py",
    "endpoint_coverage_matrix.py",
    "scripts/smoke_check.py",
}
EXPECTED_ENDPOINTS = {
    "/luxcode-browser-launch/schema",
    "/luxcode-browser-launch/detect",
    "/luxcode-browser-launch/select",
    "/luxcode-browser-launch/launch",
    "/luxcode-browser-launch/verify",
    "/luxcode-browser-launch/terminate",
    "/debug/luxcode-browser-launch-status",
}


class CheckCounter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, message: str) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8", errors="ignore")


def assert_no_blocked_source_patterns(checks: CheckCounter) -> None:
    core = source("luxcode_browser_launch_selection.py")
    checks.check("shell=False" in core, "browser launch must use shell=False")
    checks.check("os.walk" not in core and "glob(" not in core, "browser detection must not scan recursively")
    checks.check("winreg" not in core, "registry access must not be used")
    checks.check("shutil.which" not in core, "PATH based executable discovery must not be used")
    checks.check("requests." not in core, "external requests library must not be used")
    checks.check("pip install" not in core, "package installation must be absent")
    checks.check("rundll32" not in core.lower(), "shutdown/suspend helpers must be absent")
    checks.check("CREATE EXTENSION" not in core, "extension installation must be absent")
    checks.check("--load-extension" not in core, "extension loading must be absent")
    checks.check("--user-data-dir" in core, "temporary profile flag must be used")
    checks.check("--profile-directory" not in core, "existing browser profile must not be reused")
    checks.check("subprocess.Popen" in core, "structured browser launch must be implemented")
    checks.check("taskkill" in core or "terminate_selected_browser" in core, "owned cleanup must be implemented")
    checks.check("public_internet_used" in core, "public internet safety flag must be present")


def main() -> None:
    checks = CheckCounter()
    hashes = {rel: sha(ROOT / rel) for rel in EXPECTED_FILES if (ROOT / rel).exists()}
    live_artifacts = [ROOT / ".luxcode_browser_launch", ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_test_matrix", ROOT / "luxcode_tasks.db"]
    before_artifacts = {str(path): path.exists() for path in live_artifacts}

    schema = get_browser_launch_schema()
    checks.check(schema.get("ok") is True, "schema must be ok")
    checks.check(schema.get("shell_execution_allowed") is False, "shell execution must be blocked")
    checks.check("yandex" in schema.get("supported_families", []), "schema must include yandex")
    checks.check(schema.get("temporary_profile_required") is True, "temporary profile must be required")
    checks.check(schema.get("identity_verification_required") is True, "identity verification must be required")

    status = get_browser_launch_status()
    checks.check(status.get("ok") is True, "status must be ok")
    checks.check(status.get("external_api_used") is False, "external API must be false")
    checks.check(status.get("temporary_profile_required") is True, "status must report temporary profile policy")

    checks.check(normalize_browser_family("Google Chrome")["normalized_family"] == "chrome", "Chrome normalization failed")
    checks.check(normalize_browser_family("msedge")["normalized_family"] == "edge", "Edge normalization failed")
    checks.check(normalize_browser_family("Firefox")["normalized_family"] == "firefox", "Firefox normalization failed")
    checks.check(normalize_browser_family("Yandex")["normalized_family"] == "yandex", "Yandex normalization failed")
    checks.check(normalize_browser_family("Chromium Browser")["normalized_family"] == "unknown", "Unknown Chromium alias should stay explicit")
    checks.check(normalize_browser_family("not-a-browser")["supported"] is False, "unknown family must be rejected")

    with tempfile.TemporaryDirectory(prefix="lux_browser_launch_validator_") as tmp_name:
        tmp = Path(tmp_name)
        real_detection = detect_browser_executables(str(tmp))
        checks.check(real_detection.get("ok") is True, "safe detection call must succeed")
        detected = real_detection.get("detected", {})
        checks.check(set(detected) >= {"chrome", "edge", "firefox", "yandex", "chromium"}, "detection must include family records")

        for family in ("chrome", "edge", "firefox", "yandex", "chromium"):
            selected = select_browser_executable(family, detected, {"allow_fallback": False}, "validator", {"target_id": family})
            if detected.get(family, {}).get("available"):
                checks.check(selected.get("ok") is True, f"{family} exact selection failed")
                checks.check(selected.get("selected_family") == family, f"{family} selected family mismatch")
                checks.check(selected.get("exact_match") is True, f"{family} must be exact")
                checks.check(Path(selected.get("selected_executable", "")).exists(), f"{family} executable must be detected safe file")
            else:
                checks.check(selected.get("ok") is False, f"{family} unavailable selection must fail safely")
                checks.check(selected.get("launch_allowed") is False, f"{family} unavailable must not be launchable")

        missing = dict(detected)
        missing["yandex"] = {"family": "yandex", "available": False, "first_available": "", "candidates": []}
        yandex_missing = select_browser_executable("yandex", missing, {"allow_fallback": True}, "validator", {})
        checks.check(yandex_missing.get("ok") is False, "Yandex must not silently fall back to Chrome")
        checks.check(yandex_missing.get("exact_match") is False, "missing Yandex must not be exact")

        missing_firefox = dict(detected)
        missing_firefox["firefox"] = {"family": "firefox", "available": False, "first_available": "", "candidates": []}
        firefox_missing = select_browser_executable("firefox", missing_firefox, {"allow_fallback": True}, "validator", {})
        checks.check(firefox_missing.get("ok") is False, "Firefox must not fall back to Chromium")

        fallback = select_browser_executable("chromium_fallback", detected, {"allow_fallback": True}, "validator", {})
        checks.check(fallback.get("ok") is True, "explicit Chromium fallback must be selectable")
        checks.check(fallback.get("fallback_used") is True, "Chromium fallback must stay labeled fallback")
        disabled_fallback = select_browser_executable("chromium_fallback", detected, {"allow_fallback": False}, "validator", {})
        checks.check(disabled_fallback.get("ok") is False, "fallback disabled behavior failed")

        fake_path = tmp / "fake-chrome.exe"
        fake_path.write_text("fixture", encoding="utf-8")
        arbitrary = select_browser_executable("chrome", {"chrome": {"available": True, "candidates": [{"path": str(fake_path), "available": True}]}}, {}, "validator", {})
        checks.check(arbitrary.get("ok") is False, "arbitrary executable path must be rejected during selection")
        invalid_request = build_browser_launch_request("task", "target", "chrome", "chrome", str(fake_path), authority_digest="auth")
        checks.check(invalid_request.get("ok") is False, "arbitrary missing executable path must be rejected")

        available_family = next((name for name in ("chrome", "edge", "yandex", "chromium") if detected.get(name, {}).get("available")), "")
        checks.check(bool(available_family), "at least one Chromium-family browser must be locally available for launch request validation")
        selected_available = select_browser_executable(available_family, detected, {"allow_fallback": False}, "validator", {})
        request = build_browser_launch_request(
            "task",
            "target",
            available_family,
            selected_available["selected_family"],
            selected_available["selected_executable"],
            remote_debugging_port=9222,
            expected_identity="http://127.0.0.1:1",
            authority_digest="validator",
        )
        checks.check(request.get("ok") is True, "launch request must build")
        checks.check(request.get("temporary_profile_dir") == "", "validator must not create live profile")
        checks.check(request.get("remote_debugging_port") == 9222, "debug port must be preserved")
        checks.check(request.get("executable_digest"), "selected executable digest missing")
        checks.check(request.get("verification_required") is True, "verification must be required")
        public_request = build_browser_launch_request("task", "target", available_family, selected_available["selected_family"], selected_available["selected_executable"], expected_identity="https://example.com", authority_digest="validator")
        checks.check(public_request.get("ok") is False, "public URL launch request must be blocked")

        if detected.get("yandex", {}).get("available"):
            class FixtureHandler(BaseHTTPRequestHandler):
                def log_message(self, *args: object) -> None:
                    pass

                def do_GET(self) -> None:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"validator")

            server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            yandex = select_browser_executable("yandex", detected, {"allow_fallback": False}, "validator-yandex-launch", {})
            checks.check(yandex.get("ok") is True, "Yandex exact selection must work when locally available")
            request = build_browser_launch_request(
                "validator-yandex-launch",
                "yandex",
                "yandex",
                yandex["selected_family"],
                yandex["selected_executable"],
                executable_digest=yandex.get("executable_digest", ""),
                expected_identity=url,
                authority_digest="validator-yandex-launch",
                cleanup_timeout=5,
            )
            checks.check(request.get("ok") is True, "Yandex real launch request must build")
            request["controlled_url"] = url
            launch = launch_selected_browser(request)
            checks.check(launch.get("ok") is True, "Yandex real local fixture launch failed")
            verification = verify_launched_browser_identity(launch["runtime_id"], expected_identity="yandex")
            checks.check(verification.get("ok") is True, "Yandex identity verification failed")
            checks.check(verification.get("mismatch_detected") is False, "Yandex must not be reported as Chrome mismatch when Yandex executable owns launch")
            cleanup = terminate_selected_browser(launch["runtime_id"], reason="validator cleanup")
            checks.check(cleanup.get("ok") is True, "Yandex cleanup failed")
            checks.check(cleanup.get("temporary_profile_removed") is True, "Yandex temporary profile must be removed")
            server.shutdown()
            server.server_close()

    identity_missing = verify_launched_browser_identity("missing-runtime", expected_identity="chrome")
    checks.check(identity_missing.get("ok") is False, "missing runtime verification must fail safely")
    summary = summarize_browser_launch_result({"runtime_id": "r1", "status": "done", "request": {}, "result": {}})
    checks.check(summary.get("ok") is True and summary.get("safety", {}).get("shell_false") is True, "summary safety missing")

    matrix = ENDPOINT_GROUPS.get("luxcode_browser_launch", [])
    checks.check(len(matrix) == 7, "endpoint matrix must contain exactly seven browser launch records")
    checks.check({item["path"] for item in matrix} == EXPECTED_ENDPOINTS, "endpoint matrix paths mismatch")

    app_source = source("app.py")
    for path in EXPECTED_ENDPOINTS:
        checks.check(path in app_source, f"app endpoint missing: {path}")
    checks.check(app_source.count("/luxcode-browser-launch/") == 6, "app must contain six luxcode-browser-launch routes")
    checks.check(app_source.count("/debug/luxcode-browser-launch-status") == 1, "app must contain one debug browser-launch route")

    live_source = source("luxcode_live_app_interaction_testing.py")
    checks.check("luxcode_browser_launch_selection" in live_source, "live testing must delegate to browser launch core")
    checks.check("browser_launch_request" in live_source, "live testing must accept launch request")
    checks.check("terminate_selected_browser" in live_source, "live testing must cleanup via launch core")

    matrix_source = source("luxcode_test_matrix_intelligence.py")
    checks.check("requested_browser_family" in matrix_source, "matrix must record requested browser family")
    checks.check("selected_browser_family" in matrix_source, "matrix must record selected browser family")
    checks.check("identity_verified" in matrix_source, "matrix must record identity verification")
    checks.check("browser_identity_mismatch" in matrix_source, "matrix must record identity mismatch")
    checks.check("fallback_used" in matrix_source, "matrix must label fallback")

    orchestrator_source = source("luxcode_task_orchestrator.py")
    checks.check("browser_launch_state" in orchestrator_source, "orchestrator must track browser launch state")
    checks.check("browser_identity_mismatches" in orchestrator_source, "orchestrator must track mismatches")
    checks.check("browser_launch_completed" in orchestrator_source, "orchestrator launch completed state missing")

    persistence_source = source("luxcode_task_persistence.py")
    checks.check("safe_browser_launch_metadata" in persistence_source, "persistence safe browser metadata missing")
    checks.check("cookie" in persistence_source.lower(), "persistence redaction vocabulary must remain")
    checks.check("raw logs" not in persistence_source.lower(), "raw logs must not be persisted as a field")

    terminal_source = source("luxcode_terminal_process_runtime.py")
    checks.check("probe_browser_version" in terminal_source, "terminal browser version probe missing")
    checks.check("browser executable not approved" in terminal_source, "terminal browser executable allowlist guard missing")

    assert_no_blocked_source_patterns(checks)

    core_ast = ast.parse(source("luxcode_browser_launch_selection.py"))
    names = {node.name for node in core_ast.body if isinstance(node, ast.FunctionDef)}
    for name in {
        "get_browser_launch_schema",
        "normalize_browser_family",
        "detect_browser_executables",
        "select_browser_executable",
        "build_browser_launch_request",
        "launch_selected_browser",
        "verify_launched_browser_identity",
        "terminate_selected_browser",
        "summarize_browser_launch_result",
        "get_browser_launch_status",
    }:
        checks.check(name in names, f"public function missing: {name}")

    smoke_source = source("scripts/smoke_check.py")
    checks.check("luxcode_browser_launch_selection_local" in smoke_source, "targeted smoke registration missing")
    checks.check("/luxcode-browser-launch/launch" in smoke_source, "targeted smoke launch endpoint missing")
    checks.check("explicit_launch_intent" in smoke_source, "targeted smoke must verify explicit launch intent")
    checks.check("terminate" in smoke_source, "targeted smoke cleanup missing")

    for rel, before in hashes.items():
        checks.check(sha(ROOT / rel) == before, f"validator modified source file: {rel}")
    for path in live_artifacts:
        checks.check(path.exists() is before_artifacts[str(path)], f"validator changed live artifact state: {path.name}")

    print(f"PASS validate_luxcode_browser_launch_selection checks={checks.count}")


if __name__ == "__main__":
    main()
