# Issues and Fixes — Full History (Day 1–4)

Reconstructed from git history and session notes. Each entry: the symptom,
the root cause, and the fix actually applied. Read this before resuming work
to reload context without re-deriving it.

---

## Day 1 — Project structure, config, tools (`9fbd769`, `fa90f9c`)

Built: project skeleton, `AgentState`/`Finding` schema, `config.py`,
`web_search` tool, `save_finding` tool.

1. **`LANGSMITH_TRACING` bool assigned straight into `os.environ`.**
   `os.environ` only accepts strings; `Settings.LANGSMITH_TRACING` is `bool`.
   **Fix:** `os.environ["LANGSMITH_TRACING"] = str(settings.LANGSMITH_TRACING)`.

2. **Wrong assumption: "pydantic-settings populates `os.environ`
   automatically."** It does not — it only populates the `Settings` object's
   own attributes. Any third-party library that reads `os.environ` directly
   (Tavily, Mistral, LangSmith) needs the value copied over explicitly, one
   line per var, in whichever module uses that library.
   **Fix:** explicit `os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY`
   (and equivalents) in each tool/node module, not relied on globally.

3. **`InjectedStore` / `RunnableConfig` injection pattern learned, not a bug:**
   `store` and `config` params on a `@tool`-decorated function are hidden
   from the LLM's tool schema and filled by LangGraph/LangChain at runtime —
   the LLM never sees or fills them itself.

---

## Day 2 — Nodes, edges, graph build (`8061ccb`)

Built: `researcher_node`, `hitl_node`, `route_from_research`,
`route_from_hitl`, `build.py` graph assembly; `Finding.url` switched to
`Optional[str]`.

1. **`structured_llm = llm.with_structured_output`** — missing the `()` call
   and schema argument; assigns the *method object*, not a result.
   **Fix:** `llm.with_structured_output(SomeSchema)` (ultimately `bind_tools`
   was used instead for `researcher_node`, since the LLM needs to *act*, not
   produce fixed-schema data — `with_structured_output` and `bind_tools` are
   mutually exclusive on one invocation).

2. **`ChatMistralAI` never saw an API key** — `pydantic_settings` doesn't set
   `os.environ`, and LangChain model constructors read env vars directly.
   **Fix:** `os.environ["MISTRAL_API_KEY"] = settings.MISTRAL_API_KEY` before
   instantiating the model.

3. **`datetime.datetime.now()` → `AttributeError`.** `from datetime import
   datetime` imports the class itself, so `datetime.datetime` is an
   attribute lookup on the class, which doesn't exist.
   **Fix:** `datetime.now()`.

4. **`.format(topic=topic)` called on a prompt string with no `{topic}`
   placeholder** — silent no-op (topic was already being delivered via a
   separate `HumanMessage`).
   **Fix:** removed the redundant `.format()` call entirely.

5. **Import typo:** `from app.tool import save_findings` (singular) →
   `ImportError`. **Fix:** `from app.tools import save_findings`.

6. **`@tool`-wrapped function called directly from a node** →
   `TypeError: 'StructuredTool' object is not callable` (calling `.invoke()`
   instead also breaks — `InjectedStore` validation logic doesn't apply
   outside a `ToolNode`). **Fix:** removed `@tool` from `save_findings` since
   a node calls it directly — the LLM never decides to invoke it, so the
   tool-schema wrapper serves no purpose here.

7. **`store` arrived as `None` inside nodes** → `AttributeError: 'NoneType'
   object has no attribute 'put'`. LangGraph only injects `store` into node
   functions when one was passed to `compile()`.
   **Fix:** `builder.compile(checkpointer=..., store=InMemoryStore())`.

8. **`save_findings` reads `config["configurable"]["user_id"]`** — missing
   from the CLI's config dict → `KeyError` at save time.
   **Fix:** always include `user_id` alongside `thread_id` in `RunnableConfig`.

