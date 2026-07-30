"""Changes sub-model of ComplaintState.

Tracks which Complaint fields have been modified since the last save, so
downstream nodes can process only what changed instead of the entire
complaint, per 02_ARCHITECTURE.md section 4.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Changes(BaseModel):
    """Tracks fields modified since the last save.

    Attributes:
        modified_fields: Names of Complaint fields changed since the last
            save.
        last_modified_at: Timestamp of the most recent modification.
    """

    modified_fields: list[str] = Field(default_factory=list)
    last_modified_at: datetime | None = None
