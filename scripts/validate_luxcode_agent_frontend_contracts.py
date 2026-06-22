from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app

INDEX_HTML = ROOT / "static" / "luxcode_v1" / "index.html"
API_JS = ROOT / "static" / "luxcode_v1" / "luxcode_api.js"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_frontend_contract() -> None:
    index = INDEX_HTML.read_text(encoding="utf-8")
    api_js = API_JS.read_text(encoding="utf-8")

    require("/luxcode-agent/run" in api_js, "luxcode_api.js must call /luxcode-agent/run")
    require("runLuxCodeAgent" in api_js, "LuxCodeApi.runLuxCodeAgent must be exported")
    require("btnAgentMode" in index, "Coder mode button must exist")
    require("btnChatMode" in index, "Chat mode button must exist")
    require("setLuxCodeMode" in index, "mode toggle function must exist")
    require("buildAgentPayload" in index, "agent payload builder must exist")
    require("workspace_root" in index, "agent payload must include workspace_root")
    require("session_id" in index, "agent payload must include session_id")
    require("runAgentFromInput" in index, "agent send flow must exist")
    require("agent-tool-item" in index, "tool-call UI must exist")
    require("escapeAgentHtml" in index, "tool-call output must be escaped")


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


def main() -> None:
    test_frontend_contract()
    print("PASS TEST 1: Frontend contract")
    test_agent_endpoint_writes_to_workspace()
    print("PASS TEST 2: Agent endpoint writes to selected workspace")
    print("SUMMARY: ALL PASS")


if __name__ == "__main__":
    main()
