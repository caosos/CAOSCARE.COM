"""Driver <-> login link and the "My rides" calendar filter. In-process ASGI, scratch DB."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import transportation_calendar, transportation_resources  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"mr_{uuid.uuid4().hex[:6]}"
DAY = "2031-04-02"
REAL = httpx.AsyncClient
U = {k: f"{TAG}_{k}" for k in ("admin", "d1", "d2", "d3", "res")}


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def call(method, path, who, **kw):
    app = FastAPI(); app.include_router(transportation_calendar.router, prefix="/api"); app.include_router(transportation_resources.router, prefix="/api")

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, path, headers={"Authorization": f"Bearer {_issue_jwt(U[who])}"}, **kw)
    return run(go())


@pytest.fixture(scope="module", autouse=True)
def seed():
    async def up():
        await db.users.insert_many([
            {"user_id": U["admin"], "email": "a@x.t", "name": "Ad", "role": "admin"},
            {"user_id": U["d1"], "email": "d1@x.t", "name": "Driver One", "role": "staff", "department": "transportation"},
            {"user_id": U["d2"], "email": "d2@x.t", "name": "Driver Two", "role": "staff", "department": "transportation"},
            {"user_id": U["d3"], "email": "d3@x.t", "name": "Unlinked", "role": "staff", "department": "transportation"},
            {"user_id": U["res"], "email": "r@x.t", "name": "Res", "role": "resident"}])
        await db.transport_drivers.insert_many([{"driver_id": f"{TAG}_D1", "name": "D1"}, {"driver_id": f"{TAG}_D2", "name": "D2"}])
        await db.transport_runs.insert_many([
            {"run_id": f"{TAG}_r1", "date": DAY, "depart_time": "09:00", "driver_id": f"{TAG}_D1", "status": "confirmed", "resident_task_ids": [f"{TAG}_t1"]},
            {"run_id": f"{TAG}_r2", "date": DAY, "depart_time": "10:00", "driver_id": f"{TAG}_D2", "status": "confirmed", "resident_task_ids": [f"{TAG}_t2"]}])
        await db.staff_tasks.insert_many([
            {"task_id": f"{TAG}_t1", "category": "transportation", "status": "pending", "resident_name": "R1", "transport_run_id": f"{TAG}_r1"},
            {"task_id": f"{TAG}_t2", "category": "transportation", "status": "pending", "resident_name": "R2", "transport_run_id": f"{TAG}_r2"},
            {"task_id": f"{TAG}_t3", "category": "transportation", "status": "pending", "resident_name": "R3", "transport_run_id": None, "requested_for_date": DAY}])
    run(up())
    yield

    async def down():
        for c in ("users", "transport_drivers", "transport_runs", "staff_tasks"):
            key = {"users": "user_id", "transport_drivers": "driver_id", "transport_runs": "run_id", "staff_tasks": "task_id"}[c]
            await db[c].delete_many({key: {"$regex": f"^{TAG}"}})
    run(down())


def test_link_validation_and_uniqueness():
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D1", "admin", json={"user_id": U["d1"]}).status_code == 200
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D2", "admin", json={"user_id": U["d1"]}).status_code == 409   # one login, one driver
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D2", "admin", json={"user_id": "nobody"}).status_code == 422
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D2", "admin", json={"user_id": U["res"]}).status_code == 422  # not a staff login
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D2", "admin", json={"user_id": U["d2"]}).status_code == 200
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D2", "admin", json={"user_id": ""}).json()["user_id"] is None  # cleared
    assert call("PATCH", f"/api/transportation/drivers/{TAG}_D2", "admin", json={"user_id": U["d2"]}).status_code == 200


def test_my_rides_shows_only_the_linked_drivers_runs():
    q = {"date": DAY, "mine": "true"}
    d1 = call("GET", "/api/transportation/calendar", "d1", params=q).json()
    runs = d1["days"][0]["runs"]
    assert d1["mine"] is True and d1["linked_driver"] == "D1" and [r["run_id"] for r in runs] == [f"{TAG}_r1"]
    assert [x["resident_name"] for x in runs[0]["riders"]] == ["R1"] and d1["days"][0]["pending"] == []
    d2 = call("GET", "/api/transportation/calendar", "d2", params=q).json()
    assert [r["run_id"] for r in d2["days"][0]["runs"]] == [f"{TAG}_r2"]


def test_unlinked_login_sees_nothing_not_everything():
    r = call("GET", "/api/transportation/calendar", "d3", params={"date": DAY, "mine": "true"}).json()
    assert r["linked_driver"] is None and r["days"][0]["runs"] == [] and r["days"][0]["pending"] == []


def test_full_calendar_unchanged_without_mine():
    r = call("GET", "/api/transportation/calendar", "admin", params={"date": DAY}).json()
    assert {x["run_id"] for x in r["days"][0]["runs"]} >= {f"{TAG}_r1", f"{TAG}_r2"} and "mine" not in r
    assert any(p["task_id"] == f"{TAG}_t3" for p in r["days"][0]["pending"])
