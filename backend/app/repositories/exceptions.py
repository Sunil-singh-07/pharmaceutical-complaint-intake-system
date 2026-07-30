"""Repository-layer exceptions.

Raised by repositories to translate low-level database failures
(missing rows, constraint violations, connection errors) into typed
exceptions that callers can handle without depending on SQLAlchemy
directly.
"""


class RepositoryError(Exception):
    """Base exception for all repository failures."""


class ComplaintNotFoundError(RepositoryError):
    """Raised when a requested complaint record does not exist.

    Attributes:
        session_id: Identifier of the complaint session that could not
            be found.
    """

    def __init__(self, session_id: str) -> None:
        """Initialize the exception with the missing session's identifier.

        Args:
            session_id: Identifier of the complaint session that could
                not be found.
        """
        self.session_id = session_id
        super().__init__(f"Complaint record for session '{session_id}' was not found.")


class DuplicateComplaintError(RepositoryError):
    """Raised when creating a complaint record with a duplicate session_id.

    Attributes:
        session_id: Identifier that already exists in the database.
    """

    def __init__(self, session_id: str) -> None:
        """Initialize the exception with the duplicate identifier.

        Args:
            session_id: Identifier that already exists in the database.
        """
        self.session_id = session_id
        super().__init__(f"A complaint record for session '{session_id}' already exists.")


class DatabaseConnectionError(RepositoryError):
    """Raised when the repository cannot reach or use the database.

    Attributes:
        reason: Description of the underlying connection failure.
    """

    def __init__(self, reason: str) -> None:
        """Initialize the exception with the underlying failure reason.

        Args:
            reason: Description of the underlying connection failure.
        """
        self.reason = reason
        super().__init__(f"Database connection failed: {reason}")
