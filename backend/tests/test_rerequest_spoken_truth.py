"""A resident restating a need is recorded, and nothing says staff know about
it before the lifecycle does (demo session rt_2a0kohbb_1791067607790: "My
sink is leaking." on an open, unseen request; no tool call; "the maintenance
team knows about it"; re_request_count stayed 0).

Over HTTP: the restated ask is one re-request on the open request, with a
receipt chained to the request's origin; the spoken status and Layer E agree
with the lifecycle (open = not seen; acknowledged = seen); the prompt Aria is
given says the open request has not been seen and that a restated need must
go through request_staff_help; the companion prompt no longer tells Aria to
say help is on the way.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_rerequest_spoken_truth.py -q
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

TAG = f"rrq_{uuid.uuid4().hex[:8]}"
PW = "rrq-pw-12345678"
SEEN_WORDS = ("know about", "knows about", "has seen", "have seen", "are aware", "on the way")


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


def _ask(room, words):
    return _ok(requests.post(f"{API}/tasks/resident-request", json={
        "category": "maintenance", "room": room, "source": "aria_voice",
        "summary": words, "resident_words": words}, timeout=5))


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    from routes.realtime_operational_context import render_operational_block
    from routes.realtime_companion_prompt import _build_companion_instructions
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    tech_id, room = uid("user"), f"{TAG}-R"
    await db.users.insert_one({
        "user_id": tech_id, "email": f"{TAG}_tech@example.com", "name": f"{TAG} tech", "role": "staff",
        "department": "maintenance", "auth_provider": "jwt", "created_at": now_utc().isoformat(),
        "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()})
    try:
        tok = _ok(requests.post(f"{API}/auth/login", json={"email": f"{TAG}_tech@example.com", "password": PW},
                                timeout=5))["token"]
        tech = {"Authorization": f"Bearer {tok}"}

        first = _ask(room, "sink is leaking")
        tid, origin = first["task_id"], first["receipt_id"]

        # ---------- restated need, unseen request ----------
        again = _ask(room, "My sink is leaking.")
        assert again["duplicate"] is True and again["task_id"] == tid
        assert again["same_issue"] is True                      # same leak, not "something else"
        assert again["times_asked"] == 2
        t = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        assert t["re_request_count"] == 1 and t["last_re_requested_at"]
        assert [e["field"] for e in t["event_log"]] == ["re_request"]
        rec = await db.receipts.find_one({"receipt_id": again["receipt_id"]}, {"_id": 0})
        assert rec["action_type"] == "resident_request_re_requested"
        assert rec["parent_receipt_id"] == origin and rec["correlation_id"] == origin
        assert t["event_log"][0]["receipt_id"] == rec["receipt_id"]

        assert again["lifecycle"] == "open"
        assert "no one has picked it up" in again["spoken"]
        assert not any(w in again["spoken"].lower() for w in SEEN_WORDS)

        st = _ok(requests.get(f"{API}/aria/operational-state", params={"room": room}, timeout=5))
        [item] = [i for i in st["current"] + st["background"] if i["ref"] == tid]
        assert item["lifecycle"] == "open" and item["re_request_count"] == 1
        block = render_operational_block(st)
        assert "staff have not seen it yet" in block
        assert "request_staff_help" in block and "Never answer a stated need from this list alone" in block

        # ---------- after acknowledgement the same restated need says "seen" ----------
        _ok(requests.post(f"{API}/tasks/{tid}/acknowledge", headers=tech, timeout=5))
        third = _ask(room, "the sink is still leaking")
        assert third["duplicate"] is True and third["times_asked"] == 3
        assert third["lifecycle"] == "acknowledged" and "seen" in third["spoken"].lower()
        rec3 = await db.receipts.find_one({"receipt_id": third["receipt_id"]}, {"_id": 0})
        assert rec3["correlation_id"] == origin
        st = _ok(requests.get(f"{API}/aria/operational-state", params={"room": room}, timeout=5))
        assert "staff have not seen it yet" not in render_operational_block(st)

        # ---------- the companion prompt makes no arrival promise ----------
        prompt = await _build_companion_instructions(None)
        assert "help is already on the way" not in prompt
    finally:
        tids = [x["task_id"] for x in await db.staff_tasks.find({"room": room}, {"_id": 0, "task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"room": room})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_rerequest_spoken_truth():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
