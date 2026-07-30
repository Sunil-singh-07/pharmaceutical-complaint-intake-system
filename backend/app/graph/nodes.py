"""LangGraph node functions for the complaint intake workflow.

Each node is a thin orchestration wrapper around an existing service. Per
04_CODING_CONTRACT.md section 5 ("LangGraph: Orchestrate workflow only.
Never contain business rules.") and section 11 ("The LLM must never
calculate risk, validate required fields, ... invent missing complaint
information"), no node in this module implements validation, risk
calculation, or extraction logic itself:

- ``llm_extraction_node`` delegates entirely to
  :class:`~app.services.llm_service.LLMService`.
- ``map_extraction_node`` performs a direct field-by-field copy from the
  LLM's structured output into :class:`~app.models.complaint.Complaint`.
  Per 03_AI_DESIGN.md section 10, a field is only ever copied when the
  LLM actually extracted a value; unknown fields are left untouched
  rather than overwritten with ``None``, so a value confirmed earlier in
  the session is never silently erased by a later, less complete
  extraction. ``complaint_description`` additionally uses an
  append-based merge (``_merge_description``): a new turn's description
  is folded into the existing narrative rather than replacing it, unless
  it is already covered by the existing text, so a short follow-up
  message adds to the complaint history instead of erasing it.
  ``ai.missing_fields`` is derived from the merged ``Complaint`` (not from the current turn's extraction alone),
  and ``ai.summary`` is composed deterministically from the merged
  ``Complaint`` fields (``_build_summary``) -- no additional LLM call is
  made.
- ``validation_node`` delegates entirely to
  :class:`~app.services.validator.Validator`.
- ``risk_assessment_node`` delegates entirely to
  :class:`~app.services.risk_engine.RiskEngine`.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.graph.state import GraphState
from app.models.ai import AI
from app.models.changes import Changes
from app.services.llm_service import LLMService
from app.services.risk_engine import RiskEngine
from app.services.validator import Validator

logger = logging.getLogger(__name__)

#: A LangGraph node: takes the current ``GraphState`` and returns a partial
#: state update.
NodeFn = Callable[[GraphState], dict[str, Any]]

#: Maps each field on ``ExtractedComplaintData`` to the corresponding
#: field on ``Complaint``. Kept local to the mapping node since it is
#: graph-orchestration wiring, not a reusable business rule.
_EXTRACTION_FIELD_MAP = {
    # Company
    "company_name": "company_name",
    "manufacturer": "manufacturer",

    # Product
    "product_name": "product_name",
    "generic_name": "generic_name",
    "strength": "strength",
    "dosage_form": "dosage_form",
    "pack_size": "pack_size",
    "quantity": "quantity",

    # Batch
    "batch_number": "batch_number",
    "manufacturing_date": "manufacturing_date",
    "expiry_date": "expiry_date",

    # Complaint
    "complaint_category": "complaint_category",
    "complaint_type": "complaint_type",
    "defect_type": "defect_type",
    "severity": "severity",
    "description": "complaint_description",

    # Patient
    "reported_event": "reported_event",
    "symptoms": "symptoms",
}


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time.
    """
    return datetime.now(timezone.utc)


def _merge_description(current: str | None, new: str) -> str:
    """Merge a newly extracted description into the existing one.

    ``complaint_description`` is treated as an evolving narrative rather
    than a single-shot value: later turns should add to it, not silently
    replace it. This is deterministic string comparison and
    concatenation -- no LLM call is involved, and it implements no risk
    or validation logic.

    - If there is no current description yet, the new description
      becomes the description.
    - If the new text is already contained within the current
      description (case-insensitive), the current description is kept
      unchanged -- it already covers what the new text says.
    - Otherwise, the new text is treated as additional complaint detail
      and appended to the current description on a new line, so the
      full history of what was reported is preserved.

    Args:
        current: The existing ``complaint_description``, if any.
        new: The description extracted from the current turn.

    Returns:
        The merged description to store.
    """
    if not current:
        return new

    normalized_current = current.strip().lower()
    normalized_new = new.strip().lower()

    if normalized_new in normalized_current:
        return current

    return f"{current.strip()}\n{new.strip()}"


