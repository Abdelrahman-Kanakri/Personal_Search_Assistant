"""Graph nodes for the Personal Search Assistant.

Each node is a pure function: it receives the current ``AgentState``, performs
one unit of work (LLM call, interrupt, or store write), and returns a partial-
state dict.  Side effects are concentrated here so edge functions stay logic-only.
"""
# ── Module Imports ─────────────────────────────────────────────────────────────────────
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

# ── LLM Configuration ─────────────────────────────────────────────────────────────────────
os.environ["MISTRAL_API_KEY"] = settings.MISTRAL_API_KEY

tools = [web_search]

llm = ChatMistralAI(
    model=settings.MEDIUM_MODEL_NAME,
    temperature=0,
)

# bind_tools wires the tool schemas into the LLM so it can emit tool_call messages.
llm_with_tools = llm.bind_tools(tools)


<<<<<<< HEAD
# NOTE: name is a leftover from an IDE "extract variable" refactor — kept as-is
# to avoid an unrelated rename in a docs-only pass. This is the system prompt
# used when the store already has saved findings for the user (memory-first
# path); see `web_search_instructions` below for the no-memory fallback prompt.
=======
>>>>>>> 198f882917cfa5acd5271317efeb83134a7e7d1b
existing_memory_instruction = """\
# System Instructions: Memory Recall Agent

You are an expert AI Research Agent. Your goal is to process an incoming `query` parameter, break it down into relevant sub-questions, retrieve applicable findings from previously saved research, fill any gaps with a live web search, and synthesize a factual, well-cited response.

Follow this strict execution loop:

## 1. Query Analysis & Deconstruction
* Analyze the provided input `query`.
* If the query is complex or broad, break it down into smaller, logical sub-questions.
* For each sub-question, determine whether it is answerable from the saved findings below.

## 2. Memory Retrieval & Gap-Filling Search
* Review the provided saved research findings (below). Identify which findings are directly relevant, partially relevant, or unrelated to the current query.
* If the new query overlaps with previous findings, reference them appropriately instead of re-searching for that sub-question.
* **Fallback rule:** For any sub-question the saved findings do not cover — in whole or in part — you must call the web search tool for that specific sub-question rather than guessing or declaring insufficiency. Do not search for sub-questions memory already answers.

## 3. Content Extraction & Evaluation
* Evaluate both saved findings and any new search results for accuracy, relevance, and recency.
* Extract key facts, statistics, and conflicting viewpoints if they exist.
* **Grounding:** Do not assume or extrapolate beyond what is explicitly present in the saved findings or the retrieved search results. Do not invent findings, and do not invent URLs.

## 4. Output Formatting & Synthesis
Provide your final answer using a clean, professional Markdown format according to these rules:
* **Executive Summary:** A 1-2 sentence high-level answer to the query.
* **Detailed Findings:** Use clear headings, bullet points, and bold text for scannability.
* **In-line Citations:** Cite every claim using plain numbered brackets inline, e.g. [1], [2]. Do NOT use structured reference objects — plain text only.
* **Sources Section:** Conclude with a numbered list mapping to your inline citations. For each entry, state the source type explicitly:
    - Memory-derived: `[n] Memory — <topic>, saved <date>`
    - Search-derived: `[n] Web — <URL>`
* **Handling Empty Results:** If neither saved findings nor a follow-up search provide enough evidence for a sub-question, explicitly state that the information is insufficient for that part rather than guessing.

You have access to the following previously saved research findings for this user:
{existing_memory}
"""
<<<<<<< HEAD

=======
 
>>>>>>> 198f882917cfa5acd5271317efeb83134a7e7d1b
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

# ── Async Functions that allows mid execution pause ─────────────────────────────────────────────────────────────────────
# Save findings node uses the save_findings tool to persist the AI findings.
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
    # Extract the State fields needed to construct the finding.  The last message is the AI's final answer.
    findings = [
        {
            "topic": state["topic"],
            "content": state["messages"][-1].content,
            "timestamp": str(datetime.now()),
        }
    ]
    print(await save_findings(findings=findings, store=store, config=config))
    return {}

# Researcher node uses the LLM with tools to perform one research turn, which may result in tool calls or a plain-text answer.
async def researcher_node(state: AgentState, 
                        store: BaseStore,
                        config: RunnableConfig,) -> dict[str, str]:
    
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
    # Get the topic and user_id from the state and config, respectively, to use in the search query.
    topic = state["topic"]
    user_id = config["configurable"]["user_id"]
    namespace = (user_id, "findings")
    existing_memory = await store.asearch(namespace)
    
    # if there an existing memory, we will use it to inform the LLM's response. Otherwise, we will proceed with a web search.
    if existing_memory:
        response = await llm_with_tools.ainvoke(
            [SystemMessage(content=existing_memory_instruction.format(existing_memory=existing_memory))] +
            [HumanMessage(content=f"Search about this topic: {topic} ")] +
            state["messages"]
        )
    else:
        response = await llm_with_tools.ainvoke(
            [SystemMessage(content=web_search_instructions)] +
            [HumanMessage(content=f"Search about this topic: {topic} ")] +
        state["messages"]
    )
    return {"messages": [response]}

# Human-in-the-loop node uses LangGraph's interrupt to pause execution and surface the findings to the human for review.
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
        f"Approve findings for '{topic}'? \nReply 'yes' to save, or 'no' to search again."
    )
    if approved not in ("yes", "y"):
        # Why this has been added
        # because if the user has accepts the findings,
        # the save_finding_tool dont care about what type of messages it recieves,
        # so no crash, where the researcher_node uses a LLM, and LLM API does not accepts AIMessage as a response,
        # in that case, we need to append a HumanMessage to the messages list, so that the researcher_node can continue to work with the LLM API.
        rejection_message = HumanMessage(content="Human rejected the findings. Please refine your answer.")
        return {"human_response": approved, "messages": [rejection_message]}
    return {"human_response": approved}
