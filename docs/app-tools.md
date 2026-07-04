# `app/tools/` — External Actions

LangChain functions the graph uses to act outside the LLM's own context:
one true `@tool` the LLM can invoke directly (`web_search`), and one plain
function called from a node rather than by the LLM (`save_findings`).

## `web_search.py`

Tavily-backed web search tool, exposed as a LangChain `@tool`.

Import-time side effect: `os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY`.

### `@tool def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]`

Search the web and return a list of result snippets with their source URLs.

- **Args:**
  - `query`: the search query string.
  - `max_results`: maximum number of results to retrieve from Tavily
    (default `5`).
- **Returns:** a list of dicts, each with `"content"` (snippet text) and
  `"url"`.
- **Behavior:** constructs `TavilySearch(max_results=max_results)`, calls
  `.invoke({"query": query})`, and reshapes Tavily's raw `results` list into
  the `content`/`url` dict shape the rest of the app expects. Decorated with
  `@tool` so `llm_with_tools` (in `app/graph/nodes.py`) can call it directly
  in response to an LLM `tool_call`, and so it can be wrapped in a
  `ToolNode` in `build_graph`.

## `save_finding.py`

Persists research findings to the LangGraph cross-session store.

### `def save_findings(findings: list[dict[str, str]], store: Annotated[Any, InjectedStore], config: RunnableConfig) -> str`

Write a batch of research findings to the user's persistent store
namespace.

- **Args:**
  - `findings`: list of finding dicts, each containing `"topic"`,
    `"content"`, and `"timestamp"` keys.
  - `store`: LangGraph store, typed with `InjectedStore` so LangChain's
    tool-calling machinery would inject it automatically **if** this were
    invoked as an LLM tool — but it isn't (see below); the type is kept for
    documentation/type-checking value.
  - `config`: runnable config; must carry `configurable.user_id`.
- **Returns:** a confirmation string, e.g. `"Saved 1 findings to the
  knowledge store for user default_user."`
- **Behavior:** namespaces the store key as `(user_id, "findings")`, so each
  user's findings are isolated from one another. Within that namespace,
  each finding is keyed by `f"{topic}_{timestamp}"` to avoid collisions
  across research sessions. Calls `store.put(namespace, key, value)` once
  per finding.
- **Note:** **no `@tool` decorator** — despite the `InjectedStore` typing,
  this function is called directly from `save_findings_node` (a graph
  node), not exposed to the LLM as a callable tool. The `InjectedStore`
  annotation is vestigial from an earlier design where it may have been
  tool-callable.

## `__init__.py`

Re-exports `save_findings` and `web_search` — the two names the graph layer
imports: `from app.tools import save_findings, web_search`.
