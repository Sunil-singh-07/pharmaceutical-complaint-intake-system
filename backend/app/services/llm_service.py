"""LLM Service: structured information extraction only.

This service extracts structured complaint fields from raw complaint
text using a deterministic prompt and a pluggable :class:`LLMProvider`.

Per 03_AI_DESIGN.md section 7 and 04_CODING_CONTRACT.md section 11, this
service performs extraction ONLY. It must never:

- validate complaint data
- calculate risk
- orchestrate workflow
- write to the database
- make business decisions
- invent information that is not present in the source text

Provider abstraction:

``LLMProvider`` is an abstract interface. Concrete providers (e.g.
:class:`GroqProvider`) wrap a specific vendor SDK behind this interface,
so callers of :class:`LLMService` never depend on provider-specific
types or exceptions. Swapping providers requires no changes to
``LLMService`` itself.
"""

import json
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import ValidationError

from app.config.settings import get_settings
from app.models.extraction import ExtractedComplaintData
from app.services.exceptions import (
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMProviderError,
    LLMResponseParsingError,
    LLMServiceError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

#: Directory containing prompt template files.
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

#: Filename of the deterministic extraction prompt template.
_EXTRACTOR_PROMPT_FILENAME = "extractor.txt"

#: Placeholder replaced with the raw complaint text inside the template.
_COMPLAINT_TEXT_PLACEHOLDER = "{{complaint_text}}"


class LLMProvider(ABC):
    """Abstract interface for an LLM text-completion provider.

    Concrete implementations wrap a specific vendor SDK so that
    :class:`LLMService` and its callers never depend on provider-specific
    types, clients, or exceptions.
    """

    @abstractmethod
    def generate(self, prompt: str, *, timeout: float) -> str:
        """Generate a raw text completion for the given prompt.

        Args:
            prompt: The fully-rendered prompt to send to the provider.
            timeout: Maximum time, in seconds, to wait for a response.

        Returns:
            The raw text completion returned by the provider. May be an
            empty string if the provider returned no content.

        Raises:
            LLMTimeoutError: If the provider does not respond in time.
            LLMProviderError: If the provider call fails for any other
                reason.
        """
        raise NotImplementedError


class GroqProvider(LLMProvider):
    """LLMProvider implementation backed by the Groq chat completions API.

    The ``groq`` SDK is imported lazily, inside the constructor, so
    importing this module never requires the SDK to be installed unless
    a ``GroqProvider`` is actually constructed.

    Attributes:
        model: Groq model identifier used for completions.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize the Groq provider.

        Args:
            api_key: Groq API key. Defaults to the ``groq_api_key``
                application setting when not provided.
            model: Groq model identifier. Defaults to the ``groq_model``
                application setting when not provided.

        Raises:
            LLMConfigurationError: If no API key is configured, or if the
                ``groq`` package is not installed.
        """
        settings = get_settings()
        resolved_api_key = api_key or settings.groq_api_key
        if not resolved_api_key:
            raise LLMConfigurationError(
                "Groq API key is not configured. Set the GROQ_API_KEY "
                "environment variable."
            )

        try:
            from groq import Groq
        except ImportError as exc:
            raise LLMConfigurationError(
                "The 'groq' package is required to use GroqProvider. "
                "Install it with 'pip install groq'."
            ) from exc

        self._client = Groq(api_key=resolved_api_key)
        self.model: str = model or settings.groq_model

    def generate(self, prompt: str, *, timeout: float) -> str:
        """Generate a raw completion using the Groq chat completions API.

        Args:
            prompt: The fully-rendered prompt to send to Groq.
            timeout: Maximum time, in seconds, to wait for a response.

        Returns:
            The raw text completion returned by Groq, or an empty string
            if Groq returned no content.

        Raises:
            LLMTimeoutError: If Groq does not respond within ``timeout``.
            LLMProviderError: If the Groq API call fails for any other
                reason.
        """
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=timeout,
            )
        except Exception as exc:
            if self._is_timeout(exc):
                raise LLMTimeoutError("groq", timeout) from exc
            raise LLMProviderError("groq", str(exc)) from exc

        choices = getattr(response, "choices", None)
        if not choices:
            return ""
        content = choices[0].message.content
        return content or ""

    @staticmethod
    def _is_timeout(exc: Exception) -> bool:
        """Best-effort detection of timeout errors raised by the Groq SDK.

        Args:
            exc: The exception raised by the Groq SDK call.

        Returns:
            ``True`` if ``exc`` represents a timeout, ``False`` otherwise.
        """
        try:
            import groq
        except ImportError:
            return False
        return isinstance(exc, getattr(groq, "APITimeoutError", ()))


