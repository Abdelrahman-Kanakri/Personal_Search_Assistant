# `app/` — Package Root

Top-level package. Holds the interactive CLI REPL (`cli.py`) and re-exports
`run_cli` for `from app import run_cli`. Everything else lives in
subpackages:

| Subpackage | Purpose |
| --- | --- |
| [`core/`](app-core.md) | Settings singleton, structured logging |
| [`graph/`](app-graph.md) | LangGraph state, nodes, edges, graph assembly |
| [`tools/`](app-tools.md) | `@tool` functions callable by the LLM |
| [`streaming/`](app-streaming.md) | Async streaming + HITL resume helpers |
| [`memory/`](app-memory.md) | Cross-session memory layer (stub) |

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
  1. Generates a fresh `thread_id` (`uuid.uuid4()`) per run, so the
     checkpointer keeps each topic's state independent.
  2. Builds a `RunnableConfig` with `thread_id` and `user_id` — `user_id` is
     required by `save_findings` to scope the store namespace.
  3. Calls `stream_events(user_input, graph, config)`. A non-`None` return
     means the graph paused at a HITL interrupt; the inner `while` loop
     prints the interrupt prompt, reads the human's response, and calls
     `resume_graph` — repeating until the graph reaches `END` (`None`
     returned).
  4. Asks whether to start another run; anything other than `yes`/`y` exits
     the outer loop.

## `__init__.py`

Re-exports `run_cli` from `app.cli`, so callers can `from app import
run_cli` instead of reaching into the submodule.
