"""Unit tests for researcher_node (app/graph/nodes.py).

researcher_node calls two external things: the store (injected as a plain
argument) and the module-level llm_with_tools (called directly, so it has to
be monkeypatched). These tests fake both to exercise the node's one branch
(existing memory vs. none) without hitting Postgres or the real Mistral API.
"""

from unittest.mock import AsyncMock, Mock

from langchain_core.messages import AIMessage, SystemMessage

from app.graph import nodes
from app.graph.nodes import researcher_node, save_findings_node


class FakeStore:
    """Minimal store stand-in: only implements the asearch() the node calls."""

    def __init__(self, existing_memory):
        self._existing_memory = existing_memory

    async def asearch(self, namespace):
        return self._existing_memory


async def test_researcher_node_no_memory_uses_web_search_prompt(monkeypatch):
    """Empty store result -> node falls back to the web-search system prompt."""
    canned_response = AIMessage(content="draft answer")
    mock_ainvoke = AsyncMock(return_value=canned_response)
    # llm_with_tools is a pydantic-backed RunnableBinding: it rejects setting
    # arbitrary attributes on the instance, so the module-level *name* is
    # swapped instead, for a plain Mock that allows any attribute.
    fake_llm = Mock(ainvoke=mock_ainvoke)
    monkeypatch.setattr(nodes, "llm_with_tools", fake_llm)

    store = FakeStore(existing_memory=[])
    state = {"topic": "LangGraph reducers", "messages": []}
    config = {"configurable": {"user_id": "test_user"}}

    result = await researcher_node(state, store, config)

    assert result == {"messages": [canned_response]}

    called_messages = mock_ainvoke.call_args.args[0]
    system_message = called_messages[0]
    assert isinstance(system_message, SystemMessage)
    assert system_message.content == nodes.web_search_instructions


async def test_researcher_node_with_memory_uses_recall_prompt(monkeypatch):
    """Non-empty store result -> node uses the memory-recall prompt, populated with it."""
    existing_memory = [{"topic": "LangGraph reducers", "content": "prior finding"}]
    canned_response = AIMessage(content="draft answer using memory")
    mock_ainvoke = AsyncMock(return_value=canned_response)
    fake_llm = Mock(ainvoke=mock_ainvoke)
    monkeypatch.setattr(nodes, "llm_with_tools", fake_llm)

    store = FakeStore(existing_memory=existing_memory)
    state = {"topic": "LangGraph reducers", "messages": []}
    config = {"configurable": {"user_id": "test_user"}}

    result = await researcher_node(state, store, config)

    assert result == {"messages": [canned_response]}

    called_messages = mock_ainvoke.call_args.args[0]
    system_message = called_messages[0]
    assert isinstance(system_message, SystemMessage)
    assert system_message.content == nodes.existing_memory_instruction.format(
        existing_memory=existing_memory
    )


async def test_save_findings_node_persists_last_message_as_finding(monkeypatch):
    """Node builds a finding from state's topic/last message and delegates persistence to save_findings."""
    fake_content = AIMessage(content="Test content")
    mock_save_findings = AsyncMock(return_value="saved")
    monkeypatch.setattr(nodes, "save_findings", mock_save_findings)

    state = {"topic": "Test Topic", "messages": [fake_content]}
    config = {"configurable": {"user_id": "test_user"}}
    store = FakeStore(existing_memory=[])

    result = await save_findings_node(state=state, store=store, config=config)

    called_findings = mock_save_findings.call_args.kwargs["findings"]
    assert called_findings[0]["topic"] == state["topic"]
    assert called_findings[0]["content"] == fake_content.content
    assert result == {}
