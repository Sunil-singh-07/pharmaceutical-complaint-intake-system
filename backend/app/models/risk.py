"""Risk sub-model of ComplaintState.

Populated exclusively by the deterministic Risk Engine service
(``app.services.risk_engine.RiskEngine``), driven by configuration in
``risk_rules.json``. The LLM must never write to this model.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Risk(BaseModel):
    """Result of deterministic risk assessment.

    Priority, score, and recommended actions originate from
    ``risk_rules.json`` rather than being hardcoded, per
    02_ARCHITECTURE.md section 7 ("Knowledge is configuration, not
    hardcoded logic").

    Attributes:
        priority: Risk priority level, as defined by the knowledge base.
        score: Numeric risk score associated with ``priority``.
        risk_factors: Risk factor signals identified for the complaint.
        reasons: Human-readable explanations for the assigned priority.
        recommended_actions: Recommended next actions for QA personnel.
        assessment_timestamp: When risk was last assessed.
    """

    priority: str | None = None
    score: int | None = None
    risk_factors: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    assessment_timestamp: datetime | None = None