def _build_summary(complaint: Any) -> str | None:
    """Create a readable complaint summary."""

    if not any([
        complaint.product_name,
        complaint.company_name,
        complaint.batch_number,
        complaint.complaint_description,
    ]):
        return None

    lines = []

    if complaint.product_name:
        product = complaint.product_name

        if getattr(complaint, "strength", None):
            product += f" {complaint.strength}"

        if getattr(complaint, "dosage_form", None):
            product += f" {complaint.dosage_form}"

        lines.append(f"Product: {product}")

    if getattr(complaint, "company_name", None):
        lines.append(f"Company: {complaint.company_name}")

    if complaint.batch_number:
        lines.append(f"Batch: {complaint.batch_number}")

    if getattr(complaint, "expiry_date", None):
        lines.append(f"Expiry: {complaint.expiry_date}")

    if complaint.severity:
        lines.append(f"Severity: {complaint.severity}")

    if getattr(complaint, "defect_type", None):
        lines.append(f"Defect: {complaint.defect_type}")

    if getattr(complaint, "reported_event", None):
        lines.append(f"Reported Event: {complaint.reported_event}")

    if complaint.complaint_description:
        lines.append("")
        lines.append(complaint.complaint_description)

    return "\n".join(lines)


def make_llm_extraction_node(llm_service: LLMService) -> NodeFn:
    """Build the LLM Service graph node.

    Args:
        llm_service: The extraction service to delegate to.

    Returns:
        A node function that extracts structured complaint data from
        ``state.input_text`` and stores the raw result on
        ``state.extracted`` for the mapping node to consume.
    """

    def llm_extraction_node(state: GraphState) -> dict[str, Any]:
        """Extract structured complaint data from the current input text.

        Args:
            state: The current graph state.

        Returns:
            A partial state update containing the refreshed
            ``complaint_state`` (conversation and control updated) and
            the raw ``extracted`` result.

        Raises:
            ValueError: If ``state.input_text`` is empty or blank.
            LLMServiceError: If the LLM Service fails to extract
                structured data. See ``app.services.llm_service`` for the
                specific exception types.
        """
        complaint_text = state.input_text or ""

        logger.info("Running llm_extraction node.")
        extracted = llm_service.extract_information(complaint_text)

        complaint_state = state.complaint_state
        conversation = complaint_state.conversation.model_copy(
            update={"last_message": complaint_text.strip()}
        )
        control = complaint_state.control.model_copy(
            update={
                "current_node": "llm_extraction",
                "next_node": "map_extraction",
                "error": None,
            }
        )
        updated_state = complaint_state.model_copy(
            update={"conversation": conversation, "control": control}
        )

        return {"complaint_state": updated_state, "extracted": extracted}

    return llm_extraction_node


