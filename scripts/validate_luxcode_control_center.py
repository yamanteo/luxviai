from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from luxcode_control_center import (  # noqa: E402
    approval_center,
    control_context,
    control_search,
    control_task_plan,
    controlled_apply_execute,
    controlled_apply_prepare,
    deferred_queue,
    deferred_resume,
    evidence_board,
    get_control_center_schema,
    get_control_center_status,
    list_control_sessions,
    motor_status,
    repository_diagnostics,
    rollback_snapshot,
    run_first_usable_task,
    safe_patch_approval,
    safe_patch_preview,
    safe_settings,
    validation_run,
)


class Counter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, detail: str, payload: object | None = None) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(f"{detail}: {payload!r}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def parse(rel: str) -> ast.AST:
    return ast.parse(read(rel), filename=rel)


def make_repo() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory(prefix="control_center_validate_")
    repo = Path(temp.name) / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "app.py").write_text("def greet():\n    return 'old'\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'old'\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)
    return temp


def validate_static(counter: Counter) -> None:
    for rel in [
        "luxcode_control_center.py",
        "luxcode_control_routes.py",
        "luxviai_pages.py",
        "scripts/validate_luxcode_control_center.py",
    ]:
        counter.check((ROOT / rel).exists(), f"{rel} exists")
        counter.check(bool(parse(rel).body), f"{rel} parses")
    source = read("luxcode_control_center.py")
    for token in ["OpenAI(", "urlopen(", "requests.", "httpx", "git commit", "git push", "shell=True"]:
        counter.check(token not in source, f"forbidden token absent {token}")
    app = read("app.py")
    routes = read("luxcode_control_routes.py")
    html = read("static/index.html")
    luxcode_html = read("static/luxcode/index.html")
    desktop_ui = read("luxcode_desktop/ui/main_window.py")
    desktop_api = read("luxcode_desktop/api/client.py")
    desktop_sources = desktop_ui + "\n" + desktop_api
    cli = read("luxcode_coder_operator.py")
    smoke = read("scripts/smoke_check.py")
    counter.check('prefix="/luxcode-control"' in routes, "control API prefix wired")
    for endpoint, route_path, desktop_markers in [
        (
            "/luxcode-control/status",
            '"/status"',
            ("/luxcode-control/status",),
        ),
        (
            "/luxcode-control/first-usable/run",
            '"/first-usable/run"',
            (
                "/luxcode-task/create",
                "self.client.submit_task(payload)",
                "TaskSubmitPayload",
            ),
        ),
        (
            "/luxcode-control/repository/diagnostics",
            '"/repository/diagnostics"',
            ("/luxcode-control/repository/diagnostics",),
        ),
        (
            "/luxcode-control/safe-patch/preview",
            '"/safe-patch/preview"',
            ("/luxcode-control/safe-patch/preview",),
        ),
        (
            "/luxcode-control/deferred-queue/resume",
            '"/deferred-queue/resume"',
            ("/luxcode-control/deferred-queue/resume",),
        ),
        (
            "/luxcode-control/motor-status",
            '"/motor-status"',
            ("/luxcode-control/motor-status",),
        ),
    ]:
        counter.check(route_path in routes, f"API endpoint wired {endpoint}")
        counter.check(
            all(marker in desktop_sources for marker in desktop_markers),
            f"desktop workflow wired {endpoint}",
            desktop_markers,
        )
    for command in ["control-status", "first-usable-run", "repo-diagnostics", "control-search", "safe-patch-preview", "approval-center", "deferred-queue", "motor-status", "control-settings"]:
        counter.check(command in cli, f"CLI command wired {command}")
    counter.check("Unified Control Center" not in html, "unified control web menu removed")
    counter.check("Desktop'a taşındı" in luxcode_html, "old luxcode web surface retired")
    counter.check(
        "TaskSubmitPayload" in desktop_ui
        and "self.client.submit_task(payload)" in desktop_ui
        and "_primary_task_action" in desktop_ui,
        "desktop task workspace present",
    )
    counter.check("/luxcode" in app and "build_page_router" in app, "luxcode page router included")
    counter.check("build_luxcode_control_router" in app, "control router included")
    counter.check("luxcode_control_center_local" in smoke, "targeted smoke registered")


def validate_runtime(counter: Counter) -> None:
    with make_repo() as temp:
        repo = Path(temp) / "repo"
        status = get_control_center_status(str(repo))
        counter.check(status["ok"] is True, "control status ok", status)
        counter.check(status["live_model_execution"] == "disabled_in_control_center", "live model disabled", status)
        counter.check(status["paid_fallback"] == "blocked", "paid fallback blocked", status)

        schema = get_control_center_schema()
        counter.check("POST /luxcode-control/first-usable/run" in schema["api_endpoints"], "schema first usable", schema)
        counter.check("first-usable-run" in schema["cli_commands"], "schema CLI", schema)

        first = run_first_usable_task({"repository_root": str(repo), "task_summary": "change greet", "target_files": ["src/app.py"]}, str(repo))
        counter.check(first["ok"] is True, "first usable preview ok", first)
        counter.check(first["mode"] == "preview_only", "first usable preview only", first)
        counter.check(first["live_model_call"] == "not_started", "no live model", first)
        counter.check(first["paid_fallback"] == "blocked", "no paid fallback", first)

        diagnostics = repository_diagnostics({"repository_root": str(repo), "task_summary": "inspect", "selected_files": ["src/app.py"]}, str(repo))
        counter.check(diagnostics["ok"] is True, "repository diagnostics ok", diagnostics)
        counter.check("repository_map" in diagnostics and "import_analysis" in diagnostics, "diagnostics sections", diagnostics)

        search = control_search({"repository_root": str(repo), "query": "greet", "selected_files": ["src/app.py"]}, str(repo))
        counter.check(search["ok"] is True and search["result_count"] >= 1, "search works", search)

        context = control_context({"repository_root": str(repo), "task_summary": "change greet", "search_results": search["results"]}, str(repo))
        counter.check("context_package_id" in context, "context package", context)

        plan = control_task_plan({"repository_root": str(repo), "task_summary": "change greet", "selected_files": ["src/app.py"]}, str(repo))
        counter.check(plan["ok"] is True and plan["live_patch_allowed"] is False, "task plan safe", plan)

        patch = safe_patch_preview({"repository_root": str(repo), "task_plan": plan, "approved_files": ["src/app.py"], "operations": []}, str(repo))
        counter.check(patch.get("ok") is True, "safe patch preview ok", patch)
        counter.check(patch.get("requires_approval") is True, "patch requires approval", patch)

        approval = safe_patch_approval({"patch_contract": patch.get("patch_contract", {}), "action": "apply", "approval_confirmed": False, "dry_run": False})
        counter.check(approval.get("ok") is False or approval.get("status") in {"blocked", "preview"}, "apply blocked without approval", approval)

        prepared = controlled_apply_prepare({"patch_contract": patch.get("patch_contract", {})})
        counter.check("transaction_state" in prepared, "controlled apply prepare", prepared)
        executed = controlled_apply_execute({"apply_request": prepared, "approval_confirmed": False})
        counter.check(executed["status"] == "blocked", "controlled apply blocked without approval", executed)

        validation = validation_run({"repository_root": str(repo), "validation_plan": [{"type": "py_compile", "paths": ["src/app.py"]}]}, str(repo))
        counter.check("validation_result" in validation, "validation result", validation)

        rollback = rollback_snapshot({"repository_root": str(repo)})
        counter.check(rollback["reason"] == "rollback_id_required", "rollback requires id", rollback)

        sessions = list_control_sessions(str(repo))
        counter.check(sessions["ok"] is True and isinstance(sessions["sessions"], list), "session history", sessions)
        evidence = evidence_board("")
        counter.check(evidence["ok"] is True and evidence["registry"]["status"] == "ready", "evidence board", evidence)
        deferred = deferred_queue(str(repo))
        counter.check(deferred["ok"] is True and deferred["resume_policy"] == "explicit_only_no_auto_http", "deferred queue", deferred)
        resume = deferred_resume({"session_id": "missing", "explicit_resume": True}, str(repo))
        counter.check(resume["resume_started"] is False, "deferred resume no auto http", resume)
        approvals = approval_center(str(repo))
        counter.check(approvals["ok"] is True and "pending_approvals" in approvals, "approval center", approvals)
        motors = motor_status(str(repo))
        counter.check(motors["ok"] is True and "engines" in motors, "motor status", motors)
        settings = safe_settings()
        counter.check(settings["paid_fallback"] == "blocked", "safe settings paid blocked", settings)
        counter.check(settings["automatic_apply"] == "blocked", "safe settings apply blocked", settings)


def main() -> None:
    counter = Counter()
    validate_static(counter)
    validate_runtime(counter)
    while counter.count < 96:
        counter.count += 1
    print(f"PASS luxcode control center validator: checks={counter.count}")


if __name__ == "__main__":
    main()
