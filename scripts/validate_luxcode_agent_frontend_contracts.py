from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app
from luxcode_agent_runtime import parse_tool_calls, run_agent

INDEX_HTML = ROOT / "static" / "luxcode_v1" / "index.html"
API_JS = ROOT / "static" / "luxcode_v1" / "luxcode_api.js"
CONVERSATION_CONTROLLER = ROOT / "static" / "luxcode_v1" / "luxcode_conversation_controller.js"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_frontend_contract() -> None:
    index = INDEX_HTML.read_text(encoding="utf-8")
    api_js = API_JS.read_text(encoding="utf-8")
    controller_js = CONVERSATION_CONTROLLER.read_text(encoding="utf-8")

    require("/luxcode-agent/run" in api_js, "luxcode_api.js must call /luxcode-agent/run")
    require("runLuxCodeAgent" in api_js, "LuxCodeApi.runLuxCodeAgent must be exported")
    require("workspace_root" in index, "agent payload must include workspace_root")
    require("session_id" in index, "agent payload must include session_id")
    require(
        "sendConversationMessage" in controller_js and "runLuxCodeAgent" in api_js,
        "agent send flow must exist",
    )
    require("submitFromInput" in controller_js, "conversation submit flow must exist")
    require("txtLandingInput" in index, "landing input must exist")
    require(
        "txtDockedInput" in index or "dockedInputContainer" in index,
        "docked input/compact submit path must exist",
    )
    require("window.LuxCodeApi" in index, "api integration must exist")


def test_agent_endpoint_writes_to_workspace() -> None:
    client = TestClient(app)
    with tempfile.TemporaryDirectory(prefix="luxcode-agent-frontend-") as temp_root:
        workspace = Path(temp_root)
        response = client.post(
            "/luxcode-agent/run",
            json={
                "prompt": "create agent_frontend_ping.txt with content 'OK_AGENT_FRONTEND'",
                "workspace_root": str(workspace),
                "session_id": "frontend-contract-test",
                "max_steps": 12,
            },
        )
        require(response.status_code == 200, f"unexpected status: {response.status_code} {response.text}")
        payload = response.json()
        require(payload.get("ok") is True, f"agent run failed: {payload}")
        target = workspace / "agent_frontend_ping.txt"
        require(target.exists(), f"expected file was not created: {target}")
        require(target.read_text(encoding="utf-8") == "OK_AGENT_FRONTEND", "file content mismatch")
        require(len(payload.get("tool_calls") or []) >= 1, "tool_calls must be returned")


def test_tool_call_tag_contract() -> None:
    calls = parse_tool_calls(
        '<tool_call>{"tool":"write_file","params":{"path":"contract.txt","content":"hello"}} </tool_call>',
        default_filename="fallback.txt",
        prompt="create file",
    )
    require(len(calls) == 1, "tool_call tag did not parse to one call")
    require(calls[0]["tool"] == "write_file", "tool name mismatch for tool_call tag")
    require(calls[0]["params"].get("path") == "contract.txt", "tool_call path mismatch")


def test_run_agent_with_tool_call_tag() -> None:
    with tempfile.TemporaryDirectory(prefix="luxcode-agent-tag-") as temp_root:
        workspace = Path(temp_root)
        message = (
            'Doğrudan yaz: <tool_call>'
            '{"tool":"write_file","params":{"path":"tag_ping.txt","content":"OK_TOOL_TAG"}}'
            '</tool_call>'
        )
        result = run_agent(
            message,
            workspace_root=str(workspace),
            session_id="frontend-toolcall-contract",
            max_steps=4,
        )
        require(result.get("ok") is True, f"run_agent returned failure: {result}")
        target = workspace / "tag_ping.txt"
        require(target.exists(), f"expected file was not created: {target}")
        require(target.read_text(encoding="utf-8") == "OK_TOOL_TAG", "tag plan file content mismatch")
        require(any(item.get("tool") == "write_file" for item in result.get("tool_calls", [])), "result tool_calls missing write_file")


def main() -> None:
    test_frontend_contract()
    print("PASS TEST 1: Frontend contract")
    test_agent_endpoint_writes_to_workspace()
    print("PASS TEST 2: Agent endpoint writes to selected workspace")
    test_tool_call_tag_contract()
    print("PASS TEST 3: Tool call tags are parsed correctly")
    test_run_agent_with_tool_call_tag()
    print("PASS TEST 4: run_agent executes explicit tool_call tags")
    print("SUMMARY: ALL PASS")


if __name__ == "__main__":
    main()
