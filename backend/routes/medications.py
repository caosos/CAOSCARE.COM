"""Medication reminders — scheduled voice prompts spoken by the in-room kiosk.

Flow:
  - Admin creates a MedReminder for a resident: title, time "HH:MM", days list
    ("mon".."sun" or "daily"), active flag.
  - Each kiosk, when idle, polls /api/medications/due/{room} every 60s.
  - If a reminder matches the current local clock window (±1 minute) and hasn't
    been acknowledged today, the kiosk speaks the message and logs acknowledgement.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict
from deps import db, get_current_user
from models import now_utc, uid

router = APIRouter(prefix="/medications", tags=["medications"])

DayLiteral = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class MedReminder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reminder_id: str = Field(default_factory=lambda: uid("med"))
    resident_id: str
    resident_name: Optional[str] = None
    room: Optional[str] = None
    title: str                           # e.g. "Blood pressure pill"
    time_hhmm: str                        # "08:30"
    days: List[DayLiteral] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    dose_notes: Optional[str] = ""        # e.g. "One white tablet with water"
    active: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class MedReminderCreate(BaseModel):
    resident_id: str
    title: str
    time_hhmm: str
    days: List[DayLiteral] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    dose_notes: Optional[str] = ""
    active: bool = True


def _iso(doc):
    v = doc.get("created_at")
    if v and not isinstance(v, str):
        doc["created_at"] = v.isoformat()
    return doc


@router.get("")
async def list_reminders(user=Depends(get_current_user)):
    items = await db.med_reminders.find({}, {"_id": 0}).sort("time_hhmm", 1).to_list(500)
    for i in items:
        _iso(i)
    return items


@router.post("")
async def create_reminder(data: MedReminderCreate, user=Depends(get_current_user)):
    r = await db.residents.find_one({"resident_id": data.resident_id}, {"_id": 0, "name": 1, "room": 1})
    if not r:
        raise HTTPException(status_code=404, detail="Resident not found")
    rem = MedReminder(
        resident_id=data.resident_id,
        resident_name=r["name"],
        room=r.get("room"),
        title=data.title,
        time_hhmm=data.time_hhmm,
        days=data.days,
        dose_notes=data.dose_notes,
        active=data.active,
    )
    doc = rem.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.med_reminders.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: str, user=Depends(get_current_user)):
    r = await db.med_reminders.delete_one({"reminder_id": reminder_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"ok": True}


@router.get("/due/by-room/{room}")
async def due_for_room(room: str):
    """Kiosk calls this without auth. Returns reminders matching the current
    minute (server UTC time) for residents in `room`, filtered to those NOT
    already acknowledged today."""
    now_dt = now_utc()
    hhmm = now_dt.strftime("%H:%M")
    day_short = now_dt.strftime("%a").lower()[:3]  # mon/tue/...
    today = now_dt.date().isoformat()

    candidates = await db.med_reminders.find({
        "room": room,
        "active": True,
        "time_hhmm": hhmm,
        "days": day_short,
    }, {"_id": 0}).to_list(20)

    out = []
    for c in candidates:
        already = await db.med_ack.find_one({
            "reminder_id": c["reminder_id"],
            "day": today,
        }, {"_id": 0})
        if not already:
            out.append(_iso(c))
    return out


@router.post("/ack/{reminder_id}")
async def ack_reminder(reminder_id: str):
    """Kiosk calls this the moment it speaks the reminder so it doesn't repeat."""
    today = now_utc().date().isoformat()
    existing = await db.med_ack.find_one({"reminder_id": reminder_id, "day": today}, {"_id": 0})
    if existing:
        return {"ok": True, "already": True}
    doc = {
        "ack_id": uid("ack"),
        "reminder_id": reminder_id,
        "day": today,
        "at": now_utc().isoformat(),
    }
    await db.med_ack.insert_one(doc)
    doc.pop("_id", None)
    return doc
