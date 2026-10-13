"""Complete operational record for one Communication & Requests item -
the task itself plus every receipt filed against it (each receipt already
carries created_at/acknowledged_at/completed_at - real timestamps, not
synthesized). No new history system; this is a read-shaped view over
StaffTask + Receipt, split out of tasks.py to keep it under the 300-line
cap.
"""
from fastapi import APIRouter, HTTPException, Depends

from deps import db
from routes.tasks import _iso, staff_visibility_query
from routes.request_delivery import delivery_for
from routes.work_context import get_department_user

router = APIRouter(prefix="/tasks", tags=["task-detail"])


@router.get("/{task_id}/detail")
async def get_task_detail(task_id: str, user=Depends(get_department_user)):
    # Same visibility as the task list: the list scope, or a task assigned to the caller (the list's mine_only path).
    # Checked in the query, before any task field or receipt is read; an invisible task answers exactly like a missing one.
    scope = staff_visibility_query(user)
    if user.get("_work_context_id"):
        q = {"task_id": task_id, **scope}
    else:
        q = {"task_id": task_id, **scope} if not scope else {"task_id": task_id, "$or": [scope, {"assigned_to": user["user_id"]}]}
    task = await db.staff_tasks.find_one(q, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    receipts = await db.receipts.find(
        {"related_object_type": "task", "related_object_id": task_id}, {"_id": 0},
    ).sort("created_at", 1).to_list(200)
    delivery = (await delivery_for([task_id]))[task_id]
    return {"task": _iso(task), "receipts": receipts, "delivery": delivery}
