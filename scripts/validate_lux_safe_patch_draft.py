from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lux_safe_patch_draft_engine import (  # noqa: E402
    build_safe_patch_draft,
    get_safe_patch_draft_schema,
    get_safe_patch_draft_status,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_fixture() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "app.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/demo')\ndef demo():\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (root / "sample_module.py").write_text("def run():\n    return {'ok': True}\n", encoding="utf-8")
    (root / "endpoint_coverage_matrix.py").write_text("ENDPOINT_GROUPS = {}\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "smoke_check.py").write_text("def check_demo():\n    return 'ok'\n", encoding="utf-8")
    (root / "static").mkdir()
    (root / "static" / "demo.js").write_text("console.log('demo')\n", encoding="utf-8")
    (root / "config.yaml").write_text("enabled: true\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / ".env").write_text("SECRET=do-not-read\n", encoding="utf-8")
    return temp


def _assert_safety(payload: dict) -> None:
    _assert(payload.get("approval_required") is True, "approval_required must be true")
    _assert(payload.get("can_apply_now") is False, "can_apply_now must be false")
    _assert(payload.get("destructive_action_blocked") is True, "destructive_action_blocked must be true")
    _assert(payload.get("file_write_blocked") is True, "file_write_blocked must be true")
    _assert(payload.get("real_execution_blocked") is True, "real_execution_blocked must be true")
    _assert(payload.get("read_only") is True, "read_only must be true")
    _assert(payload.get("external_api_used") is False, "external_api_used must be false")
    _assert(payload.get("local_first") is True, "local_first must be true")


def _base_request(root: Path) -> dict:
    return {
        "issue_summary": "Demo endpoint schema is missing coverage and targeted smoke validation",
        "root_cause_hypotheses": [
            {
                "title": "Endpoint registration drift",
                "related_files": ["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
                "evidence": ["schema route exists without coverage entry", "smoke check missing targeted endpoint assertion"],
            }
        ],
        "selected_context": [
            {"relative_path": "app.py", "line_start": 5, "line_end": 7, "reasons": ["route location"]},
            {"relative_path": "endpoint_coverage_matrix.py", "reasons": ["coverage surface"]},
            {"relative_path": "scripts/smoke_check.py", "reasons": ["smoke surface"]},
        ],
        "requested_files": ["app.py"],
        "forbidden_files": ["static/index.html", ".env"],
        "repository_root": str(root),
        "change_intent": "Add exact endpoint, coverage, and targeted smoke draft only",
        "mode": "full_patch_preview",
        "max_patch_files": 5,
        "max_hunks_per_file": 2,
    }


def main() -> int:
    fixture = _make_fixture()
    try:
        root = Path(fixture.name)
        checks = 0

        schema = get_safe_patch_draft_schema()
        status = get_safe_patch_draft_status()
        _assert_safety(schema)
        _assert_safety(status)
        _assert("full_patch_preview" in schema["supported_modes"], "schema must expose full_patch_preview")
        _assert(status["target_file_write_enabled"] is False, "target file writes must be disabled")
        checks += 4

        single = build_safe_patch_draft(**_base_request(root))
        _assert_safety(single)
        _assert(single["request_id"].startswith("luxpatch-"), "request_id prefix mismatch")
        _assert(single["patch_targets"], "valid single-file/multi-evidence plan should select targets")
        targets = {item["target_file"] for item in single["patch_targets"]}
        _assert({"app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"} <= targets, "expected targets missing")
        _assert(".env" not in targets, ".env must never be targeted")
        _assert(single["forbidden_files_respected"] is True, "forbidden files must be respected")
        checks += 6

        steps = single["patch_steps"]
        _assert(steps, "patch steps must be populated")
        first = steps[0]
        for field in [
            "target_file",
            "target_region",
            "purpose",
            "proposed_change",
            "change_type",
            "evidence",
            "risk",
            "dependencies",
            "approval_required",
            "validation_after_change",
            "rollback_hint",
        ]:
            _assert(field in first, f"patch step missing {field}")
        _assert(first["change_type"] == "selective_edit", "draft must prefer selective edits")
        _assert(first["approval_required"] is True, "step approval must be required")
        _assert(first["rollback_hint"], "rollback hint must be present")
        checks += 4

        _assert("# DRAFT ONLY" in single["unified_diff_draft"], "unified diff must be marked draft")
        _assert("--- a/app.py" in single["unified_diff_draft"], "unified diff should include app.py")
        _assert("DRAFT ONLY" in single["unified_diff_draft"], "draft marker missing from diff")
        checks += 3

        blocked_budget = build_safe_patch_draft(
            issue_summary="budget test",
            requested_files=["app.py", "endpoint_coverage_matrix.py", "scripts/smoke_check.py"],
            repository_root=str(root),
            max_patch_files=1,
        )
        _assert(any("exceeds max_patch_files" in item["reason"] for item in blocked_budget["blocked_items"]), "oversized patch budget must be rejected")
        checks += 1

        forbidden = build_safe_patch_draft(
            issue_summary="forbidden test",
            requested_files=["app.py", ".env"],
            forbidden_files=["app.py"],
            repository_root=str(root),
        )
        _assert("app.py" not in {item["target_file"] for item in forbidden["patch_targets"]}, "forbidden file must be excluded")
        _assert(any(".env" in item["target_file"] or ".env" in item["reason"] for item in forbidden["blocked_items"]), ".env exclusion must be reported")
        checks += 2

        traversal = build_safe_patch_draft(issue_summary="traversal", requested_files=["../outside.py"], repository_root=str(root))
        _assert(any("traversal rejected" in item["reason"] for item in traversal["blocked_items"]), "path traversal must be rejected")
        outside = build_safe_patch_draft(issue_summary="outside", requested_files=[str(root.parent / "outside.py")], repository_root=str(root))
        _assert(any("outside repository" in item["reason"] for item in outside["blocked_items"]), "outside-root path must be rejected")
        binary = build_safe_patch_draft(issue_summary="binary", requested_files=["image.png"], repository_root=str(root))
        _assert(any("binary" in item["reason"] or "unsupported" in item["reason"] for item in binary["blocked_items"]), "binary file must be blocked")
        checks += 3

        destructive = build_safe_patch_draft(issue_summary="delete file and drop table", requested_files=["app.py"], repository_root=str(root))
        _assert(any(step["risk"] == "blocked" for step in destructive["patch_steps"]), "deletion/destructive request must be blocked")
        high = build_safe_patch_draft(issue_summary="configuration toggle change", requested_files=["config.yaml"], repository_root=str(root))
        _assert(any(step["risk"] == "high_risk" for step in high["patch_steps"]), "sensitive/config change should be high risk")
        checks += 2

        plan_text = "\n".join(single["verification_plan"])
        _assert("python -m py_compile app.py" in plan_text, "Python verification recommendation missing")
        _assert("endpoint presence check" in single["verification_plan"], "endpoint verification recommendation missing")
        _assert(any("smoke_check.py --check" in item for item in single["verification_plan"]), "smoke verification recommendation missing")
        _assert("python scripts/smoke_check.py --quick" in single["verification_plan"], "quick smoke recommendation missing")
        checks += 4

        _assert(single["recommended_handoff"] in {"local", "codex", "gemini_cline", "whale", "human"}, "invalid handoff target")
        _assert(single["safe_next_step"], "safe next step must be present")
        _assert(single["rollback_plan"], "rollback plan must be present")
        checks += 3

        fallback = build_safe_patch_draft(issue_summary="", requested_files=[], repository_root=str(root), mode="invalid")
        _assert_safety(fallback)
        _assert(fallback["mode"] == "full_patch_preview", "invalid mode should fall back")
        _assert(any("issue_summary is empty" in item["reason"] for item in fallback["blocked_items"]), "insufficient input fallback missing")
        checks += 3

        repeat = build_safe_patch_draft(**_base_request(root))
        _assert(repeat["request_id"] == single["request_id"], "request_id must be deterministic")
        _assert(repeat["patch_steps"] == single["patch_steps"], "patch steps must be deterministic")
        checks += 2

        verification_only = build_safe_patch_draft(
            issue_summary="verification only",
            requested_files=["sample_module.py"],
            repository_root=str(root),
            mode="verification_only",
        )
        _assert(verification_only["unified_diff_draft"] == "", "verification_only mode should not emit diff")
        checks += 1

        print(f"PASS lux safe patch draft validator: {checks} checks")
        return 0
    finally:
        fixture.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
