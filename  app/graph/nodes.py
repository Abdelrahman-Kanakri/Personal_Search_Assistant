# ── Module Imports ─────────────────────────────────────────────────────────────
import os 
from datetime import datetime

from app.core import settings
from app.tools import web_search
from app.graph.state import AgentState
from app.tool import save_findings

from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

# ── Model Initialization ─────────────────────────────────────────────────────
# Set the API key for MistralAI
os.environ["MISTRALAI_API_KEY"] = settings.MISTRAL_API_KEY

# Initialize the tools list for the agent
tools = [web_search]

# Initialize the ChatMistralAI model with the specified settings
llm = ChatMistralAI(
    model=settings.MEDIUM_MODEL_NAME,
    temperature=0,
)

# Bind the tools to the LLM
llm_with_tools = llm.bind_tools(tools)

# Create the instructions for the Search Agent
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
* **In-line Citations:** Every factual claim **must** be cited inline pointing to its specific source.
* **Sources Section:** Conclude with a numbered list of URLs used, mapping directly back to your inline citations.
* **Handling Empty Results:** If the search results do not provide enough evidence to answer the query, explicitly state that the information is insufficient rather than guessing or using outdated internal knowledge.
""" 
# ── Save Finding Node ─────────────────────────────────────────────────────
def save_findings_node(state: AgentState,
                    config: RunnableConfig,
                    store: BaseStore # We use BaseStore here instead of InjectedStore since its a node not a Tool
                    ) -> dict[str, str]:
    """Saves the findings from the search results to a persistent storage.
    
    args:
        state: The state of the agent. Should be a dictionary with the following keys
    """
    findings = [
        {
            "topic": state["topic"], 
            "content": state["messages"][-1].content,
            "timestamp": str(datetime.datetime.now()),
        }
    ]
    save_findings(findings=findings, store=store, config=config)
    return {}

# ── Researcher Node ─────────────────────────────────────────────────────
def researcher_node(state: AgentState) -> dict[str, str]:
    """The researcher agent that searches for information about a topic.
    
    args: 
        state: The state of the agent. Should be a dictionary with the following keys
            - messages: The messages exchanged between the user and the agent
            - topic: The original research question from the user
            - results: The results of the search
            - findings: The findings from the search
            - human_response: The response from the human user
    """
    # Extract the Topic from the state
    topic = state["topic"]
    
    # Create the system message with the instructions
    system_message = web_search_instructions.format(topic=topic)
    
    response = llm_with_tools.invoke(
        [SystemMessage(content = system_message)] +
        [HumanMessage(content = f"Search about : {topic} based on the provided context & System Message.")] + state["messages"]
    )
    return {
        "messages": [response],
    }

# ── Human-in-the-Loop Node ─────────────────────────────────────────────────────
def hitl_node(state: AgentState, config: RunnableConfig) -> dict[str, str]:
    """The human-in-the-loop agent that allows the user to provide feedback on the findings.
    
    args: 
        state: The state of the agent. Should be a dictionary with the following keys
            - messages: The messages exchanged between the user and the agent
            - topic: The original research question from the user
    """
    # Extract the Topic from the state
    topic = state["topic"]
    results = state["messages"][-1].content
    
    # Pause and ask for approval
    approved = interrupt(f"""Do you approve on the findings for the topic: {topic} results?,
                        \n\nResults: {results}\n\nPlease respond with 'yes' or 'no'.""")
    
    return {"human_response": approved}