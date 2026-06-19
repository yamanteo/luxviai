from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from luxcode_runtime_settings import get_runtime_status

from luxcode_control_analytics import (
    build_analytics_summary,
    build_engine_performance,
    build_savings_report,
    get_control_analytics_schema,
    get_handoff_trace,
    get_session_analytics,
)
from luxcode_control_center import (
    approval_center,
    control_context,
    control_search,
    control_task_plan,
    controlled_apply_execute,
    controlled_apply_prepare,
    deferred_queue,
    deferred_resume,
    evidence_board as control_evidence_board,
    get_control_center_schema,
    get_control_center_status,
    get_control_session,
    list_control_sessions,
    motor_status as control_motor_status,
    repository_diagnostics as control_repository_diagnostics,
    rollback_snapshot as control_rollback_snapshot,
    run_first_usable_task,
    safe_patch_approval,
    safe_patch_preview as control_safe_patch_preview,
    safe_settings as control_safe_settings,
    validation_run as control_validation_run,
    working_copy_prepare,
    sandbox_prepare,
    integration_prepare,
    integration_execute,
    integration_rollback,
    workspace_services_status,
)


def build_luxcode_control_router(base_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/luxcode-control")

    def repo_root(repository_root: Optional[str]) -> str:
        return repository_root or str(base_dir)

    @router.get("/schema")
    async def luxcode_control_schema_endpoint():
        return get_control_center_schema()

    @router.get("/status")
    async def luxcode_control_status_endpoint(repository_root: Optional[str] = None):
        return get_control_center_status(repo_root(repository_root))

    @router.get("/sessions")
    async def luxcode_control_sessions_endpoint(repository_root: Optional[str] = None):
        return list_control_sessions(repo_root(repository_root))

    @router.get("/sessions/{session_id}")
    async def luxcode_control_session_endpoint(session_id: str, repository_root: Optional[str] = None):
        return get_control_session(session_id, repo_root(repository_root))

    @router.post("/first-usable/run")
    async def luxcode_control_first_usable_run_endpoint(payload: Dict[str, Any]):
        return run_first_usable_task(payload, repo_root(payload.get("repository_root")))

    @router.post("/repository/diagnostics")
    async def luxcode_control_repository_diagnostics_endpoint(payload: Dict[str, Any]):
        return control_repository_diagnostics(payload, repo_root(payload.get("repository_root")))

    @router.post("/search")
    async def luxcode_control_search_endpoint(payload: Dict[str, Any]):
        return control_search(payload, repo_root(payload.get("repository_root")))

    @router.post("/context")
    async def luxcode_control_context_endpoint(payload: Dict[str, Any]):
        return control_context(payload, repo_root(payload.get("repository_root")))

    @router.post("/task-plan")
    async def luxcode_control_task_plan_endpoint(payload: Dict[str, Any]):
        return control_task_plan(payload, repo_root(payload.get("repository_root")))

    @router.post("/safe-patch/preview")
    async def luxcode_control_safe_patch_preview_endpoint(payload: Dict[str, Any]):
        return control_safe_patch_preview(payload, repo_root(payload.get("repository_root")))

    @router.post("/safe-patch/approval")
    async def luxcode_control_safe_patch_approval_endpoint(payload: Dict[str, Any]):
        return safe_patch_approval(payload)

    @router.post("/controlled-apply/prepare")
    async def luxcode_control_controlled_apply_prepare_endpoint(payload: Dict[str, Any]):
        return controlled_apply_prepare(payload)

    @router.post("/controlled-apply/execute")
    async def luxcode_control_controlled_apply_execute_endpoint(payload: Dict[str, Any]):
        return controlled_apply_execute(payload)

    @router.post("/validation/run")
    async def luxcode_control_validation_run_endpoint(payload: Dict[str, Any]):
        return control_validation_run(payload, repo_root(payload.get("repository_root")))

    @router.post("/rollback")
    async def luxcode_control_rollback_endpoint(payload: Dict[str, Any]):
        return control_rollback_snapshot(payload)

    @router.get("/evidence-board")
    async def luxcode_control_evidence_board_endpoint(task_id: Optional[str] = None):
        return control_evidence_board(task_id or "")

    @router.get("/deferred-queue")
    async def luxcode_control_deferred_queue_endpoint(repository_root: Optional[str] = None):
        return deferred_queue(repo_root(repository_root))

    @router.post("/deferred-queue/resume")
    async def luxcode_control_deferred_resume_endpoint(payload: Dict[str, Any]):
        return deferred_resume(payload, repo_root(payload.get("repository_root")))

    @router.get("/approvals")
    async def luxcode_control_approvals_endpoint(repository_root: Optional[str] = None):
        return approval_center(repo_root(repository_root))

    @router.get("/motor-status")
    async def luxcode_control_motor_status_endpoint(repository_root: Optional[str] = None):
        return control_motor_status(repo_root(repository_root))

    @router.get("/settings")
    async def luxcode_control_settings_endpoint():
        return control_safe_settings()

    @router.get("/runtime-status")
    async def luxcode_control_runtime_status_endpoint():
        return get_runtime_status(base_dir)

    @router.get("/workspace-services/status")
    async def luxcode_control_workspace_services_status_endpoint():
        return workspace_services_status()

    @router.post("/working-copy/prepare")
    async def luxcode_control_working_copy_prepare_endpoint(
        payload: Dict[str, Any],
    ):
        return working_copy_prepare(
            payload,
            repo_root(payload.get("repository_root")),
        )

    @router.post("/sandbox/prepare")
    async def luxcode_control_sandbox_prepare_endpoint(
        payload: Dict[str, Any],
    ):
        return sandbox_prepare(
            payload,
            repo_root(payload.get("repository_root")),
        )

    @router.post("/integration/prepare")
    async def luxcode_control_integration_prepare_endpoint(
        payload: Dict[str, Any],
    ):
        return integration_prepare(
            payload,
            repo_root(payload.get("repository_root")),
        )

    @router.post("/integration/execute")
    async def luxcode_control_integration_execute_endpoint(
        payload: Dict[str, Any],
    ):
        return integration_execute(payload)

    @router.post("/integration/rollback")
    async def luxcode_control_integration_rollback_endpoint(
        payload: Dict[str, Any],
    ):
        return integration_rollback(payload)

    @router.get("/analytics/schema")
    async def luxcode_control_analytics_schema_endpoint():
        return get_control_analytics_schema()

    @router.get("/analytics/summary")
    async def luxcode_control_analytics_summary_endpoint(
        repository_root: Optional[str] = None,
        from_: Optional[str] = Query(default=None, alias="from"),
        to: Optional[str] = None,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
    ):
        return build_analytics_summary(repo_root(repository_root), from_=from_ or "", to=to or "", engine=engine or "", model=model or "", status=status or "")

    @router.get("/analytics/engines")
    async def luxcode_control_analytics_engines_endpoint(
        repository_root: Optional[str] = None,
        from_: Optional[str] = Query(default=None, alias="from"),
        to: Optional[str] = None,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
    ):
        return build_engine_performance(repo_root(repository_root), from_=from_ or "", to=to or "", engine=engine or "", model=model or "", status=status or "")

    @router.get("/analytics/sessions/{session_id}")
    async def luxcode_control_analytics_session_endpoint(session_id: str, repository_root: Optional[str] = None):
        return get_session_analytics(session_id, repo_root(repository_root))

    @router.get("/analytics/savings")
    async def luxcode_control_analytics_savings_endpoint(
        repository_root: Optional[str] = None,
        from_: Optional[str] = Query(default=None, alias="from"),
        to: Optional[str] = None,
        engine: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
    ):
        return build_savings_report(repo_root(repository_root), from_=from_ or "", to=to or "", engine=engine or "", model=model or "", status=status or "")

    @router.get("/analytics/handoffs/{session_id}")
    async def luxcode_control_analytics_handoffs_endpoint(session_id: str, repository_root: Optional[str] = None):
        return get_handoff_trace(session_id, repo_root(repository_root))

    return router
