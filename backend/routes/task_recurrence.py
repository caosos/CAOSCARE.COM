"""Recurring work occurrences (careops-housekeeping-recurrence-001).

One generator for StaffTaskTemplate series, called by the escalation tick (the
one background schedule; no new timer) and by the admin "generate now" route.

  * dates are facility-local (today_facility_date), not UTC;
  * daily: today and tomorrow; weekly: the next 7 days on the template's weekday,
    so a weekly job shows in Upcoming before its day;
  * each occurrence is created ONCE: `occurrence_key` = "<template_id>:<date>"
    under a unique index, so repeated or concurrent runs never duplicate it, and
    rescheduling an occurrence (its planned date changes, its key does not) never
    makes the series create another one;
  * an occurrence is an ordinary StaffTask planned on its date/time in the
    template's department, with an origin receipt by the system actor
    (authority template:<id>); everything after is the normal lifecycle;
  * inactive or deleted templates generate nothing; existing occurrences stay.
"""
from datetime import date, timedelta
from typing import Optional

from pymongo.errors import DuplicateKeyError

from deps import db
from models import StaffTask
from routes.actor_context import actor_system
from routes.realtime_facility import today_facility_date
from routes.task_lifecycle import record_origin

ACTOR = actor_system("recurrence")
_index_ready = False


async def _ensure_index() -> None:
    global _index_ready
    if not _index_ready:
        await db.staff_tasks.create_index("occurrence_key", unique=True,
                                          partialFilterExpression={"occurrence_key": {"$type": "string"}})
        _index_ready = True


def occurrence_dates(tpl: dict, today: str) -> list:
    d0 = date.fromisoformat(today)
    if tpl.get("recur") == "weekly":
        if tpl.get("weekday") is None:
            return []
        return [(d0 + timedelta(days=i)).isoformat() for i in range(7)
                if (d0 + timedelta(days=i)).weekday() == tpl["weekday"]]
    return [d0.isoformat(), (d0 + timedelta(days=1)).isoformat()]


async def generate(today: Optional[str] = None) -> dict:
    await _ensure_index()
    from routes.tasks import _resolve_denorms   # import here: tasks imports the tick indirectly
    today = today or today_facility_date()
    out = {"occurrences_created": 0, "templates": 0}
    async for tpl in db.task_templates.find({"active": True}, {"_id": 0}):
        out["templates"] += 1
        for day in occurrence_dates(tpl, today):
            key = f"{tpl['template_id']}:{day}"
            if await db.staff_tasks.find_one({"$or": [
                    {"occurrence_key": key},
                    # made before occurrence keys existed (old spawn-today / seed): same template, same day
                    {"template_id": tpl["template_id"], "occurrence_key": None,
                     "created_at": {"$regex": f"^{day}T"}}]}, {"_id": 1}):
                continue
            dept = tpl.get("department") or "all_staff"
            payload = {"title": tpl["title"], "description": tpl.get("description") or "",
                       "category": tpl.get("category") or tpl.get("department") or "other",
                       "shift": tpl.get("shift", "any"), "resident_id": tpl.get("resident_id"), "room": tpl.get("room"),
                       "template_id": tpl["template_id"], "occurrence_date": day, "source": "system",
                       "visibility_role": dept, "requested_for_date": day,
                       "requested_for_time_label": tpl.get("time_label")}
            await _resolve_denorms(payload)
            doc = StaffTask(**payload).model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            doc["occurrence_key"] = key
            try:
                await db.staff_tasks.insert_one(doc)
            except DuplicateKeyError:
                continue   # another run made it first
            doc.pop("_id", None)
            await record_origin(doc, ACTOR, action_type="task_spawned_from_template",
                                authority=f"template:{tpl['template_id']}")
            out["occurrences_created"] += 1
    return out
