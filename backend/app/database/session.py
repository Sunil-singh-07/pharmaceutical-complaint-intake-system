"""Database session lifecycle management.

Provides a SQLAlchemy session factory and a FastAPI-compatible
dependency (``get_db_session``) that yields one session per request and
always closes it, avoiding any global mutable database connection.
Committing and rolling back transactions is left entirely to the
repository layer (``app.repositories``), which is best positioned to
decide transaction boundaries; this module only manages the session's
open/close lifecycle.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import get_engine

logger = logging.getLogger(__name__)


@lru_cache
def get_session_factory() -> sessionmaker:
    """Return the process-wide singleton SQLAlchemy session factory.

    Cached with ``lru_cache`` so the factory (and the engine it is bound
    to) is created only once per process.

    Returns:
        A ``sessionmaker`` bound to the shared engine.
    """
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_db_session() -> Iterator[Session]:
    """Yield a database session for the duration of a single request.

    Intended for use as a FastAPI dependency, e.g.
    ``Depends(get_db_session)``. A fresh ``Session`` is created per call
    and unconditionally closed once the caller is finished with it,
    whether or not an error occurred, so no session is ever left open or
    shared across requests or threads.

    Yields:
        A new SQLAlchemy ``Session``.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
