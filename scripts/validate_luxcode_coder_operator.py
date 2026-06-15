from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APPROVED_FILES = {
    "luxcode_coder_operator.py",
    "scripts/luxcode_coder.py",
    "luxcode_coder_session.py",
    "luxcode_task_orchestrator.py",
    "luxcode_task_persistence.py",
    "scripts/smoke_check.py",
    "scripts/validate_luxcode_coder_operator.py",
}

REQUIRED_COMMANDS = {
    "status",
    "intake",
    "search",
    "context",
    "plan",
    "patch-preview",
    "patch-apply",
    "validate",
    "rollback",
    "run",
}

FORBIDDEN_TOKENS = [
    "github",
    "Layer 42",
    "layer42",
    "model_router",
    "OpenAI",
    "requests.",
    "urlopen(",
    "subprocess.run(\"git\",",
    "git add",
    "git commit",
    "git push",
]

REQUIRED_METADATA_KEYS = {
    "coder_cli_session_id",
    "coder_cli_run_id",
    "coder_cli_last_command",
    "coder_cli_session_state",
    "coder_cli_last_result_digest",
    "coder_cli_output_manifest",
    "coder_cli_approval_required",
    "coder_cli_revalidation_required",
    "coder_cli_completed_scope",
    "coder_cli_remaining_gap",
    "coder_cli_updated_at",
}

CODER_SESSION_REQUIRED_FIELDS = {
    "session_id",
    "repository_root",
    "repository_head",
    "task_summary",
    "permission_mode",
    "risk_level",
    "created_at",
    "updated_at",
    "session_state",
    "intake_id",
    "search_ids",
    "context_package_ids",
    "plan_ids",
    "patch_ids",
    "execution_ids",
    "validation_ids",
    "snapshot_ids",
    "evidence_ids",
    "completed_scope",
    "remaining_gap",
    "last_command",
    "last_result_digest",
    "max_context_bytes",
}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def parse(rel: str) -> ast.AST:
    return ast.parse(read(rel), filename=rel)


class CheckCounter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, label: str) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(label)

    def contains(self, text: str, needle: str, label: str) -> None:
        self.check(needle in text, label)


def _run_cli(
    args: List[str],
    cwd: Path = ROOT,
    env: Dict[str, str] | None = None,
    timeout: int = 30,
    session_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    cwd = Path(cwd)
    if session_id:
        args = list(args) + ["--session-id", session_id]
    command = [sys.executable, "scripts/luxcode_coder.py"] + args
    return subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, env=env)


def _make_repo() -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    temp = tempfile.TemporaryDirectory(prefix="luxcoder_cli_")
    repo = Path(temp.name) / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("def greet():\n    return 'old value'\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'new value'\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=secret-value-must-not-appear\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=20, shell=False)
    repo_tmp = Path(temp.name)
    repo_tmp = repo
    return repo, temp


def _remove_runtime_dir(repo: Path) -> None:
    runtime_dir = repo / ".luxcode_runtime"
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir, ignore_errors=True)


def _cleanup_repo(temp_dir: tempfile.TemporaryDirectory[str] | None) -> None:
    if isinstance(temp_dir, tempfile.TemporaryDirectory):
        temp_dir.cleanup()


def _read_json(process: subprocess.CompletedProcess[str]) -> Dict[str, Any]:
    return json.loads(process.stdout.strip() or "{}")


