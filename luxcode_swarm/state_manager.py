from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .schemas import TaskClassification, TaskRecord, utc_now


class JsonStateManager:
    """Durable local state manager with atomic JSON writes.

    This is the local persistence implementation for development and desktop
    use. Its API is intentionally database-shaped so a PostgreSQL backend can
    replace it without changing orchestrator logic.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.tasks_dir = self.root / "tasks"
        self.checkpoints_dir = self.root / "checkpoints"
        self.transfers_dir = self.root / "transfers"
        self.approvals_dir = self.root / "approvals"
        self._lock = threading.Lock()
        for folder in (self.tasks_dir, self.checkpoints_dir, self.transfers_dir, self.approvals_dir):
            folder.mkdir(parents=True, exist_ok=True)

    def _atomic_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def create_task(self, prompt: str, classification: TaskClassification, initial_model: str) -> TaskRecord:
        task_id = f"swarm-{uuid.uuid4().hex}"
        now = utc_now()
        record = TaskRecord(
            task_id=task_id,
            prompt=prompt,
            status="created",
            current_model=initial_model,
            classification=classification.to_dict(),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._atomic_json(self._task_path(task_id), record.to_dict())
        return record

    def load_task(self, task_id: str) -> TaskRecord:
        path = self._task_path(task_id)
        if not path.is_file():
            raise KeyError(f"task_not_found:{task_id}")
        return TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def update_task(self, task_id: str, **updates: Any) -> TaskRecord:
        with self._lock:
            current = self.load_task(task_id).to_dict()
            current.update(updates)
            current["updated_at"] = utc_now()
            record = TaskRecord.from_dict(current)
            self._atomic_json(self._task_path(task_id), record.to_dict())
            return record

    def append_checkpoint(
        self,
        task_id: str,
        action_type: str,
        payload: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        checkpoints = self.list_checkpoints(task_id)
        item = {
            "task_id": task_id,
            "step_number": len(checkpoints) + 1,
            "action_type": action_type,
            "payload": payload,
            "result": result,
            "timestamp": utc_now(),
        }
        path = self.checkpoints_dir / task_id / f"{item['step_number']:04d}.json"
        with self._lock:
            self._atomic_json(path, item)
        record = self.load_task(task_id)
        steps = list(record.completed_steps)
        steps.append(f"{action_type}:{item['step_number']}")
        self.update_task(task_id, completed_steps=steps)
        return item

    def list_checkpoints(self, task_id: str) -> List[Dict[str, Any]]:
        folder = self.checkpoints_dir / task_id
        if not folder.is_dir():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(folder.glob("*.json"))
        ]

    def record_transfer(
        self,
        task_id: str,
        from_model: str,
        to_model: str,
        transfer_reason: str,
        context_summary: str,
    ) -> Dict[str, Any]:
        transfers = self.list_transfers(task_id)
        item = {
            "task_id": task_id,
            "step_number": len(transfers) + 1,
            "from_model": from_model,
            "to_model": to_model,
            "transfer_reason": transfer_reason,
            "context_summary": context_summary,
            "timestamp": utc_now(),
        }
        path = self.transfers_dir / task_id / f"{item['step_number']:04d}.json"
        with self._lock:
            self._atomic_json(path, item)
        return item

    def list_transfers(self, task_id: str) -> List[Dict[str, Any]]:
        folder = self.transfers_dir / task_id
        if not folder.is_dir():
            return []
        return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.json"))]

    def create_approval_request(self, task_id: str, model: str, estimated_cost_usd: float) -> Dict[str, Any]:
        item = {
            "task_id": task_id,
            "model": model,
            "estimated_cost_usd": estimated_cost_usd,
            "status": "pending",
            "created_at": utc_now(),
            "approved_at": "",
        }
        with self._lock:
            self._atomic_json(self.approvals_dir / f"{task_id}.json", item)
        self.update_task(
            task_id,
            status="awaiting_cost_approval",
            approval_required=True,
            estimated_cost_usd=estimated_cost_usd,
            current_model=model,
        )
        return item

    def approve_cost(self, task_id: str) -> Dict[str, Any]:
        path = self.approvals_dir / f"{task_id}.json"
        if not path.is_file():
            raise KeyError(f"approval_not_found:{task_id}")
        item = json.loads(path.read_text(encoding="utf-8"))
        item["status"] = "approved"
        item["approved_at"] = utc_now()
        with self._lock:
            self._atomic_json(path, item)
        self.update_task(task_id, approval_granted=True)
        return item
