from __future__ import annotations

import socket
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_autonomy_permission_controller import create_permission_profile
from luxcode_live_app_interaction_testing import (
    cancel_live_test_runtime,
    execute_live_test,
    get_live_test_evidence,
    get_live_test_runtime,
    get_live_testing_registry,
    get_live_testing_schema,
    get_live_testing_status,
    plan_live_test,
    restore_live_test_record,
    validate_live_scenario,
)


CHECKS: List[str] = []


def check(name: str, condition: bool, details: Any = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {details!r}")
    CHECKS.append(name)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_fixture(repo: Path) -> None:
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "fixture_app.py").write_text(
        r'''
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

HTML = b"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>LuxCode Fixture</title>
<style>
  body { font-family: sans-serif; }
  #mobile-only { display: none; }
  @media (max-width: 600px) { #desktop-only { display: none; } #mobile-only { display: block; } }
</style>
</head>
<body>
  <h1 data-testid='title'>Fixture ready</h1>
  <a data-testid='nav-link' href='/next'>Next</a>
  <form data-testid='fixture-form' onsubmit="event.preventDefault(); document.querySelector('[data-testid=result]').textContent = 'Hello ' + document.querySelector('[data-testid=name-input]').value;">
    <input data-testid='name-input' placeholder='name'>
    <button data-testid='submit-button'>Submit</button>
  </form>
  <div data-testid='result'></div>
  <div data-testid='hidden-panel' hidden>secret panel</div>
  <div data-testid='desktop-only' id='desktop-only'>desktop viewport ready</div>
  <div data-testid='mobile-only' id='mobile-only'>mobile viewport ready</div>
  <button data-testid='console-error' onclick="console.error('token=abc123456789SECRET')">Console</button>
  <section data-testid='stream-fixture'>
    <input data-testid='question-input'>
    <button data-testid='start-list' onclick='startList()'>Start</button>
    <button data-testid='stop-list' onclick='stopList()'>Stop</button>
    <button data-testid='resume-list' onclick='resumeList()'>Devam et</button>
    <button data-testid='new-question' onclick='newQuestion()'>New</button>
    <ol data-testid='list-output' id='list-output'></ol>
    <div data-testid='question-result' id='question-result'></div>
  </section>
  <script>
    let timer = null, index = 0, stopped = false;
    function addItem(text) { const li = document.createElement('li'); li.className = 'item'; li.dataset.testid = 'item-' + (index + 1); li.textContent = text; document.getElementById('list-output').appendChild(li); }
    function startList() { document.getElementById('list-output').innerHTML = ''; index = 0; stopped = false; addItem('1. complete'); index = 1; addItem('2. complete'); index = 2; addItem('3. partial'); index = 3; }
    function stopList() { stopped = true; if (timer) clearInterval(timer); }
    function resumeList() { stopped = false; const items = document.querySelectorAll('.item'); if (items[2]) items[2].textContent = '3. complete'; while (document.querySelectorAll('.item').length < 5) { index = document.querySelectorAll('.item').length + 1; addItem(index + '. complete'); } }
    function newQuestion() { document.getElementById('question-result').textContent = 'new answer: ' + document.querySelector('[data-testid=question-input]').value; document.getElementById('list-output').innerHTML = ''; }
  </script>
</body>
</html>"""

NEXT = b"<!doctype html><html><body><h1 data-testid='next-title'>Next page ready</h1></body></html>"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        if self.path == "/next":
            self.send_response(200); self.end_headers(); self.wfile.write(NEXT); return
        self.send_response(200); self.end_headers(); self.wfile.write(HTML)

HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
'''.lstrip(),
        encoding="utf-8",
    )


def scenario(base_url: str, scenario_id: str, steps: List[Dict[str, Any]], viewport: str = "desktop") -> Dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "task_id": f"task-{scenario_id}",
        "scenario_name": scenario_id,
        "base_url": base_url,
        "allowed_origin": base_url,
        "viewport": viewport,
        "steps": steps,
        "per_step_timeout_seconds": 5,
        "scenario_timeout_seconds": 45,
        "retry_policy": {"max_retries": 0},
        "evidence_policy": {"screenshots": True, "structured": True},
        "expected_final_state": "scenario_passed",
        "headless": True,
    }


