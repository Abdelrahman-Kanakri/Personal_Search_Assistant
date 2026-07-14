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

- **Behavior:** mirrors `main.py`'s CLI lifecycle — `async with
  (AsyncPostgresStore.from_conn_string(...) as store,
  AsyncPostgresSaver.from_conn_string(...) as checkpointer):`, `setup()` on
  both, `build_graph(store, checkpointer)`, stored on `app.state.graph`,
  then `yield`. A resource opened via `async with` can't outlive that block
  (Day 4's most important lesson — see `issues-and-fixes.md`), so the graph
  is built **once**, for the app's lifetime, not per-request — every
  request reads the same graph via the `get_graph` dependency
  (`routes.py`).
- **Known duplication:** this connection-opening block is now written twice
  — here and in the root `main.py`. `docs/architecture.md`'s `app/memory/`
  entry (before that stub package was removed) predicted this exact
  moment as the trigger for pulling store/checkpointer construction into a
  shared helper. Not yet done — flagged here as a legitimate follow-up, not
  silently accepted as fine.

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
  `state = await graph.aget_state(config)`. If `not (state.tasks and
  state.tasks[0].interrupts)`, raises `HTTPException(404, ...)` **before**
  opening the stream — covers three cases identically: `thread_id` never
  existed, already ran to completion, or was already resumed. This check
  has to happen up front; `resume_graph` itself has undefined behavior if
  called against a thread with no pending interrupt, and once the stream
  has started there's no way to turn it into a proper 404 anymore (same
  reasoning as `_sse_format`'s exception handling above).

## `__init__.py`

Re-exports `router` and `get_graph` — the reusable pieces (mounted by
`main.py`, overridden by tests). The `app` object itself is not re-exported
here; see the note on `main.py` above.
