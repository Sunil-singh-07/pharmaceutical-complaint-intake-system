"""Response schemas for the Complaints API (Phase 9).

These models compose the existing ``ComplaintState`` sub-models directly
rather than redefining their fields, so the API layer never becomes a
second source of truth for complaint data (see 02_ARCHITECTURE.md
section 4, "ComplaintState is the single source of truth"). The
top-level envelopes follow the standard success/error response format
defined in 05_API_SPECIFICATION.md section 3.
"""

from pydantic import BaseModel, Field

from app.models.ai import AI
from app.models.complaint import Complaint
from app.models.risk import Risk
from app.models.session import Session
from app.models.validation import Validation


class ComplaintStateData(BaseModel):
    """Complaint session data returned to API clients.

    Attributes:
        session: Session metadata.
        complaint: Structured complaint fields.
        ai: AI-generated outputs (summary, missing fields, confidence).
        validation: Deterministic validation results.
        risk: Deterministic risk assessment results.
    """

    session: Session
    complaint: Complaint
    ai: AI
    validation: Validation
    risk: Risk


class ComplaintResponse(BaseModel):
    """Standard success envelope wrapping full complaint session data.

    Attributes:
        success: Always ``True`` for this envelope.
        message: Human-readable description of the operation performed.
        data: The complaint session data.
    """

    success: bool = True
    message: str
    data: ComplaintStateData


class RiskData(BaseModel):
    """Risk-only payload returned by the risk endpoint.

    Attributes:
        risk: Deterministic risk assessment results.
    """

    risk: Risk


class RiskResponse(BaseModel):
    """Standard success envelope wrapping risk assessment data.

    Attributes:
        success: Always ``True`` for this envelope.
        message: Human-readable description of the operation performed.
        data: The risk assessment data.
    """

    success: bool = True
    message: str
    data: RiskData


class ValidationData(BaseModel):
    """Validation-only payload returned by the validation endpoint.

    Attributes:
        validation: Deterministic validation results.
    """

    validation: Validation


class ValidationResponse(BaseModel):
    """Standard success envelope wrapping validation results.

    Attributes:
        success: Always ``True`` for this envelope.
        message: Human-readable description of the operation performed.
        data: The validation data.
    """

    success: bool = True
    message: str
    data: ValidationData


class ErrorResponse(BaseModel):
    """Standard error envelope, per 05_API_SPECIFICATION.md section 3.

    Attributes:
        success: Always ``False`` for this envelope.
        message: Human-readable summary of the failure.
        errors: Additional structured or textual error details.
    """

    success: bool = False
    message: str
    errors: list[str] = Field(default_factory=list)
