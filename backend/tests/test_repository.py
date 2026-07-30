"""Tests for the complaint repository (Phase 10).

These tests exercise ``app.repositories.complaint_repository`` against a
real SQLite in-memory database created fresh for every test, via
SQLAlchemy's ORM. No running MySQL server is required. A SQLite
in-memory database is used ONLY for testing, per the Phase 10
instructions; production configuration still targets MySQL through
``Settings.database_url``.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.repositories.complaint_repository import (
    ComplaintRepository,
    get_complaint_repository,
)
from app.repositories.exceptions import (
    ComplaintNotFoundError,
    DatabaseConnectionError,
    DuplicateComplaintError,
)

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Provide a SQLAlchemy session backed by a fresh in-memory SQLite DB.

    ``StaticPool`` keeps a single connection alive for the engine's
    lifetime so the in-memory database (and its tables) persists across
    every query made through this session, rather than resetting on each
    new connection.

    Yields:
        An open SQLAlchemy session with all tables already created.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def repository(db_session: Session) -> ComplaintRepository:
    """Provide a ``ComplaintRepository`` bound to the test session.

    Args:
        db_session: The isolated in-memory database session.

    Returns:
        A ``ComplaintRepository`` ready for use in a test.
    """
    return ComplaintRepository(db_session)


# --------------------------------------------------------------------------
# create_complaint
# --------------------------------------------------------------------------


def test_create_complaint_persists_record(repository: ComplaintRepository) -> None:
    """Creating a complaint should persist all provided fields."""
    record = repository.create_complaint(
        "session-1",
        complaint_text="Tablet arrived broken.",
        complaint_data={"product_name": "Painex 500mg"},
        workflow_status="pending",
    )

    assert record.id is not None
    assert record.session_id == "session-1"
    assert record.complaint_text == "Tablet arrived broken."
    assert record.complaint_data == {"product_name": "Painex 500mg"}
    assert record.workflow_status == "pending"
    assert record.created_at is not None
    assert record.updated_at is not None


def test_create_complaint_duplicate_session_id_raises(
    repository: ComplaintRepository,
) -> None:
    """Creating a second record with the same session_id should fail."""
    repository.create_complaint("session-1", complaint_text="First.")

    with pytest.raises(DuplicateComplaintError) as exc_info:
        repository.create_complaint("session-1", complaint_text="Second.")

    assert exc_info.value.session_id == "session-1"


def test_create_complaint_rolls_back_on_duplicate(
    repository: ComplaintRepository, db_session: Session
) -> None:
    """A failed duplicate insert must not corrupt the existing record.

    Verifies transaction rollback behaviour: after the failed insert, the
    original record is unchanged and the session remains usable for
    further operations.
    """
    repository.create_complaint("session-1", complaint_text="Original.")

    with pytest.raises(DuplicateComplaintError):
        repository.create_complaint("session-1", complaint_text="Attempted overwrite.")

    # The session must still be usable after the rollback.
    stored = repository.get_complaint("session-1")
    assert stored.complaint_text == "Original."

    all_records = repository.list_complaints()
    assert len(all_records) == 1


# --------------------------------------------------------------------------
# get_complaint
# --------------------------------------------------------------------------


def test_get_complaint_returns_created_record(repository: ComplaintRepository) -> None:
    """Retrieving an existing record should return matching data."""
    repository.create_complaint("session-1", complaint_text="Tablet arrived broken.")

    record = repository.get_complaint("session-1")

    assert record.session_id == "session-1"
    assert record.complaint_text == "Tablet arrived broken."


def test_get_complaint_missing_raises_not_found(repository: ComplaintRepository) -> None:
    """Retrieving a non-existent session_id should raise a typed error."""
    with pytest.raises(ComplaintNotFoundError) as exc_info:
        repository.get_complaint("does-not-exist")

    assert exc_info.value.session_id == "does-not-exist"


# --------------------------------------------------------------------------
# update_complaint
# --------------------------------------------------------------------------


def test_update_complaint_updates_only_given_fields(
    repository: ComplaintRepository,
) -> None:
    """Updating should change only the passed fields, leaving others intact."""
    repository.create_complaint(
        "session-1", complaint_text="Original text.", workflow_status="pending"
    )

    updated = repository.update_complaint("session-1", workflow_status="completed")

    assert updated.workflow_status == "completed"
    assert updated.complaint_text == "Original text."


def test_update_complaint_missing_raises_not_found(repository: ComplaintRepository) -> None:
    """Updating a non-existent session_id should raise a typed error."""
    with pytest.raises(ComplaintNotFoundError):
        repository.update_complaint("does-not-exist", workflow_status="completed")


# --------------------------------------------------------------------------
# delete_complaint
# --------------------------------------------------------------------------


def test_delete_complaint_removes_record(repository: ComplaintRepository) -> None:
    """Deleting a record should make it unretrievable afterwards."""
    repository.create_complaint("session-1", complaint_text="Tablet arrived broken.")

    repository.delete_complaint("session-1")

    with pytest.raises(ComplaintNotFoundError):
        repository.get_complaint("session-1")


def test_delete_complaint_missing_raises_not_found(repository: ComplaintRepository) -> None:
    """Deleting a non-existent session_id should raise a typed error."""
    with pytest.raises(ComplaintNotFoundError):
        repository.delete_complaint("does-not-exist")


# --------------------------------------------------------------------------
# list_complaints
# --------------------------------------------------------------------------


def test_list_complaints_returns_all_records(repository: ComplaintRepository) -> None:
    """Listing should return every persisted record."""
    repository.create_complaint("session-1")
    repository.create_complaint("session-2")
    repository.create_complaint("session-3")

    records = repository.list_complaints()

    assert {record.session_id for record in records} == {"session-1", "session-2", "session-3"}


def test_list_complaints_respects_limit(repository: ComplaintRepository) -> None:
    """Listing with a limit should cap the number of returned records."""
    repository.create_complaint("session-1")
    repository.create_complaint("session-2")
    repository.create_complaint("session-3")

    records = repository.list_complaints(limit=2)

    assert len(records) == 2


def test_list_complaints_empty_returns_empty_list(repository: ComplaintRepository) -> None:
    """Listing with no records should return an empty list, not raise."""
    assert repository.list_complaints() == []


# --------------------------------------------------------------------------
# save_workflow_result
# --------------------------------------------------------------------------


def test_save_workflow_result_creates_when_missing(repository: ComplaintRepository) -> None:
    """Saving a workflow result for a new session should create a record."""
    record = repository.save_workflow_result(
        "session-1",
        complaint_text="Tablet arrived broken.",
        complaint_data={"product_name": "Painex 500mg"},
        ai_data={"summary": "Broken tablet complaint."},
        validation_data={"is_valid": True, "missing_fields": []},
        risk_data={"priority": "Medium", "score": 40},
        workflow_status="completed",
    )

    assert record.session_id == "session-1"
    assert record.complaint_data == {"product_name": "Painex 500mg"}
    assert record.ai_data == {"summary": "Broken tablet complaint."}
    assert record.validation_data == {"is_valid": True, "missing_fields": []}
    assert record.risk_data == {"priority": "Medium", "score": 40}
    assert record.workflow_status == "completed"


def test_save_workflow_result_updates_when_existing(repository: ComplaintRepository) -> None:
    """Saving a workflow result for an existing session should update it."""
    repository.create_complaint("session-1", workflow_status="pending")

    updated = repository.save_workflow_result(
        "session-1",
        complaint_text="Tablet arrived broken.",
        complaint_data={"product_name": "Painex 500mg"},
        validation_data={"is_valid": True, "missing_fields": []},
        risk_data={"priority": "High", "score": 70},
        workflow_status="completed",
    )

    assert updated.workflow_status == "completed"
    assert updated.risk_data == {"priority": "High", "score": 70}

    all_records = repository.list_complaints()
    assert len(all_records) == 1


# --------------------------------------------------------------------------
# save_validation / save_risk_assessment
# --------------------------------------------------------------------------


def test_save_validation_updates_only_validation_field(
    repository: ComplaintRepository,
) -> None:
    """Saving validation results should not disturb other fields."""
    repository.create_complaint(
        "session-1",
        complaint_text="Tablet arrived broken.",
        risk_data={"priority": "Low", "score": 10},
    )

    updated = repository.save_validation(
        "session-1", {"is_valid": False, "missing_fields": ["batch_number"]}
    )

    assert updated.validation_data == {"is_valid": False, "missing_fields": ["batch_number"]}
    assert updated.complaint_text == "Tablet arrived broken."
    assert updated.risk_data == {"priority": "Low", "score": 10}


def test_save_risk_assessment_updates_only_risk_field(
    repository: ComplaintRepository,
) -> None:
    """Saving risk assessment results should not disturb other fields."""
    repository.create_complaint(
        "session-1",
        complaint_text="Tablet arrived broken.",
        validation_data={"is_valid": True, "missing_fields": []},
    )

    updated = repository.save_risk_assessment("session-1", {"priority": "Critical", "score": 95})

    assert updated.risk_data == {"priority": "Critical", "score": 95}
    assert updated.complaint_text == "Tablet arrived broken."
    assert updated.validation_data == {"is_valid": True, "missing_fields": []}


def test_save_validation_missing_session_raises_not_found(
    repository: ComplaintRepository,
) -> None:
    """Saving validation for a non-existent session should raise."""
    with pytest.raises(ComplaintNotFoundError):
        repository.save_validation("does-not-exist", {"is_valid": True})


def test_save_risk_assessment_missing_session_raises_not_found(
    repository: ComplaintRepository,
) -> None:
    """Saving risk assessment for a non-existent session should raise."""
    with pytest.raises(ComplaintNotFoundError):
        repository.save_risk_assessment("does-not-exist", {"priority": "Low"})


# --------------------------------------------------------------------------
# Connection failure handling
# --------------------------------------------------------------------------


def _raise_operational_error(*_args: object, **_kwargs: object) -> None:
    """Raise a ``sqlalchemy.exc.OperationalError`` to simulate a lost connection.

    Raises:
        OperationalError: Always.
    """
    raise OperationalError("statement", {}, Exception("connection lost"))


def test_get_complaint_connection_failure_raises_database_connection_error(
    repository: ComplaintRepository,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection failure during a read should surface as a typed error."""
    repository.create_complaint("session-1")
    monkeypatch.setattr(db_session, "execute", _raise_operational_error)

    with pytest.raises(DatabaseConnectionError):
        repository.get_complaint("session-1")


