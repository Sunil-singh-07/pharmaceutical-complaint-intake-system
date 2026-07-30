"""Declarative base for all SQLAlchemy ORM models.

Kept as its own module, separate from both the business Pydantic models
in ``app.models`` and the connection/session machinery in
``app.database``, so ORM model modules (``app.db_models``) can import it
without pulling in engine or session construction code.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base class for all SQLAlchemy ORM models."""
