"""careops-therapy-recurrence-001: a weekly Therapy series carries provider,
discipline and location to every occurrence; occurrences are generated once;
one occurrence can be rescheduled and another cancelled without changing the
series or being refilled; the resident's upcoming read and Aria's status carry
the details; staff of other departments are refused. In-process; scratch DB.
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes request records; point DB_NAME at a scratch database", allow_module_level=True)

from fastapi import HTTPException  # noqa: E402
from deps import db  # noqa: E402
from models import StaffTaskTemplateCreate  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.aria_request_status import request_status_view  # noqa: E402
from routes.task_recurrence import generate  # noqa: E402
from routes.task_templates import create_template  # noqa: E402
from routes.upcoming_schedule import upcoming_for_resident  # noqa: E402

TAG = f"threc_{uuid.uuid4().hex[:8]}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _scenario():
    admin = {"user_id": f"{TAG}_admin", "name": "Admin", "role": "admin"}
    pt = {"user_id": f"{TAG}_pt", "name": "Therapist", "role": "staff", "department": "therapy"}
    hk = {"user_id": f"{TAG}_hk", "name": "Housekeeper", "role": "staff", "department": "housekeeping"}
    await db.users.insert_many([dict(u) for u in (admin, pt, hk)])
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"slug": "therapy", "label": "Therapy", "active": True})
    rid = f"res_{TAG}"
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R"})
    tid = None
    try:
        tpl = await create_template(StaffTaskTemplateCreate(
            title=f"{TAG} knee PT", recur="weekly", weekday=2, time_label="10:00 AM", department="therapy",
            resident_id=rid, provider_name=" Pat Lee, PT ", discipline="Physical therapy", location=""), user=admin)
        tid = tpl["template_id"]
        assert tpl["provider_name"] == "Pat Lee, PT" and tpl["location"] is None

        week = date(2026, 10, 12)        # Monday; Wednesday occurrences
        for d in (week, week + timedelta(days=7)):
            await asyncio.gather(generate(d.isoformat()), generate(d.isoformat()))
        occ = sorted(await db.staff_tasks.find({"template_id": tid}).to_list(20), key=lambda x: x["occurrence_date"])
        assert [o["occurrence_date"] for o in occ] == ["2026-10-14", "2026-10-21"]
        for o in occ:
            assert (o["provider_name"], o["discipline"], o["location"], o["visibility_role"]) == \
                   ("Pat Lee, PT", "Physical therapy", None, "therapy")
        a, b = occ

        await task_actions.set_schedule(a["task_id"], {"requested_for_date": "2026-10-15", "requested_for_time_label": "2:00 PM"},
                                        actor_from_user(pt), pt)
        await task_actions.skip(b["task_id"], "Resident away that week", actor_from_user(pt), pt)
        with pytest.raises(HTTPException) as e:
            await task_actions.set_schedule(a["task_id"], {"requested_for_date": "2026-10-16"}, actor_from_user(hk), hk)
        assert e.value.status_code == 403
        for d in (week, week + timedelta(days=7)):
            await generate(d.isoformat())
        assert await db.staff_tasks.count_documents({"template_id": tid}) == 2           # neither refilled
        series = await db.task_templates.find_one({"template_id": tid})
        assert series["time_label"] == "10:00 AM" and series["weekday"] == 2               # series unchanged

        up = await upcoming_for_resident(resident_id=rid, days=30)
        mine = [i for i in up["items"] if i["task_id"] == a["task_id"]]
        assert mine and mine[0]["provider_name"] == "Pat Lee, PT"
        assert b["task_id"] not in {i["task_id"] for i in up["items"]}                   # cancelled: not upcoming
        spoken = request_status_view(await db.staff_tasks.find_one({"task_id": a["task_id"]}))["spoken"]
        assert "Pat Lee, PT" in spoken and "2:00 PM" in spoken

        await task_actions.start(a["task_id"], actor_from_user(pt), pt)
        await task_actions.complete(a["task_id"], "Session done", actor_from_user(pt), pt)
        chain = await db.receipts.find({"related_object_id": a["task_id"]}).sort("created_at", 1).to_list(20)
        assert [c["action_type"] for c in chain] == ["task_spawned_from_template", "task_schedule_updated",
                                                     "task_in_progress", "task_completed"]
    finally:
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.task_templates.delete_many({"title": {"$regex": f"^{TAG}"}})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"title": {"$regex": f"^{TAG}"}}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids + ([tid] if tid else [])}})


def test_weekly_therapy_series():
    run(_scenario())
