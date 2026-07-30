"""Control sub-model of ComplaintState.

Tracks LangGraph execution state. LangGraph itself is wired in a later
development phase; this model only defines the state shape it will read
from and write to.
"""

from pydantic import BaseModel


class Control(BaseModel):
    """Execution control state for the LangGraph workflow.

    Attributes:
        current_node: Name of the graph node most recently executed.
        next_node: Name of the graph node scheduled to run next.
        is_waiting_for_input: Whether the graph is paused at the WAIT step,
            awaiting user input.
        is_complete: Whether the workflow has reached END for this turn.
        error: Description of the last execution error, if any.
    """

    current_node: str | None = None
    next_node: str | None = None
    is_waiting_for_input: bool = False
    is_complete: bool = False
    error: str | None = None
