"""Shared enumerations used across ComplaintState sub-models."""

from enum import Enum


class SessionStatus(str, Enum):
    """Lifecycle status of a complaint intake session."""

    ACTIVE = "active"
    SAVED = "saved"
    EXPIRED = "expired"


class ConversationRole(str, Enum):
    """Author of a single conversation turn."""

    USER = "user"
    ASSISTANT = "assistant"


class IntentType(str, Enum):
    """User intent classifications routed by the LangGraph Intent Router.

    Mirrors the branches defined in the LangGraph workflow described in
    02_ARCHITECTURE.md, section 5.
    """

    NEW_COMPLAINT = "new_complaint"
    FIELD_UPDATE = "field_update"
    UPLOAD_PDF = "upload_pdf"
    ASK_QUESTION = "ask_question"
    SAVE_REQUEST = "save_request"
