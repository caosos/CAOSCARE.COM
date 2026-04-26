"""Timers — short countdown reminders set by the AI mid-conversation.

Use case: "CAOS, remind me to take my pills in 20 minutes." The AI calls
the `set_timer` tool, this router persists a Timer doc, and the kiosk's
medication-poll loop also picks up due timers and speaks the message.

Distinct from MedReminder (which is a recurring daily schedule managed by
admin) — Timers are one-shot and resident-driven.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict
from deps import db, get_current_user
from models import now_utc, uid

router = APIRouter(prefix="/timers", tags=["timers"])


class Timer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timer_id: str = Field(default_factory=lambda: uid("tmr"))
    resident_id: Optional[str] = None
    room: Optional[str] = None
    kiosk_id: Optional[str] = None
    label: str                            # "Take your blood-pressure pill"
    due_at: str                           # ISO UTC
    fired: bool = False
    created_at: str = Field(default_factory=lambda: now_utc().isoformat())


class TimerCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    minutes: float = Field(..., ge=0.1, le=720)   # 6 sec → 12 hours
    resident_id: Optional[str] = None
    room: Optional[str] = None
    kiosk_id: Optional[str] = None


@router.post("/public")
async def create_timer_public(data: TimerCreate):
    """Public endpoint — invoked by the Realtime AI tool dispatcher mid-call,
    so it cannot rely on a user JWT. Validation is structural; the tool
    itself only fires when the model decides to."""
    due = (datetime.now(timezone.utc) + timedelta(minutes=data.minutes)).isoformat()
    t = Timer(
        label=data.label.strip(),
        due_at=due,
        resident_id=data.resident_id,
        room=data.room,
        kiosk_id=data.kiosk_id,
    )
    doc = t.model_dump()
    await db.timers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_timers(user=Depends(get_current_user)) -> List[dict]:
    items = await db.timers.find({}, {"_id": 0}).sort("due_at", -1).to_list(200)
    return items


@router.get("/due/by-room/{room}")
async def due_for_room(room: str):
    """Kiosk poll path — public, returns timers whose due_at has passed and
    haven't fired. Marks them fired atomically so they're spoken once."""
    now_iso = datetime.now(timezone.utc).isoformat()
    pending = await db.timers.find(
        {"room": room, "fired": False, "due_at": {"$lte": now_iso}},
        {"_id": 0},
    ).to_list(20)
    if pending:
        ids = [t["timer_id"] for t in pending]
        await db.timers.update_many(
            {"timer_id": {"$in": ids}},
            {"$set": {"fired": True, "fired_at": now_iso}},
        )
    return pending


@router.delete("/{timer_id}")
async def delete_timer(timer_id: str, user=Depends(get_current_user)):
    r = await db.timers.delete_one({"timer_id": timer_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Timer not found")
    return {"ok": True}
