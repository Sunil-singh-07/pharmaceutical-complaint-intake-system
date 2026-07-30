"""End-to-end tests for the compiled LangGraph workflow (Phase 8).

These tests build and invoke the real, compiled ``StateGraph`` produced by
``app.graph.workflow``, so they require the ``langgraph`` package listed
in ``requirements.txt``. If it is not installed in the current
environment, the whole module is skipped rather than failed; run
``pip install -r requirements.txt`` to enable these tests.

No test in this module calls a real LLM. ``FakeProvider`` is a test
double, matching the pattern used in ``tests/test_llm_service.py``.
"""

import json

import pytest

pytest.importorskip("langgraph", reason="langgraph is not installed in this environment.")

from app.graph.workflow import build_complaint_workflow, run_complaint_workflow  # noqa: E402
from app.models.complaint_state import ComplaintState  # noqa: E402
from app.services.exceptions import LLMEmptyResponseError  # noqa: E402
from app.services.llm_service import LLMProvider, LLMService  # noqa: E402
from app.services.risk_engine import RiskEngine  # noqa: E402
from app.services.validator import Validator  # noqa: E402

# --------------------------------------------------------------------------
# Fakes / helpers
# --------------------------------------------------------------------------


class FakeProvider(LLMProvider):
    """LLMProvider test double that never performs real network calls.

    Attributes:
        response: The raw text to return from ``generate``.
    """

    def __init__(self, response: str) -> None:
        """Initialize the fake provider.

        Args:
            response: The raw text to return from ``generate``.
        """
        self.response = response

    def generate(self, prompt: str, *, timeout: float) -> str:
        """Return the configured response, ignoring the prompt.

        Args:
            prompt: The prompt passed by the caller (ignored).
            timeout: The timeout passed by the caller (ignored).

        Returns:
            The configured ``response``.
        """
        return self.response


def _extraction_json(**overrides: object) -> str:
    """Build a valid JSON extraction response as a string.

    Args:
        **overrides: Field overrides applied on top of a full baseline.

    Returns:
        A JSON string representing an extraction result.
    """
    base: dict[str, object] = {
        "product_name": "Painex 500mg",
        "batch_number": "B12345",
        "complaint_type": "Broken Tablet",
        "severity": "Medium",
        "description": "Tablet arrived broken in blister pack.",
        "reported_event": None,
        "confidence": 0.9,
    }
    base.update(overrides)
    return json.dumps(base)


def _llm_service(response_json: str) -> LLMService:
    """Build an ``LLMService`` wired to a ``FakeProvider``.

    Args:
        response_json: The raw JSON string the fake provider should
            return.

    Returns:
        An ``LLMService`` instance that performs no real network calls.
    """
    return LLMService(provider=FakeProvider(response_json))


# --------------------------------------------------------------------------
# build_complaint_workflow
# --------------------------------------------------------------------------


def test_build_complaint_workflow_compiles() -> None:
    """The workflow should compile into an invokable graph."""
    workflow = build_complaint_workflow(
        llm_service=_llm_service(_extraction_json()),
        validator=Validator(),
        risk_engine=RiskEngine(),
    )

    assert hasattr(workflow, "invoke")


# --------------------------------------------------------------------------
# run_complaint_workflow: full pipeline
# --------------------------------------------------------------------------


def test_run_complaint_workflow_runs_full_pipeline_for_valid_complaint() -> None:
    """A well-formed complaint should flow through extraction to risk."""
    state = ComplaintState()

    result = run_complaint_workflow(
        "The tablet arrived broken in its blister pack, batch B12345.",
        state,
        llm_service=_llm_service(_extraction_json()),
    )

    # LLM Service -> extraction was applied.
    assert result.complaint.product_name == "Painex 500mg"
    assert result.complaint.batch_number == "B12345"
    assert result.complaint.complaint_type == "Broken Tablet"
    assert result.complaint.complaint_description == "Tablet arrived broken in blister pack."

    # Conversation was updated with the raw input.
    assert result.conversation.last_message == (
        "The tablet arrived broken in its blister pack, batch B12345."
    )

    # Validation Engine ran and reports complaint_category as still missing,
    # since ExtractedComplaintData has no field the LLM Service could have
    # populated it from.
    assert result.validation.validation_timestamp is not None
    assert "complaint_category" in result.validation.missing_fields
    assert result.validation.is_valid is False

    # Risk Engine ran regardless of validation outcome.
    assert result.risk.assessment_timestamp is not None
    assert result.risk.priority is not None

    # Control state reflects a completed workflow run.
    assert result.control.is_complete is True
    assert result.control.current_node == "risk_assessment"


def test_run_complaint_workflow_assigns_critical_priority_for_contamination() -> None:
    """A foreign-particle complaint should be assessed as Critical risk."""
    state = ComplaintState()

    result = run_complaint_workflow(
        "Customer found a foreign particle in the syrup bottle, batch B98765.",
        state,
        llm_service=_llm_service(
            _extraction_json(
                product_name="CoughEase Syrup",
                batch_number="B98765",
                complaint_type="Foreign Particle",
                description="Foreign particle found in syrup bottle.",
            )
        ),
    )

    assert result.risk.priority == "Critical"
    assert "patient_safety" in result.risk.risk_factors


def test_run_complaint_workflow_preserves_previously_confirmed_fields() -> None:
    """Re-running the workflow must not erase already-confirmed fields."""
    state = ComplaintState()
    state.complaint.product_name = "Painex 500mg"
    state.complaint.batch_number = "B12345"

    result = run_complaint_workflow(
        "Follow-up: same batch, additional detail about the defect.",
        state,
        llm_service=_llm_service(
            _extraction_json(product_name=None, batch_number=None)
        ),
    )

    assert result.complaint.product_name == "Painex 500mg"
    assert result.complaint.batch_number == "B12345"


def test_run_complaint_workflow_raises_value_error_for_blank_text() -> None:
    """Blank complaint text should raise ValueError, not silently proceed."""
    state = ComplaintState()

    with pytest.raises(ValueError):
        run_complaint_workflow(
            "   ",
            state,
            llm_service=_llm_service(_extraction_json()),
        )


def test_run_complaint_workflow_propagates_llm_service_errors() -> None:
    """LLM Service failures should propagate out of the workflow."""
    state = ComplaintState()

    with pytest.raises(LLMEmptyResponseError):
        run_complaint_workflow(
            "The tablet arrived broken.",
            state,
            llm_service=_llm_service(""),
        )
