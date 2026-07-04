"""LangGraph state schema for the research-assistant graph.

``AgentState`` is the single shared dict that every node reads from and writes
to.  Fields that accumulate across turns use ``Annotated`` with an explicit
reducer so LangGraph merges partial updates instead of overwriting previous values.
"""

# ── Module Imports ─────────────────────────────────────────────────────────────────────
import operator
from datetime import datetime
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ── State Classes ─────────────────────────────────────────────────────────────────────
class Finding(BaseModel):
    """A single persisted research result."""

    topic: str = Field(..., description="The research question this finding answers.")
    content: list[str] = Field(..., description="Extracted facts or passages.")
    url: Optional[str] = Field(None, description="Source URL, if available.")
    timestamp: datetime = Field(..., description="When the finding was recorded.")


class AgentState(TypedDict):
    """Shared state dict passed between every node in the graph."""

    # add_messages reducer appends new messages instead of overwriting the list.
    messages: Annotated[list[AnyMessage], add_messages]
    topic: str  # set once on graph entry; never mutated
    results: Annotated[
        list[str], operator.add
    ]  # raw search snippets accumulated across tool calls
    findings: Annotated[list[Finding], operator.add]  # approved, persisted findings
    human_response: Optional[str]  # last HITL decision ('yes' / anything else)
