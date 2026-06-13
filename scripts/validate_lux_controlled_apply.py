from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lux_controlled_apply_engine import (  # noqa: E402
    execute_controlled_apply,
    get_controlled_apply_schema,
    get_controlled_apply_status,
    prepare_controlled_apply,
    rollback_controlled_apply,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_repo() -> tempfile.TemporaryDirectory[str]:
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "app.py").write_text("alpha = 1\nanchor()\nomega = 3\n", encoding="utf-8")
    (root / "other.py").write_text("before\nanchor\nend\n", encoding="utf-8")
    (root / "dupe.py").write_text("same\nsame\n", encoding="utf-8")
    (root / "config.yaml").write_text("enabled: true\n", encoding="utf-8")
    (root / "secret.key").write_text("secret\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "unknown.xyz").write_text("unknown\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=do-not-read\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "venv").mkdir()
    (root / "venv" / "x.py").write_text("x=1\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.py").write_text("x=1\n", encoding="utf-8")
    return temp


def _replace_step(target: str = "app.py", original: str = "alpha = 1\n", replacement: str = "alpha = 2\n") -> dict:
    return {
        "target_file": target,
        "change_type": "replace_exact",
        "expected_original_text": original,
        "replacement_text": replacement,
        "target_region": "line 1",
        "purpose": "fixture exact replacement",
        "validation_after_change": ["py_compile"],
    }


def _base(root: Path, **overrides) -> dict:
    data = {
        "repository_root": str(root),
        "patch_id": "patch-demo",
        "patch_steps": [_replace_step()],
        "approved_files": ["app.py"],
        "forbidden_files": [".env"],
        "expected_file_hashes": {"app.py": _sha(root / "app.py")},
        "max_files": 5,
        "max_total_changed_lines": 20,
        "require_clean_tree": False,
        "validation_plan": ["python -m py_compile app.py"],
    }
    data.update(overrides)
    return data


def _assert_core_flags(payload: dict) -> None:
    _assert(payload["approval_required"] is True, "approval_required invariant")
    _assert(payload["validation_execution_blocked"] is True, "validation execution must be blocked")
    _assert(payload["scope_expansion_blocked"] is True, "scope expansion must be blocked")
    _assert(payload["destructive_action_blocked"] is True, "destructive action must be blocked")
    _assert(payload["external_api_used"] is False, "external_api_used must be false")
    _assert(payload["local_first"] is True, "local_first must be true")


def _prepare_and_apply(root: Path, **overrides) -> dict:
    data = _base(root, **overrides)
    prepared = prepare_controlled_apply(**data, mode="prepare")
    _assert(not prepared["blocked_items"], f"prepare blocked: {prepared}")
    applied = execute_controlled_apply(**data, mode="apply", approval_token=prepared["approval_digest"])
    _assert(applied["transaction_state"] == "applied", f"apply failed: {applied}")
    return applied


