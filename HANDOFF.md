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
- Task IDs addressed: Phase 1 review items 1–8; Phase 2 not started.
- Branch / commit: `chatgpt/phase-0`; review-fix commits are linked from the branch history.
- What changed:
  - `backend/agents/team.py`: configured `max_iter`, `max_rpm`, and `max_execution_time` for every agent; changed retired Groq/DeepSeek model IDs; tracks LLM usage through scoped CrewAI LLM events; removed cost text from the answer; emits final cost and done events on success/failure.
  - `backend/guardrails/cost.py`: accounts each completed LLM event; estimates nonzero tokens from prompt/response text when usage metadata is absent and emits a warning; checks the budget at LLM-call boundaries and after each Crew kickoff.
  - `backend/config.py`, `.env.example`: disable CrewAI telemetry and OpenTelemetry; update default rates for the selected models.
  - `tests/test_guardrails.py`: mocked task-level circuit-breaker and delegation-limit tests, plus usage fallback test.
  - `.github/workflows/phase-tests.yml`: Python 3.11 dependency installation, CrewAI constructor/event-hook compatibility check, and offline unit tests.
- Pricing verification (checked 2026-10-29):
  - Groq's official model page lists `openai/gpt-oss-20b` at $0.075/M input and $0.30/M output. The previous `llama-3.3-70b-versatile` is deprecated for developer/free tiers.
  - DeepSeek's official rate card lists `deepseek-flash` at $0.15/M cache-miss input and $0.60/M output off-peak; peak rates double and cached input is cheaper. The estimator uses the off-peak cache-miss rate as a conservative simple baseline but does not model cache-hit/peak pricing.
  - Sources: https://console.groq.com/docs/models ; https://console.groq.com/docs/deprecations ; https://api-docs.deepseek.com/quick_start/pricing/
- Untested or known issues:
  - This environment cannot run `pip install -r requirements.txt` or dispatch GitHub Actions, so the new CI job has not been observed completing. Do not treat the pin-check as passed until Actions is green.
  - CrewAI is pinned at `0.130.0`; the CI step is intended to validate the LLM constructor, Agent limits, event exports, and UsageMetrics import against that pin. If it fails, update the pin or adapt the code before use.
  - Event listeners may not be able to cancel an already-running provider request. Budget usage is recorded on each LLM completion and the next call is checked; an in-flight request cannot be refunded. The fallback estimate is approximate and may undercount non-English or token-dense content.
  - No live provider API calls were made; no tool integrations are implemented in Phase 1.
- Contract changes: None. Answer text no longer embeds cost; the final `cost` event carries totals, followed by `done`.
- Next up / blockers: Review the branch and wait for the user to say `next` before Phase 2.
