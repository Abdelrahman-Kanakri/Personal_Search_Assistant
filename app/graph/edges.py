"""Conditional edge functions that control graph routing.

Each function inspects ``AgentState`` and returns the name of the next node to
execute.  No side effects — pure routing logic only.
"""
# ── Module Imports ─────────────────────────────────────────────────────────────────────
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.graph.state import AgentState

# ─── Router functions  ───────────────────────────────────────────────────────────────────────────
# Route from research to either web search (if tool calls are pending) or human review (if the LLM produced a plain-text answer).
def route_from_research(state: AgentState, config: RunnableConfig) -> str:
    """Decide what follows a researcher-node turn.

    If the LLM returned tool calls the graph routes to ``web_search`` to execute
    them.  Once the LLM produces a plain-text answer the graph moves to the
    human-review step.

    Args:
        state: Current graph state; must contain ``messages``.
        config: Runnable config (unused, kept for signature consistency).

    Returns:
        ``"web_search"`` if tool calls are pending, otherwise ``"hitl_node"``.
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "web_search"
    return "hitl_node"

# Route from hitl to either researcher_node (if the human rejected the findings) or save_findings (if the human approved).
def route_from_hitl(state: AgentState, config: RunnableConfig) -> str:
    """Decide what follows the human-review interrupt.

    A ``'yes'`` response persists the findings and ends the run.  Any other
    response sends control back to the researcher to refine its answer.

    Args:
        state: Current graph state; must contain ``human_response``.
        config: Runnable config (unused, kept for signature consistency).

    Returns:
        ``"save_findings"`` if the human approved, otherwise ``"researcher_node"``.
    """
    if state["human_response"] == "yes":
        return "save_findings"
    return "researcher_node"
