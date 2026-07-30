"""Conversation sub-model of ComplaintState."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import ConversationRole, IntentType


class ConversationMessage(BaseModel):
    """A single turn in the complaint intake conversation.

    Attributes:
        role: Author of the message.
        content: Text content of the message.
        timestamp: Time the message was recorded.
    """

    role: ConversationRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Conversation(BaseModel):
    """Conversation history and routing context for a session.

    Attributes:
        history: Ordered list of conversation turns.
        last_message: Most recent user message, for quick access.
        last_intent: Most recently detected user intent.
    """

    history: list[ConversationMessage] = Field(default_factory=list)
    last_message: str | None = None
    last_intent: IntentType | None = None
