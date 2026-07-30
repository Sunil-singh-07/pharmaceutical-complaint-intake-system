"""Graph-local state schema used to orchestrate the complaint workflow.

``GraphState`` wraps :class:`~app.models.complaint_state.ComplaintState`
with additional fields needed only during a single graph execution: the
raw input text for the current turn, and the transient LLM extraction
result passed from the extraction node to the mapping node.

These extra fields are never part of the persisted ``ComplaintState`` and
are not written to the session store. Per 02_ARCHITECTURE.md section 4
and 04_CODING_CONTRACT.md section 2, ``ComplaintState`` itself is not
modified by this development phase; this module only adds a graph-scoped
wrapper around it.
"""

from pydantic import BaseModel

from app.models.complaint_state import ComplaintState
from app.models.extraction import ExtractedComplaintData


class GraphState(BaseModel):
    """LangGraph state schema for the complaint intake workflow.

    Attributes:
        complaint_state: The persisted complaint session state. Every
            graph node reads from and writes back to this object, per
            03_AI_DESIGN.md section 6.
        input_text: Raw complaint text supplied for the current workflow
            run. Transient: not persisted as part of ``ComplaintState``.
        extracted: Structured extraction result produced by the LLM
            Service node and consumed by the mapping node. Transient: not
            persisted as part of ``ComplaintState``.
    """

    complaint_state: ComplaintState
    input_text: str | None = None
    extracted: ExtractedComplaintData | None = None
