# CONTRACTS.md

Interfaces shared by Claude and ChatGPT. Do not change these without updating this file and noting it in HANDOFF.md.

## 1. Repo layout

```
stephen-industries/
  backend/
    main.py            # FastAPI app
    agents/            # CrewAI agents, crew, manager
    guardrails/        # cost breaker, iteration limit, HITL
    tools/             # supabase_tool.py, github_tool.py, gmail_tool.py
    audit/             # SQLite audit log
    config.py          # env loading
  frontend/
    index.html, style.css, app.js
  .env.example
  requirements.txt
```

## 2. HTTP API

| Method | Path | Body | Response |
|---|---|---|---|
| POST | /api/chat | {"session_id": str, "message": str} | {"task_id": str} |
| GET | /api/stream/{task_id} | none | SSE stream (section 3) |
| POST | /api/approve | {"task_id": str, "request_id": str, "decision": "approve" or "deny"} | {"ok": true} |
| GET | /api/health | none | {"status": "ok"} |

/api/chat returns immediately; work runs in the background so several tasks can run at once.

## 3. SSE events

Each event is one line `data: <json>` followed by a blank line. Every JSON object has `type` and `task_id`.

| type | extra fields | meaning |
|---|---|---|
| status | agent ("stephen"/"seer"/"escanor"), text | live status bar line, e.g. "Escanor is asking Seer a question..." |
| token | text | chunk of the final answer (may be one chunk if true streaming isn't available) |
| hitl_request | request_id, agent, tool, action, params | UI shows Approve/Deny modal |
| hitl_resolved | request_id, decision | modal can close |
| cost | usd (float), tokens_in, tokens_out | running or final cost |
| error | message | task failed or was stopped (includes circuit breaker) |
| done | none | stream ends |

Example:
data: {"type":"hitl_request","task_id":"t1","request_id":"r7","agent":"seer","tool":"github","action":"create_issue","params":{"title":"Add signup table"}}

## 4. Tool interface

Every tool in backend/tools/ exposes functions registered with a `kind`:
- kind="read": runs immediately.
- kind="write": must pass through the HITL guardrail before running.

Return shape for every tool function:
{"ok": bool, "data": <json-serializable or None>, "error": str or None}
Tools never raise to the agent; they return ok:false with an error message.

Guardrail entry point:
def guarded(kind: str, tool: str, action: str): ...   # decorator

## 5. Config (env vars)

```
GROQ_API_KEY=
DEEPSEEK_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
GITHUB_TOKEN=
GITHUB_REPO=owner/name
GOOGLE_CREDENTIALS_FILE=
MAX_COST_USD_PER_TASK=0.50
MAX_DELEGATIONS_PER_TASK=10
CREWAI_STORAGE_DIR=./.memory
AUDIT_DB_PATH=./audit.sqlite
```

Secrets live only in .env, which is gitignored. Never commit keys.

## 6. Audit log (SQLite)

Table tool_calls:
id INTEGER PK, ts TEXT, task_id TEXT, agent TEXT, tool TEXT, action TEXT, kind TEXT, params_json TEXT, ok INTEGER, result_json TEXT, approved_by_user INTEGER NULL

## 7. Conventions

- Python 3.11+, type hints, ruff formatting.
- One branch per phase: chatgpt/phase-N.
- Log every handoff in HANDOFF.md.
