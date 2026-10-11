"""Routing exceptions supervisor view (careops-routing-exceptions-001).

A read over the canonical records - open StaffTasks, the notifications linked
to them (request_delivery) and their receipts - listing the requests whose
handoff to a department is in trouble. Nothing is stored; recovery acts
through the existing paths (assign route; department re-notify below, which
writes ordinary notification records and a receipt).

Classes (a request can be in several):
  undelivered     - the department was not reached: notifications recorded
                    only (no provider) or none exist
  unassigned      - nobody owns it
  overdue         - a real due_at in the past, or its planned date has passed
  failed_handoff  - notification attempts were made and all failed/bounced,
                    or a lifecycle step on it was refused (a `task_*_refused`
                    receipt)
Simulated work is never "undelivered" (its notifications are recorded by
design). The currency classification (operations_currency) is kept: by
default only current and current-simulation work is listed; `include_review`
adds older records.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user
from routes.operations_currency import active_run, classify
from routes.ops_overview_util import age_seconds, task_is_overdue
from routes.realtime_facility import today_facility_date
from routes.request_delivery import delivery_for
from routes.staff_scope import ADMIN_ROLES, acting_departments, acts_for

router = APIRouter(prefix="/ops", tags=["ops"])
CLASSES = ("undelivered", "unassigned", "overdue", "failed_handoff")
OPEN = ("pending", "in_progress")


def _iso(v):
    return v if (v is None or isinstance(v, str)) else v.isoformat()


def _scope(user) -> dict:
    if user.get("role") in ADMIN_ROLES:
        return {}
    depts = sorted(acting_departments(user))
    if not depts:
        raise HTTPException(status_code=403, detail="Routing exceptions are visible to administrators and department staff")
    return {"visibility_role": {"$in": depts}}


async def _rows(user, include_review: bool, task_ids: Optional[list] = None) -> list:
    q = {"status": {"$in": list(OPEN)}, **_scope(user)}
    if task_ids is not None:
        q["task_id"] = {"$in": task_ids}
    tasks = await db.staff_tasks.find(q, {"_id": 0}).to_list(2000)
    ids = [t["task_id"] for t in tasks]
    deliv = await delivery_for(ids)
    refused, counts = {}, {}
    if ids:
        async for g in db.receipts.aggregate([{"$match": {"related_object_id": {"$in": ids}}},
                                              {"$group": {"_id": "$related_object_id", "n": {"$sum": 1},
                                                          "refused": {"$sum": {"$cond": [{"$regexMatch": {"input": "$action_type", "regex": "_refused$"}}, 1, 0]}}}}]):
            counts[g["_id"]], refused[g["_id"]] = g["n"], g["refused"]
    run = await active_run()
    rid = run["run_id"] if run else None
    now = datetime.now(timezone.utc)
    today = today_facility_date()
    out = []
    for t in tasks:
        cur = classify(t, "task", rid, now)
        if not include_review and cur["bucket"] in ("review", "sim_past"):
            continue
        d = deliv.get(t["task_id"]) or {"state": "none", "label": "", "reached": False, "attempts": 0}
        cls = []
        if not t.get("simulated") and d["state"] in ("not_sent", "none"):
            cls.append("undelivered")
        if not t.get("assigned_to"):
            cls.append("unassigned")
        planned_past = bool(t.get("requested_for_date")) and t["requested_for_date"] < today
        if task_is_overdue(t, now) or planned_past:
            cls.append("overdue")
        if d["state"] == "failed" or refused.get(t["task_id"], 0):
            cls.append("failed_handoff")
        if not cls:
            continue
        log = t.get("event_log") or []
        last = log[-1] if log else None
        out.append({
            "task_id": t["task_id"], "title": t.get("title"), "what": t.get("resident_words") or t.get("description") or t.get("title"),
            "department": t.get("visibility_role"), "resident_name": t.get("resident_name"), "room": t.get("room"),
            "priority": t.get("priority"), "status": t.get("status"), "simulated": bool(t.get("simulated")),
            "owner": t.get("assigned_name"), "assigned_to": t.get("assigned_to"),
            "created_at": _iso(t.get("created_at")), "age_seconds": age_seconds(t.get("created_at"), now) or 0,
            "due_at": _iso(t.get("due_at")), "requested_for_date": t.get("requested_for_date"),
            "latest_action": ({"at": _iso(last.get("at")), "field": last.get("field"), "by_name": last.get("by_name"), "text": last.get("text"), "to": last.get("to")}
                              if last else {"at": _iso(t.get("created_at")), "field": "created", "by_name": None, "text": t.get("source"), "to": None}),
            "delivery": d, "notification_attempts": d.get("attempts", 0),
            "times_asked": 1 + int(t.get("re_request_count") or 0), "escalation": {"re_request_count": int(t.get("re_request_count") or 0),
                                                                               "refused_steps": refused.get(t["task_id"], 0)},
            "receipts_count": counts.get(t["task_id"], 0), "currency": cur, "classes": cls,
        })
    out.sort(key=lambda r: ("failed_handoff" not in r["classes"], "undelivered" not in r["classes"], -r["age_seconds"]))
    return out


@router.get("/routing-exceptions")
async def routing_exceptions(kind: Optional[str] = None, department: Optional[str] = None,
                             include_review: bool = False, user=Depends(get_current_user)):
    if kind and kind not in CLASSES:
        raise HTTPException(status_code=422, detail=f"kind must be one of {', '.join(CLASSES)}")
    rows = await _rows(user, include_review)
    if department:
        rows = [r for r in rows if r["department"] == department]
    counts = {c: sum(1 for r in rows if c in r["classes"]) for c in CLASSES}
    items = [r for r in rows if not kind or kind in r["classes"]]
    return {"counts": counts, "total": len(rows), "items": items, "include_review": include_review, "kind": kind}


@router.get("/routing-exceptions/{task_id}")
async def routing_exception_detail(task_id: str, user=Depends(get_current_user)):
    rows = await _rows(user, True, [task_id])
    task = await db.staff_tasks.find_one({"task_id": task_id, **_scope(user)}, {"_id": 0, "task_id": 1})
    if not task:
        raise HTTPException(status_code=404, detail="Not found")
    receipts = await db.receipts.find({"related_object_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    notes = await db.notifications.find({"related_object_type": "task", "related_object_id": task_id},
                                        {"_id": 0, "to": 1, "route": 1, "status": 1, "created_at": 1, "channel": 1}).sort("created_at", 1).to_list(100)
    return {"exception": rows[0] if rows else None, "receipts": receipts, "notifications": notes}


@router.post("/routing-exceptions/{task_id}/renotify")
async def renotify(task_id: str, user=Depends(get_current_user)):
    """Send the department notification again through the normal path, for a
    request that was not reached. Same rule as acting on the request. Without a
    provider the new record is again 'recorded only' - said truthfully."""
    from routes.actor_context import actor_from_user
    from routes.notifications import notify_department, task_notice
    from routes.receipts import create_receipt
    t = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not t or t.get("status") not in OPEN:
        raise HTTPException(status_code=404, detail="Not found or already closed")
    if not acts_for(user, t.get("visibility_role")):
        raise HTTPException(status_code=403, detail="Not allowed to act on this request")
    before = (await delivery_for([task_id]))[task_id]
    actor = actor_from_user(user)
    rc = await create_receipt(action_type="department_renotified", related_object_type="task", related_object_id=task_id,
                              source="staff", resident_id=t.get("resident_id"), room=t.get("room"), assigned_role=t.get("visibility_role"),
                              status="completed", result=f"re-notified after delivery state '{before['state']}'",
                              provenance={**actor.receipt_fields(), "authority": f"acts_for:{t.get('visibility_role')}" if user.get("role") not in ADMIN_ROLES else f"admin_override:{user.get('role')}",
                                          "before_state": {"delivery": before["state"]}, "result_label": "verified"})
    records = await notify_department(t.get("visibility_role"), f"CAOS Care: reminder - open {t.get('category')} request",
                                      f"{t.get('resident_words') or t.get('description') or t.get('title')}\nRoom: {t.get('room') or 'unknown'}\n(Re-sent by {user.get('name')})",
                                      **task_notice(t, rc["receipt_id"]))
    after = (await delivery_for([task_id]))[task_id]
    return {"task_id": task_id, "receipt_id": rc["receipt_id"], "records": len(records), "delivery_before": before["state"], "delivery": after}
