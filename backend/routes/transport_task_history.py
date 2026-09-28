"""Transportation steps on the shared StaffTask history (routes/task_history.py).

A ride request is a StaffTask, so every ride step goes onto the same
append-only event_log every department uses - there is no separate ride
history. Status changes use the shared "status" field exactly like
tasks.py does (departed -> in_progress, completed, cancelled -> skipped),
and a cancel reason or completion note is a "note" entry, the same way
tasks.py records close-out notes. Ride facts that are not a status change
have their own fields:

    ride_booked      a driver + vehicle + pickup time is confirmed
    ride_not_booked  a pickup time was asked for but nothing was free
    ride_changed     the date/time was changed (text says the result)

`text` carries the plain detail (pickup time, driver, vehicle) that the
shared timeline shows.
"""
from typing import Optional

from deps import db
from routes.task_history import task_event


def actor_kwargs(actor: Optional[dict]) -> dict:
    """Staff user -> the user; no user -> the resident (Aria / room screen)."""
    if actor:
        return {"user": actor}
    return {"by": "resident", "by_name": "resident"}


async def ride_summary(run: dict) -> str:
    """"Pickup 08:45 on 2026-10-05 · Pete Nash, Van" from the run's own
    resources; names are looked up, never guessed."""
    parts = []
    if run.get("driver_id"):
        d = await db.transport_drivers.find_one({"driver_id": run["driver_id"]}, {"_id": 0, "name": 1})
        if d:
            parts.append(d["name"])
    if run.get("vehicle_id"):
        v = await db.transport_vehicles.find_one({"vehicle_id": run["vehicle_id"]}, {"_id": 0, "name": 1})
        if v:
            parts.append(v["name"])
    riders = len(run.get("resident_task_ids", []))
    text = f"Pickup {run['depart_time']} on {run['date']}"
    if parts:
        text += " · " + ", ".join(parts)
    if riders > 1:
        text += f" · shared ride ({riders} residents)"
    return text


async def booking_events(run: Optional[dict], actor: Optional[dict], *, requested_time: Optional[str],
                         date: str, changed: bool = False) -> list[dict]:
    """Events for one booking attempt (a new request, a staff assignment, or
    a change). A change always gets a ride_changed entry saying the result."""
    who = actor_kwargs(actor)
    summary = await ride_summary(run) if run else None
    if changed:
        return [task_event("ride_changed", text=summary or f"Moved to {date}, no confirmed pickup yet", **who)]
    if run:
        return [task_event("ride_booked", text=summary, **who)]
    if requested_time:
        return [task_event("ride_not_booked", text=f"No free driver and vehicle for {requested_time} on {date}", **who)]
    return []


def close_events(existing: dict, to_status: str, actor: Optional[dict], note: Optional[str]) -> list[dict]:
    """Same shape as tasks.py close-out: the note first, then the status."""
    who = actor_kwargs(actor)
    entries = []
    if note and note.strip():
        entries.append(task_event("note", text=note.strip(), **who))
    entries.append(task_event("status", frm=existing.get("status"), to=to_status, **who))
    return entries


def depart_events(existing: dict, actor: dict) -> list[dict]:
    """Same as tasks.py start: the status change, plus a claim entry when the
    request had no assignee (the driver who departs takes it)."""
    entries = [task_event("status", user=actor, frm=existing.get("status"), to="in_progress")]
    if not existing.get("assigned_to"):
        entries.append(task_event("assigned_to", user=actor, to=actor["user_id"], to_name=actor.get("name")))
    return entries
