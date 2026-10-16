"""Appointment routes (aria-appointment-verification-001).

Resident bus (public, same trust model as /medications/public/status-check):
  POST /appointments/public/check   - what Aria answers: "what time is my
                                       appointment", "is it definitely
                                       tomorrow", "did my doctor change it",
                                       "do I have a ride for it"
  POST /appointments/public/report  - the resident told Aria about one; it is
                                       recorded as REPORTED, never VERIFIED
Staff (signed in):
  POST /appointments/sources        - staff / family / email / calendar /
                                       uploaded / provider-call claim
  GET  /appointments?resident_id=   - the records with sources and history
  GET  /appointments/{id}
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, get_current_user
from operational_provenance import reject_past_date, reject_unconfirmed_time
from routes import appointment_truth as truth
from routes.actor_context import actor_from_user, actor_resident_claim
from routes.facility_local_time import facility_clock, facility_tz
from routes.resident_appointments import find_ride, match_appointment, record_source

router = APIRouter(prefix="/appointments", tags=["appointments"])

Focus = Literal["general", "time", "date", "change", "ride"]


class CheckInput(BaseModel):
    resident_id: Optional[str] = None
    room: Optional[str] = None
    about: Optional[str] = None          # "cardiologist", "Dr. Patel", "eye doctor"
    date: Optional[str] = None           # YYYY-MM-DD if they named a day
    focus: Focus = "general"


class ReportInput(BaseModel):
    resident_id: Optional[str] = None
    room: Optional[str] = None
    provider: Optional[str] = None
    location: Optional[str] = None
    date: str
    time: Optional[str] = None           # HH:MM 24h, only if they said a time
    time_as_said: Optional[str] = None   # "around 10", "10 o'clock"
    resident_words: Optional[str] = None
    says_changed: bool = False           # "they moved it to Thursday" - still only reported
    conversation_session_id: Optional[str] = None


class SourceInput(BaseModel):
    resident_id: str
    appointment_id: Optional[str] = None
    source_type: Literal["staff_entry", "family_entry", "email_confirmation", "calendar_confirmation",
                         "uploaded_confirmation", "provider_call"]
    intent: Literal["report", "confirm", "change", "cancel", "resolve"] = "confirm"
    date: Optional[str] = None
    time: Optional[str] = None
    timezone: Optional[str] = None
    provider: Optional[str] = None
    office: Optional[str] = None
    location: Optional[str] = None
    purpose: Optional[str] = None
    transport_notes: Optional[str] = None
    evidence_ref: Optional[str] = None   # email message id, calendar event id, upload id, call id
    evidence_note: Optional[str] = None
    staff_verified: bool = False         # staff attest they checked it against a confirmation
    reported_by_name: Optional[str] = None


async def _resident(resident_id: Optional[str], room: Optional[str]) -> dict:
    q = {"resident_id": resident_id} if resident_id else {"room": room} if room else None
    if not q:
        raise HTTPException(400, "resident_id or room required")
    rows = await db.residents.find(q, {"_id": 0, "resident_id": 1, "room": 1, "preferred_name": 1,
                                       "name": 1}).to_list(3)
    if len(rows) != 1:
        raise HTTPException(404 if not rows else 409, "can't tell which resident this is")
    return rows[0]


async def _today() -> tuple[str, str]:
    tz = await facility_tz()
    return facility_clock(tz)["date"], tz


def view(appt: dict, today: str, tz: str, focus: str = "general", ride=None, ride_checked=False) -> dict:
    derived = truth.derive([dict(s) for s in appt["sources"]])
    full = {**appt, "derived": derived}
    return {
        "appointment_id": appt["appointment_id"], "status": appt["status"], "name": truth.appointment_name(appt),
        "date": appt.get("date"), "time": appt.get("time"), "timezone": appt.get("timezone"),
        "starts_at_utc": appt.get("starts_at_utc"), "location": appt.get("location"),
        "verified": appt["status"] in (truth.VERIFIED, truth.CHANGED),
        "last_verified_at": appt.get("last_verified_at"),
        "days_away": _days_away(appt.get("date"), today),
        "spoken": truth.spoken_answer(full, today=today, facility_tz=tz, focus=focus, ride=ride,
                                      ride_checked=ride_checked),
        "ride": ride if focus == "ride" else None,
    }


def _days_away(day: Optional[str], today: str) -> Optional[int]:
    from datetime import date
    return (date.fromisoformat(day) - date.fromisoformat(today)).days if day else None


async def check(data: CheckInput) -> dict:
    res = await _resident(data.resident_id, data.room)
    today, tz = await _today()
    if data.about or data.date:
        appt = await match_appointment(res["resident_id"], data.about, data.date, include_cancelled=True)
        rows = [appt] if appt else []
    else:                                              # "my appointment": the next ones still ahead
        rows = await db.resident_appointments.find(
            {"resident_id": res["resident_id"], "status": {"$ne": truth.CANCELLED}}, {"_id": 0}).to_list(100)
        rows = [r for r in rows if not r.get("date") or r["date"] >= today]
        rows.sort(key=lambda r: (r.get("date") or "9999", r.get("time") or "99:99"))
    if not rows:
        what = f"a {data.about} appointment" if data.about else "an appointment"
        when = f" on {truth.say_day(data.date, today)}" if data.date else ""
        return {"ok": True, "found": False, "appointments": [],
                "spoken": f"I don't have {what}{when} on record. If you tell me about it, I can note it, "
                          "but it would be unverified until there's a confirmation."}
    out = []
    for appt in rows[:3]:
        ride, checked = await find_ride(appt) if data.focus == "ride" else (None, False)
        out.append(view(appt, today, tz, data.focus, ride, checked))
    spoken = out[0]["spoken"] if len(out) == 1 else (
        f"You have {len(rows)} appointments on record. " + " ".join(v["spoken"] for v in out))
    return {"ok": True, "found": True, "appointments": out, "spoken": spoken}


async def report(data: ReportInput) -> dict:
    res = await _resident(data.resident_id, data.room)
    past = reject_past_date(data.date)
    if past:
        return {"ok": False, "recorded": False, **past, "spoken": past["ask"]}
    if data.time_as_said:
        why = await reject_unconfirmed_time(data.time_as_said, resident_id=res["resident_id"],
                                            conversation_session_id=data.conversation_session_id)
        if why:
            return {"ok": False, "recorded": False, "reason": why,
                    "spoken": "I didn't catch a time from you, so I haven't noted one. What time did they give you?"}
    actor = actor_resident_claim(res["resident_id"], res.get("room"), "aria_voice")
    appt = await record_source(
        resident_id=res["resident_id"], room=res.get("room"), actor=actor,
        conversation_session_id=data.conversation_session_id,
        claim={"source_type": "resident_speech", "intent": "change" if data.says_changed else "report",
               "date": data.date, "time": data.time, "provider": data.provider, "location": data.location,
               "as_said": data.resident_words or data.time_as_said})
    today, tz = await _today()
    v = view(appt, today, tz)
    return {"ok": True, "recorded": True, "appointment_id": appt["appointment_id"], "status": appt["status"],
            "verified": v["verified"], "receipt_id": appt["history"][-1]["receipt_id"], "spoken": v["spoken"]}


@router.post("/public/check")
async def public_check(data: CheckInput):
    return await check(data)


@router.post("/public/report")
async def public_report(data: ReportInput):
    return await report(data)


def _staff(user: dict) -> None:
    if user.get("role") not in ("owner", "admin", "staff", "front_desk"):
        raise HTTPException(403, "staff only")


@router.post("/sources")
async def add_source(data: SourceInput, user=Depends(get_current_user)):
    _staff(user)
    res = await _resident(data.resident_id, None)
    claim = data.model_dump(exclude={"resident_id", "appointment_id"})
    appt = await record_source(resident_id=res["resident_id"], room=res.get("room"), claim=claim,
                               actor=actor_from_user(user), appointment_id=data.appointment_id)
    today, tz = await _today()
    return {**appt, "spoken_preview": view(appt, today, tz)["spoken"]}


@router.get("")
async def list_appointments(resident_id: str, user=Depends(get_current_user)):
    _staff(user)
    rows = await db.resident_appointments.find({"resident_id": resident_id}, {"_id": 0}) \
        .sort("updated_at", -1).to_list(200)
    return {"items": rows}


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, user=Depends(get_current_user)):
    _staff(user)
    appt = await db.resident_appointments.find_one({"appointment_id": appointment_id}, {"_id": 0})
    if not appt:
        raise HTTPException(404, "appointment not found")
    return appt
