"""Per-task token cost estimates and post-call circuit breaker."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from backend.config import Settings, settings

class CostLimitExceeded(RuntimeError):
    """Raised when estimated task spend exceeds the configured budget."""

@dataclass
class CostTracker:
    task_id: str
    limit_usd: float
    settings: Settings = settings
    on_cost: Callable[[dict], None] | None = None
    usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    def add_usage(self, provider: str, tokens_in: int, tokens_out: int) -> float:
        tokens_in, tokens_out = max(0, int(tokens_in or 0)), max(0, int(tokens_out or 0))
        if provider == "groq":
            in_rate, out_rate = self.settings.groq_input_usd_per_million, self.settings.groq_output_usd_per_million
        else:
            in_rate, out_rate = self.settings.deepseek_input_usd_per_million, self.settings.deepseek_output_usd_per_million
        increment = (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.usd += increment
        if self.on_cost:
            self.on_cost({"type":"cost","task_id":self.task_id,"usd":round(self.usd, 8),
                          "tokens_in":self.tokens_in,"tokens_out":self.tokens_out})
        self.check_limit()
        return increment

    def check_limit(self) -> None:
        # CrewAI exposes usage after a completion; this prevents later calls but cannot
        # cancel/refund an API request that is already in flight.
        if self.usd > self.limit_usd:
            raise CostLimitExceeded(
                f"Estimated cost ${self.usd:.6f} exceeded MAX_COST_USD_PER_TASK="
                f"${self.limit_usd:.6f}; task stopped."
            )
