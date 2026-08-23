"""Complete operational record for one Communication & Requests item -
the task itself plus every receipt filed against it (each receipt already
carries created_at/acknowledged_at/completed_at - real timestamps, not
synthesized). No new history system; this is a read-shaped view over
StaffTask + Receipt, split out of tasks.py to keep it under the 300-line
cap.
"""
from fastapi import APIRouter, HTTPException, Depends

from deps import db, get_current_user
from routes.tasks import _iso

router = APIRouter(prefix="/tasks", tags=["task-detail"])


@router.get("/{task_id}/detail")
async def get_task_detail(task_id: str, user=Depends(get_current_user)):
    task = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    receipts = await db.receipts.find(
        {"related_object_type": "task", "related_object_id": task_id}, {"_id": 0},
    ).sort("created_at", 1).to_list(200)
    return {"task": _iso(task), "receipts": receipts}
