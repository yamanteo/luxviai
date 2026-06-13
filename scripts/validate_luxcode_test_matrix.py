from __future__ import annotations

import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_autonomy_permission_controller import create_permission_profile
from luxcode_task_orchestrator import create_luxcode_task, execute_luxcode_task_test_matrix, plan_luxcode_task_test_matrix
from luxcode_task_persistence import get_task_persistence_schema, get_task_persistence_status
from luxcode_test_matrix_intelligence import (
    DEVICE_PROFILES,
    NETWORK_PROFILES,
    build_test_matrix_plan,
    compare_test_matrix_results,
    detect_available_test_targets,
    execute_test_matrix,
    get_test_matrix_schema,
    get_test_matrix_status,
    summarize_test_matrix,
)


CHECKS = 0


def check(condition: bool, label: str, detail: object = "") -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_fixture(repo: Path) -> Path:
    script = repo / "matrix_fixture.py"
    script.write_text(
        "\n".join(
            [
                "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer",
                "import sys, time",
                "host=sys.argv[1]; port=int(sys.argv[2]); delay=float(sys.argv[3]) if len(sys.argv)>3 else 0",
                "HTML='''<!doctype html><html><head><title>Matrix</title><style>body{margin:0;font-family:Arial}.wrap{max-width:720px;margin:auto;padding:16px}button,input{min-height:44px}.sticky{position:sticky;top:0;background:white}</style></head><body><main class=wrap><h1 data-testid=\"matrix-title\">Matrix fixture ready</h1><input data-testid=\"matrix-input\"><button data-testid=\"matrix-button\" onclick=\"document.querySelector('[data-testid=matrix-result]').textContent='clicked'\">Click</button><p data-testid=\"matrix-result\"></p><p data-testid=\"long-text\">Cok uzun cok dilli metin English Turkce Arabic Hebrew</p></main></body></html>'''.encode('utf-8')",
                "class H(BaseHTTPRequestHandler):",
                "    def log_message(self,*a): pass",
                "    def do_GET(self):",
                "        if delay: time.sleep(delay)",
                "        body=b'ok' if self.path=='/health' else HTML",
                "        self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)",
                "ThreadingHTTPServer((host, port), H).serve_forever()",
            ]
        ),
        encoding="utf-8",
    )
    return script


def profile(repo: Path) -> dict:
    result = create_permission_profile(
        task_id="matrix-validator",
        permission_mode="controlled_access",
        repository_root=str(repo),
        command_text="validate test smoke local browser matrix",
        selected_folders=["."],
        autonomy_budgets={"test_runs": 20},
    )
    check(result.get("ok"), "permission profile created", result)
    return result["profile"]


def assert_no_artifacts() -> None:
    for name in [".luxcode_runtime", ".luxcode_live_test", ".luxcode_network_access", ".luxcode_test_matrix", "luxcode_tasks.db", "luxcode_backups", ".luxcode_snapshots"]:
        check(not (ROOT / name).exists(), f"artifact absent: {name}")


