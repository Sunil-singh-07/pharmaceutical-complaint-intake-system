"""Complaint repository: persistence-only access to complaint records.

Per 04_CODING_CONTRACT.md section 5 and the Phase 10 objective, this
module performs ONLY persistence. It never validates complaint data,
calculates risk, calls the LLM, or orchestrates workflow; those
responsibilities remain with the Validator, RiskEngine, LLMService, and
LangGraph workflow respectively. Callers are expected to already hold
whatever data they want persisted (e.g. serialized from a
``ComplaintState``); this repository simply stores and retrieves it.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.db_models.complaint import ComplaintRecord
from app.repositories.exceptions import (
    ComplaintNotFoundError,
    DatabaseConnectionError,
    DuplicateComplaintError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComplaintRecordDTO:
    """Plain data-transfer object representing a persisted complaint record.

    Returned by every repository method instead of the underlying ORM
    entity, so callers never depend on SQLAlchemy types or risk touching
    a detached ORM instance after its session has closed.

    Attributes:
        id: Surrogate primary key.
        session_id: Unique identifier of the complaint session.
        complaint_text: Most recent raw complaint text processed.
        complaint_data: Serialized ``Complaint`` fields.
        ai_data: Serialized ``AI`` fields.
        validation_data: Serialized ``Validation`` fields.
        risk_data: Serialized ``Risk`` fields.
        workflow_status: Status of the last workflow run.
        created_at: When the record was first created.
        updated_at: When the record was last updated.
    """

    id: int
    session_id: str
    complaint_text: str | None
    complaint_data: dict[str, Any] | None
    ai_data: dict[str, Any] | None
    validation_data: dict[str, Any] | None
    risk_data: dict[str, Any] | None
    workflow_status: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_record(cls, record: ComplaintRecord) -> "ComplaintRecordDTO":
        """Build an immutable DTO snapshot from an ORM record.

        Args:
            record: The ORM entity to convert. Must still be attached to
                a session (or have had its attributes loaded) when this
                is called.

        Returns:
            A ``ComplaintRecordDTO`` capturing the record's current
            field values.
        """
        return cls(
            id=record.id,
            session_id=record.session_id,
            complaint_text=record.complaint_text,
            complaint_data=record.complaint_data,
            ai_data=record.ai_data,
            validation_data=record.validation_data,
            risk_data=record.risk_data,
            workflow_status=record.workflow_status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ComplaintRepository:
    """Persistence-only repository for complaint records.

    Every public method either returns a ``ComplaintRecordDTO`` (or list
    thereof) or raises a typed exception from
    ``app.repositories.exceptions``. No method returns a raw ORM entity,
    and no method contains validation, risk, LLM, or workflow logic.

    Attributes:
        session: The SQLAlchemy session used for all operations. Owned
            and closed by the caller (typically the ``get_db_session``
            FastAPI dependency); this repository never opens or closes
            its own session.
    """

    def __init__(self, session: Session) -> None:
        """Initialize the repository with an open database session.

        Args:
            session: An open SQLAlchemy session.
        """
        self.session = session

    def create_complaint(
        self,
        session_id: str,
        *,
        complaint_text: str | None = None,
        complaint_data: dict[str, Any] | None = None,
        ai_data: dict[str, Any] | None = None,
        validation_data: dict[str, Any] | None = None,
        risk_data: dict[str, Any] | None = None,
        workflow_status: str | None = "pending",
    ) -> ComplaintRecordDTO:
        """Create and persist a new complaint record.

        Args:
            session_id: Unique identifier of the complaint session.
            complaint_text: Raw complaint text, if available.
            complaint_data: Serialized ``Complaint`` fields, if
                available.
            ai_data: Serialized ``AI`` fields, if available.
            validation_data: Serialized ``Validation`` fields, if
                available.
            risk_data: Serialized ``Risk`` fields, if available.
            workflow_status: Initial workflow status to record.

        Returns:
            The newly created record.

        Raises:
            DuplicateComplaintError: If a record for ``session_id``
                already exists.
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        record = ComplaintRecord(
            session_id=session_id,
            complaint_text=complaint_text,
            complaint_data=complaint_data,
            ai_data=ai_data,
            validation_data=validation_data,
            risk_data=risk_data,
            workflow_status=workflow_status,
        )
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            logger.warning("Duplicate complaint session_id '%s'.", session_id)
            raise DuplicateComplaintError(session_id) from exc
        except OperationalError as exc:
            self.session.rollback()
            logger.error("Database connection failed while creating '%s': %s", session_id, exc)
            raise DatabaseConnectionError(str(exc)) from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.error(
                "Unexpected database error while creating '%s': %s", session_id, exc
            )
            raise DatabaseConnectionError(str(exc)) from exc

        self.session.refresh(record)
        logger.info("Created complaint record for session '%s'.", session_id)
        return ComplaintRecordDTO.from_orm_record(record)

    def get_complaint(self, session_id: str) -> ComplaintRecordDTO:
        """Retrieve a complaint record by ``session_id``.

        Args:
            session_id: Identifier of the complaint session to retrieve.

        Returns:
            The matching record.

        Raises:
            ComplaintNotFoundError: If no record exists for
                ``session_id``.
            DatabaseConnectionError: If the database cannot be reached.
        """
        record = self._get_or_raise(session_id)
        return ComplaintRecordDTO.from_orm_record(record)

    def update_complaint(self, session_id: str, **fields: Any) -> ComplaintRecordDTO:
        """Update one or more fields on an existing complaint record.

        Only the fields explicitly passed are modified; any column not
        included in ``**fields`` is left untouched.

        Args:
            session_id: Identifier of the complaint session to update.
            **fields: Column values to update. Keys must match
                ``ComplaintRecord`` column names (e.g.
                ``complaint_data``, ``workflow_status``).

        Returns:
            The updated record.

        Raises:
            ComplaintNotFoundError: If no record exists for
                ``session_id``.
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        record = self._get_or_raise(session_id)
        for field_name, value in fields.items():
            setattr(record, field_name, value)

        try:
            self.session.commit()
        except OperationalError as exc:
            self.session.rollback()
            logger.error("Database connection failed while updating '%s': %s", session_id, exc)
            raise DatabaseConnectionError(str(exc)) from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.error(
                "Unexpected database error while updating '%s': %s", session_id, exc
            )
            raise DatabaseConnectionError(str(exc)) from exc

        self.session.refresh(record)
        logger.info("Updated complaint record for session '%s'.", session_id)
        return ComplaintRecordDTO.from_orm_record(record)

    def delete_complaint(self, session_id: str) -> None:
        """Delete a complaint record by ``session_id``.

        Args:
            session_id: Identifier of the complaint session to delete.

        Raises:
            ComplaintNotFoundError: If no record exists for
                ``session_id``.
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        record = self._get_or_raise(session_id)
        self.session.delete(record)
        try:
            self.session.commit()
        except OperationalError as exc:
            self.session.rollback()
            logger.error("Database connection failed while deleting '%s': %s", session_id, exc)
            raise DatabaseConnectionError(str(exc)) from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.error(
                "Unexpected database error while deleting '%s': %s", session_id, exc
            )
            raise DatabaseConnectionError(str(exc)) from exc

        logger.info("Deleted complaint record for session '%s'.", session_id)

    def list_complaints(self, *, limit: int = 50, offset: int = 0) -> list[ComplaintRecordDTO]:
        """List complaint records, most recently created first.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip, for pagination.

        Returns:
            A list of matching records, most recent first. Empty if no
            records exist.

        Raises:
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        try:
            statement = (
                select(ComplaintRecord)
                .order_by(ComplaintRecord.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            records = self.session.execute(statement).scalars().all()
        except OperationalError as exc:
            logger.error("Database connection failed while listing complaints: %s", exc)
            raise DatabaseConnectionError(str(exc)) from exc
        except SQLAlchemyError as exc:
            logger.error("Unexpected database error while listing complaints: %s", exc)
            raise DatabaseConnectionError(str(exc)) from exc

        return [ComplaintRecordDTO.from_orm_record(record) for record in records]

    def save_workflow_result(
        self,
        session_id: str,
        *,
        complaint_text: str | None = None,
        complaint_data: dict[str, Any] | None = None,
        ai_data: dict[str, Any] | None = None,
        validation_data: dict[str, Any] | None = None,
        risk_data: dict[str, Any] | None = None,
        workflow_status: str | None = "completed",
    ) -> ComplaintRecordDTO:
        """Persist the full result of a workflow run for a session.

        Creates the record if this is the first time ``session_id`` has
        been persisted, otherwise overwrites all of the fields below
        with the values from this workflow run. This is a thin
        convenience wrapper around ``create_complaint`` and
        ``update_complaint``; it performs no extraction, validation, or
        risk logic of its own.

        Args:
            session_id: Identifier of the complaint session.
            complaint_text: Raw complaint text processed by the
                workflow, if available.
            complaint_data: Serialized ``Complaint`` fields.
            ai_data: Serialized ``AI`` fields.
            validation_data: Serialized ``Validation`` fields.
            risk_data: Serialized ``Risk`` fields.
            workflow_status: Status to record for this run.

        Returns:
            The created or updated record.

        Raises:
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        try:
            self._get_or_raise(session_id)
        except ComplaintNotFoundError:
            return self.create_complaint(
                session_id,
                complaint_text=complaint_text,
                complaint_data=complaint_data,
                ai_data=ai_data,
                validation_data=validation_data,
                risk_data=risk_data,
                workflow_status=workflow_status,
            )

        return self.update_complaint(
            session_id,
            complaint_text=complaint_text,
            complaint_data=complaint_data,
            ai_data=ai_data,
            validation_data=validation_data,
            risk_data=risk_data,
            workflow_status=workflow_status,
        )

    def save_validation(
        self, session_id: str, validation_data: dict[str, Any]
    ) -> ComplaintRecordDTO:
        """Persist validation results for an existing complaint record.

        Args:
            session_id: Identifier of the complaint session.
            validation_data: Serialized ``Validation`` fields.

        Returns:
            The updated record.

        Raises:
            ComplaintNotFoundError: If no record exists for
                ``session_id``.
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        return self.update_complaint(session_id, validation_data=validation_data)

    def save_risk_assessment(
        self, session_id: str, risk_data: dict[str, Any]
    ) -> ComplaintRecordDTO:
        """Persist risk assessment results for an existing complaint record.

        Args:
            session_id: Identifier of the complaint session.
            risk_data: Serialized ``Risk`` fields.

        Returns:
            The updated record.

        Raises:
            ComplaintNotFoundError: If no record exists for
                ``session_id``.
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        return self.update_complaint(session_id, risk_data=risk_data)

    def _get_or_raise(self, session_id: str) -> ComplaintRecord:
        """Fetch the ORM record for a ``session_id`` or raise if missing.

        Args:
            session_id: Identifier of the complaint session to fetch.

        Returns:
            The matching ORM entity, still attached to ``self.session``.

        Raises:
            ComplaintNotFoundError: If no record exists for
                ``session_id``.
            DatabaseConnectionError: If the database cannot be reached
                or the operation otherwise fails.
        """
        try:
            statement = select(ComplaintRecord).where(ComplaintRecord.session_id == session_id)
            record = self.session.execute(statement).scalar_one_or_none()
        except OperationalError as exc:
            logger.error("Database connection failed while fetching '%s': %s", session_id, exc)
            raise DatabaseConnectionError(str(exc)) from exc
        except SQLAlchemyError as exc:
            logger.error("Unexpected database error while fetching '%s': %s", session_id, exc)
            raise DatabaseConnectionError(str(exc)) from exc

        if record is None:
            raise ComplaintNotFoundError(session_id)
        return record


def get_complaint_repository(
    session: Session = Depends(get_db_session),
) -> ComplaintRepository:
    """Provide a ``ComplaintRepository`` bound to a request-scoped session.

    Intended for use as a FastAPI dependency, e.g.
    ``Depends(get_complaint_repository)``. The underlying session is
    supplied by ``get_db_session``, which guarantees it is closed once
    the request completes; this function performs no connection
    management of its own.

    Args:
        session: An open SQLAlchemy session, injected by FastAPI.

    Returns:
        A ``ComplaintRepository`` ready to use for the current request.
    """
    return ComplaintRepository(session)

