from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lux_debug_intelligence_core import (  # noqa: E402
    analyze_lux_debug_request,
    get_lux_debug_schema,
    get_lux_debug_status,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_fixture() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "app.py").write_text(
        "from sample_module import run\n\n@app.get('/demo')\ndef demo():\n    return run()\n",
        encoding="utf-8",
    )
    (root / "sample_module.py").write_text(
        "def run():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (root / "endpoint_coverage_matrix.py").write_text("ENDPOINT_GROUPS = {}\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "smoke_check.py").write_text("def check_demo():\n    return 'ok'\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=do-not-read\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "ignored.py").write_text("x = 1\n", encoding="utf-8")
    return temp


def _assert_safety_flags(payload: dict) -> None:
    _assert(payload.get("read_only") is True, "read_only must be true")
    _assert(payload.get("real_execution_blocked") is True, "real_execution_blocked must be true")
    _assert(payload.get("file_write_blocked") is True, "file_write_blocked must be true")
    _assert(payload.get("external_api_used") is False, "external_api_used must be false")
    _assert(payload.get("local_first") is True, "local_first must be true")


def main() -> int:
    fixture = _make_fixture()
    try:
        root = Path(fixture.name)
        schema = get_lux_debug_schema()
        status = get_lux_debug_status()
        _assert_safety_flags(schema)
        _assert_safety_flags(status)
        _assert("full_debug_preview" in schema["supported_modes"], "schema must expose full_debug_preview")
        _assert("issue_text" in schema["input_fields"], "schema must expose issue_text")
        _assert(status["patch_application_enabled"] is False, "patch application must be disabled")
        _assert(status["terminal_execution_enabled"] is False, "terminal execution must be disabled")
        _assert(status["github_action_enabled"] is False, "github action must be disabled")
        _assert(status["deployment_enabled"] is False, "deployment must be disabled")
        _assert(status["env_file_access_enabled"] is False, ".env access must be disabled")

        traceback_text = f'File "{root / "app.py"}", line 4, in demo\nRuntimeError: broken'
        result = analyze_lux_debug_request(
            issue_text="Bu hatayı bul endpoint schema app.py smoke_check",
            traceback_text=traceback_text,
            suspected_files=["app.py", ".env", "../outside.py"],
            changed_files=["endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
            repository_root=str(root),
            max_files=6,
            mode="full_debug_preview",
        )
        _assert_safety_flags(result)
        _assert(result["request_id"].startswith("luxdebug-"), "request_id prefix mismatch")
        _assert(result["mode"] == "full_debug_preview", "mode should be preserved")
        _assert(result["repository_root"] == str(root.resolve()), "repository root mismatch")
        _assert(result["normalized_issue"], "normalized issue should be populated")
        _assert(1 <= len(result["selected_context"]) <= 6, "selected context should respect max_files")
        selected = {item["relative_path"] for item in result["selected_context"]}
        _assert("app.py" in selected, "app.py should be selected from suspected/traceback")
        _assert("endpoint_coverage_matrix.py" in selected, "coverage file should be selected")
        _assert("scripts/smoke_check.py" in selected, "smoke file should be selected")
        _assert(".env" not in selected, ".env must not be selected")
        _assert("__pycache__/ignored.py" not in selected, "cache file must not be selected")
        _assert(any("traversal rejected" in item for item in result["missing_information"]), "traversal rejection should be reported")
        _assert(any(".env" in item for item in result["missing_information"]), ".env rejection should be reported")

        context_item = next(item for item in result["selected_context"] if item["relative_path"] == "app.py")
        _assert(context_item["read_only"] is True, "context item must be read-only")
        _assert(context_item["excerpt"], "context excerpt should be present")
        _assert(context_item["reasons"], "context reasons should be present")
        _assert(context_item["matched_signals"], "context signals should be present")
        _assert(context_item["traceback_line_excerpt"], "traceback line excerpt should be present")

        _assert(result["root_cause_hypotheses"], "root causes should be populated")
        cause = result["root_cause_hypotheses"][0]
        for field in ["title", "explanation", "evidence", "related_files", "confidence", "validation_needed", "likely_scope", "is_confirmed"]:
            _assert(field in cause, f"root cause missing {field}")
        _assert(cause["is_confirmed"] is False, "hypothesis must not claim confirmation")

        adjacent_titles = {issue["title"] for issue in result["adjacent_issues"]}
        for title in [
            "missing endpoint coverage",
            "missing smoke",
            "import mismatch",
            "request/schema mismatch",
            "stale status info",
            "duplicated routing logic",
            "inconsistent safety flags",
            "missing fallback",
            "missing validation",
            "unrelated modified files",
            "likely regression risks",
        ]:
            _assert(title in adjacent_titles, f"adjacent issue missing: {title}")
        _assert(all(issue["classification"] in {"directly_related", "likely_related", "optional_improvement", "out_of_scope"} for issue in result["adjacent_issues"]), "invalid adjacent classification")

        _assert(result["patch_plan"], "patch plan should be populated")
        patch = result["patch_plan"][0]
        for field in ["target_file", "purpose", "proposed_change", "risk", "dependencies", "approval_required", "validation_after_change"]:
            _assert(field in patch, f"patch plan missing {field}")
        _assert(patch["approval_required"] is True, "patch plan must require approval")
        _assert("static/index.html" in patch["must_not_touch"], "must-not-touch should include static/index.html")

        checks = {item["check"] for item in result["verification_plan"]}
        for check in [
            "py_compile",
            "targeted smoke",
            "segmented smoke",
            "quick smoke",
            "import test",
            "endpoint presence check",
            "schema check",
            "fallback test",
            "git diff --check",
            "manual UI test",
            "full smoke",
        ]:
            _assert(check in checks, f"verification plan missing {check}")
        _assert(result["recommended_handoff"] in {"local", "gemini_cline", "whale", "codex", "human"}, "invalid handoff")
        _assert(result["safe_next_step"], "safe next step should be present")
        _assert(0 <= result["confidence"] <= 1, "confidence must be normalized")

        fallback = analyze_lux_debug_request(
            issue_text="",
            repository_root=str(root),
            suspected_files=["missing.py"],
            max_files=2,
            mode="not-real-mode",
        )
        _assert_safety_flags(fallback)
        _assert(fallback["mode"] == "full_debug_preview", "unknown mode should fall back safely")
        _assert(len(fallback["selected_context"]) <= 2, "fallback should respect max_files")
        _assert(fallback["patch_plan"][0]["approval_required"] is True, "fallback patch plan should require approval")
        _assert(any("issue_text is empty" in item for item in fallback["missing_information"]), "empty issue should be reported")

        repeated = analyze_lux_debug_request(
            issue_text="Bu hatayı bul endpoint schema app.py smoke_check",
            traceback_text=traceback_text,
            suspected_files=["app.py", ".env", "../outside.py"],
            changed_files=["endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
            repository_root=str(root),
            max_files=6,
            mode="full_debug_preview",
        )
        _assert(repeated["request_id"] == result["request_id"], "request_id should be deterministic")
        print("PASS lux debug intelligence validator: 35 checks")
        return 0
    finally:
        fixture.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
