"""Pilot 1 Maintenance acceptance: a resident-originated work order, end to end.

Resident says "My sink is leaking." -> Aria's request_staff_help posts to the
public resident-request bus -> maintenance queue -> claim -> acknowledge ->
note -> start -> complete (time spent) -> receipts/history -> the status
Aria reads back is the real lifecycle. Complements
test_maintenance_workorders.py (staff-created work orders, isolation, roster).

Scoped by a TAG room (no resident seeded), so the public status/history
lookups can never see another test's or a real resident's requests.

    TEST_API_BASE=http://127.0.0.1:8094 pytest tests/test_maintenance_resident_loop.py -q
Defaults to http://127.0.0.1:8000. Skips cleanly if unreachable.
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

WORDS = "My sink is leaking."
PW = "mrl-pw-12345678"


def _backend_up() -> bool:
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _status(room):
    return requests.get(f"{API}/tasks/resident-request/status",
                        params={"room": room, "category": "maintenance"}, timeout=5).json()


async def _with_world(body):
    """Seed a maintenance tech + a housekeeper, run `body(ctx)`, clean up."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = f"mrl_{uuid.uuid4().hex[:8]}"
    users = {"tech": "maintenance", "hk": "housekeeping"}
    ctx = {"tag": tag, "room": f"{tag}-3W", "ids": {}}
    for k, dept in users.items():
        ctx["ids"][k] = uid("user")
        await db.users.insert_one({
            "user_id": ctx["ids"][k], "email": f"{tag}_{k}@example.com", "name": f"{tag} {k}",
            "role": "staff", "department": dept, "auth_provider": "jwt",
            "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode(),
            "created_at": now_utc().isoformat(),
        })
    try:
        ctx["tech"] = _login(f"{tag}_tech@example.com")
        ctx["hk"] = _login(f"{tag}_hk@example.com")
        r = requests.post(f"{API}/tasks/resident-request", json={
            "category": "maintenance", "room": ctx["room"], "resident_words": WORDS,
            "summary": WORDS, "priority": "normal", "source": "aria_voice",
        }, timeout=5)
        assert r.status_code == 200, r.text
        assert r.json()["duplicate"] is False and r.json()["status"] == "pending"
        ctx["task_id"] = r.json()["task_id"]
        await body(ctx)
    finally:
        tids = [t["task_id"] for t in await db.staff_tasks.find(
            {"room": {"$regex": f"^{tag}"}}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{tag}"}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.users.delete_many({"email": {"$regex": f"^{tag}_"}})


async def _full_loop(c):
    tid, room, T = c["task_id"], c["room"], c["tech"]

    # Routed to maintenance only: the tech's queue has it, housekeeping's does not.
    mine = {t["task_id"]: t for t in requests.get(f"{API}/tasks", headers=T, timeout=5).json()}
    assert tid in mine and mine[tid]["visibility_role"] == "maintenance"
    assert mine[tid]["resident_words"] == WORDS and mine[tid]["source"] == "aria_voice"
    assert tid not in {t["task_id"] for t in requests.get(f"{API}/tasks", headers=c["hk"], timeout=5).json()}

    s = _status(room)
    assert s["found"] and s["lifecycle"] == "open" and s["what_for"] == WORDS

    # Asking again files no second work order.
    again = requests.post(f"{API}/tasks/resident-request", json={
        "category": "maintenance", "room": room, "resident_words": WORDS, "summary": WORDS, "source": "aria_voice",
    }, timeout=5).json()
    assert again["duplicate"] and again["task_id"] == tid and again["same_issue"]

    # Acknowledge + claim + note: Aria reports who has seen it and their note.
    assert requests.post(f"{API}/tasks/{tid}/acknowledge", headers=T, timeout=5).status_code == 200
    r = requests.post(f"{API}/tasks/{tid}/assign", headers=T, json={"assigned_to": c["ids"]["tech"]}, timeout=5)
    assert r.status_code == 200 and r.json()["assigned_to"] == c["ids"]["tech"]
    note = "Drain seal is worn; replacing it this afternoon."
    assert requests.patch(f"{API}/tasks/{tid}", headers=T, json={"notes": note}, timeout=5).status_code == 200
    s = _status(room)
    assert s["lifecycle"] == "acknowledged" and s["assigned_to_name"] == f"{c['tag']} tech"
    assert "no one has picked it up" not in s["spoken"] and note.rstrip(".") in s["spoken"]

    # Start: Aria says someone is working on it; the note is still available.
    assert requests.post(f"{API}/tasks/{tid}/start", headers=T, timeout=5).json()["status"] == "in_progress"
    s = _status(room)
    assert s["lifecycle"] == "in_progress" and s["started_at"] and s["latest_update"] == note
    assert "working on it" in s["spoken"]

    # Complete: time spent is measured from start, completion note kept.
    done = requests.post(f"{API}/tasks/{tid}/complete", headers=T,
                         json={"notes": "Replaced the seal; no more leak."}, timeout=5).json()
    assert done["status"] == "completed" and done["duration_minutes"] is not None
    assert done["completed_by_name"] == f"{c['tag']} tech"

    # Current status no longer reports it; history answers "did they fix my sink?".
    assert _status(room)["found"] is False
    h = requests.get(f"{API}/tasks/resident-request/history",
                     params={"room": room, "category": "maintenance"}, timeout=5).json()
    assert h["found"] and h["requests"][0]["task_id"] == tid
    assert h["requests"][0]["lifecycle"] == "resolved" and h["requests"][0]["completed_at"]
    assert "taken care of" in h["requests"][0]["spoken"]

    # Receipt trail exists for the request and the claim.
    actions = {rc["action_type"] for rc in requests.get(f"{API}/tasks/{tid}/detail", headers=T, timeout=5).json()["receipts"]}
    assert {"resident_request_created", "resident_request_re_requested", "task_assigned"} <= actions, actions


async def _claim_without_ack(c):
    requests.post(f"{API}/tasks/{c['task_id']}/assign", headers=c["tech"],
                  json={"assigned_to": c["ids"]["tech"]}, timeout=5).raise_for_status()
    s = _status(c["room"])
    assert s["assigned_to_name"] == f"{c['tag']} tech"
    assert "no one has picked it up" not in s["spoken"], s["spoken"]


def test_maintenance_resident_loop():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_with_world(_full_loop))


@pytest.mark.xfail(strict=True, reason="SHARED CORE REQUEST SC-3: a claim does not count as acknowledged, "
                   "so Aria says 'no one has picked it up yet' about a claimed work order")
def test_claimed_work_order_is_not_reported_as_unseen():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_with_world(_claim_without_ack))
