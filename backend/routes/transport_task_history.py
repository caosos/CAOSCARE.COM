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

Every ride step is a task_lifecycle transition (SIM-0 / SC-15): the entries
built here carry the actor and the id of the receipt that records them.
"""
from typing import Optional

from deps import db
from routes.actor_context import ActorContext, actor_from_user, actor_resident_claim
from routes.staff_scope import ADMIN_ROLES
from routes.task_history import task_event


def ride_actor(user: Optional[dict], task: Optional[dict], source: str) -> ActorContext:
    """Staff user -> that user (front desk channel for staff-entered rides).
    No user -> the room the request came through: a claim, not a verified
    identity (D3); a synthetic demo resident stays marked synthetic."""
    if user:
        return actor_from_user(user, channel="front_desk" if source == "front_desk" else "staff_ui")
    task = task or {}
    return actor_resident_claim(task.get("resident_id"), task.get("room"), source,
                                synthetic=bool(task.get("simulated")))


def ride_authority(user: Optional[dict]) -> str:
    """The rule a ride step acts under. The routes already gate who may call
    them (front desk/admin, transportation operators); this names it."""
    if not user:
        return "public_resident_bus"
    role = user.get("role")
    if role in ADMIN_ROLES:
        return f"admin_override:{role}"
    if role == "front_desk":
        return "front_desk_transport"
    return f"acts_for:{user.get('department') or 'transportation'}"


def who(actor: ActorContext, rid: str) -> dict:
    return {"by": actor.actor_id, "by_name": actor.name or "resident", "receipt_id": rid}


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


async def booking_entry(run: Optional[dict], *, requested_time: Optional[str], date: str,
                        changed: bool = False) -> Optional[tuple]:
    """(field, text) for one booking attempt (a new request, a staff
    assignment, or a change), or None when there is nothing to record. A
    change always records what it changed to."""
    summary = await ride_summary(run) if run else None
    if changed:
        return "ride_changed", summary or f"Moved to {date}, no confirmed pickup yet"
    if run:
        return "ride_booked", summary
    if requested_time:
        return "ride_not_booked", f"No free driver and vehicle for {requested_time} on {date}"
    return None


def close_events(existing: dict, to_status: str, actor: ActorContext, rid: str,
                 note: Optional[str]) -> list[dict]:
    """Same shape as the lifecycle close-out: the note first, then the status."""
    entries = []
    if note and note.strip():
        entries.append(task_event("note", text=note.strip(), **who(actor, rid)))
    entries.append(task_event("status", frm=existing.get("status"), to=to_status, **who(actor, rid)))
    return entries


def depart_events(existing: dict, actor: ActorContext, rid: str) -> list[dict]:
    """Same as the lifecycle start: the status change, plus a claim entry when
    the request had no assignee (the driver who departs takes it)."""
    entries = [task_event("status", frm=existing.get("status"), to="in_progress", **who(actor, rid))]
    if not existing.get("assigned_to"):
        entries.append(task_event("assigned_to", to=actor.actor_id, to_name=actor.name, **who(actor, rid)))
    return entries
