"""The one place a staff request changes state (SIM-0 / SC-13).

Every claim, acknowledge, start, note, schedule change, completion, skip
and delete on a StaffTask goes through `transition()`:

  1. load the task (404 if missing)
  2. decide the authority the actor acts under (403 if none, no write)
  3. find the request's receipt chain; a legacy task with no origin
     receipt is refused and the refusal itself is recorded (Michael D5)
  4. write the task fields + event_log entries in one update
     (task_history.update_task_with_history)
  5. append one receipt: actor, authority, before/after state read back
     from the database, parent receipt, workflow (correlation) id, next
     state. Never taken from the request body.

Origins (a new request) are recorded by `record_origin()` in the same
shape, so every later receipt can chain back to it. The HTTP routes in
tasks.py / task_assignment.py are thin wrappers over this module; an
in-process caller (demo reset, a future simulator) gets the same checks.

Mongo here is a standalone server (no multi-document transactions): the
task is written first and its receipt immediately after. Each event_log
entry carries its receipt_id, so a missing receipt is detectable.
"""
from typing import Callable, Optional

from fastapi import HTTPException

from deps import db
from models import uid
from routes.actor_context import ActorContext
from routes.receipts import create_receipt
from routes.staff_scope import ADMIN_ROLES, acts_for
from routes.task_history import update_task_with_history

STATE_KEYS = ("status", "assigned_to", "acknowledged_by", "started_at", "completed_at",
              "requested_for_date", "requested_for_time_label")
_SOURCE_BY_CHANNEL = {"staff_ui": "staff", "front_desk": "front_desk", "system": "system",
                      "aria_voice": "aria_voice", "kiosk_button": "kiosk_button"}


class LifecycleError(HTTPException):
    """A refused transition. An HTTPException so the thin routes need no
    translation; in-process callers catch it like any HTTPException."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


def state_of(task: dict) -> dict:
    return {k: task.get(k) for k in STATE_KEYS}


def next_state(task: dict) -> str:
    status = task.get("status")
    if status in ("completed", "skipped"):
        return "closed"
    if status == "in_progress":
        return "in_progress"
    return "awaiting_start" if task.get("assigned_to") else "awaiting_claim"


def authority_for(task: dict, actor: ActorContext, user: Optional[dict]) -> Optional[str]:
    """The rule that lets this actor change this request, or None (Michael D2):
    admin/owner override, the assignee, a member of the request's department,
    or any staff member for general all-staff work."""
    if actor.actor_type == "system":
        return f"system:{actor.name}"
    if not user:
        return None
    role = user.get("role")
    if role in ADMIN_ROLES:
        return f"admin_override:{role}"
    if task.get("assigned_to") and task.get("assigned_to") == user.get("user_id"):
        return "assignee"
    vis = task.get("visibility_role")
    if acts_for(user, vis):
        return f"acts_for:{vis}"
    if vis == "all_staff" and role in ("staff", "front_desk"):
        return "all_staff"
    return None


def _chain_query(task_id: str) -> dict:
    """A request's receipt chain. A recorded refusal is evidence of an
    attempt, not part of the chain: it must never make a legacy request
    look like it has a recorded origin."""
    return {"related_object_type": "task", "related_object_id": task_id,
            "action_type": {"$not": {"$regex": "_refused$"}}}


async def chain_head(task_id: str) -> Optional[dict]:
    """The latest receipt for this request, or None for a legacy task."""
    return await db.receipts.find_one(_chain_query(task_id), {"_id": 0}, sort=[("created_at", -1)])


async def load(task_id: str) -> dict:
    task = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task:
        raise LifecycleError(404, "Task not found")
    return task


def _receipt_context(task: dict, actor: ActorContext) -> dict:
    return {"source": _SOURCE_BY_CHANNEL.get(actor.channel, "system"),
            "resident_id": task.get("resident_id"), "room": task.get("room"),
            "conversation_session_id": task.get("conversation_session_id"),
            "assigned_role": task.get("visibility_role")}


async def record_origin(task: dict, actor: ActorContext, *, action_type: str, authority: str,
                        provider_refs: Optional[list] = None) -> dict:
    """The first receipt of a request's chain. Its id is the workflow id."""
    rid = uid("rcpt")
    return await create_receipt(
        action_type=action_type, related_object_type="task", related_object_id=task["task_id"],
        assigned_user=task.get("assigned_to"), status="created", receipt_id=rid,
        provenance={**actor.receipt_fields(), "authority": authority, "correlation_id": rid,
                    "after_state": state_of(task), "result_label": "verified",
                    "provider_refs": list(provider_refs or []), "next_state": next_state(task)},
        **_receipt_context(task, actor))


