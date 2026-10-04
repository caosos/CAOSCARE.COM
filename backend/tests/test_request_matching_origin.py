"""Voice-bridge spike fixes (2026-10-03):

1. A repeat ask joins an open request only when it is about the same thing:
   "my sink is still leaking" re-asks the sink request; "my TV remote
   stopped working" is a new request, never merged into the sink.
2. A resident request has an auditable origin: no room and no resident is
   refused; a room claim's origin receipt is labelled unverified; only a
   registered endpoint of the same room may carry registered_endpoint:<id>.
3. A reply that says help is coming is never allowed for a claimed or
   assigned maintenance request (Michael 2026-10-04: no movement evidence);
   it is replaced with the true stage. Full matrix:
   tests/test_arrival_claim_guard.py.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_request_matching_origin.py -q
"""
import asyncio
import json
import os
import subprocess
import sys
import uuid

import bcrypt
import pytest
import requests

from routes.request_matching import content_tokens, match_open_request

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = f"rmo_{uuid.uuid4().hex[:8]}"


def test_matching_rules():
    sink = {"task_id": "sink", "resident_words": "My sink is leaking."}
    lamp = {"task_id": "lamp", "resident_words": "The reading lamp flickers"}
    assert match_open_request("My sink is still leaking", [sink])["task_id"] == "sink"
    assert match_open_request("My TV remote stopped working", [sink]) is None
    assert match_open_request("the lamp keeps flickering", [sink, lamp])["task_id"] == "lamp"
    assert match_open_request("Can you ask them again?", [lamp, sink])["task_id"] == "lamp"   # newest first
    assert match_open_request("anything", []) is None
    assert content_tokens("is anyone coming?") == set()


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


def _ask(room, category, words):
    return requests.post(f"{API}/tasks/resident-request", json={
        "category": category, "room": room, "source": "aria_voice", "summary": words,
        "resident_words": words}, timeout=5)


def _in_process(code: str) -> dict:
    """Run app code that uses the shared deps.db client in its own process
    (one event loop per process)."""
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=os.environ,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    room, kiosk = f"{TAG}-R", f"kio_{TAG}"
    tech, pw = uid("user"), "rmo-pw-12345678"
    await db.users.insert_one({"user_id": tech, "email": f"{TAG}_tech@example.com", "name": f"{TAG} tech",
                               "role": "staff", "department": "maintenance", "auth_provider": "jwt",
                               "created_at": now_utc().isoformat(),
                               "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    await db.kiosks.insert_one({"kiosk_id": kiosk, "room": room, "name": TAG})
    try:
        # ---------- 1. same request vs distinct request ----------
        sink = _ok(_ask(room, "maintenance", "My sink is leaking."))
        assert not sink["duplicate"]
        again = _ok(_ask(room, "maintenance", "My sink is still leaking, can you ask again?"))
        assert again["duplicate"] and again["task_id"] == sink["task_id"] and again["times_asked"] == 2
        tv = _ok(_ask(room, "maintenance", "My TV remote stopped working."))
        assert not tv["duplicate"] and tv["task_id"] != sink["task_id"]
        s = await db.staff_tasks.find_one({"task_id": sink["task_id"]})
        t = await db.staff_tasks.find_one({"task_id": tv["task_id"]})
        assert s["re_request_count"] == 1 and t.get("re_request_count", 0) == 0
        assert "remote" not in json.dumps(s.get("event_log", []))       # TV words never landed on the sink
        generic = _ok(_ask(room, "maintenance", "Can you ask them again?"))
        assert generic["duplicate"] and generic["task_id"] == tv["task_id"]   # newest open request

        # ---------- 2. origin ----------
        origin = await db.receipts.find_one({"receipt_id": sink["receipt_id"]})
        assert origin["action_type"] == "resident_request_created"
        assert origin["authority"] == "public_resident_bus"
        assert origin["identity_basis"] == "unverified_room_claim" and origin["result_label"] == "unverified"
        r = requests.post(f"{API}/tasks/resident-request", json={
            "category": "maintenance", "source": "aria_voice", "summary": "x"}, timeout=5)
        assert r.status_code == 422                                      # no room, no resident: refused
        res = _in_process(f"""
import asyncio, json
from fastapi import HTTPException
from routes.resident_requests import ResidentRequestInput, create_resident_request
from deps import db
async def main():
    ok = await create_resident_request(ResidentRequestInput(category="housekeeping", room="{room}",
        source="aria_voice", summary="fresh towels please", resident_words="fresh towels please",
        conversation_session_id="vb_{TAG}"), origin_authority="registered_endpoint:{kiosk}")
    rc = await db.receipts.find_one({{"receipt_id": ok["receipt_id"]}}, {{"_id": 0}})
    codes = []
    for bad in ("registered_endpoint:kio_nope", "admin_override:owner"):
        try:
            await create_resident_request(ResidentRequestInput(category="housekeeping", room="{room}",
                source="aria_voice", summary="towels", resident_words="towels"), origin_authority=bad)
            codes.append(200)
        except HTTPException as e:
            codes.append(e.status_code)
    print(json.dumps({{"authority": rc["authority"], "label": rc["result_label"], "codes": codes}}))
asyncio.run(main())
""")
        assert res["authority"] == f"registered_endpoint:{kiosk}" and res["label"] == "unverified"
        assert res["codes"] == [403, 403]

        # ---------- 3. arrival claims need movement evidence, not a claim ----------
        guard = """
import asyncio, json
from routes.arrival_claim_guard import guard_reply
async def main():
    a = await guard_reply("I've sent that to maintenance. It's on its way!", ["{tid}"])
    b = await guard_reply("I've sent that to maintenance.", ["{tid}"])
    print(json.dumps({{"a": a, "b": b}}))
asyncio.run(main())
"""
        before = _in_process(guard.format(tid=tv["task_id"]))
        assert "on its way" not in before["a"][0] and "I've requested help." in before["a"][0]
        assert before["a"][1] == ["It's on its way!"]
        assert before["b"] == ["I've sent that to maintenance.", []]      # no claim made: untouched
        H = {"Authorization": "Bearer " + _ok(requests.post(f"{API}/auth/login", json={
            "email": f"{TAG}_tech@example.com", "password": pw}, timeout=5))["token"]}
        _ok(requests.post(f"{API}/tasks/{tv['task_id']}/assign", headers=H, json={"assigned_to": tech}, timeout=5))
        after = _in_process(guard.format(tid=tv["task_id"]))
        # an assignment is not movement: still removed, replaced with the true stage
        assert after["a"] == ["I've sent that to maintenance. A staff member has accepted your request.",
                              ["It's on its way!"]]
    finally:
        await db.users.delete_one({"user_id": tech})
        await db.kiosks.delete_one({"kiosk_id": kiosk})


@pytest.mark.skipif(not _backend_up(), reason=f"backend not reachable at {API}")
def test_request_matching_origin_and_arrival_guard():
    asyncio.run(_run())
