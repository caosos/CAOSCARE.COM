"""RQ-028: POST /api/memory/realtime-turn needs a live Aria lease (or a very
recent release) for that resident + session. In-process, scratch DB, no OpenAI.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_rq028_test \
      JWT_SECRET=x pytest tests/test_rq028_memory_turn_auth.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import now_utc  # noqa: E402
from routes import realtime_memory_ingest as ingest  # noqa: E402

TAG = f"rq028_{uuid.uuid4().hex[:8]}"
RES, OTHER = f"{TAG}_res", f"{TAG}_other"
SID = f"{TAG}_sess"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def post(body):
    a = FastAPI()
    a.include_router(ingest.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=a), base_url="http://test") as c:
            return await c.post("/api/memory/realtime-turn", json=body)
    return run(go())


def turn(**kw):
    return {"resident_id": RES, "session_id": SID, "role": "user", "text": "hello there", **kw}


def stored(rid=RES):
    return run(db.conversations.count_documents({"resident_id": rid}))


def lease(status="active", age=0):
    run(db.resident_aria_leases.insert_one({
        "room": f"{TAG}_room", "resident_id": RES, "session_id": SID, "status": status,
        "last_seen_at": (now_utc() - timedelta(seconds=age)).isoformat()}))


def released(seconds_ago):
    run(db.resident_aria_lease_events.insert_one({
        "at": (now_utc() - timedelta(seconds=seconds_ago)).isoformat(), "event": "released",
        "lease": {"resident_id": RES, "session_id": SID, "room": f"{TAG}_room"}}))


@pytest.fixture(autouse=True)
def clean():
    async def wipe():
        await db.conversations.delete_many({"resident_id": {"$regex": f"^{TAG}"}})
        await db.resident_aria_leases.delete_many({"resident_id": {"$regex": f"^{TAG}"}})
        await db.resident_aria_lease_events.delete_many({"lease.resident_id": {"$regex": f"^{TAG}"}})
    run(wipe())
    yield
    run(wipe())


def test_no_lease_refused_nothing_stored():
    assert post(turn()).status_code == 403
    assert stored() == 0


def test_wrong_resident_or_session_refused():
    lease()
    assert post(turn(resident_id=OTHER)).status_code == 403
    assert post(turn(session_id=SID + "x")).status_code == 403
    assert stored() == 0 and stored(OTHER) == 0


def test_stale_lease_refused():
    lease(age=300)
    assert post(turn()).status_code == 403
    assert stored() == 0


def test_live_lease_stores_user_and_assistant():
    lease()
    assert post(turn()).status_code == 200
    assert post(turn(role="assistant", text="hi")).status_code == 200
    assert stored() == 2


def test_grace_after_release_then_expires():
    released(10)
    assert post(turn()).status_code == 200
    assert stored() == 1
    run(db.resident_aria_lease_events.delete_many({"lease.resident_id": RES}))
    released(ingest.RELEASE_GRACE_SECONDS + 30)
    assert post(turn()).status_code == 403
    assert stored() == 1


def test_validation_limits():
    lease()
    assert post(turn(text="x" * (ingest.MAX_TURN_CHARS + 1))).status_code == 422
    assert post(turn(role="system")).status_code == 422
    assert post(turn(session_id="")).status_code == 422
    assert stored() == 0


def test_trusted_flag_cannot_bypass_lease():
    assert post(turn(trusted=True)).status_code == 403
    assert stored() == 0


def test_in_process_phone_path_still_stores():
    data = ingest.RealtimeTurnIngest(resident_id=RES, session_id="call_1", role="user", text="phone hello")
    assert run(ingest.store_turn(data))["ok"]
    assert stored() == 1
