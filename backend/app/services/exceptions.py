"""Service-layer exceptions.

Shared exception types raised by business logic services, so API routes
can catch them and translate them into consistent HTTP error responses in
a later development phase.
"""


class SessionNotFoundError(Exception):
    """Raised when a requested session does not exist in the store.

    Attributes:
        session_id: Identifier of the session that could not be found.
    """

    def __init__(self, session_id: str) -> None:
        """Initialize the exception with the missing session's identifier.

        Args:
            session_id: Identifier of the session that could not be found.
        """
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' was not found.")


class LLMServiceError(Exception):
    """Base exception for all LLM Service failures."""


class LLMConfigurationError(LLMServiceError):
    """Raised when an LLM provider is missing required configuration.

    Examples include a missing API key or a missing provider SDK
    dependency, or a missing prompt template file.
    """


class LLMProviderError(LLMServiceError):
    """Raised when an LLM provider call fails for a non-timeout reason.

    Attributes:
        provider_name: Name of the provider that raised the error.
        reason: Description of the underlying failure.
    """

    def __init__(self, provider_name: str, reason: str) -> None:
        """Initialize the exception with the failing provider and reason.

        Args:
            provider_name: Name of the provider that raised the error.
            reason: Description of the underlying failure.
        """
        self.provider_name = provider_name
        self.reason = reason
        super().__init__(f"LLM provider '{provider_name}' failed: {reason}")


class LLMTimeoutError(LLMServiceError):
    """Raised when an LLM provider does not respond within the timeout.

    Attributes:
        provider_name: Name of the provider that timed out.
        timeout_seconds: Timeout that was exceeded, in seconds.
    """

    def __init__(self, provider_name: str, timeout_seconds: float) -> None:
        """Initialize the exception with the provider and timeout used.

        Args:
            provider_name: Name of the provider that timed out.
            timeout_seconds: Timeout that was exceeded, in seconds.
        """
        self.provider_name = provider_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"LLM provider '{provider_name}' timed out after {timeout_seconds}s."
        )


class LLMEmptyResponseError(LLMServiceError):
    """Raised when an LLM provider returns an empty or blank response."""


class PDFServiceError(Exception):
    """Base exception for all PDF Service failures."""


class PDFInvalidFileTypeError(PDFServiceError):
    """Raised when an uploaded file is not a valid PDF file.

    Attributes:
        filename: Name of the offending file.
    """

    def __init__(self, filename: str) -> None:
        """Initialize the exception with the offending file's name.

        Args:
            filename: Name of the offending file.
        """
        self.filename = filename
        super().__init__(f"File '{filename}' is not a valid PDF file.")


class PDFCorruptedError(PDFServiceError):
    """Raised when an uploaded PDF cannot be opened or read.

    Attributes:
        filename: Name of the offending file.
        reason: Description of the underlying failure.
    """

    def __init__(self, filename: str, reason: str) -> None:
        """Initialize the exception with the offending file and reason.

        Args:
            filename: Name of the offending file.
            reason: Description of the underlying failure.
        """
        self.filename = filename
        self.reason = reason
        super().__init__(f"PDF file '{filename}' is corrupted: {reason}")


class PDFEmptyError(PDFServiceError):
    """Raised when an uploaded PDF contains no extractable text.

    Attributes:
        filename: Name of the offending file.
    """

    def __init__(self, filename: str) -> None:
        """Initialize the exception with the offending file's name.

        Args:
            filename: Name of the offending file.
        """
        self.filename = filename
        super().__init__(f"PDF file '{filename}' contains no extractable text.")


class LLMResponseParsingError(LLMServiceError):
    """Raised when an LLM response is not valid, schema-conformant JSON.

    Attributes:
        raw_response: The raw response text that failed to parse.
        reason: Description of the underlying parsing or validation
            failure.
    """

    def __init__(self, raw_response: str, reason: str) -> None:
        """Initialize the exception with the offending response and reason.

        Args:
            raw_response: The raw response text that failed to parse.
            reason: Description of the underlying parsing or validation
                failure.
        """
        self.raw_response = raw_response
        self.reason = reason
        super().__init__(f"Failed to parse LLM response: {reason}")
