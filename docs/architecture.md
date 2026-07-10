# Architecture — File-by-File Map

A guide to every Python file in the project: what it's for, what it owns, and
how it connects to the rest of the graph. Read this to reorient quickly
after time away, before diving into any one file.

## Entry point

### `main.py`
Owns the Postgres connection lifecycle for the whole CLI session.
`async def main()` opens `async with (AsyncPostgresStore.from_conn_string(...) as store, AsyncPostgresSaver.from_conn_string(...) as checkpointer):`,
awaits `setup()` on both, calls `build_graph(store, checkpointer)` (a plain
sync call), then `await run_cli(graph)` — all nested inside the `with` block,
since neither connection may be used once that block exits.
`if __name__ == "__main__": asyncio.run(main())` bridges the sync script
entry point into the async world.

## `app/cli.py`
The interactive read-eval loop. `run_cli(graph: CompiledStateGraph)` loops
forever: generates a fresh `thread_id` per research topic (so checkpointer
state doesn't bleed between unrelated topics), builds a `RunnableConfig`
carrying both `thread_id` and `user_id` (the latter required because
`save_findings` namespaces the store by user), and drives `stream_events`/
`resume_graph` from `app/streaming/events.py`, printing the interrupt prompt
and looping on `resume_graph` until the graph reaches `END`.

## `app/core/` — settings and logging

### `app/core/config.py`
Defines `Settings(BaseSettings)` (pydantic-settings) and the module-level
`settings` singleton, loaded once from `.env` at import time. Every field
without a default is required — a missing `.env` value fails loudly at
startup (`ValidationError`) rather than at first use. Also eagerly copies a
few settings into `os.environ` (`OPENSSL_CONF`, the `LANGSMITH_*` vars)
because some libraries (LangSmith tracing, pyarrow's OpenSSL workaround)
read `os.environ` directly and ignore pydantic-settings entirely.

### `app/core/logging.py`
Structured JSON logging via `structlog` layered on top of stdlib `logging`.
`get_logger(name)` returns a `structlog` bound logger; if `name` is given, it
gets its own `FileHandler` writing to `logs/<name>.log` with
`propagate=False`, isolating it from the shared `logs/log.log`. Currently no
module actually calls `get_logger(__name__)` — nothing is routed to a named
channel yet, everything unnamed falls through to the shared file.

### `app/core/__init__.py`
Re-exports `settings` and `get_logger` — the only import path the rest of
the app should use (`from app.core import settings`, never
`from app.core.config import Settings` directly).

## `app/graph/` — the LangGraph state machine

### `app/graph/state.py`
`AgentState(TypedDict)` — the single shared state dict every node reads from
and writes to. `messages` uses the `add_messages` reducer (merges/appends by
message ID, doesn't overwrite). `results` and `findings` use
`Annotated[..., operator.add]` (blind concatenation) to accumulate across
turns. `human_response: Optional[str]` holds the last HITL decision.
`Finding` is a separate Pydantic `BaseModel` (validated, since it's what
gets persisted) — not a TypedDict, unlike `AgentState` itself.

### `app/graph/nodes.py`
The three nodes that do actual work:
- `researcher_node` (async) — one LLM + tool-calling turn. Reads
  `store.asearch((user_id, "findings"))` for cross-session memory; picks
  between `existing_memory_instruction` (memory found) and
  `web_search_instructions` (no memory) system prompts, then
  `await llm_with_tools.ainvoke(...)`. Owns only the `messages` field of the
  return dict.
- `hitl_node` (sync) — calls `interrupt(...)` to pause the graph for a
  three-way approve/reject/edit decision, re-prompting on unrecognized
  input. Reject appends a `HumanMessage` and loops back to
  `researcher_node` for another LLM turn. Edit issues a **second**
  `interrupt(...)` for the replacement text, then also appends it as a
  `HumanMessage` and — per `route_from_hitl` — likewise routes back to
  `researcher_node`, not straight to `save_findings`. Either non-approve
  path needs that appended message so the next `researcher_node` turn has a
  valid trailing role for the Mistral API (which rejects a request ending on
  an `AIMessage`).
- `save_findings_node` (async) — packages `state["topic"]` +
  `state["messages"][-1].content` + a timestamp into a finding dict, and
  `await`s `save_findings(...)` (the tool in `app/tools/save_finding.py`) to
  persist it. Returns `{}` — no state fields to update.

### `app/graph/edges.py`
Pure routing functions — no side effects, no state writes (state can only be
mutated by a node's returned dict, never by an edge).
- `route_from_research` — `"web_search"` if the last `AIMessage` has pending
  `tool_calls`, else `"hitl_node"`.
- `route_from_hitl` — `"save_findings"` if `human_response` is `"yes"`/`"y"`,
  else back to `"researcher_node"`.

### `app/graph/build.py`
`build_graph(store: BaseStore, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph`
— assembles the `StateGraph(AgentState)` (all `add_node`/`add_edge`/
`add_conditional_edges` calls) and compiles it. Plain `def`, not `async def`
— nothing inside needs `await`. Takes `store`/`checkpointer` as **already-open**
resources typed against the abstract base classes (not the concrete Postgres
classes) — the function only forwards them into `builder.compile(...)`, so
it never needs to know the backend is Postgres specifically. The caller
(`main.py`) owns opening and closing both.

### `app/graph/__init__.py`
Re-exports `build_graph`, `AgentState`, the three nodes, and the two edge
functions — the public surface of the `app.graph` package.

## `app/tools/` — external actions

### `app/tools/web_search.py`
`web_search` — a LangChain `@tool`-decorated function wrapping
`TavilySearch`. Returns `list[dict]` with `"content"`/`"url"` keys (not
`Document` objects) so `save_findings` can build a `Finding` from the same
shape later.

### `app/tools/save_finding.py`
`save_findings` (plain `async def`, no `@tool` — it's called directly by a
node, never by the LLM, so the `@tool` wrapper's schema-injection machinery
doesn't apply here). For each finding dict, `await store.aput(namespace=(user_id, "findings"), key=f"{topic}_{timestamp}", value=finding)`.
Must stay `async` + `await` its store call — `AsyncPostgresStore` raises if
called synchronously from the event loop, unlike the old `InMemoryStore`,
which tolerated it silently.

### `app/tools/__init__.py`
Re-exports `save_findings` and `web_search`.

## `app/memory/store.py`
Deliberately empty placeholder. All store construction currently lives
inline in `main.py`, since there's only one entry point (the CLI) that needs
it. Revisit when a second entry point (the Phase 4 FastAPI SSE endpoint)
needs the same `AsyncPostgresStore`/`AsyncPostgresSaver` construction — that's
when pulling it into a shared helper here stops being premature abstraction.

## `app/streaming/events.py`
Two async functions bridging the compiled graph to the CLI, both taking
`graph: CompiledStateGraph` as an explicit parameter (never importing a
module-level graph constant):
- `stream_events(user_input, graph, config)` — starts a new run, streams
  `on_chat_model_stream` chunks to stdout token-by-token (handling both
  plain-string and Mistral's citation-list content shapes), then checks
  `await graph.aget_state(config)` for a pending interrupt (LangGraph does
  **not** emit an `on_interrupt` event through `astream_events` — the only
  way to detect a pause is inspecting `state.next` after the stream ends).
- `resume_graph(human_response, graph, config)` — same pattern, but starts
  from `Command(resume=human_response)` instead of a fresh input dict.

## `tests/`

Full Phase 3 (per `mentor-prompt.md`) test suite — see
[`tests.md`](tests.md) for per-test detail. Summary:

- `tests/test_hitl.py` — unit tests for `hitl_node`, monkeypatching
  `app.graph.nodes.interrupt` (patch where the name is *looked up*, i.e. in
  `nodes.py`'s namespace, not where `interrupt` is defined in
  `langgraph.types`) so the node can be exercised without a running graph.
  Covers approve (`"yes"`), reject (`"no"`), and edit (`"edit"`, which
  requires `Mock(side_effect=[...])` since `interrupt` is called twice in
  sequence within that one branch).
- `tests/test_nodes.py` — `researcher_node`'s memory/no-memory branches
  (monkeypatches the module-level `llm_with_tools`) and
  `save_findings_node`'s delegation to `save_findings`.
- `tests/test_memory.py` — cross-session continuity against a real
  `InMemoryStore` (not a fake): saves a finding, then verifies a later
  `researcher_node` call recalls it via the memory-recall prompt.
- `tests/test_load.py` — full-graph concurrency test (Phase 3's "load test:
  5 concurrent threads" item), run against `InMemorySaver`/`InMemoryStore`
  rather than node-level mocks, since checkpointer/store isolation across
  `thread_id`s can't be exercised at the single-node level. Two variants:
  cross-user isolation (5 distinct `user_id`s) and same-user write
  contention (5 `thread_id`s sharing one `user_id`'s namespace).

## Package init files

`app/__init__.py` and `app/memory/__init__.py` are minimal on purpose —
neither package needs to re-export anything from a sibling package.
(These were previously stray files literally named `" __init__.py"` with a
leading space — Python silently ignored them and treated `app`/`app.memory`
as implicit namespace packages instead. Renamed properly; `app/__init__.py`
also had dead leftover content, `from app.cli import run_cli`, reduced to a
bare module docstring since nothing in the codebase imports `run_cli` from
the bare `app` package — everything already imports `app.cli` directly.)
