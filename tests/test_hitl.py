from langchain_core.messages import HumanMessage

from app.graph.nodes import hitl_node


def test_hitl_node_yes(monkeypatch):
    monkeypatch.setattr("app.graph.nodes.interrupt", lambda prompt: "yes")
    mock_state = {"topic": "Test Topic"}
    config = {}

    result = hitl_node(mock_state, config)
    assert result["human_response"] == "yes"
    assert "messages" not in result


def test_hitl_node_no(monkeypatch):
    monkeypatch.setattr("app.graph.nodes.interrupt", lambda prompt: "no")
    mock_state = {"topic": "Test Topic"}
    config = {}

    result = hitl_node(mock_state, config)
    assert result["human_response"] == "no"
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)
