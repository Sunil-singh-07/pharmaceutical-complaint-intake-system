"""Tests for the LLM Service (structured information extraction only).

No test in this module calls a real LLM. ``GroqProvider`` tests install a
fake ``groq`` module into ``sys.modules`` so provider wiring can be
exercised without the real SDK or network access.
"""

import sys
import types
from pathlib import Path

import pytest

from app.services.exceptions import (
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMResponseParsingError,
    LLMTimeoutError,
)
from app.services.llm_service import GroqProvider, LLMProvider, LLMService

# --------------------------------------------------------------------------
# Fakes / helpers
# --------------------------------------------------------------------------


class FakeProvider(LLMProvider):
    """LLMProvider test double that never performs real network calls.

    Attributes:
        response: The raw text to return from ``generate``, if not
            configured to raise.
        error: An exception instance to raise from ``generate``, if set.
        received_prompts: Every prompt passed to ``generate``, in order.
    """

    def __init__(self, response: str = "", error: Exception | None = None) -> None:
        """Initialize the fake provider.

        Args:
            response: The raw text to return from ``generate``.
            error: An exception to raise from ``generate`` instead of
                returning ``response``.
        """
        self.response = response
        self.error = error
        self.received_prompts: list[str] = []
        self.received_timeouts: list[float] = []

    def generate(self, prompt: str, *, timeout: float) -> str:
        """Record the call and return the configured response or error.

        Args:
            prompt: The prompt passed by the caller.
            timeout: The timeout passed by the caller.

        Returns:
            The configured ``response``.

        Raises:
            Exception: The configured ``error``, if set.
        """
        self.received_prompts.append(prompt)
        self.received_timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return self.response


def _valid_json_response(**overrides: object) -> str:
    """Build a valid JSON extraction response as a string.

    Args:
        **overrides: Field overrides applied on top of a full baseline.

    Returns:
        A JSON string representing an extraction result.
    """
    import json

    base = {
        "product_name": "Product X",
        "batch_number": "ABC123",
        "complaint_type": "Adverse Event",
        "severity": "Medium",
        "description": "Patient experienced vomiting after taking Product X.",
        "reported_event": "Vomiting",
        "confidence": 0.87,
    }
    base.update(overrides)
    return json.dumps(base)


