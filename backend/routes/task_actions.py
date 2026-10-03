"""The staff-request lifecycle actions, each run through
task_lifecycle.transition() so it is authorized, written with its history
entry, and receipted (SIM-0 / SC-13).

The field changes are the ones tasks.py and task_assignment.py made before
SC-13 - moved here unchanged so the HTTP routes and in-process callers
(demo reset, a future simulator) share one implementation.
"""
from datetime import datetime
from typing import Optional

from deps import db
from models import now_utc
from routes.actor_context import ActorContext
from routes.staff_scope import ADMIN_ROLES, acting_departments, acts_for
from routes.task_history import task_event
from routes.task_lifecycle import LifecycleError, chain_head, load, state_of, transition
from routes.receipts import create_receipt


def _ev(field: str, actor: ActorContext, rid: str, **kw) -> dict:
    return task_event(field, by=actor.actor_id, by_name=actor.name, receipt_id=rid, **kw)


async def assign(task_id: str, target_id: Optional[str], actor: ActorContext, user: dict):
    """Claim (assign to self), re-assign, or unassign. Admin/owner may assign
    anyone; a department member assigns within that department only."""
    task = await load(task_id)
    vis = task.get("visibility_role")
    if user.get("role") in ADMIN_ROLES:
        authority = f"admin_override:{user['role']}"
    elif acts_for(user, vis):
        authority = f"acts_for:{vis}"
    else:
        raise LifecycleError(403, "Not allowed to assign this task")
    target_id = (target_id or "").strip() or None
    if user.get("role") not in ADMIN_ROLES and target_id and target_id != user["user_id"]:
        tgt = await db.users.find_one({"user_id": target_id}, {"_id": 0, "role": 1, "department": 1})
        if not tgt or vis not in acting_departments(tgt):
            raise LifecycleError(403, "You can only assign within your own department")
    name = None
    if target_id:
        u = await db.users.find_one({"user_id": target_id}, {"_id": 0, "name": 1})
        if not u:
            raise LifecycleError(404, "Assignee not found")
        name = u.get("name")

    def build(t, rid):
        return ({"assigned_to": target_id, "assigned_name": name},
                [_ev("assigned_to", actor, rid, frm=t.get("assigned_to"), to=target_id, to_name=name)])
    return await transition(task_id, actor, user, action="assign", authority=authority, build=build,
                            action_type="task_assigned" if target_id else "task_unassigned", status="created")


async def acknowledge(task_id: str, actor: ActorContext, user: dict):
    def build(t, rid):
        if t.get("acknowledged_at"):
            return None
        return ({"acknowledged_by": actor.actor_id, "acknowledged_by_name": actor.name,
                 "acknowledged_at": now_utc().isoformat()}, [_ev("acknowledged", actor, rid)])
    return await transition(task_id, actor, user, action="acknowledge", build=build,
                            action_type="task_acknowledged", status="acknowledged")


async def start(task_id: str, actor: ActorContext, user: dict):
    def build(t, rid):
        patch = {"status": "in_progress", "started_at": now_utc().isoformat(),
                 "assigned_to": t.get("assigned_to") or actor.actor_id,
                 "assigned_name": t.get("assigned_name") or actor.name}
        entries = []
        if t.get("status") != "in_progress":
            entries.append(_ev("status", actor, rid, frm=t.get("status"), to="in_progress"))
        if not t.get("assigned_to"):
            entries.append(_ev("assigned_to", actor, rid, to=patch["assigned_to"], to_name=patch["assigned_name"]))
        return patch, entries
    return await transition(task_id, actor, user, action="start", build=build,
                            action_type="task_in_progress", status="in_progress")


async def add_note(task_id: str, text: Optional[str], actor: ActorContext, user: dict):
    """A progress note. An unchanged or empty note is not a change."""
    def build(t, rid):
        if not text or not text.strip() or text == (t.get("notes") or ""):
            return None
        return {"notes": text}, [_ev("note", actor, rid, text=text)]
    return await transition(task_id, actor, user, action="note", build=build,
                            action_type="task_note_added", status="created")


async def set_schedule(task_id: str, fields: dict, actor: ActorContext, user: dict):
    """The planned service window (requested_for_date / _time_label)."""
    def build(t, rid):
        changed = {k: v for k, v in fields.items() if v != t.get(k)}
        if not changed:
            return None
        text = " · ".join(str(v) for v in (fields.get("requested_for_date"),
                                           fields.get("requested_for_time_label")) if v) or "cleared"
        return changed, [_ev("scheduled", actor, rid, text=text)]
    return await transition(task_id, actor, user, action="schedule", build=build,
                            action_type="task_schedule_updated", status="created")


def _close_events(t: dict, to_status: str, notes: Optional[str], actor: ActorContext, rid: str) -> list:
    """A closing note is its own entry, so it never replaces earlier notes."""
    entries = []
    if (notes or "").strip():
        entries.append(_ev("note", actor, rid, text=notes.strip()))
    entries.append(_ev("status", actor, rid, frm=t.get("status"), to=to_status))
    return entries


async def complete(task_id: str, notes: Optional[str], actor: ActorContext, user: dict):
    def build(t, rid):
        finished = now_utc()
        duration = None
        if t.get("started_at"):
            try:
                started = datetime.fromisoformat(str(t["started_at"]).replace("Z", "+00:00"))
                duration = round((finished - started).total_seconds() / 60.0, 1)
            except Exception:
                pass
        patch = {"status": "completed", "completed_at": finished.isoformat(),
                 "completed_by": actor.actor_id, "completed_by_name": actor.name,
                 "duration_minutes": duration, "notes": notes or t.get("notes") or ""}
        if not t.get("started_at"):
            patch["started_at"] = finished.isoformat()
        return patch, _close_events(t, "completed", notes, actor, rid)
    return await transition(task_id, actor, user, action="complete", build=build,
                            action_type="task_completed", status="completed",
                            result=notes or "completed")


async def skip(task_id: str, notes: Optional[str], actor: ActorContext, user: Optional[dict],
               authority: Optional[str] = None):
    def build(t, rid):
        return ({"status": "skipped", "completed_at": now_utc().isoformat(),
                 "completed_by": actor.actor_id, "completed_by_name": actor.name,
                 "notes": notes or t.get("notes") or ""},
                _close_events(t, "skipped", notes, actor, rid))
    return await transition(task_id, actor, user, action="skip", build=build, authority=authority,
                            action_type="task_cancelled", status="cancelled",
                            failure_reason=notes or "skipped")


async def delete(task_id: str, actor: ActorContext, user: dict) -> dict:
    """Admin-only removal. The receipt (with the state that was removed) is
    written first, so the deletion itself is never unrecorded."""
    if user.get("role") not in ADMIN_ROLES:
        raise LifecycleError(403, "Admin required")
    task = await load(task_id)
    head = await chain_head(task_id)
    receipt = await create_receipt(
        action_type="task_deleted", related_object_type="task", related_object_id=task_id,
        status="completed", resident_id=task.get("resident_id"), room=task.get("room"),
        assigned_role=task.get("visibility_role"), source="staff",
        provenance={**actor.receipt_fields(), "authority": f"admin_override:{user['role']}",
                    "parent_receipt_id": (head or {}).get("receipt_id"),
                    "correlation_id": (head or {}).get("correlation_id"),
                    "before_state": state_of(task), "result_label": "verified", "next_state": "deleted"})
    await db.staff_tasks.delete_one({"task_id": task_id})
    return receipt
