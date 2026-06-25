from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode

from app.graph.nodes import researcher_node, hitl_node, save_findings_node
from app.graph.edges import route_from_research, route_from_hitl
from app.graph.state import AgentState
from app.tools import save_findings, web_search

import sqlite3
conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
# Define the graph
builder = StateGraph(AgentState)

# Add the nodes
builder.add_node("researcher_node", researcher_node)
builder.add_node("hitl_node", hitl_node)
builder.add_node("save_findings", save_findings_node)
builder.add_node("web_search", ToolNode([web_search]))

# Add the edges
builder.add_edge(START, "researcher_node")
builder.add_conditional_edges("researcher_node", route_from_research)
builder.add_conditional_edges("hitl_node", route_from_hitl)
builder.add_edge("save_findings", END)

graph = builder.compile(checkpointer = SqliteSaver(conn))