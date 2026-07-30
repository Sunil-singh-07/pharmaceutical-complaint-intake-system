"""ComplaintState: the single source of truth for a complaint session.

Every LangGraph node reads from and writes back to this model, per
02_ARCHITECTURE.md section 4 and 03_AI_DESIGN.md section 6. This module
only aggregates the sub-models; it must not contain business logic.
"""

from pydantic import BaseModel, Field

from app.models.ai import AI
from app.models.changes import Changes
from app.models.complaint import Complaint
from app.models.control import Control
from app.models.conversation import Conversation
from app.models.risk import Risk
from app.models.session import Session
from app.models.validation import Validation


class ComplaintState(BaseModel):
    """Aggregate state shared by every node in the complaint workflow.

    Attributes:
        session: Session metadata.
        complaint: Structured complaint data.
        ai: AI-generated outputs.
        validation: Deterministic validation results.
        risk: Deterministic risk assessment results.
        conversation: Conversation history and routing context.
        changes: Fields modified since the last save.
        control: LangGraph execution control state.
    """

    session: Session = Field(default_factory=Session)
    complaint: Complaint = Field(default_factory=Complaint)
    ai: AI = Field(default_factory=AI)
    validation: Validation = Field(default_factory=Validation)
    risk: Risk = Field(default_factory=Risk)
    conversation: Conversation = Field(default_factory=Conversation)
    changes: Changes = Field(default_factory=Changes)
    control: Control = Field(default_factory=Control)
