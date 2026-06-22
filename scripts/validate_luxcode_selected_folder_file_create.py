from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import app  # noqa: E402


TEST_ROOT = Path(r"C:\Users\Teoman\OneDrive\Desktop\LUXCODE_TEST_PROJECT")
SELECTED_FOLDER = "ui_test_selected"
TARGET_FILE = TEST_ROOT / SELECTED_FOLDER / "ping_ui_selected2.txt"
EXPECTED_CONTENT = "OK_FROM_LUXCODE"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    (TEST_ROOT / SELECTED_FOLDER).mkdir(parents=True, exist_ok=True)
    if TARGET_FILE.exists():
        TARGET_FILE.unlink()

    client = TestClient(app)

    select_response = client.post(
        "/luxcode-workspace/select-folder",
        json={
            "initial_dir": str(TEST_ROOT),
            "title": SELECTED_FOLDER,
        },
    )
    print("select-folder", select_response.status_code, select_response.json())
    _assert(select_response.status_code == 200, "select-folder did not return HTTP 200")
    _assert(select_response.json().get("ok") is True, "select-folder did not return ok:true")

    create_response = client.post(
        "/luxcode-task/create",
        json={
            "original_request": "create ping_ui_selected2.txt with content 'OK_FROM_LUXCODE'",
            "repository_root": str(TEST_ROOT),
            "selected_folders": [SELECTED_FOLDER],
        },
    )
    print("create", create_response.status_code, create_response.json())
    _assert(create_response.status_code == 200, "create did not return HTTP 200")
    task_id = str(create_response.json().get("task_id") or "")
    _assert(task_id, "create did not return task_id")

    awaiting = {}
    for index in range(8):
        advance_response = client.post("/luxcode-task/advance", json={"task_id": task_id})
        body = advance_response.json()
        print("advance-before-approval", index + 1, advance_response.status_code, body.get("current_state"), body.get("pending_approval_gate"), body.get("blocked_reasons"))
        _assert(advance_response.status_code == 200, "advance before approval did not return HTTP 200")
        if body.get("current_state") == "awaiting_approval" and body.get("requires_user_approval") is True:
            awaiting = body
            break
    _assert(awaiting, "task did not reach awaiting_approval")
    _assert(awaiting.get("pending_approval_gate") == "approve_patch", "pending approval gate is not approve_patch")

    approve_response = client.post("/luxcode-task/approve", json={"task_id": task_id})
    approve_body = approve_response.json()
    print("approve", approve_response.status_code, approve_body.get("current_state"), approve_body.get("pending_approval_gate"), approve_body.get("blocked_reasons"))
    _assert(approve_response.status_code == 200, "approve did not return HTTP 200")
    _assert(approve_body.get("current_state") == "approval_verified", "approval did not verify the task")
    _assert(approve_body.get("approval_state_approved") is True, "approval_state.approved did not become true")
    _assert(approve_body.get("approval_events_count", 0) >= 1, "approval event was not recorded")
    _assert((approve_body.get("last_approval_action") or {}).get("approval_gate") == "approve_patch", "approve did not mark approve_patch gate")

    final_advance_response = client.post("/luxcode-task/advance", json={"task_id": task_id})
    final_body = final_advance_response.json()
    print("advance-after-approval", final_advance_response.status_code, final_body.get("current_state"), final_body.get("blocked_reasons"), final_body.get("apply_summary"))
    _assert(final_advance_response.status_code == 200, "advance after approval did not return HTTP 200")
    _assert(final_body.get("current_state") != "blocked", f"task blocked after approval: {final_body.get('blocked_reasons')}")
    _assert(final_body.get("approval_state_approved") is True, "approval_state.approved was lost after advance")
    _assert(TARGET_FILE.exists(), f"target file was not created: {TARGET_FILE}")
    _assert(TARGET_FILE.read_text(encoding="utf-8") == EXPECTED_CONTENT, "target file content mismatch")

    print(f"PASS selected-folder create: {TARGET_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
