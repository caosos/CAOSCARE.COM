"""Resident Aria core step 4: call_contact is honest. Front desk or an approved family contact -> "calling isn't
set up here yet" (no CallSession created, refusal receipt); unapproved -> not_approved; no live session and not
the owner -> 403. Tool offered only with CAOSCARE_CALL_TOOL. In-process, scratch DB."""
import asyncio, inspect, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import now_utc  # noqa: E402
from routes import room_call_request as rcr  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"rcr_{uuid.uuid4().hex[:6]}"
RID, SID = f"{TAG}_res", f"{TAG}_sess"
def run(c): return asyncio.get_event_loop().run_until_complete(c)


def post(body, who=None):
    app = FastAPI(); app.include_router(rcr.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"} if who else {}
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/api/telephony/room-call-request", headers=h, json=body)
    return run(go())


@pytest.fixture(autouse=True)
def seed():
    run(db.users.insert_many([{"user_id": f"{TAG}_o", "email": "o@x.t", "name": "O", "role": "owner", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_n", "email": "n@x.t", "name": "N", "role": "staff", "department": "nursing", "auth_provider": "jwt"}]))
    run(db.resident_aria_leases.insert_one({"session_id": SID, "resident_id": RID, "room": "T9", "status": "active", "last_seen_at": now_utc().isoformat()}))
    run(db.family_contacts.insert_many([
        {"contact_id": f"{TAG}_c1", "resident_id": RID, "name": "Liam O'Brien", "relationship": "son", "phone": "+15550101", "allow_calls": True},
        {"contact_id": f"{TAG}_c2", "resident_id": RID, "name": "Ann Smith", "relationship": "niece", "phone": "+15550102", "allow_calls": False}]))
    before = run(db.call_sessions.count_documents({}))
    yield before
    for c, q in (("users", {"user_id": {"$regex": f"^{TAG}"}}), ("resident_aria_leases", {"session_id": SID}),
                 ("family_contacts", {"resident_id": RID}), ("receipts", {"conversation_session_id": SID})):
        run(getattr(db, c).delete_many(q))


def test_approved_contact_and_front_desk_are_refused_honestly_with_no_call_record(seed):
    for target, label in (("Liam", "Liam O'Brien"), ("son", "Liam O'Brien"), ("front desk", "the front desk")):
        d = post({"target": target, "resident_id": RID, "session_id": SID}).json()
        assert d["ok"] is False and d["outcome"] == "not_configured" and label in d["message"]
        assert "isn't set up" in d["message"] and not any(w in d["message"].lower() for w in ("calling now", "ringing", "answered"))
    assert run(db.call_sessions.count_documents({})) == seed                              # nothing implies dialing
    kinds = [r["action_type"] for r in run(db.receipts.find({"conversation_session_id": SID}).to_list(10))]
    assert kinds.count("call.room_request.not_configured") == 3


def test_unapproved_or_unknown_contact_is_not_approved():
    for target in ("Ann", "Bob"):
        d = post({"target": target, "resident_id": RID, "session_id": SID}).json()
        assert d["outcome"] == "not_approved" and "approved for calls" in d["message"]


def test_needs_a_live_session_or_the_owner():
    assert post({"target": "front desk", "resident_id": RID, "session_id": "not-live"}).status_code == 403
    assert post({"target": "front desk"}, who=f"{TAG}_n").status_code == 403
    assert post({"target": "front desk"}, who=f"{TAG}_o").json()["outcome"] == "not_configured"


def test_tool_offered_only_with_the_flag(monkeypatch):
    from routes.realtime_tools import _build_tools
    async def names():
        t = _build_tools(); t = await t if inspect.isawaitable(t) else t
        return [x["name"] for x in t]
    monkeypatch.delenv("CAOSCARE_CALL_TOOL", raising=False)
    assert "call_contact" not in run(names())
    monkeypatch.setenv("CAOSCARE_CALL_TOOL", "1")
    assert "call_contact" in run(names())
