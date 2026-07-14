"""Entry point for the Personal Search Assistant CLI.

Wires the Postgres-backed store (cross-session memory) and checkpointer
(per-run graph state) into the compiled LangGraph graph, then hands off to
the interactive REPL in ``app.cli``.
"""

import selectors
import asyncio
from app.cli import run_cli

from app.core import init_sentry, settings
from app.graph import open_graph

init_sentry()


async def main() -> None:
    """Open the store/checkpointer, build the graph, and run the CLI loop.

    ``open_graph`` persists research findings across sessions (keyed by
    user_id) and in-progress graph state per thread_id (so a run can be
    paused on a HITL interrupt and resumed) — see
    ``app/graph/postgres.py``, shared with the API's ``lifespan``. It's an
    async context manager so both Postgres connections close cleanly on
    exit, including on ``KeyboardInterrupt``/exceptions.
    """
    async with open_graph(settings.POSTGRES_URI) as graph:
        await run_cli(graph)


if __name__ == "__main__":
    asyncio.run(
        main(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
