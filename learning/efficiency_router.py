from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DRY_RUN_ROUTES = {
    "full_current_path",
    "short_technical_candidate",
    "emotional_full_context_needed",
    "dream_symbolic_needed",
    "count_constrained_needed",
    "crisis_safety_full_needed",
    "workspace_future_needed",
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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clamp_float(value: Any, lo: float = 0.0, hi: float = 1.0, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        x = default
    return max(lo, min(hi, x))


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _safety_level(analysis: dict[str, Any] | None, token_budget: dict[str, Any] | None) -> str:
    budget_level = str(_safe_dict(token_budget).get("safety_level", "") or "").strip().lower()
    if budget_level:
        return budget_level
    a = _safe_dict(analysis)
    safety = _safe_dict(a.get("safety_layer"))
    if a.get("crisis_risk") or safety.get("route_to_emergency"):
        return "crisis"
    if safety.get("needs_gentle_check") or safety.get("has_crisis_keyword"):
        return "sensitive"
    return str(safety.get("crisis_level", "normal") or "normal").strip().lower()


def _technical_candidate(text: str) -> bool:
    technical_terms = (
        "git status",
        "terminal",
        "cmd",
        "komut",
        "render",
        "deploy",
        "github",
        "push",
        "commit",
        "codex",
        "hata ne",
        "bug",
        "api",
        "fastapi",
        "python",
        "websocket",
        "log",
    )
    one_step_terms = (
        "tek adim",
        "simdi ne yapacagim",
        "simdi ne",
        "ilk adim",
        "one step",
        "ne yapayim",
    )
    return _contains_any(text, technical_terms) or _contains_any(text, one_step_terms)


def _long_generation(text: str) -> bool:
    return _contains_any(
        text,
        (
            "tez",
            "rapor",
            "sunum",
            "slayt",
            "makale",
            "cv yaz",
            "uzun",
            "taslak",
            "paragraf",
            "bolum",
            "liste",
        ),
    )


def _dream_context(text: str, mode: str, token_budget: dict[str, Any]) -> bool:
    if mode == "luxdream" or str(token_budget.get("budget_class", "")) == "dream_symbolic":
        return True
    return _contains_any(text, ("ruya", "ruyam", "dream"))


def _emotional_context(text: str, analysis: dict[str, Any], token_budget: dict[str, Any]) -> bool:
    if str(token_budget.get("budget_class", "")) == "emotional_support":
        return True
    if analysis.get("needs_presence") or _safe_int(analysis.get("intensity"), 0) >= 7:
        return True
    return _contains_any(
        text,
        (
            "cok kotu hissediyorum",
            "kotu hissediyorum",
            "yalnizim",
            "uzgunum",
            "bunaldim",
            "canim yaniyor",
            "iliski",
            "ayrilik",
        ),
    )


@dataclass(frozen=True)
class EfficiencyDryRunDecision:
    efficiency_dry_run_route: str = "full_current_path"
    would_use_short_context: bool = False
    would_limit_history_to_last_n: int = 18
    would_skip_group3: bool = False
    would_skip_group4: bool = False
    would_skip_long_memory: bool = False
    would_keep_safety: bool = True
    would_keep_identity_guard: bool = True
    would_keep_count_guard: bool = True
    estimated_context_savings_chars: int = 0
    estimated_layer_savings_count: int = 0
    router_confidence: float = 0.0
    route_reason: str = "default_full_current_path"
    mandatory_guards_kept: str = "safety,identity,count,basic_command,cost_logging"
    context_injected: bool = False
    active: bool = False
    version: str = "efficiency_router_dry_run_v1"

    def to_safe_dict(self) -> dict[str, Any]:
        route = self.efficiency_dry_run_route
        if route not in DRY_RUN_ROUTES:
            route = "full_current_path"
        return {
            "efficiency_dry_run_route": route,
            "would_use_short_context": bool(self.would_use_short_context),
            "would_limit_history_to_last_n": max(0, _safe_int(self.would_limit_history_to_last_n, 18)),
            "would_skip_group3": bool(self.would_skip_group3),
            "would_skip_group4": bool(self.would_skip_group4),
            "would_skip_long_memory": bool(self.would_skip_long_memory),
            "would_keep_safety": True,
            "would_keep_identity_guard": True,
            "would_keep_count_guard": True,
            "estimated_context_savings_chars": max(0, _safe_int(self.estimated_context_savings_chars, 0)),
            "estimated_layer_savings_count": max(0, _safe_int(self.estimated_layer_savings_count, 0)),
            "efficiency_dry_run_confidence": round(_clamp_float(self.router_confidence), 4),
            "route_reason": str(self.route_reason or "default_full_current_path")[:100],
            "mandatory_guards_kept": str(self.mandatory_guards_kept or "safety,identity,count,basic_command,cost_logging")[:120],
            "context_injected": False,
            "active": False,
            "version": self.version,
        }


@dataclass
class EfficiencyRouter:
    observe_only: bool = True

    def dry_run(
        self,
        *,
        message: str = "",
        mode: str = "luxviai",
        analysis: dict[str, Any] | None = None,
        token_budget: dict[str, Any] | None = None,
        count_constraints: list[Any] | None = None,
        identity_boundary: str = "",
        prompt_chars: int = 0,
        context_chars: int = 0,
        history_message_count: int = 0,
        history_chars: int = 0,
        context_item_count: int = 0,
        selected_layer_count: int = 0,
    ) -> EfficiencyDryRunDecision:
        text = _fold(message)
        mode = str(mode or "luxviai").strip().lower()
        analysis = _safe_dict(analysis)
        token_budget = _safe_dict(token_budget)
        constraints = _safe_list(count_constraints)
        safety_level = _safety_level(analysis, token_budget)
        identity_boundary = str(identity_boundary or "").strip().lower()
        history_count = max(0, _safe_int(history_message_count, 0))
        history_total_chars = max(0, _safe_int(history_chars, 0))
        context_total_chars = max(0, _safe_int(context_chars, 0))
        layers = max(0, _safe_int(selected_layer_count, 0))

        if safety_level in {"sensitive", "high_risk", "crisis"}:
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="crisis_safety_full_needed",
                router_confidence=0.96,
                route_reason="mandatory_safety_full_context",
            )
        if mode == "luxeph":
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="full_current_path",
                router_confidence=0.82,
                route_reason="luxeph_privacy_mode_no_short_path",
            )
        if identity_boundary in {"identity", "correction"}:
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="full_current_path",
                router_confidence=0.84,
                route_reason="identity_guard_caution",
            )
        if constraints:
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="count_constrained_needed",
                router_confidence=0.9,
                route_reason="count_format_guard_full_context",
            )
        if _dream_context(text, mode, token_budget):
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="dream_symbolic_needed",
                router_confidence=0.9,
                route_reason="dream_symbolic_context",
            )
        if _emotional_context(text, analysis, token_budget):
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="emotional_full_context_needed",
                router_confidence=0.86,
                route_reason="emotional_support_context_needed",
            )
        if _long_generation(text):
            route = "workspace_future_needed" if _contains_any(text, ("repo", "workspace", "dosya", "klasor")) else "full_current_path"
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route=route,
                router_confidence=0.78,
                route_reason="long_generation_or_workspace_needs_context",
            )

        short_candidate = _technical_candidate(text) and len(text.split()) <= 36
        if short_candidate:
            avg_history_chars = int(history_total_chars / max(1, history_count)) if history_count else 0
            saved_history = max(0, history_total_chars - (avg_history_chars * min(history_count, 3)))
            saved_context = max(0, context_total_chars - 280)
            layer_savings = min(layers, 4) if layers else min(max(0, _safe_int(context_item_count, 0)), 4)
            return EfficiencyDryRunDecision(
                efficiency_dry_run_route="short_technical_candidate",
                would_use_short_context=True,
                would_limit_history_to_last_n=3,
                would_skip_group3=True,
                would_skip_group4=True,
                would_skip_long_memory=True,
                estimated_context_savings_chars=saved_history + saved_context,
                estimated_layer_savings_count=layer_savings,
                router_confidence=0.78 if history_count or context_total_chars else 0.68,
                route_reason="short_technical_safe_path_candidate",
            )

        return EfficiencyDryRunDecision(
            efficiency_dry_run_route="full_current_path",
            router_confidence=0.62,
            route_reason="normal_chat_keep_current_path",
        )


def neutral_efficiency_dry_run() -> dict[str, Any]:
    return EfficiencyDryRunDecision().to_safe_dict()
