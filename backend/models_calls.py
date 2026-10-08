"""Telephony domain (Pilot 1 calling, Lane F). Kept out of models.py, which
is far over the size guideline - same split as models_transportation.py.

Call state is set ONLY from phone-system events (Asterisk ARI) or the voice
provider's call-control responses - never from what Aria says. See
docs/PILOT1_COMMUNICATIONS.md.
"""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from models import now_utc, uid

# requested -> dialing -> ringing -> connected -> ended
#                     \-> unanswered / failed -> ended
CallState = Literal["requested", "dialing", "ringing", "connected", "unanswered", "failed", "ended"]

# aria            resident handset reached the Aria extension
# front_desk      Aria (or dial 0) connecting the resident to the front desk
# family          approved family contact over the SIP trunk
# emergency       911 dialed - recorded only, never routed through CAOSCare
CallKind = Literal["aria", "front_desk", "family", "emergency"]

PhoneEndpointKind = Literal["room", "front_desk", "aria"]


class PhoneEndpoint(BaseModel):
    """A SIP extension on the local Asterisk and what it means to CAOSCare.
    `room` links a handset extension to the room (and so the resident); the
    same room string the Kiosk/Resident records use."""
    model_config = ConfigDict(extra="ignore")
    endpoint_id: str = Field(default_factory=lambda: uid("phx"))
    extension: str
    kind: PhoneEndpointKind
    room: Optional[str] = None
    label: Optional[str] = ""
    active: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class PhoneEndpointCreate(BaseModel):
    extension: str = Field(pattern=r"^\d{2,6}$")
    kind: PhoneEndpointKind
    room: Optional[str] = None
    label: Optional[str] = ""


class CallStateChange(BaseModel):
    state: CallState
    at: str
    source: str          # "asterisk" | "openai" | "caoscare"
    detail: Optional[str] = None


class CallSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_id: str = Field(default_factory=lambda: uid("call"))
    kind: CallKind
    state: CallState = "requested"
    history: List[CallStateChange] = Field(default_factory=list)
    room: Optional[str] = None
    resident_id: Optional[str] = None
    from_extension: Optional[str] = None
    # Short numeric token Asterisk dials back (REFER target / transfer
    # context); resolved once to a dial target by /telephony/dial-target.
    dial_token: Optional[str] = None
    target_extension: Optional[str] = None
    family_contact_id: Optional[str] = None
    target_label: Optional[str] = None       # "Front desk", "Susan (daughter)" - never a raw number
    parent_call_id: Optional[str] = None     # the Aria call a transfer came from
    openai_call_id: Optional[str] = None
    conversation_session_id: Optional[str] = None
    hangup_cause: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)
    connected_at: Optional[str] = None
    ended_at: Optional[str] = None
