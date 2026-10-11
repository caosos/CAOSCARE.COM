"""Department board (owner review 2026-10-11, P1 Departments & staff).

One read over the canonical records for a department: who its members are,
what open work each named worker holds (and what nobody holds yet), each
request's dispatch trail (the task's own event_log: created, assigned,
acknowledged, started, notes), and the completed history with its receipts.
Nothing is written here; assign / acknowledge / start / complete stay on the
task routes, which authorize and receipt every step. This is a read model
over StaffTask + users + receipts, never a second source of truth
(ENGINEERING_CONTRACT decisions 10-12).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user
from routes.aria_operational_state import task_lifecycle
from routes.realtime_facility import today_facility_date
from routes.staff_scope import acts_for, members_query

router = APIRouter(prefix="/departments", tags=["departments"])
OPEN = ("pending", "in_progress")
CLOSED = ("completed", "skipped")


def _iso(v):
    return v if (v is None or isinstance(v, str)) else v.isoformat()


def _trail(task: dict) -> list:
    """The dispatch trail, oldest first: who did what, when (from event_log,
    each entry already carrying its receipt id)."""
    out = [{"at": _iso(task.get("created_at")), "field": "created", "by_name": None, "to_name": None,
            "text": {"aria_voice": "Aria (resident)", "kiosk_button": "room screen", "front_desk": "front desk",
                     "simulator": "simulator", "staff": "staff"}.get(task.get("source"), task.get("source"))}]
    for e in task.get("event_log") or []:
        out.append({"at": _iso(e.get("at")), "field": e.get("field"), "by_name": e.get("by_name"),
                    "to_name": e.get("to_name"), "text": e.get("text"), "to": e.get("to"), "receipt_id": e.get("receipt_id")})
    return out


def _row(t: dict, receipts: Optional[int] = None) -> dict:
    trail = _trail(t)
    return {
        "task_id": t["task_id"], "title": t.get("title"), "what": t.get("resident_words") or t.get("description") or t.get("title"),
        "resident_name": t.get("resident_name"), "room": t.get("room"), "priority": t.get("priority"),
        "status": t.get("status"), "lifecycle": task_lifecycle(t), "source": t.get("source"),
        "assigned_to": t.get("assigned_to"), "assigned_name": t.get("assigned_name"),
        "acknowledged_by_name": t.get("acknowledged_by_name"), "completed_by_name": t.get("completed_by_name"),
        "created_at": _iso(t.get("created_at")), "acknowledged_at": _iso(t.get("acknowledged_at")),
        "started_at": _iso(t.get("started_at")), "completed_at": _iso(t.get("completed_at")),
        "duration_minutes": t.get("duration_minutes"), "notes": t.get("notes"),
        "requested_for_date": t.get("requested_for_date"), "requested_for_time_label": t.get("requested_for_time_label"),
        "trail": trail, "last_event_at": trail[-1]["at"] if trail else None,
        "receipts_count": receipts,
    }


@router.get("/{slug}/board")
async def department_board(slug: str, completed_limit: int = 30, user=Depends(get_current_user)):
    """Members and roles, open work by named worker with its dispatch trail,
    and the completed history with receipts. Readable by owner/admin and by
    anyone who acts for the department (its staff; front desk for
    Administration). Others: 403."""
    if not acts_for(user, slug):
        raise HTTPException(status_code=403, detail="Not allowed to see this department's board")
    dept = await db.departments.find_one({"slug": slug}, {"_id": 0})
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    members = await db.users.find(members_query(slug), {"_id": 0, "user_id": 1, "name": 1, "role": 1, "department": 1}).sort("name", 1).to_list(200)
    open_rows = await db.staff_tasks.find({"visibility_role": slug, "status": {"$in": list(OPEN)}}, {"_id": 0}).sort("created_at", 1).to_list(500)
    closed = await db.staff_tasks.find({"visibility_role": slug, "status": {"$in": list(CLOSED)}}, {"_id": 0}).sort("completed_at", -1).to_list(max(1, min(completed_limit, 200)))
    ids = [t["task_id"] for t in closed]
    counts = {}
    if ids:
        async for g in db.receipts.aggregate([{"$match": {"related_object_id": {"$in": ids}}}, {"$group": {"_id": "$related_object_id", "n": {"$sum": 1}}}]):
            counts[g["_id"]] = g["n"]
    work = [_row(t) for t in open_rows]
    history = [_row(t, counts.get(t["task_id"], 0)) for t in closed]

    by_worker = [{"user_id": None, "name": "Unassigned", "role": None, "work": [r for r in work if not r["assigned_to"]]}]
    seen = set()
    for m in members:
        seen.add(m["user_id"])
        by_worker.append({**m, "work": [r for r in work if r["assigned_to"] == m["user_id"]]})
    for r in work:                       # an assignee who is not a member (admin override) still shows up by name
        if r["assigned_to"] and r["assigned_to"] not in seen:
            seen.add(r["assigned_to"])
            by_worker.append({"user_id": r["assigned_to"], "name": r["assigned_name"] or r["assigned_to"], "role": None,
                              "not_member": True, "work": [x for x in work if x["assigned_to"] == r["assigned_to"]]})
    today = today_facility_date()
    return {
        "department": {"slug": dept["slug"], "label": dept.get("label"), "active": dept.get("active", True),
                       "description": dept.get("description"), "contact_email": dept.get("contact_email")},
        "members": members,
        "by_worker": by_worker,
        "history": history,
        "counts": {"open": len(work), "unassigned": sum(1 for r in work if not r["assigned_to"]),
                   "in_progress": sum(1 for r in work if r["status"] == "in_progress"),
                   "acknowledged": sum(1 for r in work if r["lifecycle"] == "acknowledged"),
                   "completed_today": sum(1 for r in history if (r["completed_at"] or "")[:10] == today and r["status"] == "completed"),
                   "closed_shown": len(history)},
        "can_assign": acts_for(user, slug),
    }
