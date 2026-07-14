"""Shared ``RunnableConfig`` construction for the CLI and API entry points.

Keeping this in one place means LangSmith tagging/metadata only needs to be
right once — both ``app.cli`` and ``app.api.routes`` call this instead of
building the config dict inline.
"""

from langchain_core.runnables import RunnableConfig


def build_run_config(
    thread_id: str, user_id: str, topic: str | None = None
) -> RunnableConfig:
    """Build the config passed to every graph invocation for one run.

    ``thread_id``/``user_id`` live under ``configurable`` — LangGraph's
    checkpointer and ``save_findings`` read them from there. ``tags``/
    ``metadata`` live at the top level — that's what LangSmith reads to label
    a trace. ``topic`` is only known when a run starts, not on resume, so
    it's optional and omitted from ``metadata`` when absent.
    """
    metadata = {"topic": topic} if topic is not None else {}
    return {
        "configurable": {"thread_id": thread_id, "user_id": user_id},
        "tags": [f"user:{user_id}"],
        "metadata": metadata,
    }
