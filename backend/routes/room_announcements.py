"""Room-targeted announcements (Voice PE slice 1).

One authorized actor asks one room's voice endpoint to speak. The request is
a RoomAnnouncement document (models_announcements.py) whose every state
change writes one receipt through routes/receipts.create_receipt, chained to
the announcement's origin receipt. The provider is reached only through
announcement_providers.py. Playback is never reported from acceptance
alone. Contract: docs/ROOM_ANNOUNCEMENT_CONTRACT.md.
"""
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError

from announcement_providers import get_provider
from deps import db, get_current_user, require_front_desk_or_admin
from models import uid
from models_announcements import RoomAnnouncement, RoomAnnouncementRequest
from routes.actor_context import ActorContext, actor_from_user
from routes.receipts import create_receipt
from routes.room_announcement_policy import Refusal, authorize, origin_object, resolve_room
from routes.task_lifecycle import result_label_for as _actor_label

router = APIRouter(prefix="/room-announcements", tags=["room-announcements"])
PROVIDER_TIMEOUT_S = float(os.environ.get("CAOSCARE_ANNOUNCE_TIMEOUT_S", "30"))
_RECEIPT_STATUS = {"requested": "created", "rejected": "failed", "failed": "failed",
                   "playback_finished": "completed"}
ANONYMOUS = ActorContext(actor_id="anonymous", actor_type="external-provider",
                         identity_basis="unauthenticated", channel="http")


async def ensure_indexes():
    await db.room_announcements.create_index("idempotency_key", unique=True)
    await db.room_announcements.create_index("announcement_id", unique=True)


