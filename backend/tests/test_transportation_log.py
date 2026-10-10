"""Transportation ride log: GET /api/transportation/log (json|csv). In-process ASGI, scratch DB."""
import asyncio, csv, io, os, sys, uuid
from datetime import datetime, timezone
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import transportation_log  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"tlog_{uuid.uuid4().hex[:6]}"
DAY = "2031-03-10"
REAL = httpx.AsyncClient
U = {"admin": f"{TAG}_a", "front": f"{TAG}_f", "transp": f"{TAG}_t", "nurse": f"{TAG}_n"}


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def get(path, who=None):
    app = FastAPI(); app.include_router(transportation_log.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(U[who])}"} if who else {}

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, headers=h)
    return run(go())


def _task(n, **kw):
    return {"task_id": f"{TAG}_{n}", "category": "transportation", "status": "pending", "description": f"clinic {n}",
            "resident_name": f"Res {n}", "room": f"R{n}", "requested_for_date": DAY, "requested_for_time_label": "9 AM",
            "created_at": datetime.now(timezone.utc).isoformat(), "source": "front_desk", "re_request_count": 0, **kw}


@pytest.fixture(scope="module", autouse=True)
def seed():
    async def up():
        await db.users.insert_many([
            {"user_id": U["admin"], "email": "a@x.t", "name": "Ad", "role": "admin"},
            {"user_id": U["front"], "email": "f@x.t", "name": "Fd", "role": "front_desk"},
            {"user_id": U["transp"], "email": "t@x.t", "name": "Tr", "role": "staff", "department": "transportation"},
            {"user_id": U["nurse"], "email": "n@x.t", "name": "Nu", "role": "staff", "department": "nursing"}])
        await db.transport_drivers.insert_one({"driver_id": f"{TAG}_d", "name": "Dana Driver"})
        await db.transport_vehicles.insert_one({"vehicle_id": f"{TAG}_v", "name": "Van 1"})
        await db.transport_runs.insert_many([
            {"run_id": f"{TAG}_r1", "date": DAY, "depart_time": "08:30", "driver_id": f"{TAG}_d", "vehicle_id": f"{TAG}_v", "status": "confirmed", "resident_task_ids": [f"{TAG}_booked"]},
            {"run_id": f"{TAG}_r2", "date": DAY, "depart_time": "10:00", "driver_id": f"{TAG}_d", "vehicle_id": f"{TAG}_v", "status": "in_progress", "departed_at": "x", "resident_task_ids": [f"{TAG}_departed"]}])
        await db.staff_tasks.insert_many([
            _task("waiting"), _task("booked", transport_run_id=f"{TAG}_r1"), _task("departed", transport_run_id=f"{TAG}_r2", status="in_progress"),
            _task("done", status="completed", completed_at="2031-03-10T15:00:00+00:00", event_log=[{"field": "note", "text": "all fine"}]),
            _task("cancel", status="skipped", re_request_count=2, event_log=[{"field": "note", "text": "resident feels better"}, {"field": "status", "to": "skipped", "at": "2031-03-09T10:00:00+00:00"}]),
            _task("other_day", requested_for_date="2031-05-01")])
        await db.receipts.insert_many([{"receipt_id": f"{TAG}_rc{i}", "related_object_type": "task", "related_object_id": f"{TAG}_booked", "action_type": "transportation_booked", "created_at": "x"} for i in range(2)])
    async def down():
        for c in ("users", "transport_drivers", "transport_vehicles", "transport_runs", "staff_tasks", "receipts"):
            await db[c].delete_many({"$or": [{"user_id": {"$regex": f"^{TAG}"}}, {"driver_id": {"$regex": f"^{TAG}"}}, {"vehicle_id": {"$regex": f"^{TAG}"}},
                                             {"run_id": {"$regex": f"^{TAG}"}}, {"task_id": {"$regex": f"^{TAG}"}}, {"receipt_id": {"$regex": f"^{TAG}"}}]})
    run(up()); yield; run(down())


Q = f"/api/transportation/log?from={DAY}&to={DAY}&q={TAG}"


def test_one_row_per_ride_with_derived_status_driver_vehicle_and_range():
    r = get(Q, "admin"); assert r.status_code == 200
    by = {x["task_id"].replace(f"{TAG}_", ""): x for x in r.json()["rows"]}
    assert set(by) == {"waiting", "booked", "departed", "done", "cancel"}   # other_day is out of range
    assert [by[k]["status"] for k in ("waiting", "booked", "departed", "done", "cancel")] == ["waiting", "booked", "departed", "completed", "cancelled"]
    assert by["booked"]["driver"] == "Dana Driver" and by["booked"]["vehicle"] == "Van 1" and by["booked"]["pickup_time"] == "08:30"
    assert by["booked"]["receipt_count"] == 2 and by["waiting"]["driver"] is None
    assert by["cancel"]["last_note"] == "resident feels better" and by["cancel"]["times_asked"] == 3
    assert by["cancel"]["closed_at"] == "2031-03-09T10:00:00+00:00" and by["done"]["closed_at"].startswith("2031-03-10")
    assert r.json()["counts"] == {"waiting": 1, "booked": 1, "departed": 1, "completed": 1, "cancelled": 1}


def test_status_filter_and_text_search():
    assert [x["status"] for x in get(Q + "&status=cancelled", "admin").json()["rows"]] == ["cancelled"]
    assert get(Q.replace(TAG, "Dana"), "front").json()["total"] >= 2
    assert get(Q + "&status=bogus", "admin").status_code == 422


def test_access_roles_and_range_limits():
    assert get(Q).status_code == 401
    assert get(Q, "nurse").status_code == 403
    for who in ("admin", "front", "transp"):
        assert get(Q, who).status_code == 200
    assert get("/api/transportation/log?from=2031-01-01&to=2031-12-31", "admin").status_code == 422
    assert get("/api/transportation/log?from=2031-03-10&to=2031-03-01", "admin").status_code == 422


def test_csv_matches_json_rows():
    j = get(Q, "admin").json()["rows"]
    r = get(Q + "&format=csv", "admin")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert [x["task_id"] for x in rows] == [x["task_id"] for x in j] and rows[0].keys() >= {"driver", "vehicle", "status", "last_note"}
