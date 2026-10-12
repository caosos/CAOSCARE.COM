"""careops-housekeeping-recurrence-001: a weekly Housekeeping series creates one
occurrence per facility date on its weekday, planned on that date/time in the
department queue, exactly once across repeated and concurrent runs; rescheduling
an occurrence does not make the series create another; it completes through the
normal lifecycle; the resident's upcoming read shows it; only owner/admin can
create a series, and invalid series are refused. In-process; scratch DB only.
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
from routes.task_recurrence import generate  # noqa: E402
from routes.task_templates import create_template, delete_template  # noqa: E402
from routes.upcoming_schedule import upcoming_for_resident  # noqa: E402

TAG = f"hkrec_{uuid.uuid4().hex[:8]}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _scenario():
    admin = {"user_id": f"{TAG}_admin", "name": "Admin", "role": "admin"}
    hk = {"user_id": f"{TAG}_hk", "name": "Housekeeper", "role": "staff", "department": "housekeeping"}
    nurse = {"user_id": f"{TAG}_nurse", "name": "Nurse", "role": "staff", "department": "nursing"}
    await db.users.insert_many([dict(u) for u in (admin, hk, nurse)])
    if not await db.departments.find_one({"slug": "housekeeping"}):
        await db.departments.insert_one({"slug": "housekeeping", "label": "Housekeeping", "active": True})
    rid = f"res_{TAG}"
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R"})
    tid = None
    try:
        with pytest.raises(HTTPException) as e:
            await create_template(StaffTaskTemplateCreate(title="x", recur="weekly", weekday=1, department="housekeeping"), user=hk)
        assert e.value.status_code == 403
        with pytest.raises(HTTPException) as e:
            await create_template(StaffTaskTemplateCreate(title="x", recur="weekly", department="housekeeping"), user=admin)
        assert e.value.status_code == 422
        with pytest.raises(HTTPException) as e:
            await create_template(StaffTaskTemplateCreate(title="x", recur="weekly", weekday=1, department="nope"), user=admin)
        assert e.value.status_code == 422

        today = date(2026, 10, 12)               # a Monday
        tpl = await create_template(StaffTaskTemplateCreate(
            title=f"{TAG} weekly room clean", recur="weekly", weekday=1, time_label="9:00 AM",
            department="housekeeping", resident_id=rid), user=admin)
        tid = tpl["template_id"]
        assert tpl["room"] == f"{TAG}-R"
        assert await db.receipts.count_documents({"related_object_id": tid, "action_type": "task_template_created"}) == 1

        await asyncio.gather(generate(today.isoformat()), generate(today.isoformat()))
        await generate(today.isoformat())
        occ = await db.staff_tasks.find({"template_id": tid}).to_list(20)
        assert len(occ) == 1          # one occurrence for this series despite three runs (two concurrent)
        o = occ[0]
        assert o["occurrence_date"] == "2026-10-13" and o["requested_for_date"] == "2026-10-13"
        assert o["requested_for_time_label"] == "9:00 AM" and o["visibility_role"] == "housekeeping"
        assert o["status"] == "pending" and o["resident_id"] == rid
        origin = await db.receipts.find_one({"related_object_id": o["task_id"], "action_type": "task_spawned_from_template"})
        assert origin and origin["actor_type"] == "system" and origin["authority"] == f"template:{tid}"

        # the next week: a second occurrence on the following Tuesday, not another for this week
        await generate((today + timedelta(days=7)).isoformat())
        dates = sorted(x["occurrence_date"] for x in await db.staff_tasks.find({"template_id": tid}).to_list(20))
        assert dates == ["2026-10-13", "2026-10-20"]

        # reschedule one occurrence; the series does not refill its slot
        await task_actions.set_schedule(o["task_id"], {"requested_for_date": "2026-10-14", "requested_for_time_label": "2:00 PM"},
                                        actor_from_user(hk), hk)
        await generate(today.isoformat())
        assert await db.staff_tasks.count_documents({"template_id": tid}) == 2
        with pytest.raises(HTTPException) as e:
            await task_actions.set_schedule(o["task_id"], {"requested_for_date": "2026-10-15"}, actor_from_user(nurse), nurse)
        assert e.value.status_code == 403

        up = await upcoming_for_resident(resident_id=rid, days=30)
        assert o["task_id"] in {i["task_id"] for i in up["items"]}

        await task_actions.start(o["task_id"], actor_from_user(hk), hk)
        await task_actions.complete(o["task_id"], "Room cleaned", actor_from_user(hk), hk)
        chain = await db.receipts.find({"related_object_id": o["task_id"]}).sort("created_at", 1).to_list(20)
        assert [c["action_type"] for c in chain] == ["task_spawned_from_template", "task_schedule_updated",
                                                     "task_in_progress", "task_completed"]
        assert len({c.get("correlation_id") for c in chain}) == 1

        await delete_template(tid, user=admin)
        await generate((today + timedelta(days=14)).isoformat())
        assert await db.staff_tasks.count_documents({"template_id": tid}) == 2
        assert await db.receipts.count_documents({"related_object_id": tid, "action_type": "task_template_deleted"}) == 1
    finally:
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.task_templates.delete_many({"title": {"$regex": f"^{TAG}"}})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"title": {"$regex": f"^{TAG}"}}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids + ([tid] if tid else [])}})


def test_weekly_housekeeping_series():
    run(_scenario())
