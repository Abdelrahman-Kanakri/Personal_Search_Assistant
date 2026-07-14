# `app/graph/` — LangGraph State Machine

Defines and assembles the research-assistant graph: shared state schema
(`state.py`), the units of work (`nodes.py`), the routing logic between them
(`edges.py`), and the compiled graph (`build.py`). Nodes are pure
input-state → output-partial-state functions; all routing logic lives in
`edges.py` so it stays side-effect free and independently testable.

## `state.py`

LangGraph state schema. `AgentState` is the single shared dict every node
reads from and writes to. Fields that accumulate across turns use
`Annotated` with an explicit reducer so LangGraph merges partial updates
instead of overwriting previous values.

### `class Finding(BaseModel)`

A single persisted research result.

| Field | Type | Description |
| --- | --- | --- |
| `topic` | `str` | The research question this finding answers (required). |
| `content` | `list[str]` | Extracted facts or passages (required). |
| `url` | `Optional[str]` | Source URL, if available (defaults to `None`). |
| `timestamp` | `datetime` | When the finding was recorded (required). |

### `class AgentState(TypedDict)`

Shared state dict passed between every node in the graph.

| Field | Type | Reducer | Notes |
| --- | --- | --- | --- |
| `messages` | `Annotated[list[AnyMessage], add_messages]` | `add_messages` | Appends new messages instead of overwriting the list. |
| `topic` | `str` | none | Set once on graph entry; never mutated. |
| `results` | `Annotated[list[str], operator.add]` | `operator.add` | Raw search snippets accumulated across tool calls. |
| `findings` | `Annotated[list[Finding], operator.add]` | `operator.add` | Approved, persisted findings. |
| `human_response` | `Optional[str]` | none | Last HITL decision (`'yes'` / anything else). |

## `nodes.py`

Graph nodes. Each node receives the current `AgentState`, performs one unit
of work (LLM call, interrupt, or store write), and returns a partial-state
dict. Side effects (LLM calls, store writes, human interrupts) are
concentrated here so `edges.py` stays logic-only.

Import-time setup: `os.environ["MISTRAL_API_KEY"] = settings.MISTRAL_API_KEY`;
`tools = [web_search]`; `llm = ChatMistralAI(model=settings.MEDIUM_MODEL_NAME, temperature=0)`;
`llm_with_tools = llm.bind_tools(tools)` — wires the tool schemas into the
LLM so it can emit `tool_calls` messages.

### `existing_memory_instruction` (system prompt — memory-recall path)

The system prompt used when the store already has saved findings for the
current user: it instructs the LLM to decompose the query, prefer
previously saved findings over re-searching, fall back to `web_search` only
for sub-questions memory doesn't cover, cite every claim (`[n]`), and list
sources as either `Memory — <topic>, saved <date>` or `Web — <URL>`.
Formatted with `.format(existing_memory=...)` before use.

### `web_search_instructions`

System prompt used when there is **no** saved memory for the user (pure
web-search path). Instructs the LLM to decompose the query, run iterative
Tavily searches, prefer reputable sources, cite every claim (`[n]`), and
list a numbered URL source list. No memory-formatting placeholder — used
verbatim.

### `async def save_findings_node(state: AgentState, store: BaseStore, config: RunnableConfig) -> dict`

Persist the agent's last message as a timestamped finding.

- **Args:**
  - `state`: must contain `topic` and `messages`.
  - `store`: `BaseStore` — a plain `BaseStore`, not `InjectedStore`, because
    this runs as a *node* (LangGraph injects it via the node signature), not
    as an LLM-callable `@tool`.
  - `config`: runnable config carrying `configurable.user_id`.

  Parameter order matches `researcher_node`'s `(state, store, config)` —
  unified so both nodes share one convention and call sites can rely on
  keyword arguments instead of guessing positional order.
- **Returns:** `{}` — no state fields are updated after saving; the finding
  is written directly to the store, not to `AgentState`.
- **Behavior:** builds `[{"topic": state["topic"], "content":
  state["messages"][-1].content, "timestamp": str(datetime.now())}]` and
  delegates to `save_findings` (see [`app-tools.md`](app-tools.md)).

### `async def researcher_node(state: AgentState, store: BaseStore, config: RunnableConfig) -> dict[str, str]`

Run one LLM + tool-calling turn for the research task.

- **Args:**
  - `state`: must contain `topic` and `messages`.
  - `store`: used to check `store.asearch((user_id, "findings"))` for prior
    findings before choosing which system prompt to use.
  - `config`: runnable config; `configurable.user_id` selects the store
    namespace.
- **Returns:** `{"messages": [response]}` — the `add_messages` reducer on
  `AgentState.messages` appends rather than overwrites the history.
