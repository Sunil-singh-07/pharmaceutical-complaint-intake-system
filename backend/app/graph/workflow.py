"""LangGraph workflow orchestration for complaint intake (Phase 8).

Wires together the existing LLM Service, a field-mapping step, the
Validation Engine, and the Risk Engine into a single LangGraph workflow,
per 02_ARCHITECTURE.md section 5 and 06_DEVELOPMENT_PLAN.md Phase 8::

    START -> LLM Service -> Map ExtractedComplaintData -> ComplaintState
          -> Validation Engine -> Risk Engine -> END

This module contains no business logic of its own. Extraction,
validation, and risk assessment are delegated entirely to
:class:`~app.services.llm_service.LLMService`,
:class:`~app.services.validator.Validator`, and
:class:`~app.services.risk_engine.RiskEngine` respectively, per
04_CODING_CONTRACT.md section 5 ("LangGraph: Orchestrate workflow only.
Never contain business rules.").
"""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    make_llm_extraction_node,
    make_risk_assessment_node,
    make_validation_node,
    map_extraction_node,
)
from app.graph.state import GraphState
from app.models.complaint_state import ComplaintState
from app.services.llm_service import LLMService
from app.services.risk_engine import RiskEngine
from app.services.validator import Validator

logger = logging.getLogger(__name__)


def build_complaint_workflow(
    llm_service: LLMService,
    validator: Validator,
    risk_engine: RiskEngine,
) -> Any:
    """Build and compile the Phase 8 complaint intake LangGraph workflow.

    Args:
        llm_service: Service used to extract structured complaint data.
        validator: Service used to deterministically validate the
            complaint.
        risk_engine: Service used to deterministically assess complaint
            risk.

    Returns:
        A compiled LangGraph workflow ready to be invoked via
        ``.invoke(GraphState(...))``.
    """
    builder = StateGraph(GraphState)

    builder.add_node("llm_extraction", make_llm_extraction_node(llm_service))
    builder.add_node("map_extraction", map_extraction_node)
    builder.add_node("validation", make_validation_node(validator))
    builder.add_node("risk_assessment", make_risk_assessment_node(risk_engine))

    builder.add_edge(START, "llm_extraction")
    builder.add_edge("llm_extraction", "map_extraction")
    builder.add_edge("map_extraction", "validation")
    builder.add_edge("validation", "risk_assessment")
    builder.add_edge("risk_assessment", END)

    return builder.compile()


def run_complaint_workflow(
    complaint_text: str,
    state: ComplaintState,
    *,
    llm_service: LLMService,
    validator: Validator | None = None,
    risk_engine: RiskEngine | None = None,
) -> ComplaintState:
    """Run the complete complaint intake workflow for a single message.

    Args:
        complaint_text: Raw complaint text to extract information from.
        state: The current ``ComplaintState`` for the session.
        llm_service: Service used to extract structured complaint data.
            The caller is responsible for constructing it (e.g. with a
            ``GroqProvider``), keeping provider configuration out of this
            module.
        validator: Service used to validate the complaint. Defaults to a
            new ``Validator`` instance when not provided.
        risk_engine: Service used to assess complaint risk. Defaults to a
            new ``RiskEngine`` instance when not provided.

    Returns:
        The updated ``ComplaintState`` after extraction, mapping,
        validation, and risk assessment have all run.

    Raises:
        ValueError: If ``complaint_text`` is empty or blank.
        LLMServiceError: If the LLM Service fails to extract structured
            data. See ``app.services.llm_service`` for the specific
            exception types.
    """
    logger.info("Starting complaint workflow for session '%s'.", state.session.session_id)

    workflow = build_complaint_workflow(
        llm_service=llm_service,
        validator=validator or Validator(),
        risk_engine=risk_engine or RiskEngine(),
    )
    initial_state = GraphState(complaint_state=state, input_text=complaint_text)
    result = workflow.invoke(initial_state)
    updated_state: ComplaintState = result["complaint_state"]

    logger.info(
        "Completed complaint workflow for session '%s': is_valid=%s, priority=%s",
        updated_state.session.session_id,
        updated_state.validation.is_valid,
        updated_state.risk.priority,
    )
    return updated_state
