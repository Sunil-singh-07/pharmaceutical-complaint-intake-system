"""Tests for the Complaints API routes (Phase 9).

These tests exercise the FastAPI routes in ``app.api.complaints``
through ``TestClient`` only. Per the Phase 9 instructions, the LangGraph
workflow is always mocked here via dependency overrides, so no test in
this module builds a real graph, imports ``langgraph``, or calls a real
LLM. This keeps the module runnable regardless of whether the optional
``langgraph`` package is installed.

The Session Store is overridden with a fresh, isolated instance per test
so tests never depend on or leak state to the process-wide singleton
used outside of tests.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.complaints import get_llm_service, get_workflow_runner
from app.main import app
from app.models.complaint_state import ComplaintState
from app.services.exceptions import LLMEmptyResponseError
from app.services.session_store import SessionStore, get_session_store

# --------------------------------------------------------------------------
# Fakes / helpers
# --------------------------------------------------------------------------


def _fake_workflow_success(
    message: str, state: ComplaintState, *, llm_service: object
) -> ComplaintState:
    """Fake ``run_complaint_workflow`` simulating a fully processed complaint.

    Mirrors the shape of a real workflow result (complaint fields,
    validation, and risk populated) without touching the LLM Service,
    the Validator, the Risk Engine, or LangGraph itself.

    Args:
        message: Raw complaint text (ignored; used to populate the
            description field for observability in assertions).
        state: The current ``ComplaintState`` for the session.
        llm_service: Ignored. Present only to match the real
            ``run_complaint_workflow`` signature.

    Returns:
        The updated ``ComplaintState``.
    """
    complaint = state.complaint.model_copy(
        update={
            "product_name": "Painex 500mg",
            "batch_number": "B12345",
            "complaint_type": "Broken Tablet",
            "complaint_description": message,
        }
    )
    validation = state.validation.model_copy(update={"is_valid": True, "missing_fields": []})
    risk = state.risk.model_copy(update={"priority": "Medium", "score": 40})
    return state.model_copy(
        update={"complaint": complaint, "validation": validation, "risk": risk}
    )


def _fake_workflow_blank_text(
    message: str, state: ComplaintState, *, llm_service: object
) -> ComplaintState:
    """Fake ``run_complaint_workflow`` simulating a blank-text failure.

    Args:
        message: Raw complaint text (ignored).
        state: The current ``ComplaintState`` for the session (ignored).
        llm_service: Ignored.

    Raises:
        ValueError: Always, mirroring the real workflow's blank-text
            check.
    """
    raise ValueError("complaint_text must not be empty or blank.")


def _fake_workflow_llm_error(
    message: str, state: ComplaintState, *, llm_service: object
) -> ComplaintState:
    """Fake ``run_complaint_workflow`` simulating an LLM Service failure.

    Args:
        message: Raw complaint text (ignored).
        state: The current ``ComplaintState`` for the session (ignored).
        llm_service: Ignored.

    Raises:
        LLMEmptyResponseError: Always, mirroring a real LLM Service
            failure.
    """
    raise LLMEmptyResponseError("LLM provider returned an empty response.")


@pytest.fixture
def session_store() -> SessionStore:
    """Provide a fresh, isolated ``SessionStore`` for a single test.

    Returns:
        A new, empty ``SessionStore`` instance.
    """
    return SessionStore()


@pytest.fixture
def client(session_store: SessionStore) -> Iterator[TestClient]:
    """Provide a ``TestClient`` with the session store dependency overridden.

    The LLM Service and workflow runner dependencies are left to be
    overridden by individual tests, since the desired fake behaviour
    differs per test.

    Args:
        session_store: The isolated session store to inject.

    Yields:
        A configured ``TestClient``.
    """
    app.dependency_overrides[get_session_store] = lambda: session_store
    app.dependency_overrides[get_llm_service] = lambda: object()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session_store, None)
        app.dependency_overrides.pop(get_llm_service, None)
        app.dependency_overrides.pop(get_workflow_runner, None)


# --------------------------------------------------------------------------
# POST /api/complaints
# --------------------------------------------------------------------------


def test_create_complaint_returns_201_and_processed_state(client: TestClient) -> None:
    """A valid complaint message should be created and fully processed."""
    app.dependency_overrides[get_workflow_runner] = lambda: _fake_workflow_success

    response = client.post("/api/complaints", json={"message": "Tablet arrived broken."})

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["complaint"]["product_name"] == "Painex 500mg"
    assert body["data"]["complaint"]["complaint_description"] == "Tablet arrived broken."
    assert body["data"]["validation"]["is_valid"] is True
    assert body["data"]["risk"]["priority"] == "Medium"
    assert "session_id" in body["data"]["session"]


def test_create_complaint_persists_session(
    client: TestClient, session_store: SessionStore
) -> None:
    """A created complaint session should be retrievable from the store."""
    app.dependency_overrides[get_workflow_runner] = lambda: _fake_workflow_success

    response = client.post("/api/complaints", json={"message": "Tablet arrived broken."})
    session_id = response.json()["data"]["session"]["session_id"]

    stored_state = session_store.get_session(session_id)
    assert stored_state.complaint.product_name == "Painex 500mg"


def test_create_complaint_rejects_empty_message(client: TestClient) -> None:
    """An empty message should fail request schema validation with 422."""
    app.dependency_overrides[get_workflow_runner] = lambda: _fake_workflow_success

    response = client.post("/api/complaints", json={"message": ""})

    assert response.status_code == 422


def test_create_complaint_rejects_blank_message(client: TestClient) -> None:
    """Whitespace-only text should surface as a 400 via the workflow's own check."""
    app.dependency_overrides[get_workflow_runner] = lambda: _fake_workflow_blank_text

    response = client.post("/api/complaints", json={"message": "   "})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False


