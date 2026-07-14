# `tests/` — Pytest Unit Tests

Unit tests for individual graph components, run in isolation from a live
graph or database (monkeypatching LangGraph internals, or using
`InMemoryStore`/`InMemorySaver`, rather than standing up Postgres) — plus a
full-graph concurrency test and a full-API integration test.

## `test_hitl.py`

Tests for `hitl_node` (`app/graph/nodes.py`). Monkeypatches
`app.graph.nodes.interrupt` directly (patched where the name is *looked up*
— `app.graph.nodes.interrupt` — not where it's defined, `langgraph.types`)
so the node can be exercised synchronously, without a running graph or a
real paused thread.

### `def test_hitl_node_yes(monkeypatch)`

Approval (`'yes'`) should record the decision and add no extra message.
Patches `interrupt` to return `"yes"`, calls `hitl_node({"topic": "Test
Topic"}, {})`, and asserts `result["human_response"] == "yes"` and
`"messages" not in result` — on approval the graph routes straight to
`save_findings`, so there's no need for a message to feed back into the
researcher's LLM context.

### `def test_hitl_node_no(monkeypatch)`

Rejection (`'no'`) should record the decision and append a `HumanMessage`.
Patches `interrupt` to return `"no"`, calls `hitl_node`, and asserts
`result["human_response"] == "no"`, `len(result["messages"]) == 1`, and
`isinstance(result["messages"][0], HumanMessage)` — required because
`researcher_node` re-invokes the LLM afterward, and the Mistral API rejects
an `AIMessage` as the most recent turn, so the rejection has to look like a
human turn to be valid input.

### `def test_hitl_node_edit(monkeypatch)`

Edit (`'edit'`) should record the decision, take a second interrupt for the
replacement text, and append that text as a `HumanMessage`. Two
`interrupt()` calls happen in sequence inside the edit branch — a single
fixed-return `lambda` can't model that, since it always returns the same
value regardless of call count — so this uses `Mock(side_effect=["edit",
replacement_text])` to return a different value on each successive call.
Asserts `result["human_response"] == "edit"`, one `HumanMessage` in
`result["messages"]`, and that the replacement text appears in its content.

## `test_nodes.py`

Unit tests for `researcher_node` and `save_findings_node`
(`app/graph/nodes.py`). A `FakeStore` stand-in implements only the
`asearch()` method the nodes call, avoiding a real Postgres/`InMemoryStore`
round-trip. The module-level `llm_with_tools` is swapped for a plain `Mock`
via `monkeypatch.setattr(nodes, "llm_with_tools", fake_llm)` — it's a
pydantic-backed `RunnableBinding` that rejects arbitrary attribute
assignment, so the module-level *name* is replaced rather than mutating the
instance.

### `async def test_researcher_node_no_memory_uses_web_search_prompt(monkeypatch)`

Empty store result → node falls back to `web_search_instructions`. Asserts
the system message passed to `llm_with_tools.ainvoke` matches that prompt
exactly.

### `async def test_researcher_node_with_memory_uses_recall_prompt(monkeypatch)`

Non-empty store result → node uses `existing_memory_instruction`, formatted
with the retrieved memory. Asserts the system message content matches
`existing_memory_instruction.format(existing_memory=existing_memory)`.

### `async def test_save_findings_node_persists_last_message_as_finding(monkeypatch)`

Monkeypatches `save_findings` itself (not the store), so the test only
checks that `save_findings_node` builds the right finding dict and
delegates correctly — not `save_findings`'s own persistence logic (covered
implicitly by `test_memory.py`). Asserts the `findings` kwarg passed to
`save_findings` has `topic` matching `state["topic"]` and `content` matching
the last message's `.content`.

## `test_memory.py`

Cross-session continuity test, against a **real** `InMemoryStore` (not a
fake) — this is the one place the actual `store.aput`/`store.asearch`
round-trip is exercised outside a full graph run.

### `async def test_researcher_node_recalls_finding_from_prior_session(monkeypatch)`

Calls `save_findings_node` to persist a finding for `test_user`, then calls
`researcher_node` again (fresh `state`, same `user_id`, `llm_with_tools`
monkeypatched) and asserts the earlier finding's content shows up in the
system prompt passed to the LLM — proving memory actually survives between
node calls, not just that `asearch`/`aput` exist.

## `test_load.py`

