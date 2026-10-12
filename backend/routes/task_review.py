"""Nursing exception lifecycle (careops-nursing-exception-lifecycle-001).

Two steps the request lifecycle lacked, both on the canonical StaffTask +
receipt path (task_lifecycle.transition):

  escalate  - "I can't complete this": the worker (assignee, a member of the
              request's department, or admin) gives a reason. The request
              stays OPEN, goes back to pending and unassigned so it is not
              left sitting with someone who cannot do it, and is flagged
              needs_review for a supervisor. Receipt `task_escalated`.
  review    - an owner/admin (the supervisor tier; there is no department
              lead role yet) records that they looked at it, with a note.
              Clears the flag. Receipt `task_reviewed`. The supervisor then
              uses the existing steps: assign it to someone else, or cancel
              it with a reason.

  inspect   - (careops-housekeeping-inspection-001) an owner/admin inspects a
              COMPLETED request: "pass" records the inspection (receipt
              `task_inspected`, the request stays completed); "return" sends the
              same request back for correction through the existing receipted
              reopen (reason required), and records it as an inspection return.

Cancelling with a reason (skip) and reassignment (assign) already existed and
are not duplicated here.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import get_current_user
from models import now_utc
from routes.actor_context import ActorContext, actor_from_user
from routes.staff_scope import ADMIN_ROLES
from routes.task_history import task_event
from routes import task_actions
from routes.task_lifecycle import LifecycleError, check, transition

router = APIRouter(prefix="/tasks", tags=["tasks"])


class ReasonInput(BaseModel):
    reason: str = Field("", max_length=500)


class InspectInput(BaseModel):
    result: str = Field(..., pattern="^(pass|return)$")
    note: str = Field("", max_length=500)


def _ev(field: str, actor: ActorContext, rid: str, **kw) -> dict:
    return task_event(field, by=actor.actor_id, by_name=actor.name, receipt_id=rid, **kw)


async def escalate(task_id: str, reason: Optional[str], actor: ActorContext, user: dict):
    reason = (reason or "").strip()
    if not reason:
        raise LifecycleError(422, "Say why it can't be completed")

    def build(t, rid):
        if t.get("needs_review") and (t.get("escalation_reason") or "") == reason and not t.get("assigned_to"):
            return None   # same report again: nothing changes
        patch = {"status": "pending", "assigned_to": None, "assigned_name": None, "started_at": None,
                 "needs_review": True, "escalation_reason": reason,
                 "escalated_at": now_utc().isoformat(), "escalated_by_name": actor.name,
                 "escalation_count": int(t.get("escalation_count") or 0) + 1, "notes": reason}
        entries = [_ev("note", actor, rid, text=reason),
                   _ev("escalated", actor, rid, text=reason)]
        if t.get("assigned_to"):
            entries.append(_ev("assigned_to", actor, rid, frm=t.get("assigned_to"), to=None))
        if t.get("status") != "pending":
            entries.append(_ev("status", actor, rid, frm=t.get("status"), to="pending", text=reason))
        return patch, entries
    return await transition(task_id, actor, user, action="escalate", build=build,
                            action_type="task_escalated", status="created", result=reason)


async def review(task_id: str, note: Optional[str], actor: ActorContext, user: dict):
    if (user or {}).get("role") not in ADMIN_ROLES:
        raise LifecycleError(403, "Only a supervisor (owner or admin) can review an escalated request")
    note = (note or "").strip()
    if not note:
        raise LifecycleError(422, "Add a review note (what you decided)")

    def build(t, rid):
        if not t.get("needs_review"):
            return None
        return ({"needs_review": False, "reviewed_at": now_utc().isoformat(),
                 "reviewed_by_name": actor.name, "review_note": note, "notes": note},
                [_ev("note", actor, rid, text=note), _ev("reviewed", actor, rid, text=note)])
    after, receipt = await transition(task_id, actor, user, action="review", build=build,
                                      action_type="task_reviewed", status="created", result=note)
    if receipt is None:
        raise LifecycleError(409, "This request is not waiting for review. Nothing was changed.")
    return after, receipt


async def inspect(task_id: str, result: str, note: Optional[str], actor: ActorContext, user: dict):
    if (user or {}).get("role") not in ADMIN_ROLES:
        raise LifecycleError(403, "Only a supervisor (owner or admin) can inspect completed work")
    note = (note or "").strip()
    task, _auth, _ = await check(task_id, actor, user, action="inspect", allow_closed=True)
    if task.get("status") != "completed":
        raise LifecycleError(409, "Only completed work can be inspected. Nothing was changed.")
    if result == "return":
        if not note:
            raise LifecycleError(422, "Say what needs correcting")
        await task_actions.reopen(task_id, f"Returned after inspection: {note}", actor, user)

        def mark(t, rid):
            return ({"inspection_result": "returned", "inspected_at": now_utc().isoformat(),
                     "inspected_by_name": actor.name, "inspection_note": note},
                    [_ev("inspected", actor, rid, text=f"Returned for correction: {note}")])
        return await transition(task_id, actor, user, action="inspect", build=mark,
                                 action_type="task_inspection_returned", status="created", result=note)

    def build(t, rid):
        if t.get("inspection_result") == "passed":
            return None   # already passed: nothing changes
        return ({"inspection_result": "passed", "inspected_at": now_utc().isoformat(),
                 "inspected_by_name": actor.name, "inspection_note": note or None},
                [_ev("inspected", actor, rid, text=f"Passed{': ' + note if note else ''}")])
    return await transition(task_id, actor, user, action="inspect", build=build, allow_closed=True,
                            action_type="task_inspected", status="completed", result=note or "passed")


@router.post("/{task_id}/inspect")
async def inspect_route(task_id: str, body: InspectInput, user: dict = Depends(get_current_user)):
    task, receipt = await inspect(task_id, body.result, body.note, actor_from_user(user), user)
    return {"ok": True, "task_id": task["task_id"], "status": task["status"],
            "inspection_result": task.get("inspection_result"), "receipt_id": (receipt or {}).get("receipt_id")}


@router.post("/{task_id}/escalate")
async def escalate_route(task_id: str, body: ReasonInput, user: dict = Depends(get_current_user)):
    task, receipt = await escalate(task_id, body.reason, actor_from_user(user), user)
    return {"ok": True, "task_id": task["task_id"], "needs_review": task.get("needs_review"),
            "receipt_id": (receipt or {}).get("receipt_id")}


@router.post("/{task_id}/review")
async def review_route(task_id: str, body: ReasonInput, user: dict = Depends(get_current_user)):
    task, receipt = await review(task_id, body.reason, actor_from_user(user), user)
    return {"ok": True, "task_id": task["task_id"], "needs_review": task.get("needs_review"),
            "receipt_id": receipt["receipt_id"]}
