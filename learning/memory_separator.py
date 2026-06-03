from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MemorySeparator:
    """Aşama-1 iskelet: kişisel ve global çıkarımları ayırır."""

    def split(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "personal": {
                "theme": payload.get("theme"),
                "micro_signals": payload.get("micro_signals", {}),
            },
            "global": {
                "theme": payload.get("theme"),
                "recommendation": payload.get("recommendation"),
            },
        }
