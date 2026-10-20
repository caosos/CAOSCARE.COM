"""Bounded, read-only discovery over the canonical resident request records.

Reuse the existing mine/history scope, open-status vocabulary and safe view.
The private channel supplies the authorized resident; no model chooses one.
"""
import re
from datetime import datetime

from deps import db
from models import now_utc
from routes.facility_local_time import facility_local, facility_tz
from routes.request_delivery import delivery_for
from routes.resident_requests import (
    CATEGORY_ALIASES, OPEN_TASK_STATUSES, _resident_safe_view, _scope_query,
)

MAX_OFFSET = 1000
PROJECTION = {
    "_id": 0, "task_id": 1, "category": 1, "visibility_role": 1,
    "resident_words": 1, "description": 1, "title": 1, "status": 1,
    "created_at": 1, "updated_at": 1, "acknowledged_at": 1,
    "started_at": 1, "completed_at": 1, "last_re_requested_at": 1,
    "assigned_to": 1, "assigned_name": 1, "assigned_to_name": 1,
    "event_log.at": 1,
}


def _timestamp(value, tz):
    """Only known, timezone-bearing timestamps become spoken clock evidence."""
    raw = value.isoformat() if isinstance(value, datetime) else value
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return {**facility_local(dt.isoformat(), tz), "timezone": tz}


def _latest_recorded_update(task, tz):
    candidates = []
    for field in ("updated_at", "acknowledged_at", "started_at",
                  "completed_at", "last_re_requested_at"):
        stamp = _timestamp(task.get(field), tz)
        if stamp:
            candidates.append({**stamp, "source": field})
    for event in task.get("event_log") or []:
        stamp = _timestamp(event.get("at"), tz)
        if stamp:
            candidates.append({**stamp, "source": "latest_recorded_event"})
    return max(candidates, key=lambda s: datetime.fromisoformat(s["iso"])) if candidates else None


async def find_resident_requests(resident_id: str, *, department=None, issue=None,
                                 scope="recent", limit=10, offset=0) -> dict:
    """Search before pagination; recent includes closed history, open does not.

    Issue words are literal case-insensitive substrings, not semantic matching.
    All filters refine the same resident predicate. This service never writes.
    """
    if scope not in ("recent", "open") or not 1 <= limit <= 20 or not 0 <= offset <= MAX_OFFSET:
        raise ValueError("Invalid bounded request lookup")
    q = _scope_query(resident_id, None, None, allow_session=False)
    if scope == "open":
        q["status"] = {"$in": OPEN_TASK_STATUSES}
    clauses = []
    if department:
        department = department.strip().lower()
        clauses.append({"$or": [{"category": department}, {"visibility_role": department}]})
    if issue:
        for word in dict.fromkeys(issue.split()):
            clauses.append({"$or": [
                {field: {"$regex": re.escape(word), "$options": "i"}}
                for field in ("resident_words", "description", "title")
            ]})
    if clauses:
        q["$and"] = clauses
    tasks = await db.staff_tasks.find(q, PROJECTION).sort(
        [("created_at", -1), ("task_id", -1)],
    ).skip(offset).limit(limit + 1).max_time_ms(2000).to_list(limit + 1)
    has_more = len(tasks) > limit
    tasks = tasks[:limit]
    tz = await facility_tz()
    deliveries = await delivery_for(t["task_id"] for t in tasks)
    slugs = {CATEGORY_ALIASES.get(t["category"], t["category"]) for t in tasks}
    labels = {d["slug"]: d.get("label") for d in await db.departments.find(
        {"slug": {"$in": list(slugs)}}, {"_id": 0, "slug": 1, "label": 1},
    ).to_list(20)}
    rows = []
    for task in tasks:
        view = _resident_safe_view(task, tz)
        created = _timestamp(task.get("created_at"), tz)
        updated = _latest_recorded_update(task, tz)
        slug = CATEGORY_ALIASES.get(view["category"], view["category"])
        delivery = deliveries[task["task_id"]]
        rows.append({
            "request_id": view["task_id"], "summary": view["what_for"],
            "category": view["category"],
            "department": {"slug": slug, "label": labels.get(slug)},
            "status": view["status"], "lifecycle": view["lifecycle"],
            "is_open": view["is_open"],
            "created_at": created["iso"] if created else None, "created": created,
            "updated_at": updated["iso"] if updated else None, "updated": updated,
            "delivery": {k: delivery[k] for k in ("state", "label", "reached", "attempts")},
        })
    next_offset = offset + len(rows)
    return {
        "ok": True, "found": bool(rows), "requests": rows,
        "profile_scope": "configured_one_profile", "scope": scope,
        "filters": {"department": department, "issue": issue},
        "checked_at": now_utc().isoformat(), "timezone": tz,
        "limit": limit, "offset": offset, "has_more": has_more,
        "next_offset": next_offset if has_more and next_offset <= MAX_OFFSET else None,
        "pagination_limit_reached": has_more and next_offset > MAX_OFFSET,
        "coverage": {
            "order": "created_at_desc_then_request_id_desc",
            "time_window": "retained_records_no_age_cutoff",
            "issue_matching": "all_literal_words_case_insensitive_not_semantic",
            "snapshot": False,
        },
        "message": (
            "Results describe recorded requests, not proof staff were notified or service completed. "
            "Missing timestamps are unknown; updated may be the latest recorded event, as labeled. "
            "No match is not proof no request exists: check filters and remaining pages, or broaden "
            "to recent without issue/department filters. If the pagination limit is reached, refine "
            "the filters; this is not an exhaustive account history. Never create a request just to test lookup."
        ),
    }
