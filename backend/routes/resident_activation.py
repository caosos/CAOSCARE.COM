"""Resident-scoped activation coalescing for the Level 1 resident-assistance
event model (2026-09-06 directive).

Generalizes what routes/rf_activation.py used to do for RF pendants only:
"does this RESIDENT already have an open, unresolved event, or does this
press need to open a fresh one." Any mapped help-source (RF pendant, kiosk
button, a future wearable) calls record_resident_activation() so two
different devices firing for the same resident while an event is open
attach to the SAME alert_id, never spawn a second one - the directive's
explicit correction: the event is resident-scoped, not resident+device
scoped. routes/pendants.py (a separate, older, frequency-keyed pendant
scaffold - see PROJECT_STATE.md 2026-08-29 entry) is deliberately NOT
wired through this; that system was already flagged as legacy/untouched
before this work started.

Key behavior change from the old rf_activation.py: the "is there an open
event" lookup no longer requires activation_consumed_at to already be
None. It only requires resident_id match + status in (active,
acknowledged) - i.e. "not yet resolved by staff." activation_consumed_at
is reset to None on every coalesced press regardless of its prior value,
which is what lets a repeat press reactivate Aria on an event that
already had (and ended) one session - routes/kiosks.py's active-emergency
poll was also fixed (5-minute created_at cutoff removed) to match, since
a real event can legitimately stay open far longer than 5 minutes.
"""
import logging
import os
from typing import Optional

from deps import db
from models import Alert, PressRecord, now_utc

log = logging.getLogger(__name__)


async def record_resident_activation(
    resident_id: Optional[str],
    room: Optional[str],
    source: str,
    device_id: Optional[str] = None,
    rssi: Optional[float] = None,
    severity: str = "assist",
    auto_voice: bool = True,
    message: Optional[str] = None,
    triggered_by: str = "manual",
    source_metadata: Optional[dict] = None,
    kiosk_id: Optional[str] = None,
) -> dict:
    """Attach this press to the resident's open event, or open a new one.
    Returns the resulting alert dict (already persisted) plus a
    `coalesced` bool the caller can use to decide what response to send."""
    press = PressRecord(device_id=device_id, source=source, rssi=rssi)
    press_dict = press.model_dump()
    press_dict["at"] = press_dict["at"].isoformat()

    # Primary key is resident_id (the directive's own scoping rule). A
    # device not yet assigned to a resident (resident_id is None) falls
    # back to room-scoped coalescing instead of never coalescing at all -
    # otherwise an unassigned pendant would spam a fresh alert per press.
    if resident_id or room:
        open_alert = await db.alerts.find_one(
            {
                "status": {"$in": ["active", "acknowledged"]},
                **({"resident_id": resident_id} if resident_id else {"room": room, "resident_id": None}),
            },
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if open_alert:
            await db.alerts.update_one(
                {"alert_id": open_alert["alert_id"]},
                {
                    "$inc": {"press_count": 1},
                    "$push": {"presses": press_dict},
                    "$set": {"activation_consumed_at": None},
                },
            )
            doc = await db.alerts.find_one({"alert_id": open_alert["alert_id"]}, {"_id": 0})
            return {**doc, "coalesced": True}

    # No open event for this resident - open a fresh one.
    resident_name = None
    if resident_id:
        r = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
        if r:
            resident_name = r.get("name")
            room = room or r.get("room")

    footnote = await _pattern_footnote(resident_id) if resident_id else None

    alert = Alert(
        kiosk_id=kiosk_id,
        resident_id=resident_id,
        resident_name=resident_name,
        room=room,
        severity=severity,
        message=message or "Help requested",
        triggered_by=triggered_by,
        auto_voice=auto_voice,
        press_count=1,
        pattern_footnote=footnote,
        source_metadata=source_metadata,
    )
    doc = alert.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["acknowledged_at"] = None
    doc["resolved_at"] = None
    doc["presses"] = [press_dict]

    # Receipt is created here (not at close) so its `created_at` reflects
    # the real open time; it's marked "completed" when the event closes
    # (routes/alerts.py resolve()/close_alert()). It POINTS at the alert
    # rather than duplicating presses[]/event_log[] - those stay the one
    # source of truth on the Alert document itself.
    try:
        from routes.receipts import create_receipt
        receipt = await create_receipt(
            action_type="resident_assistance_event",
            related_object_type="alert",
            related_object_id=doc["alert_id"],
            source="system",
            resident_id=resident_id,
            room=room,
        )
        doc["receipt_id"] = receipt["receipt_id"]
    except Exception as e:
        log.warning(f"receipt creation failed for alert {doc['alert_id']}: {e}")

    await db.alerts.insert_one(doc)
    doc.pop("_id", None)
    return {**doc, "coalesced": False}


async def _pattern_footnote(resident_id: str) -> Optional[str]:
    from routes.resident_patterns import footnote_for_resident_now
    try:
        return await footnote_for_resident_now(resident_id)
    except Exception as e:
        log.warning(f"pattern footnote lookup failed for {resident_id}: {e}")
        return None


async def try_call_on_call_phone(room: Optional[str], resident_name: Optional[str]) -> None:
    """Best-effort Twilio VOICE call - same no-op-without-credentials shape
    as routes/escalation.py::_try_sms. Real ringing plugs in here once
    Twilio credentials exist; until then this only logs what it would do."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_phone = os.environ.get("TWILIO_FROM_PHONE")
    facility = await db.facilities.find_one({}, {"_id": 0, "on_call_phone": 1})
    to_phone = facility.get("on_call_phone") if facility else None
    who = resident_name or "A resident"
    if not (sid and token and from_phone and to_phone):
        log.info(f"[live-line] would call {to_phone}: {who} in room {room} wants someone now (Twilio not configured)")
        return
    try:
        from twilio.rest import Client  # type: ignore
        client = Client(sid, token)
        twiml = f"<Response><Say>{who} in room {room} is asking for help now. Please check the CAOS Care dashboard.</Say></Response>"
        client.calls.create(to=to_phone, from_=from_phone, twiml=twiml)
    except Exception as e:
        log.warning(f"twilio call failed: {e}")
