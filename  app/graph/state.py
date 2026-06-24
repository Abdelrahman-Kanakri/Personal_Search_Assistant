from typing import Annotated, Optional, TypedDict
from pydantic import BaseModel, Field
from datetime import datetime

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

import operator

class Finding(BaseModel):
    """A finding in the search results."""
    topic: str = Field(..., description="The topic of the finding.")
    content: list[str] = Field(..., description="The content of the finding.")
    url: str = Field(..., description="The URL of the finding.")
    timestamp: datetime = Field(..., description="The timestamp of the finding.")

class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[list[AnyMessage], add_messages] # The messages exchanged between the user and the agent
    topic: str # The original research question from the user
    results: Annotated[list[str], operator.add] # The results of the search
    findings: Annotated[list[Finding], operator.add] # The findings from the search
    human_response: Optional[str] # The response from the human user