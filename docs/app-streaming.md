# `app/streaming/` — Event Streaming and HITL Resume

Async helpers that drive the compiled graph and surface events to the CLI.
This is the layer between `app/cli.py` (user-facing REPL) and the graph
itself — it owns the `astream_events` loop and the interrupt/resume
protocol, so the CLI only has to deal with "here's a prompt" /
"here's `None`, we're done."

## `events.py`

### `async def stream_events(user_input: str, graph: CompiledStateGraph, config: RunnableConfig) -> str | None`

Start a research run and stream agent output until an interrupt or
completion.

- **Args:**
  - `user_input`: the research topic/query, passed as `state["topic"]`
    (with `messages: []` to start a fresh run).
  - `graph`: the compiled LangGraph graph.
  - `config`: runnable config including `thread_id` and `user_id`.
- **Returns:** the interrupt payload string if the graph pauses for human
  review (from `hitl_node`'s `interrupt(...)` call), or `None` if the graph
  ran to completion (reached `END`) without interrupting.
- **Behavior:** iterates `graph.astream_events({"topic": ..., "messages":
  []}, config, version="v2")`. On every `"on_chat_model_stream"` event, the
  chunk's content is printed token-by-token (handles both the plain-string
  content case and the list-of-content-parts case, e.g. Mistral's mixed
  text/tool-call streaming shape — only `{"type": "text"}` parts are
  printed). After the stream ends, calls `graph.aget_state(config)`; if
  `state.next` is non-empty the graph is paused, so the first interrupt's
  value (`state.tasks[0].interrupts[0].value`) is returned; otherwise
  `None`.

### `async def resume_graph(human_response: str, graph: CompiledStateGraph, config: RunnableConfig) -> str | None`

Resume a graph that was suspended at a HITL interrupt.

- **Args:**
  - `human_response`: the user's approval decision (`'yes'` / anything
    else).
  - `graph`: the compiled LangGraph graph.
  - `config`: the **same** runnable config used in the original
    `stream_events` call — `thread_id` must match so the checkpointer loads
    the correct suspended state.
- **Returns:** the next interrupt payload if the graph pauses again
  (rejection routes back to `researcher_node`, which may hit `hitl_node`
  again), or `None` if the graph ran to completion.
- **Behavior:** wraps `human_response` in `Command(resume=human_response)`
  so LangGraph can unblock the interrupt and continue execution from where
  it paused. Streams and inspects final state identically to
  `stream_events`.

## `__init__.py`

Currently empty. No re-exports are defined; callers import directly from
`app.streaming.events` (e.g. `from app.streaming.events import
stream_events, resume_graph`, as done in `app/cli.py`).