@pytest.fixture
def fake_groq_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install a fake ``groq`` module into ``sys.modules`` for provider tests.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.

    Returns:
        The fake module, so tests can configure its ``Groq`` client.
    """
    fake_module = types.ModuleType("groq")

    class FakeAPITimeoutError(Exception):
        """Stand-in for groq.APITimeoutError."""

    class FakeGroq:
        """Stand-in for groq.Groq; test wires .chat.completions.create."""

        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.chat: types.SimpleNamespace | None = None

    fake_module.Groq = FakeGroq  # type: ignore[attr-defined]
    fake_module.APITimeoutError = FakeAPITimeoutError  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "groq", fake_module)
    return fake_module


def _fake_chat_response(content: str | None) -> types.SimpleNamespace:
    """Build a fake Groq chat-completion response object.

    Args:
        content: The message content the fake response should carry.

    Returns:
        An object shaped like ``groq``'s completion response.
    """
    message = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(choices=[choice])


# --------------------------------------------------------------------------
# Successful extraction
# --------------------------------------------------------------------------


def test_successful_extraction_returns_populated_fields() -> None:
    """A well-formed JSON response should populate every field."""
    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider, timeout_seconds=10.0)

    result = service.extract_information(
        "The patient experienced vomiting after taking Product X. "
        "Batch ABC123. Purchased yesterday."
    )

    assert result.product_name == "Product X"
    assert result.batch_number == "ABC123"
    assert result.complaint_type == "Adverse Event"
    assert result.severity == "Medium"
    assert result.reported_event == "Vomiting"
    assert result.confidence == 0.87


def test_extraction_sends_complaint_text_in_prompt() -> None:
    """The complaint text should be embedded in the rendered prompt."""
    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider)

    service.extract_information("Unique marker text 12345.")

    assert len(provider.received_prompts) == 1
    assert "Unique marker text 12345." in provider.received_prompts[0]
    assert "{{complaint_text}}" not in provider.received_prompts[0]


def test_extraction_passes_configured_timeout_to_provider() -> None:
    """The configured timeout should be forwarded to the provider."""
    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider, timeout_seconds=7.5)

    service.extract_information("Some complaint text.")

    assert provider.received_timeouts == [7.5]


def test_extraction_strips_markdown_code_fences() -> None:
    """A response wrapped in ```json fences should still parse correctly."""
    fenced = "```json\n" + _valid_json_response() + "\n```"
    provider = FakeProvider(response=fenced)
    service = LLMService(provider=provider)

    result = service.extract_information("Some complaint text.")

    assert result.product_name == "Product X"


# --------------------------------------------------------------------------
# Empty complaint text
# --------------------------------------------------------------------------


def test_blank_complaint_text_raises_value_error() -> None:
    """Blank complaint text should be rejected before calling the provider."""
    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider)

    with pytest.raises(ValueError):
        service.extract_information("   ")

    assert provider.received_prompts == []


# --------------------------------------------------------------------------
# Malformed JSON
# --------------------------------------------------------------------------


def test_malformed_json_raises_response_parsing_error() -> None:
    """Non-JSON provider output should raise LLMResponseParsingError."""
    provider = FakeProvider(response="this is not json {")
    service = LLMService(provider=provider)

    with pytest.raises(LLMResponseParsingError):
        service.extract_information("Some complaint text.")


def test_json_array_raises_response_parsing_error() -> None:
    """A top-level JSON array (not an object) should be rejected."""
    provider = FakeProvider(response="[1, 2, 3]")
    service = LLMService(provider=provider)

    with pytest.raises(LLMResponseParsingError):
        service.extract_information("Some complaint text.")


def test_unknown_extra_field_is_rejected() -> None:
    """Extra, unexpected fields should fail schema validation."""
    payload = _valid_json_response()
    injected = payload[:-1] + ', "unexpected_field": "surprise"}'
    provider = FakeProvider(response=injected)
    service = LLMService(provider=provider)

    with pytest.raises(LLMResponseParsingError):
        service.extract_information("Some complaint text.")


# --------------------------------------------------------------------------
# Empty response
# --------------------------------------------------------------------------


def test_empty_string_response_raises_empty_response_error() -> None:
    """An empty string response should raise LLMEmptyResponseError."""
    provider = FakeProvider(response="")
    service = LLMService(provider=provider)

    with pytest.raises(LLMEmptyResponseError):
        service.extract_information("Some complaint text.")


def test_whitespace_only_response_raises_empty_response_error() -> None:
    """A whitespace-only response should raise LLMEmptyResponseError."""
    provider = FakeProvider(response="   \n  ")
    service = LLMService(provider=provider)

    with pytest.raises(LLMEmptyResponseError):
        service.extract_information("Some complaint text.")


# --------------------------------------------------------------------------
# Timeout / provider exceptions
# --------------------------------------------------------------------------


def test_provider_timeout_error_propagates() -> None:
    """LLMTimeoutError raised by the provider should propagate unchanged."""
    provider = FakeProvider(error=LLMTimeoutError("fake", 5.0))
    service = LLMService(provider=provider, timeout_seconds=5.0)

    with pytest.raises(LLMTimeoutError):
        service.extract_information("Some complaint text.")


def test_provider_generic_exception_is_wrapped_as_provider_error() -> None:
    """An unexpected provider exception should be wrapped, not leaked."""
    provider = FakeProvider(error=RuntimeError("connection reset"))
    service = LLMService(provider=provider)

    with pytest.raises(LLMProviderError) as exc_info:
        service.extract_information("Some complaint text.")

    assert "connection reset" in str(exc_info.value)


def test_provider_error_from_provider_propagates_unchanged() -> None:
    """LLMProviderError raised directly by the provider should not be
    double-wrapped."""
    provider = FakeProvider(error=LLMProviderError("fake", "boom"))
    service = LLMService(provider=provider)

    with pytest.raises(LLMProviderError) as exc_info:
        service.extract_information("Some complaint text.")

    assert exc_info.value.provider_name == "fake"


# --------------------------------------------------------------------------
# Missing fields
# --------------------------------------------------------------------------


def test_missing_fields_default_to_none() -> None:
    """Fields absent from the JSON response should default to None."""
    provider = FakeProvider(response='{"product_name": "Product X"}')
    service = LLMService(provider=provider)

    result = service.extract_information("Some complaint text.")

    assert result.product_name == "Product X"
    assert result.batch_number is None
    assert result.complaint_type is None
    assert result.severity is None
    assert result.description is None
    assert result.reported_event is None
    assert result.confidence is None


def test_explicit_null_values_are_preserved_as_none() -> None:
    """Explicit JSON null values should map to None, never be guessed."""
    provider = FakeProvider(
        response=_valid_json_response(batch_number=None, severity=None)
    )
    service = LLMService(provider=provider)

    result = service.extract_information("Some complaint text.")

    assert result.batch_number is None
    assert result.severity is None


# --------------------------------------------------------------------------
# Confidence parsing
# --------------------------------------------------------------------------


def test_valid_confidence_is_parsed_as_float() -> None:
    """A valid confidence value should parse as a float in range."""
    provider = FakeProvider(response=_valid_json_response(confidence=0.42))
    service = LLMService(provider=provider)

    result = service.extract_information("Some complaint text.")

    assert result.confidence == 0.42


def test_confidence_above_one_raises_response_parsing_error() -> None:
    """A confidence above 1.0 should fail schema validation."""
    provider = FakeProvider(response=_valid_json_response(confidence=1.5))
    service = LLMService(provider=provider)

    with pytest.raises(LLMResponseParsingError):
        service.extract_information("Some complaint text.")


def test_confidence_below_zero_raises_response_parsing_error() -> None:
    """A negative confidence should fail schema validation."""
    provider = FakeProvider(response=_valid_json_response(confidence=-0.1))
    service = LLMService(provider=provider)

    with pytest.raises(LLMResponseParsingError):
        service.extract_information("Some complaint text.")


def test_non_numeric_confidence_raises_response_parsing_error() -> None:
    """A non-numeric confidence value should fail schema validation."""
    provider = FakeProvider(response=_valid_json_response(confidence="very high"))
    service = LLMService(provider=provider)

    with pytest.raises(LLMResponseParsingError):
        service.extract_information("Some complaint text.")


def test_null_confidence_is_accepted() -> None:
    """An explicit null confidence should be accepted as None."""
    provider = FakeProvider(response=_valid_json_response(confidence=None))
    service = LLMService(provider=provider)

    result = service.extract_information("Some complaint text.")

    assert result.confidence is None


# --------------------------------------------------------------------------
# parse_response / generate as standalone methods
# --------------------------------------------------------------------------


def test_parse_response_can_be_called_directly() -> None:
    """parse_response should be usable independently of extract_information."""
    provider = FakeProvider()
    service = LLMService(provider=provider)

    result = service.parse_response(_valid_json_response())

    assert result.product_name == "Product X"


def test_generate_can_be_called_directly() -> None:
    """generate should be usable independently of extract_information."""
    provider = FakeProvider(response="raw provider output")
    service = LLMService(provider=provider)

    raw = service.generate("a prompt")

    assert raw == "raw provider output"


# --------------------------------------------------------------------------
# Prompt template loading
# --------------------------------------------------------------------------


def test_missing_prompt_template_raises_configuration_error(tmp_path: Path) -> None:
    """A missing prompt template file should raise LLMConfigurationError."""
    provider = FakeProvider(response=_valid_json_response())
    missing_path = tmp_path / "does_not_exist.txt"
    service = LLMService(provider=provider, prompt_path=missing_path)

    with pytest.raises(LLMConfigurationError):
        service.extract_information("Some complaint text.")


def test_prompt_template_is_cached_after_first_load(tmp_path: Path) -> None:
    """The prompt template should be read from disk only once."""
    prompt_path = tmp_path / "extractor.txt"
    prompt_path.write_text("PROMPT: {{complaint_text}}", encoding="utf-8")
    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider, prompt_path=prompt_path)

    service.extract_information("first complaint")
    prompt_path.write_text("CHANGED: {{complaint_text}}", encoding="utf-8")
    service.extract_information("second complaint")

    assert provider.received_prompts[0] == "PROMPT: first complaint"
    assert provider.received_prompts[1] == "PROMPT: second complaint"


def test_default_prompt_path_resolves_to_bundled_extractor_file() -> None:
    """LLMService with no prompt_path override should use the bundled file."""
    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider)

    service.extract_information("Some complaint text.")

    assert service._prompt_path.name == "extractor.txt"
    assert service._prompt_path.is_file()


# --------------------------------------------------------------------------
# Default timeout resolution
# --------------------------------------------------------------------------


def test_default_timeout_comes_from_settings_when_not_provided() -> None:
    """Omitting timeout_seconds should fall back to application settings."""
    from app.config.settings import get_settings

    provider = FakeProvider(response=_valid_json_response())
    service = LLMService(provider=provider)

    assert service.timeout_seconds == get_settings().llm_timeout_seconds


# --------------------------------------------------------------------------
# GroqProvider: configuration
# --------------------------------------------------------------------------


def test_groq_provider_raises_configuration_error_without_api_key() -> None:
    """GroqProvider should refuse to construct without an API key."""
    with pytest.raises(LLMConfigurationError):
        GroqProvider(api_key=None)


def test_groq_provider_constructs_with_explicit_api_key(
    fake_groq_module: types.ModuleType,
) -> None:
    """GroqProvider should construct successfully given an explicit key."""
    provider = GroqProvider(api_key="test-key", model="test-model")

    assert provider.model == "test-model"


# --------------------------------------------------------------------------
# GroqProvider: generate() success, timeout, and provider errors
# --------------------------------------------------------------------------


def test_groq_provider_generate_returns_message_content(
    fake_groq_module: types.ModuleType,
) -> None:
    """A successful Groq completion should return its message content."""
    provider = GroqProvider(api_key="test-key")
    provider._client.chat = types.SimpleNamespace(
        completions=types.SimpleNamespace(
            create=lambda **kwargs: _fake_chat_response("{}")
        )
    )

    result = provider.generate("a prompt", timeout=5.0)

    assert result == "{}"


def test_groq_provider_generate_returns_empty_string_for_no_choices(
    fake_groq_module: types.ModuleType,
) -> None:
    """A response with no choices should yield an empty string."""
    provider = GroqProvider(api_key="test-key")
    empty_response = types.SimpleNamespace(choices=[])
    provider._client.chat = types.SimpleNamespace(
        completions=types.SimpleNamespace(create=lambda **kwargs: empty_response)
    )

    result = provider.generate("a prompt", timeout=5.0)

    assert result == ""


def test_groq_provider_generate_raises_timeout_error(
    fake_groq_module: types.ModuleType,
) -> None:
    """A groq.APITimeoutError should be translated to LLMTimeoutError."""
    provider = GroqProvider(api_key="test-key")

    def _raise_timeout(**kwargs: object) -> None:
        raise fake_groq_module.APITimeoutError("timed out")

    provider._client.chat = types.SimpleNamespace(
        completions=types.SimpleNamespace(create=_raise_timeout)
    )

    with pytest.raises(LLMTimeoutError):
        provider.generate("a prompt", timeout=1.0)


def test_groq_provider_generate_raises_provider_error_for_other_failures(
    fake_groq_module: types.ModuleType,
) -> None:
    """A non-timeout SDK exception should be translated to LLMProviderError."""
    provider = GroqProvider(api_key="test-key")

    def _raise_generic(**kwargs: object) -> None:
        raise RuntimeError("service unavailable")

    provider._client.chat = types.SimpleNamespace(
        completions=types.SimpleNamespace(create=_raise_generic)
    )

    with pytest.raises(LLMProviderError):
        provider.generate("a prompt", timeout=1.0)


# --------------------------------------------------------------------------
# End-to-end: LLMService using GroqProvider (fully mocked SDK)
# --------------------------------------------------------------------------


def test_llm_service_end_to_end_with_groq_provider(
    fake_groq_module: types.ModuleType,
) -> None:
    """LLMService should work end-to-end with GroqProvider's SDK mocked out."""
    provider = GroqProvider(api_key="test-key")
    provider._client.chat = types.SimpleNamespace(
        completions=types.SimpleNamespace(
            create=lambda **kwargs: _fake_chat_response(_valid_json_response())
        )
    )
    service = LLMService(provider=provider)

    result = service.extract_information(
        "The patient experienced vomiting after taking Product X."
    )

    assert result.product_name == "Product X"
    assert result.confidence == 0.87