9. **Node returned a string instead of a dict** —
   `return save_findings(...)` (the tool's confirmation string) instead of a
   partial state dict → `InvalidUpdateError: Expected dict, got Saved 1
   findings...`. **Fix:** call the tool, optionally print its result, then
   `return {}` — a node's return value must always be a dict, even an empty one.

10. **Mistral citation responses: `content` can be a `list`, not a `str`** —
    needed to extract text before building/saving a `Finding`. **Fix:**
    branch on `isinstance(content, list)` and join the `"text"` parts.

---

## Day 3 — Restructure, streaming, CLI, logging (`18cca7c`, `c792350`, `d0b0fe3`)

Built: renamed/modularized file layout, `streaming/events.py`, `cli.py`,
`core/logging.py` (structlog + stdlib), Claude skills setup.

1. **`for event in graph.astream_events(...)`** (missing `async`) →
   `TypeError` at runtime. **Fix:** `async for`.

2. **`event["data"]["text"]`** — wrong key. **Fix:**
   `event["data"]["chunk"].content`.

3. **`astream_events` never emits an `on_interrupt` event**, despite the
   original implementation checking for one. When `interrupt()` fires inside
   a node, LangGraph silently ends the async generator — the interrupt value
   is only in the checkpoint, not streamed as an event.
   **Fix:** after the `async for` loop ends, call
   `state = await graph.aget_state(config)`; if `state.next` is non-empty the
   graph is paused, and `state.tasks[0].interrupts[0].value` is the value
   passed to `interrupt()`.

4. **`RunnableConfig(**config.dict(), thread_id=...)`** — wrong; it's a
   `TypedDict`, not a Pydantic model. **Fix:** build/assign the dict directly.

5. **HITL resume loop bugs (three separate ones, same area):**
   `resume_graph` called with the interrupt *prompt* instead of the human's
   *answer*; `while stream_result is not None` never reassigning
   `stream_result` inside the loop → infinite loop; `resume_result` checked
   for `is not None` before ever being assigned → `NameError`.

6. **`version="v1"`** on `astream_events` — outdated; **fix:** `"v2"`.

7. **`SqliteSaver` is sync-only; `AsyncSqliteSaver` needs a running event
   loop at construction time** — calling it at module level (before
   `asyncio.run`) → `RuntimeError: no running event loop`.
   **Fix (for dev at the time):** `MemorySaver()` — sync/async-compatible,
   no setup step, acceptable to lose state on restart during development.

8. **`researcher_node` was sync, using `.invoke()`** — LangGraph wraps sync
   node functions in `run_in_executor`, and LangChain's streaming callbacks
   don't cross that thread boundary, so `on_chat_model_stream` events never
   fired and nothing printed. **Fix:** `async def researcher_node`, `await
   llm_with_tools.ainvoke(...)`.

9. **Leading-space filenames:** a directory literally named `" app"` (with a
   leading space) and several `__init__.py` files also had a leading space
   in the filename. **Fix at the time:** `mv " app" app` and renamed the
   `__init__.py` files — this fix didn't fully stick: `app/__init__.py` and
   `app/memory/__init__.py` still had stray space-prefixed duplicates
   sitting alongside as of Day 4's documentation pass (harmless, since `app`
   worked anyway as an implicit namespace package). **Finally resolved on
   Day 4**, while writing this doc: both stray files renamed properly;
   `app/__init__.py`'s dead leftover content (`from app.cli import run_cli`,
   unused anywhere in the codebase) reduced to a bare module docstring.

10. **`langchain_mistralai` missing from `pyproject.toml`.** **Fix:**
    `uv add langchain-mistralai`.

11. **Wrong env var name `MISTRALAI_API_KEY`** (extra "AI"). **Fix:** pass
    `api_key=settings.MISTRAL_API_KEY` directly to the `ChatMistralAI`
    constructor instead of relying on an env var lookup.

12. **Missing edge `web_search → researcher_node`** — graph had no way to
    return control to the researcher after a tool call.

13. **Edge router returned `"search_web"` but the node was registered as
    `"web_search"`** — name mismatch between `route_from_research`'s return
    value and `add_node`'s registered name.

14. **`app/main.py` edited instead of the real entry point** — the actual
    entry point is the root `main.py`, not a same-named file inside the
    package.

15. **`cli.py`'s config dict was missing `user_id`** — `save_findings` needs
    it for the store namespace → `KeyError` at save time (same class of bug
    as Day 2, item 8, resurfacing after the CLI was rebuilt during the
    restructure).

16. **Logging: missing `logs/` directory crashed the entire app at import
    time**, not just logging. `logging.basicConfig(filename="logs/log.log")`
    constructs a `FileHandler` eagerly at import time; since
    `app/core/__init__.py` imports `get_logger`, and nearly every module
    imports `from app.core import settings`, one missing directory broke
    every downstream import in the project.
    **Fix:** `mkdir -p logs/`, added `logs/` to `.gitignore`.

17. **`structlog.Formatter(...)`** — doesn't exist (`AttributeError`); same
    blast radius as #16 since it also lives in `app/core/logging.py`.
    **Fix:** `logging.Formatter(...)`.

