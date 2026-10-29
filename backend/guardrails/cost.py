"""Per-task token cost estimates, event-hook accounting, and circuit breaker."""
from __future__ import annotations

import json
import math
import threading
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
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
    """Extract usage from CrewAI's LLMCallCompletedEvent response payload."""
    response = _field(event, "response", "completion")
    usage = _field(event, "usage", "token_usage", "usage_metadata")
    if usage is None:
        usage = _field(response, "usage", "token_usage", "usage_metadata")
    if usage is None:
        usage = _field(response, "response", "completion")
    if usage is None:
        return None
    prompt = _field(usage, "prompt_tokens", "input_tokens", "prompt_token_count")
    completion = _field(usage, "completion_tokens", "output_tokens", "completion_token_count")
    if prompt is None or completion is None:
        nested = _field(usage, "usage", "token_usage")
        prompt = _field(nested, "prompt_tokens", "input_tokens")
        completion = _field(nested, "completion_tokens", "output_tokens")
    if prompt is None or completion is None:
        return None
    return max(0, int(prompt)), max(0, int(completion))


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
        # CrewAI 0.130.0's event bus catches handler exceptions. Do not rely on
        # this exception interrupting kickoff; _run_one checks after each stage.
        self.check_limit()
        return increment

    def add_event_usage(self, provider: str, event: Any) -> None:
        usage = _usage_from_event(event)
        if usage is not None and (usage[0] > 0 or usage[1] > 0):
            self.add_usage(provider, *usage)
            return
        prompt = _text(_field(event, "messages", "prompt", "input", "request"))
        if not prompt:
            prompt = _text(_field(event, "response", "completion"))
        completion = _text(_field(event, "response", "completion", "output", "result"))
        tokens_in = max(1, math.ceil(len(prompt) / 4))
        tokens_out = max(1, math.ceil(len(completion) / 4))
        self.add_usage(provider, tokens_in, tokens_out, estimated=True)

    def check_limit(self) -> None:
        if self.usd > self.limit_usd:
            raise CostLimitExceeded(
                f"Estimated cost ${self.usd:.6f} exceeded MAX_COST_USD_PER_TASK="
                f"${self.limit_usd:.6f}; task stopped."
            )


_ACTIVE_COST_CONTEXT: ContextVar[tuple[CostTracker, str, Callable[[dict], None] | None] | None] = ContextVar(
    "stephen_active_cost_context", default=None
)
_EVENT_SCOPE_LOCK = threading.RLock()


@contextmanager
def llm_cost_event_scope(
    tracker: CostTracker, provider: str, on_event: Callable[[dict], None] | None = None,
) -> Iterator[None]:
    """Account LLM events for the active task; serialize scopes for CrewAI 0.130's global bus."""
    try:
        from crewai.utilities.events import (
            LLMCallCompletedEvent,
            LLMCallStartedEvent,
            crewai_event_bus,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Installed CrewAI version lacks the required LLM event hooks "
            "(expected crewai.utilities.events for CrewAI 0.130.0)."
        ) from exc

    # CrewAI 0.130.0's event bus is global and scoped_handlers clears its handler
    # registry. Serialize these scopes so simultaneous tasks cannot mix usage or
    # temporarily erase one another's subscriptions.
    with _EVENT_SCOPE_LOCK:
        token = _ACTIVE_COST_CONTEXT.set((tracker, provider, on_event))
        try:
            with crewai_event_bus.scoped_handlers():
                @crewai_event_bus.on(LLMCallStartedEvent)
                def _before_llm_call(source: Any, event: Any) -> None:
                    active = _ACTIVE_COST_CONTEXT.get()
                    if active is not None:
                        active[0].check_limit()

                @crewai_event_bus.on(LLMCallCompletedEvent)
                def _after_llm_call(source: Any, event: Any) -> None:
                    active = _ACTIVE_COST_CONTEXT.get()
                    if active is not None:
                        active[0].add_event_usage(active[1], event)
                yield
        finally:
            _ACTIVE_COST_CONTEXT.reset(token)
