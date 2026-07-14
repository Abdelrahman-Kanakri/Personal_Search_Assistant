# `app/streaming/` — Event Streaming and HITL Resume

Async generators that drive the compiled graph and surface events to
callers. This is the layer between the user-facing surfaces (`app/cli.py`,
`app/api/routes.py`) and the graph itself — it owns the `astream_events`
loop and the interrupt/resume protocol, so callers only deal with a stream
of `(kind, payload)` tuples: `"token"`/`"interrupt"`/`"done"`.

## `events.py`

### `async def stream_events(user_input: str, graph: CompiledStateGraph, config: RunnableConfig) -> AsyncGenerator[tuple[str, str | None], None]`

Start a research run and stream agent output until an interrupt or
completion.

- **Args:**
  - `user_input`: the research topic/query, passed as `state["topic"]`
    (with `messages: []` to start a fresh run).
  - `graph`: the compiled LangGraph graph.
  - `config`: runnable config including `thread_id` and `user_id` (build via
    `app.core.build_run_config`, not by hand).
- **Yields:** `(kind, content)` tuples —
  - `("token", str)` for each chunk of streamed LLM output.
  - `("interrupt", str)` once, if the graph pauses for human review — the
    interrupt prompt from `hitl_node`.
  - `("done", None)` once, if the graph ran to completion (`END`) without
    interrupting.
- **Behavior:** iterates `graph.astream_events({"topic": ..., "messages":
  []}, config, version="v2")`. On every `"on_chat_model_stream"` event, the
  chunk's content is yielded token-by-token (handles both the plain-string
  content case and the list-of-content-parts case, e.g. Mistral's mixed
  text/tool-call streaming shape — only `{"type": "text"}` parts are
  yielded). After the stream ends, calls `graph.aget_state(config)`; LangGraph
  does **not** emit an `on_interrupt` event through `astream_events` — the
  only reliable way to detect a pause is `state.tasks and
  state.tasks[0].interrupts` (not `state.next`, which can read as an empty
  tuple on a *second* interrupt within one node's replay — see
  `issues-and-fixes.md`'s HITL edit-flow entry). If a pending interrupt
  exists, yields its value; otherwise yields `("done", None)`.

### `async def resume_graph(human_response: str, graph: CompiledStateGraph, config: RunnableConfig) -> AsyncGenerator[tuple[str, str | None], None]`

Resume a graph that was suspended at a HITL interrupt.

- **Args:**
  - `human_response`: the user's approval decision (`'yes'`/`'no'`/`'edit'`,
    or — after an `'edit'` choice — the replacement text).
  - `graph`: the compiled LangGraph graph.
  - `config`: the **same** runnable config used in the original
    `stream_events` call — `thread_id` must match so the checkpointer loads
    the correct suspended state.
- **Yields:** same `(kind, content)` shape as `stream_events` — another
  `"interrupt"` if the graph pauses again (rejection/edit routes back to
  `researcher_node`, which may hit `hitl_node` again), or `"done"` if the
  graph ran to completion.
- **Behavior:** wraps `human_response` in `Command(resume=human_response)` so
  LangGraph can unblock the interrupt and continue execution from where it
  paused. Streams and inspects final state identically to `stream_events`.

## Callers

- `app/cli.py`'s `run_cli` — `async for kind, payload in stream_result:`,
  reassigning `stream_result = resume_graph(...)` on every `"interrupt"`.
- `app/api/routes.py`'s `_sse_format` — wraps the same tuples into SSE-ready
  dicts for `sse_starlette.EventSourceResponse`, so an HTTP client drives
  the identical protocol the CLI does.

## `__init__.py`

Re-exports `stream_events` and `resume_graph` — `from app.streaming import
stream_events, resume_graph`.
