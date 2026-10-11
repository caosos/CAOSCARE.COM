"""A ride for a planned request (careops-therapy-transport-link-001).

A planned request in any department (therapy appointments first) can need a
ride. "Ride needed" creates or attaches EXACTLY ONE ordinary transportation
request through the same core the front desk uses (routes/transportation.py:
submit_transport_request / change_request / cancel_request): the ride is a
normal StaffTask in the transportation department, booked by the one engine,
visible to transportation staff and to the resident like any other ride. The
two records point at each other (`linked_ride_task_id` on the appointment,
`linked_appointment_task_id` on the ride) and the link is receipted on the
appointment's chain (`task_ride_requested`, provider_refs = the ride's task id
and origin receipt). Nothing is copied; there is no second store.

Idempotent: while the linked ride is open, asking again returns it. An open
ride for the same resident on the same date is attached (the core records a
re-request), never duplicated. Once the ride is cancelled, a new ask may
create a new one.

Follow-through: a change of the appointment's planned window changes the
ride's date/time (`transportation_changed`); cancelling the appointment
cancels the ride with the reason (`transportation_cancelled`). Both run
through the ride's own lifecycle, so the ride's history and receipts record
them. Completing the appointment leaves the ride alone (its depart/complete
steps belong to transportation).
"""
from typing import Optional

from fastapi import HTTPException

from deps import db
from routes.actor_context import ActorContext
from routes.task_history import task_event, update_task_with_history
from routes.task_lifecycle import (CLOSED_STATUSES, LifecycleError, authority_for, check, load,
                                   transition)

# routes.transportation (and the voice-context module that imports it) import
# routes.tasks for _resolve_denorms, and routes.tasks imports this module for
# its hooks, so the transportation modules are imported inside the functions
# that need them, not at module load.


def _core():
    from routes import transportation as t
    return t


async def ride_summary(ride: dict) -> dict:
    """What the appointment's holder may know about the linked ride: its own
    status and the real run facts - the same facts the resident's status
    view reports, never a guess."""
    from routes.transportation_voice_context import run_view_for_task
    _, run_view = await run_view_for_task(ride)
    return {
        "task_id": ride["task_id"], "status": ride["status"],
        "booked": bool(ride.get("transport_run_id")) and ride["status"] != "skipped",
        "requested_for_date": ride.get("requested_for_date"),
        "requested_for_time_label": ride.get("requested_for_time_label"),
        "run": run_view,
        "cancel_reason": ride.get("notes") if ride["status"] == "skipped" else None,
    }


async def _linked_ride(task: dict) -> Optional[dict]:
    rid = task.get("linked_ride_task_id")
    return await db.staff_tasks.find_one({"task_id": rid, "category": "transportation"}, {"_id": 0}) if rid else None


async def get_ride(task_id: str, actor: ActorContext, user: dict) -> dict:
    task = await load(task_id)
    if not authority_for(task, actor, user):
        raise LifecycleError(403, "Not allowed to see this request")
    ride = await _linked_ride(task)
    return {"linked": bool(ride), "ride": await ride_summary(ride) if ride else None}


async def request_ride(task_id: str, actor: ActorContext, user: dict) -> dict:
    """Create-or-attach exactly one ride for this planned request."""
    task, _auth, _head = await check(task_id, actor, user, action="ride")
    if not task.get("resident_id") or not task.get("requested_for_date"):
        raise LifecycleError(422, "Plan the appointment first (resident and date) before requesting a ride")
    linked = await _linked_ride(task)
    if linked and linked["status"] not in CLOSED_STATUSES:
        return {"task_id": linked["task_id"], "already_linked": True, "attached_existing": False,
                "booked": bool(linked.get("transport_run_id")), "ride": await ride_summary(linked)}
    resident = await db.residents.find_one({"resident_id": task["resident_id"]}, {"_id": 0, "room": 1})
    if not resident:
        raise LifecycleError(404, "Resident not found")
    core = _core()
    req = core.TransportRequestInput(
        resident_id=task["resident_id"], room=task.get("room") or resident.get("room"),
        purpose=f"{task.get('title') or 'Appointment'} ({(task.get('visibility_role') or 'staff').replace('_', ' ')} appointment)",
        requested_for_date=task["requested_for_date"], requested_for_time_label=task.get("requested_for_time_label"),
        priority=task.get("priority") or "normal", source="front_desk",
    )
    res = await core.submit_transport_request(req, actor=user)
    ride_id = res["task_id"]
    when = " ".join(x for x in (task.get("requested_for_time_label"), task["requested_for_date"]) if x)
    text = f"{'Attached to existing' if res.get('duplicate') else 'Requested'} ride {ride_id} for {when}"

    def build(t, rid):
        return ({"linked_ride_task_id": ride_id},
                [task_event("ride_requested", by=actor.actor_id, by_name=actor.name, receipt_id=rid, to=ride_id, text=text)])
    _after, receipt = await transition(task_id, actor, user, action="ride", build=build,
                                       action_type="task_ride_requested", status="created", result=text,
                                       provider_refs=[ride_id, res["receipt_id"]])
    await update_task_with_history(
        ride_id, {"linked_appointment_task_id": task_id},
        [task_event("linked_appointment", by=actor.actor_id, by_name=actor.name, receipt_id=receipt["receipt_id"],
                    to=task_id, text=f"Ride for: {task.get('title')}")])
    ride = await load(ride_id)
    return {"task_id": ride_id, "already_linked": False, "attached_existing": bool(res.get("duplicate")),
            "booked": bool(res.get("booked")), "receipt_id": receipt["receipt_id"], "ride": await ride_summary(ride)}


async def sync_schedule(task: dict, user: dict) -> Optional[dict]:
    """The appointment's planned window changed: move the linked open ride
    with it (the ride's own change step, receipted). Returns the change
    result, None when there is no open linked ride or nothing differs."""
    ride = await _linked_ride(task)
    if not ride or ride["status"] in CLOSED_STATUSES:
        return None
    if ride.get("requested_for_date") == task.get("requested_for_date") and \
            ride.get("requested_for_time_label") == task.get("requested_for_time_label"):
        return None
    if not task.get("requested_for_date"):
        return None   # window cleared: the ride keeps its date until someone cancels or changes it explicitly
    try:
        core = _core()
        return await core.change_request(ride["task_id"], core.TransportChangeInput(
            requested_for_date=task["requested_for_date"], requested_for_time_label=task.get("requested_for_time_label")),
            source="front_desk", actor=user)
    except HTTPException:
        return None   # the ride's own refusal is recorded on the ride; the appointment change stands


async def cancel_linked(task: dict, user: dict, reason: Optional[str]) -> Optional[dict]:
    """The appointment was cancelled: cancel its open linked ride with the reason."""
    ride = await _linked_ride(task)
    if not ride or ride["status"] in CLOSED_STATUSES:
        return None
    try:
        return await _core().cancel_request(ride["task_id"], source="front_desk", actor=user,
                                    reason=f"Appointment cancelled: {reason or 'no reason given'}")
    except HTTPException:
        return None
