"""Transportation ride LOG: one row per ride over a date range, any status.

Read-only over the canonical StaffTask / TransportRun / receipts. The daily report and the
calendar show one day; this is the history a coordinator needs ("what rides did we give last
week, who drove, which were cancelled and why"). Same access as the calendar. CSV supported.
"""
import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from deps import db
from routes.realtime_facility import FACILITY_TZ, today_facility_date
from routes.transportation_runs import require_transport_operator

router = APIRouter(prefix="/transportation", tags=["transportation-log"])

MAX_DAYS = 93
MAX_ROWS = 5000   # fetch cap; if more match, the response says truncated (never silently partial)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r", "\n")


def csv_safe(v):
    """Spreadsheet formula neutralization (CSV injection): a cell that a spreadsheet would treat as a
    formula (or that starts with a control character) gets a leading apostrophe. Readable text is kept."""
    if v is None:
        return ""
    t = str(v)
    t = "".join(ch for ch in t if ch in "\t\r\n" or ord(ch) >= 32)   # drop other control characters
    if t.startswith(_FORMULA_START) or t.lstrip().startswith(_FORMULA_START):
        return "'" + t
    return t
COLUMNS = ["task_id", "requested_at", "resident_name", "room", "purpose", "appointment_date", "appointment_time",
           "status", "pickup_date", "pickup_time", "driver", "vehicle", "source", "requested_by",
           "closed_at", "last_note", "times_asked", "receipt_count"]
STATUSES = ("waiting", "booked", "departed", "completed", "cancelled")


def _local_date(iso) -> Optional[str]:
    try:
        dt = datetime.fromisoformat(iso) if isinstance(iso, str) else iso
        return dt.astimezone(ZoneInfo(FACILITY_TZ)).strftime("%Y-%m-%d")
    except Exception:
        return None


def derive_status(task: dict, run: Optional[dict]) -> str:
    """cancelled/completed come from the task; departed/booked from the run; else waiting."""
    s = task.get("status")
    if s == "skipped":
        return "cancelled"
    if s == "completed":
        return "completed"
    if run and (run.get("status") == "in_progress" or run.get("departed_at")):
        return "departed"
    if run or task.get("transport_run_id") or task.get("transport_slot_id"):
        return "booked"
    return "waiting"


def _last_note(task: dict) -> Optional[str]:
    for e in reversed(task.get("event_log") or []):
        if e.get("field") == "note" and e.get("text"):
            return e["text"]
    return task.get("notes")


def _closed_at(task: dict, status: str) -> Optional[str]:
    if status == "completed":
        return task.get("completed_at")
    if status == "cancelled":
        for e in reversed(task.get("event_log") or []):
            if e.get("field") == "status" and e.get("to") == "skipped":
                return e.get("at")
        return task.get("updated_at")
    return None


@router.get("/log")
async def ride_log(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    status: Optional[str] = None,
    q: Optional[str] = None,
    format: str = Query("json", pattern="^(json|csv)$"),
    user=Depends(require_transport_operator),
):
    today = today_facility_date()

    def _d(v, name):
        try:
            return date.fromisoformat(v)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"'{name}' must be YYYY-MM-DD")
    end_d = _d(date_to, "to") if date_to else date.fromisoformat(today)
    start_d = _d(date_from, "from") if date_from else end_d - timedelta(days=6)
    end, start = end_d.isoformat(), start_d.isoformat()
    span = (end_d - start_d).days
    if span < 0:
        raise HTTPException(status_code=422, detail="'from' is after 'to'")
    if span > MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"range is limited to {MAX_DAYS} days")
    if status and status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(STATUSES)}")

    # A ride belongs to the range by its appointment date, else the day it was requested. Narrow in
    # the database (created_at is stored UTC, so pad a day each side), then filter exactly in Python.
    pad_lo = (start_d - timedelta(days=1)).isoformat()
    pad_hi = (end_d + timedelta(days=2)).isoformat()
    query = {"category": "transportation", "$or": [
        {"requested_for_date": {"$gte": start, "$lte": end}},
        {"requested_for_date": {"$in": [None, ""]}, "created_at": {"$gte": pad_lo, "$lt": pad_hi}},
    ]}
    found = await db.staff_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(MAX_ROWS + 1)
    truncated = len(found) > MAX_ROWS
    tasks = [t for t in found[:MAX_ROWS] if start <= (t.get("requested_for_date") or _local_date(t.get("created_at")) or "") <= end]
    run_ids = {t["transport_run_id"] for t in tasks if t.get("transport_run_id")}
    runs = {r["run_id"]: r for r in await db.transport_runs.find({"run_id": {"$in": list(run_ids)}}, {"_id": 0}).to_list(2000)} if run_ids else {}
    drivers = {d["driver_id"]: d["name"] for d in await db.transport_drivers.find({}, {"_id": 0}).to_list(500)}
    vehicles = {v["vehicle_id"]: v.get("name") or v["vehicle_id"] for v in await db.transport_vehicles.find({}, {"_id": 0}).to_list(500)}
    rc: dict = {}
    if tasks:
        async for r in db.receipts.find({"related_object_type": "task", "related_object_id": {"$in": [t["task_id"] for t in tasks]}},
                                        {"_id": 0, "related_object_id": 1}):
            rc[r["related_object_id"]] = rc.get(r["related_object_id"], 0) + 1

    rows = []
    for t in tasks:
        run = runs.get(t.get("transport_run_id"))
        st = derive_status(t, run)
        if status and st != status:
            continue
        row = {
            "task_id": t["task_id"], "requested_at": t.get("created_at"), "resident_name": t.get("resident_name"),
            "room": t.get("room"), "purpose": t.get("description"), "appointment_date": t.get("requested_for_date"),
            "appointment_time": t.get("requested_for_time_label"), "status": st,
            "pickup_date": run.get("date") if run else None, "pickup_time": run.get("depart_time") if run else None,
            "driver": drivers.get(run.get("driver_id")) if run else None,
            "vehicle": vehicles.get(run.get("vehicle_id")) if run else None,
            "source": t.get("source"), "requested_by": t.get("created_by_name") or t.get("created_by"),
            "closed_at": _closed_at(t, st), "last_note": _last_note(t),
            "times_asked": 1 + int(t.get("re_request_count") or 0), "receipt_count": rc.get(t["task_id"], 0),
        }
        if q:
            hay = " ".join(str(row.get(k) or "") for k in ("resident_name", "room", "purpose", "driver", "vehicle", "task_id")).lower()
            if q.lower() not in hay:
                continue
        rows.append(row)
    rows.sort(key=lambda r: (r["appointment_date"] or r["requested_at"] or "", r["requested_at"] or ""), reverse=True)

    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: csv_safe(r.get(c)) for c in COLUMNS})
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="rides-{start}-to-{end}.csv"',
                                          **({"X-Truncated": "true"} if truncated else {})})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    return {"from": start, "to": end, "total": len(rows), "counts": counts, "truncated": truncated,
            "truncated_note": (f"More than {MAX_ROWS} rides matched; narrow the range. This list is incomplete." if truncated else None), "rows": rows}
