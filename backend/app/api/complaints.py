"""Complaints API routes.

Thin REST layer over the existing Session Store and LangGraph workflow.
Per 04_CODING_CONTRACT.md section 5 and 02_ARCHITECTURE.md section 3,
routes in this module only:

- validate request models (via Pydantic schemas)
- invoke the existing Session Store and LangGraph workflow
- shape typed responses
- let service-layer exceptions propagate for translation into HTTP
  responses by the exception handlers registered in ``app.main``

No extraction, validation, or risk-calculation logic is implemented
here; it all remains inside the existing services.

``POST /api/complaints`` is a single, conversational endpoint: every
call is one turn over one persistent ``ComplaintState``, per
02_ARCHITECTURE.md section 4 ("ComplaintState is the single source of
truth") and 03_AI_DESIGN.md section 5. There is no separate create vs.
edit/correction/update endpoint. Whether a turn starts a new session or
continues an existing one is decided entirely by
``ComplaintCreateRequest.session_id``:

- ``session_id`` omitted or ``null`` -> a new session is created.
- ``session_id`` provided -> the existing session is loaded, the
  workflow runs once against its current ``ComplaintState``, and the
  result is written back to the same session. If no session exists for
  that identifier, ``SessionNotFoundError`` propagates (never silently
  starting a new session instead).

The LangGraph workflow (``app.graph.workflow``) depends on the optional
``langgraph`` package. To keep this module importable in environments
where that package is not installed, the workflow is only imported
lazily, inside ``get_workflow_runner``, and never at module load time.
"""

import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated


from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status,HTTPException
from app.repositories.complaint_repository import (
    ComplaintRepository,
    get_complaint_repository,
)
from app.models.complaint_state import ComplaintState
from app.schemas.complaint_request import ComplaintCreateRequest
from app.schemas.complaint_response import (
    ComplaintResponse,
    ComplaintStateData,
    RiskData,
    RiskResponse,
    ValidationData,
    ValidationResponse,
)
from app.services.llm_service import GroqProvider, LLMService
from app.services.pdf_service import extract_text_from_pdf
from app.services.session_store import SessionStore, get_session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])

#: Signature of ``app.graph.workflow.run_complaint_workflow``.
WorkflowRunner = Callable[..., ComplaintState]


@lru_cache
def get_llm_service() -> LLMService:
    """Return the process-wide singleton LLM Service instance.

    Wraps the default Groq-backed provider. Cached with ``lru_cache`` to
    mirror the pattern used by ``get_settings`` and
    ``get_session_store``. Routes depend on this indirectly via FastAPI
    dependency injection, so tests can override it with a fake service
    and never call a real LLM.

    Returns:
        A shared ``LLMService`` instance.

    Raises:
        LLMConfigurationError: If no Groq API key is configured. Only
            raised when this dependency is actually resolved, i.e. when
            a request reaches a route that needs it without the
            dependency being overridden.
    """
    return LLMService(provider=GroqProvider())


def get_workflow_runner() -> WorkflowRunner:
    """Return the callable used to run the LangGraph complaint workflow.

    The import is performed lazily, inside this function, so that
    ``app.api.complaints`` (and therefore ``app.main``) can be imported
    even in environments where the optional ``langgraph`` package is not
    installed. The import only executes when this dependency is
    actually resolved; tests override it with a fake runner and never
    trigger the import.

    Returns:
        ``app.graph.workflow.run_complaint_workflow``.
    """
    from app.graph.workflow import run_complaint_workflow

    return run_complaint_workflow


SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
WorkflowRunnerDep = Annotated[WorkflowRunner, Depends(get_workflow_runner)]


def _to_state_data(complaint_state: ComplaintState) -> ComplaintStateData:
    """Build the API response payload from a ``ComplaintState``.

    Args:
        complaint_state: The complaint session state to expose.

    Returns:
        A ``ComplaintStateData`` composed of the session's sub-models.
    """
    return ComplaintStateData(
        session=complaint_state.session,
        complaint=complaint_state.complaint,
        ai=complaint_state.ai,
        validation=complaint_state.validation,
        risk=complaint_state.risk,
    )


