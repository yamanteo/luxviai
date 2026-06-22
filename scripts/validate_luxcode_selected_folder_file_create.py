from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from app import app  # noqa: E402  # import after path adjustments


TEST_ROOT = Path(r"C:\Users\Teoman\OneDrive\Desktop\LUXCODE_TEST_PROJECT")
SELECTED_FOLDER = "ui_test_selected"
TARGET_FILE = TEST_ROOT / SELECTED_FOLDER / "ping_ui_selected2.txt"
EXPECTED_CONTENT = "OK_FROM_LUXCODE"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _poll_status(client: TestClient, task_id: str):
    response = client.get(f"/luxcode-task/{task_id}")
    return response.status_code, response.json()


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
    create_body = create_response.json()
    task_id = str(create_body.get("task_id") or "")
    _assert(task_id, "create did not return task_id")

    status = str(create_body.get("status") or "")
    if status == "completed" and create_body.get("ok") is True:
        print("task-completed-immediately", status, create_body.get("message"))
    else:
        waiting_for_approval = False
        for index in range(10):
            status_code, status_body = _poll_status(client, task_id)
            print(
                "status-check",
                index + 1,
                status_code,
                status_body.get("current_state") or status_body.get("status"),
                status_body.get("requires_user_approval"),
            )
            _assert(status_code == 200, "status check did not return HTTP 200")

            if status_body.get("requires_user_approval") is True and status_body.get("pending_approval_gate"):
                waiting_for_approval = True
                break
            if status_body.get("current_state") in {"completed", "blocked", "failed"}:
                break

            advance_response = client.post("/luxcode-task/advance", json={"task_id": task_id})
            advance_body = advance_response.json()
            print(
                "advance-before-approval",
                index + 1,
                advance_response.status_code,
                advance_body.get("current_state"),
                advance_body.get("pending_approval_gate"),
                advance_body.get("blocked_reasons"),
            )
            _assert(advance_response.status_code == 200, "advance before approval did not return HTTP 200")

            if advance_body.get("requires_user_approval") is True and advance_body.get("pending_approval_gate"):
                waiting_for_approval = True
                break

        if waiting_for_approval:
            approve_response = client.post("/luxcode-task/approve", json={"task_id": task_id})
            approve_body = approve_response.json()
            print(
                "approve",
                approve_response.status_code,
                approve_body.get("current_state"),
                approve_body.get("pending_approval_gate"),
                approve_body.get("blocked_reasons"),
            )
            _assert(approve_response.status_code == 200, "approve did not return HTTP 200")
            _assert(
                approve_body.get("approval_state_approved") is not False,
                "approval_state.approved was not set",
            )
            _assert(
                isinstance(approve_body.get("last_approval_action"), dict)
                and approve_body.get("last_approval_action", {}).get("approval_action") == "approve",
                "approve response did not include approval action",
            )

            final_response = client.post("/luxcode-task/advance", json={"task_id": task_id})
            final_body = final_response.json()
            print(
                "advance-after-approval",
                final_response.status_code,
                final_body.get("current_state"),
                final_body.get("blocked_reasons"),
            )
            _assert(final_response.status_code == 200, "advance after approval did not return HTTP 200")

    _assert(TARGET_FILE.exists(), f"target file was not created: {TARGET_FILE}")
    _assert(TARGET_FILE.read_text(encoding="utf-8") == EXPECTED_CONTENT, "target file content mismatch")
    print(f"PASS selected-folder create: {TARGET_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
