# `app/api/` — FastAPI SSE Endpoints

Phase 4's second entry point: an HTTP client drives the same compiled graph
the CLI does, over Server-Sent Events. `main.py` owns the ASGI app and the
Postgres connection lifecycle; `routes.py` owns the two endpoints.

## `main.py`

The ASGI app itself — an entry point, invoked as `app.api.main:app`, not
re-exported through `app/api/__init__.py` (same convention as `app.cli`'s
`run_cli` staying off `app/__init__.py`).

Run with:
```
uv run uvicorn app.api.main:app --reload --loop app.api.main:loop_factory
```

### `def loop_factory() -> asyncio.AbstractEventLoop`

Uvicorn `--loop` hook, required on Windows.

- **Args:** none.
- **Returns:** a **loop instance**, not a factory-of-factories — this is the
  non-obvious part. Uvicorn's built-in named loops (`"asyncio"`/`"uvloop"`/
  `"auto"`) resolve through a two-level signature,
  `(use_subprocess: bool) -> Callable[[], AbstractEventLoop]`, but a custom
  `--loop module:callable` string is used **directly** as the final
  zero-arg factory — uvicorn's `Config.get_loop_factory()` skips the
  `use_subprocess` resolution step entirely for custom strings. Matching the
  built-in two-level signature here (an earlier attempt) makes
  `asyncio.Runner` call unbound methods on the `SelectorEventLoop` *class*
  instead of an instance — surfaces as `TypeError:
  BaseEventLoop.create_task() missing 1 required positional argument:
  'coro'`, a confusing error for a signature mismatch.
- **Behavior:** on `win32`, returns `asyncio.SelectorEventLoop()`; psycopg's
  async driver needs it — uvicorn's default `"asyncio"` loop picks
  `ProactorEventLoop` on Windows, under which
  `AsyncPostgresStore`/`AsyncPostgresSaver`'s connect just **hangs at
  startup with no exception** (same root cause `main.py`'s CLI entry point
  already worked around — see `issues-and-fixes.md`, Day 6). Elsewhere,
  returns `asyncio.new_event_loop()`. Not used in the Docker image — Linux
  containers get uvicorn's normal loop selection (which picks up `uvloop`
  for free via the `uvicorn[standard]` extra; this factory's non-Windows
  branch would bypass that).

### `async def lifespan(app: FastAPI) -> AsyncIterator[None]`

Open the store/checkpointer, build the graph, tear both down on shutdown.

- **Behavior:** `async with open_graph(settings.POSTGRES_URI) as graph:
  app.state.graph = graph; yield`. `open_graph` (`app/graph/postgres.py`) is
  the same helper `main.py`'s CLI entry point uses — previously each entry
  point opened `AsyncPostgresStore`/`AsyncPostgresSaver` independently; see
  `app-graph.md`'s `postgres.py` section for why that duplication existed
  and when it got fixed. A resource opened via `async with` can't outlive
  that block (Day 4's most important lesson — see `issues-and-fixes.md`),
  so the graph is built **once**, for the app's lifetime, not per-request —
  every request reads the same graph via the `get_graph` dependency
  (`routes.py`).

### `app`

Module-level `FastAPI(title="Personal Search Assistant API", lifespan=lifespan)`,
with `router` included. `init_sentry()` is called at import time, module
level — before the app object is even constructed.

## `routes.py`

### `def get_graph(request: Request) -> CompiledStateGraph`

FastAPI dependency returning `request.app.state.graph` — the compiled graph
the lifespan built. Routed through a dependency rather than read directly
so tests can `app.dependency_overrides[get_graph] = lambda: test_graph`
without booting the real Postgres-backed lifespan at all (see
`tests/test_api.py`).

### `async def _sse_format(events) -> AsyncGenerator[dict, None]`

Wrap a `(kind, payload)` event generator (from `app.streaming.events`) into
SSE-ready dicts.

- **Args:** `events` — an `AsyncGenerator[tuple[str, str | None], None]`,
  i.e. what `stream_events`/`resume_graph` yield.
- **Yields:** `{"event": kind, "data": <json string>}` dicts —
  `sse_starlette.EventSourceResponse` turns each into the `event: ...\ndata:
  ...\n\n` wire format itself; this function doesn't hand-format SSE text.
- **Behavior:** wraps the `async for` in `try`/`except Exception`. A
  mid-stream exception can't become an HTTP error response — the 200 status
  and headers are already sent by the time any token has streamed — so it's
  caught here and turned into a terminal `{"event": "error", ...}` frame
  instead of silently truncating the connection. `except Exception` (not a
  narrower type) is deliberate: this is the SSE wire protocol's boundary,
  and *any* failure needs to become a client-visible event, not just
  specific expected ones.

### `@router.post("/") async def start_run(body: StartRunRequest, graph=Depends(get_graph)) -> EventSourceResponse`

Start a new research run and stream its output as SSE.

- **Behavior:** generates `thread_id = str(uuid.uuid4())`, builds the config
  via `build_run_config(thread_id, body.user_id, body.topic)`, returns
  `EventSourceResponse(_sse_format(stream_events(...)), headers={"X-Thread-Id":
  thread_id})`. The client must capture that header — it's the only place
  the generated `thread_id` is surfaced — and send it back on every
  `resume` call this run produces.

### `@router.post("/{thread_id}/resume") async def resume_run(thread_id: uuid.UUID, body: ResumeRunRequest, graph=Depends(get_graph)) -> EventSourceResponse`

Resume a run paused at a HITL interrupt and stream its output as SSE.

- **Behavior:** builds the config via `build_run_config(str(thread_id),
  body.user_id)` (no `topic` — unknown at resume time), then
  `state = await graph.aget_state(config)`. Two checks before opening the
  stream, both because there's no way to turn a failure into a proper error
  response once streaming has started (same reasoning as `_sse_format`'s
  exception handling above):
  1. If `not (state.tasks and state.tasks[0].interrupts)`, raises
     `HTTPException(404, ...)` — covers three cases identically:
     `thread_id` never existed, already ran to completion, or was already
     resumed.
  2. If `body.user_id != state.metadata.get("user_id")`, raises
     `HTTPException(403, ...)`. `configurable.user_id` is **not** preserved
     in `state.config` — LangGraph's checkpointer only keeps
     `thread_id`/`checkpoint_ns`/`checkpoint_id` there — but every
     non-reserved `configurable` key **is** copied into checkpoint
     `metadata` automatically, which is what makes this check possible:
     `state.metadata["user_id"]` is the authoritative value from when the
     run actually started, independent of whatever the client claims on
     resume. Verified empirically (not assumed) before relying on it —
     `state.config`'s omission of `user_id` is easy to expect wrongly.

## `__init__.py`

Re-exports `router` and `get_graph` — the reusable pieces (mounted by
`main.py`, overridden by tests). The `app` object itself is not re-exported
here; see the note on `main.py` above.
