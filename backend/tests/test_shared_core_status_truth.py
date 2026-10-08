"""Shared-core SC-3..SC-7: what Aria says about a request matches the record.

SC-3 a claim/assignment by a real staff member is never "no one has picked
     it up yet" (nursing claim, maintenance admin-assignment), and Layer E
     agrees.
SC-4 in progress: the latest staff note is in the spoken status; resolved:
     who completed it and their closing note.
SC-5 the note is spoken with its real time (the same label the view
     returns), and repeat asks are counted in all (first ask included).
SC-6 front desk claims, assigns (to front desk colleagues) and notes
     Administration requests; cannot act on other departments; department
     staff behaviour unchanged.
SC-7 a time typed by an authenticated front-desk user is accepted; the
     same time from Aria voice is still rejected.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_shared_core_status_truth.py -q
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

TAG = f"sst_{uuid.uuid4().hex[:8]}"
PICKED_UP = "no one has picked it up"


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


def _ask(room, category, words, headers=None, source="aria_voice"):
    return _ok(requests.post(f"{API}/tasks/resident-request", headers=headers, json={
        "category": category, "room": room, "source": source, "summary": words, "resident_words": words,
    }, timeout=5))


def _status(room):
    return _ok(requests.get(f"{API}/tasks/resident-request/status", params={"room": room}, timeout=5))


def _layer_e_lifecycle(room, task_id, headers):
    # admin-only since RQ-025
    st = _ok(requests.get(f"{API}/aria/operational-state", params={"room": room}, headers=headers, timeout=5))
    items = [i for i in st["current"] + st["background"] if i.get("ref") == task_id]
    return items[0]["lifecycle"] if items else None


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    pw = "sst-pw-12345678"
    people = {
        "admin": ("admin", None), "nurse": ("staff", "nursing"), "tech": ("staff", "maintenance"),
        "fd1": ("front_desk", None), "fd2": ("front_desk", None),
    }
    ids, names = {}, {}
    for k, (role, dept) in people.items():
        ids[k], names[k] = uid("user"), f"{TAG} {k}"
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": names[k], "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}

        # ---------- Nursing: claim without acknowledge (SC-3), note (SC-4/5), repeat (SC-5) ----------
        room = f"{TAG}-N"
        nt = _ask(room, "nursing", "I need help going to the bathroom")["task_id"]
        assert PICKED_UP in _status(room)["spoken"]              # genuinely unseen: says so
        _ok(requests.post(f"{API}/tasks/{nt}/assign", headers=H["nurse"],
                          json={"assigned_to": ids["nurse"]}, timeout=5))
        s = _status(room)
        assert s["lifecycle"] == "acknowledged" and s["acknowledged"] is True
        assert PICKED_UP not in s["spoken"] and names["nurse"] in s["spoken"]
        assert _layer_e_lifecycle(room, nt, H["admin"]) == "acknowledged"        # Layer E agrees

        again = _ask(room, "nursing", "I still need help going to the bathroom")
        assert again["duplicate"] and again["re_request_count"] == 1 and again["times_asked"] == 2
        assert PICKED_UP not in again["spoken"]
        assert _status(room)["times_asked"] == 2

        _ok(requests.post(f"{API}/tasks/{nt}/start", headers=H["nurse"], timeout=5))
        _ok(requests.patch(f"{API}/tasks/{nt}", headers=H["nurse"], json={"notes": "on my way with the walker"}, timeout=5))
        s = _status(room)
        assert s["lifecycle"] == "in_progress"
        assert "on my way with the walker" in s["spoken"]                       # SC-4
        label = s["latest_update_at"]["label"]
        assert label and f"({label})" in s["spoken"]                            # SC-5: real note time
        assert "no timestamp" not in s["spoken"]

        _ok(requests.post(f"{API}/tasks/{nt}/complete", headers=H["nurse"],
                          json={"notes": "resident back in bed"}, timeout=5))
        h = _ok(requests.get(f"{API}/tasks/resident-request/history", params={"room": room}, timeout=5))
        done = next(x for x in h["requests"] if x["task_id"] == nt)
        assert f"taken care of by {names['nurse']}" in done["spoken"]           # SC-4: who finished it
        assert "resident back in bed" in done["spoken"]                          # SC-4: closing note

        # ---------- Maintenance: admin assigns a tech (not a claim) (SC-3) ----------
        mroom = f"{TAG}-M"
        mt = _ask(mroom, "maintenance", "my sink is leaking")["task_id"]
        _ok(requests.post(f"{API}/tasks/{mt}/assign", headers=H["admin"], json={"assigned_to": ids["tech"]}, timeout=5))
        s = _status(mroom)
        assert s["lifecycle"] == "acknowledged" and PICKED_UP not in s["spoken"]
        assert f"{names['tech']} has taken it on" in s["spoken"]
        # unassigning puts it back to genuinely unseen - the owner rule is not sticky
        _ok(requests.post(f"{API}/tasks/{mt}/assign", headers=H["admin"], json={"assigned_to": None}, timeout=5))
        assert PICKED_UP in _status(mroom)["spoken"]
        # maintenance staff permissions unchanged
        assert requests.post(f"{API}/tasks/{mt}/assign", headers=H["tech"],
                             json={"assigned_to": ids["nurse"]}, timeout=5).status_code == 403
        _ok(requests.post(f"{API}/tasks/{mt}/assign", headers=H["tech"], json={"assigned_to": ids["tech"]}, timeout=5))

        # ---------- Front desk (SC-6, SC-7) ----------
        froom = f"{TAG}-F"
        cb = _ask(froom, "front_desk", "Please call my daughter back at 3 PM", headers=H["fd1"],
                  source="front_desk")                                          # SC-7: accepted
        ft = cb["task_id"]
        voice = requests.post(f"{API}/tasks/resident-request", json={
            "category": "front_desk", "room": f"{TAG}-V", "source": "aria_voice",
            "summary": "call my daughter back at 3 PM"}, timeout=5)
        assert voice.status_code == 422                                          # guard kept for Aria

        roster = _ok(requests.get(f"{API}/staff/assignable", headers=H["fd1"],
                                  params={"department": "administration"}, timeout=5))
        assert {ids["fd1"], ids["fd2"]} <= {u["user_id"] for u in roster}
        assert requests.get(f"{API}/staff/assignable", headers=H["fd1"],
                            params={"department": "maintenance"}, timeout=5).status_code == 403

        _ok(requests.post(f"{API}/tasks/{ft}/assign", headers=H["fd1"], json={"assigned_to": ids["fd2"]}, timeout=5))
        _ok(requests.patch(f"{API}/tasks/{ft}", headers=H["fd2"], json={"notes": "left a voicemail"}, timeout=5))
        # (resident status covers resident-originated requests only, so check the record)
        d = _ok(requests.get(f"{API}/tasks/{ft}/detail", headers=H["fd1"], timeout=5))["task"]
        assert d["assigned_to"] == ids["fd2"] and d["notes"] == "left a voicemail"
        assert d["visibility_role"] == "administration"
        assert [e["field"] for e in d["event_log"]] == ["assigned_to", "note"]
        # front desk cannot act on another department's request, or assign outside it
        assert requests.post(f"{API}/tasks/{mt}/assign", headers=H["fd1"],
                             json={"assigned_to": ids["fd1"]}, timeout=5).status_code == 403
        assert requests.post(f"{API}/tasks/{ft}/assign", headers=H["fd1"],
                             json={"assigned_to": ids["tech"]}, timeout=5).status_code == 403
        # nursing staff cannot act on an Administration request
        assert requests.post(f"{API}/tasks/{ft}/assign", headers=H["nurse"],
                             json={"assigned_to": ids["nurse"]}, timeout=5).status_code == 403
    finally:
        tids = [t["task_id"] for t in await db.staff_tasks.find(
            {"room": {"$regex": f"^{TAG}"}}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{TAG}"}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.receipts.delete_many({"room": {"$regex": f"^{TAG}"}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_shared_core_status_truth():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