def test_create_complaint_commit_failure_rolls_back_and_raises(
    repository: ComplaintRepository,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A commit failure during create should roll back and raise a typed error."""
    monkeypatch.setattr(db_session, "commit", _raise_operational_error)

    with pytest.raises(DatabaseConnectionError):
        repository.create_complaint("session-1")


def test_update_complaint_commit_failure_rolls_back_and_raises(
    repository: ComplaintRepository,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A commit failure during update should roll back and raise a typed error."""
    repository.create_complaint("session-1")
    monkeypatch.setattr(db_session, "commit", _raise_operational_error)

    with pytest.raises(DatabaseConnectionError):
        repository.update_complaint("session-1", workflow_status="completed")


def test_list_complaints_connection_failure_raises_database_connection_error(
    repository: ComplaintRepository,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection failure while listing should surface as a typed error."""
    monkeypatch.setattr(db_session, "execute", _raise_operational_error)

    with pytest.raises(DatabaseConnectionError):
        repository.list_complaints()


# --------------------------------------------------------------------------
# FastAPI dependency wiring
# --------------------------------------------------------------------------


def test_get_complaint_repository_returns_repository_bound_to_session(
    db_session: Session,
) -> None:
    """The FastAPI dependency should wrap the given session in a repository."""
    repository = get_complaint_repository(db_session)

    assert isinstance(repository, ComplaintRepository)
    assert repository.session is db_session
