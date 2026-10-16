"""'I was supposed to get my medicine at six - is someone coming?'

Owner scenario 2026-10-16 (aria-room-runtime-fixes-001). A medication
REMINDER is not proof that a med tech is coming, and Aria has no signal that
anyone is "on the way". This is the one truthful read + action path:

  1. read what is known: today's scheduled reminders for the resident
     (db.med_reminders), whether the kiosk announced them (db.med_ack), and
     any open Nursing request (db.staff_tasks) with its real lifecycle;
  2. report only what is confirmed - staff acknowledged / started, by whom;
  3. when nothing is confirmed, route a HIGH-priority Nursing request through
     the canonical request service (create_resident_request: dedup, receipt,
     staff notification), or re-ask on the open one;
  4. return the receipt/task ids and a spoken line that never says someone
     is coming or on the way, because no part of the system can prove that.
"""
import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from deps import db
from routes.aria_operational_state import task_lifecycle
from routes.facility_local_time import facility_clock, facility_tz
from routes.medications import acked_on
from routes.resident_requests import ResidentRequestInput, create_resident_request, OPEN_TASK_STATUSES

router = APIRouter(prefix="/medications", tags=["medications"])

NURSING = "nursing"
NO_CONFIRMATION = "I don't have confirmation that anyone is on the way yet."
_MED_WORDS = re.compile(r"\b(medic\w*|medicine|meds?|pills?|tablets?|dose|insulin|med tech)\b", re.I)


def _is_medication_request(task: dict) -> bool:
    text = " ".join(str(task.get(k) or "") for k in ("resident_words", "description", "title"))
    return bool(_MED_WORDS.search(text))


class MedicationStatusInput(BaseModel):
    resident_id: Optional[str] = None
    room: Optional[str] = None
    resident_words: Optional[str] = None
    conversation_session_id: Optional[str] = None


def _clock(hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


async def _schedule_today(resident_id: str, clock: dict) -> list:
    rows = await db.med_reminders.find(
        {"resident_id": resident_id, "active": True, "days": clock["weekday"]},
        {"_id": 0, "reminder_id": 1, "title": 1, "time_hhmm": 1},
    ).sort("time_hhmm", 1).to_list(20)
    out = []
    for r in rows:
        ack = await acked_on(r["reminder_id"], clock)
        out.append({"title": r.get("title"), "time": _clock(r["time_hhmm"]), "time_hhmm": r["time_hhmm"],
                    "due": r["time_hhmm"] <= clock["hhmm"],
                    "reminder_announced": bool(ack)})
    return out


def _staff_line(task: dict) -> Optional[str]:
    """Only what the request record proves."""
    life = task_lifecycle(task)
    who = task.get("assigned_name") or task.get("assigned_to_name")
    if life == "in_progress":
        return f"{who or 'A nurse'} has started on your nursing request."
    if life == "acknowledged":
        return "Nursing has acknowledged your request" + (f" and {who} has it." if who else ".")
    return None


async def check_medication_status(data: MedicationStatusInput) -> dict:
    clock = facility_clock(await facility_tz())
    schedule = await _schedule_today(data.resident_id, clock) if data.resident_id else []
    scope = {"resident_id": data.resident_id} if data.resident_id else {"room": data.room}
    # Only an open MEDICATION request can confirm anything about medication;
    # an unrelated open nursing request (toileting, a fall check) never does.
    open_rows = await db.staff_tasks.find(
        {**scope, "category": NURSING, "status": {"$in": OPEN_TASK_STATUSES}}, {"_id": 0},
    ).sort("created_at", -1).to_list(20)
    open_task = next((t for t in open_rows if _is_medication_request(t)), None)
    confirmed = _staff_line(open_task) if open_task else None
    result = {
        "ok": True, "source": "medication_status_check", "facility_time": clock["hhmm"],
        "scheduled_today": schedule,
        # Nothing in CAOSCare observes a staff member walking to the room.
        "someone_confirmed_on_the_way": False,
    }
    if confirmed:
        result.update(staff_confirmed=True, task_id=open_task["task_id"], lifecycle=task_lifecycle(open_task),
                      spoken=f"{confirmed} I can't see from here whether anyone is on the way.")
        return result

    words = (data.resident_words or "").strip() or "Resident is asking whether someone is coming with their medication."
    req = await create_resident_request(ResidentRequestInput(
        category=NURSING, resident_id=data.resident_id, room=data.room, resident_words=words,
        summary="Medication not received yet - resident asking whether someone is coming",
        priority="high", source="aria_voice", conversation_session_id=data.conversation_session_id,
    ))
    sent = ("I've asked nursing again on your open request" if req.get("duplicate")
            else "I'm sending a high-priority request to nursing now")
    result.update(staff_confirmed=False, task_id=req.get("task_id"), receipt_id=req.get("receipt_id"),
                  duplicate=bool(req.get("duplicate")), priority="high",
                  spoken=f"{NO_CONFIRMATION} {sent}.")
    return result


@router.post("/public/status-check")
async def medication_status_check(data: MedicationStatusInput):
    """Public resident bus (same trust model as /tasks/resident-request)."""
    return await check_medication_status(data)
