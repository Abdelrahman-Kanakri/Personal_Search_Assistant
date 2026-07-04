# `app/memory/` — Cross-Session Memory Layer (Stub)

Both files in this package are currently **empty placeholders** — there is
no code to reference or document yet.

- `store.py` — 0 bytes.
- `__init__.py` — 0 bytes.

## Current state of cross-session memory

Cross-session persistence already works today, but it lives directly in
`app/graph/nodes.py` and `app/tools/save_finding.py`, wired through
LangGraph's own `AsyncPostgresStore` (constructed in `main.py`, passed into
`build_graph`):

- `researcher_node` reads prior findings via `store.asearch((user_id,
  "findings"))`.
- `save_findings_node` / `save_findings` write approved findings via
  `store.put((user_id, "findings"), key, value)`.

This package is presumably intended to become a dedicated abstraction layer
on top of that — e.g. summarization/trimming of accumulated findings,
retrieval-quality helpers, or a typed wrapper around the raw store calls
(see the `agent-memory` skill for the general pattern: managing
conversation history and long-term persistent memory separately from
in-node store calls). Until code lands here, treat `app/graph/nodes.py` and
`app/tools/save_finding.py` as the source of truth for how memory actually
works in this project.
