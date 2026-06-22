from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from tool_executor import (  # noqa: E402
    create_directory,
    delete_file,
    edit_file,
    list_directory,
    read_file,
    run_command,
    search_in_files,
    write_file,
)
from luxcode_agent_runtime import run_agent  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    temp = Path(tempfile.mkdtemp(prefix="luxcode_agent_tools_"))
    try:
        test_path = "tools/test_tool.txt"
        check(create_directory("tools", workspace_root=temp)["success"], "create_directory failed")
        check(write_file(test_path, "hello", workspace_root=temp)["success"], "write_file failed")
        read = read_file(test_path, workspace_root=temp)
        check(read["success"] and read["result"] == "hello", "read_file mismatch")
        edited = edit_file(test_path, "hello", "hello world", workspace_root=temp)
        check(edited["success"], "edit_file failed")
        check(read_file(test_path, workspace_root=temp)["result"] == "hello world", "edit_file did not persist")
        search = search_in_files(".", "hello world", workspace_root=temp)
        check(search["success"] and search["result"], "search_in_files did not find text")
        listed = list_directory("tools", workspace_root=temp)
        check(listed["success"] and listed["result"], "list_directory failed")
        check(delete_file(test_path, workspace_root=temp)["success"], "delete_file failed")
        check(not (temp / test_path).exists(), "delete_file did not remove file")
        print("PASS TEST 1: Tool Engine")

        version = run_command("python --version", workspace_root=temp)
        check(version["success"], "python --version failed")
        directory = run_command("dir", workspace_root=temp)
        check(directory["success"], "dir failed")
        print("PASS TEST 2: Command Runner")

        agent = run_agent("test.py dosyası oluştur, içine hello world yaz, çalıştır", workspace_root=temp, session_id="validator")
        check(agent["ok"], f"agent loop failed: {agent}")
        check((temp / "test.py").is_file(), "agent did not create test.py")
        check("hello world" in str(agent["results"][-1]["result"]["result"]["stdout"]), "agent command output mismatch")
        print("PASS TEST 3: Agent Loop")

        client = TestClient(app)
        response = client.post(
            "/luxcode-agent/run",
            json={"prompt": "mevcut projeyi tara ve bana rapor ver", "workspace_root": str(temp), "session_id": "api-validator"},
        )
        body = response.json()
        check(response.status_code == 200 and body.get("ok"), f"agent API scan failed: {body}")
        check(body["results"][0]["tool"] == "list_directory", "agent API did not use list_directory")
        print("PASS TEST 4: Integration API")

        print("SUMMARY: ALL PASS")
        return 0
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
