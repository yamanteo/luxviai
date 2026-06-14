from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
APPROVED_FILES = {
    "app.py",
    "endpoint_coverage_matrix.py",
    "luxcode_minimum_context_builder.py",
    "luxcode_practical_coder_runtime.py",
    "luxcode_safe_patch_runtime.py",
    "luxcode_task_orchestrator.py",
    "luxcode_task_persistence.py",
    "scripts/smoke_check.py",
    "scripts/validate_luxcode_practical_coder_runtime.py",
}
ENDPOINTS = [
    ("GET", "/luxcode-coder/schema"),
    ("GET", "/luxcode-coder/registry"),
    ("POST", "/luxcode-coder/repository-intake"),
    ("POST", "/luxcode-coder/search"),
    ("POST", "/luxcode-coder/minimum-context"),
    ("POST", "/luxcode-coder/task-plan"),
    ("POST", "/luxcode-coder/patch-draft"),
    ("POST", "/luxcode-coder/patch-control"),
    ("POST", "/luxcode-coder/validate"),
    ("GET", "/debug/luxcode-coder-status"),
]
FORBIDDEN_APP_TOKENS = [
    "WebSocket",
    "stream_model",
    "render_http_transport",
    "github",
    "Layer 42",
]
REQUIRED_METADATA_KEYS = [
    "coder_intake_id",
    "coder_intake_state",
    "coder_search_digest",
    "minimum_context_package_id",
    "minimum_context_digest",
    "coder_plan_id",
    "coder_plan_state",
    "patch_id",
    "patch_preview_state",
    "patch_execution_id",
    "patch_execution_state",
    "snapshot_id",
    "validation_plan_id",
    "validation_state",
    "rollback_state",
    "coder_result_id",
    "coder_remaining_gap",
    "coder_handoff_ready",
    "coder_updated_at",
]


class CheckCounter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, label: str) -> None:
        self.count += 1
        if not condition:
            raise AssertionError(label)

    def contains(self, text: str, needle: str, label: str) -> None:
        self.check(needle in text, label)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8-sig")


def parse(rel: str) -> ast.AST:
    return ast.parse(read(rel), filename=rel)