- **Behavior:** if `existing_memory` is non-empty, invokes `llm_with_tools`
  with the memory-recall system prompt (`jls_extract_var` /
  `existing_memory_instruction`, formatted with the retrieved memory);
  otherwise invokes it with `web_search_instructions`. Either way, a
  `HumanMessage(f"Search about this topic: {topic}")` plus the existing
  `state["messages"]` history is appended after the system prompt. The
  LLM's response may contain plain text (research complete) or `tool_calls`
  (needs a web search) — `route_from_research` inspects it to decide the
  next node.

### `def hitl_node(state: AgentState, config: RunnableConfig) -> dict`

Pause execution and surface the latest findings to the human for a genuine
three-way approve / reject / edit decision.

- **Args:**
  - `state`: must contain `topic` and `messages`.
  - `config`: unused, kept for signature consistency with other nodes.
- **Returns:**
  - Approve (`'yes'`/`'y'`): `{"human_response": approved}` — no
    `messages` key, since `researcher_node` isn't invoked again on this
    path (see `route_from_hitl` below), so there's nothing to feed it.
  - Reject (`'no'`/`'n'`): `{"human_response": approved, "messages":
    [HumanMessage("User has rejected the findings for '<topic>'.")]}`.
  - Edit (`'edit'`/`'e'`): a **second** `interrupt(...)` call asks for the
    replacement text, then returns `{"human_response": approved, "messages":
    [HumanMessage(f"...revise your prior answer accordingly: {user_input}")]}`.
  - Anything else: re-prompts with a clarifying message and loops (`while
    True`) — the human is asked again rather than the graph erroring or
    silently defaulting to a branch.
- **Behavior:** calls LangGraph's `interrupt(...)` with an approval prompt,
  which suspends the graph until the caller resumes it with
  `Command(resume=...)`. Both the reject and edit paths append a
  `HumanMessage` to `messages` — required because both route back to
  `researcher_node` for another LLM turn (see `route_from_hitl`), and the
  Mistral API rejects a request whose most recent turn is an `AIMessage`.
  Only the approve path skips this, since it goes straight to
  `save_findings_node`, which never calls an LLM.

## `edges.py`

Conditional edge functions that control graph routing. Each function
inspects `AgentState` and returns the name of the next node to execute. No
side effects — pure routing logic only.

### `def route_from_research(state: AgentState, config: RunnableConfig) -> str`

Decide what follows a researcher-node turn.

- **Args:** `state` (must contain `messages`), `config` (unused).
- **Returns:** `"web_search"` if the last message is an `AIMessage` with
  pending `tool_calls`; otherwise `"hitl_node"` (the LLM produced a
  plain-text answer).

### `def route_from_hitl(state: AgentState, config: RunnableConfig) -> str`

Decide what follows the human-review interrupt.

- **Args:** `state` (must contain `human_response`), `config` (unused).
- **Returns:** `"save_findings"` if `state["human_response"]` is `'yes'` or
  `'y'`; otherwise `"researcher_node"` — this covers **both** `'no'` and
  `'edit'` identically, since neither is special-cased here. An edit's
  replacement text reaches the LLM as just another `HumanMessage` in
  `state["messages"]`, the same mechanism a rejection uses; there is no
  "skip straight to save" shortcut for edits.

## `build.py`

Assembles and compiles the graph. Takes an already-open checkpointer and
store — the caller (`main.py` for the CLI, `app/api/main.py`'s lifespan for
the API) owns opening and closing both via `async with`.

### `def build_graph(store: BaseStore, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph`

Return the compiled research-assistant graph.

- **Args:**
  - `store`: cross-session findings store, injected into `researcher_node`
    and `save_findings_node`. Typed against the abstract `BaseStore`, not
    the concrete `AsyncPostgresStore` — the function only forwards it into
    `builder.compile(...)`, never calling a Postgres-specific method, so
    typing it abstractly costs nothing and buys back testability (an
    `InMemoryStore` works identically in tests) and backend-swap
    flexibility.
  - `checkpointer`: per-thread run-state checkpointer enabling HITL
    pause/resume, typed against `BaseCheckpointSaver` for the same reason.
- **Returns:** the compiled `CompiledStateGraph`.
- **Behavior:** builds a `StateGraph(AgentState)` with four nodes
  (`researcher_node`, `hitl_node`, `save_findings`, and `web_search` wrapped
  in a prebuilt `ToolNode`), wires:
  - `START → researcher_node`
  - `researcher_node →` (conditional, `route_from_research`) `→ web_search` or `hitl_node`
  - `hitl_node →` (conditional, `route_from_hitl`) `→ save_findings` or `researcher_node`
  - `web_search → researcher_node`
  - `save_findings → END`

  then compiles with `checkpointer=checkpointer, store=store`.

## `__init__.py`

Public interface for the package. Re-exports `AgentState`, `researcher_node`,
`hitl_node`, `save_findings_node`, `route_from_research`, `route_from_hitl`,
and `build_graph` — import `build_graph` to get the compiled, ready-to-run
graph; the other exports exist mainly for testing individual components in
isolation (see [`tests.md`](tests.md)).
