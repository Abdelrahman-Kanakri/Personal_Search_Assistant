# Rule: LangGraph

- Define graph state as a `TypedDict`. Use `Annotated[list, add_messages]` (or an
  explicit reducer) for any field that accumulates — don't overwrite by accident.
- Keep **nodes pure and small**: input state → output partial state. Side effects
  (DB, network, LLM calls) belong in clearly named nodes, not buried in edges.
- Use **conditional edges** for routing logic; name the router function for what it
  *decides*, not how (e.g. `route_after_retrieval`).
- Always wire a **checkpointer** when memory/persistence matters, and say which one
  (`MemorySaver` for dev, a Postgres/Supabase saver for prod) and why.
- When introducing a new LangGraph concept (reducers, interrupts, subgraphs,
  `Command`), explain it in one line the first time it appears.
- Prefer streaming (`.stream` / `.astream`) for anything user-facing; show how to read
  the event types.
