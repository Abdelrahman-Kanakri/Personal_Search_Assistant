"""Postgres-backed graph lifecycle, shared by the CLI and API entry points.

Both entry points need the same thing: an open ``AsyncPostgresStore`` +
``AsyncPostgresSaver``, tables created, wired into a compiled graph, torn
down cleanly on exit. ``build_graph`` itself stays deliberately
Postgres-agnostic (``BaseStore``/``BaseCheckpointSaver``) — this is the one
module allowed to know the backend is Postgres specifically.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.postgres.aio import AsyncPostgresStore

from app.core import get_logger
from app.graph.build import build_graph

logger = get_logger(__name__)


@asynccontextmanager
async def open_graph(conn_string: str) -> AsyncIterator[CompiledStateGraph]:
    """Open the Postgres store/checkpointer, build the graph, and tear both
    down on exit.

    A resource opened via ``async with`` can't outlive that block — the
    caller must do everything with the yielded graph *inside* this context
    manager's `with` block, not after it.
    """
    async with (
        AsyncPostgresStore.from_conn_string(conn_string) as store,
        AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer,
    ):
        await store.setup()
        await checkpointer.setup()
        logger.info("postgres_backend_ready")
        yield build_graph(store, checkpointer)
    logger.info("postgres_backend_closed")
