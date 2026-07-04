# `tests/` — Pytest Unit Tests

Unit tests for individual graph components, run in isolation from a live
graph or database (monkeypatching LangGraph internals where needed rather
than standing up Postgres).

## `test_hitl.py`

Tests for `hitl_node` (`app/graph/nodes.py`). Monkeypatches
`app.graph.nodes.interrupt` directly so the node can be exercised
synchronously, without a running graph or a real paused thread.

### `def test_hitl_node_yes(monkeypatch)`

Approval (`'yes'`) should record the decision and add no extra message.
Patches `interrupt` to return `"yes"`, calls `hitl_node({"topic": "Test
Topic"}, {})`, and asserts `result["human_response"] == "yes"` and
`"messages" not in result` — on approval the graph routes straight to
`save_findings`, so there's no need for a rejection message to feed back
into the researcher's LLM context.

### `def test_hitl_node_no(monkeypatch)`

Rejection (`'no'`) should record the decision and append a `HumanMessage`.
Patches `interrupt` to return `"no"`, calls `hitl_node`, and asserts
`result["human_response"] == "no"`, `len(result["messages"]) == 1`, and
`isinstance(result["messages"][0], HumanMessage)` — required because
`researcher_node` re-invokes the LLM afterward, and the Mistral API rejects
an `AIMessage` as the most recent turn, so the rejection has to look like a
human turn to be valid input.

## `test_memory.py`

Empty — 0 bytes. Presumably reserved for tests covering
[`app/memory/`](app-memory.md) once that package has an
implementation.

## `test_nodes.py`

Empty — 0 bytes. Presumably reserved for tests covering
`researcher_node` and `save_findings_node` (`app/graph/nodes.py`), which
currently have no dedicated test coverage — only `hitl_node` is tested (see
`test_hitl.py` above).
