from __future__ import annotations

import json
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
    from luxcode_working_copy_service import (
        get_working_copy_service_status,
        prepare_working_copy,
    )
    from luxcode_sandbox_service import (
        get_sandbox_service_status,
        prepare_sandbox,
    )
    from luxcode_integration_service import (
        execute_integration,
        get_integration_service_status,
        prepare_integration,
        rollback_integration,
    )

    checks = 0
    with tempfile.TemporaryDirectory(prefix="lux_workspace_services_") as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "src").mkdir()
        main_file = repo / "src" / "demo.py"
        main_file.write_text("VALUE = 1\n", encoding="utf-8")
        (repo / ".env").write_text("SECRET=do-not-copy\n", encoding="utf-8")

        check(
            get_working_copy_service_status()["service_ready"] is True,
            "working copy status",
        )
        check(
            get_sandbox_service_status()["service_ready"] is True,
            "sandbox status",
        )
        check(
            get_integration_service_status()["service_ready"] is True,
            "integration status",
        )
        checks += 3

        working = prepare_working_copy(
            repo,
            workspace_id="fixture-workspace",
            selected_files=["src/demo.py", ".env"],
        )
        check(working["ok"] is True, "working copy prepare", working)
        working_root = Path(working["working_copy_root"])
        check((working_root / "src" / "demo.py").is_file(), "file copied")
        check(not (working_root / ".env").exists(), "secret excluded")
        check(main_file.read_text(encoding="utf-8") == "VALUE = 1\n", "main unchanged")
        checks += 4

        sandbox = prepare_sandbox(
            repo,
            working_root,
            sandbox_id="fixture-sandbox",
        )
        check(sandbox["ok"] is True, "sandbox prepare", sandbox)
        sandbox_root = Path(sandbox["sandbox_root"])
        sandbox_file = sandbox_root / "src" / "demo.py"
        check(sandbox_file.is_file(), "sandbox file")
        check(main_file.read_text(encoding="utf-8") == "VALUE = 1\n", "main still unchanged")
        checks += 3

        sandbox_file.write_text("VALUE = 2\n", encoding="utf-8")
        plan = prepare_integration(
            repo,
            sandbox_root,
            patch_id="fixture-patch",
            approved_files=["src/demo.py"],
        )
        check(plan["ok"] is True, "integration prepare", plan)
        check(plan["approval_required"] is True, "approval required")
        check(main_file.read_text(encoding="utf-8") == "VALUE = 1\n", "prepare no write")
        checks += 3

        blocked = execute_integration(
            plan["patch_contract"],
            approval_confirmed=False,
            approval_token="",
        )
        check(blocked["status"] == "blocked", "apply blocked")
        check(main_file.read_text(encoding="utf-8") == "VALUE = 1\n", "blocked no write")
        checks += 2

        approval = plan["patch_contract"]["approval_digest"]
        applied = execute_integration(
            plan["patch_contract"],
            approval_confirmed=True,
            approval_token=approval,
        )
        check(applied["ok"] is True, "apply", applied)
        check(main_file.read_text(encoding="utf-8") == "VALUE = 2\n", "main changed")
        check(applied["rollback_available"] is True, "rollback available")
        checks += 3

        preview = rollback_integration(
            repository_root=repo,
            patch_id="fixture-patch",
            rollback_id=applied["rollback_id"],
            approval_token="",
            preview_only=True,
        )
        check(preview["ok"] is True, "rollback preview", preview)
        rollback_digest = preview["rollback_result"]["approval_digest"]
        rolled_back = rollback_integration(
            repository_root=repo,
            patch_id="fixture-patch",
            rollback_id=applied["rollback_id"],
            approval_token=rollback_digest,
            preview_only=False,
        )
        check(rolled_back["ok"] is True, "rollback execute", rolled_back)
        check(main_file.read_text(encoding="utf-8") == "VALUE = 1\n", "rollback restored")
        checks += 3

    print(json.dumps({"status": "PASS", "checks": checks}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
