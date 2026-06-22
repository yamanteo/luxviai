from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from luxcode_swarm.adapters import BaseModelAdapter, ToolCallNormalizer
from luxcode_swarm.adapters import OllamaAdapter
from luxcode_swarm.classifier import ComplexityClassifier
from luxcode_swarm.router import SwarmOrchestrator
from luxcode_swarm.schemas import ModelResult, SwarmConfig, TaskClassification, ToolCall
from luxcode_swarm.state_manager import JsonStateManager
from luxcode_swarm.tools import ToolRegistry


class FixtureAdapter(BaseModelAdapter):
    model_name = "ollama"

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        if context.get("tool_results"):
            return ModelResult(ok=True, model=self.model_name, content="fixture completed after tool", tool_calls=[])
        return ModelResult(
            ok=True,
            model=self.model_name,
            content="fixture completed",
            tool_calls=[ToolCall(id="fixture-write", name="filesystem_write", arguments={"path": "agent_result.txt", "content": "swarm ok\n"})],
            usage_tokens=12,
        )


class NoToolAdapter(BaseModelAdapter):
    model_name = "ollama"

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        return ModelResult(ok=True, model=self.model_name, content="I would do it", tool_calls=[])


class TwoStepAdapter(BaseModelAdapter):
    model_name = "ollama"

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        if not context.get("tool_results"):
            return ModelResult(
                ok=True,
                model=self.model_name,
                content="step one",
                tool_calls=[ToolCall(id="two-step-write", name="filesystem_write", arguments={"path": "loop.txt", "content": "loop ok\n"})],
            )
        return ModelResult(ok=True, model=self.model_name, content="done after tool", tool_calls=[])


class ThreeStepAdapter(BaseModelAdapter):
    model_name = "ollama"

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        results = context.get("tool_results") or []
        if len(results) == 0:
            return ModelResult(
                ok=True,
                model=self.model_name,
                content="write",
                tool_calls=[ToolCall(id="three-step-write", name="filesystem_write", arguments={"path": "multi.txt", "content": "multi ok\n"})],
            )
        if len(results) == 1:
            return ModelResult(
                ok=True,
                model=self.model_name,
                content="run",
                tool_calls=[ToolCall(id="three-step-run", name="bash_execute", arguments={"command": "python --version", "timeout": 10})],
            )
        return ModelResult(ok=True, model=self.model_name, content="done after write and command", tool_calls=[])


class DangerousCommandAdapter(BaseModelAdapter):
    model_name = "ollama"

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        return ModelResult(
            ok=True,
            model=self.model_name,
            content="danger",
            tool_calls=[ToolCall(id="danger-run", name="bash_execute", arguments={"command": "rm -rf .", "timeout": 10})],
        )


class TraversalAdapter(BaseModelAdapter):
    model_name = "ollama"

    def execute(self, prompt: str, context: Dict[str, Any], tools: List[Dict[str, Any]]) -> ModelResult:
        return ModelResult(
            ok=True,
            model=self.model_name,
            content="escape",
            tool_calls=[ToolCall(id="escape-write", name="filesystem_write", arguments={"path": "../evil.txt", "content": "bad"})],
        )