18. **Duplicate fields in every log line** — `level`/`logger`/`timestamp`
    appeared twice: once written into the JSON by structlog's processors,
    once again as a text prefix from `logging.basicConfig`'s default
    formatter wrapping around the JSON string.
    **Fix:** gave the root handler the same bare `Formatter("%(message)s")`
    as the named per-channel handlers, so it passes the JSON through instead
    of prefixing it. **Known trade-off (left open):** third-party loggers
    (httpx, urllib3, etc.) bypass structlog's processors entirely and now
    log with *zero* metadata under the bare formatter, having previously at
    least kept a timestamp+level+name text prefix. Proposed but not yet
    applied: give the app's own shared channel a real name (e.g.
    `get_logger("app")`, `propagate=False`) and leave the literal root
    logger on the old prefixed text format as a catch-all for third-party libs.

---

## Day 4 — HITL fix, tests, Postgres migration (`a0ca7aa`, `198f882`, `c2e634e`, `56649c5`)

Built: HITL reject-loop fix, `test_hitl.py`, full migration from
`InMemoryStore`/`MemorySaver` to `AsyncPostgresStore`/`AsyncPostgresSaver`.

1. **`route_from_hitl` checked `state["human_response"] == "yes"` exactly**
   — typing `"y"` at the CLI prompt silently mis-routed back to
   `researcher_node`. **Fix:** `if state["human_response"] in ("yes", "y")`.

2. **Real rejection crashed:** `httpx.HTTPStatusError: ... Expected last
   role User or Tool ... but got assistant`. Root cause: `hitl_node` only
   returned `{"human_response": approved}` on rejection — nothing appended
   to `messages`, so the message list still ended on the researcher's own
   prior `AIMessage`, and Mistral's API rejects any request not ending on
   `user`/`tool`. **Fix:** `hitl_node` now also returns
   `{"messages": [HumanMessage(content="Human rejected the findings...")]}`
   on rejection. **Principle:** edge functions (`edges.py`) are pure
   routers — they return a node-name string and cannot write state; only a
   node's returned dict, merged through the state's reducer, can.

3. **`ModuleNotFoundError: No module named 'app'` under `uv run pytest`.**
   pytest's default import mode inserts the first ancestor directory
   *without* `__init__.py` into `sys.path`; since `tests/` has none, pytest
   added `tests/` itself, not the project root. **Fix:** added
   `[tool.pytest.ini_options]\npythonpath = ["."]` to `pyproject.toml`.

4. **Testing `hitl_node`'s `interrupt()` call** requires monkeypatching,
   since `interrupt()` only behaves correctly inside a running graph.
   **Gotcha:** patch where the name is *looked up*
   (`app.graph.nodes.interrupt`, since `nodes.py` does
   `from langgraph.types import interrupt`), not where it's defined
   (`langgraph.types.interrupt`).

5. **`async with` closes its resources the instant the block's dynamic
   scope ends** — identically whether that's from falling through, a
   `return` inside the block, or an exception. First `main.py` draft called
   `build_graph(...)`/`run_cli(...)` outside (dedented from) the `async
   with` that opened the Postgres connections — both were already closed
   before the graph was even built. **Fix:** nested both calls inside the
   `with` block. This is the single most important rule from this
   migration — a resource opened via `async with` can never be handed back
   to a caller still-open once that block ends.

