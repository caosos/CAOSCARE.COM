"""Agent Control Plane data shapes. Local to this package on purpose: no
shared model (backend/models.py) is changed by this lane."""
import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

COMMAND_STATUSES = ("queued", "delivered", "acknowledged", "completed", "failed", "cancelled")
MAX_INSTRUCTION = 4000
# Control characters other than newline and tab.
_BAD_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")


class CommandInput(BaseModel):
    """What the owner's browser may send. Anything else in the body is
    ignored (extra="ignore"): issued_by, status and the delivery target are
    always decided server-side."""
    model_config = ConfigDict(extra="ignore")
    client_command_id: str = Field(min_length=8, max_length=64)
    target_agent_id: str = Field(min_length=1, max_length=64)
    instruction: str
    parent_command_id: Optional[str] = None
    based_on_integration_sha: Optional[str] = None

    @field_validator("instruction")
    @classmethod
    def _instruction(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("instruction is empty")
        if len(v) > MAX_INSTRUCTION:
            raise ValueError(f"instruction longer than {MAX_INSTRUCTION} characters")
        if _BAD_CHARS.search(v):
            raise ValueError("instruction contains control characters")
        return v

    @field_validator("based_on_integration_sha")
    @classmethod
    def _sha(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _SHA.match(v):
            raise ValueError("based_on_integration_sha must be 7-40 lowercase hex characters")
        return v


class AgentSeed(BaseModel):
    agent_id: str
    display_name: str
    role: str
    binding_id: Optional[str] = None     # key into registry.BINDINGS, server-side only


class StatusEntry(BaseModel):
    at: str
    from_status: Optional[str] = None
    to_status: str
    by: str
    receipt_id: str
    note: Optional[str] = None


class Delivery(BaseModel):
    ok: bool
    evidence: str                     # what the adapter can actually show
    simulated: bool = False


class AgentReply(BaseModel):
    status: str                       # "acknowledged" | "completed" | "failed"
    message: str
    simulated: bool = False


class AgentStatus(BaseModel):
    state: str                        # online / working / waiting / blocked / offline / unknown
    adapter: Optional[str] = None
    simulated: bool = False
    detail: Optional[str] = None
    events: List[dict] = Field(default_factory=list)
