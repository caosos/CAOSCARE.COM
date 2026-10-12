"""careops-frontdesk-callback-contact-fields-001: a front-desk callback request
can carry an optional callback phone (validated, normalized) and preferred
callback time/window on the same StaffTask - no callback entity. Only staff
entry (source front_desk) may set them; the public resident bus is refused.
Staff edit them through the existing details path (receipted, phone masked in
history; other departments 403). Residents and Aria never see them, and
nothing claims a call happened. Uses the backend test gate's server.
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
TAG = f"cbf_{uuid.uuid4().hex[:8]}"


def _up():
    try:
        return requests.get(f"{API}/health", timeout=3).ok
    except Exception:
        return False


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "cbf-pw-12345678"
    for k, (role, dept) in {"fd": ("front_desk", None), "nurse": ("staff", "nursing")}.items():
        await db.users.insert_one({"user_id": uid("user"), "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    room = f"{TAG}-R"
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": room, "created_at": now_utc().isoformat()})
    tids = []
    try:
        H = {k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
             for k in ("fd", "nurse")}
        base = {"category": "front_desk", "resident_id": rid, "source": "front_desk", "summary": "Callback about the September bill"}
        # invalid input refused, nothing stored
        for bad in ({"callback_phone": "12"}, {"callback_phone": "call my daughter"}, {"callback_window": "x" * 81}):
            r = requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={**base, **bad}, timeout=5)
            assert r.status_code == 422, (bad, r.status_code, r.text)
        assert await db.staff_tasks.count_documents({"resident_id": rid}) == 0
        # the public resident bus may not set them
        r = requests.post(f"{API}/tasks/resident-request", json={**base, "source": "kiosk_button", "room": room,
                                                                  "callback_phone": "555-010-4321"}, timeout=5)
        assert r.status_code == 422, (r.status_code, r.text)
        assert await db.staff_tasks.count_documents({"resident_id": rid}) == 0
        # staff entry: stored normalized on the same request
        r = requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            **base, "callback_phone": "(555) 010-4321", "callback_window": "  after 2 pm  "}, timeout=5)
        assert r.status_code == 200, r.text
        tid = r.json()["task_id"]; tids.append(tid)
        t = await db.staff_tasks.find_one({"task_id": tid})
        assert t["callback_phone"] == "+15550104321" and t["callback_window"] == "after 2 pm"
        assert t["visibility_role"] == "administration" and t["status"] == "pending"
        # staff detail read has them; residents / Aria do not
        d = requests.get(f"{API}/tasks/{tid}/detail", headers=H["fd"], timeout=5).json()
        assert d["task"]["callback_phone"] == "+15550104321"
        s = requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid}, timeout=5).json()
        assert s["found"] and "callback" not in str({k: v for k, v in s.items() if k != "spoken"}).replace("Callback about", "")
        assert "0104321" not in str(s) and "after 2 pm" not in str(s)
        # edit through the existing details path: receipted, phone masked in history
        r = requests.patch(f"{API}/tasks/{tid}", headers=H["fd"], json={"callback_window": "tomorrow morning", "callback_phone": "+44 20 7946 0958"}, timeout=5)
        assert r.status_code == 200, r.text
        t = await db.staff_tasks.find_one({"task_id": tid})
        assert t["callback_window"] == "tomorrow morning" and t["callback_phone"] == "+442079460958"
        rc = await db.receipts.find_one({"related_object_id": tid, "action_type": "task_details_updated"}, sort=[("created_at", -1)])
        assert rc and rc["authority"] == "acts_for:administration"
        ev = [e for e in t["event_log"] if e.get("field") == "details"][-1]
        assert "0958" in ev["text"] and "2079460958" not in ev["text"], ev["text"]
        assert requests.patch(f"{API}/tasks/{tid}", headers=H["fd"], json={"callback_phone": "nope"}, timeout=5).status_code == 422
        # another department may not edit; clearing works; no call claimed anywhere
        assert requests.patch(f"{API}/tasks/{tid}", headers=H["nurse"], json={"callback_window": "now"}, timeout=5).status_code == 403
        assert requests.patch(f"{API}/tasks/{tid}", headers=H["fd"], json={"callback_phone": ""}, timeout=5).status_code == 200
        t = await db.staff_tasks.find_one({"task_id": tid})
        assert t.get("callback_phone") is None and t["status"] == "pending"
        assert await db.receipts.count_documents({"related_object_id": tid, "action_type": {"$regex": "call\\."}}) == 0
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"resident_id": rid})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


def test_callback_contact_fields():
    if os.environ.get("DB_NAME") in ("caoscare", "", None):
        pytest.skip("point DB_NAME at a scratch database")
    if not _up():
        pytest.skip(f"backend not reachable at {API}")
    asyncio.new_event_loop().run_until_complete(_run())
