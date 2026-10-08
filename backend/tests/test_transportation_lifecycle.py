"""Transportation lifecycle end to end, over HTTP against a running backend:
resident request (Aria path) -> front desk assignment with a named driver/
vehicle -> shared run -> depart -> complete, plus change, cancel, driver
hours, flex drivers, role permissions and run reconciliation.

Own synthetic fixtures (users, residents, drivers, vehicles tagged with a
per-run TAG) on dates in 2031, deleted at the end - never depends on demo
seed data and never touches real residents. Same single-asyncio.run()
Motor pattern as test_staff_department.py.

Run with (pointed at a backend started from THIS worktree):
    TEST_API_BASE=http://127.0.0.1:8093 pytest tests/test_transportation_lifecycle.py -q
"""
import asyncio
import os
import sys
import uuid

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"trlc_{uuid.uuid4().hex[:8]}"
from datetime import date as _date, timedelta as _td
_BASE = _date.today() + _td(days=((0 - _date.today().weekday()) % 7) + 7)   # a Monday 7-13 days ahead (inside the far-date guard)
MON, TUE, WED = ((_BASE + _td(days=i)).isoformat() for i in range(3))
PW = "test-pw-123456"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _post(path, headers=None, **body):
    return requests.post(f"{API}{path}", headers=headers or {}, json=body, timeout=10)


def _get(path, headers=None, **params):
    return requests.get(f"{API}{path}", headers=headers or {}, params=params, timeout=10)


async def _user(db, role, department=None):
    from models import uid, now_utc
    email = f"{TAG}_{role}_{department or 'x'}@example.com"
    await db.users.insert_one({
        "user_id": uid("user"), "email": email, "name": f"{TAG} {role} {department or ''}".strip(),
        "role": role, "department": department, "auth_provider": "jwt",
        "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode(),
        "created_at": now_utc().isoformat(),
    })
    r = _post("/auth/login", email=email, password=PW)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _status(resident_id):
    r = _get("/transportation/request/status", resident_id=resident_id)
    r.raise_for_status()
    return r.json()


async def _log(db, task_id):
    t = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0, "event_log": 1})
    return [(e["field"], e.get("to"), e.get("by_name")) for e in t.get("event_log", [])]


