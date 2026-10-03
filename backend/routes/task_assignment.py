"""Explicit assignment for staff tasks / work orders - claim, re-assign,
unassign. Its own router on the same /tasks prefix (the pattern
task_detail.py and resident_requests.py already use) so tasks.py stays
under the file-size cap.

Assignment is a FIELD on the existing StaffTask, never a new status: the
directive's NEW -> ASSIGNED -> IN PROGRESS -> COMPLETED workflow maps onto
    (pending, assigned_to=None)
      -> (pending, assigned_to set)      [this endpoint]
      -> in_progress                     [POST /tasks/{id}/start]
      -> completed                       [POST /tasks/{id}/complete]
No new model, no new collection - the Operations Overview and audit trail
read the same StaffTask/Receipt records they already do.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_current_user
from routes import task_actions
from routes.actor_context import actor_from_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


class AssignInput(BaseModel):
    assigned_to: Optional[str] = None   # a user_id, or null / "" to unassign


def _iso(doc: dict) -> dict:
    for k in ("created_at", "started_at", "completed_at", "due_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.post("/{task_id}/assign")
async def assign_task(task_id: str, data: AssignInput, user=Depends(get_current_user)):
    """Claim (assign to self), re-assign, or unassign. Admin/owner may
    assign anyone. A department member may claim a task in their own
    department or hand it to a co-worker in that SAME department - never
    across the department boundary. Rules and receipt: task_actions.assign."""
    task, _ = await task_actions.assign(task_id, data.assigned_to, actor_from_user(user), user)
    return _iso(task)
