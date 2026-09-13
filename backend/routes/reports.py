"""Operations reporting - read-only aggregations over the operational truth
that already exists (staff_tasks, receipts, alerts). No reporting database,
no duplicate records. Shares the StaffTask predicates in
routes/ops_overview_util.py with the Operations Overview so "open" /
"overdue" / "closed today" mean exactly one thing across both.

Reports
  GET /reports/daily-exceptions   - what needs attention today (current-state
                                    exceptions + failed/cancelled actions
                                    filed on `date`)
  GET /reports/weekly-workload    - per-department factual task volumes over
                                    a window
Both accept `format=csv` and return the SAME filtered rows as the JSON.
Admin/owner only.
"""
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from deps import db, require_admin
from routes.realtime_facility import today_facility_date, FACILITY_TZ
from routes.ops_overview_util import (
    EPOCH, parse_dt, age_seconds, local_date, dept_label, short_duration,
    task_is_open, task_is_unassigned, task_is_overdue,
)

router = APIRouter(prefix="/reports", tags=["reports"])

STALE_HOURS = 72

DAILY_CAVEATS = [
    "'Overdue' means a real due_at is in the past. Work that is merely old is "
    "reported as age, never as overdue.",
    "Open resident-assistance events are read live from the alert collection; "
    "those over 72h are likely stale RF/pendant test activations, not a live queue.",
    "'Failed / cancelled action' rows come from receipts whose status is "
    "failed or cancelled - coverage is only as complete as the receipt system.",
]
WEEKLY_CAVEATS = [
    "Counts are factual task volumes - not productivity, quality, or staff "
    "performance measures.",
    "by_staff is an assignment count only; an unassigned or later-reassigned "
    "task is not attributed to anyone.",
    "still_open / assigned_open / unassigned_open are a live snapshot; "
    "created / completed are within the window.",
]

DAILY_COLUMNS = [
    "kind", "ref_type", "ref_id", "title", "department_slug", "department_label",
    "room", "resident_id", "resident_name", "owner", "status", "priority",
    "severity", "opened_at", "age_hours", "due_at", "overdue", "reason", "result", "receipt_id",
]
WEEKLY_COLUMNS = [
    "department_slug", "department_label", "created", "completed", "still_open",
    "assigned_open", "unassigned_open", "oldest_open_ref_id", "oldest_open_age_hours",
    "staff_breakdown",
]


def _humanize(s) -> str:
    t = str(s or "").replace("_", " ").strip()
    return t[:1].upper() + t[1:] if t else "-"


