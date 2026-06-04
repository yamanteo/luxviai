from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BUDGET_CLASSES = {
    "short_technical",
    "normal_chat",
    "emotional_support",
    "dream_symbolic",
    "long_generation",
    "count_constrained",
    "crisis_safety",
    "workspace_future",
}


def _fold(value: str) -> str:
    table = str.maketrans(
        {
            "ç": "c",
            "Ç": "c",
            "ğ": "g",
            "Ğ": "g",
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "Ö": "o",
            "ş": "s",
            "Ş": "s",
            "ü": "u",
            "Ü": "u",
        }
    )
    return str(value or "").translate(table).lower()


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _safety_level(analysis: dict[str, Any] | None) -> str:
    a = _safe_dict(analysis)
    safety = _safe_dict(a.get("safety_layer"))
    if a.get("crisis_risk") or safety.get("route_to_emergency"):
        return "crisis"
    if safety.get("needs_gentle_check") or safety.get("has_crisis_keyword"):
        return "sensitive"
    level = str(safety.get("crisis_level", "normal") or "normal").strip().lower()
    return level or "normal"


def _task_type(message: str, mode: str, analysis: dict[str, Any] | None, count_constraints: list[Any]) -> str:
    text = _fold(message)
    a = _safe_dict(analysis)
    if _safety_level(a) in {"sensitive", "high_risk", "crisis"}:
        return "safety"
    if count_constraints:
        return "count_format"
    if mode == "luxdream" or _contains_any(text, ("ruya", "ruyam", "dream")):
        return "dream"
    if _contains_any(text, ("tez", "rapor", "sunum", "slayt", "makale", "uzun", "taslak")):
        return "long_generation"
    if _contains_any(text, ("codex", "render", "github", "terminal", "hata", "bug", "deploy", "api", "fastapi", "python", "websocket")):
        return "technical"
    if a.get("needs_presence") or a.get("intensity", 0) >= 7:
        return "emotional_support"
    return "chat"


@dataclass(frozen=True)
class TokenBudgetDecision:
    budget_class: str = "normal_chat"
    observe_only: bool = True
    active: bool = False
    route_reason: str = "default"
    task_type: str = "chat"
    safety_level: str = "normal"
    count_constraint_present: bool = False
    cache_hint: str = "none"
    version: str = "token_budget_policy_v1"

    def to_safe_dict(self) -> dict[str, Any]:
        budget_class = self.budget_class if self.budget_class in BUDGET_CLASSES else "normal_chat"
        return {
            "budget_class": budget_class,
            "observe_only": True,
            "active": False,
            "route_reason": str(self.route_reason or "default")[:80],
            "task_type": str(self.task_type or "chat")[:60],
            "safety_level": str(self.safety_level or "normal")[:40],
            "count_constraint_present": bool(self.count_constraint_present),
            "cache_hint": str(self.cache_hint or "none")[:60],
            "version": self.version,
        }


@dataclass
class TokenBudgetPolicy:
    observe_only: bool = True

    def classify(
        self,
        *,
        message: str = "",
        mode: str = "luxviai",
        analysis: dict[str, Any] | None = None,
        count_constraints: list[Any] | None = None,
    ) -> TokenBudgetDecision:
        constraints = _safe_list(count_constraints)
        task_type = _task_type(message, mode, analysis, constraints)
        safety_level = _safety_level(analysis)
        text = _fold(message)

        if safety_level in {"sensitive", "high_risk", "crisis"}:
            budget_class = "crisis_safety"
            reason = "safety_signal"
        elif constraints:
            budget_class = "count_constrained"
            reason = "explicit_count_or_format"
        elif task_type == "technical" and len(text.split()) <= 28:
            budget_class = "short_technical"
            reason = "short_technical_intent"
        elif task_type == "dream":
            budget_class = "dream_symbolic"
            reason = "dream_or_symbolic_context"
        elif task_type == "long_generation":
            budget_class = "long_generation"
            reason = "long_generation_request"
        elif task_type == "emotional_support":
            budget_class = "emotional_support"
            reason = "emotional_support_signal"
        elif _contains_any(text, ("workspace", "dosya", "repo", "proje klasoru")):
            budget_class = "workspace_future"
            reason = "workspace_future_candidate"
        else:
            budget_class = "normal_chat"
            reason = "normal_chat_default"

        return TokenBudgetDecision(
            budget_class=budget_class,
            observe_only=True,
            active=False,
            route_reason=reason,
            task_type=task_type,
            safety_level=safety_level,
            count_constraint_present=bool(constraints),
            cache_hint="static_prompt_candidate" if budget_class in {"short_technical", "normal_chat"} else "none",
        )


def neutral_token_budget_decision() -> dict[str, Any]:
    return TokenBudgetDecision().to_safe_dict()