Full-graph concurrency test — Phase 3's "load test: 5 concurrent threads"
item. Unlike the other three files, this drives the **real compiled
graph** (`build_graph`) end-to-end rather than calling a node function
directly, because the thing under test — checkpointer/store isolation
across concurrently-running `thread_id`s — doesn't exist at the
single-node level. Uses `InMemorySaver`/`InMemoryStore` (fast, no Postgres)
and a fake `llm_with_tools` whose `ainvoke` is an `AsyncMock(side_effect=...)`
that derives its response from the *actual call arguments* (the last
`HumanMessage`'s content, which contains the thread's topic) — a fixed
`return_value` or an order-indexed `side_effect` list can't be trusted
under concurrency, since call order across `asyncio.gather` isn't
meaningful.

### `async def run_one_thread(graph, thread_id, user_id, topic) -> dict`

Shared helper: invokes the graph until it pauses at the `hitl_node`
interrupt (asserts `"__interrupt__"` is in the returned state — a compiled
graph with a checkpointer returns normally on `interrupt()`, it does not
raise), then resumes with `Command(resume="yes")` and returns the final
state.

### `async def test_five_concurrent_threads_isolate_state(monkeypatch)`

5 distinct `(thread_id, user_id, topic)` triples, run concurrently via
`asyncio.gather`. Targets isolation **across users** — each `user_id` gets
its own `(user_id, "findings")` namespace. Asserts each thread's final
message contains its own topic (no cross-thread bleed), and that each
user's namespace holds exactly one finding matching its topic.

### `async def test_five_concurrent_threads_same_user_isolate_by_thread(monkeypatch)`

5 distinct `thread_id`s but one **shared** `user_id` — targets write
contention **within a single namespace** instead, a distinct failure mode
from the cross-user test (a lost or clobbered concurrent write wouldn't
show up there, since the namespaces never overlap). Two separate checks,
not one merged loop: a per-thread loop asserts each final message still
carries its own topic; a single post-loop `store.asearch((shared_user_id,
"findings"))` asserts the namespace ended up with exactly 5 findings and
the recovered topic set matches what was written — this second check has
to run once, after all writes are done, not per-thread, since it's a
namespace-wide invariant.

## `test_api.py`

Integration tests for `app/api/routes.py`, driven over HTTP via
`httpx.AsyncClient` + `ASGITransport(app=app)` — no real network socket, and
no Postgres: the `get_graph` dependency is overridden to a test graph
(`InMemoryStore`/`InMemorySaver` + a mocked `llm_with_tools`, same pattern
as `test_load.py`), so the app's real Postgres-backed `lifespan` never runs.

### `_fake_llm_response(messages, *args, **kwargs) -> AIMessage`, `_collect_sse_events(response) -> list[dict]`

Module-level helpers. The first mirrors `test_load.py`'s echo-the-topic
mock. The second reassembles a streamed SSE body into `[{"event": ...,
"data": {...}}, ...]` by reading `response.aiter_lines()` and splitting on
blank lines — deliberately not a literal string split on
`sse_starlette`'s separator (`"\r\n"` by default), since that's an
implementation detail the test shouldn't couple to.

### `client` fixture

Monkeypatches `nodes.llm_with_tools`, builds a test graph, and sets
`app.dependency_overrides[get_graph]` for the duration of the test, popping
it afterward so tests don't leak state into each other.

### `async def test_start_run_streams_tokens_then_interrupt(client)`

`POST /runs/` with a topic; asserts a 200, an `text/event-stream`
content-type, a parseable UUID in `X-Thread-Id`, and that the stream ends on
an `"interrupt"` event whose content mentions the topic. Does **not** assert
any `"token"` event occurred — `nodes.llm_with_tools` is a bare
`Mock(ainvoke=...)`, not a real `Runnable`, so `astream_events` never emits
`on_chat_model_stream` for it; that event requires proper Runnable
instrumentation. Token streaming itself is exercised manually against the
real model, not by this test.

### `async def test_resume_run_with_yes_completes(client)`

Starts a run, drains its stream to let the pause land, then `POST
.../resume` with `{"response": "yes"}`. Asserts the resumed stream is
exactly one `"done"` event — no further LLM turn happens on the approve
path (see `route_from_hitl`), so there's nothing else to stream.

### `async def test_resume_run_without_pending_interrupt_returns_404(client)`

`POST .../resume` against a `thread_id` that was never started. Asserts
`404` — covers the `get_graph`/`aget_state` pre-check in `resume_run`, not
just the happy path.

### `async def test_resume_run_with_wrong_user_id_returns_403(client)`

Starts a run as `user_id="alice"`, then resumes the same `thread_id` with
`user_id="mallory"`. Asserts `403` — covers `resume_run`'s check against
`state.metadata["user_id"]` (the checkpoint's own recorded value, not
whatever the client claims), guarding against resuming — and so writing
`save_findings` into — another user's thread.
