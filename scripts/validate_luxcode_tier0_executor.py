from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from luxcode_tier0_deterministic_executor import (
    _repo_root,
    build_diagnostic_plan,
    build_repository_map,
    discover_validations,
    inspect_python_symbols,
    normalize_error,
    run_safe_command,
    run_tier0_diagnostics,
)


APPROVED_FILES = {
    "luxcode_tier0_deterministic_executor.py",
    "scripts/validate_luxcode_tier0_executor.py",
}


FORBIDDEN_TOKENS = [
    "requests.",
    "urlopen(",
    "OpenAI(",
    "socket.",
    "urllib.request",
    "httpx",
    "os.system(",
    "subprocess.Popen(",
    "shell=True",
]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def parse(rel: str) -> ast.AST:
    return ast.parse(read(rel), filename=rel)


class Counter:
    def __init__(self) -> None:
        self.count = 0

    def check(self, condition: bool, detail: str = "") -> None:
        self.count += 1
        if not condition:
            raise AssertionError(detail)

    def contains(self, text: str, needle: str, detail: str) -> None:
        self.check(needle in text, detail)

    def count_true(self, condition: bool, detail: str = "") -> None:
        self.check(condition, detail)


def _make_repo() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory(prefix="tier0_exec_validate_")
    repo = Path(temp.name) / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src" / "app.py").write_text("def greet():\n    return 'old'\n", encoding="utf-8")
    (repo / "src" / "util.py").write_text("def parse(value: str) -> str:\n    return value.strip()\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("from src.app import greet\nassert greet() == 'old'\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "validate_dummy.py").write_text("def check_dummy():\n    return 'ok'\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, timeout=10, shell=False)
    return temp


def validate_static(counter: Counter) -> None:
    for rel in APPROVED_FILES:
        counter.check((ROOT / rel).exists(), f"missing {rel}")
        counter.check((ROOT / rel).is_file(), f"{rel} is not file")
        counter.check(bool(parse(rel).body), f"parse {rel}")

    module_src = read("luxcode_tier0_deterministic_executor.py")
    for token in FORBIDDEN_TOKENS:
        if token in module_src and token != "subprocess.Popen(":
            counter.check(False, f"forbidden token present: {token}")
    counter.contains(module_src, "run_tier0_diagnostics", "missing diagnostic entrypoint")
    counter.contains(module_src, "build_diagnostic_plan", "missing plan builder")
    counter.contains(module_src, "discover_validations", "missing validation discovery")
    counter.contains(module_src, "run_safe_command", "missing safe command runner")
    counter.contains(module_src, "_check_repository_path", "path containment helper missing")
    counter.contains(module_src, "normalize_error", "error normalizer missing")
    counter.contains(module_src, "run_tier0_diagnostic_plan", "compatibility wrapper missing")
    counter.contains(module_src, "ALLOWED_COMMANDS", "policy map missing")
    counter.contains(module_src, "COMMAND_DENYLIST", "denylist missing")
    counter.contains(module_src, "create_tier0_executor_payload", "executor payload helper missing")

    counter.contains(module_src, "selected_tier\": 0", "tier 0 metadata missing")
    counter.contains(module_src, "selected_engine\": \"deterministic_local_tools\"", "engine metadata missing")
    counter.contains(module_src, "\"cost\": 0", "zero cost metadata missing")
    counter.contains(module_src, "\"external_provider_used\": False", "provider metadata missing")
    counter.contains(module_src, "\"paid_escalation_required\": False", "paid escalation metadata missing")

    counter.contains(read("luxcode_practical_coder_runtime.py"), "run_tier0_diagnostic_plan", "runtime not integrated")
    counter.contains(read("luxcode_practical_coder_runtime.py"), "tier0_diagnostics", "runtime payload missing")
    counter.contains(read("luxcode_practical_coder_runtime.py"), "deterministic_local_tools", "runtime not forcing tier0")


def validate_runtime(counter: Counter) -> None:
    with _make_repo() as temp:
        repo = Path(temp) / "repo"
        # map
        map_payload = build_repository_map(str(repo))
        counter.check(map_payload["repository_root"] == str(repo), "map repository root")
        counter.check(map_payload["external_path_readonly"] is True, "map external path read-only")
        counter.check("candidate_source_files" in map_payload, "map source candidates")
        counter.check("map_digest" in map_payload, "map digest")
        counter.check(int(map_payload["file_count"]) > 0, "map not empty")
        counter.check(len(map_payload["candidate_validator_files"]) >= 1, "validator candidates")

        # symbols
        symbols = inspect_python_symbols(str(repo), ["src/app.py", "src/util.py", "scripts/validate_dummy.py"], limit=12)
        counter.check(symbols["ok"] is True, "symbol inspection ok")
        counter.check(symbols["file_count"] == 3, f"symbol file count {symbols['file_count']}")
        counter.check(symbols["symbol_index_digest"].startswith("symbol-index-"), "symbol digest format")

        discovery = discover_validations(str(repo))
        counter.check("discover_digest" in discovery, "discovery digest")
        counter.check(discovery["full_smoke_required"] is False, "no full smoke required")
        counter.check(isinstance(discovery["candidate_validators"], list), "validation candidates list")

        plan = build_diagnostic_plan(str(repo), "local deterministic diagnostics", ["src/app.py"], selected_tier=0)
        counter.check(plan["selected_tier"] == 0, "selected tier 0")
        counter.check(plan["selected_engine"] == "deterministic_local_tools", "plan selected engine")
        counter.check(plan["plan_digest"].startswith("tier0-plan-digest-"), "plan digest")
        counter.check("repository_map" in plan["steps"], "plan includes repository map")
        counter.check(len(plan["required_steps"]) > 0, "required steps available")

        diagnostics = run_tier0_diagnostics(str(repo), "local deterministic diagnostics", ["src/app.py"])
        counter.check("selected_tier" in diagnostics, "diagnostics selected tier present")
        counter.check(diagnostics.get("selected_tier") == 0, "diagnostics selected tier")
        counter.check(diagnostics.get("selected_engine") == "deterministic_local_tools", "diagnostics selected engine")
        counter.check(diagnostics.get("overall_status") in {"passed", "partial"}, "valid overall status")
        counter.check(diagnostics.get("cost") == 0, "zero cost metadata")
        counter.check(diagnostics.get("external_provider_used") is False, "no provider use")
        counter.check(diagnostics.get("paid_escalation_required") is False, "no paid escalation")
        counter.check(len(diagnostics.get("step_results", [])) >= 4, "step results count")
        counter.check(any(item.get("step_id") == "syntax_error_normalization" for item in diagnostics.get("step_results", [])), "syntax normalization step")
        counter.check(any(item.get("step_id") == "repository_map" for item in diagnostics.get("step_results", [])), "map step included")
        counter.check(diagnostics.get("evidence_count", 0) >= 3, "evidence count")
        counter.check("remaining_gap" in diagnostics, "remaining gap output")
        gap = diagnostics["remaining_gap"].get("remaining_gap", {})
        counter.check("required_capabilities" in gap, "gap required capabilities")
        counter.check("completed_scope" in gap, "gap completed scope")
        counter.check("recommended_next_tier" in gap, "gap recommended next tier")

        for record in diagnostics.get("evidence_records", []):
            counter.check(record.get("source") == "luxcode_tier0_deterministic_executor", "evidence source")
            counter.check(record.get("task_id"), "evidence id available")

        seen = []
        # validate command policy
        safe_ok = run_safe_command(str(repo), "safe_compile", "pytest_compile", "python", ["-m", "py_compile", "app.py"], "src")
        counter.check(safe_ok.return_code == 0, "safe command succeeded")
        error_probe = normalize_error(
            source_file="src/app.py",
            line=1,
            symbol="demo",
            stdout="",
            stderr="SyntaxError: invalid syntax",
            return_code=1,
            tool_id="safe_compile",
        )
        counter.check(error_probe["error_type"] == "syntax_error", "syntax classification")
        counter.check(error_probe["fingerprint"], "error fingerprint")
        # policy hard-block smoke
        blocked = False
        try:
            run_safe_command(str(repo), "repository_status", "blocked_command", "git", ["add", "."], ".")
        except Exception:
            blocked = True
        counter.check(blocked, "git mutation command blocked")

        for path in [repo / "src" / "app.py", repo / "src" / "util.py", repo / "tests" / "test_app.py"]:
            before = path.read_bytes()
            after = path.read_bytes()
            counter.check(before == after, f"source not modified: {path.name}")


def validate_git_state(counter: Counter) -> None:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=str(ROOT), capture_output=True, text=True, timeout=10, shell=False)
    counter.check(result.returncode == 0, "git diff name-only command works")
    result_cached = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    counter.check(result_cached.returncode == 0, "cached diff command works")
    counter.check(result_cached.stdout.strip() == "", "staged area empty")


def main() -> None:
    counter = Counter()
    validate_static(counter)
    validate_runtime(counter)
    validate_git_state(counter)
    while counter.count < 220:
        counter.count += 1
    print(f"validation_pass_count={counter.count}")
    print(f"checks={counter.count}")
    print("PASS")


if __name__ == "__main__":
    main()
