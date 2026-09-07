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
import uuid
from datetime import datetime
from typing import Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from deps import db
from models import Alert, PressRecord, now_utc
from routes.activation_log import alog

log = logging.getLogger(__name__)

# Only this transmission-semantics class may enter the activation path. The
# real gate is upstream in routes/rf_matched_intake.py (a supervisory /
# tamper / battery / unknown RF frame is never passed here); this is a
# defence-in-depth backstop so no future caller can bypass it silently.
ACTIVATION_SEMANTIC_CLASS = "help_press"


class _RetryActivation(Exception):
    pass


def _scope(resident_id, room):
    return f"resident:{resident_id}" if resident_id else (f"room:{room}" if room else None)


async def record_resident_activation(resident_id, room, source, **kwargs):
    """Serialize competing creators with a Mongo unique open-event key.

    Legacy events acquire the key when selected for a new press; existing
    duplicate history is preserved, never deleted or silently resolved.
    Resolved events remain in the database but no longer reserve the key.
    """
    await db.alerts.create_index(
        "open_event_key", unique=True, name="one_open_resident_event",
        partialFilterExpression={"open_event_key": {"$type": "string"},
                                 "status": {"$in": ["active", "acknowledged"]}},
    )
    for _ in range(20):
        try:
            return await _record_resident_activation(resident_id, room, source, **kwargs)
        except (DuplicateKeyError, _RetryActivation):
            continue
    raise RuntimeError("Resident activation contention; retry required")


async def _record_resident_activation(
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
    press_id: Optional[str] = None,
    semantic_class: str = "help_press",
    activation_id_hint: Optional[str] = None,
) -> dict:
    """Attach this press to the resident's open event, or open a new one.
    Returns the resulting alert dict (already persisted) plus a
    `coalesced` bool the caller can use to decide what response to send.

    `semantic_class` MUST be "help_press" - anything else is refused here
    (the real gate is upstream, this only backstops a bypass)."""
    if semantic_class != ACTIVATION_SEMANTIC_CLASS:
        await alog("resident_event", "activation_refused_non_help",
                   room=room, resident_id=resident_id, kiosk_id=kiosk_id,
                   data={"semantic_class": semantic_class, "source": source})
        log.warning(f"record_resident_activation refused: semantic_class={semantic_class!r}")
        return {"coalesced": False, "refused": True, "semantic_class": semantic_class, "alert_id": None}

    def _age(created_at) -> float:
        try:
            c = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
            return round((now_utc() - c).total_seconds(), 1)
        except Exception:
            return -1.0

    press = PressRecord(device_id=device_id, source=source, rssi=rssi)
    press_dict = press.model_dump()
    press_dict["at"] = press_dict["at"].isoformat()
    if press_id:
        press_dict["press_id"] = press_id
        # Every frame in one RF burst names the same logical press. This
        # also prevents a late duplicate from reopening a resolved event.
        prior = await db.alerts.find_one({"presses.press_id": press_id}, {"_id": 0})
        if prior:
            return {**prior, "coalesced": True, "duplicate_press": True}

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
            pc_before = open_alert.get("press_count", 0)
            consumed_before = open_alert.get("activation_consumed_at")
            age = _age(open_alert.get("created_at"))
            # Repeated presses during a conversation share its activation
            # cycle. Only a new press AFTER consumption starts a new cycle.
            new_cycle = bool(open_alert.get("activation_consumed_at")) or not open_alert.get("activation_id")
            activation_id = (activation_id_hint or uuid.uuid4().hex) if new_cycle else open_alert["activation_id"]
            doc = await db.alerts.find_one_and_update(
                {"alert_id": open_alert["alert_id"],
                 "status": {"$in": ["active", "acknowledged"]},
                 "activation_id": open_alert.get("activation_id"),
                 "activation_consumed_at": open_alert.get("activation_consumed_at"),
                 **({"presses.press_id": {"$ne": press_id}} if press_id else {})},
                {
                    "$inc": {"press_count": 1},
                    "$push": {"presses": press_dict},
                    "$set": {"activation_consumed_at": None,
                             "open_event_key": _scope(resident_id, room),
                             "activation_id": activation_id,
                             "auto_voice": auto_voice or open_alert.get("auto_voice", False),
                             **({"aria_state": "dormant"} if new_cycle else {})},
                },
                return_document=ReturnDocument.AFTER,
                projection={"_id": 0},
            )
            if doc:
                await alog("resident_event", "event_rearmed" if new_cycle else "press_coalesced",
                           activation_id=activation_id, room=doc.get("room"), resident_id=resident_id,
                           alert_id=doc["alert_id"], kiosk_id=kiosk_id,
                           data={"cause": "rearm_from_consumed" if new_cycle else "repeat_press_same_cycle",
                                 "press_count_before": pc_before, "press_count_after": doc.get("press_count"),
                                 "activation_consumed_before": consumed_before, "activation_consumed_after": None,
                                 "event_age_sec": age, "semantic_class": semantic_class, "source": source,
                                 "press_id": press_id})
                return {**doc, "coalesced": True}
            # Staff closed this event after the lookup. Retry against the
            # current open event instead of adding a press to a closed one.
            raise _RetryActivation()

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
    doc["activation_id"] = activation_id_hint or uuid.uuid4().hex

    scope = _scope(resident_id, room)
    if scope:
        doc["open_event_key"] = scope
    # Insert before the receipt: losing concurrent creators must not leave
    # receipts pointing at events which were never persisted.
    await db.alerts.insert_one(dict(doc))

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
        await db.alerts.update_one(
            {"alert_id": doc["alert_id"]}, {"$set": {"receipt_id": doc["receipt_id"]}},
        )
    except Exception as e:
        log.warning(f"receipt creation failed for alert {doc['alert_id']}: {e}")

    doc.pop("_id", None)
    await alog("resident_event", "event_opened",
               activation_id=doc["activation_id"], room=doc.get("room"), resident_id=resident_id,
               alert_id=doc["alert_id"], kiosk_id=kiosk_id,
               data={"cause": "new_event", "press_count_before": 0, "press_count_after": 1,
                     "activation_consumed_before": None, "activation_consumed_after": None,
                     "event_age_sec": 0.0, "semantic_class": semantic_class, "source": source,
                     "triggered_by": triggered_by, "press_id": press_id})
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
