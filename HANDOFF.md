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

### 2026-10-29 / ChatGPT — Claude review fixes
- Task IDs addressed: Phase 1 review items 1–6 and 8; Phase 2 not started.
- Branch: `chatgpt/phase-0`.
- What changed:
  - `backend/agents/team.py`: sets `max_iter`, `max_rpm`, and `max_execution_time` on every agent; updates model IDs; listens to scoped CrewAI LLM events; removes cost from answer text; emits final cost and done events on both success and failure.
  - `backend/guardrails/cost.py`: per-LLM-call cost accounting, nonzero text-length estimates and warning callbacks when usage metadata is missing, and a circuit-breaker exception from the completion event.
  - `backend/config.py`, `.env.example`: set CrewAI/OpenTelemetry telemetry-disable flags and updated provider rates.
  - `tests/test_guardrails.py`: added mocked task-level cost breaker and delegation-limit tests plus usage-estimation test.
- Pricing verification (2026-10-29):
  - Groq official model listing: `openai/gpt-oss-20b` costs $0.075/M input and $0.30/M output. The prior `llama-3.3-70b-versatile` is deprecated for developer/free tiers.
  - DeepSeek official rate card: `deepseek-flash` costs $0.15/M cache-miss input and $0.60/M output off-peak. Peak rates double; cache-hit input is cheaper and not modeled separately in this estimator.
  - Sources: https://console.groq.com/docs/models ; https://console.groq.com/docs/deprecations ; https://api-docs.deepseek.com/quick_start/pricing/
- Untested or known issues:
  - I could not run `pip install -r requirements.txt` on Python 3.11 or execute the mocked tests in this environment. CrewAI 0.130.0 event exports, scoped handler behavior, `LLM(...)` arguments, and `CrewOutput.token_usage` fields therefore remain unverified at runtime. Do not treat the pin-check as passed.
  - The repository tool did not place the attempted GitHub Actions workflow on this branch; no workflow is claimed as committed.
  - The budget is estimated from event usage when present, otherwise approximate text length. Provider calls already in flight cannot be refunded. DeepSeek peak/cache-hit billing is not modeled precisely.
  - No live provider calls were made; Phase 1 has no tool integrations.
- Contract changes: None. Cost is emitted in a final `cost` event, followed by `done`; the answer text no longer includes a cost suffix.
- Next up / blockers: Review this branch. Wait for the user to say `next` before Phase 2.