6. **A function used as a type annotation** — `graph: build_graph` instead
   of `graph: CompiledStateGraph`. Doesn't crash (Python doesn't enforce
   annotations at runtime) but is semantically nonsense.
   **Fix:** `from langgraph.graph.state import CompiledStateGraph` (found
   via `inspect.signature(StateGraph.compile)` — not re-exported from
   `langgraph.graph`'s top-level `__init__`).

7. **`from_conn_string` called as an instance method** on a same-named
   parameter instead of the class. **Fix:**
   `AsyncPostgresStore.from_conn_string(...)` /
   `AsyncPostgresSaver.from_conn_string(...)` — both are classmethods.

8. **`build_graph`'s params typed against the concrete Postgres classes**,
   even though the function body never calls a Postgres-specific method on
   either — it only forwards them into `builder.compile(...)`.
   **Fix:** typed against the abstract base classes instead —
   `store: BaseStore`, `checkpointer: BaseCheckpointSaver` — costs nothing
   and buys back testability (can hand it `InMemoryStore`/`MemorySaver` in
   unit tests) and backend-swap flexibility.

9. **Sync `store.put(...)` inside the event loop** →
   `asyncio.exceptions.InvalidStateError: Synchronous calls to
   AsyncPostgresStore detected in the main event loop`. `InMemoryStore`
   silently tolerated this; `AsyncPostgresStore` enforces async-only access
   and raises. **Fix:** `store.aput(...)`.

10. **`aput(...)` called without `await`, in a plain `def`** →
    `RuntimeWarning: coroutine 'AsyncBatchedBaseStore.aput' was never
    awaited`. `save_findings` created a coroutine object and discarded it —
    findings were silently never persisted, even though the function's
    return string claimed success. **Fix:** `save_findings` → `async def`,
    added `await` before `store.aput(...)`.

11. **Stale imports/docstrings left over from the migration** —
    `MemorySaver` import, unused `conn_string`/`settings` in `build.py`, and
    a module docstring still describing the old module-level `graph`
    constant and "build at import time" behavior. **Fix:** removed the dead
    lines, rewrote the docstring to describe the current design.

12. **Docker Postgres container was stopped, not gone**, between sessions —
    re-running `docker run` would have created a conflicting duplicate.
    **Fix:** `docker start research-assistant-pg` (data persists across
    stop/start). Check status: `docker ps -a --filter name=research-assistant-pg`.

13. **`git pull` refused to merge** — local branch was 1 commit behind
    `origin/main` (a remote rename in `nodes.py`, also made independently
    locally, uncommitted). Git only objects to merging over *uncommitted*
    changes. **Fix:** commit local changes first, then pull/merge.

**End state:** migration fully done and runtime-verified — a complete CLI
research run (topic → stream → HITL approve → save) works end-to-end
against the live Postgres container, not just reads correctly.

---

## Day 5 — HITL edit flow, Phase 3 test suite, docs pass (`678a37f`, `3f4070f`)

Built: three-way approve/reject/edit in `hitl_node` with a re-prompt
validation loop; unified `save_findings_node`'s parameter order to
`(state, store, config)` (matching `researcher_node`) and switched call
sites to keyword arguments; wrote `test_nodes.py`, `test_memory.py`, and an
edit-flow case in `test_hitl.py`; added `ruff`/`pytest-asyncio` as dev
dependencies; wrote this `docs/` tree and the README; cleaned up stray
leading-space `__init__.py` files.

1. **Resolved — `hitl_node`'s edit branch was never meant to route straight
   to `save_findings`; the original commit message was just inaccurate.**
   `route_from_hitl` (`app/graph/edges.py`) special-cases only `"yes"`/`"y"`
   → `"save_findings"`; both `"no"` and `"edit"` fall through to
   `"researcher_node"` — correct, since an edit's replacement text needs
   another LLM turn to act on it, same mechanism a rejection uses. Commit
   `395626a` ("Day 5 (Continued)") rewrote the commit message to say this
   explicitly, and `test_hitl_node_edit` in `test_hitl.py` covers the path.
   No code change was needed.

2. **Silent positional-argument bug risk, not an actual bug yet**: before
   this day, `save_findings_node` and `researcher_node` had different
   parameter orders (`(state, config, store)` vs. `(state, store, config)`).
   Both types were unannotated at call sites originally relying on
   positional args — swapping `store`/`config` positionally would type-check
   fine (both are duck-typed at the call site) but fail confusingly at
   runtime. **Fix:** unified the order across both nodes and switched every
   call site (including in `build.py`'s graph wiring and all three test
   files) to keyword arguments, so a future reorder can't silently swap the
   two.

---

## Load-test session (uncommitted as of this writing) — concurrency tests

Built: `tests/test_load.py` — two full-graph concurrency tests closing
Phase 3's "load test: 5 concurrent threads" item (cross-user isolation, then
a same-user write-contention variant). Session context: user built this
under `mentor-prompt.md`'s standing mentor persona; the exact override
phrase `MENTOR OVERRIDE: show me the code` was used twice to get a
reference implementation after Socratic review had already surfaced each
bug in the user's own draft — not used to skip understanding, since both
uses were followed by a walkthrough of the non-obvious mechanics.

