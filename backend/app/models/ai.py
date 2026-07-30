"""AI sub-model of ComplaintState.

Holds only outputs produced by the LLM: summary, missing fields, and
extraction confidence. Per 03_AI_DESIGN.md section 7, the LLM must never
write to Validation or Risk.
"""

from pydantic import BaseModel, Field


class AI(BaseModel):
    """AI-generated outputs for the current complaint.

    Attributes:
        summary: Natural language summary of the complaint.
        missing_fields: Field names the AI identified as not yet provided.
        confidence: Overall extraction confidence, between 0.0 and 1.0.
    """

    summary: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
