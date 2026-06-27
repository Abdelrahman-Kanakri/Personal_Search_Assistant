"""Assemble and compile the research-assistant LangGraph graph.

The module-level ``graph`` object is the compiled, checkpointer-wired graph
imported by the streaming layer and the CLI.  Building at import time means
any missing environment variables or mis-wired edges surface immediately on
startup rather than on the first user request.
"""
# ── Module Imports ─────────────────────────────────────────────────────────────────────
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.graph.edges import route_from_hitl, route_from_research
from app.graph.nodes import hitl_node, researcher_node, save_findings_node
from app.graph.state import AgentState
from app.tools import web_search

# ── Graph Builder ─────────────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)

# ── Add Nodes ──
builder.add_node("researcher_node", researcher_node)
builder.add_node("hitl_node", hitl_node)
builder.add_node("save_findings", save_findings_node)
builder.add_node("web_search", ToolNode([web_search]))

# ── Add Edges ──
builder.add_edge(START, "researcher_node")
builder.add_conditional_edges("researcher_node", route_from_research)
builder.add_conditional_edges("hitl_node", route_from_hitl)
builder.add_edge("web_search", "researcher_node")
builder.add_edge("save_findings", END)

# ── Compile the Graph  ──
graph = builder.compile(checkpointer = MemorySaver(),
                        store = InMemoryStore())