def _receipt_types(admin, task_id):
    detail = _get(f"/tasks/{task_id}/detail", admin).json()
    return [r["action_type"] for r in detail.get("receipts", [])]


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    residents = []
    for i in range(5):
        rid = uid("res")
        await db.residents.insert_one({
            "resident_id": rid, "name": f"{TAG} Resident {i}", "room": f"{TAG[-4:]}{i}",
            "created_at": now_utc().isoformat(),
        })
        residents.append(rid)
    r1, r2, r3, r4, r5 = residents
    try:
        admin = await _user(db, "admin")
        desk = await _user(db, "front_desk")
        driver_staff = await _user(db, "staff", "transportation")
        nurse = await _user(db, "staff", "nursing")

        # ---- fleet: admin configures, front desk can read ----
        drv_a = _post("/transportation/drivers", admin, name=f"{TAG} Driver A").json()
        drv_b = _post("/transportation/drivers", admin, name=f"{TAG} Driver B", work_days=[1, 2, 3, 4],
                      shift_start="08:00", shift_end="16:00").json()
        drv_c = _post("/transportation/drivers", admin, name=f"{TAG} Driver C").json()
        drv_f = _post("/transportation/drivers", admin, name=f"{TAG} Flex", is_flex=True).json()
        van = _post("/transportation/vehicles", admin, name=f"{TAG} Van", capacity=2).json()
        car = _post("/transportation/vehicles", admin, name=f"{TAG} Car", capacity=1).json()
        assert drv_b["work_days"] == [1, 2, 3, 4] and drv_b["shift_start"] == "08:00"
        assert _post("/transportation/drivers", desk, name="nope").status_code == 403
        names = {d["name"] for d in _get("/transportation/drivers", desk).json()}
        assert drv_a["name"] in names
        # clearing hours with null works
        cleared = requests.patch(f"{API}/transportation/drivers/{drv_f['driver_id']}", headers=admin,
                                 json={"shift_start": None}, timeout=5).json()
        assert cleared.get("shift_start") is None

        # ---- 1. natural resident request (what Aria sends for
        #         "I need transportation for my appointment at 9:30 on the fifth") ----
        r = _post("/transportation/request", resident_id=r1, purpose="doctor appointment",
                  requested_for_date=MON, requested_for_time_label="9:30", source="aria_voice")
        assert r.status_code == 200, r.text
        t1 = r.json()
        assert t1["booked"] is False and t1["duplicate"] is False
        s = _status(r1)
        assert s["found"] and s["status"] == "pending" and s["booked"] is False
        assert s["requested_for_time_label"] == "9:30"
        # re-asking the same day is a re-request, not a second ride
        again = _post("/transportation/request", resident_id=r1, purpose="doctor appointment",
                      requested_for_date=MON, source="aria_voice").json()
        assert again["duplicate"] is True and again["task_id"] == t1["task_id"]
        assert ("re_request", 1, "resident") in await _log(db, t1["task_id"])
        # the public path cannot claim to be the front desk
        assert _post("/transportation/request", resident_id=r1, purpose="x", requested_for_date=MON,
                     source="front_desk").status_code == 403

        # ---- 2. driver hours: B does not work Mondays ----
        res = _post(f"/transportation/request/{t1['task_id']}/assign", desk, start_time="08:45",
                    driver_id=drv_b["driver_id"], vehicle_id=van["vehicle_id"]).json()
        assert res["booked"] is False and res["reason"] == "no_availability"

        # ---- 3. front desk assigns a named driver + vehicle + destination ----
        res = _post(f"/transportation/request/{t1['task_id']}/assign", desk, start_time="08:45",
                    destination="Dr. Patel clinic", driver_id=drv_a["driver_id"], vehicle_id=van["vehicle_id"]).json()
        assert res["booked"] is True, res
        s = _status(r1)
        assert s["booked"] is True and s["run"]["depart_time"] == "08:45"
        assert s["run"]["driver_name"] == drv_a["name"] and s["run"]["vehicle_name"] == van["name"]
        assert "transportation_booked" in _receipt_types(admin, t1["task_id"])
        booked = [e for e in (await db.staff_tasks.find_one({"task_id": t1["task_id"]}))["event_log"] if e["field"] == "ride_booked"]
        assert len(booked) == 1 and "Pickup 08:45" in booked[0]["text"] and drv_a["name"] in booked[0]["text"]
        assert booked[0]["by_name"].endswith("front_desk")

        # ---- 4. staff-entered ride to the same named destination shares the run ----
        t2 = _post("/transportation/staff/request", desk, resident_id=r2, purpose="eye exam",
                   requested_for_date=MON, requested_for_time_label="9:15 appointment",
                   start_time="08:50", destination="dr. patel clinic").json()
        assert t2["booked"] is True and t2["shared"] is True, t2
        task2 = await db.staff_tasks.find_one({"task_id": t2["task_id"]}, {"_id": 0})
        assert task2["source"] == "front_desk"
        assert [f for f, _, _ in await _log(db, t2["task_id"])] == ["ride_booked"]
        # same time, no destination -> never pooled. A is busy, B is off on
        # Mondays, and the flex driver is never auto-picked, so C gets it.
        t3 = _post("/transportation/staff/request", desk, resident_id=r3, purpose="pharmacy",
                   requested_for_date=MON, start_time="08:50", vehicle_id=car["vehicle_id"]).json()
        assert t3["booked"] is True and t3["shared"] is False, t3
        run3 = await db.transport_runs.find_one({"resident_task_ids": t3["task_id"]}, {"_id": 0})
        assert run3["driver_id"] not in (drv_f["driver_id"], drv_b["driver_id"], drv_a["driver_id"])
        # A and C are now both busy at 08:50: auto-booking must NOT fall back
        # to the flex driver, but staff can book the flex driver by name.
        t3b = _post("/transportation/staff/request", desk, resident_id=r2, purpose="haircut",
                    requested_for_date=MON, start_time="08:55").json()
        assert t3b["duplicate"] is True    # r2 already rides on MON - re-request, not a second ride
        auto = _post(f"/transportation/request/{t1['task_id']}/assign", desk, start_time="08:55")
        assert auto.json().get("detail") == "Request is already booked"
        tf = _post("/transportation/staff/request", desk, resident_id=r4, purpose="bank",
                   requested_for_date=TUE, start_time="07:00", driver_id=drv_f["driver_id"],
                   vehicle_id=van["vehicle_id"]).json()
        assert tf["booked"] is True
        assert (await db.transport_runs.find_one({"resident_task_ids": tf["task_id"]}))["driver_id"] == drv_f["driver_id"]
        # auto-booking at the same time: A/C free -> never the flex driver
        tauto = _post("/transportation/staff/request", desk, resident_id=r5, purpose="walk",
                      requested_for_date=TUE, start_time="07:00", vehicle_id=car["vehicle_id"]).json()
        assert tauto["booked"] is True
        assert (await db.transport_runs.find_one({"resident_task_ids": tauto["task_id"]}))["driver_id"] != drv_f["driver_id"]

        # ---- 5. calendar + permissions ----
        cal = _get("/transportation/calendar", desk, date=MON).json()
        day = cal["days"][0]
        shared_run = next(x for x in day["runs"] if len(x["riders"]) == 2)
        assert {x["task_id"] for x in shared_run["riders"]} == {t1["task_id"], t2["task_id"]}
        assert _get("/transportation/calendar", driver_staff, date=MON).status_code == 200
        assert _get("/transportation/calendar", nurse, date=MON).status_code == 403
        assert _post(f"/transportation/runs/{shared_run['run_id']}/depart", nurse).status_code == 403

        # ---- 6. depart + complete (a driver does it) ----
        r = _post(f"/transportation/runs/{shared_run['run_id']}/depart", driver_staff)
        assert r.status_code == 200 and r.json()["riders"] == 2, r.text
        assert _status(r1)["status"] == "in_progress" and _status(r1)["run"]["status"] == "in_progress"
        assert _post(f"/transportation/runs/{shared_run['run_id']}/depart", driver_staff).status_code == 400
        log2 = await _log(db, t2["task_id"])
        assert ("status", "in_progress", f"{TAG} staff transportation") in log2
        assert any(f == "assigned_to" for f, _, _ in log2)          # departing driver takes it
        r = _post(f"/transportation/runs/{shared_run['run_id']}/complete", driver_staff, notes="Both back by 11:20")
        assert r.status_code == 200, r.text
        s = _status(r1)
        assert s["status"] == "completed" and s["run"]["status"] == "completed" and s["run"]["completed_at"]
        types = _receipt_types(admin, t2["task_id"])
        assert "transportation_departed" in types and "transportation_completed" in types
        log2 = await _log(db, t2["task_id"])
        assert [f for f, _, _ in log2][-2:] == ["note", "status"] and log2[-1][1] == "completed"

        # ---- 7. single-rider completion closes that rider's run ----
        r = _post(f"/transportation/request/{t3['task_id']}/complete", desk)
        assert r.status_code == 200, r.text
        assert (await db.transport_runs.find_one({"run_id": run3["run_id"]}))["status"] == "completed"

        # ---- 8. change: staff moves a ride to another day and books it ----
        t4 = _post("/transportation/request", resident_id=r1, purpose="dentist",
                   requested_for_date=TUE, requested_for_time_label="after lunch", source="aria_voice").json()
        r = _post(f"/transportation/staff/request/{t4['task_id']}/change", desk, requested_for_date=WED,
                  requested_for_time_label="1 pm", start_time="12:30", driver_id=drv_b["driver_id"],
                  vehicle_id=car["vehicle_id"])
        assert r.status_code == 200 and r.json()["booked"] is True, r.text
        assert "transportation_changed" in _receipt_types(admin, t4["task_id"])
        assert [f for f, _, _ in await _log(db, t4["task_id"])] == ["ride_changed"]
        # outside B's shift -> not booked
        r = _post(f"/transportation/staff/request/{t4['task_id']}/change", desk, requested_for_date=WED,
                  start_time="17:30", driver_id=drv_b["driver_id"]).json()
        assert r["booked"] is False

        # ---- 9. cancel with a reason; status reflects it, run released ----
        r = _post(f"/transportation/staff/request/{t4['task_id']}/change", desk, requested_for_date=WED,
                  start_time="12:30", driver_id=drv_a["driver_id"], vehicle_id=car["vehicle_id"]).json()
        assert r["booked"] is True
        run4 = (await db.staff_tasks.find_one({"task_id": t4["task_id"]}))["transport_run_id"]
        r = _post(f"/transportation/staff/request/{t4['task_id']}/cancel", desk, reason="Appointment moved by the clinic")
        assert r.status_code == 200, r.text
        s = _status(r1)
        assert s["status"] == "skipped" and s["booked"] is False and s["cancel_reason"] == "Appointment moved by the clinic"
        assert (await db.transport_runs.find_one({"run_id": run4}))["status"] == "cancelled"
        log4 = await db.staff_tasks.find_one({"task_id": t4["task_id"]})
        tail = [(e["field"], e.get("to"), e.get("text")) for e in log4["event_log"]][-2:]
        assert tail == [("note", None, "Appointment moved by the clinic"), ("status", "skipped", None)]
        assert _post(f"/transportation/staff/request/{t4['task_id']}/cancel", desk).status_code == 400

        # ---- 10. closing a ride through the generic task path frees the driver ----
        t5 = _post("/transportation/staff/request", desk, resident_id=r2, purpose="bank", requested_for_date=WED,
                   start_time="10:00", driver_id=drv_a["driver_id"], vehicle_id=van["vehicle_id"]).json()
        assert t5["booked"] is True
        assert _post(f"/tasks/{t5['task_id']}/skip", admin).status_code == 200
        t6 = _post("/transportation/staff/request", desk, resident_id=r3, purpose="library", requested_for_date=WED,
                   start_time="10:00", driver_id=drv_a["driver_id"], vehicle_id=van["vehicle_id"]).json()
        assert t6["booked"] is True, "driver A should be free again after the generic skip"
    finally:
        driver_ids = [d["driver_id"] async for d in db.transport_drivers.find({"name": {"$regex": f"^{TAG}"}})]
        tasks = [t["task_id"] async for t in db.staff_tasks.find({"resident_id": {"$in": residents}})]
        await db.transport_runs.delete_many({"$or": [{"driver_id": {"$in": driver_ids}}, {"resident_task_ids": {"$in": tasks}}]})
        await db.receipts.delete_many({"related_object_id": {"$in": tasks}})
        await db.staff_tasks.delete_many({"task_id": {"$in": tasks}})
        await db.transport_drivers.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.transport_vehicles.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.residents.delete_many({"resident_id": {"$in": residents}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_transportation_lifecycle():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