def idempotency_key(req: RoomAnnouncementRequest, actor: ActorContext) -> str:
    """Caller's key, or one derived from what would make a replay identical.
    A staff-direct announcement has no origin object, so the same words to
    the same room by the same person within 10 minutes count as a retry."""
    if req.idempotency_key:
        return f"caller:{actor.actor_id}:{req.idempotency_key}"
    bucket = int(datetime.now(timezone.utc).timestamp() // 600) if req.origin_type == "staff_direct" else 0
    raw = "|".join([req.origin_type, req.origin_id or "", req.community_id, req.room,
                    req.message.strip(), actor.actor_id, str(bucket)])
    return "derived:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


def result_label_for(actor: ActorContext) -> str:
    """How much the actor is known; an unauthenticated caller is unverified."""
    return "unverified" if actor.identity_basis == "unauthenticated" else _actor_label(actor)


def _source(actor: ActorContext) -> str:
    if actor.identity_basis == "system":
        return "system"
    return "front_desk" if actor.role == "front_desk" else "staff"


async def _step(ann: dict, state: str, actor: ActorContext, *, label: str, next_state: str,
                status: Optional[str] = None, failure: Optional[str] = None,
                evidence: Optional[dict] = None, provider_refs: Optional[list] = None,
                set_fields: Optional[dict] = None) -> dict:
    """Move the announcement to `state` and write its chained receipt."""
    # The origin receipt id is fixed when the document is created, so a
    # concurrent duplicate can always link to it.
    rid = ann["correlation_id"] if state == "requested" else uid("rcpt")
    correlation = ann["correlation_id"]
    before = {"state": ann["state"]}
    receipt = await create_receipt(
        action_type=f"room_announcement_{state}", related_object_type="room_announcement",
        related_object_id=ann["announcement_id"], source=_source(actor),
        resident_id=ann.get("resident_id"), room=ann["room"],
        status=status or _RECEIPT_STATUS.get(state, "in_progress"), failure_reason=failure,
        result=ann["message"][:300] if state == "playback_finished" else None, receipt_id=rid,
        provenance={**actor.receipt_fields(), "authority": ann.get("authority"),
                    "parent_receipt_id": ann.get("last_receipt_id"), "correlation_id": correlation,
                    "before_state": before, "after_state": {"state": state},
                    "result_label": label, "provider_refs": provider_refs or [],
                    "next_state": next_state,
                    "evidence": {"community_id": ann["community_id"], "kiosk_id": ann.get("kiosk_id"),
                                 "target_device_id": ann.get("target_device_id"),
                                 "origin": {"type": ann["origin_type"], "id": ann.get("origin_id")},
                                 "purpose": ann["purpose"], "priority": ann["priority"],
                                 "idempotency_key": ann["idempotency_key"], **(evidence or {})}})
    fields = {"state": state, "last_receipt_id": rid, "correlation_id": correlation,
              "next_action": next_state, **(set_fields or {})}
    if failure:
        fields["failure_reason"] = failure
    entry = {"state": state, "at": receipt["created_at"], "receipt_id": rid}
    await db.room_announcements.update_one(
        {"announcement_id": ann["announcement_id"]}, {"$set": fields, "$push": {"history": entry}})
    ann.update(fields)
    ann["history"].append(entry)
    return receipt


async def _finish(ann: dict, actor: ActorContext, outcome: str, final_rid: str) -> dict:
    """RECEIPT_RECORDED: the outcome receipt exists; nothing further runs."""
    now = datetime.now(timezone.utc).isoformat()
    fields = {"state": "receipt_recorded", "outcome": outcome, "final_receipt_id": final_rid}
    entry = {"state": "receipt_recorded", "at": now, "receipt_id": final_rid}
    await db.room_announcements.update_one(
        {"announcement_id": ann["announcement_id"]}, {"$set": fields, "$push": {"history": entry}})
    ann.update(fields)
    ann["history"].append(entry)
    return ann


async def announce(req: RoomAnnouncementRequest, *, actor: ActorContext, user: Optional[dict] = None,
                   provider=None) -> dict:
    """The one way CAOSCare makes a room speak. Returns the announcement
    (with `duplicate: True` when an identical request already exists)."""
    provider = provider or get_provider()
    ann = RoomAnnouncement(
        community_id=req.community_id, room=req.room, message=req.message.strip(),
        purpose=req.purpose, priority=req.priority, origin_type=req.origin_type,
        origin_id=req.origin_id, idempotency_key=idempotency_key(req, actor),
        scheduled_for=req.scheduled_for, actor_id=actor.actor_id, actor_type=actor.actor_type,
        provider=provider.name, correlation_id=uid("rcpt")).model_dump()
    try:
        await db.room_announcements.insert_one(dict(ann))
    except DuplicateKeyError:
        return await _duplicate(ann["idempotency_key"], actor)
    origin = await _step(ann, "requested", actor, label=result_label_for(actor), next_state="authorize")
    try:
        room = await resolve_room(req.community_id, req.room)
        ann.update(room)
        await db.room_announcements.update_one({"announcement_id": ann["announcement_id"]}, {"$set": room})
        obj = await origin_object(req.origin_type, req.origin_id, req.room)
        decision = authorize(actor, user, req, obj)
    except Refusal as r:
        rec = await _step(ann, "rejected", actor, label="failed", next_state="none",
                          failure=r.reason, evidence={"refusal_detail": r.detail},
                          set_fields={"authorization": {"allowed": False, "reason": r.reason}})
        return await _finish(ann, actor, "rejected", rec["receipt_id"])
    auth = {"allowed": True, **decision, "quiet_hours_policy": "none_defined",
            "emergency_policy": "none_defined"}
    ann["authority"] = decision["authority"]
    await _step(ann, "authorized", actor, label=result_label_for(actor), next_state="queue",
                set_fields={"authority": decision["authority"], "authorization": auth})
    await _step(ann, "queued", actor, label=result_label_for(actor), next_state="send")
    req_desc = {"provider": provider.name, "target_device_id": ann["target_device_id"]}
    await _step(ann, "sent_to_provider", actor, label=result_label_for(actor),
                next_state="await_provider", evidence={"provider_request": req_desc},
                set_fields={"provider_request": req_desc})
    result = await provider.announce(ann["target_device_id"], ann["message"],
                                     preannounce=True, timeout_s=PROVIDER_TIMEOUT_S)
    return await _record_provider_result(ann, actor, provider, result)


async def _record_provider_result(ann: dict, actor: ActorContext, provider, result) -> dict:
    label_ok = "simulated" if provider.simulated else "verified"
    ev = {"provider_request": result.request, "provider_response": result.response,
          "evidence_level": result.evidence_level,
          "limitation": "provider-reported; not an acoustic confirmation that anyone heard it"}
    fields = {"provider_request": result.request, "provider_response": result.response,
              "evidence_level": result.evidence_level}
    if not result.accepted:
        timeout = result.timed_out
        rec = await _step(ann, "failed", actor, label="unverified" if timeout else "failed",
                          next_state="staff_check" if timeout else "none", failure=result.failure,
                          evidence={**ev, "note": "timed out: it may still play; not retried"}
                          if timeout else ev, set_fields=fields)
        return await _finish(ann, actor, "unverified_timeout" if timeout else "failed", rec["receipt_id"])
    if result.started:
        await _step(ann, "playback_started", actor, label=label_ok, next_state="await_finish",
                    evidence=ev, set_fields=fields)
    if result.finished:
        rec = await _step(ann, "playback_finished", actor, label=label_ok, next_state="none",
                          evidence=ev, set_fields=fields)
        return await _finish(ann, actor, "played", rec["receipt_id"])
    # Accepted (or started) without finish evidence: the strongest truthful
    # state stays where the evidence ends; never reported as played.
    state = "playback_started" if result.started else "sent_to_provider"
    rec = await _step(ann, state, actor, label="unverified", status="acknowledged",
                      next_state="staff_check",
                      evidence={**ev, "note": "provider accepted; no playback-finished evidence"},
                      set_fields=fields)
    return await _finish(ann, actor, "unconfirmed", rec["receipt_id"])


async def _duplicate(key: str, actor: ActorContext) -> dict:
    """A repeat of an existing announcement: nothing is sent again; the
    attempt is recorded on the original, outside its lifecycle chain."""
    existing = await db.room_announcements.find_one({"idempotency_key": key}, {"_id": 0})
    await create_receipt(
        action_type="room_announcement_duplicate_ignored", related_object_type="room_announcement",
        related_object_id=existing["announcement_id"], source=_source(actor),
        resident_id=existing.get("resident_id"), room=existing["room"], status="cancelled",
        provenance={**actor.receipt_fields(), "authority": existing.get("authority"),
                    "parent_receipt_id": existing.get("correlation_id"),
                    "correlation_id": existing.get("correlation_id"),
                    "result_label": result_label_for(actor),
                    "next_state": "none",
                    "evidence": {"idempotency_key": key, "existing_state": existing.get("state")}})
    return {**existing, "duplicate": True}


@router.post("")
async def post_announcement(req: RoomAnnouncementRequest, request: Request):
    try:
        user = await get_current_user(request)
    except HTTPException:
        user = None
    actor = actor_from_user(user) if user else ANONYMOUS
    ann = await announce(req, actor=actor, user=user)
    ann.pop("_id", None)
    code = 200
    if ann.get("outcome") == "rejected":
        code = 401 if user is None else 403
    return JSONResponse(status_code=code, content=_jsonable(ann))


@router.get("/{announcement_id}")
async def get_announcement(announcement_id: str, _=Depends(require_front_desk_or_admin)):
    doc = await db.room_announcements.find_one({"announcement_id": announcement_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "announcement not found")
    return _jsonable(doc)


def _jsonable(doc: dict) -> dict:
    return jsonable_encoder({k: v for k, v in doc.items() if k != "_id"})
