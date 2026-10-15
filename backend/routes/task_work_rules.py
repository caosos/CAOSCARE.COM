"""What a worker may do next with a request, checked before anything is written.

Owner requirements (issue #168, 2026-10-14): acknowledge, claim, start and
complete are distinct; picking up a call is not fulfilling it; a worker does
not run overlapping work; completion needs an outcome; an administrative
override needs a reason and keeps the full history. Every refusal is
receipted (task_lifecycle.record_refusal) and returned as a clear 409/422 -
never an unexplained 500 ("Could not start", Michael 22:51 CDT: the database's
one-active-ticket index refused a second start and nothing caught it).

The rules:
  start     - the request is pending or already yours in progress; it is not
              claimed by someone else (reassign it first - recorded); and in a
              simulation run you hold no other in-progress request (one active
              ticket per worker, the same rule the simulator's workers follow).
  complete  - the request is in progress and you are working it, with a
              written outcome. An owner/admin may complete otherwise only with
              an override reason, which is recorded on the receipt.
  cancel    - needs a stated reason (resident no longer needs it, duplicate...).
"""
from typing import Optional

from deps import db
from routes.actor_context import ActorContext
from routes.staff_scope import ADMIN_ROLES
from routes import task_lifecycle
from routes.task_lifecycle import LifecycleError


async def _refuse(task: dict, actor: ActorContext, user: Optional[dict], action: str,
                  status: int, message: str) -> None:
    await task_lifecycle.record_refusal(task, actor, task_lifecycle.authority_for(task, actor, user),
                                        action, message)
    raise LifecycleError(status, message + " Nothing was changed; the attempt was recorded.")


def _authorized(task: dict, actor: ActorContext, user: Optional[dict]) -> None:
    """Authority first, exactly as task_lifecycle.check: a person with no
    authority over the request is told so (403) before any work rule."""
    if not task_lifecycle.authority_for(task, actor, user):
        raise LifecycleError(403, "Not allowed to act on this request")


def _who(task: dict) -> str:
    return task.get("assigned_name") or task.get("assigned_to") or "someone else"


def _what(task: dict) -> str:
    where = f" ({task['room']})" if task.get("room") else ""
    return f"“{task.get('title') or task['task_id']}”{where}"


async def check_start(task_id: str, actor: ActorContext, user: Optional[dict]) -> None:
    task = await task_lifecycle.load(task_id)
    _authorized(task, actor, user)
    if task.get("status") == "in_progress" and task.get("assigned_to") == actor.actor_id:
        return
    if task.get("status") not in ("pending", "in_progress"):
        return      # closed requests are refused by task_lifecycle.check
    holder = task.get("assigned_to")
    if task.get("status") == "in_progress" and holder != actor.actor_id:
        await _refuse(task, actor, user, "start", 409,
                      f"{_who(task)} is already working on this request.")
    if holder and holder != actor.actor_id:
        await _refuse(task, actor, user, "start", 409,
                      f"This request is claimed by {_who(task)}. Reassign it to yourself first "
                      "(the reassignment is recorded), or leave it with them.")
    run_id = task.get("simulation_run_id")
    if run_id:
        busy = await db.staff_tasks.find_one({
            "simulation_run_id": run_id, "assigned_to": actor.actor_id,
            "status": "in_progress", "task_id": {"$ne": task_id},
        }, {"_id": 0, "task_id": 1, "title": 1, "room": 1})
        if busy:
            await _refuse(task, actor, user, "start", 409,
                          f"You are already working on {_what(busy)}. Complete it, hand it off "
                          "or mark it blocked before starting another.")


async def check_complete(task_id: str, notes: Optional[str], actor: ActorContext,
                         user: Optional[dict], override_reason: Optional[str]) -> Optional[str]:
    """None when the completion is ordinary; the override reason when an
    owner/admin completes outside the normal flow. Refuses otherwise."""
    task = await task_lifecycle.load(task_id)
    _authorized(task, actor, user)
    if task.get("status") not in ("pending", "in_progress"):
        return None   # closed: task_lifecycle.check refuses and records it
    if not (notes or "").strip():
        await _refuse(task, actor, user, "complete", 422,
                      "Write what was done (the outcome) before completing this request.")
    working = task.get("status") == "in_progress" and task.get("assigned_to") == actor.actor_id
    if working:
        return None
    reason = (override_reason or "").strip()
    if (user or {}).get("role") in ADMIN_ROLES and reason:
        return reason
    if task.get("status") == "pending":
        await _refuse(task, actor, user, "complete", 409,
                      "This request has not been started. Start it first; picking up or "
                      "acknowledging a request is not completing it.")
    await _refuse(task, actor, user, "complete", 409,
                  f"{_who(task)} is working on this request; only they can complete it "
                  "(an owner/admin may override with a recorded reason).")
    return None


async def check_cancel(task_id: str, notes: Optional[str], actor: ActorContext,
                       user: Optional[dict]) -> None:
    task = await task_lifecycle.load(task_id)
    _authorized(task, actor, user)
    if task.get("status") in ("pending", "in_progress") and not (notes or "").strip():
        await _refuse(task, actor, user, "cancel", 422,
                      "Give the reason for cancelling (for example: resident no longer needs "
                      "help, duplicate request).")


# Assignment outcomes (#168: reassignment and handoff are distinct outcomes):
#   claim     - nobody held it; you take it                 -> task_assigned
#   assign    - nobody held it; given to a named worker     -> task_assigned
#   reassign  - waiting, held by one worker, moved to another -> task_reassigned  (reason)
#   release   - waiting, held by one worker, back to the queue -> task_unassigned (reason)
#   handoff   - in progress, passed to another worker or back to the queue
#               -> task_handed_off (reason); it waits until the new holder starts it
ASSIGN_ACTION = {"claim": "task_assigned", "assign": "task_assigned", "reassign": "task_reassigned",
                 "release": "task_unassigned", "handoff": "task_handed_off"}
_ASK = {"reassign": "Say why it is being moved to someone else.",
        "release": "Say why it is going back to the queue.",
        "handoff": "Say why the work is being handed off and what is left to do."}


def assignment_kind(task: dict, target_id: Optional[str], actor_id: str) -> Optional[str]:
    prev = task.get("assigned_to")
    if prev == target_id:
        return None
    if task.get("status") == "in_progress":
        return "handoff"
    if not prev:
        return "claim" if target_id == actor_id else "assign"
    return "reassign" if target_id else "release"


async def check_assign(task_id: str, target_id: Optional[str], reason: Optional[str],
                       actor: ActorContext, user: Optional[dict]) -> Optional[str]:
    """The kind of assignment change, refusing (422) a reassignment, release or
    handoff that does not say why."""
    task = await task_lifecycle.load(task_id)
    kind = assignment_kind(task, target_id, actor.actor_id)
    if kind in _ASK and task.get("status") in ("pending", "in_progress") and not (reason or "").strip():
        await _refuse(task, actor, user, "assign", 422, _ASK[kind])
    return kind
