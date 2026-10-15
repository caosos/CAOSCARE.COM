"""Department roster: real accounts (REAL) plus the simulator's rota (SIM),
department permission, no invented duty for real staff."""
import asyncio
import uuid

import pytest
from fastapi import HTTPException

from deps import db
from routes import department_roster as dr

TAG = f"dr_{uuid.uuid4().hex[:8]}"
DEPT = f"{TAG}_dept"


def run(c):
    return asyncio.run(c)


@pytest.fixture
def seeded():
    async def setup():
        await db.departments.insert_one({"slug": DEPT, "label": "Roster test", "active": True})
        await db.users.insert_many([
            {"user_id": f"{TAG}_a", "name": f"{TAG} Ann", "role": "staff", "department": DEPT},
            {"user_id": f"{TAG}_b", "name": f"{TAG} Bob", "role": "staff", "department": DEPT}])
        await db.staff_tasks.insert_one({"task_id": f"{TAG}_t", "assigned_to": f"{TAG}_a", "status": "in_progress",
                                         "title": "Fix the sink", "visibility_role": DEPT})
    run(setup())
    yield
    async def teardown():
        await db.departments.delete_many({"slug": DEPT})
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}_"}})
        await db.staff_tasks.delete_many({"task_id": {"$regex": f"^{TAG}_"}})
    run(teardown())


def test_real_staff_are_listed_with_truthful_duty(seeded):
    out = run(dr.department_roster(DEPT, user={"role": "owner"}))
    real = [p for p in out["people"] if p["kind"] == "real"]
    assert [p["name"] for p in real] == [f"{TAG} Ann", f"{TAG} Bob"]
    ann = real[0]
    assert ann["duty"] == "not_recorded" and ann["availability"] == "busy" and ann["current"]["task_id"] == f"{TAG}_t"
    assert real[1]["availability"] == "available"


def test_department_permission(seeded):
    assert run(dr.department_roster(DEPT, user={"role": "staff", "department": DEPT}))["real_count"] == 2
    with pytest.raises(HTTPException) as e:
        run(dr.department_roster(DEPT, user={"role": "staff", "department": "kitchen"}))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        run(dr.department_roster("no_such_dept", user={"role": "owner"}))
    assert e.value.status_code == 404
