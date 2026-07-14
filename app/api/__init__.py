"""FastAPI SSE endpoints. The ASGI app itself is an entry point, not
re-exported here — run it via ``app.api.main:app`` (see ``app/api/main.py``),
same convention as ``app.cli.run_cli`` staying off ``app/__init__.py``.
"""

from app.api.routes import get_graph, router

__all__ = ["router", "get_graph"]
