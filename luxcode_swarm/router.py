from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .adapters import BaseModelAdapter, default_adapters
from .classifier import ComplexityClassifier
from .cost_guardian import CostGuardian
from .schemas import ModelResult, SwarmConfig
from .state_manager import JsonStateManager
from .tools import ToolRegistry


class SwarmOrchestrator:
    def __init__(
        self,
        config: SwarmConfig,
        *,
        classifier: ComplexityClassifier | None = None,
        state_manager: JsonStateManager | None = None,
        tools: ToolRegistry | None = None,
        adapters: Dict[str, BaseModelAdapter] | None = None,
        cost_guardian: CostGuardian | None = None,
    ) -> None:
        self.config = config
        state_root = Path(config.workspace_root) / config.state_root
        self.classifier = classifier or ComplexityClassifier()
        self.state = state_manager or JsonStateManager(state_root)
        self.tools = tools or ToolRegistry(config.workspace_root, config.command_timeout_seconds)
        self.adapters = adapters or default_adapters()
        self.cost = cost_guardian or CostGuardian(config)

    def route_chain(self, complexity: int) -> List[str]:
        if complexity <= 3:
            return ["ollama", "gemini", "cloud_models"]
        if complexity <= 6:
            return ["gemini", "cloud_models", "deepseek"]
        if complexity <= 8:
            return ["cloud_models", "deepseek", "whale"]
        return ["deepseek", "whale", "codex"]

    def tool_specs(self) -> List[Dict[str, Any]]:
        return [
            {"name": "filesystem_read", "arguments": {"path": "string"}},
            {"name": "filesystem_write", "arguments": {"path": "string", "content": "string"}},
            {"name": "filesystem_list", "arguments": {"dir": "string"}},
            {"name": "bash_execute", "arguments": {"command": "string", "timeout": "integer"}},
        ]

    def execute(self, prompt: str) -> Dict[str, Any]:
        classification = self.classifier.classify(prompt)
        chain = self.route_chain(classification.complexity)
        task = self.state.create_task(prompt, classification, chain[0])
        all_tool_results: List[Dict[str, Any]] = []
        context: Dict[str, Any] = {
            "task_id": task.task_id,
            "classification": classification.to_dict(),
            "checkpoints": [],
            "transfers": [],
            "tool_results": [],
        }

        for index, model_name in enumerate(chain):
            if self.cost.requires_approval(model_name, classification.estimated_tokens):
                estimated = self.cost.estimate_cost_usd(model_name, classification.estimated_tokens)
                approval = self.state.create_approval_request(task.task_id, model_name, estimated)
                return {
                    "ok": False,
                    "status": "awaiting_cost_approval",
                    "task_id": task.task_id,
                    "model": model_name,
                    "approval": approval,
                    "message": f"Paid model approval required for {model_name}. Estimated cost ${estimated:.4f}.",
                }

            result = self._run_model_loop(
                task_id=task.task_id,
                model_name=model_name,
                prompt=prompt,
                context=context,
                requires_filesystem=classification.requires_filesystem,
            )

            if result["ok"]:
                all_tool_results.extend(result["tool_results"])
                record = self.state.update_task(
                    task.task_id,
                    status="completed",
                    current_model=model_name,
                    result={"content": result["model_result"].content, "tool_results": all_tool_results},
                )
                return {
                    "ok": True,
                    "status": "completed",
                    "task": record.to_dict(),
                    "model_result": result["model_result"].to_dict(),
                    "tool_results": all_tool_results,
                    "steps": result["steps"],
                }

            failed_result: ModelResult = result["model_result"]
            if self._is_non_escalatable_security_error(failed_result.error):
                record = self.state.update_task(task.task_id, status="failed", current_model=model_name, last_error=failed_result.error)
                return {"ok": False, "status": "failed", "task": record.to_dict(), "error": failed_result.error}

            next_model = chain[index + 1] if index + 1 < len(chain) else ""
            self.state.update_task(task.task_id, status="failed" if not next_model else "escalating", current_model=model_name, last_error=failed_result.error)
            if next_model:
                summary = self._summarize_context(prompt, failed_result.error, context)
                transfer = self.state.record_transfer(task.task_id, model_name, next_model, failed_result.error or failed_result.finish_reason, summary)
                context["transfers"].append(transfer)
                context["previous_error"] = failed_result.error
                context["previous_model"] = model_name
                continue

            record = self.state.update_task(task.task_id, status="failed", current_model=model_name, last_error=failed_result.error)
            return {"ok": False, "status": "failed", "task": record.to_dict(), "error": failed_result.error}

        record = self.state.update_task(task.task_id, status="failed", last_error="model_chain_exhausted")
        return {"ok": False, "status": "failed", "task": record.to_dict(), "error": "model_chain_exhausted"}

    def _is_non_escalatable_security_error(self, error: str) -> bool:
        text = str(error or "")
        return any(marker in text for marker in ("denied_command", "path_outside_workspace"))

    def _run_model_loop(
        self,
        *,
        task_id: str,
        model_name: str,
        prompt: str,
        context: Dict[str, Any],
        requires_filesystem: bool,
    ) -> Dict[str, Any]:
        adapter = self.adapters.get(model_name)
        if adapter is None:
            return {
                "ok": False,
                "model_result": ModelResult(ok=False, model=model_name, error="adapter_missing", finish_reason="configuration_required"),
                "tool_results": [],
                "steps": 0,
            }

        tool_results: List[Dict[str, Any]] = []
        max_steps = 8
        for step in range(1, max_steps + 1):
            result = adapter.execute(prompt, context, self.tool_specs())
            if not result.ok:
                return {"ok": False, "model_result": result, "tool_results": tool_results, "steps": step}

            if not result.tool_calls:
                if requires_filesystem and not tool_results:
                    missing = ModelResult(
                        ok=False,
                        model=model_name,
                        error="tool_calls_required_but_missing",
                        finish_reason="tool_calls_required",
                    )
                    return {"ok": False, "model_result": missing, "tool_results": tool_results, "steps": step}
                return {"ok": True, "model_result": result, "tool_results": tool_results, "steps": step}

            for call in result.tool_calls:
                tool_result = self.tools.execute_tool(call.name, call.arguments)
                checkpoint = self.state.append_checkpoint(
                    task_id,
                    call.name,
                    {"tool_call": call.to_dict(), "step": step},
                    tool_result,
                )
                item = {"tool_call": call.to_dict(), "result": tool_result, "step": step}
                context["checkpoints"].append(checkpoint)
                context["tool_results"].append(item)
                tool_results.append(item)
                if not tool_result.get("ok"):
                    failed = ModelResult(ok=False, model=model_name, error=str(tool_result), finish_reason="tool_error")
                    return {"ok": False, "model_result": failed, "tool_results": tool_results, "steps": step}

            if result.content.startswith("local fallback planned "):
                final = ModelResult(
                    ok=True,
                    model=model_name,
                    content="local fallback completed with real tool results",
                    tool_calls=[],
                    usage_tokens=result.usage_tokens,
                    finish_reason="stop",
                )
                return {"ok": True, "model_result": final, "tool_results": tool_results, "steps": step}

            prompt = (
                "Tool results are now available in context.tool_results. "
                "If the task is complete, answer with final content and no tool_calls. "
                "If more work is required, return the next tool_call only."
            )

        exhausted = ModelResult(ok=False, model=model_name, error="max_tool_steps_exhausted", finish_reason="max_steps")
        return {"ok": False, "model_result": exhausted, "tool_results": tool_results, "steps": max_steps}

    def _summarize_context(self, prompt: str, error: str, context: Dict[str, Any]) -> str:
        checkpoint_count = len(context.get("checkpoints") or [])
        transfer_count = len(context.get("transfers") or [])
        return (
            f"Prompt length={len(prompt)} chars. "
            f"Checkpoints={checkpoint_count}. Transfers={transfer_count}. "
            f"Last error={error[:500]}"
        )