class LLMService:
    """Structured information extraction service backed by an LLM.

    The service never validates data, calculates risk, writes to the
    database, or orchestrates workflow; those responsibilities belong to
    the Validator, RiskEngine, SessionStore, and LangGraph respectively.

    The service is stateless beyond a cached, thread-safe copy of the
    extraction prompt template, so a single instance may be shared and
    called concurrently across threads.

    Attributes:
        provider: The LLM provider used to generate completions.
        timeout_seconds: Maximum time, in seconds, to wait for a provider
            response.
    """

    def __init__(
        self,
        provider: LLMProvider,
        timeout_seconds: float | None = None,
        prompt_path: Path | None = None,
    ) -> None:
        """Initialize the LLM Service.

        Args:
            provider: The LLM provider used to generate completions. The
                caller is responsible for constructing the desired
                provider (e.g. :class:`GroqProvider`), keeping
                provider-specific configuration out of this service.
            timeout_seconds: Maximum time, in seconds, to wait for a
                provider response. Defaults to the ``llm_timeout_seconds``
                application setting when not provided.
            prompt_path: Path to the extraction prompt template. Defaults
                to ``extractor.txt`` bundled in ``app/prompts``.
        """
        self.provider = provider
        self.timeout_seconds: float = (
            timeout_seconds
            if timeout_seconds is not None
            else get_settings().llm_timeout_seconds
        )
        self._prompt_path: Path = prompt_path or (_PROMPTS_DIR / _EXTRACTOR_PROMPT_FILENAME)
        self._prompt_template: str | None = None
        self._prompt_lock = threading.Lock()

    def extract_information(self, complaint_text: str) -> ExtractedComplaintData:
        """Extract structured complaint data from raw complaint text.

        Args:
            complaint_text: Raw, unstructured complaint text (e.g. an
                email body or transcribed note).

        Returns:
            The structured fields the LLM was able to extract. Fields the
            LLM could not determine are ``None``; the LLM is never
            permitted to guess.

        Raises:
            ValueError: If ``complaint_text`` is empty or blank.
            LLMConfigurationError: If the prompt template cannot be
                loaded.
            LLMTimeoutError: If the provider does not respond in time.
            LLMProviderError: If the provider call fails.
            LLMEmptyResponseError: If the provider returns an empty
                response.
            LLMResponseParsingError: If the response is not valid,
                schema-conformant JSON.
        """
        if not complaint_text or not complaint_text.strip():
            raise ValueError("complaint_text must not be empty or blank.")

        prompt = self._build_prompt(complaint_text)
        raw_response = self.generate(prompt)
        return self.parse_response(raw_response)

    def generate(self, prompt: str) -> str:
        """Call the configured provider to generate a raw completion.

        Args:
            prompt: The fully-rendered prompt to send to the provider.

        Returns:
            The raw text completion returned by the provider.

        Raises:
            LLMTimeoutError: If the provider does not respond in time.
            LLMProviderError: If the provider call fails for any other
                reason.
        """
        logger.info(
            "Sending extraction prompt to LLM provider '%s' (prompt_length=%d)",
            type(self.provider).__name__,
            len(prompt),
        )

        try:
            raw_response = self.provider.generate(prompt, timeout=self.timeout_seconds)
        except LLMServiceError:
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error from LLM provider '%s': %s",
                type(self.provider).__name__,
                exc,
            )
            raise LLMProviderError(type(self.provider).__name__, str(exc)) from exc

        logger.info(
            "Received LLM response from provider '%s' (response_length=%d)",
            type(self.provider).__name__,
            len(raw_response or ""),
        )
        return raw_response

    def parse_response(self, raw_response: str) -> ExtractedComplaintData:
        """Parse and validate a raw LLM response into structured data.

        Args:
            raw_response: The raw text returned by the provider, expected
                to be a single JSON object.

        Returns:
            The parsed, schema-validated extraction result.

        Raises:
            LLMEmptyResponseError: If ``raw_response`` is empty or blank.
            LLMResponseParsingError: If ``raw_response`` is not valid
                JSON, is not a JSON object, or fails schema validation.
        """
        if raw_response is None or not raw_response.strip():
            raise LLMEmptyResponseError("LLM provider returned an empty response.")

        cleaned = self._strip_code_fences(raw_response)

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMResponseParsingError(raw_response, f"Invalid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise LLMResponseParsingError(
                raw_response, "Expected a JSON object at the top level."
            )

        try:
            extracted = ExtractedComplaintData.model_validate(payload)
        except ValidationError as exc:
            raise LLMResponseParsingError(raw_response, str(exc)) from exc

        logger.info(
            "Parsed LLM extraction result: confidence=%s", extracted.confidence
        )
        return extracted

    def _build_prompt(self, complaint_text: str) -> str:
        """Render the extraction prompt template for a given complaint.

        Args:
            complaint_text: Raw complaint text to embed in the prompt.

        Returns:
            The fully-rendered prompt string.

        Raises:
            LLMConfigurationError: If the prompt template cannot be
                loaded.
        """
        template = self._load_prompt_template()
        return template.replace(_COMPLAINT_TEXT_PLACEHOLDER, complaint_text.strip())

    def _load_prompt_template(self) -> str:
        """Load and cache the extraction prompt template from disk.

        Returns:
            The raw prompt template text.

        Raises:
            LLMConfigurationError: If the prompt template file is
                missing.
        """
        with self._prompt_lock:
            if self._prompt_template is None:
                if not self._prompt_path.is_file():
                    raise LLMConfigurationError(
                        f"Extraction prompt template not found: {self._prompt_path}"
                    )
                self._prompt_template = self._prompt_path.read_text(encoding="utf-8")
            return self._prompt_template

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Strip Markdown code fences some providers wrap JSON responses in.

        Args:
            text: Raw response text, possibly wrapped in ``` or ```json
                fences.

        Returns:
            The text with any surrounding code fence removed.
        """
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
