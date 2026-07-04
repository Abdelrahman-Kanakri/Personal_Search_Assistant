"""Interactive CLI for the Personal Search Assistant.

Runs a read-eval loop that:
    1. Accepts a research topic.
    2. Streams the agent's output token-by-token.
    3. Surfaces any HITL interrupt for user approval.
    4. Resumes the graph until it reaches END.
"""
# ── Module Imports ─────────────────────────────────────────────────────────────────────

import uuid

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from app.streaming.events import resume_graph, stream_events
from app.core import settings
import os

os.environ["OPENSSL_CONF"] = settings.OPENSSL_CONF
os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
os.environ["LANGSMITH_TRACING"] = str(settings.LANGSMITH_TRACING)
os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
# Hardcoded for single-user CLI; swap with real auth when needed.
USER_ID = "default_user"


# ── Main CLI Function ─────────────────────────────────────────────────────────────────────
async def run_cli(graph: CompiledStateGraph) -> None:
    """Main REPL: each iteration is one complete research run."""
    while True:
        # Fresh thread_id per run keeps checkpointer state independent across topics.
        thread_id = str(uuid.uuid4())
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": USER_ID,  # required by save_findings to scope the store namespace
            }
        }

        user_input = input("\nEnter a research topic (or 'exit' to quit): ").strip()
        if user_input.lower() == "exit":
            break

        # stream_result is non-None only when the graph pauses at a HITL interrupt.
        stream_result = await stream_events(user_input, graph, config)
        while stream_result is not None:
            print(f"\n{stream_result}")
            human_response = input("Your response: ").strip()
            print("\nResuming...")
            stream_result = await resume_graph(human_response, graph, config)

        print("\nResearch run completed.\n")

        again = input("Start a new research run? (yes/no): ").strip().lower()
        if again not in ("yes", "y"):
            break
