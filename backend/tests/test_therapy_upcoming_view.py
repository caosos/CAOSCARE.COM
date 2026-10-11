"""careops-therapy-upcoming-view-001: date-ordered upcoming schedule over the
canonical StaffTask rows, for therapy staff and for the resident.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_upcoming_view.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"thu_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    from routes.realtime_facility import today_facility_date
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "thu-pw-12345678"
    people = {"fd": ("front_desk", None), "pt": ("staff", "therapy"), "nurse": ("staff", "nursing"), "admin": ("admin", None)}
    ids = {}
    for k, (role, dept) in people.items():
        ids[k] = uid("user")
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"department_id": uid("dept"), "slug": "therapy", "label": "Therapy",
                                         "active": True, "created_at": now_utc().isoformat(), "_tag": TAG})
    room = f"{TAG}-R"
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "preferred_name": "Pat", "room": room,
                                   "created_at": now_utc().isoformat()})
    today = date.fromisoformat(today_facility_date())
    d1, d2, past = (today + timedelta(days=1)).isoformat(), (today + timedelta(days=2)).isoformat(), (today - timedelta(days=1)).isoformat()
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}

        def ask(summary):
            return _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
                "category": "therapy", "resident_id": rid, "source": "front_desk",
                "summary": summary, "resident_words": summary}, timeout=5))["task_id"]

        def plan(t, dte, label, **details):
            _ok(requests.patch(f"{API}/tasks/{t}", headers=H["pt"],
                               json={"requested_for_date": dte, "requested_for_time_label": label, **details}, timeout=5))

        a = ask("Afternoon PT (knee)"); plan(a, d2, "2:00 PM", provider_name="Tess Ortiz PT", discipline="physical therapy", location="Therapy room")
        b = ask("Morning PT (hip)");    plan(b, d2, "9:30 AM")
        c = ask("Speech session");      plan(c, d1, "around 3 pm", discipline="speech therapy")
        e = ask("Untimed visit");       plan(e, d1, "afternoon")        # no clock time: after the timed ones that day
        unplanned = ask("Not planned yet")
        done = ask("Already done");     plan(done, d1, "8:00 AM")
        _ok(requests.post(f"{API}/tasks/{done}/complete", headers=H["pt"], json={"notes": "attended"}, timeout=5))
        old = ask("Yesterday's visit"); plan(old, past, "10:00 AM")
        ride = _ok(requests.post(f"{API}/tasks/{a}/ride", headers=H["pt"], timeout=5))["task_id"]

        # --- staff view: order, content, visibility ---
        # the department schedule lists every resident's planned work; assert on this test's resident only
        def mine(view):
            return [i["task_id"] for i in view["items"] if i.get("resident_id") == rid]
        v1 = _ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"], params={"department": "therapy", "days": 14}, timeout=5))
        order = mine(v1)
        assert order == [c, e, b, a], order           # d1: 3 pm then untimed; d2: 9:30 then 2:00
        assert unplanned not in order and done not in order and old not in order and ride not in order
        byid = {i["task_id"]: i for i in v1["items"]}
        assert byid[a]["provider_name"] == "Tess Ortiz PT" and byid[a]["location"] == "Therapy room"
        assert byid[a]["lifecycle"] == "open" and byid[a]["spoken"]
        assert byid[a]["ride"] and byid[a]["ride"]["task_id"] == ride and byid[a]["ride"]["booked"] is False
        assert byid[b]["ride"] is None
        v2 = _ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"], params={"department": "therapy", "days": 14}, timeout=5))
        assert mine(v2) == order                                      # stable across reads

        # a claim changes lifecycle, not the order
        _ok(requests.post(f"{API}/tasks/{b}/assign", headers=H["pt"], json={"assigned_to": ids["pt"]}, timeout=5))
        v3 = _ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"], params={"department": "therapy"}, timeout=5))
        assert mine(v3) == order
        assert {i["task_id"]: i for i in v3["items"]}[b]["lifecycle"] == "acknowledged"

        # authorization: nursing staff see nothing of therapy; front desk and admin see it; anonymous 401
        assert _ok(requests.get(f"{API}/tasks/upcoming", headers=H["nurse"], params={"department": "therapy"}, timeout=5))["items"] == []
        nurse_all = _ok(requests.get(f"{API}/tasks/upcoming", headers=H["nurse"], timeout=5))["items"]
        assert not any(i["task_id"] in order for i in nurse_all)
        for who in ("fd", "admin"):
            got = [i["task_id"] for i in _ok(requests.get(f"{API}/tasks/upcoming", headers=H[who], params={"department": "therapy"}, timeout=5))["items"]]
            assert [t for t in got if t in order] == order, who
        assert requests.get(f"{API}/tasks/upcoming", timeout=5).status_code == 401
        # days window: 0 days = today only -> none of these
        assert mine(_ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"], params={"department": "therapy", "days": 0}, timeout=5))) == []

        # --- resident view: same order, resident-safe fields, ride truth ---
        rv = _ok(requests.get(f"{API}/tasks/resident-request/upcoming", params={"resident_id": rid}, timeout=5))
        assert [i["task_id"] for i in rv["items"]] == order          # the linked ride is not a row of its own
        # a standalone ride (not linked to an appointment) IS listed for the resident
        solo = _ok(requests.post(f"{API}/transportation/staff/request", headers=H["fd"], json={
            "resident_id": rid, "purpose": "pharmacy run", "requested_for_date": d1, "requested_for_time_label": "11:00 AM"}, timeout=5))
        solo_id = solo.get("task_id") or solo.get("request", {}).get("task_id")
        rv2 = [i["task_id"] for i in _ok(requests.get(f"{API}/tasks/resident-request/upcoming", params={"resident_id": rid}, timeout=5))["items"]]
        assert solo_id in rv2 and rv2.index(solo_id) == 0, rv2     # d1 11:00 AM sorts before d1 "around 3 pm"
        ra = {i["task_id"]: i for i in rv["items"]}[a]
        assert ra["scheduled_date"] == d2 and ra["scheduled_time_label"] == "2:00 PM"
        assert ra["provider_name"] == "Tess Ortiz PT" and ra["location"] == "Therapy room"
        assert "assigned_to" not in ra and "visibility_role" not in ra       # resident-safe view only
        assert ra["ride"]["task_id"] == ride and ra["ride"]["booked"] is False
        assert ra["spoken"].startswith("No one has picked") or "Planned for 2:00 PM" in ra["spoken"]
        by_room = _ok(requests.get(f"{API}/tasks/resident-request/upcoming", params={"room": room}, timeout=5))
        assert [i["task_id"] for i in by_room["items"]] == rv2          # room scoping gives the same list (incl. the standalone ride)
        assert requests.get(f"{API}/tasks/resident-request/upcoming", timeout=5).status_code == 400
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.departments.delete_many({"_tag": TAG})
        await db.residents.delete_many({"resident_id": rid})
        tids = [t["task_id"] for t in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_upcoming_schedule_order_authorization_and_resident_view():
    asyncio.run(_run())
