"""Session sub-model of ComplaintState."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.enums import SessionStatus


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time.
    """
    return datetime.now(timezone.utc)


class Session(BaseModel):
    """Metadata describing a complaint intake session.

    Attributes:
        session_id: Unique identifier for the session.
        created_at: Timestamp when the session was created.
        last_updated: Timestamp when the session was last modified.
        status: Current lifecycle status of the session.
    """

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=_utc_now)
    last_updated: datetime = Field(default_factory=_utc_now)
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