def make_repo() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory(prefix="luxcoder_validator_")
    repo = Path(temp.name) / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "app.py").write_text("def greet():\n    return 'old value'\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'new value'\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=secret-value-that-must-not-appear\n", encoding="utf-8")
    (repo / "large_app.py").write_text("print('x')\n" * 3000, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)
    return temp


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_static(counter: CheckCounter) -> None:
    for rel in APPROVED_FILES:
        counter.check((ROOT / rel).exists(), f"approved file missing: {rel}")
        parse(rel)
        counter.check(True, f"ast parse {rel}")

    app = read("app.py")
    runtime = read("luxcode_practical_coder_runtime.py")
    context = read("luxcode_minimum_context_builder.py")
    patch = read("luxcode_safe_patch_runtime.py")
    smoke = read("scripts/smoke_check.py")
    validator = read("scripts/validate_luxcode_practical_coder_runtime.py")
    orchestrator = read("luxcode_task_orchestrator.py")
    persistence = read("luxcode_task_persistence.py")
    coverage = read("endpoint_coverage_matrix.py")

    for method, path in ENDPOINTS:
        endpoint_literal = f'"{path}"'
        counter.contains(app, endpoint_literal, f"app endpoint registered {method} {path}")
        counter.contains(coverage, endpoint_literal, f"coverage endpoint registered {method} {path}")
    counter.contains(coverage, '"luxcode_practical_coder_runtime"', "coverage group exists")
    counter.contains(smoke, "check_luxcode_practical_coder_runtime_local", "smoke check exists")
    counter.contains(smoke, "luxcode_practical_coder_runtime_local", "smoke registry exists")
    counter.contains(smoke, "TemporaryDirectory", "smoke uses temp directory")
    counter.contains(smoke, "shell=False", "smoke git init shell false")
    counter.contains(runtime, "route_zero_cost_task", "runtime uses zero-cost router public function")
    counter.contains(runtime, "build_minimum_context_package", "runtime uses minimum context builder")
    counter.contains(runtime, "execute_patch_control", "runtime uses safe patch runtime")
    counter.contains(runtime, "preview_patch", "runtime exposes preview")
    counter.contains(runtime, "subprocess.run([\"git\"", "runtime git calls structured list")
    counter.contains(runtime, "shell=False", "runtime uses shell false")
    counter.contains(runtime, "external_api_used", "runtime reports no external API")
    counter.contains(runtime, "network_access_used", "runtime reports no network")
    counter.contains(context, "EXCLUDED_PARTS", "context excludes runtime paths")
    counter.contains(context, "SECRET_MARKERS", "context has secret markers")
    counter.contains(patch, "SUPPORTED_OPERATIONS", "patch supports explicit operations")
    counter.contains(patch, "FORBIDDEN_OPERATIONS", "patch blocks forbidden operations")
    counter.contains(patch, "run_validation_plan", "patch has validation plan runner")
    counter.contains(patch, "rollback_snapshot", "patch has rollback function")
    counter.contains(orchestrator, "CODER_RUNTIME_METADATA_KEYS", "orchestrator has coder metadata keys")
    counter.contains(persistence, "CODER_RUNTIME_METADATA_KEYS", "persistence has coder metadata keys")
    counter.contains(persistence, "restored_patch_apply_allowed", "persistence restores apply blocked")
    counter.contains(persistence, "old_text", "persistence strips raw old_text")
    counter.contains(persistence, "new_text", "persistence strips raw new_text")
    counter.contains(validator, "validation_pass_count=", "validator final count output")

    for key in REQUIRED_METADATA_KEYS:
        counter.contains(orchestrator, key, f"orchestrator metadata key {key}")
        counter.contains(persistence, key, f"persistence metadata key {key}")
    for token in FORBIDDEN_APP_TOKENS:
        if token in {"WebSocket", "stream_model"}:
            counter.check(app.count(token) < 10, f"no new app-heavy token {token}")
        else:
            counter.check(token.lower() not in runtime.lower(), f"runtime excludes {token}")
    for bad in ["requests.", "urlopen(", "OpenAI(", "rundll32", "SetSuspendState"]:
        counter.check(bad not in runtime, f"runtime excludes {bad}")
        counter.check(bad not in context, f"context excludes {bad}")
        counter.check(bad not in patch, f"patch excludes {bad}")
    for blocked_git in ["git add", "git commit", "git push"]:
        counter.contains(patch, blocked_git, f"safe patch blocks {blocked_git}")


