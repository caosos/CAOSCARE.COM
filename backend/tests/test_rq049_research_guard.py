"""RQ-049: POST /api/research needs a live Aria session (or owner token) and is
rate limited when a paid provider is enabled. Provider MOCKED; scratch DB.

    cd backend && DB_NAME=caoscare_rq049_test JWT_SECRET=x pytest tests/test_rq049_research_guard.py -q
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
from routes import research, research_guard  # noqa: E402
from routes import research_openai_search as oas  # noqa: E402

TAG = f"rq049_{uuid.uuid4().hex[:8]}"
RES, SID, ROOM = f"{TAG}_res", f"{TAG}_sess", f"{TAG}_room"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("CAOSCARE_RESEARCH_PROVIDER", "openai_web_search")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "m")
    monkeypatch.setenv("CAOSCARE_RESEARCH_RATE_PER_MIN", "3")
    research_guard.reset_rate_limit()
    calls, events = [], []

    async def fake_ask(question, system):
        calls.append(question)
        return {"answer": "ok", "citations": [{"url": "https://a.test", "title": "A"}],
                "search_calls": 1, "provenance": {}}

    async def fake_log(**k):
        events.append(k)
        return k
    monkeypatch.setattr(oas, "ask", fake_ask)
    monkeypatch.setattr(research, "log_event", fake_log)
    monkeypatch.setattr(research_guard, "log_event", fake_log)
    yield calls, events
    for c in (db.resident_aria_leases, db.resident_aria_lease_events):
        run(c.delete_many({"$or": [{"resident_id": RES}, {"lease.resident_id": RES}]}))
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))


def post(body, headers=None):
    a = FastAPI()
    a.include_router(research.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=a), base_url="http://test") as c:
            return await c.post("/api/research", json=body, headers=headers or {})
    return run(go())


def q(**kw):
    return {"question": "who is the mayor", **kw}


def lease():
    run(db.resident_aria_leases.insert_one({
        "room": ROOM, "resident_id": RES, "session_id": SID, "status": "active",
        "last_seen_at": now_utc().isoformat()}))


def test_no_lease_denied_no_provider_call(setup):
    calls, events = setup
    r = post(q(resident_id=RES, session_id=SID))
    assert r.status_code == 403 and calls == []
    assert events[-1]["status"] == "failed" and events[-1]["error_message"] == "no live session"
    assert post(q()).status_code == 403 and calls == []


def test_live_lease_allowed(setup):
    calls, _ = setup
    lease()
    r = post(q(resident_id=RES, session_id=SID))
    assert r.status_code == 200 and r.json()["live"] is True and calls == ["who is the mayor"]
    assert post(q(resident_id="other", session_id=SID)).status_code == 403


def test_grace_after_release_then_expiry(setup):
    run(db.resident_aria_lease_events.insert_one({
        "event": "released", "at": (now_utc() - timedelta(seconds=20)).isoformat(),
        "lease": {"room": ROOM, "resident_id": RES, "session_id": SID}}))
    assert post(q(resident_id=RES, session_id=SID)).status_code == 200
    run(db.resident_aria_lease_events.delete_many({"lease.resident_id": RES}))
    run(db.resident_aria_lease_events.insert_one({
        "event": "released", "at": (now_utc() - timedelta(seconds=300)).isoformat(),
        "lease": {"room": ROOM, "resident_id": RES, "session_id": SID}}))
    assert post(q(resident_id=RES, session_id=SID)).status_code == 403


def test_owner_token_allowed(setup):
    from routes.auth import _issue_jwt
    uid = f"{TAG}_owner"
    run(db.users.insert_one({"user_id": uid, "email": f"{uid}@t.test", "name": "o", "role": "owner"}))
    h = {"Authorization": f"Bearer {_issue_jwt(uid)}"}
    assert post(q(), h).status_code == 200
    uid2 = f"{TAG}_staff"
    run(db.users.insert_one({"user_id": uid2, "email": f"{uid2}@t.test", "name": "s", "role": "staff"}))
    assert post(q(), {"Authorization": f"Bearer {_issue_jwt(uid2)}"}).status_code == 403


def test_rate_limit_per_room(setup):
    calls, events = setup
    lease()
    body = q(resident_id=RES, session_id=SID)
    assert [post(body).status_code for _ in range(3)] == [200, 200, 200]
    r = post(body)
    assert r.status_code == 429 and "can't look that up" in r.json()["detail"]
    assert len(calls) == 3 and events[-1]["error_message"] == "rate limit"


def test_provider_none_unaffected(setup, monkeypatch):
    monkeypatch.setenv("CAOSCARE_RESEARCH_PROVIDER", "none")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(research, "OPENAI_API_KEY", "")
    r = post(q())
    assert r.status_code == 503  # unavailable, but not 403/429
    assert post({"question": "x" * 501}).status_code == 422
