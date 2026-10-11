"""careops-therapy-details-001: optional operational details (provider name,
discipline, location) on the canonical therapy StaffTask.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_details.py -q
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
TAG = f"thd_{uuid.uuid4().hex[:8]}"


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
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "thd-pw-12345678"
    people = {"fd": ("front_desk", None), "pt": ("staff", "therapy"), "nurse": ("staff", "nursing"), "admin": ("admin", None)}
    ids, names = {}, {}
    for k, (role, dept) in people.items():
        ids[k], names[k] = uid("user"), f"{TAG} {k}"
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": names[k], "role": role,
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
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}
        d1 = (date.today() + timedelta(days=3)).isoformat()
        d2 = (date.today() + timedelta(days=4)).isoformat()
        t = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "Physical therapy (knee)", "resident_words": "knee session"}, timeout=5))["task_id"]
        details = {"provider_name": "Tess Ortiz PT", "discipline": "physical therapy", "location": "Therapy room, 2nd floor"}

        # unauthorized: nursing staff and the front desk get 403 and nothing is written
        for who in ("nurse", "fd"):
            r = requests.patch(f"{API}/tasks/{t}", headers=H[who], json=details, timeout=5)
            assert r.status_code == 403, (who, r.text)
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert doc.get("provider_name") is None and not doc.get("event_log")
        assert await db.receipts.count_documents({"related_object_id": t}) == 1

        # validation: too long -> 422, nothing written
        r = requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={"discipline": "x" * 61}, timeout=5)
        assert r.status_code == 422, r.text
        assert await db.receipts.count_documents({"related_object_id": t}) == 1

        # therapist sets the details together with the window -> one details receipt + one schedule receipt
        _ok(requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={**details, "requested_for_date": d1, "requested_for_time_label": "10:00 AM"}, timeout=5))
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert doc["provider_name"] == "Tess Ortiz PT" and doc["discipline"] == "physical therapy" and doc["location"] == "Therapy room, 2nd floor"
        dr = await db.receipts.find_one({"related_object_id": t, "action_type": "task_details_updated"}, {"_id": 0})
        assert dr and dr["before_state"]["provider_name"] is None and dr["after_state"]["provider_name"] == "Tess Ortiz PT"
        assert dr["after_state"]["location"] == "Therapy room, 2nd floor" and dr["actor_id"] == ids["pt"] and dr["authority"] == "acts_for:therapy"
        assert await db.receipts.count_documents({"related_object_id": t, "action_type": "task_schedule_updated"}) == 1
        ent = [e for e in doc["event_log"] if e["field"] == "details"]
        assert len(ent) == 1 and ent[0]["receipt_id"] == dr["receipt_id"] and "Tess Ortiz PT" in ent[0]["text"]

        # staff list, resident view and Aria carry the details
        lst = _ok(requests.get(f"{API}/tasks", headers=H["pt"], timeout=5))
        row = next(x for x in lst if x["task_id"] == t)
        assert row["provider_name"] == "Tess Ortiz PT" and row["location"] == "Therapy room, 2nd floor"
        mine = _ok(requests.get(f"{API}/tasks/resident-request/mine", params={"resident_id": rid}, timeout=5))
        me = next(x for x in (mine if isinstance(mine, list) else mine.get("requests", [])) if x["task_id"] == t)
        assert me["provider_name"] == "Tess Ortiz PT" and me["discipline"] == "physical therapy" and me["location"] == "Therapy room, 2nd floor"
        s = _ok(requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid, "category": "therapy"}, timeout=5))
        assert "with Tess Ortiz PT (physical therapy) at Therapy room, 2nd floor" in s["spoken"], s["spoken"]

        # edit one field -> a second details receipt with before/after; unchanged values are not a change
        _ok(requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={"location": "Clinic downtown"}, timeout=5))
        recs = [r async for r in db.receipts.find({"related_object_id": t, "action_type": "task_details_updated"}, {"_id": 0}).sort("created_at", 1)]
        assert len(recs) == 2 and recs[1]["before_state"]["location"] == "Therapy room, 2nd floor" and recs[1]["after_state"]["location"] == "Clinic downtown"
        assert recs[1]["after_state"]["provider_name"] == "Tess Ortiz PT"
        _ok(requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={"location": "Clinic downtown"}, timeout=5))
        assert await db.receipts.count_documents({"related_object_id": t, "action_type": "task_details_updated"}) == 2

        # reschedule keeps the details; clearing a field is receipted and spoken without it
        _ok(requests.patch(f"{API}/tasks/{t}", headers=H["pt"], json={"requested_for_date": d2, "requested_for_time_label": "2:00 PM"}, timeout=5))
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert doc["requested_for_date"] == d2 and doc["provider_name"] == "Tess Ortiz PT" and doc["location"] == "Clinic downtown"
        _ok(requests.patch(f"{API}/tasks/{t}", headers=H["admin"], json={"location": ""}, timeout=5))
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert doc["location"] is None
        s = _ok(requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid, "category": "therapy"}, timeout=5))
        assert "with Tess Ortiz PT (physical therapy)" in s["spoken"] and " at " not in s["spoken"].split("Planned for", 1)[1]
        last = await db.receipts.find_one({"related_object_id": t, "action_type": "task_details_updated"}, {"_id": 0}, sort=[("created_at", -1)])
        assert last["authority"] == "admin_override:admin" and last["before_state"]["location"] == "Clinic downtown" and last["after_state"]["location"] is None
        # the chain stays linked
        chain = [r async for r in db.receipts.find({"related_object_id": t, "action_type": {"$not": {"$regex": "_refused$"}}}, {"_id": 0}).sort("created_at", 1)]
        for prev, cur in zip(chain, chain[1:]):
            assert cur["parent_receipt_id"] == prev["receipt_id"]
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.staff_tasks.delete_many({"room": room})
        await db.receipts.delete_many({"room": room})
        await db.notifications.delete_many({"room": room})
        await db.residents.delete_one({"resident_id": rid})
        await db.departments.delete_many({"_tag": TAG})


@pytest.mark.skipif(not _backend_up(), reason="backend not reachable")
def test_therapy_details():
    assert os.environ.get("MONGO_URL") and os.environ.get("DB_NAME")
    asyncio.run(_run())