def main() -> None:
    schema = get_live_testing_schema()
    check("schema exposes structured actions", "click" in schema["supported_actions"], schema)
    check("raw javascript endpoint absent", schema["raw_javascript_endpoint"] is False, schema)
    registry = get_live_testing_registry()
    check("browser registry resolved", registry["browser_adapter"]["engine"] == "chromium_cdp", registry)
    check("browser available locally", registry["browser_adapter"]["available"] is True, registry)
    check("no browser download required", registry["browser_adapter"]["downloads_required"] is False, registry)

    watched = [ROOT / "app.py", ROOT / "endpoint_coverage_matrix.py", ROOT / "scripts" / "smoke_check.py", ROOT / "static" / "index.html"]
    before = {str(path): path.read_bytes() for path in watched if path.exists()}
    live_paths = [ROOT / ".luxcode_runtime", ROOT / ".luxcode_live_test", ROOT / ".luxcode_snapshots", ROOT / "luxcode_tasks.db", ROOT / "luxcode_backups"]
    live_state = {str(path): path.exists() for path in live_paths}

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        write_fixture(repo)
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        profile = create_permission_profile(
            task_id="live-validator",
            permission_mode="controlled_access",
            repository_root=str(repo),
            command_text="run tests for local live app fixture",
            scope_items=[{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
        )["profile"]
        service = {
            "working_directory": ".",
            "executable": "python",
            "arguments": ["scripts/fixture_app.py", str(port)],
            "timeout_seconds": 30,
            "permission_profile": profile,
            "health_check": {"check_type": "http_get", "host": "127.0.0.1", "port": port, "path": "/health", "retries": 10, "retry_interval": 0.1},
        }

        form = scenario(base_url, "basic_form", [
            {"step_id": "desktop", "action_type": "set_viewport", "viewport": "desktop"},
            {"step_id": "navigate", "action_type": "navigate", "target_url": base_url},
            {"step_id": "ready", "action_type": "wait_for_ready"},
            {"step_id": "title", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "title"}},
            {"step_id": "fill", "action_type": "fill", "selector": {"type": "test_id", "value": "name-input"}, "value": "Ada token=abc123456789SECRET"},
            {"step_id": "submit", "action_type": "click", "selector": {"type": "test_id", "value": "submit-button"}},
            {"step_id": "result", "action_type": "assert_text_contains", "selector": {"type": "test_id", "value": "result"}, "expected_text": "Hello Ada"},
            {"step_id": "hidden", "action_type": "assert_hidden", "selector": {"type": "test_id", "value": "hidden-panel"}},
            {"step_id": "shot", "action_type": "capture_screenshot"},
        ])
        validation = validate_live_scenario(form)
        check("form scenario validates", validation["valid"] is True, validation)
        plan = plan_live_test(form, repository_root=str(repo), working_directory=".", permission_profile=profile, service=service)
        check("form plan ok", plan["ok"] is True, plan)
        check("permission allowed", plan["plan"]["permission_decision"]["allowed"] is True, plan)
        result = execute_live_test(plan["plan"])
        runtime = result["runtime"]
        check("form scenario passed", runtime["state"] == "scenario_passed", runtime)
        check("service managed through terminal runtime", runtime.get("service_runtime", {}).get("shell") is False, runtime)
        check("browser owned by runtime", runtime.get("browser", {}).get("owned_by_runtime") is True, runtime)
        check("screenshot evidence captured", runtime.get("evidence", [{}])[0].get("cleaned") is True, runtime)
        check("secret redacted from runtime", "abc123456789SECRET" not in str(runtime), runtime)
        evidence = get_live_test_evidence(runtime["live_test_runtime_id"])
        check("evidence endpoint returns metadata", evidence["ok"] is True and evidence["evidence"], evidence)
        check("runtime lookup works", get_live_test_runtime(runtime["live_test_runtime_id"])["ok"] is True, runtime)

        view = scenario(base_url, "viewport_matrix", [
            {"step_id": "nav", "action_type": "navigate", "target_url": base_url},
            {"step_id": "desktop", "action_type": "set_viewport", "viewport": "desktop"},
            {"step_id": "desktop-visible", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "desktop-only"}},
            {"step_id": "mobile", "action_type": "set_viewport", "viewport": "mobile"},
            {"step_id": "mobile-reload", "action_type": "navigate", "target_url": base_url},
            {"step_id": "mobile-visible", "action_type": "assert_visible", "selector": {"type": "test_id", "value": "mobile-only"}},
        ])
        view_plan = plan_live_test(view, repository_root=str(repo), working_directory=".", permission_profile=profile, service=service)
        check("viewport plan ok", view_plan["ok"] is True, view_plan)
        view_result = execute_live_test(view_plan["plan"])["runtime"]
        check("desktop mobile viewport passed", view_result["state"] == "scenario_passed", view_result)
        check("mobile wording is viewport only", "physical" not in str(view_result).lower(), view_result)

        stop_resume = scenario(base_url, "stream_stop_resume_list_continuity", [
            {"step_id": "nav", "action_type": "navigate", "target_url": base_url},
            {"step_id": "start", "action_type": "click", "selector": {"type": "test_id", "value": "start-list"}},
            {"step_id": "third-visible", "action_type": "wait_for_selector", "selector": {"type": "test_id", "value": "item-3"}, "timeout_seconds": 8},
            {"step_id": "stop", "action_type": "click", "selector": {"type": "test_id", "value": "stop-list"}},
            {"step_id": "no-new-after-stop", "action_type": "assert_element_count", "selector": ".item", "expected_count": 3},
            {"step_id": "resume", "action_type": "click", "selector": {"type": "test_id", "value": "resume-list"}},
            {"step_id": "third-complete", "action_type": "assert_text", "selector": {"type": "test_id", "value": "item-3"}, "expected_text": "3. complete"},
            {"step_id": "list-complete", "action_type": "assert_element_count", "selector": ".item", "expected_count": 5},
            {"step_id": "new-fill", "action_type": "fill", "selector": {"type": "test_id", "value": "question-input"}, "value": "fresh question"},
            {"step_id": "new-question", "action_type": "click", "selector": {"type": "test_id", "value": "new-question"}},
            {"step_id": "no-old-pending", "action_type": "assert_element_count", "selector": ".item", "expected_count": 0},
            {"step_id": "new-answer", "action_type": "assert_text_contains", "selector": {"type": "test_id", "value": "question-result"}, "expected_text": "fresh question"},
        ])
        stop_plan = plan_live_test(stop_resume, repository_root=str(repo), working_directory=".", permission_profile=profile, service=service)
        check("stop resume plan ok", stop_plan["ok"] is True, stop_plan)
        stop_result = execute_live_test(stop_plan["plan"])["runtime"]
        check("stop resume scenario passed", stop_result["state"] == "scenario_passed", stop_result)

        console_scenario = scenario(base_url, "console_errors", [
            {"step_id": "nav", "action_type": "navigate", "target_url": base_url},
            {"step_id": "error", "action_type": "click", "selector": {"type": "test_id", "value": "console-error"}},
            {"step_id": "collect", "action_type": "collect_console_errors"},
        ])
        console_result = execute_live_test(plan_live_test(console_scenario, repository_root=str(repo), working_directory=".", permission_profile=profile, service=service)["plan"])["runtime"]
        check("console scenario passed", console_result["state"] == "scenario_passed", console_result)
        check("console secret redacted", "abc123456789SECRET" not in str(console_result), console_result)

        external = validate_live_scenario(scenario("https://example.com", "external", [{"step_id": "nav", "action_type": "navigate", "target_url": "https://example.com"}]))
        check("external url rejected", external["valid"] is False, external)
        raw = validate_live_scenario(scenario(base_url, "raw", [{"step_id": "raw", "action_type": "raw_javascript", "script": "alert(1)"}]))
        check("raw script rejected", raw["valid"] is False, raw)
        invalid_selector = validate_live_scenario(scenario(base_url, "bad_selector", [{"step_id": "bad", "action_type": "click", "selector": "div; window.x=1"}]))
        check("invalid selector rejected", invalid_selector["valid"] is False, invalid_selector)
        unsupported = validate_live_scenario(scenario(base_url, "unsupported", [{"step_id": "drag", "action_type": "drag_to"}]))
        check("unsupported action rejected", unsupported["valid"] is False, unsupported)
        outside = plan_live_test(form, repository_root=str(repo), working_directory="..", permission_profile=profile)
        check("scope violation rejected", outside["ok"] is False, outside)
        timeout_case = scenario(base_url, "timeout", [{"step_id": "missing", "action_type": "wait_for_selector", "selector": {"type": "test_id", "value": "never"}, "timeout_seconds": 1}])
        timeout_result = execute_live_test(plan_live_test(timeout_case, repository_root=str(repo), working_directory=".", permission_profile=profile, service=service)["plan"])["runtime"]
        check("timeout/missing selector cleans up", timeout_result["state"] == "scenario_failed" and timeout_result["cleanup_state"] == "cleaned", timeout_result)
        cancel_result = cancel_live_test_runtime(runtime["live_test_runtime_id"])
        check("cancel completed safely", cancel_result["ok"] is True, cancel_result)
        restored = restore_live_test_record({"live_test_runtime_id": "restore-me", "state": "scenario_running", "browser": {"pid": 999999}})
        check("restore does not auto execute", restored["runtime"]["execution_resumed"] is False and restored["runtime"]["state"] == "manual_review_required", restored)

    status = get_live_testing_status()
    check("status local only", status["local_only"] is True and status["external_network_used"] is False, status)
    check("no raw javascript allowed", status["raw_javascript_allowed"] is False, status)
    for path in watched:
        if path.exists():
            check(f"watched source unchanged {path.name}", path.read_bytes() == before[str(path)], path)
    for path in live_paths:
        check(f"live artifact state unchanged {path.name}", path.exists() is live_state[str(path)], path)

    print(f"PASS luxcode live app interaction testing validator: {len(CHECKS)} checks")


if __name__ == "__main__":
    main()
