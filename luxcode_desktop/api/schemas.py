from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskSubmitPayload:
    task_summary: str
    main_repository_root: str
    working_copy_root: str = ""
    sandbox_root: str = ""
    workspace_mode: str = "sandbox_copy"
    selected_files: list[str] = field(default_factory=list)
    target_files: list[str] = field(default_factory=list)
    allowed_files: list[str] = field(default_factory=list)
    suspected_files: list[str] = field(default_factory=list)
    excluded_paths: list[str] = field(default_factory=list)
    pilot_mode: bool = True
    local_worker_enabled: bool = True
    free_gemini_enabled: bool = True
    free_cloud_enabled: bool = True
    live_external_enabled: bool = False
    paid_escalation_allowed: bool = False
    auto_apply: bool = False
    execution_mode: str = "automatic"
    access_level: str = "controlled"
    allowed_engines: list[str] = field(default_factory=list)
    engine_configurations: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[dict[str, str]] = field(default_factory=list)
    budget_limit: float | None = None
    call_limit: int | None = None
    time_limit_seconds: int | None = None
    sync_before_task: bool = True
    validate_in_sandbox: bool = True
    validate_in_working_copy: bool = True
    validate_in_main: bool = True

    def to_backend_payload(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["repository_root"] = self.main_repository_root
        return payload
