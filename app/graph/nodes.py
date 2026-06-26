"""Graph nodes for the Personal Search Assistant.

Each node is a pure function: it receives the current ``AgentState``, performs
one unit of work (LLM call, interrupt, or store write), and returns a partial-
state dict.  Side effects are concentrated here so edge functions stay logic-only.
"""
import os
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_mistralai import ChatMistralAI
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

from app.core import settings
from app.graph.state import AgentState
from app.tools import save_findings, web_search

os.environ["MISTRAL_API_KEY"] = settings.MISTRAL_API_KEY

tools = [web_search]

llm = ChatMistralAI(
    model=settings.MEDIUM_MODEL_NAME,
    temperature=0,
)

# bind_tools wires the tool schemas into the LLM so it can emit tool_call messages.
llm_with_tools = llm.bind_tools(tools)

web_search_instructions = """\
# System Instructions: Web Research Agent

You are an expert AI Research Agent. Your goal is to process an incoming `query` parameter, break it down into optimized search strategies, gather relevant data from the web, and synthesize a factual, well-cited response.

Follow this strict execution loop:

## 1. Query Analysis & Deconstruction
* Analyze the provided input `query`.
* If the query is complex or broad, break it down into smaller, logical sub-questions.
* Identify core keywords, synonyms, and search syntax (e.g., `"phrase matching"` or `site:`) that will yield the highest quality results.

## 2. Search Execution & Optimization
* Formulate precise search queries for your available web search tool.
* **Iterative Search:** Do not rely on a single search query. If the initial results are shallow or lack sufficient detail, modify your terms and execute a follow-up search.
* Prioritize reputable sources (e.g., official documentation, academic repositories, trusted news outlets, or primary data sources).

## 3. Content Extraction & Evaluation
* Evaluate the search results for accuracy, relevance, and recency.
* Extract key facts, statistics, and conflicting viewpoints if they exist.
* **Grounding:** Do not assume or extrapolate information beyond what is explicitly found in the retrieved snippets or web pages.

## 4. Output Formatting & Synthesis
Provide your final answer using a clean, professional Markdown format according to these rules:
* **Executive Summary:** A 1-2 sentence high-level answer to the query.
* **Detailed Findings:** Use clear headings, bullet points, and bold text for scannability.
* **In-line Citations:** Cite sources using plain numbered brackets inline, e.g. [1], [2]. Do NOT use structured reference objects — plain text only.
* **Sources Section:** Conclude with a numbered list of URLs used, mapping directly back to your inline citations.
* **Handling Empty Results:** If the search results do not provide enough evidence to answer the query, explicitly state that the information is insufficient rather than guessing or using outdated internal knowledge.
"""


async def save_findings_node(
    state: AgentState,
    config: RunnableConfig,
    store: BaseStore,  # BaseStore not InjectedStore: this is a node, not a @tool
) -> dict:
    """Persist the agent's last message as a timestamped finding.

    Packages the current topic and the last AI message into a finding dict and
    delegates to ``save_findings``, which writes it to the LangGraph cross-session
    store under a per-user namespace.

    Args:
        state: Current graph state; must contain ``topic`` and ``messages``.
        config: Runnable config carrying ``configurable.user_id``.
        store: LangGraph store instance injected by the runtime at node invocation.

    Returns:
        Empty dict — no state fields are updated after saving.
    """
    findings = [
        {
            "topic": state["topic"],
            "content": state["messages"][-1].content,
            "timestamp": str(datetime.now()),
        }
    ]
    print(save_findings(findings=findings, store=store, config=config))
    return {}


async def researcher_node(state: AgentState) -> dict[str, str]:
    
    """Run one LLM + tool-calling turn for the research task.

    Prepends the system prompt and a human trigger message, then invokes the
    tool-bound LLM.  The LLM may respond with plain text (research complete) or
    with ``tool_calls`` (needs a web search).  The conditional edge
    ``route_from_research`` inspects the response to decide which branch to take.

    Args:
        state: Current graph state; must contain ``topic`` and ``messages``.

    Returns:
        Partial state dict with ``messages`` containing the new AI response.
        The ``add_messages`` reducer in ``AgentState`` appends rather than
        overwrites the history.
    """
    topic = state["topic"]
    response = await llm_with_tools.ainvoke(
        [SystemMessage(content=web_search_instructions)]
        + [HumanMessage(content=f"Search about this topic: {topic} ")]
        + state["messages"]
    )
    return {"messages": [response]}


def hitl_node(state: AgentState, config: RunnableConfig) -> dict:
    """Pause execution and surface the latest findings to the human for review.

    Uses LangGraph's ``interrupt`` to yield control back to the caller.  The
    graph is suspended here and resumes only when the caller supplies a
    ``Command(resume=...)`` with the human's decision.

    Args:
        state: Current graph state; must contain ``topic`` and ``messages``.
        config: Runnable config (unused here, kept for signature consistency).

    Returns:
        Partial state dict with ``human_response`` set to the human's input.
        ``'yes'`` routes to save; anything else routes back to the researcher.
    """
    topic = state["topic"]

    approved = interrupt(
        f"Approve findings for '{topic}'? Reply 'yes' to save, or 'no' to search again."
    )
    return {"human_response": approved}
