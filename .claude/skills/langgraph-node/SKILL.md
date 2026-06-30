---
name: langgraph-node
description: Use when the user wants to add a new node to a LangGraph graph, or asks to "scaffold a node". Produces a typed, testable node following the project's LangGraph rules.
---

# Skill: Scaffold a LangGraph Node

When asked to add a node, produce:

1. A typed node function: `def node_name(state: GraphState) -> dict` that returns only
   the partial state it changes.
2. Isolated side effects (LLM/DB calls) — no hidden I/O in routing functions.
3. The edge wiring snippet (`graph.add_node(...)` + the relevant `add_edge` /
   `add_conditional_edges`), shown separately so it's obvious where it plugs in.
4. A minimal `pytest` test that calls the node with a hand-built state dict and
   asserts on the returned partial state.

Naming: node functions describe the action (`retrieve_docs`); routers describe the
decision (`route_after_retrieval`). Keep each node under ~30 lines; if it's bigger,
suggest splitting.

Always end by noting which reducer the new field needs in `GraphState` (or confirming
it overwrites intentionally).
