"""Audit log export — the receipts for any HIPAA/compliance review.

Produces CSV exports of:
  • All alerts with full lifecycle (who pressed, who acknowledged, who resolved, duration, outcome)
  • All staff task completions (who did what, when, how long, notes)
  • All pager events bridged from the facility RF system
  • All medication reminder acknowledgements

Admins only. Date-ranged. Every row stamped with UTC timestamps.
"""
import csv
import io
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from deps import db, get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])


def _iso_range(start: Optional[str], end: Optional[str]) -> tuple[str, str]:
    """Return (start_iso, end_iso). If missing, default to last 30 days / now."""
    if not end:
        end_dt = datetime.now(timezone.utc)
    else:
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    if not start:
        start_dt = end_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = start_dt.replace(day=max(1, start_dt.day - 30))
    else:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return start_dt.isoformat(), end_dt.isoformat()


def _csv_response(rows: list[dict], columns: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: (r.get(c) if r.get(c) is not None else "") for c in columns})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _require_admin(user):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")


@router.get("/alerts.csv")
async def export_alerts(
    start: Optional[str] = Query(None, description="ISO start time"),
    end: Optional[str] = Query(None, description="ISO end time"),
    user=Depends(get_current_user),
):
    _require_admin(user)
    s, e = _iso_range(start, end)
    rows = await db.alerts.find(
        {"created_at": {"$gte": s, "$lte": e}}, {"_id": 0},
    ).sort("created_at", -1).to_list(10000)
    cols = [
        "alert_id", "created_at", "resident_id", "resident_name", "room", "zone",
        "severity", "status", "triggered_by", "message", "pendant_id", "frequency",
        "auto_voice", "press_count", "escalated", "escalation_level",
        "acknowledged_by", "acknowledged_at",
        "resolved_by", "resolved_at", "outcome", "close_notes",
    ]
    return _csv_response(rows, cols, f"caos-alerts-{s[:10]}-to-{e[:10]}.csv")


@router.get("/tasks.csv")
async def export_tasks(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    _require_admin(user)
    s, e = _iso_range(start, end)
    rows = await db.staff_tasks.find(
        {"created_at": {"$gte": s, "$lte": e}}, {"_id": 0},
    ).sort("created_at", -1).to_list(10000)
    cols = [
        "task_id", "created_at", "title", "category", "shift",
        "resident_name", "room", "assigned_name",
        "status", "started_at", "completed_at", "completed_by_name",
        "duration_minutes", "notes",
    ]
    return _csv_response(rows, cols, f"caos-tasks-{s[:10]}-to-{e[:10]}.csv")


@router.get("/pages.csv")
async def export_pages(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    _require_admin(user)
    s, e = _iso_range(start, end)
    rows = await db.pager_events.find(
        {"created_at": {"$gte": s, "$lte": e}}, {"_id": 0},
    ).sort("created_at", -1).to_list(10000)
    cols = [
        "page_id", "created_at", "source", "cap_code", "urgency",
        "resident_name", "room", "zone", "message",
    ]
    return _csv_response(rows, cols, f"caos-pages-{s[:10]}-to-{e[:10]}.csv")


@router.get("/medications.csv")
async def export_medications(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    _require_admin(user)
    s, e = _iso_range(start, end)
    acks = await db.med_ack.find(
        {"at": {"$gte": s, "$lte": e}}, {"_id": 0},
    ).sort("at", -1).to_list(10000)
    # enrich with reminder info
    out = []
    for a in acks:
        rem = await db.med_reminders.find_one({"reminder_id": a["reminder_id"]}, {"_id": 0}) or {}
        out.append({
            "ack_id": a.get("ack_id"),
            "day": a.get("day"),
            "at": a.get("at"),
            "reminder_id": a.get("reminder_id"),
            "title": rem.get("title"),
            "time_hhmm": rem.get("time_hhmm"),
            "resident_name": rem.get("resident_name"),
            "room": rem.get("room"),
            "dose_notes": rem.get("dose_notes"),
        })
    cols = ["at", "day", "time_hhmm", "resident_name", "room", "title", "dose_notes", "reminder_id", "ack_id"]
    return _csv_response(out, cols, f"caos-medications-{s[:10]}-to-{e[:10]}.csv")


@router.get("/summary")
async def audit_summary(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """Quick counts for the admin UI — what's in each export file."""
    _require_admin(user)
    s, e = _iso_range(start, end)
    alerts = await db.alerts.count_documents({"created_at": {"$gte": s, "$lte": e}})
    tasks = await db.staff_tasks.count_documents({"created_at": {"$gte": s, "$lte": e}})
    pages = await db.pager_events.count_documents({"created_at": {"$gte": s, "$lte": e}})
    meds = await db.med_ack.count_documents({"at": {"$gte": s, "$lte": e}})
    return {"start": s, "end": e, "alerts": alerts, "tasks": tasks, "pages": pages, "medications": meds}