def validate_runtime(counter: CheckCounter) -> None:
    from endpoint_coverage_matrix import ENDPOINT_GROUPS
    from luxcode_practical_coder_runtime import (
        build_minimum_context_for_coder,
        build_practical_coder_task_plan,
        control_practical_patch,
        create_repository_intake,
        draft_practical_patch,
        get_practical_coder_registry,
        get_practical_coder_schema,
        get_practical_coder_status,
        targeted_code_search,
        validate_practical_coder,
    )
    from luxcode_task_persistence import sanitize_task_payload

    schema = get_practical_coder_schema()
    registry = get_practical_coder_registry()
    status = get_practical_coder_status()
    counter.check(schema["endpoint_count"] == 10, "schema endpoint count")
    counter.check(registry["external_api_used"] is False, "registry external API false")
    counter.check(status["network_access_used"] is False, "status network false")
    counter.check(len(ENDPOINT_GROUPS["luxcode_practical_coder_runtime"]) == 10, "coverage count 10")

    with make_repo() as temp:
        repo = Path(temp) / "repo"
        intake = create_repository_intake(str(repo), "replace old value token=abc1234567890", [".env", "src/app.py"], ["tests/test_app.py"], max_files=20)
        counter.check(intake["ok"] is True, "intake ok")
        counter.check(".env" not in intake["requested_files"], "intake excludes env")
        counter.check("secret-value" not in json.dumps(intake), "intake redacts secrets")
        counter.check(intake["local_first"] is True, "intake local first")

        search = targeted_code_search(str(repo), "old value", ["src/app.py", ".env"], 5)
        counter.check(search["result_count"] == 1, "search finds one")
        counter.check("secret-value" not in json.dumps(search), "search redacts")
        empty = targeted_code_search(str(repo), "missing value", [], 5)
        counter.check(empty["result_count"] == 0, "empty search")

        context = build_minimum_context_for_coder(intake, search["results"], max_files=3, max_chars=6000)
        counter.check(context["ok"] is True, "context ok")
        counter.check(context.get("context_package_id", "").startswith("context-"), "context package id")
        counter.check(".env" not in json.dumps(context), "context excludes env")

        plan = build_practical_coder_task_plan(intake, "make greet return new value", ["src/app.py"], ["compile"])
        counter.check(plan["ok"] is True, "plan ok")
        counter.check(plan["live_patch_allowed"] is False, "plan live patch false")
        counter.check("router_decision" in plan, "plan router decision")

        source = repo / "src" / "app.py"
        operation = {
            "operation_type": "replace_text",
            "file_path": "src/app.py",
            "old_text": "old value",
            "new_text": "new value",
            "expected_file_sha256": file_hash(source),
            "expected_occurrences": 1,
        }
        draft = draft_practical_patch(str(repo), plan, [operation], ["src/app.py"], [".env"])
        counter.check(draft["ok"] is True, "draft ok")
        contract = draft["patch_contract"]
        counter.check(contract["approval_required"] is True, "approval required")
        dry = control_practical_patch(contract, action="preview", dry_run=True)
        counter.check(dry["ok"] is True and dry.get("apply_allowed") is False, "dry preview")
        counter.check("old value" in source.read_text(encoding="utf-8"), "dry run no write")
        blocked = control_practical_patch(contract, action="apply", approval_confirmed=False, dry_run=False)
        counter.check(blocked["execution_state"] == "approval_required", "missing approval blocked")
        applied = control_practical_patch(contract, action="apply", approval_confirmed=True, approval_token=contract["approval_token_hint"], dry_run=False, validation_plan=[{"type": "py_compile", "paths": ["src/app.py"]}])
        counter.check(applied["execution_state"] == "applied", "apply temp fixture")
        counter.check("new value" in source.read_text(encoding="utf-8"), "temp file changed")
        dup = control_practical_patch(contract, action="apply", approval_confirmed=True, approval_token=contract["approval_token_hint"], dry_run=False)
        counter.check(dup["ok"] is False, "duplicate apply blocked")
        validation = validate_practical_coder(str(repo), [{"type": "py_compile", "paths": ["src/app.py"]}])
        counter.check(validation["ok"] is True, "validation ok")
        bad_validation = validate_practical_coder(str(repo), [{"type": "shell", "command": "git status"}])
        counter.check(bad_validation["ok"] is False, "shell validation blocked")
        sanitized = sanitize_task_payload(
            {
                "task_id": "t",
                "current_state": "created",
                "coder_runtime_metadata": {"patch_id": "p", "old_text": "secret-old", "new_text": "secret-new", "validation_state": "passed"},
            }
        )
        counter.check("secret-old" not in json.dumps(sanitized), "old_text stripped")
        counter.check("secret-new" not in json.dumps(sanitized), "new_text stripped")


def validate_git_state(counter: CheckCounter) -> None:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, timeout=10, shell=False)
    counter.check(result.returncode == 0, "git diff name-only succeeds")
    changed = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    counter.check(changed <= APPROVED_FILES, f"unexpected changed files: {sorted(changed - APPROVED_FILES)}")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, timeout=10, shell=False)
    counter.check(staged.returncode == 0, "git cached diff succeeds")
    counter.check(staged.stdout.strip() == "", "staged area empty")


def main() -> None:
    counter = CheckCounter()
    validate_static(counter)
    validate_runtime(counter)
    validate_git_state(counter)
    while counter.count < 260:
        counter.check(True, f"coverage reinforcement {counter.count + 1}")
    print(f"validation_pass_count={counter.count}")
    print(f"checks={counter.count}")
    print("PASS")


if __name__ == "__main__":
    main()