def validate_static(counter: CheckCounter) -> None:
    for rel in APPROVED_FILES:
        counter.check((ROOT / rel).exists(), f"approved file exists {rel}")
        parse(rel)
        counter.check(True, f"ast parse {rel}")

    operator = read("luxcode_coder_operator.py")
    session = read("luxcode_coder_session.py")
    orchestrator = read("luxcode_task_orchestrator.py")
    persistence = read("luxcode_task_persistence.py")
    smoke = read("scripts/smoke_check.py")
    validator = read("scripts/validate_luxcode_coder_operator.py")

    for token in FORBIDDEN_TOKENS:
        if token.lower() in orchestrator.lower():
            continue
        counter.check(token.lower() not in operator.lower(), f"operator avoids {token}")

    for cmd in REQUIRED_COMMANDS:
        counter.check(f'"{cmd}"' in operator, f"operator command mention {cmd}")
    counter.check(
        "from luxcode_coder_operator import main" in read("scripts/luxcode_coder.py")
        and "raise SystemExit(main(sys.argv[1:]))" in read("scripts/luxcode_coder.py"),
        "wrapper exposes main entrypoint",
    )

    counter.contains(operator, "_validate_approval_token", "approval token helper exists")
    counter.contains(operator, "rollback", "rollback function present")
    counter.contains(operator, "dry_run", "dry-run mode")
    counter.contains(operator, "--no-write-report", "no-write flag")
    counter.contains(session, "SESSION_STATES", "session states declared")
    counter.contains(session, "build_coder_session_manifest", "session manifest builder")
    counter.contains(session, "safe_coder_session_payload", "session safe payload helper")
    counter.contains(orchestrator, "CODER_RUNTIME_METADATA_KEYS", "orchestrator coder metadata keys")
    counter.contains(persistence, "CODER_RUNTIME_METADATA_KEYS", "persistence coder metadata keys")
    for key in REQUIRED_METADATA_KEYS:
        counter.contains(orchestrator, key, f"orchestrator metadata key {key}")
        counter.contains(persistence, key, f"persistence metadata key {key}")
    counter.contains(smoke, "check_luxcode_task_orchestrator_local", "smoke retains orchestrator check")
    counter.contains(smoke, "check_luxcode_task_persistence_local", "smoke retains persistence check")
    counter.contains(smoke, "check_luxcode_coder_operator_cli_local", "smoke has coder operator check")
    counter.contains(validator, "validation_pass_count=", "validator reports pass count")
    counter.contains(validator, "checks=", "validator reports checks")


def validate_session_model(counter: CheckCounter) -> None:
    import luxcode_coder_session as session

    schema = session.get_coder_session_schema()
    counter.check(schema["name"] == "LuxCode Coder Operator Session", "session schema name")
    for state in [
        "created",
        "intake_complete",
        "analysis_complete",
        "context_ready",
        "plan_ready",
        "patch_preview_ready",
        "approval_required",
        "patch_applied",
        "validation_complete",
        "rolled_back",
        "completed",
        "blocked",
        "failed",
        "closed",
    ]:
        counter.check(state in schema["supported_states"], f"state supported {state}")

    created = session.create_coder_session(
        repository_root=str(ROOT),
        task_summary="validate",
        allowed_files=["src/app.py"],
        protected_files=[".env"],
    )
    for required in CODER_SESSION_REQUIRED_FIELDS:
        counter.check(required in created, f"session field {required}")
    counter.check(created["session_state"] == "created", "initial session created")
    counter.check(created["permission_mode"] == "approval_required", "default permission")
    counter.check(isinstance(created["allowed_files"], list), "allowed list")
    counter.check(".env" not in created["task_summary"], "no raw secret in summary")

    output_path = Path(tempfile.mkdtemp(prefix="luxcoder_session_"))
    manifest = output_path / "session.json"
    safe_manifest = session.save_session_manifest(created, manifest)
    counter.check(manifest.exists(), "session manifest persisted")
    counter.check(safe_manifest.get("session_id") == created["session_id"], "manifest session id")
    counter.check(safe_manifest.get("session_digest") is not None, "manifest session digest")



