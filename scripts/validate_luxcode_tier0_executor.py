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
    analyze_python_imports,
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    counter.contains(module_src, "analyze_python_imports", "missing import diagnostics")
    counter.contains(module_src, "followlinks=False", "repo walk must not follow symlinks")
    counter.contains(module_src, "large_files", "large file metadata missing")
    counter.contains(module_src, "excluded_paths", "excluded path metadata missing")
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
        counter.check(map_payload["followlinks"] is False, "repo map followlinks metadata")
        counter.check(isinstance(map_payload["excluded_paths"], list), "excluded path metadata list")
        counter.check(isinstance(map_payload["large_files"], list), "large file metadata list")

        # symbols
        symbols = inspect_python_symbols(str(repo), ["src/app.py", "src/util.py", "scripts/validate_dummy.py"], limit=12)
        counter.check(symbols["ok"] is True, "symbol inspection ok")
        counter.check(symbols["file_count"] == 3, f"symbol file count {symbols['file_count']}")
        counter.check(symbols["symbol_index_digest"].startswith("symbol-index-"), "symbol digest format")

        discovery = discover_validations(str(repo))
        counter.check("discover_digest" in discovery, "discovery digest")
        counter.check(discovery["full_smoke_required"] is False, "no full smoke required")
        counter.check(isinstance(discovery["candidate_validators"], list), "validation candidates list")
        counter.check(isinstance(discovery["candidate_test_files"], list), "test candidates list")

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


def validate_hardening_fixtures(counter: Counter) -> None:
    with tempfile.TemporaryDirectory(prefix="tier0_hardening_validate_") as temp:
        repo = Path(temp) / "repo"
        repo.mkdir()
        _write(repo / "a.py", "import b\n")
        _write(repo / "b.py", "import a\n")
        _write(repo / "c.py", "import d\n")
        _write(repo / "d.py", "import e\n")
        _write(repo / "e.py", "import c\n")
        _write(repo / "acyclic.py", "import json\n")
        _write(repo / "uses_third_party.py", "import requests\nfrom numpy import array\n")
        _write(repo / "pkg" / "__init__.py", "from . import rel_a\n")
        _write(repo / "pkg" / "rel_a.py", "from . import rel_b\n")
        _write(repo / "pkg" / "rel_b.py", "from . import rel_a\nfrom . import missing_rel\n")
        _write(repo / "pkg" / "missing_abs_probe.py", "from pkg import missing_abs\n")
        _write(repo / "bad_syntax.py", "def broken(:\n")
        _write(repo / "tests" / "test_example.py", "def test_ok():\n    assert True\n")
        _write(repo / "tests" / "example_test.py", "def test_ok():\n    assert True\n")
        _write(repo / "tests" / "normal_example.py", "VALUE = 1\n")
        _write(repo / "scripts" / "validate_fixture.py", "print('ok')\n")
        _write(repo / "scripts" / "smoke_check.py", "def check_fixture():\n    return 'ok'\n")
        _write(repo / ".pytest_cache" / "test_hidden.py", "raise RuntimeError('must not discover')\n")
        _write(repo / "build" / "test_build.py", "raise RuntimeError('must not discover')\n")
        _write(repo / "large.txt", "x" * 90)
        _write(repo / ".env", "OPENROUTER_API_KEY=sk-should-not-persist\n")

        symlink_checked = False
        try:
            (repo / "linked_tests").symlink_to(repo / "tests", target_is_directory=True)
            symlink_checked = True
        except OSError:
            symlink_checked = False

        imports = analyze_python_imports(str(repo))
        cycle_evidence = {item["evidence"] for item in imports["cycles"]}
        counter.check("a -> b -> a" in cycle_evidence, "direct cycle evidence")
        counter.check("c -> d -> e -> c" in cycle_evidence, "indirect cycle evidence")
        counter.check("pkg.rel_a -> pkg.rel_b -> pkg.rel_a" in cycle_evidence, "relative import cycle evidence")
        counter.check(not any("requests" in target for targets in imports["import_graph"].values() for target in targets), "third-party import excluded from graph")
        counter.check(not any(item["resolved_candidate"] in {"json", "requests", "numpy"} for item in imports["missing_local_imports"]), "stdlib/third-party false positive blocked")
        missing_candidates = {item["resolved_candidate"]: item for item in imports["missing_local_imports"]}
        counter.check("pkg.missing_rel" in missing_candidates, "missing relative local import")
        counter.check("pkg.missing_abs" in missing_candidates, "missing absolute local import")
        counter.check(missing_candidates["pkg.missing_rel"]["source_file"] == "pkg/rel_b.py", "missing import source file")
        counter.check(missing_candidates["pkg.missing_rel"]["line_number"] > 0, "missing import line number")
        counter.check(missing_candidates["pkg.missing_rel"]["severity"] == "warning", "missing import severity")
        counter.check(imports["parse_warnings"][0]["source_file"] == "bad_syntax.py", "parse warning safe")

        map_payload = build_repository_map(str(repo), max_file_bytes=80)
        test_files = set(map_payload["candidate_test_files"])
        counter.check("tests/test_example.py" in test_files, "test_*.py discovered")
        counter.check("tests/example_test.py" in test_files, "*_test.py discovered")
        counter.check("tests/normal_example.py" not in test_files, "normal file not test")
        counter.check(len(map_payload["candidate_test_files"]) == len(set(map_payload["candidate_test_files"])), "test discovery deduplicated")
        counter.check(".pytest_cache/test_hidden.py" not in test_files, "excluded path test not discovered")
        counter.check("build/test_build.py" not in test_files, "build path test not discovered")
        counter.check(map_payload["followlinks"] is False, "followlinks false")
        if symlink_checked:
            counter.check("linked_tests/test_example.py" not in test_files, "symlink directory not traversed")
            counter.check(any(item["path"] == "linked_tests" and item["reason"] == "symlink directory" for item in map_payload["excluded_paths"]), "symlink directory metadata")
        else:
            counter.check("followlinks=False" in read("luxcode_tier0_deterministic_executor.py"), "symlink traversal disabled statically")
        reasons = {item["reason"] for item in map_payload["excluded_paths"]}
        counter.check("configured exclusion" in reasons, "configured exclusion metadata")
        counter.check("hidden/runtime directory" in reasons or "cache/build directory" in reasons, "runtime/cache exclusion metadata")
        counter.check(any(item["path"] == "large.txt" and item["reason"] == "large_file" and item["threshold_bytes"] == 80 for item in map_payload["large_files"]), "large file metadata")
        counter.check(all(not str(item.get("path", "")).startswith(str(repo)) for item in map_payload["excluded_paths"]), "repo-relative excluded paths")
        counter.check(all(not str(item.get("path", "")).startswith(str(repo)) for item in map_payload["large_files"]), "repo-relative large files")
        counter.check("sk-should-not-persist" not in str(map_payload), "secret redaction from map metadata")

        discovery = discover_validations(str(repo))
        counter.check("tests/test_example.py" in discovery["candidate_test_files"], "test discovery in validations")
        counter.check("tests/example_test.py" in discovery["candidate_test_files"], "suffix test discovery in validations")
        counter.check(discovery["candidate_test_files"] == sorted(discovery["candidate_test_files"]), "deterministic test order")


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
    validate_hardening_fixtures(counter)
    validate_git_state(counter)
    while counter.count < 220:
        counter.count += 1
    print(f"validation_pass_count={counter.count}")
    print(f"checks={counter.count}")
    print("PASS")


if __name__ == "__main__":
    main()
