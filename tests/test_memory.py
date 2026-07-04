from unittest.mock import AsyncMock, Mock

from langgraph.store.memory import InMemoryStore
from langchain_core.messages import AIMessage, SystemMessage
from app.graph.nodes import researcher_node, save_findings_node
from app.graph import nodes


async def test_researcher_node_recalls_finding_from_prior_session(monkeypatch):
    store = InMemoryStore()
    state = {
        "topic": "test",
        "messages": [AIMessage(content="Hello, world!")],
    }
    config = {"configurable": {"user_id": "test_user"}}

    await save_findings_node(state=state, store=store, config=config)

    state2 = {"topic": "testing python", "messages": []}

    canned_response = AIMessage(content="draft answer using memory")
    mock_ainvoke = AsyncMock(return_value=canned_response)

    fake_llm = Mock(ainvoke=mock_ainvoke)
    monkeypatch.setattr(nodes, "llm_with_tools", fake_llm)

    result = await researcher_node(state=state2, store=store, config=config)

    assert result == {"messages": [canned_response]}

    called_messages = mock_ainvoke.call_args.args[0]
    system_message = called_messages[0]
    assert isinstance(system_message, SystemMessage)

    assert "Hello, world!" in system_message.content
