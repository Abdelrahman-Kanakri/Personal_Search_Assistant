from app.graph.state import AgentState
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
def route_from_research(state: AgentState, config: RunnableConfig) -> str:
    """ 
    Routes the Researcher Node either to:
        - the Human-in-the-Loop Node 
        - or the Save Findings Node based on the human response.
        
    args:
        state: The state of the agent. Should be a dictionary with the following keys
            - messages: The messages exchanged between the user and the agent
            - topic: The original research question from the user
    """
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "search_web"
    else:
        return "hitl_node"


def route_from_hitl(state: AgentState, config: RunnableConfig) -> str:
    """ 
    Routes the Human-in-the-Loop Node either to:
        - the Save Findings Node if the human approves the findings
        - or back to the Researcher Node if the human does not approve the findings.
        
    args:
        state: The state of the agent. Should be a dictionary with the following keys
            - messages: The messages exchanged between the user and the agent
            - topic: The original research question from the user
            - human_response: The response from the human user
    """
    if state["human_response"] == "yes":
        return "save_findings"
    else:
        return "researcher_node"