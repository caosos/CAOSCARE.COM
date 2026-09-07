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
from datetime import datetime
from typing import Optional

from deps import db
from models import Alert, PressRecord, now_utc
from routes.activation_log import alog, new_activation_id

log = logging.getLogger(__name__)

# Only this transmission-semantics class may enter the activation path. The
# gate is enforced upstream in routes/rf_matched_intake.py (a supervisory /
# tamper / battery / unknown frame is never passed here at all); this is a
# defence-in-depth backstop so a future caller can't bypass it silently.
ACTIVATION_SEMANTIC_CLASS = "help_press"

# One physical press of a real Interlogix-Security / Lifeline pendant emits
# ~3-8 RF frames at a ~0.5s cadence, spanning up to ~3.2s (live-evidenced,
# Room 214 pendant rfd_6e8f06632b41, 2026-09-06: see docs/LEVEL1_BREAKTEST.md).
# The android bridge POSTs every frame to /rf/event with its own monotonic
# sequence, and nothing between there and here collapses them - so without
# this window every echo frame was a separate press_count increment and a
# separate presses[] record (invariants 2 and 3).
#
# The window is measured from the PREVIOUS frame of the same device on the
# same open event (tracked as Alert.last_rf_frame_at), not from the first
# frame - so the whole repeat train collapses no matter how long it runs,
# while a genuinely new press this many seconds after the last frame still
# counts (invariant 4). ~0.5s is the observed frame cadence; the default
# leaves generous slack for missed/re-sent frames without bridging two real
# presses. Env-overridable for other pendant hardware / to let tests shrink
# it. A help pendant cannot physically distinguish "button held/re-fired"
# from "pressed twice fast" anyway, so collapsing a sub-window re-press is
# the safe call - every raw frame is still in db.rf_events regardless.
try:
    RF_PRESS_DEBOUNCE_SECONDS = float(os.environ.get("RF_PRESS_DEBOUNCE_SECONDS", "3"))
except ValueError:
    RF_PRESS_DEBOUNCE_SECONDS = 3.0


def _is_echo_frame(open_alert: dict, source: str, device_id: Optional[str]) -> bool:
    """True when this frame is a repeat frame of a physical press already
    recorded on `open_alert` - i.e. it lands within RF_PRESS_DEBOUNCE_SECONDS
    of the previous frame from the SAME device. Only RF-pendant frames echo;
    kiosk-button presses are discrete deliberate taps and are never
    debounced."""
    if source != "rf_pendant" or not device_id:
        return False
    if open_alert.get("last_rf_frame_device") != device_id:
        return False
    last_at = open_alert.get("last_rf_frame_at")
    if not last_at:
        # Older event opened before this field existed - fall back to the
        # last recorded same-device press timestamp.
        for p in reversed(open_alert.get("presses") or []):
            if p.get("source") == "rf_pendant" and p.get("device_id") == device_id:
                last_at = p.get("at")
                break
    if not last_at:
        return False
    try:
        prev = datetime.fromisoformat(last_at) if isinstance(last_at, str) else last_at
        delta = (now_utc() - prev).total_seconds()
    except (ValueError, TypeError):
        return False
    return 0 <= delta < RF_PRESS_DEBOUNCE_SECONDS