class CriticalClassifier:
    def classify(self, prompt: str) -> TaskClassification:
        return TaskClassification(9, 5000, True, False, "forced critical")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="luxcode_swarm_validate_") as temp:
        root = Path(temp)
        state = JsonStateManager(root / ".state")
        tools = ToolRegistry(root)

        write = tools.filesystem_write("README.md", "# Test\n")
        assert_true(write["ok"], "filesystem_write failed")
        read = tools.filesystem_read("README.md")
        assert_true(read["ok"] and read["content"] == "# Test\n", "filesystem_read mismatch")
        listing = tools.filesystem_list(".")
        assert_true(any(item["path"] == "README.md" for item in listing["entries"]), "filesystem_list missing README.md")
        command = tools.bash_execute("python --version", timeout=10)
        assert_true("Python" in (command["stdout"] + command["stderr"]), "bash_execute did not run python")

        normalized = ToolCallNormalizer.normalize_ollama(json.dumps({"tool": "filesystem_list", "arguments": {"dir": "."}}))
        assert_true(normalized[0].name == "filesystem_list", "ollama normalizer failed")
        gemini = ToolCallNormalizer.normalize_gemini({"name": "filesystem_read", "args": {"path": "README.md"}})
        assert_true(gemini.name == "filesystem_read", "gemini normalizer failed")
        claude = ToolCallNormalizer.normalize_claude({"id": "a", "name": "bash_execute", "input": {"command": "python --version"}})
        assert_true(claude.name == "bash_execute", "claude normalizer failed")

        classification = ComplexityClassifier().classify("read README.md and make a small file change")
        assert_true(1 <= classification.complexity <= 10, "classifier complexity out of range")
        assert_true(classification.requires_filesystem, "classifier did not detect filesystem need")

        orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(root), state_root=".state"),
            state_manager=state,
            tools=tools,
            adapters={"ollama": FixtureAdapter()},
        )
        result = orchestrator.execute("create agent_result.txt")
        assert_true(result["ok"], "orchestrator did not complete")
        assert_true((root / "agent_result.txt").read_text(encoding="utf-8") == "swarm ok\n", "orchestrator tool write missing")
        task_id = result["task"]["task_id"]
        checkpoints = state.list_checkpoints(task_id)
        assert_true(len(checkpoints) == 1, "checkpoint was not recorded")

        no_tool_root = root / "no_tool"
        no_tool_root.mkdir()
        no_tool = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(no_tool_root), state_root=".state"),
            adapters={"ollama": NoToolAdapter(), "gemini": NoToolAdapter(), "cloud_models": NoToolAdapter()},
        )
        no_tool_result = no_tool.execute("read file README.md")
        assert_true(not no_tool_result["ok"], "filesystem task completed without tool_calls")
        assert_true(no_tool_result["error"] == "tool_calls_required_but_missing", "missing tool call error not enforced")

        loop_root = root / "loop_workspace"
        loop_root.mkdir()
        loop_orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(loop_root), state_root=".state"),
            adapters={"ollama": TwoStepAdapter()},
        )
        loop_result = loop_orchestrator.execute("create loop.txt")
        assert_true(loop_result["ok"], "tool loop did not complete")
        assert_true(loop_result["steps"] == 2, "tool loop did not call adapter after tool result")
        assert_true((loop_root / "loop.txt").read_text(encoding="utf-8") == "loop ok\n", "tool loop did not write file")

        multi_root = root / "multi_workspace"
        multi_root.mkdir()
        multi_orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(multi_root), state_root=".state"),
            adapters={"ollama": ThreeStepAdapter()},
        )
        multi_result = multi_orchestrator.execute("write multi.txt then run python --version")
        assert_true(multi_result["ok"], "multi-tool flow did not complete")
        assert_true(multi_result["steps"] == 3, "multi-tool flow did not reach final model turn")
        assert_true(len(multi_result["tool_results"]) == 2, "multi-tool flow did not execute two tools")
        assert_true((multi_root / "multi.txt").read_text(encoding="utf-8") == "multi ok\n", "multi-tool write missing")

        denied = tools.bash_execute("rm -rf .", timeout=10)
        assert_true(not denied["ok"] and denied["error"] == "denied_command", "dangerous command was not denied")

        traversal = tools.execute_tool("filesystem_write", {"path": "../evil.txt", "content": "bad"})
        assert_true(not traversal["ok"] and "path_outside_workspace" in traversal["error"], "path traversal was not blocked")

        dangerous_root = root / "danger_workspace"
        dangerous_root.mkdir()
        dangerous_orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(dangerous_root), state_root=".state"),
            adapters={"ollama": DangerousCommandAdapter()},
        )
        dangerous_result = dangerous_orchestrator.execute("list files")
        assert_true(not dangerous_result["ok"], "dangerous command task completed")
        assert_true("denied_command" in dangerous_result["error"], "dangerous command did not surface denied_command")

        traversal_root = root / "traversal_workspace"
        traversal_root.mkdir()
        traversal_orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(traversal_root), state_root=".state"),
            adapters={"ollama": TraversalAdapter()},
        )
        traversal_result = traversal_orchestrator.execute("list files")
        assert_true(not traversal_result["ok"], "path traversal task completed")
        assert_true("path_outside_workspace" in traversal_result["error"], "path traversal did not surface path_outside_workspace")

        approval_root = root / "approval_workspace"
        approval_root.mkdir()
        approval_orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(approval_root), state_root=".state"),
            classifier=CriticalClassifier(),
        )
        approval_result = approval_orchestrator.execute("critical refactor and deploy")
        assert_true(not approval_result["ok"], "critical paid task ran without approval")
        assert_true(approval_result["status"] == "awaiting_cost_approval", "critical task did not request approval")

        compact_root = root / "compact_html_workspace"
        compact_root.mkdir()
        compact_orchestrator = SwarmOrchestrator(
            SwarmConfig(workspace_root=str(compact_root), state_root=".state"),
            adapters={"ollama": OllamaAdapter(base_url="http://127.0.0.1:1", timeout=1)},
        )
        compact_result = compact_orchestrator.execute("create coder.html")
        coder_path = compact_root / "coder.html"
        assert_true(compact_result["ok"], "compact coder.html task failed")
        assert_true(coder_path.is_file(), "coder.html was not created")
        coder_content = coder_path.read_text(encoding="utf-8")
        assert_true("monaco-editor" in coder_content, "coder.html does not load editor from CDN")
        assert_true(len(coder_content) <= 4000, "coder.html is too large")

        from fastapi.testclient import TestClient
        import app

        legacy_root = root / "legacy_endpoint_workspace"
        legacy_root.mkdir()
        client = TestClient(app.app)
        legacy_response = client.post(
            "/luxcode-task/create",
            json={"original_request": "create ping.txt", "workspace_root": str(legacy_root), "mode": "swarm"},
        )
        legacy_body = legacy_response.json()
        assert_true(legacy_response.status_code == 200, "legacy create endpoint did not return 200")
        assert_true(legacy_body.get("ok") is True, "legacy create endpoint did not complete via swarm")
        assert_true((legacy_root / "ping.txt").is_file(), "legacy create did not write ping.txt to selected workspace")
        assert_true(not (REPO_ROOT / "ping.txt").exists(), "legacy create wrote ping.txt to repo root")

        print("PASS luxcode_swarm filesystem tools")
        print("PASS luxcode_swarm tool normalizers")
        print("PASS luxcode_swarm classifier")
        print("PASS luxcode_swarm orchestrator checkpoint")
        print("PASS luxcode_swarm rejects filesystem completion without tool calls")
        print("PASS luxcode_swarm multi-step tool loop")
        print("PASS luxcode_swarm multi-tool write plus command")
        print("PASS luxcode_swarm dangerous command denylist")
        print("PASS luxcode_swarm path traversal block")
        print("PASS luxcode_swarm paid model approval gate")
        print("PASS luxcode_swarm compact coder html")
        print("PASS legacy luxcode-task create forwards selected workspace to swarm")
        print("SUMMARY: ALL PASS (12)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
