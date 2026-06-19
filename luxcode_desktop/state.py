from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TERMINAL_STATUSES = {"completed", "failed", "blocked", "cancelled", "rejected", "rolled_back"}


@dataclass
class TaskState:
    task_id: str = ""
    session_id: str = ""
    status: str = "idle"
    workspace_mode: str = "sandbox_copy"
    main_repository_root: str = ""
    working_copy_root: str = ""
    sandbox_root: str = ""
    sync_status: str = "unknown"
    conflict_status: str = "unknown"
    active_engine: str = "-"
    active_model: str = "-"
    route_candidates: list[dict[str, Any]] = field(default_factory=list)
    real_attempts: list[dict[str, Any]] = field(default_factory=list)
    completed_work_units: list[dict[str, Any]] = field(default_factory=list)
    running_work_unit: dict[str, Any] | None = None
    remaining_work_units: list[dict[str, Any]] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    next_safe_action: str = ""
    progress_percent: int = 0
    sandbox_validation_status: str = "not_started"
    working_copy_validation_status: str = "not_started"
    main_validation_status: str = "not_started"
    safe_patch_status: str = "not_ready"
    approval_status: str = "none"
    integration_status: str = "not_started"
    rollback_status: str = "not_started"
    token_usage: str = "unavailable"
    provider_cost: str = "cost_status=unavailable"
    handoff_reason: str = "-"
    error: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TaskState":
        state = cls()

        for key in state.__dataclass_fields__:
            if key in payload:
                setattr(state, key, payload[key])

        state.task_id = str(payload.get("task_id") or payload.get("id") or state.task_id)
        state.session_id = str(payload.get("session_id") or state.session_id)
        state.status = str(
            payload.get("current_state")
            or payload.get("status")
            or payload.get("outcome")
            or state.status
        )

        state.next_safe_action = str(payload.get("next_safe_action") or state.next_safe_action)
        state.completed_steps = [
            str(item) for item in (payload.get("completed_steps") or state.completed_steps or [])
        ]
        state.pending_steps = [
            str(item) for item in (payload.get("pending_steps") or state.pending_steps or [])
        ]
        state.changed_files = [
            str(item) for item in (payload.get("changed_files") or state.changed_files or [])
        ]
        state.blocked_reasons = [
            str(item) for item in (payload.get("blocked_reasons") or state.blocked_reasons or [])
        ]

        if not payload.get("completed_work_units") and state.completed_steps:
            state.completed_work_units = [{"title": item} for item in state.completed_steps]

        if not payload.get("remaining_work_units") and state.pending_steps:
            state.remaining_work_units = [{"title": item} for item in state.pending_steps]

        if state.status == "completed":
            state.pending_steps = []
            state.remaining_work_units = []
            state.progress_percent = 100
        elif "progress_percent" not in payload:
            total = len(state.completed_steps) + len(state.pending_steps)
            state.progress_percent = round((len(state.completed_steps) / total) * 100) if total else 0

        zero_cost = payload.get("zero_cost_routing")
        if isinstance(zero_cost, dict):
            selected_engine = zero_cost.get("selected_engine")
            if selected_engine and str(selected_engine).lower() != "none":
                state.active_engine = str(selected_engine)

        approval_state = payload.get("approval_state")
        if isinstance(approval_state, dict):
            if approval_state.get("approved") is True:
                state.approval_status = "approved"
            elif state.status == "awaiting_approval":
                state.approval_status = "waiting"

        if state.status == "awaiting_approval":
            state.safe_patch_status = "ready_for_review"
        elif state.status == "completed" and not payload.get("patch_summary"):
            state.safe_patch_status = "not_required"

        return state

    @property
    def is_terminal(self) -> bool:
        return self.status.casefold() in TERMINAL_STATUSES
