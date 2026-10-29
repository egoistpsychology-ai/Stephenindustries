"""Per-task token cost estimates, event-hook accounting, and circuit breaker."""
from __future__ import annotations

import json
import math
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from backend.config import Settings, settings


class CostLimitExceeded(RuntimeError):
    """Raised when estimated task spend exceeds the configured budget."""


def _field(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and obj.get(name) is not None:
            return obj[name]
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _usage_from_event(event: Any) -> tuple[int, int] | None:
    """Extract usage from common CrewAI/provider event shapes, if present."""
    for usage in (_field(event, "usage", "token_usage", "usage_metadata"),
                  _field(event, "response", "completion")):
        if usage is None:
            continue
        prompt = _field(usage, "prompt_tokens", "input_tokens", "prompt_token_count")
        completion = _field(usage, "completion_tokens", "output_tokens", "completion_token_count")
        if prompt is not None and completion is not None:
            return max(0, int(prompt)), max(0, int(completion))
        nested = _field(usage, "usage", "token_usage")
        if nested is not None:
            prompt = _field(nested, "prompt_tokens", "input_tokens")
            completion = _field(nested, "completion_tokens", "output_tokens")
            if prompt is not None and completion is not None:
                return max(0, int(prompt)), max(0, int(completion))
    return None


@dataclass
class CostTracker:
    task_id: str
    limit_usd: float
    settings: Settings = settings
    on_cost: Callable[[dict], None] | None = None
    on_warning: Callable[[str], None] | None = None
    usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    def add_usage(self, provider: str, tokens_in: int, tokens_out: int, *, estimated: bool = False) -> float:
        tokens_in = max(0, int(tokens_in or 0))
        tokens_out = max(0, int(tokens_out or 0))
        if provider == "groq":
            in_rate = self.settings.groq_input_usd_per_million
            out_rate = self.settings.groq_output_usd_per_million
        else:
            in_rate = self.settings.deepseek_input_usd_per_million
            out_rate = self.settings.deepseek_output_usd_per_million
        increment = (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.usd += increment
        if estimated:
            message = "CrewAI/provider token usage missing; estimated tokens from text length. Cost is approximate."
            warnings.warn(message, RuntimeWarning, stacklevel=2)
            if self.on_warning:
                self.on_warning(message)
        if self.on_cost:
            self.on_cost({
                "type": "cost", "task_id": self.task_id, "usd": round(self.usd, 8),
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
            })
        self.check_limit()
        return increment

    def add_event_usage(self, provider: str, event: Any) -> None:
        usage = _usage_from_event(event)
        if usage is not None and (usage[0] > 0 or usage[1] > 0):
            self.add_usage(provider, *usage)
            return
        prompt = _text(_field(event, "messages", "prompt", "input", "request"))
        completion = _text(_field(event, "response", "completion", "output", "result"))
        # Use a non-zero minimum estimate if a provider omits usage and text fields.
        tokens_in = max(1, math.ceil(len(prompt) / 4))
        tokens_out = max(1, math.ceil(len(completion) / 4))
        self.add_usage(provider, tokens_in, tokens_out, estimated=True)

    def check_limit(self) -> None:
        if self.usd > self.limit_usd:
            raise CostLimitExceeded(
                f"Estimated cost ${self.usd:.6f} exceeded MAX_COST_USD_PER_TASK="
                f"${self.limit_usd:.6f}; task stopped."
            )


@contextmanager
def llm_cost_event_scope(
    tracker: CostTracker, provider: str, on_event: Callable[[dict], None] | None = None,
) -> Iterator[None]:
    """Account every LLMCallCompletedEvent in a scoped CrewAI event-bus subscription."""
    try:
        from crewai.events import LLMCallCompletedEvent, LLMCallStartedEvent, crewai_event_bus
    except ImportError as exc:
        raise RuntimeError("Installed CrewAI version lacks the required LLM event hooks.") from exc

    with crewai_event_bus.scoped_handlers():
        @crewai_event_bus.on(LLMCallStartedEvent)
        def _before_llm_call(source: Any, event: Any) -> None:
            tracker.check_limit()

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def _after_llm_call(source: Any, event: Any) -> None:
            # Propagate the breaker exception through the synchronous event bus so
            # CrewAI stops processing this kickoff instead of starting another call.
            tracker.add_event_usage(provider, event)
        yield
