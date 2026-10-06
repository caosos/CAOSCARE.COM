"""Transportation lane (Terminal 8, lane 3): resident request/receipt bus
+ a real availability ledger, per the Terminal 8 handoff's calendar
decision. Availability lives in TransportSlot (an internal schedule here -
see docs/TERMINAL_8_OPERATIONAL_LAYER.md for the real-Outlook-calendar
boundary, not yet built). A request is a StaffTask (category=
"transportation") that POINTS AT a slot via transport_slot_id once
reserved - availability, request, and booking stay separate concerns.

Capability-state discipline (verified_read vs verified_control), inherited
directly from the handoff: an open slot is verified_read - Aria may say
"there's an opening." A slot is only verified_control - Aria may say
"you're booked" - once transport_slot_id is actually set AND a
"transportation_booked" receipt exists. Reservation uses an atomic
find_one_and_update with a capacity guard so two concurrent requests for
the same last slot cannot both win it.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import StaffTask, TaskPriority, now_utc
from deps import db
from routes.notifications import notify_department, task_notice
from routes.tasks import _resolve_denorms
from routes import task_lifecycle
from routes.task_history import task_event
from routes.transport_task_history import booking_entry, close_events, ride_actor, ride_authority, who
from routes.realtime_facility import today_facility_date
from routes.transportation_legacy_slots import DEFAULT_SLOT_HOURS, release_legacy_slot
from transportation_engine import find_or_create_run, release_task_from_run, get_scheduling_config, to_minutes, find_free_resource_pair
from operational_provenance import reject_unconfirmed_time

router = APIRouter(prefix="/transportation", tags=["transportation"])

OPEN_TASK_STATUSES = ["pending", "in_progress"]


# ================= AVAILABILITY =================
@router.get("/availability/public")
async def public_availability(date: Optional[str] = None):
    """No auth - what Aria's 'ask availability' tool calls. Resource-aware
    (driver+vehicle), the same engine /request actually books against, so
    this can never promise an opening /request then can't honor. Checked at
    the DEFAULT_SLOT_HOURS marks purely as a UX granularity for offering
    times; /request itself books to the exact minute given."""
    day = date or today_facility_date()
    config = await get_scheduling_config()
    buffer_minutes = config.get("buffer_minutes", 30)
    out = []
    for hh in DEFAULT_SLOT_HOURS:
        start = to_minutes(hh)
        window = (start - buffer_minutes, start + buffer_minutes)
        driver, vehicle = await find_free_resource_pair(day, window, buffer_minutes)
        out.append({"start_time": hh, "open": bool(driver and vehicle)})
    return out


# ================= REQUEST =================
class TransportRequestInput(BaseModel):
    resident_id: Optional[str] = None
    room: Optional[str] = None
    purpose: str                                # "pharmacy", "doctor appointment", etc.
    requested_for_date: str
    requested_for_time_label: Optional[str] = None   # free text as heard, e.g. "around 10"
    start_time: Optional[str] = None            # exact "HH:00" if a specific open slot was chosen
    priority: TaskPriority = "normal"
    source: str = "aria_voice"
    conversation_session_id: Optional[str] = None


# Sources the public (unauthenticated) request path may claim. A request
# raised by staff goes through routes/transportation_staff.py instead.
PUBLIC_SOURCES = ("aria_voice", "kiosk_button")


def _booking_notify_body(task: dict, run: Optional[dict]) -> str:
    if run:
        shared = f" (sharing run with {len(run['resident_task_ids']) - 1} other resident(s))" if len(run.get("resident_task_ids", [])) > 1 else ""
        return (
            f"BOOKED — {task['requested_for_date']} at {run['depart_time']}{shared}\n"
            f"Purpose: {task['description']}\nRoom: {task.get('room') or 'unknown'}"
        )
    return (
        f"REQUESTED (no run secured yet) — {task['requested_for_date']} "
        f"({task.get('requested_for_time_label') or 'no time given'})\n"
        f"Purpose: {task['description']}\nRoom: {task.get('room') or 'unknown'}"
    )


@router.post("/request")
async def create_transport_request(data: TransportRequestInput):
    """No auth - same public trust model as the other resident-facing
    request endpoints. The time guard and booking live in
    submit_transport_request, shared with the staff path."""
    if data.source not in PUBLIC_SOURCES:
        raise HTTPException(status_code=403, detail="Staff-entered requests use /transportation/staff/request")
    # 2026-08-23: same guard as /tasks/resident-request - a claimed clock
    # time must trace back to something the resident actually said.
    rejection = await reject_unconfirmed_time(
        f"{data.purpose} {data.requested_for_time_label or ''}",
        resident_id=data.resident_id, conversation_session_id=data.conversation_session_id,
    )
    if rejection:
        raise HTTPException(status_code=422, detail={"needs_clarification": True, "field": "requested_for_time_label", "reason": rejection})
    return await submit_transport_request(data)


async def submit_transport_request(
    data: TransportRequestInput, *, actor: Optional[dict] = None, destination: Optional[str] = None,
    driver_id: Optional[str] = None, vehicle_id: Optional[str] = None,
) -> dict:
    """Create (or re-request) one ride and try to book it. Dedup: an
    existing open transportation request for the same resident/room on the
    SAME requested_for_date is treated as a re-request (history preserved,
    not silently discarded), matching the maintenance/nursing re-request
    pattern. A different date is treated as a genuinely separate ride.
    `actor` is the staff user entering it; None means the resident.
    Every step is a task_lifecycle transition with its own chained receipt
    (SIM-0 / SC-15)."""
    user, authority = actor, ride_authority(actor)
    dup_q: dict = {
        "category": "transportation", "status": {"$in": OPEN_TASK_STATUSES},
        "requested_for_date": data.requested_for_date,
    }
    if data.resident_id:
        dup_q["resident_id"] = data.resident_id
    elif data.room:
        dup_q["room"] = data.room
    else:
        dup_q = None

    existing = await db.staff_tasks.find_one(dup_q, {"_id": 0}, sort=[("created_at", -1)]) if dup_q else None
    if existing:
        ra = ride_actor(user, existing, data.source)
        # A legacy ride with no recorded origin refuses the change (recorded,
        # D5); the ask is then filed as a new ride rather than lost (D3).
        try:
            existing, receipt = await task_lifecycle.transition(
                existing["task_id"], ra, user, action="re_request", authority=authority,
                action_type="transportation_re_requested", status="created",
                build=lambda t, rid: (
                    {"re_request_count": t.get("re_request_count", 0) + 1,
                     "last_re_requested_at": now_utc().isoformat()},
                    [task_event("re_request", to=t.get("re_request_count", 0) + 1, text=data.purpose,
                                **who(ra, rid))]))
        except task_lifecycle.LifecycleError as e:
            if e.status_code != 409:
                raise
            existing = None
    if existing:
        return {
            "task_id": existing["task_id"], "receipt_id": receipt["receipt_id"],
            "status": existing["status"], "duplicate": True, "re_request_count": existing["re_request_count"],
            "booked": bool(existing.get("transport_run_id") or existing.get("transport_slot_id")),
        }

    payload = {
        "title": f"Transportation: {data.purpose[:100]}",
        "description": data.purpose,
        "category": "transportation",
        "priority": data.priority,
        "source": data.source,
        "visibility_role": "transportation",
        "resident_id": data.resident_id,
        "room": data.room,
        "resident_words": data.purpose if data.source in PUBLIC_SOURCES else None,
        "conversation_session_id": data.conversation_session_id,
        "requested_for_date": data.requested_for_date,
        "requested_for_time_label": data.requested_for_time_label,
        **await task_lifecycle.simulation_marker(data.resident_id),
    }
    await _resolve_denorms(payload)
    task = StaffTask(**payload)
    doc = task.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.staff_tasks.insert_one(doc)
    doc.pop("_id", None)
    ra = ride_actor(user, doc, data.source)
    receipt = await task_lifecycle.record_origin(doc, ra, action_type="transportation_requested",
                                                 authority=authority)

    # Resource-aware booking (see transportation_engine.py) - the single
    # place Aria, Admin, and Front Desk all get the same booked/pending
    # answer from. Needs the real task_id, so this runs after insert. An
    # exact time with no free run is a real "needs coordination" step
    # (transportation_no_slot), distinct from "no time given yet".
    booking = await find_or_create_run(data.requested_for_date, data.start_time, destination, doc["task_id"], driver_id, vehicle_id)
    run = booking["run"]
    entry = await booking_entry(run, requested_time=data.start_time, date=data.requested_for_date)
    if entry:
        field, text = entry
        _, step = await task_lifecycle.transition(
            doc["task_id"], ra, user, action="book", authority=authority, result=text,
            action_type="transportation_booked" if run else "transportation_no_slot", status="created",
            build=lambda t, rid: ({"transport_run_id": run["run_id"]} if run else None,
                                  [task_event(field, text=text, **who(ra, rid))]))
        receipt = step or receipt
    if run:
        doc["transport_run_id"] = run["run_id"]
    await notify_department("transportation", f"CAOS Care: transportation {'booked' if run else 'requested'}", _booking_notify_body(doc, run),
                            **task_notice(doc, receipt["receipt_id"]))

    return {
        "task_id": doc["task_id"], "receipt_id": receipt["receipt_id"], "status": doc["status"],
        "duplicate": False, "booked": bool(run), "shared": booking["shared"],
        "run": {"date": data.requested_for_date, "depart_time": run["depart_time"]} if run else None,
    }


class TransportChangeInput(BaseModel):
    requested_for_date: str
    requested_for_time_label: Optional[str] = None
    start_time: Optional[str] = None


async def _open_transport_task(task_id: str, user: Optional[dict], source: str, action: str) -> dict:
    """The ride must exist and still be open. A step on a closed ride is
    refused (400, the transportation contract) and the refusal is recorded
    (SC-14)."""
    existing = await db.staff_tasks.find_one({"task_id": task_id, "category": "transportation"}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Transportation request not found")
    if existing["status"] not in OPEN_TASK_STATUSES:
        await task_lifecycle.record_refusal(
            existing, ride_actor(user, existing, source), ride_authority(user), action,
            f"request is already {existing['status']}: closed requests are not changed; nothing changed")
        raise HTTPException(status_code=400, detail=f"Request is already {existing['status']}")
    return existing


async def change_request(
    task_id: str, data: TransportChangeInput, *, source: str, actor: Optional[dict] = None,
    destination: Optional[str] = None, driver_id: Optional[str] = None, vehicle_id: Optional[str] = None,
) -> dict:
    """Releases the old run seat (if any), attempts to book the new time,
    preserves history via a receipt rather than pretending the original
    request never existed. Shared by Aria's change and the staff change.
    The lifecycle check runs before the seat is released, so a refused
    change touches nothing."""
    user, authority = actor, ride_authority(actor)
    existing = await _open_transport_task(task_id, user, source, "change")
    ra = ride_actor(user, existing, source)
    await task_lifecycle.check(task_id, ra, user, action="change", authority=authority)
    await release_task_from_run(existing.get("transport_run_id"), task_id)
    await release_legacy_slot(existing.get("transport_slot_id"))
    booking = await find_or_create_run(data.requested_for_date, data.start_time, destination, task_id, driver_id, vehicle_id)
    new_run = booking["run"]

    patch = {
        "requested_for_date": data.requested_for_date,
        "requested_for_time_label": data.requested_for_time_label,
        "transport_run_id": new_run["run_id"] if new_run else None,
        "transport_slot_id": None,
    }
    field, text = await booking_entry(new_run, requested_time=data.start_time,
                                      date=data.requested_for_date, changed=True)
    when = f"{data.requested_for_date} at {new_run['depart_time']}" if new_run else f"{data.requested_for_date}, no confirmed time"
    updated, receipt = await task_lifecycle.transition(
        task_id, ra, user, action="change", authority=authority, action_type="transportation_changed",
        status="created", result=f"Changed to {when}",
        build=lambda t, rid: (patch, [task_event(field, text=text, **who(ra, rid))]))
    await notify_department("transportation", "CAOS Care: transportation request changed", _booking_notify_body(updated, new_run),
                            **task_notice(updated, receipt["receipt_id"]))
    return {
        "task_id": task_id, "receipt_id": receipt["receipt_id"], "status": updated["status"],
        "booked": bool(new_run), "shared": booking["shared"],
        "run": {"date": data.requested_for_date, "depart_time": new_run["depart_time"]} if new_run else None,
    }


async def cancel_request(task_id: str, *, source: str, actor: Optional[dict] = None, reason: Optional[str] = None) -> dict:
    user, authority = actor, ride_authority(actor)
    existing = await _open_transport_task(task_id, user, source, "cancel")
    ra = ride_actor(user, existing, source)
    await task_lifecycle.check(task_id, ra, user, action="cancel", authority=authority)
    await release_task_from_run(existing.get("transport_run_id"), task_id)
    await release_legacy_slot(existing.get("transport_slot_id"))
    patch = {"status": "skipped", "completed_at": now_utc().isoformat()}
    if reason:
        patch["notes"] = reason
    _, receipt = await task_lifecycle.transition(
        task_id, ra, user, action="cancel", authority=authority, action_type="transportation_cancelled",
        status="cancelled", result=reason,
        build=lambda t, rid: (patch, close_events(t, "skipped", ra, rid, reason)))
    await notify_department(
        "transportation", "CAOS Care: transportation request cancelled",
        f"Cancelled — was {existing['requested_for_date']}\nPurpose: {existing['description']}\nRoom: {existing.get('room') or 'unknown'}"
        + (f"\nReason: {reason}" if reason else ""),
        **task_notice(existing, receipt["receipt_id"]),
    )
    return {"task_id": task_id, "receipt_id": receipt["receipt_id"], "status": "skipped"}


@router.post("/request/{task_id}/change")
async def change_transport_request(task_id: str, data: TransportChangeInput):
    """No auth, matching the request endpoint's trust model (Aria)."""
    return await change_request(task_id, data, source="aria_voice")


@router.post("/request/{task_id}/cancel")
async def cancel_transport_request(task_id: str):
    return await cancel_request(task_id, source="aria_voice")