def map_extraction_node(state: GraphState) -> dict[str, Any]:
    """Map the LLM's structured output onto ``Complaint``.

    Only fields the LLM actually extracted (non-``None``) are considered
    for copying. Fields the LLM could not determine are left untouched
    on the existing ``Complaint``, in accordance with the project's
    zero-hallucination policy: unknown values must never overwrite
    previously confirmed data. ``complaint_description`` is merged with
    an additional append rule (see ``_merge_description``): new complaint
    detail from a later turn is appended to the existing description on
    a new line rather than replacing it, unless it is already covered by
    the existing text.

    ``ai.missing_fields`` is derived from the *merged* ``Complaint``
    (i.e. what is still unknown after this turn's update is applied),
    not from which fields happened to be mentioned in this turn's
    extraction alone -- a field confirmed in an earlier turn and not
    repeated now is not "missing". ``ai.summary`` is a deterministic,
    template-based restatement of the merged ``Complaint`` fields (see
    ``_build_summary``); no additional LLM call is made.

    This node performs no validation or risk calculation; it is pure
    orchestration glue between the LLM Service and the downstream
    Validation Engine and Risk Engine.

    Args:
        state: The current graph state, including the ``extracted``
            result produced by ``llm_extraction_node``.

    Returns:
        A partial state update containing the refreshed
        ``complaint_state`` (complaint, ai, changes, and control
        updated).
    """
    complaint_state = state.complaint_state
    control = complaint_state.control.model_copy(
        update={"current_node": "map_extraction", "next_node": "validation"}
    )

    extracted = state.extracted
    complaint = complaint_state.complaint
    changes = complaint_state.changes
    confidence = complaint_state.ai.confidence

    if extracted is None:
        logger.info("Running map_extraction node: no extraction result to map.")
    else:
        logger.info("Running map_extraction node.")

        complaint_updates: dict[str, Any] = {}
        modified_fields: list[str] = []
        for extracted_field, complaint_field in _EXTRACTION_FIELD_MAP.items():
            value = getattr(extracted, extracted_field, None)
            if value is None:
                continue

            current_value = getattr(complaint, complaint_field)
            if complaint_field == "complaint_description":
                merged_value = _merge_description(current_value, value)
                if merged_value != current_value:
                    complaint_updates[complaint_field] = merged_value
                    modified_fields.append(complaint_field)
                continue

            if current_value != value:
                complaint_updates[complaint_field] = value
                modified_fields.append(complaint_field)

        if complaint_updates:
            complaint = complaint.model_copy(update=complaint_updates)

        if modified_fields:
            merged_modified = sorted(set(changes.modified_fields) | set(modified_fields))
            changes = Changes(modified_fields=merged_modified, last_modified_at=_utc_now())

        confidence = extracted.confidence

    missing_fields = [
        complaint_field
        for complaint_field in _EXTRACTION_FIELD_MAP.values()
        if not getattr(complaint, complaint_field)
    ]
    ai = AI(
        summary=_build_summary(complaint),
        missing_fields=missing_fields,
        confidence=confidence,
    )

    updated_state = complaint_state.model_copy(
        update={"complaint": complaint, "ai": ai, "changes": changes, "control": control}
    )
    return {"complaint_state": updated_state}


def make_validation_node(validator: Validator) -> NodeFn:
    """Build the Validation Engine graph node.

    Args:
        validator: The deterministic validation service to delegate to.

    Returns:
        A node function that validates ``state.complaint_state.complaint``
        and stores the result on ``state.complaint_state.validation``.
    """

    def validation_node(state: GraphState) -> dict[str, Any]:
        """Run deterministic validation against the current complaint.

        Args:
            state: The current graph state.

        Returns:
            A partial state update containing the refreshed
            ``complaint_state`` (validation and control updated).
        """
        logger.info("Running validation node.")
        complaint_state = state.complaint_state
        validation = validator.validate(complaint_state.complaint)
        control = complaint_state.control.model_copy(
            update={"current_node": "validation", "next_node": "risk_assessment"}
        )
        updated_state = complaint_state.model_copy(
            update={"validation": validation, "control": control}
        )
        return {"complaint_state": updated_state}

    return validation_node


def make_risk_assessment_node(risk_engine: RiskEngine) -> NodeFn:
    """Build the Risk Engine graph node.

    Args:
        risk_engine: The deterministic risk assessment service to
            delegate to.

    Returns:
        A node function that assesses ``state.complaint_state.complaint``
        and stores the result on ``state.complaint_state.risk``.
    """

    def risk_assessment_node(state: GraphState) -> dict[str, Any]:
        """Run deterministic risk assessment against the current complaint.

        Args:
            state: The current graph state.

        Returns:
            A partial state update containing the refreshed
            ``complaint_state`` (risk and control updated, workflow
            marked complete).
        """
        logger.info("Running risk_assessment node.")
        complaint_state = state.complaint_state
        risk = risk_engine.assess(complaint_state.complaint)
        control = complaint_state.control.model_copy(
            update={
                "current_node": "risk_assessment",
                "next_node": None,
                "is_complete": True,
            }
        )
        updated_state = complaint_state.model_copy(update={"risk": risk, "control": control})
        return {"complaint_state": updated_state}

    return risk_assessment_node