@router.post(
    "",
    response_model=ComplaintResponse,
    summary="Submit a complaint conversation turn",
)
def submit_complaint_message(
    response: Response,
    session_store: SessionStoreDep,
    llm_service: LLMServiceDep,
    run_workflow: WorkflowRunnerDep,
    message: Annotated[str, Form(description="Raw complaint text to process.")],
    session_id: Annotated[
        str | None,
        Form(description="Identifier of an existing complaint session to continue."),
    ] = None,
    pdf: Annotated[
        UploadFile | None,
        File(description="Optional supporting PDF document for this turn."),
    ] = None,
) -> ComplaintResponse:
    """Process one turn of a complaint intake conversation.

    Every call is a single turn over one persistent ``ComplaintState``,
    per 02_ARCHITECTURE.md section 4 and 03_AI_DESIGN.md section 5:

    1. Load ``ComplaintState`` — create it if ``session_id`` is
       ``None``, otherwise load the existing session.
    2. If a PDF was uploaded, extract its text and append it to
       ``message`` (see below); otherwise use ``message`` unchanged.
    3. Invoke the LangGraph workflow exactly once against that state.
    4. Store the updated ``ComplaintState`` back in the Session Store.
    5. Return the updated state.

    There is no separate edit, correction, or update endpoint: a
    follow-up message (a correction, an answer to a missing-field
    question, additional detail) is submitted the same way, by passing
    the same ``session_id`` again. The conversation continues, turn by
    turn, until the session is explicitly saved (a later phase);
    nothing in this handler ends or restarts a session on its own.

    When a PDF is uploaded, its extracted text is concatenated onto the
    end of ``message`` as ``message + "\\n\\n" + extracted_pdf_text``
    and the combined text is sent into the existing LangGraph workflow
    exactly as any other message would be; no separate PDF workflow is
    used. When no PDF is uploaded, behavior is unchanged from before
    this feature was added.

    Args:
        response: The outgoing response, used to set the status code to
            201 when a new session was created, or 200 when an existing
            session was continued.
        session_store: Session persistence service.
        llm_service: Extraction service used by the workflow.
        run_workflow: Callable that executes the LangGraph workflow.
        message: Raw complaint text for this turn.
        session_id: Identifier of an existing complaint session to
            continue. Omit to start a new session.
        pdf: Optional PDF file whose extracted text is appended to
            ``message`` before it is sent into the workflow.

    Returns:
        The resulting complaint session, including extraction,
        validation, and risk results.

    Raises:
        SessionNotFoundError: If ``session_id`` is provided but no
            session exists for it. A new session is never silently
            created in this case.
        ValueError: If the combined message is blank after stripping.
        LLMServiceError: If the LLM Service fails to extract structured
            data.
        PDFInvalidFileTypeError: If ``pdf`` is uploaded but is not a
            valid PDF file.
        PDFCorruptedError: If ``pdf`` is uploaded but cannot be opened
            or read.
        PDFEmptyError: If ``pdf`` is uploaded but contains no
            extractable text.
    """
    request = ComplaintCreateRequest(message=message, session_id=session_id)

    complaint_text = request.message
    if pdf is not None:
        pdf_bytes = pdf.file.read()
        extracted_pdf_text = extract_text_from_pdf(pdf_bytes, pdf.filename)
        complaint_text = f"{complaint_text}\n\n{extracted_pdf_text}"

    session_id = request.session_id.strip() if request.session_id else None

    if not session_id:
        state = session_store.create_session()
        response.status_code = status.HTTP_201_CREATED
        result_message = "Complaint session created."
        logger.info("Created session '%s' for new complaint.", state.session.session_id)
    else:
        state = session_store.get_session(session_id)
        response.status_code = status.HTTP_200_OK
        result_message = "Complaint session updated."
        logger.info("Continuing session '%s'.", state.session.session_id)

    updated_state = run_workflow(complaint_text, state, llm_service=llm_service)
    session_store.update_session(updated_state.session.session_id, updated_state)
#     repository.save_workflow_result(
#         session_id=updated_state.session.session_id,
#         complaint_text=complaint_text,
#         complaint_data=updated_state.complaint.model_dump(mode="json"),
#         ai_data=updated_state.ai.model_dump(mode="json"),
#         validation_data=updated_state.validation.model_dump(mode="json"),
#         risk_data=updated_state.risk.model_dump(mode="json"),
#         workflow_status="completed",
#   )

    return ComplaintResponse(message=result_message, data=_to_state_data(updated_state))


@router.get(
    "/{session_id}",
    response_model=ComplaintResponse,
    summary="Get complaint session",
)
def get_complaint(session_id: str, session_store: SessionStoreDep) -> ComplaintResponse:
    """Retrieve the current state of a complaint session.

    Args:
        session_id: Identifier of the session to retrieve.
        session_store: Session persistence service.

    Returns:
        The current complaint session state.

    Raises:
        SessionNotFoundError: If no session exists for ``session_id``.
    """
    state = session_store.get_session(session_id)
    return ComplaintResponse(message="Session retrieved.", data=_to_state_data(state))


@router.get(
    "/{session_id}/risk",
    response_model=RiskResponse,
    summary="Get complaint risk assessment",
)
def get_complaint_risk(session_id: str, session_store: SessionStoreDep) -> RiskResponse:
    """Retrieve the current risk assessment for a complaint session.

    Args:
        session_id: Identifier of the session to retrieve.
        session_store: Session persistence service.

    Returns:
        The current deterministic risk assessment.

    Raises:
        SessionNotFoundError: If no session exists for ``session_id``.
    """
    state = session_store.get_session(session_id)
    return RiskResponse(message="Risk assessment retrieved.", data=RiskData(risk=state.risk))


@router.get(
    "/{session_id}/validation",
    response_model=ValidationResponse,
    summary="Get complaint validation results",
)
def get_complaint_validation(
    session_id: str, session_store: SessionStoreDep
) -> ValidationResponse:
    """Retrieve the current validation results for a complaint session.

    Args:
        session_id: Identifier of the session to retrieve.
        session_store: Session persistence service.

    Returns:
        The current deterministic validation results.

    Raises:
        SessionNotFoundError: If no session exists for ``session_id``.
    """
    state = session_store.get_session(session_id)
    return ValidationResponse(
        message="Validation results retrieved.",
        data=ValidationData(validation=state.validation),
    )