def main() -> int:
    checks = 0
    live_runtime = REPO_ROOT / ".luxcode_runtime"
    live_before = live_runtime.exists()

    schema = get_controlled_apply_schema()
    status = get_controlled_apply_status()
    _assert(schema["default_mode"] == "dry_run", "default mode must be dry_run")
    _assert(status["shell_execution_enabled"] is False, "shell execution disabled")
    _assert_core_flags(schema)
    _assert_core_flags(status)
    checks += 4

    fixture = _make_repo()
    try:
        root = Path(fixture.name)
        original = (root / "app.py").read_text(encoding="utf-8")

        dry = execute_controlled_apply(**_base(root))
        _assert(dry["mode"] == "dry_run", "omitted mode should dry-run")
        _assert(dry["transaction_state"] == "dry_run", "dry-run state expected")
        _assert((root / "app.py").read_text(encoding="utf-8") == original, "dry-run must not write")
        _assert_core_flags(dry)
        checks += 4

        prepared = prepare_controlled_apply(**_base(root), mode="prepare")
        _assert(prepared["approval_digest"].startswith("lux-approve-"), "prepare digest missing")
        missing = execute_controlled_apply(**_base(root), mode="apply")
        wrong = execute_controlled_apply(**_base(root), mode="apply", approval_token="wrong")
        _assert(missing["transaction_state"] == "blocked" and missing["blocked_items"], "missing approval blocked")
        _assert(wrong["transaction_state"] == "blocked" and wrong["blocked_items"], "wrong approval blocked")
        altered_patch = _base(root, patch_steps=[_replace_step(replacement="alpha = 9\n")])
        _assert(execute_controlled_apply(**altered_patch, mode="apply", approval_token=prepared["approval_digest"])["transaction_state"] == "blocked", "altered patch blocked")
        altered_files = _base(root, approved_files=["app.py", "other.py"])
        _assert(execute_controlled_apply(**altered_files, mode="apply", approval_token=prepared["approval_digest"])["transaction_state"] == "blocked", "altered approved files blocked")
        altered_hash = _base(root, expected_file_hashes={"app.py": "0" * 64})
        _assert(execute_controlled_apply(**altered_hash, mode="apply", approval_token=prepared["approval_digest"])["transaction_state"] == "blocked", "altered expected hash blocked")
        checks += 6

        applied = _prepare_and_apply(root)
        _assert((root / "app.py").read_text(encoding="utf-8").startswith("alpha = 2"), "exact replacement applied")
        _assert(applied["approval_valid"] is True and applied["preconditions_passed"] is True, "apply invariants")
        _assert(applied["rollback_available"] is True, "rollback available")
        _assert(set(applied["files_changed"]) == {"app.py"}, "only approved file changed")
        checks += 4

        preview = rollback_controlled_apply(repository_root=str(root), rollback_id=applied["rollback_id"], mode="rollback_preview")
        rolled = rollback_controlled_apply(repository_root=str(root), rollback_id=applied["rollback_id"], mode="rollback", approval_token=preview["approval_digest"])
        _assert(rolled["transaction_state"] == "rolled_back", "rollback should succeed")
        _assert((root / "app.py").read_text(encoding="utf-8") == original, "rollback restores bytes")
        _assert(_sha(root / "app.py") == applied["file_hashes_before"]["app.py"], "rollback restores hash")
        _assert(applied["rollback_manifest"]["files"]["app.py"]["existed"] is True, "manifest complete")
        checks += 4

        before_step = {"target_file": "other.py", "change_type": "insert_before_exact", "anchor": "anchor\n", "replacement_text": "inserted-before\n", "purpose": "before", "validation_after_change": []}
        before_applied = _prepare_and_apply(root, patch_id="before", patch_steps=[before_step], approved_files=["other.py"], expected_file_hashes={"other.py": _sha(root / "other.py")})
        _assert("inserted-before\nanchor" in (root / "other.py").read_text(encoding="utf-8"), "insert-before succeeds")
        before_preview = rollback_controlled_apply(repository_root=str(root), rollback_id=before_applied["rollback_id"], mode="rollback_preview")
        rollback_controlled_apply(repository_root=str(root), rollback_id=before_applied["rollback_id"], mode="rollback", approval_token=before_preview["approval_digest"])
        after_step = {"target_file": "other.py", "change_type": "insert_after_exact", "anchor": "anchor\n", "replacement_text": "inserted-after\n", "purpose": "after", "validation_after_change": []}
        _prepare_and_apply(root, patch_id="after", patch_steps=[after_step], approved_files=["other.py"], expected_file_hashes={"other.py": _sha(root / "other.py")})
        _assert("anchor\ninserted-after" in (root / "other.py").read_text(encoding="utf-8"), "insert-after succeeds")
        checks += 2

        for label, payload in [
            ("ambiguous", _base(root, patch_steps=[_replace_step("dupe.py", "same\n", "new\n")], approved_files=["dupe.py"], expected_file_hashes={"dupe.py": _sha(root / "dupe.py")})),
            ("missing anchor", _base(root, patch_steps=[_replace_step(original="missing\n")], expected_file_hashes={"app.py": _sha(root / "app.py")})),
            ("traversal", _base(root, patch_steps=[_replace_step("../outside.py")], approved_files=["../outside.py"])),
            ("outside", _base(root, patch_steps=[_replace_step(str(root.parent / "outside.py"))], approved_files=[str(root.parent / "outside.py")])),
            (".env", _base(root, patch_steps=[_replace_step(".env")], approved_files=[".env"])),
            ("secret", _base(root, patch_steps=[_replace_step("secret.key")], approved_files=["secret.key"])),
            (".git", _base(root, patch_steps=[_replace_step(".git/config")], approved_files=[".git/config"])),
            ("venv", _base(root, patch_steps=[_replace_step("venv/x.py")], approved_files=["venv/x.py"])),
            ("cache", _base(root, patch_steps=[_replace_step("__pycache__/x.py")], approved_files=["__pycache__/x.py"])),
            ("binary", _base(root, patch_steps=[_replace_step("image.png")], approved_files=["image.png"])),
            ("unsupported", _base(root, patch_steps=[_replace_step("unknown.xyz")], approved_files=["unknown.xyz"])),
            ("forbidden", _base(root, forbidden_files=["app.py"])),
            ("non-approved", _base(root, approved_files=["other.py"])),
            ("duplicate", _base(root, patch_steps=[_replace_step(), _replace_step(replacement="alpha = 4\n")])),
            ("file budget", _base(root, patch_steps=[_replace_step(), _replace_step("other.py", "before\n", "after\n")], approved_files=["app.py", "other.py"], max_files=1)),
            ("line budget", _base(root, patch_steps=[_replace_step(replacement="a\nb\nc\nd\n")], max_total_changed_lines=2)),
            ("sha mismatch", _base(root, expected_file_hashes={"app.py": "f" * 64})),
            ("delete", _base(root, patch_steps=[{**_replace_step(), "change_type": "delete_file"}])),
            ("directory", _base(root, patch_steps=[{**_replace_step(), "target_file": ".", "change_type": "directory_operation"}], approved_files=["."])),
            ("command absent", _base(root, patch_steps=[{**_replace_step(), "change_type": "shell_command"}])),
        ]:
            result = prepare_controlled_apply(**payload, mode="prepare")
            _assert(result["transaction_state"] == "blocked", f"{label} should block")
        checks += 20

    finally:
        fixture.cleanup()

    fixture2 = _make_repo()
    try:
        root = Path(fixture2.name)
        prepared = prepare_controlled_apply(**_base(root), mode="prepare")
        (root / "app.py").write_text("changed after prepare\n", encoding="utf-8")
        modified = execute_controlled_apply(**_base(root), mode="apply", approval_token=prepared["approval_digest"])
        _assert(modified["transaction_state"] == "blocked", "source modified after prepare blocked")
        checks += 1

        created_step = {"target_file": "new_file.py", "change_type": "create_new_text_file", "replacement_text": "print('new')\n", "purpose": "create", "validation_after_change": []}
        created = _prepare_and_apply(root, patch_id="create", patch_steps=[created_step], approved_files=["new_file.py"], expected_file_hashes={})
        _assert((root / "new_file.py").exists(), "create-new-text-file succeeds when approved")
        _assert(created["rollback_available"] is True, "create rollback available")
        checks += 2

        existing_create = execute_controlled_apply(**_base(root, patch_id="create-existing", patch_steps=[{**created_step, "target_file": "app.py"}], approved_files=["app.py"], expected_file_hashes={}), mode="apply", approval_token="bad")
        _assert(existing_create["transaction_state"] == "blocked", "create existing blocked")
        checks += 1
    finally:
        fixture2.cleanup()

    fixture3 = _make_repo()
    try:
        root = Path(fixture3.name)
        applied = _prepare_and_apply(root, patch_id="rollback-block")
        (root / "app.py").write_text("changed after apply\n", encoding="utf-8")
        preview = rollback_controlled_apply(repository_root=str(root), rollback_id=applied["rollback_id"], mode="rollback_preview")
        blocked = rollback_controlled_apply(repository_root=str(root), rollback_id=applied["rollback_id"], mode="rollback", approval_token=preview["approval_digest"])
        _assert(blocked["transaction_state"] == "blocked", "rollback blocks changed file")
        _assert(blocked["precondition_failures"], "rollback changed-file failure reported")
        checks += 2
    finally:
        fixture3.cleanup()

    fixture4 = _make_repo()
    try:
        root = Path(fixture4.name)
        step1 = _replace_step("app.py", "alpha = 1\n", "alpha = 7\n")
        step2 = {"target_file": "other.py", "change_type": "replace_exact", "expected_original_text": "before\n", "replacement_text": "boom\n", "purpose": "fail", "validation_after_change": [], "simulate_write_failure": True}
        data = _base(root, patch_id="fail", patch_steps=[step1, step2], approved_files=["app.py", "other.py"], expected_file_hashes={"app.py": _sha(root / "app.py"), "other.py": _sha(root / "other.py")})
        prepared = prepare_controlled_apply(**data, mode="prepare")
        failed = execute_controlled_apply(**data, mode="apply", approval_token=prepared["approval_digest"])
        _assert(failed["transaction_state"] == "transaction_failed", "transaction failure state")
        _assert((root / "app.py").read_text(encoding="utf-8").startswith("alpha = 1"), "partial write restored")
        _assert((root / "other.py").read_text(encoding="utf-8").startswith("before"), "no partial second write")
        checks += 3
    finally:
        fixture4.cleanup()

    fixture5 = _make_repo()
    try:
        root = Path(fixture5.name)
        digest1 = prepare_controlled_apply(**_base(root), mode="prepare")["approval_digest"]
        digest2 = prepare_controlled_apply(**_base(root), mode="prepare")["approval_digest"]
        dry1 = execute_controlled_apply(**_base(root))
        dry2 = execute_controlled_apply(**_base(root))
        _assert(digest1 == digest2, "approval digest deterministic")
        _assert(dry1["request_id"] == dry2["request_id"], "dry-run deterministic")
        fallback = execute_controlled_apply(repository_root=str(root), patch_id="", patch_steps=[], approved_files=[])
        _assert(fallback["transaction_state"] == "blocked", "insufficient input fallback")
        _assert(dry1["transaction_state"] in {"dry_run", "prepared", "blocked", "applied", "rolled_back", "transaction_failed"}, "valid transaction state")
        _assert((root / ".luxcode_runtime").exists() is False, "rollback area only after real apply")
        blocked = prepare_controlled_apply(**_base(root, patch_steps=[{**_replace_step(), "change_type": "delete_file"}]), mode="prepare")
        _assert(blocked["recommended_handoff"] == "human", "blocked/high-risk handoff")
        _assert(dry1["validation_execution_blocked"] is True, "validation execution remains blocked")
        checks += 7
    finally:
        fixture5.cleanup()

    _assert(live_runtime.exists() is live_before, "LUXDEEP rollback area must remain unchanged")
    checks += 1

    print(f"PASS lux controlled apply validator: {checks} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
