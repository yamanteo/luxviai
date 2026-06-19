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
    import luxcode_codewhale_task_bridge as bridge

    checks = 0
    with tempfile.TemporaryDirectory(prefix="lux_codewhale_validator_") as tmp:
        repo = Path(tmp) / "repo"
        (repo / "src").mkdir(parents=True)
        target = repo / "src" / "app.py"
        target.write_text("def greet():\n    return 1\n", encoding="utf-8")

        original_resolver = bridge.resolve_codewhale_executable
        bridge.resolve_codewhale_executable = lambda: "codewhale.cmd"

        doctor_payload = {
            "version": "0.8.57",
            "config_present": True,
            "workspace": str(repo),
            "api_key": {"source": "config"},
            "base_url": "https://api.deepseek.com/beta",
            "strict_tool_mode": {"enabled": False},
            "tls": {"certificate_verification": True},
            "sandbox": {"available": False},
            "api_connectivity": {"checked": False},
            "capability": {
                "resolved_provider": "deepseek",
                "resolved_model": "deepseek-v4-pro",
            },
        }

        model_contract = {
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
            commands.append(list(command))
            if "doctor" in command:
                return {
                    "ok": True,
                    "state": "completed",
                    "returncode": 0,
                    "stdout": json.dumps(doctor_payload),
                    "stderr": "",
                    "duration_ms": 1,
                    "process_started": True,
                }
            return {
                "ok": True,
                "state": "completed",
                "returncode": 0,
                "stdout": json.dumps({"message": json.dumps(model_contract)}),
                "stderr": "",
                "duration_ms": 2,
                "process_started": True,
            }

        readiness = bridge.inspect_codewhale_readiness(
            repository_root=str(repo),
            runner=runner,
        )
        _check(readiness["status"] == "READY_FOR_TASK_APPROVAL", "readiness", readiness)
        _check(readiness["auto_mode_allowed"] is False, "auto blocked")
        _check("sandbox_unavailable_auto_mode_forbidden" in readiness["warnings"], "sandbox warning")
        checks += 3

        approval = bridge.build_codewhale_task_approval(
            task_id="task-codewhale",
            repository_root=str(repo),
            target_files=["src/app.py"],
        )
        blocked = bridge.execute_codewhale_task_bridge(
            task_id="task-codewhale",
            repository_root=str(repo),
            task_summary="fix greet",
            target_files=["src/app.py"],
            minimum_context={"src/app.py": target.read_text(encoding="utf-8")},
            approval={},
            environ={},
            runner=runner,
        )
        _check(blocked["state"] == "blocked", "default closed", blocked)
        _check(blocked["external_api_used"] is False, "no call when blocked")
        checks += 2

        approved = dict(approval)
        approved.update({
            "approved": True,
            "consumed": False,
            "confirmation_text": bridge.EXACT_APPROVAL_TEXT,
        })
        environ = {
            "LUXCODE_CODEWHALE_ENABLED": "1",
            "LUXCODE_CODEWHALE_REAL_REQUESTS_ENABLED": "1",
            "LUXCODE_CODEWHALE_MANUAL_ONLY_CONFIRMED": "1",
            "LUXCODE_CODEWHALE_PAID_MODEL_ACKNOWLEDGED": "1",
        }
        result = bridge.execute_codewhale_task_bridge(
            task_id="task-codewhale",
            repository_root=str(repo),
            task_summary="fix greet",
            target_files=["src/app.py"],
            minimum_context={"src/app.py": target.read_text(encoding="utf-8")},
            approval=approved,
            environ=environ,
            runner=runner,
        )
        _check(result["ok"] is True, "fixture execution", result)
        _check(result["patch_steps"][0]["operation_type"] == "replace_text", "safe operation")
        _check(target.read_text(encoding="utf-8") == "def greet():\n    return 1\n", "no file write")
        exec_command = commands[-1]
        joined = " ".join(exec_command)
        _check(" exec " in f" {joined} ", "exec command", exec_command)
        _check("--json" in exec_command, "json output", exec_command)
        _check("--auto" not in exec_command, "no auto", exec_command)
        _check("--continue" not in exec_command, "no continue", exec_command)
        _check("--api-key" not in exec_command, "no key argument", exec_command)
        checks += 8

        bridge.resolve_codewhale_executable = original_resolver

    print(json.dumps({"status": "PASS", "checks": checks}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
