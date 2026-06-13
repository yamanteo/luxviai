from __future__ import annotations

import socket
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_autonomy_permission_controller import create_permission_profile  # noqa: E402
from luxcode_terminal_process_runtime import (  # noqa: E402
    cancel_terminal_runtime,
    check_port,
    detect_stale_processes,
    execute_terminal_action,
    get_safe_runtime_metadata,
    get_terminal_process,
    get_terminal_runtime_registry,
    get_terminal_runtime_schema,
    get_terminal_runtime_status,
    health_check,
    plan_terminal_action,
    restore_runtime_record,
    stop_terminal_process,
)
from luxcode_task_orchestrator import (  # noqa: E402
    cancel_luxcode_task_terminal_runtime,
    create_luxcode_task,
    execute_luxcode_task_terminal_action,
    get_luxcode_task_status,
    plan_luxcode_task_terminal_action,
)
from luxcode_task_persistence import initialize_task_store, load_task_state, save_task_state  # noqa: E402


CHECKS: list[str] = []


def check(name: str, condition: bool, detail: object = None) -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail!r}")
    CHECKS.append(name)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def make_fixture(root: Path) -> Path:
    repo = root / "fixture"
    repo.mkdir()
    (repo / "scripts").mkdir()
    (repo / "tests").mkdir()
    (repo / "scripts" / "server.py").write_text(
        "\n".join(
            [
                "from http.server import BaseHTTPRequestHandler, HTTPServer",
                "import sys",
                "class H(BaseHTTPRequestHandler):",
                "    def log_message(self, *args): pass",
                "    def do_GET(self):",
                "        self.send_response(200)",
                "        self.end_headers()",
                "        self.wfile.write(b'ok')",
                "port = int(sys.argv[1])",
                "print('TOKEN=abc123456789SECRET', flush=True)",
                "HTTPServer(('127.0.0.1', port), H).serve_forever()",
            ]
        ),
        encoding="utf-8",
    )
    (repo / "scripts" / "timeout.py").write_text(
        "import time\nprint('api_key=abc123456789SECRET', flush=True)\ntime.sleep(10)\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_ok.py").write_text("print('ok')\n", encoding="utf-8")
    return repo


