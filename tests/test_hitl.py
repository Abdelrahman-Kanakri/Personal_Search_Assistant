"""Unit tests for the human-in-the-loop (HITL) node.

``hitl_node`` calls LangGraph's ``interrupt()`` to pause the graph and wait
for a human decision. These tests monkeypatch ``interrupt`` directly so the
node can be exercised synchronously, without a running graph or a real
paused thread.
"""

from unittest.mock import Mock

from langchain_core.messages import HumanMessage

from app.graph.nodes import hitl_node


def test_hitl_node_yes(monkeypatch):
    """Approval ('yes') should record the decision and add no extra message.

    On approval the graph routes straight to ``save_findings`` — there is no
    need for a rejection message to feed back into the researcher's LLM
    context, so ``messages`` must be absent from the returned partial state.
    """
    monkeypatch.setattr("app.graph.nodes.interrupt", lambda prompt: "yes")
    mock_state = {"topic": "Test Topic"}
    config = {}

    result = hitl_node(mock_state, config)
    assert result["human_response"] == "yes"
    assert "messages" not in result


def test_hitl_node_no(monkeypatch):
    """Rejection ('no') should record the decision and append a HumanMessage.

    The extra HumanMessage is required because the researcher node re-invokes
    the LLM afterward, and the Mistral API rejects an AIMessage as the most
    recent turn — the rejection must look like a human turn to be valid input.
    """
    monkeypatch.setattr("app.graph.nodes.interrupt", lambda prompt: "no")
    mock_state = {"topic": "Test Topic"}
    config = {}

    result = hitl_node(mock_state, config)
    assert result["human_response"] == "no"
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)


def test_hitl_node_edit(monkeypatch):
    """Edit ('edit') should record the decision, then a second interrupt for
    the replacement text, and append that text as a HumanMessage.

    Two interrupt() calls happen in sequence inside hitl_node's edit branch:
    the first returns the 'edit' choice, the second returns the human's
    replacement text. A single fixed-return lambda can't model that — it
    always returns the same value regardless of call count — so this uses
    Mock(side_effect=[...]) to return a different value on each successive
    call.
    """
    replacement_text = "Train topic instead of Test topic."
    monkeypatch.setattr(
        "app.graph.nodes.interrupt",
        Mock(side_effect=["edit", replacement_text]),
    )
    mock_state = {"topic": "Test Topic"}
    config = {}

    result = hitl_node(mock_state, config)
    assert result["human_response"] == "edit"
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)
    assert replacement_text in result["messages"][0].content
