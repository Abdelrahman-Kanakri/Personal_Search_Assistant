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
| [`app/memory/`](docs/app-memory.md) | Cross-session memory layer (package files are empty placeholders; the logic itself lives inline in `app/graph/nodes.py`) |
| [`tests/`](docs/tests.md) | Pytest unit tests |

All per-directory docs live in [`docs/`](docs/), alongside
[`docs/architecture.md`](docs/architecture.md) (file-by-file architecture
map) and [`docs/issues-and-fixes.md`](docs/issues-and-fixes.md) (day-by-day
build history).

## Running

```bash
uv run main.py
```

Requires a reachable Postgres instance (`POSTGRES_URI` in `.env`) — it backs
both the LangGraph checkpointer (in-progress run state, keyed by
`thread_id`) and the store (cross-session findings, keyed by `user_id`).

## `main.py` — entry point

### `conn_string`

Module-level constant, `settings.POSTGRES_URI`. Shared connection string:
the store and the checkpointer are two logical stores on the same Postgres
instance.

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

`asyncio.run(main())` — standard async entry-point guard.
