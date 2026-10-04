"""Room announcement - CAOSCare asking one room's voice endpoint to speak.

A workflow object like StaffTask: the document holds the current state and
its history; every state change also writes one chained receipt through the
existing receipt service (routes/receipts.py). Kept out of models.py
(already oversized). Contract: docs/ROOM_ANNOUNCEMENT_CONTRACT.md.
"""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from models import now_utc, uid

AnnouncementState = Literal[
    "requested", "authorized", "rejected", "queued", "sent_to_provider",
    "playback_started", "playback_finished", "failed", "receipt_recorded"]
# How the request ended. "unconfirmed": the provider accepted it but gave no
# playback evidence - never reported as played.
AnnouncementOutcome = Literal["rejected", "played", "unconfirmed", "failed", "unverified_timeout"]
# Strongest evidence the provider returned (docs/ROOM_ANNOUNCEMENT_CONTRACT.md).
EvidenceLevel = Literal["none", "provider_accepted", "provider_reported_started",
                        "provider_reported_finished"]
OriginType = Literal["task", "alert", "staff_direct", "system_workflow"]
Purpose = Literal["request_update", "transport_update", "facility_notice", "staff_message", "reminder"]
Priority = Literal["routine", "important", "emergency"]


class RoomAnnouncementRequest(BaseModel):
    """What a caller asks for. Actor and authority are never taken from here."""
    model_config = ConfigDict(extra="forbid")
    community_id: str
    room: str
    message: str = Field(min_length=1, max_length=300)
    purpose: Purpose
    priority: Priority = "routine"
    origin_type: OriginType
    origin_id: Optional[str] = None          # task_id / alert_id; required unless staff_direct
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    scheduled_for: Optional[datetime] = None


class RoomAnnouncement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    announcement_id: str = Field(default_factory=lambda: uid("ann"))
    community_id: str
    room: str
    resident_id: Optional[str] = None
    kiosk_id: Optional[str] = None
    target_device_id: Optional[str] = None
    message: str
    purpose: str
    priority: str
    origin_type: str
    origin_id: Optional[str] = None
    idempotency_key: str
    scheduled_for: Optional[datetime] = None
    actor_id: str
    actor_type: str
    authority: Optional[str] = None
    authorization: dict = Field(default_factory=dict)
    state: AnnouncementState = "requested"
    outcome: Optional[AnnouncementOutcome] = None
    evidence_level: EvidenceLevel = "none"
    provider: Optional[str] = None
    provider_request: Optional[dict] = None
    provider_response: Optional[dict] = None
    failure_reason: Optional[str] = None
    next_action: Optional[str] = None
    correlation_id: Optional[str] = None     # origin receipt id
    last_receipt_id: Optional[str] = None
    final_receipt_id: Optional[str] = None
    history: List[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