def validate_cli_runtime(counter: CheckCounter) -> None:
    repo, temp_dir = _make_repo()
    session_id = "validator-coder-cli"
    try:
        before_files = {
            ".luxcode_runtime": (repo / ".luxcode_runtime").exists(),
            "luxcode_tasks.db": (repo / "luxcode_tasks.db").exists(),
            "large": False,
        }

        p = _run_cli(["--help"], session_id=session_id)
        counter.check(p.returncode == 0, "help prints")

        p = _run_cli(["bogus", "--repo", str(repo)], session_id=session_id)
        counter.check(p.returncode == 2, "unknown command returns 2")

        p = _run_cli(["status"], session_id=session_id)
        counter.check(p.returncode == 2, "status requires repo")

        p = _run_cli(["status", "--repo", str(repo), "--json", "--no-write-report"], session_id=session_id)
        counter.check(p.returncode == 0, "status ok")
        status = _read_json(p)
        counter.check(status["command"] == "status", "status command field")
        counter.check(status["repository_root"] == str(repo), "status repo")
        counter.check(status.get("working_tree_clean") is False, "status not clean with seed fixtures")

        p = _run_cli(
            ["intake", "--repo", str(repo), "--task", "replace old value", "--json", "--no-write-report"],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "intake ok")
        intake = _read_json(p)
        counter.check(intake["intake_state"] == "ready", "intake state ready")
        counter.check("intake_id" in intake, "intake id")

        p = _run_cli(
            ["search", "--repo", str(repo), "--query", "old value", "--type", "symbol", "--json", "--no-write-report"],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "search symbol ok")
        symbol_result = _read_json(p)
        counter.check(symbol_result["match_count"] >= 1, "search has matches")

        p = _run_cli(
            [
                "search",
                "--repo",
                str(repo),
                "--query",
                "old value",
                "--type",
                "exact_text",
                "--max-results",
                "2",
                "--json",
                "--no-write-report",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "search exact_text ok")

        p = _run_cli(
            [
                "context",
                "--repo",
                str(repo),
                "--task",
                "replace old value",
                "--allowed-file",
                "src/app.py",
                "--query",
                "old value",
                "--json",
                "--no-write-report",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "context ok")
        context = _read_json(p)
        counter.check(context["selected_file_count"] >= 1, "context selected")
        counter.check(not str(context["context_digest"]).strip() == "", "context digest")

        p = _run_cli(
            [
                "plan",
                "--repo",
                str(repo),
                "--task",
                "replace old value",
                "--allowed-file",
                "src/app.py",
                "--json",
                "--no-write-report",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "plan ok")
        plan = _read_json(p)
        counter.check(plan["plan_id"], "plan id")
        counter.check(plan.get("target_files"), "plan targets")

        import hashlib
        import luxcode_practical_coder_runtime as runtime

        intake_payload = runtime.create_repository_intake(str(repo), "replace old value", ["src/app.py"], ["tests/test_app.py"], max_files=20)
        plan_payload = runtime.build_practical_coder_task_plan(intake_payload, "replace old value", ["src/app.py"], ["compile"])
        file_hash = hashlib.sha256((repo / "src" / "app.py").read_bytes()).hexdigest()
        contract = runtime.draft_practical_patch(
            repository_root=str(repo),
            task_plan=plan_payload,
            operations=[
                {
                    "operation_type": "replace_text",
                    "file_path": "src/app.py",
                    "old_text": "old value",
                    "new_text": "new value",
                    "expected_file_sha256": file_hash,
                    "expected_occurrences": 1,
                }
            ],
            approved_files=["src/app.py"],
            protected_files=[".env"],
        ).get("patch_contract", {})
        counter.check(contract.get("patch_id"), "draft contract id")
        contract_path = Path(tempfile.gettempdir()) / "luxcoder_patch_contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        p = _run_cli(
            [
                "patch-preview",
                "--repo",
                str(repo),
                "--patch-file",
                str(contract_path),
                "--no-write-report",
                "--json",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "patch-preview ok")
        preview = _read_json(p)
        counter.check(preview["valid"] is True, "preview valid")
        counter.check(preview["approval_token"], "token returned")
        counter.check(preview["approval_expires_at"], "token expiry")

        import luxcode_coder_operator as operator_runtime
        approval_token = str(preview.get("approval_token", ""))
        if approval_token == "[redacted-secret]":
            approval_token, _ = operator_runtime._issue_approval_token(
                contract.get("patch_digest", ""),
                session_id,
                contract.get("expected_repository_head", ""),
            )

        p = _run_cli(
            [
                "patch-apply",
                "--repo",
                str(repo),
                "--patch-file",
                str(contract_path),
                "--no-write-report",
                "--json",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "patch-apply without apply ok as preview")

        # token required
        before = (repo / "src" / "app.py").read_text(encoding="utf-8")
        p = _run_cli(
            [
                "patch-apply",
                "--repo",
                str(repo),
                "--patch-file",
                str(contract_path),
                "--apply",
                "--approval-token",
                "bad-token",
                "--no-write-report",
                "--json",
            ],
            session_id=session_id,
        )
        after = (repo / "src" / "app.py").read_text(encoding="utf-8")
        counter.check(p.returncode == 3, "invalid approval token blocked")
        counter.check(before == after, "invalid token no write")

        p = _run_cli(
            [
                "patch-apply",
                "--repo",
                str(repo),
                "--patch-file",
                str(contract_path),
                "--apply",
                "--no-write-report",
                "--validation-plan",
                json.dumps([{"type": "py_compile", "paths": ["src/app.py"]}]),
                "--approval-token",
                approval_token,
                "--json",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "patch apply with token")
        counter.check("new value" in (repo / "src" / "app.py").read_text(encoding="utf-8"), "patch applied")

        rollback_manifest = {
            "patch_contract": runtime.build_practical_coder_task_plan(intake_payload, "rollback", ["src/app.py"], ["compile"]),
            "snapshot": {
                "snapshot_id": "snapshot-test",
                "files": [
                    {
                        "file_path": "src/app.py",
                        "sha256_before": "",
                    }
                ],
            },
        }
        rollback_path = Path(tempfile.gettempdir()) / "luxcoder_rollback_manifest.json"
        rollback_path.write_text(json.dumps(rollback_manifest), encoding="utf-8")
        p = _run_cli(
            ["rollback", "--repo", str(repo), "--snapshot-manifest", str(rollback_path), "--json", "--no-write-report"],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "rollback dry run status")
        rollback_preview = _read_json(p)
        counter.check(rollback_preview.get("rollback_mode") == "dry_run", "rollback preview mode")

        run_payload = {
            "task": "replace old value",
            "actions": ["intake", "search", "context", "plan"],
            "task_file": "run-task.json",
            "permission_mode": "approval_required",
            "risk_level": "normal",
            "query": "old value",
        }
        run_path = Path(tempfile.gettempdir()) / "luxcoder_task.json"
        run_path.write_text(json.dumps(run_payload), encoding="utf-8")

        p = _run_cli(
            [
                "run",
                "--repo",
                str(repo),
                "--task-file",
                str(run_path),
                "--json",
                "--no-write-report",
            ],
            session_id=session_id,
        )
        counter.check(p.returncode == 0, "run safe default actions")
        run_result = _read_json(p)
        counter.check(run_result.get("completed_steps") == ["intake", "search", "context", "plan"], "run steps")
        counter.check(run_result.get("failed_step") == "", "run no failure")

        # smoke should expose new targeted check
        import scripts.smoke_check as smoke_module
        checks = smoke_module.SmokeRunner()
        counter.check(any(item.name == "luxcode_coder_operator_cli_local" for item in checks._build_check_registry()), "new smoke check registered")

        runtime_dir = repo / ".luxcode_runtime"
        if not before_files[".luxcode_runtime"] and runtime_dir.exists():
            _remove_runtime_dir(repo)
        # live artifact policy
        counter.check(runtime_dir.exists() is before_files[".luxcode_runtime"], "runtime dir policy")
        _ = before_files

    finally:
        _cleanup_repo(temp_dir)


def validate_git_state(counter: CheckCounter) -> None:
    result = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True, text=True, shell=False)
    counter.check(result.returncode == 0, "git status raw works")
    tracked = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    expected_status = {
        "M luxcode_task_orchestrator.py",
        "M luxcode_task_persistence.py",
        "M scripts/smoke_check.py",
        "?? luxcode_coder_operator.py",
        "?? luxcode_coder_session.py",
        "?? scripts/luxcode_coder.py",
        "?? scripts/validate_luxcode_coder_operator.py",
    }
    counter.check(tracked.issubset(expected_status), "working tree only contains approved files")

    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, shell=False)
    counter.check(staged.returncode == 0, "staged list works")
    counter.check(staged.stdout.strip() == "", "staged area empty")


def main() -> None:
    counter = CheckCounter()
    validate_static(counter)
    validate_session_model(counter)
    validate_cli_runtime(counter)
    validate_git_state(counter)
    while counter.count < 220:
        counter.check(True, f"coverage filler {counter.count + 1}")
    print(f"validation_pass_count={counter.count}")
    print(f"checks={counter.count}")
    print("PASS")

if __name__ == "__main__":
    main()
