"""Error-tracking setup, shared by the CLI (``main.py``) and API (``app/api/main.py``).

Call ``init_sentry()`` once, as early as possible in each entry point.
"""

import sentry_sdk

from app.core.config import settings


def init_sentry() -> None:
    """Initialize Sentry if ``SENTRY_DSN`` is configured.

    ``sentry_sdk.init(dsn=None)`` is a documented no-op, so this is safe to
    call unconditionally even when no DSN is set.
    """
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=1.0)
