"""CrewAI agents and bounded manager-first orchestration; no tools in Phase 1."""
from __future__ import annotations
import json
import re
import uuid
from dataclasses import dataclass
from typing import Callable
from crewai import Agent, Crew, LLM, Process, Task
from backend.config import Settings, settings
from backend.guardrails.cost import CostTracker
from backend.guardrails.delegation import DelegationCounter

StatusCallback = Callable[[dict], None]

class MissingAPIKeyError(RuntimeError):
    """Raised if the required provider API key is absent."""

@dataclass
class TaskResult:
    task_id: str
    answer: str
    cost_usd: float
    tokens_in: int
    tokens_out: int

def _llm(provider: str, config: Settings) -> LLM:
    if provider == "groq":
        if not config.groq_api_key:
            raise MissingAPIKeyError("GROQ_API_KEY is not set; copy .env.example to .env.")
        return LLM(model="groq/llama-3.3-70b-versatile", api_key=config.groq_api_key)
    if not config.deepseek_api_key:
        raise MissingAPIKeyError("DEEPSEEK_API_KEY is not set; copy .env.example to .env.")
    return LLM(model="deepseek/deepseek-chat", api_key=config.deepseek_api_key,
               base_url="https://api.deepseek.com")

def build_agents(config: Settings = settings) -> tuple[Agent, Agent, Agent]:
    stephen = Agent(
        role="Engineering Manager",
        goal="Plan backend and frontend work, then review the results.",
        backstory="You are Stephen. You never write code. You make the initial assignments and review output.",
        llm=_llm("groq", config), allow_delegation=False, verbose=False,
        respect_context_window=True,
    )
    seer = Agent(
        role="Backend Engineer", goal="Analyze backend requirements, interfaces, and server-side design.",
        backstory="You are Seer. In Phase 1, provide analysis only.",
        llm=_llm("deepseek", config), allow_delegation=False, verbose=False,
        respect_context_window=True,
    )
    escanor = Agent(
        role="Frontend Engineer", goal="Analyze frontend layout, accessibility, and API integration.",
        backstory="You are Escanor. In Phase 1, provide analysis only.",
        llm=_llm("deepseek", config), allow_delegation=False, verbose=False,
        respect_context_window=True,
    )
    return stephen, seer, escanor

def _run_one(agent: Agent, description: str, expected_output: str) -> tuple[str, int, int]:
    task = Task(description=description, expected_output=expected_output, agent=agent)
    output = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    usage = getattr(output, "token_usage", None)
    tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
    tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
    return str(getattr(output, "raw", output)), tokens_in, tokens_out

def _extract_plan(raw: str, request: str) -> dict[str, str]:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    for candidate in ([match.group(0), raw] if match else [raw]):
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return {
                "seer_task": str(value.get("seer_task") or f"Analyze backend needs for: {request}"),
                "escanor_task": str(value.get("escanor_task") or f"Analyze frontend needs for: {request}"),
            }
    return {
        "seer_task": f"Analyze backend requirements and risks. Request: {request}",
        "escanor_task": f"Analyze frontend requirements and UI/API needs. Request: {request}",
    }

def run_team_task(message: str, *, task_id: str | None = None,
                  on_event: StatusCallback | None = None,
                  config: Settings = settings) -> TaskResult:
    if not message.strip():
        raise ValueError("message must not be empty")
    task_id = task_id or str(uuid.uuid4())
    def emit(event: dict) -> None:
        if on_event:
            on_event({"task_id": task_id, **event})
    tracker = CostTracker(
        task_id=task_id, limit_usd=config.max_cost_usd_per_task, settings=config,
        on_cost=(lambda event: on_event(event)) if on_event else None,
    )
    delegations = DelegationCounter(maximum=config.max_delegations_per_task)
    try:
        emit({"type":"status","agent":"stephen","text":"Stephen is analyzing requirements..."})
        stephen, seer, escanor = build_agents(config)
        raw, tin, tout = _run_one(
            stephen,
            "Return only JSON with string keys seer_task and escanor_task. Assign bounded analysis tasks. "
            "Do not write code, use tools, or ask agents to chat with each other.\nUser request: " + message,
            "A JSON object with seer_task and escanor_task string fields.",
        )
        tracker.add_usage("groq", tin, tout)
        plan = _extract_plan(raw, message)

        delegations.consume("seer")
        emit({"type":"status","agent":"seer","text":"Stephen delegated backend analysis to Seer."})
        seer_text, tin, tout = _run_one(
            seer, "Analyze only: " + plan["seer_task"] + "\nOriginal request: " + message,
            "Concise backend analysis with assumptions, interfaces, and risks.",
        )
        tracker.add_usage("deepseek", tin, tout)

        delegations.consume("escanor")
        emit({"type":"status","agent":"escanor","text":"Stephen delegated frontend analysis to Escanor."})
        escanor_text, tin, tout = _run_one(
            escanor, "Analyze only: " + plan["escanor_task"] + "\nOriginal request: " + message,
            "Concise frontend analysis with UI, accessibility, and API integration notes.",
        )
        tracker.add_usage("deepseek", tin, tout)

        emit({"type":"status","agent":"stephen","text":"Stephen is reviewing the team output..."})
        review, tin, tout = _run_one(
            stephen,
            "Review the analyses against the request. Give a safe practical next step. "
            "Do not claim code was written or tools were used.\nRequest: " + message
            + "\nSeer: " + seer_text + "\nEscanor: " + escanor_text,
            "A concise user-facing summary with limitations and next steps.",
        )
        tracker.add_usage("groq", tin, tout)
        answer = review.strip() + f"\n\nCost: ${tracker.usd:.6f}"
        emit({"type":"token","text":answer})
        emit({"type":"status","agent":"stephen","text":"Stephen finished reviewing the result."})
        return TaskResult(task_id, answer, tracker.usd, tracker.tokens_in, tracker.tokens_out)
    except Exception as exc:
        emit({"type":"error","message":str(exc)})
        raise
