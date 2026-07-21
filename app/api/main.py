"""FastAPI application entry point.

Uses ``app.graph.open_graph`` for the same Postgres connection lifecycle the
CLI's ``main.py`` uses, via a lifespan context manager — not per-request. A
resource opened inside ``async with`` cannot outlive that block
(docs/issues-and-fixes.md, Day 4 item 5), so the graph is built once here
and handed to every request via ``app.state``.

Run with: ``uv run uvicorn app.api.main:app --reload --loop app.api.main:loop_factory``

The explicit ``--loop`` is required on Windows — see ``loop_factory`` below.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core import get_logger, init_sentry, settings
from app.graph import open_graph

logger = get_logger(__name__)
init_sentry()


def loop_factory() -> asyncio.AbstractEventLoop:
    """Uvicorn ``--loop`` hook — must return a loop *instance*, zero args.

    Unlike uvicorn's built-in named loops ("asyncio"/"uvloop"/"auto"), a
    custom ``--loop module:callable`` string is used directly as the final
    factory, with no intermediate ``use_subprocess`` resolution step — so
    this can't reuse uvicorn's two-level ``asyncio_loop_factory`` signature.

    psycopg's async driver needs ``SelectorEventLoop``, not Windows' default
    ``ProactorEventLoop`` (docs/issues-and-fixes.md, Day 6) — uvicorn's
    built-in ``"asyncio"`` loop choice picks Proactor on win32, under which
    the lifespan's ``AsyncPostgresStore``/``AsyncPostgresSaver`` connect just
    hangs at startup with no exception.
    """
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the store/checkpointer, build the graph, and tear both down on shutdown."""
    async with open_graph(settings.POSTGRES_URI) as graph:
        app.state.graph = graph
        logger.info("api_startup_complete")
        yield
    logger.info("api_shutdown_complete")


app = FastAPI(title="Personal Search Assistant API", lifespan=lifespan)
app.include_router(router)
