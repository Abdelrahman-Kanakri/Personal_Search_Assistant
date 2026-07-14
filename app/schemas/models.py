from pydantic import BaseModel, Field
from typing import Literal


class Event(BaseModel):
    """
    A model representing an event in the system.
    """

    type: Literal["token", "interrupt", "done", "error"] = Field(
        ..., description="The type of the event."
    )
    content: str | None = Field(
        None, description="The content of the event, if applicable."
    )


class StartRunRequest(BaseModel):
    """Body for ``POST /runs`` — starts a new research run."""

    topic: str = Field(..., description="The research topic to investigate.")
    user_id: str = Field(
        "default_user", description="Scopes saved findings in the store."
    )


class ResumeRunRequest(BaseModel):
    """Body for ``POST /runs/{thread_id}/resume`` — answers a pending HITL interrupt."""

    response: str = Field(
        ...,
        description="'yes'/'no'/'edit' for the approve/reject/edit prompt, or the "
        "replacement text when resuming after an 'edit' choice.",
    )
    user_id: str = Field(
        "default_user",
        description="Must match the user_id the run was originally started with.",
    )