1. **`AsyncMock(return_value=X)` is a trap under concurrency.** Every
   concurrent call gets the identical object `X` back, regardless of which
   coroutine invoked it or with what arguments — makes it impossible to
   assert "thread A's response didn't leak into thread B," since all
   threads' responses are indistinguishable by construction, not because
   isolation actually held. **Fix:** `AsyncMock(side_effect=callable)`,
   where the callable derives its return value from the actual call
   arguments (`messages[-1].content`, which contains that call's topic).

2. **`interrupt()` does not raise inside `ainvoke()`.** A compiled graph
   with a checkpointer, invoked via `await graph.ainvoke(...)`, returns
   *normally* when it hits `interrupt()` — the returned dict gets an extra
   `"__interrupt__"` key holding a list of `Interrupt` objects, execution
   just doesn't proceed past that node. Resume via `await
   graph.ainvoke(Command(resume=<value>), config=config)` with the same
   `thread_id`. Verified against a minimal throwaway graph before relying on
   it in the real test.

3. **A namespace-wide invariant needs a namespace-wide check, not N
   per-item checks run after all items already exist.** First draft of the
   same-user contention test copy-pasted the cross-user test's per-thread
   loop body — including a `store.asearch(...)` call and `assert
   len(findings) == 1` *inside* the loop. Since `asyncio.gather` only
   returns after all 5 threads' writes have already landed in the one
   shared namespace, that assertion fails on the very first loop iteration
   (finds all 5, not 1). **Fix:** split into two separate checks — a
   per-thread loop asserting only "this thread's own content is correct,"
   and one `asearch` call *after* the loop asserting the whole namespace's
   final count and topic set.

---

## HITL edit-flow session (uncommitted as of this writing) — `state.next` vs `state.tasks`

**Symptom:** typing `edit`/`e` at the HITL approve/reject/edit prompt didn't
ask for refinement text — the CLI printed "Resuming..." then "Research run
completed." as if the edit branch never ran.

**Root cause**, isolated by reproducing against the compiled graph directly
(`build_graph` + `InMemoryStore`/`InMemorySaver` + a mocked
`llm_with_tools`, bypassing the CLI to rule out `edges.py`/`nodes.py`
first): `hitl_node`'s edit branch calls `interrupt()` **twice** in sequence
within one node execution — once for the yes/no/edit choice, once more for
the replacement text (see Day 5's edit-flow build). On the *first*
interrupt, `graph.aget_state(config).next` correctly showed
`('hitl_node',)`. On the *second* interrupt — reached by replaying the same
node with the cached resume value satisfying the first `interrupt()`
call — `state.next` came back as an **empty tuple**, even though
`state.tasks` clearly showed a pending `PregelTask(name='hitl_node',
interrupts=(Interrupt(value='Please provide your refinements...'),))`.

`state.next` reflects nodes scheduled for the *next* Pregel super-step,
computed from the last *completed* step's checkpoint bookkeeping — it isn't
re-derived for a second pause within what LangGraph still treats as the
same task retry. `state.tasks[i].interrupts` doesn't have that gap; it's
the live, authoritative per-task signal, unaffected by whether this is the
first or a subsequent interrupt in the node's execution.

Both `stream_events` and `resume_graph` (`app/streaming/events.py`) guarded
on `if state.next:` before reading `state.tasks[0].interrupts[0].value` —
the guard was wrong, the read itself was always fine. **Fix:** guard
changed to `if state.tasks and state.tasks[0].interrupts:` (the
`state.tasks and` prefix avoids `IndexError` on the empty-tuple case when
the graph genuinely finished at `END`).

**`StateSnapshot` has three related-but-different fields worth
distinguishing, not just two:**

- `.next` — node *names* scheduled for the next super-step. Fine for
  general "is the graph done" bookkeeping; not reliable for detecting a
  second interrupt within the same node's replay (this bug).
- `.tasks` — tuple of `PregelTask` (name, error, result, `.interrupts`).
  The authoritative per-node source of truth for interrupts/errors/results.
- `.interrupts` (top-level on `StateSnapshot`, sibling of `.tasks`) — a
  flattened aggregate of every interrupt across every task in the step.
  Convenient, but `Interrupt` objects only carry `value`/`id`, no node
  reference — flattening **loses task attribution**. Harmless today (only
  `hitl_node` ever interrupts in this graph) but would silently conflate
  two different nodes' interrupts if a second interruptible node were ever
  added. Deliberately kept `tasks[0].interrupts[0]` instead, for that
  reason.
- `"__interrupt__" in result` (the mechanism `tests/test_load.py` uses) — a
  fourth, separate option: available only on the dict returned directly
  from `ainvoke`/`astream` in the *same call*, no extra `aget_state()`
  round-trip needed. Not usable for checking status out-of-band later,
  which is exactly why the CLI's streaming layer needs `aget_state()` +
  `.tasks` in the first place — `astream_events` silently ends its
  generator the moment `interrupt()` fires (Day 3, item 3), so nothing
  about the interrupt survives in the event stream itself.

Verified fixed end-to-end against the real CLI: `edit` now correctly
prompts for refinement text before resuming.
