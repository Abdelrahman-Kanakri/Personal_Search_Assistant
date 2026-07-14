# Architecture — File-by-File Map

A guide to every Python file in the project: what it's for, what it owns, and
how it connects to the rest of the graph. Read this to reorient quickly
after time away, before diving into any one file.

## Entry points

Two now — the CLI (`main.py`) and the API (`app/api/main.py`). Both open
their own Postgres store/checkpointer via `async with` and build their own
graph; see `app/api/main.py`'s doc note below for the resulting duplication
this created, flagged but not yet resolved.

### `main.py`
Owns the Postgres connection lifecycle for the whole CLI session. Calls
`init_sentry()` at module level, before anything else. `async def main()`
opens `async with (AsyncPostgresStore.from_conn_string(...) as store, AsyncPostgresSaver.from_conn_string(...) as checkpointer):`,
awaits `setup()` on both, calls `build_graph(store, checkpointer)` (a plain
sync call), then `await run_cli(graph)` — all nested inside the `with` block,
since neither connection may be used once that block exits.
`if __name__ == "__main__": asyncio.run(main(), loop_factory=lambda:
asyncio.SelectorEventLoop(selectors.SelectSelector()))` bridges the sync
script entry point into the async world — the explicit `loop_factory` is a
Windows fix: psycopg's async driver needs `SelectorEventLoop`, not Windows'
default `ProactorEventLoop` (see `issues-and-fixes.md`, Day 6). The API's
`app/api/main.py` needed the identical fix, but via uvicorn's own `--loop`
hook instead, since uvicorn — not this module — owns the event loop there.

### `app/api/main.py` / `app/api/routes.py`
The second entry point — a FastAPI app exposing the same graph over SSE.
Detailed in [`app-api.md`](app-api.md); summary: `main.py` owns the ASGI app
and the (once again duplicated) Postgres connection lifespan, plus the
`loop_factory` uvicorn `--loop` hook for the same Windows psycopg issue as
the CLI. `routes.py` exposes `POST /runs/` (start) and `POST
/runs/{thread_id}/resume` (resume), both streaming `sse_starlette.EventSourceResponse`
built from `app.streaming.events`' `(kind, payload)` generators. Deviates
from `mentor-prompt.md`'s original single `GET /research/stream?topic=X&thread_id=Y`
design — deliberately: the resume step needs to carry the human's response
text in a body, which a bodyless `GET` can't do cleanly.

## `app/cli.py`
The interactive read-eval loop. `run_cli(graph: CompiledStateGraph)` loops
forever: reads the topic, generates a fresh `thread_id` per research topic
(so checkpointer state doesn't bleed between unrelated topics), builds the
config via `app.core.build_run_config(thread_id, USER_ID, user_input)` —
shared with the API, not built inline here anymore — and drives
`stream_events`/`resume_graph` from `app/streaming/events.py`, printing the
interrupt prompt and looping on `resume_graph` until the graph reaches
`END`.

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

### `app/core/observability.py`
`init_sentry()` — calls `sentry_sdk.init(dsn=settings.SENTRY_DSN,
traces_sample_rate=1.0)`. Safe to call unconditionally: `dsn=None` is a
documented Sentry no-op, so dev environments without `SENTRY_DSN` set are
unaffected. Called once, at module level, from both `main.py` and
`app/api/main.py`.

### `app/core/run_config.py`
`build_run_config(thread_id, user_id, topic=None) -> RunnableConfig` —
extracted so `app/cli.py` and `app/api/routes.py` stop building this dict
independently. Puts `thread_id`/`user_id` under `configurable` (where the
checkpointer and `save_findings` read them) and `tags=[f"user:{user_id}"]`
/ `metadata={"topic": topic}` at the config's **top level** (where LangSmith
reads them to label a trace) — a distinction worth remembering, since
`configurable` and top-level are easy to conflate but read by entirely
different consumers.

### `app/core/__init__.py`
Re-exports `settings`, `get_logger`, `init_sentry`, and `build_run_config` —
the only import path the rest of the app should use (`from app.core import
settings`, never `from app.core.config import Settings` directly).

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

## `app/memory/` (removed, Day 6)
Was a deliberately empty placeholder package. Removed once it became clear
cross-session memory already lives entirely in `app/graph/nodes.py` and
`app/tools/save_finding.py` — there was nothing to move into it. The
originally-planned trigger for *this* kind of shared-helper extraction (a
second entry point needing the same store/checkpointer construction) has
since arrived with `app/api/main.py` — but store/checkpointer construction
duplication went unresolved rather than into a revived `app/memory/`; see
`app-api.md`'s note on `lifespan`.