def _csv_response(rows: list[dict], columns: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _load(now: datetime):
    departments = await db.departments.find({}, {"_id": 0}).sort("label", 1).to_list(100)
    tasks = await db.staff_tasks.find({}, {"_id": 0}).to_list(6000)
    return departments, {d["slug"]: d for d in departments}, tasks


# ======================= 1. DAILY OPERATIONAL EXCEPTIONS =======================
@router.get("/daily-exceptions")
async def daily_exceptions(
    date: Optional[str] = None,
    department: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    user=Depends(require_admin),
):
    day = date or today_facility_date()
    now = datetime.now(timezone.utc)
    _, by_slug, tasks = await _load(now)

    open_alerts = await db.alerts.find(
        {"status": {"$in": ["active", "acknowledged"]}}, {"_id": 0},
    ).sort("created_at", 1).to_list(2000)
    failed_receipts = [
        r for r in await db.receipts.find(
            {"status": {"$in": ["failed", "cancelled"]}}, {"_id": 0},
        ).sort("created_at", -1).to_list(1000)
        if local_date(r.get("created_at")) == day
    ]

    rows: list[dict] = []

    def push(kind, ref_type, ref_id, *, rank, title, dept_slug, dept_lbl, reason, opened_at,
             room=None, resident_id=None, resident_name=None, owner=None, status=None,
             priority=None, severity=None, due_at=None, overdue=False, result=None, receipt_id=None):
        rows.append({
            "kind": kind, "ref_type": ref_type, "ref_id": ref_id, "title": title,
            "department_slug": dept_slug, "department_label": dept_lbl, "room": room,
            "resident_id": resident_id, "resident_name": resident_name, "owner": owner,
            "status": status, "priority": priority, "severity": severity,
            "opened_at": opened_at, "age_hours": round((age_seconds(opened_at, now) or 0) / 3600, 1),
            "due_at": due_at, "overdue": overdue, "reason": reason, "result": result,
            "receipt_id": receipt_id, "_rank": rank, "_ts": parse_dt(opened_at) or EPOCH,
        })

    for t in tasks:
        slug = t.get("visibility_role") or "all_staff"
        lbl = dept_label(slug, by_slug)
        common = dict(dept_slug=slug, dept_lbl=lbl, opened_at=t.get("created_at"),
                      room=t.get("room"), resident_id=t.get("resident_id"),
                      resident_name=t.get("resident_name"), owner=t.get("assigned_name"),
                      status=t.get("status"), priority=t.get("priority"))
        title = t.get("title") or t.get("description") or "(untitled task)"
        booked = t.get("transport_run_id") or t.get("transport_slot_id")
        past_date = bool(t.get("requested_for_date")) and t["requested_for_date"] < day
        if task_is_overdue(t, now):
            push("overdue", "task", t["task_id"], rank=1, title=title,
                 reason=f"Overdue by {short_duration(age_seconds(t.get('due_at'), now) or 0)}",
                 due_at=t.get("due_at"), overdue=True, **common)
        elif t.get("category") == "transportation" and not booked:
            push("transportation_attention", "task", t["task_id"], rank=3, title=title,
                 reason="Ride requested, no slot booked", **common)
        elif t.get("category") == "transportation" and past_date:
            push("transportation_attention", "task", t["task_id"], rank=3, title=title,
                 reason="Past its requested date, still open", **common)
        elif task_is_unassigned(t):
            push("unassigned_open", "task", t["task_id"], rank=5, title=title,
                 reason=f"Unassigned - open {short_duration(age_seconds(t.get('created_at'), now) or 0)}", **common)
        elif task_is_open(t) and t.get("re_request_count", 0) > 0:
            push("re_requested_open", "task", t["task_id"], rank=4, title=title,
                 reason=f"Resident has re-asked {t['re_request_count']} time(s)", **common)

    for a in open_alerts:
        stale = (age_seconds(a.get("created_at"), now) or 0) > STALE_HOURS * 3600
        reason = "Unacknowledged" if a.get("status") == "active" else "Acknowledged, unresolved"
        if stale:
            reason += " (open >72h - likely stale test data)"
        push("open_assistance_event", "alert", a.get("alert_id"), rank=6 if stale else 0,
             title=a.get("resident_name") or "Unknown resident", dept_slug="nursing",
             dept_lbl="Care / Nursing", reason=reason, opened_at=a.get("created_at"),
             room=a.get("room"), resident_id=a.get("resident_id"),
             resident_name=a.get("resident_name"), severity=a.get("severity"),
             status=a.get("status"), owner=a.get("acknowledged_by"))

    for r in failed_receipts:
        slug = r.get("assigned_role") or "all_staff"
        push("failed_action", "receipt", r.get("receipt_id"), rank=2,
             title=_humanize(r.get("action_type")), dept_slug=slug,
             dept_lbl=dept_label(slug, by_slug),
             reason=f"Operational action {r.get('status')}", opened_at=r.get("created_at"),
             room=r.get("room"), resident_id=r.get("resident_id"),
             result=r.get("failure_reason") or r.get("result"), status=r.get("status"),
             receipt_id=r.get("receipt_id"))

    if department:
        rows = [x for x in rows if x["department_slug"] == department]
    rows.sort(key=lambda x: (x["_rank"], x["_ts"], str(x["ref_id"])))
    clean = [{k: v for k, v in x.items() if not k.startswith("_")} for x in rows]

    if format == "csv":
        return _csv_response(clean, DAILY_COLUMNS, f"daily-exceptions-{day}.csv")
    return {
        "report": "daily-exceptions", "date": day, "department": department,
        "generated_at": now.isoformat(),
        "counts": dict(Counter(x["kind"] for x in clean)),
        "total": len(clean), "rows": clean, "caveats": DAILY_CAVEATS,
    }


# ======================= 2. WEEKLY DEPARTMENT WORKLOAD =======================
@router.get("/weekly-workload")
async def weekly_workload(
    week_start: Optional[str] = None,
    days: int = Query(7, ge=1, le=31),
    department: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    user=Depends(require_admin),
):
    tz = ZoneInfo(FACILITY_TZ)
    now = datetime.now(timezone.utc)
    if week_start:
        start_local = datetime.strptime(week_start, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        t = datetime.now(tz)
        start_local = datetime(t.year, t.month, t.day, tzinfo=tz) - timedelta(days=days - 1)
    start_dt = start_local.astimezone(timezone.utc)
    end_dt = (start_local + timedelta(days=days)).astimezone(timezone.utc)

    def in_window(v) -> bool:
        d = parse_dt(v)
        return d is not None and start_dt <= d < end_dt

    departments, _by, tasks = await _load(now)
    users = {u["user_id"]: u.get("name") for u in await db.users.find(
        {}, {"_id": 0, "user_id": 1, "name": 1}).to_list(3000)}

    def report(label, slug, dt_tasks):
        still_open = [t for t in dt_tasks if task_is_open(t)]
        assigned_open = sum(1 for t in still_open if t.get("assigned_to"))
        oldest = min(still_open, key=lambda t: parse_dt(t.get("created_at")) or now, default=None)
        staff: dict = {}
        for t in dt_tasks:
            uid = t.get("assigned_to")
            if not uid:
                continue
            s = staff.setdefault(uid, {
                "user_id": uid, "name": users.get(uid) or t.get("assigned_name") or uid,
                "open": 0, "completed_this_week": 0,
            })
            if task_is_open(t):
                s["open"] += 1
            if t.get("status") == "completed" and in_window(t.get("completed_at")):
                s["completed_this_week"] += 1
        by_staff = sorted(staff.values(), key=lambda s: (-s["open"], -s["completed_this_week"], s["name"]))
        return {
            "department_slug": slug, "department_label": label,
            "created": sum(1 for t in dt_tasks if in_window(t.get("created_at"))),
            "completed": sum(1 for t in dt_tasks if t.get("status") == "completed" and in_window(t.get("completed_at"))),
            "still_open": len(still_open), "assigned_open": assigned_open,
            "unassigned_open": len(still_open) - assigned_open,
            "oldest_open_ref_id": oldest["task_id"] if oldest else None,
            "oldest_open_age_hours": round((age_seconds(oldest["created_at"], now) or 0) / 3600, 1) if oldest else None,
            "by_staff": by_staff,
            "staff_breakdown": "; ".join(
                f"{s['name']}: {s['open']} open, {s['completed_this_week']} done" for s in by_staff
            ),
        }

    rows = [report(d["label"], d["slug"], [t for t in tasks if t.get("visibility_role") == d["slug"]])
            for d in departments]
    rows.append(report("General / all-staff", "all_staff",
                       [t for t in tasks if (t.get("visibility_role") or "all_staff") == "all_staff"]))
    if department:
        rows = [r for r in rows if r["department_slug"] == department]

    if format == "csv":
        return _csv_response(rows, WEEKLY_COLUMNS, f"weekly-workload-{start_local.date()}.csv")
    return {
        "report": "weekly-workload", "week_start": str(start_local.date()), "days": days,
        "window_end": str((start_local + timedelta(days=days)).date()), "department": department,
        "generated_at": now.isoformat(), "rows": rows, "caveats": WEEKLY_CAVEATS,
    }
