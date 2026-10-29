"""FastAPI entry point for the Stephen Industries chat app."""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.agents.team import run_team_task

app = FastAPI(title="Stephen Industries")
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
_task_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
_task_loops: dict[str, asyncio.AbstractEventLoop] = {}


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


def _queue_event(task_id: str, event: dict[str, Any]) -> None:
    queue = _task_queues.get(task_id)
    loop = _task_loops.get(task_id)
    if queue is not None and loop is not None and not loop.is_closed():
        loop.call_soon_threadsafe(queue.put_nowait, event)


async def _run_task(task_id: str, message: str) -> None:
    try:
        await asyncio.to_thread(
            run_team_task,
            message,
            task_id=task_id,
            on_event=lambda event: _queue_event(task_id, event),
        )
    except Exception as exc:
        _queue_event(task_id, {"type": "error", "task_id": task_id, "message": str(exc)})
        _queue_event(task_id, {"type": "done", "task_id": task_id})


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, str]:
    task_id = str(uuid.uuid4())
    _task_queues[task_id] = asyncio.Queue()
    _task_loops[task_id] = asyncio.get_running_loop()
    asyncio.create_task(_run_task(task_id, request.message.strip()))
    return {"task_id": task_id}


@app.get("/api/stream/{task_id}")
async def stream(task_id: str) -> StreamingResponse:
    queue = _task_queues.get(task_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Unknown task_id")

    async def event_stream():
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("type") == "done":
                _task_queues.pop(task_id, None)
                _task_loops.pop(task_id, None)
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
