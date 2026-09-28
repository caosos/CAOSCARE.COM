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

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, get_current_user
from routes.receipts import create_receipt
from routes.task_history import task_event, update_task_with_history
from routes.staff_scope import acting_departments, acts_for

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
    across the department boundary, so Housekeeping can't be handed
    Maintenance work by mistake."""
    existing = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    vis = existing.get("visibility_role")
    target_id = (data.assigned_to or "").strip() or None

    if not acts_for(user, vis):
        raise HTTPException(status_code=403, detail="Not allowed to assign this task")
    if user.get("role") not in ("owner", "admin") and target_id and target_id != user["user_id"]:
        tgt = await db.users.find_one({"user_id": target_id}, {"_id": 0, "role": 1, "department": 1})
        if not tgt or vis not in acting_departments(tgt):
            raise HTTPException(status_code=403, detail="You can only assign within your own department")

    assigned_name = None
    if target_id:
        u = await db.users.find_one({"user_id": target_id}, {"_id": 0, "name": 1})
        if not u:
            raise HTTPException(status_code=404, detail="Assignee not found")
        assigned_name = u.get("name")

    await update_task_with_history(
        task_id, {"assigned_to": target_id, "assigned_name": assigned_name},
        [task_event("assigned_to", user=user, frm=existing.get("assigned_to"), to=target_id,
                    to_name=assigned_name)],
    )
    await create_receipt(
        action_type="task_unassigned" if not target_id else "task_assigned",
        related_object_type="task", related_object_id=task_id,
        source="staff", requested_by=user["user_id"],
        assigned_user=target_id, assigned_role=vis,
    )
    return _iso(await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0}))
