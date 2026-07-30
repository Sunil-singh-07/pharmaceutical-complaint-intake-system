"""Database engine construction.

Builds the SQLAlchemy ``Engine`` used by the application from
configuration in ``Settings``. This module performs connection setup
only: no persistence, validation, risk calculation, or workflow logic
lives here, per 04_CODING_CONTRACT.md section 5.
"""

import logging
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide singleton SQLAlchemy ``Engine``.

    The connection URL is built entirely from ``Settings.database_url``,
    which is sourced from environment variables; no credentials are
    hardcoded here. Cached with ``lru_cache`` so the engine (and its
    connection pool) is created only once per process, mirroring the
    pattern used by ``get_settings`` and ``get_session_store``.

    ``pool_pre_ping`` is enabled so a stale or dropped connection is
    detected and transparently replaced rather than surfacing as an
    opaque failure on the next query.

    Returns:
        The shared SQLAlchemy ``Engine``.
    """
    settings = get_settings()
    database_url = settings.database_url
    logger.info("Creating database engine for '%s'.", _mask_credentials(database_url))
    return create_engine(database_url, pool_pre_ping=True, future=True)


def _mask_credentials(database_url: str) -> str:
    """Return a copy of a database URL with any credentials masked.

    Used only for safe logging; never affects the connection itself.

    Args:
        database_url: The raw SQLAlchemy database URL, possibly
            containing embedded credentials.

    Returns:
        The URL with the username and password replaced by ``***``, or
        ``"***"`` if the URL could not be parsed.
    """
    try:
        parsed = make_url(database_url)
    except Exception:  # noqa: BLE001 - logging helper must never raise.
        return "***"
    if parsed.username or parsed.password:
        parsed = parsed.set(username="***", password="***")
    return str(parsed)