def _rf_frame_stamp(source: str, device_id: Optional[str]) -> dict:
    """The last-frame marker to write on every RF frame (echo or counted) so
    the next frame is measured from this one."""
    if source == "rf_pendant" and device_id:
        return {"last_rf_frame_at": now_utc().isoformat(), "last_rf_frame_device": device_id}
    return {}


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
    semantic_class: str = "help_press",
    activation_id_hint: Optional[str] = None,
) -> dict:
    """Attach this press to the resident's open event, or open a new one.
    Returns the resulting alert dict (already persisted) plus a
    `coalesced` bool the caller can use to decide what response to send,
    and the `activation_id` correlation id for the cycle it landed in.

    `semantic_class` MUST be "help_press" - anything else is refused here
    (the real gate is upstream, this only backstops a bypass)."""
    if semantic_class != ACTIVATION_SEMANTIC_CLASS:
        await alog("resident_event", "activation_refused_non_help",
                   room=room, resident_id=resident_id, kiosk_id=kiosk_id,
                   data={"semantic_class": semantic_class, "source": source})
        log.warning(f"record_resident_activation refused: semantic_class={semantic_class!r} (not help_press)")
        return {"coalesced": False, "refused": True, "semantic_class": semantic_class, "alert_id": None}

    press = PressRecord(device_id=device_id, source=source, rssi=rssi)
    press_dict = press.model_dump()
    press_dict["at"] = press_dict["at"].isoformat()

    def _age(created_at) -> float:
        try:
            c = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
            return round((now_utc() - c).total_seconds(), 1)
        except Exception:
            return -1.0

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
            frame_stamp = _rf_frame_stamp(source, device_id)
            pc_before = open_alert.get("press_count", 0)
            consumed_before = open_alert.get("activation_consumed_at")
            age = _age(open_alert.get("created_at"))
            if _is_echo_frame(open_alert, source, device_id):
                # Repeat frame of a press already counted. rf.py still writes
                # this frame to db.rf_events unconditionally - evidence is
                # kept, only the human-press count is protected. Do not touch
                # press_count / presses[] / activation_consumed_at; only
                # advance the last-frame marker so the train keeps collapsing.
                if frame_stamp:
                    await db.alerts.update_one(
                        {"alert_id": open_alert["alert_id"]}, {"$set": frame_stamp},
                    )
                await alog("resident_event", "press_echo_suppressed",
                           activation_id=open_alert.get("activation_id"), room=open_alert.get("room"),
                           resident_id=resident_id, alert_id=open_alert["alert_id"],
                           data={"press_count": pc_before, "reason": "rf_echo_window",
                                 "semantic_class": semantic_class, "source": source})
                return {**open_alert, "coalesced": True, "echo_frame": True,
                        "activation_id": open_alert.get("activation_id")}

            # A press onto an already-consumed cycle (or one that never had
            # an activation_id) RE-ARMS the event: a new activation cycle.
            rearm = bool(consumed_before) or not open_alert.get("activation_id")
            activation_id = (activation_id_hint or new_activation_id()) if rearm else open_alert["activation_id"]
            await db.alerts.update_one(
                {"alert_id": open_alert["alert_id"]},
                {
                    "$inc": {"press_count": 1},
                    "$push": {"presses": press_dict},
                    "$set": {"activation_consumed_at": None, "activation_id": activation_id, **frame_stamp},
                },
            )
            doc = await db.alerts.find_one({"alert_id": open_alert["alert_id"]}, {"_id": 0})
            await alog("resident_event", "event_rearmed" if rearm else "press_coalesced",
                       activation_id=activation_id, room=doc.get("room"), resident_id=resident_id,
                       alert_id=doc["alert_id"], kiosk_id=kiosk_id,
                       data={"cause": "rearm_from_consumed" if rearm else "repeat_press_same_cycle",
                             "press_count_before": pc_before, "press_count_after": doc.get("press_count"),
                             "activation_consumed_before": consumed_before, "activation_consumed_after": None,
                             "event_age_sec": age, "semantic_class": semantic_class, "source": source})
            return {**doc, "coalesced": True, "activation_id": activation_id}

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
    doc["activation_id"] = activation_id_hint or new_activation_id()
    doc.update(_rf_frame_stamp(source, device_id))

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
    await alog("resident_event", "event_opened",
               activation_id=doc["activation_id"], room=doc.get("room"), resident_id=resident_id,
               alert_id=doc["alert_id"], kiosk_id=kiosk_id,
               data={"cause": "new_event", "press_count_before": 0, "press_count_after": 1,
                     "activation_consumed_before": None, "activation_consumed_after": None,
                     "event_age_sec": 0.0, "semantic_class": semantic_class, "source": source,
                     "triggered_by": triggered_by})
    return {**doc, "coalesced": False, "activation_id": doc["activation_id"]}


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
