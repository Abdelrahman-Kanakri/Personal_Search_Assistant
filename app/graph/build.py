"""Assemble and compile the research-assistant LangGraph graph.

``build_graph`` takes an already-open checkpointer and store and wires up the
graph topology (nodes, edges, compile). The caller owns the connection
lifecycle — see ``main.py``, which opens both via ``async with`` for the
lifetime of the CLI session before calling this function.
"""

# ── Module Imports ─────────────────────────────────────────────────────────────────────
from langgraph.store.base import BaseStore
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from app.graph.edges import route_from_hitl, route_from_research
from app.graph.nodes import hitl_node, researcher_node, save_findings_node
from app.graph.state import AgentState
from app.tools import web_search


# ── Graph Builder ─────────────────────────────────────────────────────────────────────
def build_graph(
    store: BaseStore, checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph:
    """Return the compiled research-assistant graph."""
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
    graph = builder.compile(checkpointer=checkpointer, store=store)
    return graph
