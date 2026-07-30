"""Request schemas for the Complaints API.

These models define the shape of incoming HTTP request bodies only. The
actual extraction, validation, and risk assessment logic remains fully
delegated to the existing LangGraph workflow and its underlying
services, per 04_CODING_CONTRACT.md section 5.
"""

from pydantic import BaseModel, Field


class ComplaintCreateRequest(BaseModel):
    """Request body for a single complaint conversation turn.

    The same request model is used both to start a new complaint
    session and to continue an existing one: every user message is
    simply another conversation turn over one persistent
    ``ComplaintState``. Which behavior occurs is decided entirely by
    whether ``session_id`` is provided, not by any separate "edit" or
    "correction" mode.

    Attributes:
        message: Raw complaint text used by the LangGraph workflow to
            extract structured complaint information for this turn.
            Blank or whitespace-only text is rejected by the workflow
            itself (see ``app.graph.workflow.run_complaint_workflow``),
            not re-validated here, to avoid duplicating that check.
        session_id: Identifier of an existing complaint session to
            continue. When omitted (or ``null``), a new session is
            created. When provided, the referenced session's
            ``ComplaintState`` is loaded and updated in place; if no
            session exists for this identifier, the request fails with
            a 404 rather than silently starting a new session.
    """

    message: str = Field(
        ...,
        min_length=1,
        description="Raw complaint text to process (e.g. an email body or note).",
    )
    session_id: str | None = Field(
        default=None,
        description=(
            "Identifier of an existing complaint session to continue. "
            "Omit to start a new session."
        ),
    )