async def _record_refusal(task: dict, actor: ActorContext, authority: str, action: str) -> None:
    await create_receipt(
        action_type=f"task_{action}_refused", related_object_type="task", related_object_id=task["task_id"],
        status="failed", failure_reason="no origin receipt: legacy request without provenance; "
                                        "transition refused, nothing changed",
        provenance={**actor.receipt_fields(), "authority": authority, "before_state": state_of(task),
                    "after_state": state_of(task), "result_label": "failed"},
        **_receipt_context(task, actor))


Build = Callable[[dict, str], Optional[tuple]]


async def transition(task_id: str, actor: ActorContext, user: Optional[dict], *, action: str,
                     action_type: str, status: str, build: Build, authority: Optional[str] = None,
                     result: Optional[str] = None, failure_reason: Optional[str] = None,
                     provider_refs: Optional[list] = None, require_chain: bool = True):
    """Apply one state change and record it. `build(task, receipt_id)` returns
    (set_fields, event_entries), or None when nothing would change (no write,
    no receipt). Returns (task_after, receipt_or_None)."""
    task = await load(task_id)
    auth = authority or authority_for(task, actor, user)
    if not auth:
        raise LifecycleError(403, "Not allowed to act on this request")
    head = await chain_head(task_id)
    if not head and require_chain:
        await _record_refusal(task, actor, auth, action)
        raise LifecycleError(409, "This request has no recorded origin, so it can't be changed here. "
                                  "Nothing was changed; the attempt was recorded.")
    rid = uid("rcpt")
    built = build(task, rid)
    if built is None:
        return task, None
    set_fields, entries = built
    correlation = (head or {}).get("correlation_id")
    if head and not correlation:   # chain started before SIM-0: its first receipt is the origin
        first = await db.receipts.find_one(_chain_query(task_id), {"_id": 0, "receipt_id": 1},
                                           sort=[("created_at", 1)])
        correlation = first["receipt_id"]
    await update_task_with_history(task_id, set_fields, entries)
    after = await load(task_id)
    receipt = await create_receipt(
        action_type=action_type, related_object_type="task", related_object_id=task_id,
        assigned_user=after.get("assigned_to"), status=status, result=result,
        failure_reason=failure_reason, receipt_id=rid,
        provenance={**actor.receipt_fields(), "authority": auth,
                    "parent_receipt_id": (head or {}).get("receipt_id"),
                    "correlation_id": correlation,
                    "before_state": state_of(task), "after_state": state_of(after),
                    "result_label": "verified", "provider_refs": list(provider_refs or []),
                    "next_state": next_state(after)},
        **_receipt_context(after, actor))
    return after, receipt


async def simulation_marker(resident_id: Optional[str]) -> dict:
    """StaffTask simulation provenance (ENGINEERING_CONTRACT decision 4), read
    only from the server-side resident record - never from a request body.
    A synthetic (demo) resident's work is marked so DEMO RESET can find it."""
    if not resident_id:
        return {}
    r = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0, "synthetic": 1})
    if r and r.get("synthetic"):
        return {"simulated": True, "simulation_scope": "demo_room"}
    return {}
