"""careops-transport-calendar-001: an empty-looking calendar day says where the rides are: the next dates
with open rides, and how many open unbooked requests are dated before today. Default day is the facility
date. In-process, scratch DB, no external calls."""
import asyncio, os, sys, uuid
from datetime import date, timedelta
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import transportation_calendar as cal  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402
from routes.realtime_facility import today_facility_date  # noqa: E402

TAG = f"tce_{uuid.uuid4().hex[:6]}"
def run(c): return asyncio.get_event_loop().run_until_complete(c)


def get(who, **params):
    app = FastAPI(); app.include_router(cal.router, prefix="/api")
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get("/api/transportation/calendar", headers={"Authorization": f"Bearer {_issue_jwt(who)}"}, params=params)
    return run(go())


@pytest.fixture(autouse=True)
def seed():
    run(db.users.insert_many([{"user_id": f"{TAG}_fd", "email": "fd@x.t", "name": "FD", "role": "front_desk", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_n", "email": "n@x.t", "name": "N", "role": "staff", "department": "nursing", "auth_provider": "jwt"}]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.staff_tasks.delete_many({"task_id": {"$regex": f"^{TAG}"}})); run(db.transport_runs.delete_many({"run_id": {"$regex": f"^{TAG}"}}))


def task(n, day, **kw):
    run(db.staff_tasks.insert_one({"task_id": f"{TAG}_t{n}", "category": "transportation", "status": "pending", "transport_run_id": None,
                                   "requested_for_date": day, "title": f"ride {n}", **kw}))


def test_empty_day_points_to_later_rides_and_counts_past_dated_open_requests():
    today = date.fromisoformat(today_facility_date())
    d = lambda n: (today + timedelta(days=n)).isoformat()
    far = 900                                                           # far future: no other test's rides out there
    earlier_before = get(f"{TAG}_fd", date=d(far)).json()["elsewhere"]["earlier_open_unbooked"]
    task(1, d(far + 3)); task(2, d(far + 3)); task(3, d(far + 9)); task(4, d(-5)); task(5, d(-1))
    task(6, d(-2), status="completed")                                   # closed: not counted
    task(7, d(-3), transport_slot_id="slot_legacy")                      # booked on a legacy hourly slot: not unbooked
    run(db.transport_runs.insert_one({"run_id": f"{TAG}_r1", "date": d(far + 5), "status": "confirmed", "depart_time": "10:00", "resident_task_ids": []}))
    run(db.transport_runs.insert_one({"run_id": f"{TAG}_r2", "date": d(far + 6), "status": "completed", "depart_time": "10:00", "resident_task_ids": []}))
    r = get(f"{TAG}_fd", date=d(far + 1))
    assert r.status_code == 200
    body = r.json()
    assert all(not x["runs"] and not x["pending"] for x in body["days"])
    assert body["elsewhere"]["next_dates"] == [{"date": d(far + 3), "count": 2}, {"date": d(far + 5), "count": 1}, {"date": d(far + 9), "count": 1}]
    assert body["elsewhere"]["earlier_open_unbooked"] == earlier_before + 2


def test_default_day_is_the_facility_date_and_access_is_scoped():
    assert get(f"{TAG}_fd").json()["start_date"] == today_facility_date()
    assert get(f"{TAG}_n").status_code == 403