def test_create_complaint_returns_502_on_llm_failure(client: TestClient) -> None:
    """An LLM Service failure should surface as a 502 error response."""
    app.dependency_overrides[get_workflow_runner] = lambda: _fake_workflow_llm_error

    response = client.post("/api/complaints", json={"message": "Tablet arrived broken."})

    assert response.status_code == 502
    body = response.json()
    assert body["success"] is False


def test_create_complaint_requires_message_field(client: TestClient) -> None:
    """A missing 'message' field should fail request schema validation."""
    app.dependency_overrides[get_workflow_runner] = lambda: _fake_workflow_success

    response = client.post("/api/complaints", json={})

    assert response.status_code == 422


# --------------------------------------------------------------------------
# GET /api/complaints/{session_id}
# --------------------------------------------------------------------------


def test_get_complaint_returns_stored_state(
    client: TestClient, session_store: SessionStore
) -> None:
    """An existing session should be retrievable by its session_id."""
    state = session_store.create_session()
    state.complaint.product_name = "Painex 500mg"
    session_store.update_session(state.session.session_id, state)

    response = client.get(f"/api/complaints/{state.session.session_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["complaint"]["product_name"] == "Painex 500mg"
    assert body["data"]["session"]["session_id"] == state.session.session_id


def test_get_complaint_returns_404_for_unknown_session(client: TestClient) -> None:
    """An unknown session_id should return a 404 error response."""
    response = client.get("/api/complaints/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False


# --------------------------------------------------------------------------
# GET /api/complaints/{session_id}/risk
# --------------------------------------------------------------------------


def test_get_complaint_risk_returns_stored_risk(
    client: TestClient, session_store: SessionStore
) -> None:
    """An existing session's risk data should be retrievable."""
    state = session_store.create_session()
    state.risk.priority = "Critical"
    state.risk.score = 90
    session_store.update_session(state.session.session_id, state)

    response = client.get(f"/api/complaints/{state.session.session_id}/risk")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["risk"]["priority"] == "Critical"
    assert body["data"]["risk"]["score"] == 90


def test_get_complaint_risk_returns_404_for_unknown_session(client: TestClient) -> None:
    """An unknown session_id should return a 404 error response."""
    response = client.get("/api/complaints/does-not-exist/risk")

    assert response.status_code == 404


# --------------------------------------------------------------------------
# GET /api/complaints/{session_id}/validation
# --------------------------------------------------------------------------


def test_get_complaint_validation_returns_stored_validation(
    client: TestClient, session_store: SessionStore
) -> None:
    """An existing session's validation data should be retrievable."""
    state = session_store.create_session()
    state.validation.is_valid = False
    state.validation.missing_fields = ["batch_number"]
    session_store.update_session(state.session.session_id, state)

    response = client.get(f"/api/complaints/{state.session.session_id}/validation")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["validation"]["is_valid"] is False
    assert body["data"]["validation"]["missing_fields"] == ["batch_number"]


def test_get_complaint_validation_returns_404_for_unknown_session(client: TestClient) -> None:
    """An unknown session_id should return a 404 error response."""
    response = client.get("/api/complaints/does-not-exist/validation")

    assert response.status_code == 404
