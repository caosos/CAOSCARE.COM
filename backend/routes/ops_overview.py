"""Admin / ED operations overview - one read-only aggregation answering
"what needs my attention right now?" for the whole building.

Pure read: every number here is derived live from the existing
staff_tasks / alerts / departments / transport records. No new collection,
no new task/department model, no writes, and nothing in the RF / pendant /
ResidentEvent / realtime lifecycle is touched - resident-assistance events
(db.alerts) are queried only. Admin/owner only. Parse/format helpers live
in ops_overview_util.py to keep this handler under the file-size cap.

Sections mirror the directive:
  1. attention        - ranked, actionable, oldest-first within a tier
  2. departments      - open / overdue / unassigned / in_progress / done-today
  3. assistance       - resident-assistance events, read-only summary
  4. tasks            - ownership + aging (no-owner, overdue, sitting longest)
  5. transportation   - compact "today", reusing the existing request/run truth
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from deps import db, require_admin
from routes.realtime_facility import today_facility_date
from routes.ops_overview_util import (
    EPOCH, parse_dt, age_seconds, local_date, dept_label, task_link_hint, short_duration,
    task_is_open, task_is_unassigned, task_is_overdue, task_completed_on,
)

router = APIRouter(prefix="/ops", tags=["ops-overview"])

OPEN_TASK = ("pending", "in_progress")
OPEN_ALERT = ("active", "acknowledged")
ATTENTION_CAP = 50
LIST_CAP = 15
STALE_HOURS = 72

COUNTS_CAVEAT = (
    "Open resident-assistance events include historical RF/pendant test "
    "activations that were never staff-resolved - treat 'open >72h' as "
    "likely stale test data, not a live queue. Task counts are production."
)


@router.get("/overview")
async def operations_overview(
    attention_limit: int = Query(ATTENTION_CAP, ge=1, le=400),
    user=Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    facility_date = today_facility_date()

    departments = await db.departments.find({}, {"_id": 0}).sort("label", 1).to_list(100)
    by_slug = {d["slug"]: d for d in departments}

    tasks = await db.staff_tasks.find({}, {"_id": 0}).to_list(4000)
    open_alerts = await db.alerts.find(
        {"status": {"$in": list(OPEN_ALERT)}}, {"_id": 0},
    ).sort("created_at", 1).to_list(2000)
    resolved_today = sum(
        1 for a in await db.alerts.find(
            {"status": "resolved"}, {"_id": 0, "resolved_at": 1},
        ).sort("resolved_at", -1).to_list(1000)
        if local_date(a.get("resolved_at")) == facility_date
    )

    # ---------- shared task classification (one source of truth in
    # ops_overview_util, also used by routes/reports.py) ----------
    def is_open(t):
        return task_is_open(t)

    def is_overdue(t):
        return task_is_overdue(t, now)

    def is_unassigned(t):
        return task_is_unassigned(t)

    def done_today(t):
        return task_completed_on(t, facility_date)

    def dept_row(label, slug, dt_tasks, *, active=True, is_general=False):
        return {
            "slug": slug, "label": label, "active": active, "is_general": is_general,
            "open": sum(1 for t in dt_tasks if is_open(t)),
            "overdue": sum(1 for t in dt_tasks if is_overdue(t)),
            "unassigned": sum(1 for t in dt_tasks if is_unassigned(t)),
            "in_progress": sum(1 for t in dt_tasks if t.get("status") == "in_progress"),
            "completed_today": sum(1 for t in dt_tasks if done_today(t)),
        }

    # ---------- 2. DEPARTMENT STATUS ----------
    dept_rows = [
        dept_row(d["label"], d["slug"], [t for t in tasks if t.get("visibility_role") == d["slug"]],
                 active=d.get("active", True))
        for d in departments
    ]
    dept_rows.append(dept_row(
        "General / all-staff", "all_staff",
        [t for t in tasks if (t.get("visibility_role") or "all_staff") == "all_staff"],
        is_general=True,
    ))

    # ---------- 3. RESIDENT ASSISTANCE SUMMARY (read-only) ----------
    def alert_age(a):
        return age_seconds(a.get("created_at"), now) or 0

    oldest = open_alerts[0] if open_alerts else None
    assistance = {
        "active": sum(1 for a in open_alerts if a.get("status") == "active"),
        "acknowledged": sum(1 for a in open_alerts if a.get("status") == "acknowledged"),
        "resolved_today": resolved_today,
        "open_total": len(open_alerts),
        "unowned_open": sum(1 for a in open_alerts if not a.get("acknowledged_by")),
        "owned_open": sum(1 for a in open_alerts if a.get("acknowledged_by")),
        "aging_open_gt_2h": sum(1 for a in open_alerts if alert_age(a) > 7200),
        "aging_open_gt_24h": sum(1 for a in open_alerts if alert_age(a) > 86400),
        "possibly_stale_open_gt_72h": sum(1 for a in open_alerts if alert_age(a) > STALE_HOURS * 3600),
        "oldest_open": None if not oldest else {
            "alert_id": oldest.get("alert_id"), "resident_name": oldest.get("resident_name"),
            "room": oldest.get("room"), "severity": oldest.get("severity"),
            "status": oldest.get("status"), "minutes_open": round(alert_age(oldest) / 60),
        },
        "stale_threshold_hours": STALE_HOURS,
    }

    # ---------- 5. TRANSPORTATION (compact today) ----------
    def tr_booked(t):
        return bool(t.get("transport_run_id") or t.get("transport_slot_id"))

    tr = [t for t in tasks if t.get("category") == "transportation"]
    tr_open = [t for t in tr if is_open(t)]
    waiting_unbooked = sorted(
        (t for t in tr_open if not tr_booked(t)),
        key=lambda t: parse_dt(t.get("created_at")) or EPOCH,
    )
    transportation = {
        "date": facility_date,
        "requests_today": sum(1 for t in tr if local_date(t.get("created_at")) == facility_date),
        "open": len(tr_open),
        "booked_open": sum(1 for t in tr_open if tr_booked(t)),
        "needs_action": len(waiting_unbooked),
        "past_requested_date_open": sum(
            1 for t in tr_open if (t.get("requested_for_date") or "") and t["requested_for_date"] < facility_date
        ),
        "completed_today": sum(1 for t in tr if done_today(t)),
        "waiting_unbooked": [
            {"task_id": t["task_id"], "room": t.get("room"), "requested_for_date": t.get("requested_for_date")}
            for t in waiting_unbooked[:10]
        ],
    }

    # ---------- 4. TASK OWNERSHIP / AGING ----------
    open_tasks = [t for t in tasks if is_open(t)]

    def task_view(t):
        return {
            "task_id": t["task_id"],
            "title": t.get("title") or t.get("description") or "(untitled)",
            "category": t.get("category"),
            "department": dept_label(t.get("visibility_role"), by_slug),
            "room": t.get("room"), "resident_name": t.get("resident_name"),
            "assigned_name": t.get("assigned_name"), "priority": t.get("priority"),
            "status": t.get("status"),
            "age_seconds": age_seconds(t.get("created_at"), now) or 0,
            "overdue": is_overdue(t), "re_request_count": t.get("re_request_count", 0),
            "link_hint": task_link_hint(t),
        }

    by_age = sorted(open_tasks, key=lambda t: (parse_dt(t.get("created_at")) or EPOCH, t["task_id"]))
    tasks_section = {
        "open_total": len(open_tasks),
        "unassigned_open": sum(1 for t in open_tasks if is_unassigned(t)),
        "overdue_open": sum(1 for t in open_tasks if is_overdue(t)),
        "completed_today": sum(1 for t in tasks if done_today(t)),
        "oldest_open": [task_view(t) for t in by_age[:LIST_CAP]],
        "unassigned": [task_view(t) for t in by_age if not t.get("assigned_to")][:LIST_CAP],
    }

    # ---------- 1. NEEDS ATTENTION NOW ----------
    items = []

    def push(tier, kind, ref_id, title, reason, *, opened_at=None, **extra):
        items.append({
            "tier": tier, "kind": kind, "ref_id": ref_id, "title": title, "reason": reason,
            "age_seconds": age_seconds(opened_at, now) or 0, "opened_at": opened_at,
            # sort on the fixed open time, never on a per-request "now" - two
            # items opened <1s apart would otherwise swap between polls as
            # int(age) crosses a second boundary.
            "_ts": parse_dt(opened_at) or EPOCH,
            **{k: extra.get(k) for k in (
                "resident_name", "room", "department", "owner", "status", "severity", "priority", "link_hint",
            )},
        })

    for a in open_alerts:
        stale = (age_seconds(a.get("created_at"), now) or 0) > STALE_HOURS * 3600
        if a.get("status") == "active":
            tier = 0 if a.get("severity") == "emergency" else 1
            reason = "Unacknowledged emergency" if a.get("severity") == "emergency" else "Unacknowledged assistance call"
        else:
            tier, reason = 4, "Acknowledged, not yet resolved"
        if stale:
            tier = 7  # demote likely-stale test rows to the bottom, still visible
            reason += " (open >72h - likely stale test data)"
        push(tier, "assistance", a.get("alert_id"), a.get("resident_name") or "Unknown resident", reason,
             opened_at=a.get("created_at"), resident_name=a.get("resident_name"), room=a.get("room"),
             department="Care / Nursing", owner=a.get("acknowledged_by"),
             status=a.get("status"), severity=a.get("severity"), link_hint="assistance")

    for t in open_tasks:
        hint = task_link_hint(t)
        common = dict(opened_at=t.get("created_at"), resident_name=t.get("resident_name"),
                      room=t.get("room"), department=dept_label(t.get("visibility_role"), by_slug),
                      owner=t.get("assigned_name"), status=t.get("status"),
                      priority=t.get("priority"), link_hint=hint)
        title = t.get("title") or t.get("description") or "(untitled task)"
        booked = t.get("transport_run_id") or t.get("transport_slot_id")
        past_date = (t.get("requested_for_date") or "") and t["requested_for_date"] < facility_date
        if is_overdue(t):
            push(2, "task", t["task_id"], title, f"Overdue by {short_duration(age_seconds(t.get('due_at'), now) or 0)}", **common)
        elif t.get("category") == "transportation" and not booked:
            push(3, "transportation", t["task_id"], title, "Ride requested, no slot booked", **common)
        elif t.get("category") == "transportation" and past_date:
            push(3, "transportation", t["task_id"], title, "Past its requested date, still open", **common)
        elif not t.get("assigned_to"):
            push(5, "task", t["task_id"], title, "Unassigned - no owner", **common)
        elif t.get("re_request_count", 0) > 0:
            push(6, "task", t["task_id"], title, f"Resident has asked {t['re_request_count']}x", **common)

    items.sort(key=lambda x: (x["tier"], x["_ts"], str(x["ref_id"])))
    attention = [{k: v for k, v in it.items() if k != "_ts"} for it in items[:attention_limit]]

    return {
        "generated_at": now.isoformat(),
        "facility_date": facility_date,
        "attention": attention,
        "attention_total": len(items),
        "departments": dept_rows,
        "assistance": assistance,
        "tasks": tasks_section,
        "transportation": transportation,
        "counts_caveat": COUNTS_CAVEAT,
    }
