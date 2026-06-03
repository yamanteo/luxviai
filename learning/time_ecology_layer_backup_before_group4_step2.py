from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .group4_signals import TimeEcologySignal


def _time_of_day_bucket(now: datetime) -> str:
    h = int(now.hour)
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "day"
    if 18 <= h < 23:
        return "evening"
    return "night"


@dataclass(slots=True)
class TimeEcologyLayerEngine:
    def extract_time_ecology_signal(
        self,
        message: str,
        analysis: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
    ) -> TimeEcologySignal:
        _ = message, analysis, profile, session
        now_local = datetime.now()
        return TimeEcologySignal(
            time_of_day_bucket=_time_of_day_bucket(now_local),
            rhythm_bucket="unknown",
            fatigue_context_bucket="unknown",
            urgency_bucket="low",
            safe_summary="time_ecology_stub_signal",
            confidence=0.2,
            risk_flags=[],
        )


def extract_time_ecology_signal(
    message: str,
    analysis: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> TimeEcologySignal:
    return TimeEcologyLayerEngine().extract_time_ecology_signal(message, analysis, profile, session)

