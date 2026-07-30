"""Tests for the individual LangGraph node functions (Phase 8).

These tests exercise each node function directly, without building or
compiling a LangGraph ``StateGraph``, so they run regardless of whether
the ``langgraph`` package is installed. No test in this module calls a
real LLM; ``FakeProvider`` is a test double, matching the pattern used in
``tests/test_llm_service.py``.
"""

import json

import pytest

from app.graph.nodes import (
    make_llm_extraction_node,
    make_risk_assessment_node,
    make_validation_node,
    map_extraction_node,
)
from app.graph.state import GraphState
from app.models.complaint import Complaint
from app.models.complaint_state import ComplaintState
from app.models.extraction import ExtractedComplaintData
from app.services.exceptions import LLMEmptyResponseError
from app.services.llm_service import LLMProvider, LLMService
from app.services.risk_engine import RiskEngine
from app.services.validator import Validator

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


def _graph_state(input_text: str = "The tablet arrived broken.") -> GraphState:
    """Build a fresh ``GraphState`` wrapping a new ``ComplaintState``.

    Args:
        input_text: The raw complaint text for this workflow run.

    Returns:
        A ``GraphState`` instance.
    """
    return GraphState(complaint_state=ComplaintState(), input_text=input_text)


# --------------------------------------------------------------------------
# llm_extraction_node
# --------------------------------------------------------------------------


def test_llm_extraction_node_stores_extracted_result_and_updates_control() -> None:
    """The node should populate 'extracted' and update conversation/control."""
    llm_service = _llm_service(_extraction_json())
    node = make_llm_extraction_node(llm_service)
    state = _graph_state("The tablet arrived broken.")

    update = node(state)

    assert update["extracted"] is not None
    assert isinstance(update["extracted"], ExtractedComplaintData)
    assert update["extracted"].product_name == "Painex 500mg"

    updated_complaint_state: ComplaintState = update["complaint_state"]
    assert updated_complaint_state.conversation.last_message == "The tablet arrived broken."
    assert updated_complaint_state.control.current_node == "llm_extraction"
    assert updated_complaint_state.control.next_node == "map_extraction"
    assert updated_complaint_state.control.error is None


def test_llm_extraction_node_raises_value_error_for_blank_text() -> None:
    """Blank input text should raise ValueError, per LLMService's contract."""
    llm_service = _llm_service(_extraction_json())
    node = make_llm_extraction_node(llm_service)
    state = _graph_state("   ")

    with pytest.raises(ValueError):
        node(state)


def test_llm_extraction_node_propagates_llm_service_errors() -> None:
    """LLM Service failures should propagate rather than being swallowed."""
    llm_service = _llm_service("")  # empty response triggers LLMEmptyResponseError
    node = make_llm_extraction_node(llm_service)
    state = _graph_state("The tablet arrived broken.")

    with pytest.raises(LLMEmptyResponseError):
        node(state)


# --------------------------------------------------------------------------
# map_extraction_node
# --------------------------------------------------------------------------


def test_map_extraction_node_copies_non_null_fields_into_complaint() -> None:
    """Every non-null extracted field should be copied onto Complaint."""
    extracted = ExtractedComplaintData(
        product_name="Painex 500mg",
        batch_number="B12345",
        complaint_type="Broken Tablet",
        severity="Medium",
        description="Tablet arrived broken.",
        confidence=0.9,
    )
    state = GraphState(complaint_state=ComplaintState(), extracted=extracted)

    update = map_extraction_node(state)
    complaint_state: ComplaintState = update["complaint_state"]

    assert complaint_state.complaint.product_name == "Painex 500mg"
    assert complaint_state.complaint.batch_number == "B12345"
    assert complaint_state.complaint.complaint_type == "Broken Tablet"
    assert complaint_state.complaint.severity == "Medium"
    assert complaint_state.complaint.complaint_description == "Tablet arrived broken."
    assert complaint_state.ai.confidence == 0.9
    assert complaint_state.control.current_node == "map_extraction"
    assert complaint_state.control.next_node == "validation"
    assert set(complaint_state.changes.modified_fields) == {
        "product_name",
        "batch_number",
        "complaint_type",
        "severity",
        "complaint_description",
    }
    assert complaint_state.changes.last_modified_at is not None


