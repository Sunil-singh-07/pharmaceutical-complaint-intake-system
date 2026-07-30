"""ORM model for persisted complaint records.

Maps a complaint session's persistence-relevant data onto a single
database table. Extraction, validation, and risk output are stored as
opaque JSON payloads rather than duplicated column-by-column, so this
model never has to be kept in sync with the business models in
``app.models``. Per 04_CODING_CONTRACT.md section 5, this module
contains no business logic: it describes storage shape only.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time.
    """
    return datetime.now(timezone.utc)


class ComplaintRecord(Base):
    """Persisted complaint session record.

    One row per complaint session, keyed by ``session_id``. Rows are
    created and updated exclusively through
    ``app.repositories.complaint_repository.ComplaintRepository``.

    Attributes:
        id: Surrogate primary key.
        session_id: Unique identifier of the complaint session (matches
            ``ComplaintState.session.session_id``).
        complaint_text: Most recent raw complaint text processed for
            this session.
        complaint_data: Serialized ``Complaint`` fields, as a JSON
            object.
        ai_data: Serialized ``AI`` fields, as a JSON object.
        validation_data: Serialized ``Validation`` fields, as a JSON
            object.
        risk_data: Serialized ``Risk`` fields, as a JSON object.
        workflow_status: Status of the last workflow run for this
            session (e.g. ``"pending"``, ``"completed"``, ``"failed"``).
        created_at: When the record was first created.
        updated_at: When the record was last updated.
    """

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    complaint_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    complaint_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ai_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    risk_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    workflow_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )
