# Personal Search Assistant

A LangGraph research agent with human-in-the-loop (HITL) approval and
cross-session memory. Given a topic, it checks previously saved findings,
fills any gaps with a live Tavily web search, produces a cited Markdown
answer, pauses for human approval, and — on approval — persists the answer
so future runs on related topics can reuse it instead of re-searching.

## Package map

| Path | Contents |
| --- | --- |
| [`app/`](docs/app.md) | Package root: CLI REPL loop, top-level re-exports |
| [`app/core/`](docs/app-core.md) | Settings (`pydantic-settings`) and structured JSON logging |
| [`app/graph/`](docs/app-graph.md) | LangGraph state schema, nodes, routing edges, graph assembly |
| [`app/tools/`](docs/app-tools.md) | `@tool`-decorated functions the LLM can call |
| [`app/streaming/`](docs/app-streaming.md) | Async event streaming + HITL resume helpers |
| [`app/api/`](docs/app-api.md) | FastAPI SSE endpoints — the second (HTTP) entry point |
| [`app/schemas/`](docs/app-schemas.md) | Pydantic request/response/event models |
| [`tests/`](docs/tests.md) | Pytest unit + integration tests |

All per-directory docs live in [`docs/`](docs/), alongside
[`docs/architecture.md`](docs/architecture.md) (file-by-file architecture
map) and [`docs/issues-and-fixes.md`](docs/issues-and-fixes.md) (day-by-day
build history).

## Running

Two entry points, both requiring a reachable Postgres instance
(`POSTGRES_URI` in `.env`) — it backs both the LangGraph checkpointer
(in-progress run state, keyed by `thread_id`) and the store (cross-session
findings, keyed by `user_id`).

### CLI

```bash
uv run main.py
```

### API

```bash
uv run uvicorn app.api.main:app --reload --loop app.api.main:loop_factory
```

The `--loop app.api.main:loop_factory` is **required on Windows** — psycopg's
async driver hangs (no exception) under uvicorn's default event loop there.
See [`docs/app-api.md`](docs/app-api.md) for why. Not needed, and not used,
inside the Docker image (Linux gets uvicorn's normal loop selection, which
picks up `uvloop` for free).

### Docker

```bash
docker build -t personal-search-assistant .
docker run --env-file .env -p 8000:8000 personal-search-assistant
```

Runs the API only; point `POSTGRES_URI` in `.env` at a reachable Postgres
instance (e.g. `host.docker.internal` if it's running on the host).

## `main.py` — CLI entry point

### `conn_string`

Module-level constant, `settings.POSTGRES_URI`. Shared connection string:
the store and the checkpointer are two logical stores on the same Postgres
instance. `init_sentry()` is called at module level, before this.

### `async def main() -> None`

Opens `AsyncPostgresStore` and `AsyncPostgresSaver` as async context
managers over `conn_string`, calls `.setup()` on each (idempotent — creates
the underlying tables/indexes on first run, no-op afterward), builds the
compiled graph via `build_graph(store, checkpointer)`, and hands off to
`run_cli(graph)`.

- **Args:** none.
- **Returns:** `None` — runs until the CLI loop exits (user chooses not to
  start another run).
- **Behavior:** the `async with` block guarantees both Postgres connections
  close cleanly on exit, including on unhandled exceptions or
  `KeyboardInterrupt`.

### `if __name__ == "__main__":`

`asyncio.run(main(), loop_factory=lambda:
asyncio.SelectorEventLoop(selectors.SelectSelector()))` — the explicit
`loop_factory` is a Windows fix: psycopg's async driver needs
`SelectorEventLoop`, not Windows' default `ProactorEventLoop` (see
`docs/issues-and-fixes.md`, Day 6).

The API's entry point, `app/api/main.py`, is documented in
[`docs/app-api.md`](docs/app-api.md).
