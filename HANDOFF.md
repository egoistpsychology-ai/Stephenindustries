# HANDOFF.md

Newest entry on top.

## Template
- Date / Author:
- Task IDs done:
- Branch / commit:
- What changed (files):
- Untested or known issues:
- Contract changes (if any):
- Next up / blockers:

## Log

### 2026-10-29 / ChatGPT — follow-up safety review fixes
- Task IDs addressed: CrewAI event import path, event-bus behavior, task isolation, conservative pricing, and event-bus test; Phase 2 not started.
- Branch: `chatgpt/phase-0`.
- What changed:
  - `backend/agents/team.py`: sets `max_iter`, `max_rpm`, and `max_execution_time` on every agent; updates model IDs; listens to scoped CrewAI LLM events; removes cost from answer text; emits final cost and done events on both success and failure.
  - `backend/guardrails/cost.py`: uses the CrewAI 0.130.0 event path (`crewai.utilities.events`), filters usage through a task-scoped context, serializes event scopes because the bus is global, estimates nonzero usage when metadata is missing, and documents that handler exceptions are swallowed by this version of the bus.
  - `backend/config.py`, `.env.example`: set CrewAI/OpenTelemetry telemetry-disable flags and updated provider rates.
  - `tests/test_guardrails.py`: adds a fake completion event emitted through the actual CrewAI event bus, alongside mocked task-level breaker/delegation tests and usage-estimation coverage.
- Pricing verification (2026-10-29):
  - Groq official model listing: `openai/gpt-oss-20b` costs $0.075/M input and $0.30/M output. The prior `llama-3.3-70b-versatile` is deprecated for developer/free tiers.
  - DeepSeek official rate card: `deepseek-flash` off-peak cache-miss input is $0.15/M and output $0.60/M; peak rates double. The estimator now defaults to conservative peak rates and ignores cache-hit discounts.
  - Sources: https://console.groq.com/docs/models ; https://console.groq.com/docs/deprecations ; https://api-docs.deepseek.com/quick_start/pricing/
- Untested or known issues:
  - Source inspection of the official CrewAI 0.130.0 tag confirms LLM events are exported from `crewai.utilities.events`, not `crewai.events`; its event bus catches handler exceptions and continues. This fixes the import and removes the false claim that raising inside a handler interrupts kickoff. The per-call event accounting is verified by a test authored against the real bus, but the test suite and installation still have not been run here.
  - The repository tool did not place the attempted GitHub Actions workflow on this branch; no workflow is claimed as committed.
  - The budget is estimated from event usage when present, otherwise approximate text length. Because CrewAI 0.130.0 swallows event-handler exceptions, the event callback alone cannot interrupt an in-flight kickoff; the team checks the tracker after each stage. This is a stage-level breaker, not a proven hard per-LLM-call interrupt. Provider calls already in flight cannot be refunded. Task scopes are serialized to avoid global-bus cross-accounting.
  - No live provider calls were made; Phase 1 has no tool integrations.
- Contract changes: None. Cost is emitted in a final `cost` event, followed by `done`; the answer text no longer includes a cost suffix.
- Next up / blockers: Install with Python 3.11+, run `pip install -r requirements.txt -r dev-requirements.txt` and `pytest -q tests`; inspect any failures. Do not start Phase 2 until the user says `next`.
