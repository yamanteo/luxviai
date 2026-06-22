from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TaskClassification:
    complexity: int
    estimated_tokens: int
    requires_filesystem: bool
    requires_web: bool
    reason: str = ""

    def normalized(self) -> "TaskClassification":
        complexity = max(1, min(10, int(self.complexity)))
        tokens = max(1, int(self.estimated_tokens))
        return TaskClassification(
            complexity=complexity,
            estimated_tokens=tokens,
            requires_filesystem=bool(self.requires_filesystem),
            requires_web=bool(self.requires_web),
            reason=str(self.reason or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        item = self.normalized()
        return {
            "complexity": item.complexity,
            "estimated_tokens": item.estimated_tokens,
            "requires_filesystem": item.requires_filesystem,
            "requires_web": item.requires_web,
            "reason": item.reason,
        }


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


@dataclass
class ModelResult:
    ok: bool
    model: str
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage_tokens: int = 0
    finish_reason: str = "stop"
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "model": self.model,
            "content": self.content,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "usage_tokens": self.usage_tokens,
            "finish_reason": self.finish_reason,
            "error": self.error,
        }


@dataclass(frozen=True)
class SwarmConfig:
    workspace_root: str
    state_root: str = ".luxcode_runtime/swarm_state"
    free_models: tuple[str, ...] = ("ollama", "gemini", "cloud_models")
    paid_models: tuple[str, ...] = ("deepseek", "whale", "codex")
    max_retries_per_model: int = 2
    command_timeout_seconds: int = 30
    max_cost_usd_without_approval: float = 0.0


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    prompt: str
    status: str
    current_model: str
    classification: Dict[str, Any]
    created_at: str
    updated_at: str
    approval_required: bool = False
    approval_granted: bool = False
    estimated_cost_usd: float = 0.0
    completed_steps: tuple[str, ...] = ()
    last_error: str = ""
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "status": self.status,
            "current_model": self.current_model,
            "classification": self.classification,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approval_required": self.approval_required,
            "approval_granted": self.approval_granted,
            "estimated_cost_usd": self.estimated_cost_usd,
            "completed_steps": list(self.completed_steps),
            "last_error": self.last_error,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TaskRecord":
        return cls(
            task_id=str(payload["task_id"]),
            prompt=str(payload["prompt"]),
            status=str(payload["status"]),
            current_model=str(payload.get("current_model") or ""),
            classification=dict(payload.get("classification") or {}),
            created_at=str(payload.get("created_at") or utc_now()),
            updated_at=str(payload.get("updated_at") or utc_now()),
            approval_required=bool(payload.get("approval_required")),
            approval_granted=bool(payload.get("approval_granted")),
            estimated_cost_usd=float(payload.get("estimated_cost_usd") or 0.0),
            completed_steps=tuple(str(item) for item in payload.get("completed_steps") or []),
            last_error=str(payload.get("last_error") or ""),
            result=payload.get("result"),
        )
