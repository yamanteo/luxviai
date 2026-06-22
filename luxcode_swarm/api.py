from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .router import SwarmOrchestrator
from .schemas import SwarmConfig


class SwarmTaskRequest(BaseModel):
    prompt: str = Field(min_length=1)
    workspace_root: str | None = None
    folderPath: str | None = None
    selectedFolder: str | None = None


class ApprovalRequest(BaseModel):
    task_id: str = Field(min_length=1)


def build_swarm_router(workspace_root: str | Path) -> APIRouter:
    router = APIRouter(prefix="/luxcode-swarm", tags=["luxcode-swarm"])
    default_workspace = Path(workspace_root).resolve()

    @router.get("/status")
    def status() -> Dict[str, Any]:
        return {
            "ok": True,
            "service": "luxcode_swarm",
            "workspace_root": str(Path(workspace_root).resolve()),
            "routing": {
                "simple": ["ollama", "gemini", "cloud_models"],
                "medium": ["gemini", "cloud_models", "deepseek"],
                "hard": ["cloud_models", "deepseek", "whale"],
                "critical": ["deepseek", "whale", "codex"],
            },
        }

    @router.post("/tasks")
    def create_task(request: SwarmTaskRequest) -> Dict[str, Any]:
        requested_workspace = request.workspace_root or request.folderPath or request.selectedFolder
        active_workspace = Path(requested_workspace).expanduser().resolve() if requested_workspace else default_workspace
        if not active_workspace.is_dir():
            raise HTTPException(status_code=400, detail={"error": "workspace_not_found", "workspace_root": str(active_workspace)})
        orchestrator = SwarmOrchestrator(SwarmConfig(workspace_root=str(active_workspace)))
        return orchestrator.execute(request.prompt)

    @router.post("/approvals")
    def approve(request: ApprovalRequest) -> Dict[str, Any]:
        orchestrator = SwarmOrchestrator(SwarmConfig(workspace_root=str(default_workspace)))
        return orchestrator.state.approve_cost(request.task_id)

    return router
