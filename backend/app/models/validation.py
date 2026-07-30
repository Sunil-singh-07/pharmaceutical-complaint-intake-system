"""Validation sub-model of ComplaintState.

Populated exclusively by the deterministic Validator service
(``app.services.validator.Validator``). The LLM must never write to this
model, per 04_CODING_CONTRACT.md section 11.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ValidationError(BaseModel):
    """A single structured validation failure.

    Attributes:
        field: Name of the Complaint field the error relates to.
        message: Human-readable description of the failure.
    """

    field: str
    message: str


class Validation(BaseModel):
    """Result of deterministic complaint validation.

    Attributes:
        is_valid: Whether the complaint currently satisfies all validation
            rules and can be saved.
        errors: Structured validation failures found in the complaint.
        warnings: Non-blocking validation warnings.
        missing_fields: Names of mandatory fields that are still missing.
        validation_timestamp: When validation was last performed.
    """

    is_valid: bool = False
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    validation_timestamp: datetime | None = None
