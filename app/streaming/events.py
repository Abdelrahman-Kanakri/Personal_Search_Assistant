"""Async streaming helpers that drive the graph and surface events to the CLI.

``stream_events`` starts a new research run and streams token output until it
hits a HITL interrupt, returning the interrupt payload so the CLI can prompt the
user.  ``resume_graph`` resumes a suspended run after the user has responded.
"""

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph


async def stream_events(
    user_input: str, graph: CompiledStateGraph, config: RunnableConfig
) -> str | None:
    """Start a research run and stream agent output until an interrupt or completion.

    Args:
        user_input: The research topic/query passed as ``state["topic"]``.
        graph: The compiled LangGraph graph.
        config: Runnable config including ``thread_id`` and ``user_id``.

    Returns:
        The interrupt payload string if the graph pauses for human review,
        or ``None`` if the graph ran to completion without interrupting.
    """
    async for event in graph.astream_events(
        {"topic": user_input, "messages": []},
        config,
        version="v2",
    ):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if isinstance(chunk.content, str) and chunk.content:
                print(chunk.content, end="", flush=True)
            elif isinstance(chunk.content, list):
                for part in chunk.content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        print(part["text"], end="", flush=True)

    state = await graph.aget_state(config)
    if state.next:
        return state.tasks[0].interrupts[0].value
    return None


async def resume_graph(
    human_response: str, graph: CompiledStateGraph, config: RunnableConfig
) -> str | None:
    """Resume a graph that was suspended at a HITL interrupt.

    Wraps the human response in a ``Command(resume=...)`` so LangGraph can
    unblock the interrupt and continue from where it paused.

    Args:
        human_response: The user's approval decision (``'yes'`` / anything else).
        graph: The compiled LangGraph graph.
        config: The same runnable config used in the original ``stream_events``
            call — the ``thread_id`` must match so the checkpointer loads the
            correct suspended state.

    Returns:
        The next interrupt payload if the graph pauses again, or ``None`` if
        the graph ran to completion.
    """
    async for event in graph.astream_events(
        Command(resume=human_response), config, version="v2"
    ):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if isinstance(chunk.content, str) and chunk.content:
                print(chunk.content, end="", flush=True)
            elif isinstance(chunk.content, list):
                for part in chunk.content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        print(part["text"], end="", flush=True)
    state = await graph.aget_state(config)
    if state.next:
        return state.tasks[0].interrupts[0].value
    return None
