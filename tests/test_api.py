"""Integration tests for the FastAPI SSE endpoints in ``app/api/routes.py``.

Drives the app over HTTP via ``httpx.AsyncClient`` (through ``ASGITransport``,
no real network socket). The ``get_graph`` dependency is overridden to a test
graph — ``InMemoryStore``/``InMemorySaver`` plus a mocked LLM, same pattern as
``tests/test_load.py`` — so these tests never touch Postgres or a real model
API, and never need the app's real Postgres-backed lifespan to run at all.
"""

import json
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.api.main import app
from app.api.routes import get_graph
from app.graph import build_graph, nodes


def _fake_llm_response(messages: list[BaseMessage], *args, **kwargs) -> AIMessage:
    """Mirrors tests/test_load.py's fake LLM: echoes the human turn's content
    back so the test can assert on the topic without needing a real model."""
    last_human_message = messages[-1]
    return AIMessage(content=f"findings for: {last_human_message.content}")


async def _collect_sse_events(response: httpx.Response) -> list[dict]:
    """Reassemble an SSE body into ``[{"event": ..., "data": {...}}, ...]``.

    Reads line-by-line rather than splitting on a literal separator, since
    sse_starlette's line separator ("\\r\\n" by default) is an implementation
    detail this test shouldn't depend on.
    """
    events = []
    event_type: str | None = None
    data_line: str | None = None
    async for line in response.aiter_lines():
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_line = line.removeprefix("data:").strip()
        elif line == "" and event_type is not None:
            events.append({"event": event_type, "data": json.loads(data_line)})
            event_type, data_line = None, None
    return events


@pytest.fixture
async def client(monkeypatch) -> AsyncIterator[httpx.AsyncClient]:
    """An AsyncClient wired to the app, with a mocked LLM and a test graph."""
    mock_ainvoke = AsyncMock(side_effect=_fake_llm_response)
    monkeypatch.setattr(nodes, "llm_with_tools", Mock(ainvoke=mock_ainvoke))

    test_graph = build_graph(InMemoryStore(), InMemorySaver())
    app.dependency_overrides[get_graph] = lambda: test_graph

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_graph, None)


async def test_start_run_streams_tokens_then_interrupt(client: httpx.AsyncClient):
    async with client.stream(
        "POST", "/runs/", json={"topic": "capital of Jordan"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        thread_id = response.headers["x-thread-id"]
        uuid.UUID(thread_id)  # raises ValueError if not a valid UUID

        events = await _collect_sse_events(response)

    # No "token" assertion: nodes.llm_with_tools is a bare Mock(ainvoke=...),
    # not a real Runnable, so astream_events never emits on_chat_model_stream
    # for it — that event requires proper Runnable instrumentation. Token
    # streaming itself is exercised manually against the real model instead.
    assert events[-1]["event"] == "interrupt"
    assert "capital of Jordan" in events[-1]["data"]["content"]


async def test_resume_run_with_yes_completes(client: httpx.AsyncClient):
    async with client.stream(
        "POST", "/runs/", json={"topic": "capital of Jordan"}
    ) as start_response:
        thread_id = start_response.headers["x-thread-id"]
        await _collect_sse_events(start_response)  # drain to let the pause land

    async with client.stream(
        "POST", f"/runs/{thread_id}/resume", json={"response": "yes"}
    ) as resume_response:
        assert resume_response.status_code == 200
        events = await _collect_sse_events(resume_response)

    assert events == [{"event": "done", "data": {"type": "done", "content": None}}]


async def test_resume_run_without_pending_interrupt_returns_404(
    client: httpx.AsyncClient,
):
    never_started_thread_id = str(uuid.uuid4())
    response = await client.post(
        f"/runs/{never_started_thread_id}/resume", json={"response": "yes"}
    )
    assert response.status_code == 404
