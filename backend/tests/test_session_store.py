"""Tests for the in-memory SessionStore service."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models.complaint_state import ComplaintState
from app.services.exceptions import SessionNotFoundError
from app.services.session_store import SessionStore, get_session_store


def test_create_session_returns_complaint_state_with_id() -> None:
    """create_session should return a ComplaintState with a session_id."""
    store = SessionStore()

    state = store.create_session()

    assert isinstance(state, ComplaintState)
    assert state.session.session_id


def test_get_session_returns_stored_state() -> None:
    """get_session should return the exact state created for a session."""
    store = SessionStore()
    created = store.create_session()

    fetched = store.get_session(created.session.session_id)

    assert fetched.session.session_id == created.session.session_id


def test_get_session_raises_for_unknown_id() -> None:
    """get_session should raise SessionNotFoundError for an unknown id."""
    store = SessionStore()

    with pytest.raises(SessionNotFoundError):
        store.get_session("does-not-exist")


def test_update_session_replaces_stored_state() -> None:
    """update_session should persist changes made to the ComplaintState."""
    store = SessionStore()
    created = store.create_session()
    created.complaint.product_name = "Painex"

    updated = store.update_session(created.session.session_id, created)

    assert updated.complaint.product_name == "Painex"
    fetched = store.get_session(created.session.session_id)
    assert fetched.complaint.product_name == "Painex"


def test_update_session_bumps_last_updated_timestamp() -> None:
    """update_session should refresh the session's last_updated timestamp."""
    store = SessionStore()
    created = store.create_session()
    original_updated_at = created.session.last_updated

    updated = store.update_session(created.session.session_id, created)

    assert updated.session.last_updated >= original_updated_at


def test_update_session_raises_for_unknown_id() -> None:
    """update_session should raise SessionNotFoundError for an unknown id."""
    store = SessionStore()
    orphan_state = ComplaintState()

    with pytest.raises(SessionNotFoundError):
        store.update_session(orphan_state.session.session_id, orphan_state)


def test_update_session_raises_for_mismatched_session_id() -> None:
    """update_session should reject a state whose session_id doesn't match."""
    store = SessionStore()
    created = store.create_session()
    other_state = ComplaintState()

    with pytest.raises(ValueError):
        store.update_session(created.session.session_id, other_state)


def test_delete_session_removes_state() -> None:
    """delete_session should remove the session so it can no longer be read."""
    store = SessionStore()
    created = store.create_session()

    store.delete_session(created.session.session_id)

    with pytest.raises(SessionNotFoundError):
        store.get_session(created.session.session_id)


def test_delete_session_raises_for_unknown_id() -> None:
    """delete_session should raise SessionNotFoundError for an unknown id."""
    store = SessionStore()

    with pytest.raises(SessionNotFoundError):
        store.delete_session("does-not-exist")


def test_sessions_are_independent() -> None:
    """Multiple sessions in the same store should not affect one another."""
    store = SessionStore()
    first = store.create_session()
    second = store.create_session()
    first.complaint.product_name = "Painex"
    store.update_session(first.session.session_id, first)

    fetched_second = store.get_session(second.session.session_id)

    assert fetched_second.complaint.product_name is None


def test_get_session_store_returns_singleton() -> None:
    """get_session_store should return the same instance on every call."""
    first = get_session_store()
    second = get_session_store()

    assert first is second


def test_concurrent_session_creation_is_thread_safe() -> None:
    """Many concurrent create_session calls should each yield a unique id."""
    store = SessionStore()

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: store.create_session(), range(200)))

    session_ids = {state.session.session_id for state in results}
    assert len(session_ids) == 200
