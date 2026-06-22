from __future__ import annotations

from .schemas import SwarmConfig


class CostGuardian:
    def __init__(self, config: SwarmConfig) -> None:
        self.config = config

    def estimate_cost_usd(self, model: str, estimated_tokens: int) -> float:
        if model in self.config.free_models:
            return 0.0
        rate_per_1k = {
            "deepseek": 0.002,
            "whale": 0.003,
            "codex": 0.004,
        }.get(model, 0.003)
        return round((max(1, estimated_tokens) / 1000.0) * rate_per_1k, 6)

    def requires_approval(self, model: str, estimated_tokens: int) -> bool:
        if model not in self.config.paid_models:
            return False
        return self.estimate_cost_usd(model, estimated_tokens) > self.config.max_cost_usd_without_approval
