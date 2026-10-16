"""Canonical outside-appointment record (aria-appointment-verification-001).

One `db.resident_appointments` document per appointment. Every source that
says something about it - the resident telling Aria, a staff or family entry,
a confirmation email / calendar entry / uploaded document, later an
authorized call to the office - is appended to `sources` as a claim with its
provenance, and the status, date and time are re-derived from all claims
(routes/appointment_truth.py). Nothing is overwritten: superseded claims stay
on the record, every change is a `history` entry, and every write is one
receipt (actor, authority, before/after, evidence, chained per appointment).

Callers: routes/appointments.py (resident bus + staff API). An inbound-email
or calendar parser would call record_source() with actor_system(...).
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from deps import db
from models import uid
from routes import appointment_truth as truth
from routes.actor_context import ActorContext
from routes.facility_local_time import facility_tz
from routes.receipts import create_receipt

_CLAIM_FIELDS = ("date", "time", "timezone", "provider", "office", "location", "purpose", "transport_notes",
                 "as_said", "evidence_ref", "evidence_note", "staff_verified", "reported_by_name")
_STOP = {"my", "the", "a", "an", "doctor", "doctors", "dr", "appointment", "appt", "office", "with", "at", "to",
         "see", "visit", "i", "think", "is", "on", "for", "of", "and", "s"}
_RECEIPT_SOURCE = {"aria_voice": "aria_voice", "staff_ui": "staff", "email": "system", "system": "system"}


async def ensure_indexes() -> None:
    """From app startup only: one record per appointment id, and the
    per-resident lookup the matcher and the check route use."""
    await db.resident_appointments.create_index("appointment_id", unique=True, name="appointment_id_unique")
    await db.resident_appointments.create_index([("resident_id", 1), ("updated_at", -1)], name="resident_lookup")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokens(text: Optional[str]) -> set:
    words = "".join(c.lower() if c.isalnum() else " " for c in (text or "")).split()
    return {w for w in words if w not in _STOP and len(w) > 1}


def _validate(claim: dict, actor: ActorContext) -> dict:
    kind, intent = claim.get("source_type"), claim.get("intent") or "report"
    if kind not in truth.SOURCE_TYPES:
        raise HTTPException(422, f"unknown source_type {kind!r}")
    if intent not in truth.INTENTS:
        raise HTTPException(422, f"unknown intent {intent!r}")
    if (kind == "resident_speech") != (actor.role == "resident"):
        raise HTTPException(403, "resident speech comes only from the resident's room; staff record other sources")
    if kind in ("resident_speech", "family_entry") and intent in ("confirm", "resolve"):
        intent = "report"                       # a resident or family member reports; they can't verify
    if kind in truth.CONFIRMATION_TYPES + ("provider_call",) and not claim.get("evidence_ref"):
        raise HTTPException(422, f"a {kind.replace('_', ' ')} needs its evidence reference")
    if intent == "resolve" and not (kind == "staff_entry" and claim.get("staff_verified")):
        raise HTTPException(422, "only a staff-verified entry can resolve a conflict")
    if kind != "staff_entry":
        claim.pop("staff_verified", None)
    if intent != "cancel" and not claim.get("date"):
        raise HTTPException(422, "date (YYYY-MM-DD) is required")
    try:
        if claim.get("date"):
            datetime.strptime(claim["date"], "%Y-%m-%d")
        if claim.get("time"):
            datetime.strptime(claim["time"], "%H:%M")
        ZoneInfo(claim["timezone"])
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"bad date, time or timezone: {e}")
    claim["intent"] = intent
    return claim


async def _check_call_evidence(claim: dict, resident_id: str) -> None:
    """A provider call verifies only if CAOSCare has the call and it connected
    (routes/call_lifecycle.py) - never because someone says the office was called."""
    if claim["source_type"] != "provider_call":
        return
    call = await db.call_sessions.find_one({"call_id": claim["evidence_ref"]}, {"_id": 0})
    if not call or not call.get("connected_at"):
        raise HTTPException(422, "no connected call with that id is on record, so the office was not reached")
    if call.get("resident_id") not in (None, resident_id):
        raise HTTPException(422, "that call belongs to another resident")


def _candidate_dates(doc: dict) -> set:
    return {s.get("date") for s in doc.get("sources", []) if s.get("date")}


async def match_appointment(resident_id: str, about: Optional[str], day: Optional[str],
                            include_cancelled: bool = False) -> Optional[dict]:
    """The resident's appointment a mention refers to: the same provider /
    office / purpose words, else the same day. None = a new appointment."""
    q = {"resident_id": resident_id}
    if not include_cancelled:
        q["status"] = {"$ne": truth.CANCELLED}
    rows = await db.resident_appointments.find(q, {"_id": 0}).sort("updated_at", -1).to_list(200)
    want = tokens(about)
    if want:
        named = [r for r in rows if want & tokens(" ".join(filter(None, (r.get("provider"), r.get("office"),
                                                                         r.get("purpose")))))]
        if named:
            dated = [r for r in named if day and day in _candidate_dates(r)]
            return (dated or named)[0]
        return None
    if day:
        return next((r for r in rows if day in _candidate_dates(r)), None)
    return None


def _project(doc: dict) -> dict:
    """Canonical fields from the derived truth."""
    d = truth.derive(doc["sources"])
    gov = d["governing"]
    latest = lambda key: next((s.get(key) for s in reversed(doc["sources"]) if s.get(key)), None)  # noqa: E731
    settled = d["status"] in (truth.VERIFIED, truth.CHANGED, truth.REPORTED, truth.NEEDS_CONFIRMATION) and gov
    when = gov if settled and gov.get("intent") != "cancel" else None
    out = {
        "status": d["status"],
        "date": when.get("date") if when else None,
        "time": when.get("time") if when else None,
        "timezone": (when or {}).get("timezone") or latest("timezone"),
        "starts_at_utc": truth.starts_at_utc(when.get("date"), when.get("time"), when["timezone"]) if when else None,
        "provider": latest("provider"), "office": latest("office"), "location": latest("location"),
        "purpose": latest("purpose"), "transport_notes": latest("transport_notes"),
        "governing_source_id": gov["source_id"] if gov else None,
        "superseded_source_ids": d["superseded"],
        "discrepancy_source_ids": [s["source_id"] for s in d["discrepancies"]],
        "candidate_source_ids": [s["source_id"] for s in d["candidates"]],
    }
    if gov and gov["authoritative"] and d["status"] != truth.CONFLICT:
        out["last_verified_at"] = gov["received_at"]
        out["verified_by"] = gov["source_type"]
    else:
        out["last_verified_at"], out["verified_by"] = None, None
    return out


_ACTION = {truth.VERIFIED: "appointment_verified", truth.CONFLICT: "appointment_conflict",
           truth.CHANGED: "appointment_changed", truth.CANCELLED: "appointment_cancelled",
           truth.NEEDS_CONFIRMATION: "appointment_needs_confirmation", truth.REPORTED: "appointment_reported"}


def _action(before: Optional[str], after: str, intent: str) -> str:
    if before is None:
        return "appointment_created"
    if before == truth.CONFLICT and after in (truth.VERIFIED, truth.CHANGED) and intent == "resolve":
        return "appointment_conflict_resolved"
    return _ACTION[after] if before != after else "appointment_source_added"


def _authority(actor: ActorContext, room: Optional[str]) -> str:
    if actor.actor_type == "system":
        return f"system:{actor.name}"
    if actor.role == "resident":
        return f"resident_claim:room:{room or 'unknown'}"
    return f"admin_override:{actor.role}" if actor.role in ("owner", "admin") else f"staff_entry:{actor.role}"


def _state(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    return {k: doc.get(k) for k in ("status", "date", "time", "timezone", "provider", "location")}


async def record_source(*, resident_id: str, room: Optional[str], claim: dict, actor: ActorContext,
                        appointment_id: Optional[str] = None, conversation_session_id: Optional[str] = None) -> dict:
    """Append one claim to the resident's appointment (matched, named, or new),
    re-derive its truth and write one receipt. Returns the updated record."""
    claim = {k: claim.get(k) for k in ("source_type", "intent") + _CLAIM_FIELDS if claim.get(k) not in (None, "")}
    claim.setdefault("timezone", await facility_tz())
    claim = _validate(claim, actor)
    await _check_call_evidence(claim, resident_id)

    for _ in range(3):                                   # optimistic retry on a concurrent write
        if appointment_id:
            doc = await db.resident_appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
            if not doc or doc["resident_id"] != resident_id:
                raise HTTPException(404, "appointment not found for this resident")
        else:
            about = " ".join(filter(None, (claim.get("provider"), claim.get("office"), claim.get("purpose"))))
            doc = await match_appointment(resident_id, about, claim.get("date"),
                                          include_cancelled=claim["intent"] != "report")
        new = doc is None
        if new and claim["intent"] in ("cancel", "resolve"):
            raise HTTPException(404, "no matching appointment on record to cancel or resolve")
        doc = doc or {"appointment_id": uid("appt"), "resident_id": resident_id, "room": room, "sources": [],
                      "history": [], "version": 0, "created_at": _now()}
        before = _state(None if new else doc)
        receipt_id = uid("rcpt")
        source = {**claim, "source_id": uid("src"), "received_at": _now(), "receipt_id": receipt_id,
                  "conversation_session_id": conversation_session_id, "actor": actor.receipt_fields()}
        sources = doc["sources"] + [source]
        projected = _project({**doc, "sources": sources})
        source["authoritative"] = truth.is_authoritative(source)
        action = _action(before and before["status"], projected["status"], claim["intent"])
        entry = {"at": source["received_at"], "action": action, "source_id": source["source_id"],
                 "source_type": claim["source_type"], "status_before": before and before["status"],
                 "status_after": projected["status"], "receipt_id": receipt_id}
        update = {"$set": {**projected, "updated_at": source["received_at"], "version": doc["version"] + 1},
                  "$push": {"sources": source, "history": entry}}
        if new:
            base = {k: v for k, v in doc.items() if k not in ("sources", "history", "version")}
            res = await db.resident_appointments.update_one(
                {"appointment_id": doc["appointment_id"]},
                {**update, "$setOnInsert": base}, upsert=True)
            ok = res.upserted_id is not None
        else:
            res = await db.resident_appointments.update_one(
                {"appointment_id": doc["appointment_id"], "version": doc["version"]}, update)
            ok = res.modified_count == 1
        if ok:
            break
    else:
        raise HTTPException(409, "the appointment changed while recording; try again")

    after = {**_state({**doc, **projected})}
    earlier = doc["history"][-1]["receipt_id"] if doc["history"] else None
    first = doc["history"][0]["receipt_id"] if doc["history"] else receipt_id
    await create_receipt(
        action_type=action, related_object_type="resident_appointment", related_object_id=doc["appointment_id"],
        source=_RECEIPT_SOURCE.get(actor.channel, "staff"), resident_id=resident_id, room=room,
        conversation_session_id=conversation_session_id, status="completed",
        result=f"{claim['source_type']} ({claim['intent']}) -> {projected['status']}",
        receipt_id=receipt_id,
        provenance={**actor.receipt_fields(), "authority": _authority(actor, room), "parent_receipt_id": earlier,
                    "correlation_id": first, "before_state": before, "after_state": after,
                    "result_label": "verified" if source["authoritative"] and projected["status"] in (
                        truth.VERIFIED, truth.CHANGED, truth.CANCELLED) else "unverified",
                    "provider_refs": [r for r in (source["source_id"], claim.get("evidence_ref")) if r],
                    "next_state": projected["status"]},
    )
    return await db.resident_appointments.find_one({"appointment_id": doc["appointment_id"]}, {"_id": 0})


async def find_ride(appt: dict) -> tuple[Optional[dict], bool]:
    """(ride, checked): an open transportation request for the resident on the
    appointment day, read through the ride's own summary. Not checked when the
    day isn't settled."""
    if not appt.get("date"):
        return None, False
    from routes.resident_requests import OPEN_TASK_STATUSES
    from routes.task_ride_link import ride_summary
    ride = await db.staff_tasks.find_one(
        {"resident_id": appt["resident_id"], "category": "transportation", "requested_for_date": appt["date"],
         "status": {"$in": OPEN_TASK_STATUSES}}, {"_id": 0}, sort=[("created_at", -1)])
    return (await ride_summary(ride) if ride else None), True
