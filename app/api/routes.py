"""FastAPI SSE endpoints for starting and resuming research runs.

Wraps ``app.streaming.events.stream_events``/``resume_graph`` — both already
async generators yielding ``(kind, payload)`` tuples — into ``text/event-stream``
responses via ``sse_starlette.EventSourceResponse``, so an HTTP client drives
the same graph the CLI does. The compiled graph comes from the ``get_graph``
dependency, which reads ``request.app.state.graph`` (set once at startup by
the lifespan in ``app/api/main.py``) — routed through a dependency, not read
directly, so tests can override it with a non-Postgres graph.
"""

import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from langgraph.graph.state import CompiledStateGraph
from sse_starlette.sse import EventSourceResponse

from app.core import build_run_config
from app.schemas.models import Event, ResumeRunRequest, StartRunRequest
from app.streaming.events import resume_graph, stream_events

router = APIRouter(prefix="/runs", tags=["runs"])


def get_graph(request: Request) -> CompiledStateGraph:
    """Dependency: the compiled graph the lifespan built and stored on ``app.state``."""
    return request.app.state.graph


async def _sse_format(
    events: AsyncGenerator[tuple[str, str | None], None],
) -> AsyncGenerator[dict, None]:
    """Wrap a ``(kind, payload)`` event generator into SSE-ready dicts.

    ``EventSourceResponse`` turns each dict into the ``event: ...\\ndata:
    ...\\n\\n`` wire format itself. A mid-stream exception can't become an
    HTTP error response — the 200 and headers are already sent — so it's
    caught here and turned into a terminal ``error`` event instead of
    silently truncating the connection.
    """
    try:
        async for kind, payload in events:
            event = Event(type=kind, content=payload)
            yield {"event": kind, "data": event.model_dump_json()}
    except Exception as exc:
        error_event = Event(type="error", content=str(exc))
        yield {"event": "error", "data": error_event.model_dump_json()}


@router.post("/")
async def start_run(
    body: StartRunRequest, graph: CompiledStateGraph = Depends(get_graph)
) -> EventSourceResponse:
    """Start a new research run and stream its output as SSE.

    The generated ``thread_id`` is returned in the ``X-Thread-Id`` response
    header — the client must send it back on ``POST /runs/{thread_id}/resume``
    for every HITL interrupt this run produces.
    """
    thread_id = str(uuid.uuid4())
    config = build_run_config(thread_id, body.user_id, body.topic)
    return EventSourceResponse(
        _sse_format(stream_events(body.topic, graph, config)),
        headers={"X-Thread-Id": thread_id},
    )


@router.post("/{thread_id}/resume")
async def resume_run(
    thread_id: uuid.UUID,
    body: ResumeRunRequest,
    graph: CompiledStateGraph = Depends(get_graph),
) -> EventSourceResponse:
    """Resume a run paused at a HITL interrupt and stream its output as SSE.

    404s up front, before opening the stream, if this ``thread_id`` has no
    pending interrupt — either it never existed, already ran to completion,
    or was already resumed. 403s if ``body.user_id`` doesn't match the
    ``user_id`` the run actually started with.
    """
    config = build_run_config(str(thread_id), body.user_id)
    state = await graph.aget_state(config)
    if not (state.tasks and state.tasks[0].interrupts):
        raise HTTPException(
            status_code=404,
            detail=f"No pending HITL interrupt for thread_id={thread_id}.",
        )
    # `configurable.user_id` isn't preserved in state.config (LangGraph's
    # checkpointer only keeps thread_id/checkpoint_ns/checkpoint_id there) —
    # but it IS copied into checkpoint metadata automatically, which is the
    # only place the run's *original* user_id can still be read back from.
    original_user_id = state.metadata.get("user_id")
    if body.user_id != original_user_id:
        raise HTTPException(
            status_code=403,
            detail="user_id does not match the user_id this run was started with.",
        )
    return EventSourceResponse(_sse_format(resume_graph(body.response, graph, config)))
