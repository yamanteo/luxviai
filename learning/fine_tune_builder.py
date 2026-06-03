from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import append_jsonl, ensure_dir


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_text(value: Any) -> str:
    text = str(value or "")
    # Basic privacy scrubbing for exported fine-tune candidates.
    text = re.sub(r"https?://\S+", "[link]", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"\buser_[a-z0-9_]+\b", "[user]", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{8,}\b", "[number]", text)
    return text.strip()


SENSITIVE_BLOCK_PATTERNS: tuple[str, ...] = (
    "taciz",
    "tecavuz",
    "istismar",
    "aile ici siddet",
    "kendime zarar",
    "intihar",
    "oldurecegim",
    "zarar verecegim",
    "kumar",
    "bagimlilik",
)


def _sanitize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    out = dict(candidate)
    messages = out.get("messages", [])
    if isinstance(messages, list):
        clean_messages: list[dict[str, Any]] = []
        for m in messages:
            if not isinstance(m, dict):
                continue
            clean_messages.append(
                {
                    "role": str(m.get("role", "")).strip(),
                    "content": _sanitize_text(m.get("content")),
                }
            )
        out["messages"] = clean_messages
    meta = out.get("meta", {})
    if isinstance(meta, dict):
        clean_meta = {}
        for k, v in meta.items():
            if isinstance(v, str):
                clean_meta[k] = _sanitize_text(v)
            elif isinstance(v, list):
                clean_meta[k] = [str(x).strip() for x in v[:20]]
            else:
                clean_meta[k] = v
        out["meta"] = clean_meta
    return out


def _candidate_signature(row: dict[str, Any]) -> str:
    messages = row.get("messages", [])
    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for m in messages[:2]:
        if not isinstance(m, dict):
            continue
        parts.append(f"{m.get('role','')}::{str(m.get('content','')).strip()[:500]}")
    return "|".join(parts).strip().lower()


def _contains_sensitive_content(candidate: dict[str, Any]) -> bool:
    messages = candidate.get("messages", [])
    if not isinstance(messages, list):
        return False
    merged = " ".join(str((m or {}).get("content", "")) for m in messages if isinstance(m, dict)).lower()
    return any(p in merged for p in SENSITIVE_BLOCK_PATTERNS)


@dataclass
class FineTuneCandidateStore:
    base_dir: Path

    @property
    def global_dir(self) -> Path:
        return self.base_dir / "data" / "global"

    @property
    def fine_path(self) -> Path:
        return self.global_dir / "fine_tune_candidates.jsonl"

    @property
    def elite_path(self) -> Path:
        return self.global_dir / "elite_candidates.jsonl"

    @property
    def pending_path(self) -> Path:
        return self.global_dir / "pending_candidates.jsonl"

    @property
    def rejected_path(self) -> Path:
        return self.global_dir / "rejected_candidates.jsonl"

    def ensure_files(self) -> None:
        ensure_dir(self.global_dir)
        for p in [self.fine_path, self.elite_path, self.pending_path, self.rejected_path]:
            if not p.exists():
                p.write_text("", encoding="utf-8")

    def _is_recent_duplicate(self, signature: str, limit: int = 50) -> bool:
        if not signature or not self.fine_path.exists():
            return False
        try:
            tail: deque[str] = deque(maxlen=max(1, limit))
            with self.fine_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        tail.append(line)
            for ln in tail:
                try:
                    row = json.loads(ln)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                if _candidate_signature(row) == signature:
                    return True
        except Exception:
            return False
        return False

    def add_candidate(self, candidate: dict[str, Any], score: float) -> None:
        clean = _sanitize_candidate(candidate if isinstance(candidate, dict) else {})
        if _contains_sensitive_content(clean):
            append_jsonl(
                self.rejected_path,
                {
                    "created_at": now_iso(),
                    "score": round(float(score), 4),
                    "reason": "sensitive_content_blocked",
                },
            )
            return
        signature = _candidate_signature(clean)
        if self._is_recent_duplicate(signature):
            return
        row = {
            "created_at": now_iso(),
            "score": round(float(score), 4),
            **clean,
        }
        append_jsonl(self.fine_path, row)
        if score >= 0.95:
            append_jsonl(self.elite_path, row)
        elif score >= 0.85:
            append_jsonl(self.pending_path, row)
        else:
            append_jsonl(self.rejected_path, row)
