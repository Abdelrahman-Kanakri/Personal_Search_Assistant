"""Async streaming helpers that drive the graph and surface events to the CLI.

``stream_events`` starts a new research run and streams token output until it
hits a HITL interrupt, returning the interrupt payload so the CLI can prompt the
user.  ``resume_graph`` resumes a suspended run after the user has responded.
"""

from collections.abc import AsyncGenerator
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from app.core import bind_run_context, clear_run_context, get_logger

logger = get_logger(__name__)


async def stream_events(
    user_input: str, graph: CompiledStateGraph, config: RunnableConfig
) -> AsyncGenerator[tuple[str, str | None], None]:
    """Start a research run and stream agent output until an interrupt or completion.

    Args:
        user_input: The research topic/query passed as ``state["topic"]``.
        graph: The compiled LangGraph graph.
        config: Runnable config including ``thread_id`` and ``user_id``.

    Yields:
        An AsyncGenerator yielding tuples of the:
        - event type ["token", "interrupt", "done"]
        - content of the event, if applicable:
            -   (``None`` for "done" events).
            -   (the interrupt payload for "interrupt" events).
            -   (the token string for "token" events).
    """
    bind_run_context(
        thread_id=config["configurable"]["thread_id"],
        user_id=config["configurable"]["user_id"],
    )
    try:
        logger.info("run_started", topic=user_input)
        async for event in graph.astream_events(
            {"topic": user_input, "messages": []},
            config,
            version="v2",
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if isinstance(chunk.content, str) and chunk.content:
                    yield ("token", chunk.content)
                elif isinstance(chunk.content, list):
                    for part in chunk.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            yield ("token", part["text"])

        state = await graph.aget_state(config)
        if state.tasks and state.tasks[0].interrupts:
            logger.info("run_interrupted")
            yield ("interrupt", state.tasks[0].interrupts[0].value)
        else:
            logger.info("run_completed")
            yield ("done", None)
    finally:
        clear_run_context()


async def resume_graph(
    human_response: str, graph: CompiledStateGraph, config: RunnableConfig
) -> AsyncGenerator[tuple[str, str | None], None]:
    """Resume a graph that was suspended at a HITL interrupt.

    Wraps the human response in a ``Command(resume=...)`` so LangGraph can
    unblock the interrupt and continue from where it paused.

    Args:
        human_response: The user's approval decision (``'yes'`` / anything else).
        graph: The compiled LangGraph graph.
        config: The same runnable config used in the original ``stream_events``
            call — the ``thread_id`` must match so the checkpointer loads the
            correct suspended state.

    Yields:
        An AsyncGenerator yielding tuples of the:
        - event type ["token", "interrupt", "done"]
        - content of the event, if applicable:
            -   (``None`` for "done" events).
            -   (the interrupt payload for "interrupt" events).
            -   (the token string for "token" events).
    """
    bind_run_context(
        thread_id=config["configurable"]["thread_id"],
        user_id=config["configurable"]["user_id"],
    )
    try:
        logger.info("run_resumed")
        async for event in graph.astream_events(
            Command(resume=human_response), config, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if isinstance(chunk.content, str) and chunk.content:
                    yield ("token", chunk.content)
                elif isinstance(chunk.content, list):
                    for part in chunk.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            yield ("token", part["text"])
        state = await graph.aget_state(config)
        if state.tasks and state.tasks[0].interrupts:
            logger.info("run_interrupted")
            yield ("interrupt", state.tasks[0].interrupts[0].value)
        else:
            logger.info("run_completed")
            yield ("done", None)
    finally:
        clear_run_context()