## `app/streaming/events.py`
Two async **generator** functions bridging the compiled graph to any
caller, both taking `graph: CompiledStateGraph` as an explicit parameter
(never importing a module-level graph constant), both yielding `(kind,
payload)` tuples — `"token"`/`"interrupt"`/`"done"` — rather than returning
a single value (refactored Day 6, for API-readiness: a `return` can't be
consumed incrementally by an SSE response, a `yield` can):
- `stream_events(user_input, graph, config)` — starts a new run, yields
  `("token", chunk)` for each `on_chat_model_stream` chunk (handling both
  plain-string and Mistral's citation-list content shapes), then checks
  `await graph.aget_state(config)` for a pending interrupt (LangGraph does
  **not** emit an `on_interrupt` event through `astream_events` — the only
  reliable way to detect a pause is `state.tasks and
  state.tasks[0].interrupts`, not `state.next` — see the HITL edit-flow
  entry in `issues-and-fixes.md` for why `.next` specifically is
  unreliable on a second interrupt within one node's replay) and yields
  `("interrupt", value)` or `("done", None)` accordingly.
- `resume_graph(human_response, graph, config)` — same pattern, but starts
  from `Command(resume=human_response)` instead of a fresh input dict.

Consumed by both `app/cli.py` (`async for kind, payload in ...`) and
`app/api/routes.py` (wrapped into SSE dicts by `_sse_format`) — the same
protocol, two transports.

## `app/schemas/models.py`
`Event(BaseModel)` — `type: Literal["token", "interrupt", "done", "error"]`,
`content: str | None` — the wire representation of one `(kind, payload)`
tuple from `app/streaming/events.py`; `"error"` is added by
`app/api/routes.py`'s `_sse_format`, never yielded by `stream_events`/
`resume_graph` themselves. Also `StartRunRequest`/`ResumeRunRequest`, the
API's two request bodies. Full field tables in
[`app-schemas.md`](app-schemas.md).

## `app/api/` — FastAPI SSE endpoints
Phase 4's second entry point — see [`app-api.md`](app-api.md) for full
detail (the `loop_factory` uvicorn `--loop` contract gotcha, the
`get_graph` dependency for testability, the `_sse_format` exception-to-event
boundary, the 404 pre-check on resume). `main.py` covered under "Entry
points" above.

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
- `tests/test_api.py` — Phase 4 integration tests for `app/api/routes.py`,
  driven over HTTP via `httpx.AsyncClient` + `ASGITransport`, with
  `get_graph` overridden to a test graph so Postgres/the real `lifespan`
  never run. Covers start→interrupt, resume→done, and resume-with-no-
  pending-interrupt→404.

## Deployment

### `Dockerfile`
uv-based (`FROM python:3.14-slim`, copies the `uv`/`uvx` binaries from
astral's published image rather than installing pip/curl into the runtime
image), two-stage `uv sync` (dependencies-only layer cached separately from
the app-code layer), `CMD uv run uvicorn app.api.main:app --host 0.0.0.0
--port 8000` — **no** `--loop app.api.main:loop_factory` here, deliberately:
that factory's non-Windows branch is a plain `asyncio.new_event_loop()`,
which would silently forgo the `uvloop` performance uvicorn's normal `"auto"`
loop selection gets for free on Linux (`uvicorn[standard]` bundles it as a
non-Windows extra). The `--loop` override only matters on the Windows dev
host.

### `.dockerignore`
Added alongside the `Dockerfile` — without it, `COPY . .` would have pulled
`.venv` (host binaries, wrong platform for the container), `.git`, and
`logs/` into the image.

## Package init files

`app/__init__.py` is minimal on purpose — the package doesn't need to
re-export anything from a sibling package. (Previously a stray file
literally named `" __init__.py"` with a leading space — Python silently
ignored it and treated `app` as an implicit namespace package instead.
Renamed properly; also had dead leftover content, `from app.cli import
run_cli`, reduced to a bare module docstring since nothing in the codebase
imports `run_cli` from the bare `app` package — everything already imports
`app.cli` directly.)

`app/api/__init__.py`, `app/schemas/__init__.py`, and
`app/streaming/__init__.py` were empty placeholders until this pass — filled
in following the same re-export convention as `app/core/__init__.py`,
`app/graph/__init__.py`, and `app/tools/__init__.py` (`app/api/__init__.py`
re-exports `router`/`get_graph`, not the `app` ASGI object itself — same
"entry points aren't re-exported through a parent package" convention as
`app/__init__.py` above).
