---
name: agent-design
description: Use when deciding HOW to structure an agentic system — whether a task needs an agent at all, how to wire tool/function calling, and which control pattern (ReAct, plan-execute, router) fits. Triggers "should this be an agent", "design an agent", "tool calling", "function calling", "agent architecture", "how do I structure this agent". NOT for adding one node to an existing graph (use langgraph-node) and NOT for evaluating an agent (use agent-eval).
---

# Skill: Agent Design

First question, every time: **does this even need an agent?** An agent = an LLM that
decides its own control flow (which tool, how many steps, when to stop). That power
costs latency, money, and unpredictability. If the steps are known in advance, write a
**chain/pipeline**, not an agent. Use an agent only when the path genuinely depends on
intermediate results.

## Decision rule
- Fixed steps, known order → **chain**. Deterministic, cheap, testable.
- Branching on output, variable tool use, unknown step count → **agent**.
- Mostly fixed but one branch point → **chain with a router node**, not a full agent.

## If it's an agent, pick the control pattern
- **ReAct** (reason → act → observe → repeat) — general default. Good for tool use
  with a clear stopping condition.
- **Plan-then-execute** — generate a plan up front, execute steps. Better for
  multi-step tasks where wandering is expensive; easier to inspect.
- **Router / supervisor** — one node classifies and dispatches to specialized
  sub-agents. Use when tasks split into distinct skill domains.

In your stack, build these as a **LangGraph** graph: nodes = steps/tools, conditional
edges = the agent's decisions, checkpointer = memory. (Scaffold individual nodes with
the langgraph-node skill.)

## Tool/function-calling rules
- A tool is a typed function with a **precise docstring** — the model picks tools from
  names + descriptions, so vague docstrings cause wrong calls. Treat the docstring as
  the prompt it is.
- Keep tools **small and single-purpose**. One `search_orders(customer_id: str)` beats
  one `do_everything(action: str, payload: dict)`.
- Validate tool inputs and handle tool errors *inside* the tool — return a useful error
  string, don't raise into the loop.

## Non-negotiable guardrails on the loop
- A hard **max-iterations / step budget**. Agents loop forever otherwise.
- An explicit **termination condition** — what state means "done".
- A fallback when the model calls no tool or an unknown one.

Decide chain-vs-agent out loud before writing code, and justify it. Most "agent"
requests are better as chains.
