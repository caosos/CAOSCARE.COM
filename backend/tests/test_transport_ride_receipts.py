"""SC-15: every transportation ride step is a lifecycle transition with its
own receipt chained to the ride's origin (SIM-0 receipt law).

Over HTTP against a running backend, own synthetic fixtures on 2031 dates:
- a front-desk ride: staff request (booked) -> staff change -> depart ->
  complete;
- an Aria ride: public request (not booked) -> front desk assigns ->
  Aria change -> depart -> complete;
- an Aria ride that is cancelled;
- a step on a closed ride is refused (400) and the refusal is recorded.
Each step: one receipt, parent = previous receipt, workflow id = origin,
actor + identity basis + authority, before = previous after; every
event_log entry carries an existing receipt id. Aria's transport status
answer is checked at each stage.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_transport_ride_receipts.py -q
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

TAG = f"trr_{uuid.uuid4().hex[:8]}"
PW = "trr-pw-12345678"
from datetime import date as _date, timedelta as _td
_BASE = _date.today() + _td(days=((0 - _date.today().weekday()) % 7) + 7)
DAY1, DAY2, DAY3 = ((_BASE + _td(days=i)).isoformat() for i in range(3))


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _post(path, headers=None, **body):
    return requests.post(f"{API}{path}", headers=headers or {}, json=body, timeout=10)


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


def _status(resident_id):
    return _ok(requests.get(f"{API}/transportation/request/status", params={"resident_id": resident_id}, timeout=5))


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    users, H = {}, {}
    for k, role, dept in (("admin", "admin", None), ("desk", "front_desk", None),
                          ("driver", "staff", "transportation")):
        users[k] = uid("user")
        email = f"{TAG}_{k}@example.com"
        await db.users.insert_one({
            "user_id": users[k], "email": email, "name": f"{TAG} {k}", "role": role, "department": dept,
            "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()})
        H[k] = {"Authorization": f"Bearer {_ok(_post('/auth/login', email=email, password=PW))['token']}"}
    res = []
    for i in range(3):
        rid = uid("res")
        await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident {i}",
                                       "room": f"{TAG}-{i}", "created_at": now_utc().isoformat()})
        res.append(rid)
    fd_res, aria_res, cancel_res = res

    async def chain(tid):
        return await db.receipts.find({"related_object_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(50)

    async def task(tid):
        return await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})

    async def assert_chain(tid, expected):
        rs = await chain(tid)
        assert [r["action_type"] for r in rs] == [a for a, _ in expected], [r["action_type"] for r in rs]
        origin = rs[0]
        assert origin["receipt_id"] == origin["correlation_id"] and origin["parent_receipt_id"] is None
        for r, (_, (actor_id, basis, authority)) in zip(rs, expected):
            assert r["actor_id"] == actor_id and r["identity_basis"] == basis, r
            assert r["authority"] == authority, r
        for prev, r in zip(rs, rs[1:]):
            assert r["parent_receipt_id"] == prev["receipt_id"] and r["correlation_id"] == origin["receipt_id"]
            assert r["before_state"] == prev["after_state"]
        t = await task(tid)
        ids = {e.get("receipt_id") for e in t["event_log"]}
        assert None not in ids and ids == {r["receipt_id"] for r in rs[1:]}
        return rs

    try:
        _ok(_post("/transportation/drivers", H["admin"], name=f"{TAG} Driver"))
        _ok(_post("/transportation/vehicles", H["admin"], name=f"{TAG} Van", capacity=2))
        desk = (users["desk"], "authenticated", "front_desk_transport")
        driver = (users["driver"], "authenticated", "acts_for:transportation")

        # ---------- front-desk ride ----------
        fd = _ok(_post("/transportation/staff/request", H["desk"], resident_id=fd_res, purpose="dentist",
                       requested_for_date=DAY1, start_time="09:00"))
        assert fd["booked"] is True
        _ok(_post(f"/transportation/staff/request/{fd['task_id']}/change", H["desk"],
                  requested_for_date=DAY1, start_time="10:00"))
        fd_run = (await task(fd["task_id"]))["transport_run_id"]
        _ok(_post(f"/transportation/runs/{fd_run}/depart", H["driver"]))
        assert _status(fd_res)["status"] == "in_progress"
        _ok(_post(f"/transportation/runs/{fd_run}/complete", H["driver"], notes="Dropped off"))
        rs = await assert_chain(fd["task_id"], [
            ("transportation_requested", desk), ("transportation_booked", desk), ("transportation_changed", desk),
            ("transportation_departed", driver), ("transportation_completed", driver)])
        assert rs[0]["channel"] == "front_desk" and rs[-1]["after_state"]["status"] == "completed"

        # ---------- Aria ride ----------
        claim = (aria_res, "unverified_room_claim", "public_resident_bus")
        ar = _ok(_post("/transportation/request", resident_id=aria_res, purpose="pharmacy",
                       requested_for_date=DAY2, requested_for_time_label="morning", source="aria_voice"))
        assert ar["booked"] is False
        s = _status(aria_res)
        assert s["found"] and s["status"] == "pending" and s["booked"] is False      # Aria: requested, not booked
        assert _ok(_post(f"/transportation/request/{ar['task_id']}/assign", H["desk"], start_time="11:00"))["booked"]
        assert _status(aria_res)["booked"] is True                                   # Aria: now booked
        _ok(_post(f"/transportation/request/{ar['task_id']}/change",
                  requested_for_date=DAY2, start_time="13:00"))
        ar_run = (await task(ar["task_id"]))["transport_run_id"]
        _ok(_post(f"/transportation/runs/{ar_run}/depart", H["driver"]))
        _ok(_post(f"/transportation/runs/{ar_run}/complete", H["driver"]))
        await assert_chain(ar["task_id"], [
            ("transportation_requested", claim), ("transportation_booked", desk),
            ("transportation_changed", claim), ("transportation_departed", driver),
            ("transportation_completed", driver)])
        s = _status(aria_res)                       # Aria: the most recent closed ride, said as completed
        assert s["found"] and s["status"] == "completed" and s["run"]["status"] == "completed"

        # ---------- cancel ----------
        cx = _ok(_post("/transportation/request", resident_id=cancel_res, purpose="library",
                       requested_for_date=DAY3, source="aria_voice"))
        _ok(_post(f"/transportation/staff/request/{cx['task_id']}/cancel", H["desk"], reason="family driving"))
        rs = await assert_chain(cx["task_id"], [
            ("transportation_requested", (cancel_res, "unverified_room_claim", "public_resident_bus")),
            ("transportation_cancelled", desk)])
        assert rs[-1]["after_state"]["status"] == "skipped"
        s = _status(cancel_res)                     # Aria: cancelled, not booked, with the reason
        assert s["status"] == "skipped" and s["booked"] is False and s["cancel_reason"] == "family driving"

        # ---------- a step on a closed ride: refused (400) and recorded (SC-14) ----------
        before = await task(cx["task_id"])
        assert _post(f"/transportation/staff/request/{cx['task_id']}/cancel", H["desk"]).status_code == 400
        assert _post(f"/transportation/request/{fd['task_id']}/complete", H["driver"]).status_code == 400
        assert await task(cx["task_id"]) == before
        assert (await chain(cx["task_id"]))[-1]["action_type"] == "task_cancel_refused"
        assert (await chain(fd["task_id"]))[-1]["action_type"] == "task_complete_refused"
    finally:
        tids = [t["task_id"] for t in await db.staff_tasks.find(
            {"resident_id": {"$in": res}}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"resident_id": {"$in": res}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
            await db.transport_runs.delete_many({"resident_task_ids": {"$in": tids}})
        await db.transport_drivers.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.transport_vehicles.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.residents.delete_many({"resident_id": {"$in": res}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_transport_ride_receipts():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