def validate() -> None:
    live_paths = [
        ROOT / ".luxcode_runtime",
        ROOT / "luxcode_tasks.db",
        ROOT / ".luxcode_snapshots",
        ROOT / "luxcode_backups",
    ]
    live_files = [
        ROOT / "luxcode_terminal_process_runtime.py",
        ROOT / "luxcode_task_orchestrator.py",
        ROOT / "luxcode_task_persistence.py",
        ROOT / "app.py",
        ROOT / "endpoint_coverage_matrix.py",
        ROOT / "scripts" / "validate_luxcode_terminal_process_runtime.py",
        ROOT / "scripts" / "smoke_check.py",
    ]
    before = {str(path): path.read_bytes() for path in live_files if path.exists()}
    service_runtime_id = ""
    timeout_runtime_id = ""

    with tempfile.TemporaryDirectory() as tmp:
        repo = make_fixture(Path(tmp))
        port = free_port()
        profile_result = create_permission_profile(
            task_id="terminal-fixture",
            permission_mode="controlled_access",
            repository_root=str(repo),
            command_text="test et validator calistir servis baslat",
            scope_items=[{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
        )
        profile = profile_result["profile"]

        schema = get_terminal_runtime_schema()
        check("structured action model exists", {"run_script", "run_validator", "run_test", "run_build", "install_dependency", "start_service", "stop_service", "check_process", "check_port", "health_check"} <= set(schema["action_types"]))
        check("raw shell endpoint absent", schema["raw_shell_endpoint"] is False)
        registry = get_terminal_runtime_registry(str(repo))
        check("executable registry includes python", "python" in registry["executable_registry"], registry)

        raw = plan_terminal_action("run_script", str(repo), ".", "python", [], raw_command="python -c print(1)")
        check("raw shell command rejected", raw["ok"] is False, raw)
        blocked_exe = plan_terminal_action("run_script", str(repo), ".", "cmd", ["/c", "echo hi"])
        check("allowlist outside executable rejected", blocked_exe["ok"] is False, blocked_exe)
        traversal = plan_terminal_action("run_script", str(repo), "../", "python", [])
        check("path traversal rejected", traversal["ok"] is False, traversal)
        outside = plan_terminal_action("run_script", str(repo), str(Path(tmp)), "python", [])
        check("scope outside cwd rejected", outside["ok"] is False, outside)
        chained = plan_terminal_action("run_script", str(repo), ".", "python", ["-c", "print(1) && echo bad"])
        check("command chaining rejected", chained["ok"] is False, chained)
        env_secret = plan_terminal_action("run_script", str(repo), ".", "python", ["tests/test_ok.py"], environment={"API_TOKEN": "secret"})
        check("secret env injection rejected", env_secret["ok"] is False, env_secret)

        plan_result = plan_terminal_action(
            "start_service",
            str(repo),
            ".",
            "python",
            ["scripts/server.py", str(port)],
            timeout_seconds=20,
            process_mode="background",
            permission_profile=profile,
            metadata={"task_id": "terminal-fixture"},
        )
        check("start_service plan success", plan_result["ok"] and plan_result["plan"]["shell"] is False, plan_result)
        plan = plan_result["plan"]
        check("permission decision produced", "permission_decision" in plan and plan["permission_decision"]["allowed"] is True, plan)
        check("risk classification produced", plan["risk_classification"] == "important", plan)
        check("environment policy bounded", plan["environment_policy"]["dotenv_read"] is False, plan)
        check("cleanup policy owned process only", plan["cleanup_policy"]["owned_process_only"] is True, plan)

        executed = execute_terminal_action(plan)
        check("service starts shell false", executed["ok"] and executed["runtime"]["status"] == "running", executed)
        runtime = executed["runtime"]
        service_runtime_id = runtime["runtime_id"]
        check("pid ownership recorded", isinstance(runtime["pid"], int) and runtime["ownership"]["owned_by_runtime"], runtime)
        check("audit start events recorded", any(event["event_type"] == "process_running" for event in runtime["audit_events"]), runtime)

        ready = health_check("tcp", "127.0.0.1", port, retries=20, retry_interval=0.1)
        check("readiness tcp succeeds", ready["healthy"] is True, ready)
        port_result = check_port("127.0.0.1", port, expected_runtime_id=service_runtime_id)
        check("port listening detected", port_result["listening"] is True, port_result)
        check("runtime owns expected port", port_result["expected_runtime_owns_port"] is True, port_result)
        http = health_check("http_get", "127.0.0.1", port, path="/", retries=5, retry_interval=0.1)
        check("localhost http health succeeds", http["healthy"] is True, http)
        external = health_check("http_get", "example.com", 80)
        check("external http target blocked", external["ok"] is False, external)
        status = get_terminal_process(service_runtime_id)
        check("process lookup works", status["ok"] and status["runtime"]["runtime_id"] == service_runtime_id, status)

        stopped = stop_terminal_process(service_runtime_id)
        check("service stop succeeds", stopped["ok"] and stopped["runtime"]["status"] == "stopped", stopped)
        after_stop = check_port("127.0.0.1", port)
        check("port released after stop", after_stop["available"] is True, after_stop)
        safe_meta = get_safe_runtime_metadata(stopped["runtime"])
        check("output redacted", "abc123456789SECRET" not in str(safe_meta), safe_meta)
        check("bounded stdout summary", len(safe_meta["stdout_summary"]) <= 6000, safe_meta)

        timeout_plan = plan_terminal_action("run_script", str(repo), ".", "python", ["scripts/timeout.py"], timeout_seconds=1, permission_profile=profile)
        timeout_result = execute_terminal_action(timeout_plan["plan"])
        timeout_runtime_id = timeout_result["runtime"]["runtime_id"]
        check("timeout cleanup status", timeout_result["runtime"]["status"] in {"timed_out", "stopped"}, timeout_result)
        check("timeout redacts stderr stdout", "abc123456789SECRET" not in str(timeout_result["runtime"]), timeout_result)
        check("timeout process removed from live tracking", get_terminal_process(timeout_runtime_id)["runtime"]["status"] in {"timed_out", "stopped"}, timeout_result)

        cancel_plan = plan_terminal_action("start_service", str(repo), ".", "python", ["scripts/server.py", str(free_port())], timeout_seconds=20, process_mode="background", permission_profile=profile, metadata={"task_id": "cancel-task"})
        cancel_exec = execute_terminal_action(cancel_plan["plan"])
        cancel_result = cancel_terminal_runtime(task_id="cancel-task")
        check("cancel cleans owned process", cancel_result["cancelled"] >= 1, cancel_result)
        check("stale preview safe", detect_stale_processes()["automatic_kill"] is False)

        collision_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        collision_socket.bind(("127.0.0.1", 0))
        collision_socket.listen(1)
        collision_port = int(collision_socket.getsockname()[1])
        collision = check_port("127.0.0.1", collision_port)
        collision_socket.close()
        check("port collision does not kill other process", collision["listening"] is True and collision["available"] is False, collision)

        restored = restore_runtime_record({"runtime_id": "restore-1", "status": "running", "pid": 999999})
        check("restore does not auto start process", restored["runtime"]["execution_resumed"] is False, restored)
        check("restore marks manual review", restored["runtime"]["status"] == "manual_review_required", restored)

        store = Path(tmp) / "store"
        initialize_task_store("local_sqlite", str(store))
        save = save_task_state({"task_id": "runtime-task", "current_state": "created", "process_metadata": safe_meta}, mode="local_sqlite", storage_root=str(store))
        loaded = load_task_state("runtime-task", mode="local_sqlite", storage_root=str(store))
        check("persistence stores safe process metadata", save["ok"] and loaded["task"]["process_metadata"]["runtime_id"] == safe_meta["runtime_id"], loaded)

        task = create_luxcode_task(
            original_request="test et",
            repository_root=str(repo),
            suspected_files=["scripts/server.py"],
            permission_mode="controlled_access",
            scope_items=[{"path": ".", "type": "folder", "recursive": True, "rights": ["read", "write"]}],
        )
        planned_task = plan_luxcode_task_terminal_action(task["task_id"], "run_test", ".", "python", ["tests/test_ok.py"], timeout_seconds=5)
        check("orchestrator terminal planning works", planned_task["terminal_runtime_plan"]["action_type"] == "run_test", planned_task)
        executed_task = execute_luxcode_task_terminal_action(task["task_id"])
        check("orchestrator terminal execution works", executed_task["terminal_runtime_result"]["status"] == "completed", executed_task)
        cancel_task = cancel_luxcode_task_terminal_runtime(task["task_id"])
        check("orchestrator terminal cancel hook works", cancel_task["terminal_runtime_result"]["ok"] is True, cancel_task)

        check("status endpoint data valid", get_terminal_runtime_status()["status"] == "ready")
        check("no network access flag", get_terminal_runtime_status()["network_access_used"] is False)
        check("shell false invariant", get_terminal_runtime_status()["shell_used"] is False)
        check("no live commit push deploy", get_terminal_runtime_status()["live_commit_push_deploy_used"] is False)
        check("no live source mutation", all(path.read_bytes() == before[str(path)] for path in live_files if path.exists()))

    check("temporary fixture removed", not Path(tmp).exists())
    check("no live artifacts created", not any(path.exists() for path in live_paths))
    check("validator minimum coverage", len(CHECKS) >= 45)
    if service_runtime_id:
        check("service runtime no longer running", get_terminal_process(service_runtime_id)["runtime"]["status"] in {"stopped", "timed_out"})


if __name__ == "__main__":
    try:
        validate()
    finally:
        detect_stale_processes()
    print(f"PASS luxcode terminal process runtime validator: {len(CHECKS)} checks")