def test_map_extraction_node_never_overwrites_known_value_with_null() -> None:
    """Fields the LLM could not extract must not erase existing data."""
    existing_complaint = Complaint(product_name="Painex 500mg", batch_number="B12345")
    complaint_state = ComplaintState(complaint=existing_complaint)
    extracted = ExtractedComplaintData(product_name=None, batch_number=None)
    state = GraphState(complaint_state=complaint_state, extracted=extracted)

    update = map_extraction_node(state)
    updated_complaint_state: ComplaintState = update["complaint_state"]

    assert updated_complaint_state.complaint.product_name == "Painex 500mg"
    assert updated_complaint_state.complaint.batch_number == "B12345"
    assert updated_complaint_state.changes.modified_fields == []


def test_map_extraction_node_reports_ai_missing_fields() -> None:
    """AI.missing_fields should list Complaint fields the LLM left null."""
    extracted = ExtractedComplaintData(product_name="Painex 500mg")
    state = GraphState(complaint_state=ComplaintState(), extracted=extracted)

    update = map_extraction_node(state)
    complaint_state: ComplaintState = update["complaint_state"]

    assert "batch_number" in complaint_state.ai.missing_fields
    assert "complaint_type" in complaint_state.ai.missing_fields
    assert "complaint_description" in complaint_state.ai.missing_fields
    assert "product_name" not in complaint_state.ai.missing_fields


def test_map_extraction_node_handles_missing_extraction_result() -> None:
    """The node should no-op gracefully when there is nothing to map."""
    state = GraphState(complaint_state=ComplaintState(), extracted=None)

    update = map_extraction_node(state)
    complaint_state: ComplaintState = update["complaint_state"]

    assert complaint_state.complaint == Complaint()
    assert complaint_state.control.current_node == "map_extraction"


# --------------------------------------------------------------------------
# validation_node
# --------------------------------------------------------------------------


def test_validation_node_delegates_to_validator_and_updates_control() -> None:
    """The node should store the Validator's result and update control."""
    complaint = Complaint(
        product_name="Painex 500mg",
        complaint_description="Tablet arrived broken.",
        complaint_category="Physical Defect",
        complaint_type="Broken Tablet",
    )
    complaint_state = ComplaintState(complaint=complaint)
    state = GraphState(complaint_state=complaint_state)

    node = make_validation_node(Validator())
    update = node(state)
    updated_complaint_state: ComplaintState = update["complaint_state"]

    assert updated_complaint_state.validation.is_valid is True
    assert updated_complaint_state.control.current_node == "validation"
    assert updated_complaint_state.control.next_node == "risk_assessment"


def test_validation_node_reports_missing_required_fields() -> None:
    """An incomplete complaint should surface missing required fields."""
    state = GraphState(complaint_state=ComplaintState())

    node = make_validation_node(Validator())
    update = node(state)
    updated_complaint_state: ComplaintState = update["complaint_state"]

    assert updated_complaint_state.validation.is_valid is False
    assert "product_name" in updated_complaint_state.validation.missing_fields


# --------------------------------------------------------------------------
# risk_assessment_node
# --------------------------------------------------------------------------


def test_risk_assessment_node_delegates_to_risk_engine_and_completes_workflow() -> None:
    """The node should store the RiskEngine's result and mark completion."""
    complaint = Complaint(
        complaint_category="Contamination",
        complaint_type="Foreign Particle",
    )
    complaint_state = ComplaintState(complaint=complaint)
    state = GraphState(complaint_state=complaint_state)

    node = make_risk_assessment_node(RiskEngine())
    update = node(state)
    updated_complaint_state: ComplaintState = update["complaint_state"]

    assert updated_complaint_state.risk.priority == "Critical"
    assert updated_complaint_state.control.current_node == "risk_assessment"
    assert updated_complaint_state.control.next_node is None
    assert updated_complaint_state.control.is_complete is True
