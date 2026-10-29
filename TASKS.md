# TASKS.md

Status: todo / doing / review / done. Update when you start or finish.

## Phase 0: Setup
- 0.1 Repo, docs, .gitignore (.env, .memory, *.sqlite) — done
- 0.2 requirements.txt (pinned), .env.example, backend/config.py — done

## Phase 1: Agents (no tools)
- 1.1 Stephen (Groq), Seer and Escanor (DeepSeek) agents; manager delegates only at first — implementation scaffolded
- 1.2 Per-task delegation limit (MAX_DELEGATIONS_PER_TASK) — implemented
- 1.3 Cost tracking + circuit breaker (MAX_COST_USD_PER_TASK), emits cost and error events — implemented; post-completion enforcement limitation documented

## Phase 2: Chat app
- 2.1 FastAPI app: /api/chat, /api/stream, /api/health, background tasks, SSE event bus
- 2.2 Dark-mode chat UI, SSE client, status bar, cost line
- 2.3 Verify UI against CONTRACTS.md with a mock SSE server

## Phase 3: Tools (read-only first)
- 3.1 Supabase tool: read schema, query rows
- 3.2 GitHub tool: read issues, fetch repo contents
- 3.3 SQLite audit log + logging wrapper

## Phase 4: Human approval for writes
- 4.1 guarded() decorator, pending-request registry, /api/approve, hitl_* events
- 4.2 Approve/Deny modal in UI
- 4.3 Write actions: Supabase insert/delete, GitHub create_issue

## Phase 5: Memory
- 5.1 CrewAI short/long-term memory with local storage + local embedder
- 5.2 Optional: project-snapshot store for past architectures

## Phase 6: Gmail (last)
- 6.1 Gmail OAuth + read/draft (read), send (write, HITL)
