"""Entry point for the Personal Search Assistant CLI.

Wires the Postgres-backed store (cross-session memory) and checkpointer
(per-run graph state) into the compiled LangGraph graph, then hands off to
the interactive REPL in ``app.cli``.
"""
import asyncio
from app.cli import run_cli

from app.core import settings
from app.graph import build_graph
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Same Postgres instance backs both the store and the checkpointer; setup()
# is idempotent (CREATE TABLE IF NOT EXISTS-style) so it's safe on every run.
conn_string = settings.POSTGRES_URI


async def main() -> None:
    """Open the store/checkpointer, build the graph, and run the CLI loop.

    ``store`` persists research findings across sessions (keyed by user_id);
    ``checkpointer`` persists in-progress graph state per thread_id so a run
    can be paused (HITL interrupt) and resumed. Both are async context
    managers so their connections are closed cleanly on exit, including on
    ``KeyboardInterrupt``/exceptions.
    """
    async with (
        AsyncPostgresStore.from_conn_string(conn_string) as store,
        AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer
    ):
        # Create the underlying Postgres tables/indexes on first run.
        await store.setup()
        await checkpointer.setup()
        graph = build_graph(store, checkpointer)
        await run_cli(graph)

if __name__ == "__main__":
    asyncio.run(main())