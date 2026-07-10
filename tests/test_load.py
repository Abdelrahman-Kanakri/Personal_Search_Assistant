"""Load test: N concurrent threads through the compiled graph.

Verifies checkpointer/store isolation under concurrency — Phase 3 item 4.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from app.graph import nodes
from app.graph.build import build_graph


async def run_one_thread(graph, thread_id: str, user_id: str, topic: str) -> dict:
    """Drive one thread from START through the HITL interrupt to completion.

    Returns the final state after approval, so the caller can check that this
    thread's own topic/content came back — not another thread's.
    """
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    paused_state = await graph.ainvoke({"topic": topic, "messages": []}, config=config)
    assert "__interrupt__" in paused_state, f"{thread_id} did not pause for HITL"

    return await graph.ainvoke(Command(resume="yes"), config=config)


async def test_five_concurrent_threads_isolate_state(monkeypatch):
    """5 distinct thread_id/user_id pairs run concurrently; each ends with
    its own topic/finding, none see another thread's state."""

    # Response derived from the *input* messages, not call count/order — under
    # concurrency, a fixed return_value or a side_effect list indexed by call
    # order can't tell which thread it's answering for.
    def fake_response(messages: list[BaseMessage], *args, **kwargs) -> AIMessage:
        last_human_message = messages[-1]
        return AIMessage(content=f"findings for: {last_human_message.content}")

    mock_ainvoke = AsyncMock(side_effect=fake_response)
    fake_llm = Mock(ainvoke=mock_ainvoke)
    monkeypatch.setattr(nodes, "llm_with_tools", fake_llm)

    store = InMemoryStore()
    checkpointer = InMemorySaver()
    graph = build_graph(store, checkpointer)

    # 5 distinct user_ids: targets store-namespace isolation *across users*.
    # A same-user/multi-topic variant (contention *within* one namespace) is
    # a separate follow-up test.
    triples = [(f"thread_{i}", f"user_{i}", f"topic_{i}") for i in range(5)]

    results = await asyncio.gather(
        *(
            run_one_thread(graph, thread_id, user_id, topic)
            for thread_id, user_id, topic in triples
        )
    )

    for (thread_id, user_id, topic), final_state in zip(triples, results):
        last_message = final_state["messages"][-1]
        assert topic in last_message.content, (
            f"{thread_id} ended up with the wrong content: {last_message.content!r}"
        )

        findings = await store.asearch((user_id, "findings"))
        assert len(findings) == 1
        assert findings[0].value["topic"] == topic


async def test_five_concurrent_threads_same_user_isolate_by_thread(monkeypatch):
    """5 distinct thread_ids, same user_id, run concurrently. Tests write
    contention on a single store namespace — not user isolation."""

    # TODO 1: same fake_response pattern as the other test — copy or factor
    def fake_response(messages: list[BaseMessage], *args, **kwargs) -> AIMessage:
        last_human_message = messages[-1]
        return AIMessage(content=f"findings for: {last_human_message.content}")

    mock_ainvoke = AsyncMock(side_effect=fake_response)
    fake_llm = Mock(ainvoke=mock_ainvoke)
    monkeypatch.setattr(nodes, "llm_with_tools", fake_llm)

    # TODO 2: same InMemoryStore/InMemorySaver/build_graph setup.
    store = InMemoryStore()
    checkpointer = InMemorySaver()
    graph = build_graph(store, checkpointer)
    # TODO 3: build triples, but this time user_id is the SAME constant
    # across all 5 — only thread_id and topic vary. Think about why
    # thread_id still has to be unique even though user_id isn't (what does
    # the checkpointer key on?).
    shared_user_id = "user_shared"
    triples = [(f"thread_{i}", shared_user_id, f"topic_{i}") for i in range(5)]

    results = await asyncio.gather(
        *(
            run_one_thread(graph, thread_id, user_id, topic)
            for thread_id, user_id, topic in triples
        )
    )

    # Per-thread check: each thread's own final message still carries its
    # own topic, same as the cross-user test.
    for (thread_id, _user_id, topic), final_state in zip(triples, results):
        last_message = final_state["messages"][-1]
        assert topic in last_message.content, (
            f"{thread_id} ended up with the wrong content: {last_message.content!r}"
        )

    # Shared-namespace check: all 5 concurrent writers landed in the SAME
    # (shared_user_id, "findings") namespace. If a write got lost or
    # clobbered another under concurrency, this count or this set is where
    # it would show up — a per-thread check above can't see it, since each
    # thread only looks at its own final_state, never the namespace as a
    # whole.
    findings = await store.asearch((shared_user_id, "findings"))
    assert len(findings) == 5, (
        f"expected 5 findings in the shared namespace, got {len(findings)}"
    )
    expected_topics = {topic for _thread_id, _user_id, topic in triples}
    actual_topics = {finding.value["topic"] for finding in findings}
    assert actual_topics == expected_topics
