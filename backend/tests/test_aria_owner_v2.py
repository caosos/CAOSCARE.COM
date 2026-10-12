"""Resident Aria core step 1-2: Michael's own Aria on the shared context layers behind CAOSCARE_ARIA_OWNER_V2.
Off (default): owner session exactly as before (3 tools, old capability text). On: truth rules, continuity
from db.aria_conversations, the read-only shared tools, facility context. OpenAI is never called (recorder)."""
import asyncio, os, sys, types, uuid
from datetime import timedelta
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import now_utc  # noqa: E402
from routes import realtime as rt  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"aov2_{uuid.uuid4().hex[:6]}"
OWNER = f"{TAG}_owner"
REAL = httpx.AsyncClient
def run(c): return asyncio.get_event_loop().run_until_complete(c)


class Rec:
    calls = []
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *e): return False
    async def post(self, url, headers=None, json=None, **kw):
        Rec.calls.append(url)
        class R:
            status_code = 200; text = "{}"
            @staticmethod
            def json(): return {"value": "ek_fake", "expires_at": 0}
        return R()


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setattr(rt, "httpx", types.SimpleNamespace(AsyncClient=Rec))
    monkeypatch.setattr(rt, "OPENAI_API_KEY", "sk-test-not-real")
    Rec.calls = []
    run(db.users.insert_one({"user_id": OWNER, "email": f"{OWNER}@x.t", "name": "Michael", "role": "owner", "auth_provider": "jwt"}))
    t = (now_utc() - timedelta(minutes=2)).isoformat()
    run(db.aria_conversations.insert_many([
        {"owner_user_id": OWNER, "session_id": f"{TAG}_s1", "role": "user", "content": f"Remind me about the {TAG} invoice", "created_at": t},
        {"owner_user_id": OWNER, "session_id": f"{TAG}_s1", "role": "assistant", "content": "Okay, which client?", "created_at": t}]))
    yield
    run(db.users.delete_many({"user_id": OWNER})); run(db.aria_conversations.delete_many({"owner_user_id": OWNER}))


def mint():
    app = FastAPI(); app.include_router(rt.router, prefix="/api")
    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.post("/api/realtime/aria-session", headers={"Authorization": f"Bearer {_issue_jwt(OWNER)}"}, json={})
    r = run(go()); assert r.status_code == 200, r.text
    return r.json()["_caos"]


def test_flag_off_is_the_old_owner_session(monkeypatch):
    monkeypatch.delenv("CAOSCARE_ARIA_OWNER_V2", raising=False)
    c = mint()
    assert [t["name"] for t in c["tools"]] == ["request_staff_help", "check_request_status", "end_conversation"]
    assert "will eventually have memory, tools" in c["instructions"] and f"{TAG} invoice" not in c["instructions"]
    assert c["context"] == {"owner_user_id": OWNER}


def test_flag_on_shares_context_layers_and_read_only_tools(monkeypatch):
    monkeypatch.setenv("CAOSCARE_ARIA_OWNER_V2", "1")
    c = mint()
    names = [t["name"] for t in c["tools"]]
    assert names[:3] == ["request_staff_help", "check_request_status", "end_conversation"]
    assert set(names[3:]) == {"get_current_time", "get_weather", "research_topic", "get_todays_schedule", "get_menu"}
    assert not {"toggle_light", "adjust_room_temperature", "call_for_help"} & set(names)      # not bound to a room
    ins = c["instructions"]
    assert "will eventually have memory, tools" not in ins and "You do NOT have device control" not in ins
    assert f"Remind me about the {TAG} invoice" in ins                                          # continuity from aria_conversations
    assert "research_topic" in ins and c["context"]["facility_tz"]
    assert all("client_secrets" in u for u in Rec.calls) and len(Rec.calls) == 1               # only the (faked) session mint
