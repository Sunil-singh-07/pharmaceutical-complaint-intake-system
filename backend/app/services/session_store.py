"""In-memory session store (Session Manager service).

Provides create/get/update/delete operations over ``ComplaintState``
objects, keyed by ``session_id``. This is an MVP implementation backed by
a plain dictionary guarded by a lock for thread safety.

The public interface (``create_session`` / ``get_session`` /
``update_session`` / ``delete_session``) is intentionally storage-agnostic
so it can be swapped for a database-backed implementation in a later
development phase without changing any calling code.
"""

import threading
from datetime import datetime, timezone
from functools import lru_cache

from app.models.complaint_state import ComplaintState
from app.services.exceptions import SessionNotFoundError


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time.
    """
    return datetime.now(timezone.utc)


class SessionStore:
    """Thread-safe in-memory store of ``ComplaintState`` objects.

    Sessions are keyed by ``session_id``. All operations acquire a single
    lock, which is sufficient for MVP-scale concurrent access from
    FastAPI request handlers.
    """

    def __init__(self) -> None:
        """Initialize an empty session store."""
        self._sessions: dict[str, ComplaintState] = {}
        self._lock = threading.Lock()

    def create_session(self) -> ComplaintState:
        """Create and store a new complaint session.

        Returns:
            The newly created ``ComplaintState``, with a freshly generated
            ``session_id``.
        """
        state = ComplaintState()
        with self._lock:
            self._sessions[state.session.session_id] = state
        return state

    def get_session(self, session_id: str) -> ComplaintState:
        """Retrieve a session by its identifier.

        Args:
            session_id: Identifier of the session to retrieve.

        Returns:
            The stored ``ComplaintState``.

        Raises:
            SessionNotFoundError: If no session exists for ``session_id``.
        """
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            raise SessionNotFoundError(session_id)
        return state

    def update_session(self, session_id: str, state: ComplaintState) -> ComplaintState:
        """Replace the stored state for an existing session.

        The session's ``last_updated`` timestamp is refreshed as part of
        the update.

        Args:
            session_id: Identifier of the session to update.
            state: The new ``ComplaintState`` to store. Its
                ``session.session_id`` must match ``session_id``.

        Returns:
            The stored ``ComplaintState``.

        Raises:
            ValueError: If ``state.session.session_id`` does not match
                ``session_id``.
            SessionNotFoundError: If no session exists for ``session_id``.
        """
        if state.session.session_id != session_id:
            raise ValueError(
                f"state.session.session_id '{state.session.session_id}' "
                f"does not match session_id '{session_id}'."
            )

        with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFoundError(session_id)
            state.session.last_updated = _utc_now()
            self._sessions[session_id] = state

        return state

    def delete_session(self, session_id: str) -> None:
        """Delete a session from the store.

        Args:
            session_id: Identifier of the session to delete.

        Raises:
            SessionNotFoundError: If no session exists for ``session_id``.
        """
        with self._lock:
            if session_id not in self._sessions:
                raise SessionNotFoundError(session_id)
            del self._sessions[session_id]


@lru_cache
def get_session_store() -> SessionStore:
    """Return the process-wide singleton ``SessionStore`` instance.

    Using ``lru_cache`` ensures every caller shares the same in-memory
    store within a process, mirroring the pattern used by
    ``app.config.settings.get_settings``.

    Returns:
        The shared ``SessionStore`` instance.
    """
    return SessionStore()
