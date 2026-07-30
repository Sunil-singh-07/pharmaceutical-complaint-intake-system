"""Tests for the ComplaintState model and its sub-models."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models.ai import AI
from app.models.complaint import Complaint
from app.models.complaint_state import ComplaintState
from app.models.conversation import ConversationMessage
from app.models.enums import ConversationRole, IntentType, SessionStatus


def test_complaint_state_default_construction() -> None:
    """ComplaintState should be constructible with no arguments."""
    state = ComplaintState()

    assert state.session.session_id
    assert state.session.status == SessionStatus.ACTIVE
    assert state.complaint == Complaint()
    assert state.ai.missing_fields == []
    assert state.validation.is_valid is False
    assert state.risk.risk_factors == []
    assert state.conversation.history == []
    assert state.changes.modified_fields == []
    assert state.control.is_complete is False


def test_complaint_fields_default_to_none() -> None:
    """Unset Complaint fields must remain None, never guessed."""
    complaint = Complaint()

    assert complaint.company_name is None
    assert complaint.product_name is None
    assert complaint.batch_number is None
    assert complaint.manufacturing_date is None
    assert complaint.expiry_date is None
    assert complaint.complaint_description is None
    assert complaint.complaint_category is None
    assert complaint.complaint_type is None
    assert complaint.quantity is None


def test_complaint_state_accepts_populated_complaint() -> None:
    """ComplaintState should accept a fully populated Complaint."""
    complaint = Complaint(
        company_name="Acme Pharma",
        product_name="Painex 500mg",
        batch_number="B12345",
        manufacturing_date=date(2025, 1, 1),
        expiry_date=date(2027, 1, 1),
        complaint_description="Tablet arrived broken.",
        complaint_category="Physical Defect",
        complaint_type="Broken Tablet",
        quantity="1 box",
    )
    state = ComplaintState(complaint=complaint)

    assert state.complaint.product_name == "Painex 500mg"
    assert state.complaint.complaint_type == "Broken Tablet"


def test_conversation_history_appends_messages() -> None:
    """Conversation history should store ordered ConversationMessage items."""
    state = ComplaintState()
    state.conversation.history.append(
        ConversationMessage(role=ConversationRole.USER, content="Hello")
    )
    state.conversation.last_message = "Hello"
    state.conversation.last_intent = IntentType.NEW_COMPLAINT

    assert len(state.conversation.history) == 1
    assert state.conversation.history[0].role == ConversationRole.USER
    assert state.conversation.last_intent == IntentType.NEW_COMPLAINT


def test_ai_confidence_bounds_are_enforced() -> None:
    """AI.confidence must reject values outside the 0.0-1.0 range."""
    AI(confidence=0.0)
    AI(confidence=1.0)

    with pytest.raises(ValidationError):
        AI(confidence=1.5)


def test_complaint_state_round_trip_serialization() -> None:
    """ComplaintState should serialize to a dict and back without loss."""
    state = ComplaintState(complaint=Complaint(product_name="Painex"))

    dumped = state.model_dump(mode="json")
    restored = ComplaintState.model_validate(dumped)

    assert restored.complaint.product_name == "Painex"
    assert restored.session.session_id == state.session.session_id
