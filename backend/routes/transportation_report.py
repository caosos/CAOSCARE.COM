"""Daily transportation operations report (Terminal 8 transportation pilot,
directive section 7-8). Read-only aggregation over the canonical
StaffTask/Receipt/TransportSlot records - never derived from email inbox
state, per the directive's own instruction. Split into its own file from
transportation.py to keep both under the 400-line cap.

One day, reconciled: what came in, what went out, what's still open.
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends

from deps import db, get_current_user
from routes.realtime_facility import today_facility_date, FACILITY_TZ

router = APIRouter(prefix="/transportation", tags=["transportation"])

ACTION_LABELS = {
    "transportation_requested": "requested (no slot yet)",
    "transportation_booked": "booked",
    "transportation_changed": "changed",
    "transportation_cancelled": "cancelled",
    "transportation_completed": "completed",
    "transportation_no_slot": "declined - no slot",
    "transportation_re_requested": "re-requested",
}


def _iso(v):
    return v if isinstance(v, str) else (v.isoformat() if v else None)


def _local_date(created_at) -> Optional[str]:
    """created_at is stored in UTC (now_utc().isoformat()) - comparing its
    raw string prefix against a facility-local date is exactly the
    UTC-vs-facility-timezone bug already fixed once elsewhere in this
    project (see docs/ARIA_VOICE_FIRST.md). Convert to the facility's own
    calendar date before filtering "today"."""
    if not created_at:
        return None
    try:
        dt = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
        return dt.astimezone(ZoneInfo(FACILITY_TZ)).strftime("%Y-%m-%d")
    except Exception:
        return None


@router.get("/report")
async def daily_report(date: Optional[str] = None, user=Depends(get_current_user)):
    day = date or today_facility_date()

    # ---- INBOUND: requests received today ----
    # created_at is stored as isoformat() with a timezone offset, so a
    # naive string range against date-only bounds isn't reliable - filter
    # on the date prefix in Python instead of trying to encode that in the
    # Mongo query.
    all_transport_docs = await db.staff_tasks.find({"category": "transportation"}, {"_id": 0}).to_list(2000)
    inbound_docs = [t for t in all_transport_docs if _local_date(t.get("created_at")) == day]
    inbound = [
        {
            "task_id": t["task_id"], "resident_id": t.get("resident_id"), "room": t.get("room"),
            "purpose": t.get("description"), "requested_for_date": t.get("requested_for_date"),
            "requested_for_time_label": t.get("requested_for_time_label"), "source": t.get("source"),
            "received_at": _iso(t.get("created_at")),
            # "status" on the task itself is staff-acknowledgment workflow
            # (pending/in_progress/completed), NOT whether a ride is
            # actually booked - that truth lives only in transport_slot_id.
            # A request can sit at status="pending" (unacknowledged) while
            # already genuinely booked. Surface the real truth explicitly
            # so the UI doesn't make callers infer it from "status".
            "booked": bool(t.get("transport_slot_id")),
        }
        for t in inbound_docs
    ]

    # ---- OUTBOUND / ACTIONS: receipts filed today ----
    receipt_docs = await db.receipts.find(
        {"related_object_type": "task", "action_type": {"$in": list(ACTION_LABELS.keys())}},
        {"_id": 0},
    ).to_list(2000)
    receipt_docs = [r for r in receipt_docs if _local_date(r.get("created_at")) == day]
    outbound = [
        {
            "task_id": r["related_object_id"], "action": ACTION_LABELS.get(r["action_type"], r["action_type"]),
            "resident_id": r.get("resident_id"), "room": r.get("room"), "at": _iso(r.get("created_at")),
        }
        for r in receipt_docs
    ]
    counts_by_action = {}
    for r in receipt_docs:
        counts_by_action[r["action_type"]] = counts_by_action.get(r["action_type"], 0) + 1

    # ---- CURRENT STATE ----
    all_open = await db.staff_tasks.find(
        {"category": "transportation", "status": {"$in": ["pending", "in_progress"]}}, {"_id": 0},
    ).to_list(500)
    upcoming_rides = [
        t for t in all_open if t.get("transport_slot_id") and (t.get("requested_for_date") or "") >= today_facility_date()
    ]
    waiting_unbooked = [t for t in all_open if not t.get("transport_slot_id")]
    follow_ups = [t for t in all_open if t.get("re_request_count", 0) > 0]

    # ---- SUMMARY ----
    total_completed = sum(1 for r in receipt_docs if r["action_type"] == "transportation_completed")
    total_cancelled = sum(1 for r in receipt_docs if r["action_type"] == "transportation_cancelled")
    total_booked = sum(1 for r in receipt_docs if r["action_type"] == "transportation_booked")
    total_no_slot = sum(1 for r in receipt_docs if r["action_type"] == "transportation_no_slot")

    slots = await db.transport_slots.find({"date": day}, {"_id": 0}).to_list(50)
    total_capacity = sum(s["capacity"] for s in slots)
    total_booked_seats = sum(s["booked_count"] for s in slots)

    return {
        "date": day,
        "inbound": inbound,
        "outbound": outbound,
        "current_state": {
            "upcoming_rides": [{"task_id": t["task_id"], "room": t.get("room"), "requested_for_date": t.get("requested_for_date")} for t in upcoming_rides],
            "waiting_unbooked": [{"task_id": t["task_id"], "room": t.get("room"), "requested_for_date": t.get("requested_for_date")} for t in waiting_unbooked],
            "conflicts_declined_no_slot": total_no_slot,
            "follow_ups_required": [{"task_id": t["task_id"], "room": t.get("room"), "re_request_count": t.get("re_request_count")} for t in follow_ups],
        },
        "summary": {
            "total_requests_received": len(inbound_docs),
            "total_booked": total_booked,
            "total_completed": total_completed,
            "total_cancelled": total_cancelled,
            "total_unresolved": len(waiting_unbooked),
            "action_counts": {ACTION_LABELS.get(k, k): v for k, v in counts_by_action.items()},
            "slot_capacity": total_capacity,
            "slot_booked": total_booked_seats,
            "utilization": round(total_booked_seats / total_capacity, 2) if total_capacity else None,
        },
    }
