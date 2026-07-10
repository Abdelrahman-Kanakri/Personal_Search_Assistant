from pydantic import BaseModel, Field
from typing import Literal


class Event(BaseModel):
    """
    A model representing an event in the system.
    """

    type: Literal["token", "interrupt", "done"] = Field(
        ..., description="The type of the event."
    )
    content: str | None = Field(
        None, description="The content of the event, if applicable."
    )