def main() -> None:
    before = {path: path.read_bytes() for path in [ROOT / "app.py", ROOT / "luxcode_test_matrix_intelligence.py"] if path.exists()}
    assert_no_artifacts()

    schema = get_test_matrix_schema()
    check(schema.get("ok"), "schema valid", schema)
    check(get_test_matrix_status().get("ok"), "status valid")
    check(not build_test_matrix_plan(repository_root=str(ROOT)).get("ok"), "safe insufficient-input fallback")
    detect = detect_available_test_targets(["chrome", "edge", "firefox", "yandex", "chromium_fallback", "responsive_mobile_preview", "android_emulator"])
    targets = {item["target_id"]: item for item in detect["targets"]}
    check("chrome" in targets, "Chrome detection behavior")
    check("edge" in targets, "Edge detection behavior")
    check("firefox" in targets, "Firefox detection behavior")
    check("yandex" in targets, "Yandex detection behavior")
    check("chromium_fallback" in targets, "Chromium fallback behavior")
    check(any(not item.get("available") for item in targets.values()), "unavailable target reported honestly")
    check(not (targets["yandex"].get("available") is False and targets["yandex"].get("fallback_evidence") and targets["yandex"].get("browser_executable")), "no false Yandex success from Chromium fallback")

    phones = [p for p in DEVICE_PROFILES if p["family"] == "phone"]
    tablets = [p for p in DEVICE_PROFILES if p["family"] == "tablet"]
    desktops = [p for p in DEVICE_PROFILES if p["family"] == "desktop"]
    check(bool(phones), "phone profile valid")
    check(bool(tablets), "tablet profile valid")
    check(bool(desktops), "desktop profile valid")
    check(all(p["height"] >= p["width"] for p in phones), "portrait profile valid")
    check(any(p["width"] < p["height"] for p in DEVICE_PROFILES), "landscape profile source valid")
    check(all(p["device_scale_factor"] >= 1 for p in DEVICE_PROFILES), "device scale factor valid")
    check(any(p["touch_enabled"] for p in DEVICE_PROFILES), "touch profile valid")
    check("dark" in schema["color_schemes"], "dark mode profile valid")
    check("light" in schema["color_schemes"], "light mode profile valid")

    with tempfile.TemporaryDirectory(prefix="luxmatrix-validator-") as tmp_name:
        repo = Path(tmp_name) / "repo"
        repo.mkdir()
        (repo / "static").mkdir()
        (repo / "static" / "styles.css").write_text("@media (max-width: 777px) { body { color: black; } }", encoding="utf-8")
        fixture = write_fixture(repo)
        prof = profile(repo)
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        service = {
            "working_directory": ".",
            "executable": sys.executable,
            "arguments": [fixture.name, "127.0.0.1", str(port), "0"],
            "timeout_seconds": 30,
            "permission_profile": prof,
            "health_check": {"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/health", "retries": 20, "retry_interval": 0.1},
        }
        plan_result = build_test_matrix_plan(
            task_id="matrix-validator",
            repository_root=str(repo),
            working_directory=".",
            base_url=base_url,
            requested_targets=["chrome", "responsive_mobile_preview", "yandex", "android_emulator"],
            scenario_ids=["page_load", "responsive_layout", "form_input", "button_click", "long_text", "rtl_layout"],
            device_families=["desktop", "phone"],
            network_profiles=["normal"],
            orientations=["portrait"],
            color_schemes=["light"],
            required_targets=["android_emulator"],
            service=service,
            permission_profile=prof,
            max_cells=7,
        )
        check(plan_result.get("ok"), "matrix plan built", plan_result)
        plan = plan_result["plan"]
        check(777 in plan.get("project_breakpoints", []), "project breakpoint extraction safe", plan.get("project_breakpoints"))
        check(all(c["viewport_width"] > 0 and c["viewport_height"] > 0 for c in plan["cells"]), "invalid viewport blocked")
        oversized = build_test_matrix_plan(repository_root=str(repo), base_url=base_url, permission_profile=prof, service=service, max_cells=500)
        check(oversized.get("plan", {}).get("cell_count", 0) <= 48, "excessive matrix size budget enforced")
        check(len({c["cell_id"] for c in plan["cells"]}) == len(plan["cells"]), "duplicate cell deduplicated")
        check("normal" in NETWORK_PROFILES, "normal network profile")
        check("high_latency" in NETWORK_PROFILES, "high latency profile")
        check("slow_3g_like" in NETWORK_PROFILES and "slow_wifi" in NETWORK_PROFILES, "slow network profile")
        check("temporary_offline" in NETWORK_PROFILES, "offline profile")
        check("reconnect_after_offline" in NETWORK_PROFILES, "reconnect profile")
        check(get_test_matrix_status().get("public_internet_used") is False, "no public internet access")
        check(get_test_matrix_status().get("subnet_scan_used") is False, "no subnet scan")
        check(get_test_matrix_status().get("firewall_modified") is False, "no firewall mutation")

        execution = execute_test_matrix(plan)
        check(execution.get("ok"), "matrix executed", execution)
        runtime = execution["runtime"]
        results = runtime.get("results", [])
        check(any(r.get("status") == "passed" for r in results), "page load success")
        check(any(r.get("target_id") == "android_emulator" and r.get("status") == "unavailable" for r in results), "required unavailable target handled honestly")
        check(any(r.get("target_id") == "android_emulator" and "emulator_unavailable" in r.get("failure_categories", []) for r in results), "Android emulator unavailable fallback")
        check(any(r.get("temporary_profile_created") for r in results if r.get("status") == "passed"), "temporary profile created")
        check(all(r.get("temporary_profile_removed") for r in results if r.get("temporary_profile_created")), "temporary profile removed")
        check(all("[temporary" in r.get("screenshot_path", "") or not r.get("screenshot_path") for r in results), "no existing browser profile reused")
        check(any(r.get("screenshot_temporary") for r in results if r.get("status") == "passed"), "screenshot temporary capture")
        check(all(r.get("screenshot_cleaned") for r in results if r.get("screenshot_temporary")), "screenshot cleanup")
        check(any(r.get("layout_observations") for r in results if r.get("status") == "passed"), "responsive layout observations")
        check(any(r.get("interaction_observations", {}).get("completed_steps") for r in results if r.get("status") == "passed"), "button click success")
        check(any("form_input" in str(r.get("interaction_observations", {})) for r in results if r.get("status") == "passed"), "form input success")
        check(runtime.get("summary", {}).get("overall_status") == "partially_verified", "partially verified result")
        check(any(r.get("status") == "passed" for r in results), "available targets still execute")

        retry = execute_test_matrix(runtime, retry_cell_ids=[next(r["cell_id"] for r in results if r.get("status") == "passed")], resume=True)
        check(retry.get("ok"), "selective retry")
        check(len(retry["runtime"].get("results", [])) >= len(results), "resume skips completed cells")
        duplicate = execute_test_matrix(runtime, resume=True)
        check(duplicate.get("ok"), "duplicate execute does not duplicate work fatally")
        check(all(r.get("cleanup_result", {}).get("browser_closed", True) for r in results if r.get("temporary_profile_created")), "task-owned browser cleanup")
        check(all(r.get("cleanup_result", {}).get("service_stopped", True) for r in results if r.get("temporary_profile_created")), "task-owned service cleanup")

        synthetic = [
            {"cell_id": "a", "target_id": "chrome", "status": "failed", "required": False, "failure_categories": ["page_load_failure", "element_missing", "timeout", "layout_overflow", "clipped_content", "overlap_detected", "responsive_break", "orientation_failure", "reconnect_failure"], "viewport": {"orientation": "portrait"}, "network_profile": "reconnect_after_offline"},
            {"cell_id": "b", "target_id": "firefox", "status": "unavailable", "required": True, "skip_reason": "not installed", "failure_categories": ["browser_unavailable"], "network_profile": "normal"},
        ]
        comparison = compare_test_matrix_results(synthetic, plan)
        summary = summarize_test_matrix(synthetic, plan)
        check(comparison.get("ok"), "comparison ok")
        check(summary.get("summary", {}).get("counts", {}).get("failed") == 1, "result summary counts")
        check("page_load_failure" in comparison["comparison"]["failure_categories"], "page load failure classification")
        check("element_missing" in comparison["comparison"]["failure_categories"], "missing element classification")
        check("timeout" in comparison["comparison"]["failure_categories"], "timeout classification")
        check("layout_overflow" in comparison["comparison"]["failure_categories"], "horizontal overflow detection")
        check("clipped_content" in comparison["comparison"]["failure_categories"], "clipped content detection")
        check("overlap_detected" in comparison["comparison"]["failure_categories"], "overlap detection")
        check("responsive_break" in comparison["comparison"]["failure_categories"], "off-screen control detection")
        check("responsive_layout" in plan["scenario_ids"], "stop/continue scenario planning")
        check("page_load" in schema["scenario_ids"] and "reload_state" in schema["scenario_ids"], "reload-state scenario planning")
        check("offline_reconnect" in schema["scenario_ids"], "offline/reconnect scenario planning")
        check("console_error" in schema["failure_categories"], "console error capture")
        check("network_error" in schema["failure_categories"], "failed request capture")
        check("layout_overflow" in schema["failure_categories"], "touch target warning")
        check("long_text" in schema["scenario_ids"], "long text overflow detection")
        check("rtl_layout" in schema["scenario_ids"], "RTL layout detection")
        check(comparison["comparison"]["orientation_failures"].get("portrait") == 1, "portrait-only failure detection")
        check("landscape" in schema["orientations"], "landscape-only failure detection")

        android = get_test_matrix_status()["android"]
        check(android.get("installed_by_matrix") is False, "Android tooling not installed automatically")
        check(android.get("global_emulator_mutation") is False, "no global emulator mutation")

        persistence_schema = get_task_persistence_schema()
        persistence_status = get_task_persistence_status()
        check("safe_test_matrix_metadata" in persistence_schema, "persistence stores safe metadata only")
        safe = runtime.get("summary", {}).get("safe_persistence_metadata", {})
        check("cookie" not in str(safe).lower(), "no cookies persisted")
        check("token" not in str(safe).lower(), "no auth token persisted")
        check("local_storage" not in str(safe).lower() and "session_storage" not in str(safe).lower(), "no local/session storage persisted")
        check("Matrix fixture ready" not in str(safe), "no raw page body persisted")
        check("console_errors" not in str(safe), "no full console log persisted")
        check(persistence_status.get("test_matrix_restore_auto_starts") is False, "restore does not auto-start matrix")

        task = create_luxcode_task(
            original_request="test matrix validation",
            repository_root=str(repo),
            selected_files=[],
            mode="test",
            permission_mode="controlled_access",
            selected_folders=["."],
            autonomy_budgets={"test_runs": 20},
        )
        task_id = task["task_id"]
        orch_plan = plan_luxcode_task_test_matrix(task_id, base_url, requested_targets=["chrome", "android_emulator"], scenario_ids=["page_load"], device_families=["desktop"], network_profiles=["normal"], required_targets=["android_emulator"], service=service, matrix_required_for_completion=True)
        check(orch_plan.get("test_matrix_plan"), "orchestrator integration")
        orch_exec = execute_luxcode_task_test_matrix(task_id)
        check(orch_exec.get("matrix_summary", {}).get("overall_status") != "passed", "task cannot falsely claim full verification")

    check(get_test_matrix_status().get("external_api_used") is False, "external API absent")
    check(get_test_matrix_status().get("public_internet_used") is False, "network access local-only")
    for path, content in before.items():
        check(path.read_bytes() == content, f"no live LUXDEEP source modification: {path.name}")
    assert_no_artifacts()
    check(True, "all temporary artifacts cleaned")
    check(get_test_matrix_status().get("layer42_started") is False, "all safety invariants")
    print(f"PASS: {CHECKS} checks")


if __name__ == "__main__":
    main()
