# `app/` — Package Root

Top-level package. Holds the interactive CLI REPL (`cli.py`); the module
itself is a bare docstring, deliberately re-exporting nothing (see
`__init__.py` below). Everything else lives in subpackages:

| Subpackage | Purpose |
| --- | --- |
| [`core/`](app-core.md) | Settings singleton, structured logging, Sentry init, shared `RunnableConfig` builder |
| [`graph/`](app-graph.md) | LangGraph state, nodes, edges, graph assembly |
| [`tools/`](app-tools.md) | `@tool` functions callable by the LLM |
| [`streaming/`](app-streaming.md) | Async streaming + HITL resume helpers |
| [`api/`](app-api.md) | FastAPI SSE endpoints — the API entry point |
| [`schemas/`](app-schemas.md) | Pydantic models shared by the CLI, API, and streaming layers |

`app/memory/` (a stub package) was removed on Day 6 — cross-session memory
lives directly in `app/graph/nodes.py` and `app/tools/save_finding.py`
instead; see those docs, not a `memory/` package.

## `cli.py`

Interactive REPL: accepts a research topic, streams the agent's output
token-by-token, surfaces any HITL interrupt for user approval, and resumes
the graph until it reaches `END`.

Import-time side effect: sets `OPENSSL_CONF`, `LANGSMITH_API_KEY`,
`LANGSMITH_ENDPOINT`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` in
`os.environ` from `settings` — these are read by LangSmith's tracing client
and by pyarrow, both of which only look at env vars, not application config
objects, so this module has to push them in before any graph code runs.

### `USER_ID`

Module-level constant, `"default_user"`. Hardcoded because the CLI is
single-user; swap for real auth (session-derived user id) when this becomes
multi-user.

### `async def run_cli(graph: CompiledStateGraph) -> None`

Main REPL loop — each iteration is one complete research run.

- **Args:**
  - `graph`: the compiled, checkpointer- and store-wired LangGraph graph
    (from `build_graph`).
- **Returns:** `None` — loops until the user answers `exit` at the topic
  prompt, or declines to start another run.
- **Behavior:**
  1. Reads the topic, then generates a fresh `thread_id` (`uuid.uuid4()`)
     per run, so the checkpointer keeps each topic's state independent.
  2. Builds the config via `app.core.build_run_config(thread_id, USER_ID,
     user_input)` — topic is known by this point, so it flows into
     LangSmith's `metadata` too, not just `configurable`.
  3. Calls `stream_events(user_input, graph, config)` and iterates the
     `(kind, payload)` tuples it yields: `"token"` prints incrementally,
     `"interrupt"` prints the prompt, reads the human's response, and
     reassigns `stream_result = resume_graph(...)` to keep looping, `"done"`
     ends the inner loop.
  4. Asks whether to start another run; anything other than `yes`/`y` exits
     the outer loop.

## `__init__.py`

Bare module docstring — deliberately re-exports nothing. (Previously had a
dead `from app.cli import run_cli` re-export; removed on Day 3 since nothing
in the codebase imported `run_cli` from the bare `app` package — everything
imports `app.cli` directly. `app.api`, by contrast, *does* re-export its
public surface — see [`app-api.md`](app-api.md) — since `router`/`get_graph`
genuinely have callers outside their own module.)
