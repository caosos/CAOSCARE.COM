"""RQ-016: (1) a request with a resident_id but no room takes the room from
the resident record (a supplied room is kept); (2) Activities is a default
department, added to already-seeded communities too.

    cd backend && DB_NAME=caoscare_rq016_test pytest tests/test_rq016_request_room.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402

TAG = f"rq016_{uuid.uuid4().hex[:8]}"
RID = f"{TAG}_res"


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    async def setup():
        await seed_default_departments()
        await db.residents.insert_one({"resident_id": RID, "name": f"{TAG} Resident", "room": "R-77"})
    run(setup())
    yield
    async def tear():
        await db.residents.delete_many({"resident_id": RID})
        await db.staff_tasks.delete_many({"resident_id": RID})
        await db.notifications.delete_many({"resident_id": RID})
    run(tear())


def _req(**kw):
    return ResidentRequestInput(category="maintenance", resident_id=RID, summary=f"{TAG} sink leaking",
                                resident_words="sink leaking", **kw)


def test_room_derived_from_resident_record():
    out = run(create_resident_request(_req()))
    task = run(db.staff_tasks.find_one({"task_id": out["task_id"]}))
    assert task["room"] == "R-77"
    assert "Room: R-77" in (task.get("description") or "") or "unknown" not in str(task)
    note = run(db.notifications.find({"related_object_id": out["task_id"]}).to_list(10))
    assert all("Room: unknown" not in (n.get("body") or n.get("message") or "") for n in note)


def test_supplied_room_is_kept():
    out = run(create_resident_request(_req(room="OTHER-1")))
    task = run(db.staff_tasks.find_one({"task_id": out["task_id"]}))
    assert task["room"] == "OTHER-1"


def test_activities_department_seeded_idempotently():
    run(db.departments.delete_many({"slug": "activities"}))
    run(seed_default_departments())
    run(seed_default_departments())
    rows = run(db.departments.find({"slug": "activities"}, {"_id": 0}).to_list(5))
    assert len(rows) == 1 and rows[0]["label"] == "Activities"
