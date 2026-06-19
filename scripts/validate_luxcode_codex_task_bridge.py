from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(condition: bool, label: str, payload=None) -> None:
    if not condition:
        raise AssertionError(f"{label}: {payload!r}")


def main() -> int:
    import luxcode_codex_task_bridge as bridge

    checks = 0
    with tempfile.TemporaryDirectory(prefix="lux_codex_validator_") as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        target = repo / "src" / "app.py"
        target.write_text(
            "def greet():\n    return 1\n",
            encoding="utf-8",
        )

        original_resolver = bridge.resolve_codex_executable
        bridge.resolve_codex_executable = lambda: "codex.cmd"

        response_payload = {
            "analysis_summary": "fixture safe patch",
            "patch_operations": [
                {
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "old_text": "def greet():\n    return 1\n",
                    "new_text": "def greet():\n    return 2\n",
                    "expected_occurrences": 1,
                    "reason": "fixture",
                }
            ],
            "validation_recommendations": ["py_compile"],
            "remaining_gap": "",
            "failure_reason": "",
        }

        commands = []

        def runner(command, *, cwd, timeout_seconds):
            command = list(command)
            commands.append(command)
            if "--version" in command:
                return {
                    "ok": True,
                    "state": "completed",
                    "returncode": 0,
                    "stdout": "codex-cli 0.140.0\n",
                    "stderr": "",
                    "duration_ms": 1,
                    "process_started": True,
                }
            if "login" in command and "status" in command:
                return {
                    "ok": True,
                    "state": "completed",
                    "returncode": 0,
                    "stdout": "Logged in using ChatGPT\n",
                    "stderr": "",
                    "duration_ms": 1,
                    "process_started": True,
                }
            output_index = command.index("-o") + 1
            Path(command[output_index]).write_text(
                json.dumps(response_payload),
                encoding="utf-8",
            )
            return {
                "ok": True,
                "state": "completed",
                "returncode": 0,
                "stdout": '{"type":"turn.completed"}\n',
                "stderr": "",
                "duration_ms": 2,
                "process_started": True,
            }

        readiness = bridge.inspect_codex_readiness(
            repository_root=str(repo),
            runner=runner,
        )
        _check(
            readiness["status"] == "READY_FOR_TASK_APPROVAL",
            "readiness",
            readiness,
        )
        _check(readiness["sandbox_mode"] == "read-only", "read only")
        _check(readiness["approval_policy"] == "never", "never approval")
        checks += 3

        approval = bridge.build_codex_task_approval(
            task_id="task-codex",
            repository_root=str(repo),
            target_files=["src/app.py"],
        )

        blocked = bridge.execute_codex_task_bridge(
            task_id="task-codex",
            repository_root=str(repo),
            task_summary="fix greet",
            target_files=["src/app.py"],
            minimum_context={
                "src/app.py": target.read_text(encoding="utf-8")
            },
            approval={},
            environ={},
            runner=runner,
        )
        _check(blocked["state"] == "blocked", "default closed", blocked)
        _check(blocked["external_api_used"] is False, "no call blocked")
        checks += 2

        approved = dict(approval)
        approved.update(
            {
                "approved": True,
                "consumed": False,
                "confirmation_text": bridge.EXACT_APPROVAL_TEXT,
            }
        )
        environ = {
            "LUXCODE_CODEX_ENABLED": "1",
            "LUXCODE_CODEX_REAL_REQUESTS_ENABLED": "1",
            "LUXCODE_CODEX_MANUAL_ONLY_CONFIRMED": "1",
            "LUXCODE_CODEX_EMERGENCY_ONLY_CONFIRMED": "1",
            "LUXCODE_CODEX_CREDIT_USAGE_ACKNOWLEDGED": "1",
        }

        result = bridge.execute_codex_task_bridge(
            task_id="task-codex",
            repository_root=str(repo),
            task_summary="fix greet",
            target_files=["src/app.py"],
            minimum_context={
                "src/app.py": target.read_text(encoding="utf-8")
            },
            approval=approved,
            environ=environ,
            runner=runner,
        )
        _check(result["ok"] is True, "fixture execution", result)
        _check(
            result["patch_steps"][0]["operation_type"] == "replace_text",
            "safe operation",
        )
        _check(
            target.read_text(encoding="utf-8")
            == "def greet():\n    return 1\n",
            "no file write",
        )

        exec_command = commands[-1]
        joined = " ".join(exec_command)
        _check("exec" in exec_command, "exec command", exec_command)
        _check("-s" in exec_command, "sandbox flag", exec_command)
        _check(
            exec_command[exec_command.index("-s") + 1] == "read-only",
            "read-only sandbox",
            exec_command,
        )
        _check("-a" in exec_command, "approval flag", exec_command)
        _check(
            exec_command[exec_command.index("-a") + 1] == "never",
            "approval never",
            exec_command,
        )
        _check("--json" in exec_command, "json events", exec_command)
        _check("--output-schema" in exec_command, "output schema", exec_command)
        _check("-o" in exec_command, "last message output", exec_command)
        _check(
            "--dangerously-bypass-approvals-and-sandbox"
            not in exec_command,
            "no dangerous bypass",
            exec_command,
        )
        _check("workspace-write" not in joined, "no workspace write")
        _check("danger-full-access" not in joined, "no full access")
        _check("--skip-git-repo-check" not in exec_command, "git check kept")
        _check("-m" not in exec_command and "--model" not in exec_command,
               "no model override")
        checks += 15

        bridge.resolve_codex_executable = original_resolver

    print(json.dumps({"status": "PASS", "checks": checks}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
