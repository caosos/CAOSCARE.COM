"""Security regression: POST /api/realtime/aria-session is owner-only and the
owner whose private Aria memory is used comes from the authenticated user,
never from the request body (2026-10-05 fix).

Before the fix the route had no auth dependency, took `owner_user_id` from
the JSON body and returned instructions built from that owner's
db.aria_memories in `_caos.instructions`.

In-process (ASGI) against a scratch database. OpenAI is never called:
routes.realtime.httpx / routes.realtime_resident_session.httpx are replaced
by a recorder that returns a fake ephemeral key.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_ariaauth_test \
      JWT_SECRET=x pytest tests/test_realtime_aria_session_auth.py -q
"""
import asyncio
import os
import sys
import types
import uuid

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test users/memories; point DB_NAME at a scratch database",
                allow_module_level=True)

from deps import db  # noqa: E402
from routes import realtime as realtime_routes  # noqa: E402
from routes import realtime_resident_session  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"ariaauth_{uuid.uuid4().hex[:8]}"
OWNER_A = f"{TAG}_owner_a"
OWNER_B = f"{TAG}_owner_b"
ADMIN = f"{TAG}_admin"
STAFF = f"{TAG}_staff"
MEMORY_A = f"{TAG} owner A private standing fact"
MEMORY_B = f"{TAG} owner B private standing fact"

REAL_ASYNC_CLIENT = httpx.AsyncClient


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class OpenAIRecorder:
    """Stands in for httpx.AsyncClient inside the realtime routes."""
    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None, **kw):
        OpenAIRecorder.calls.append({"url": url, "json": json})

        class R:
            status_code = 200
            text = "{}"

            @staticmethod
            def json():
                return {"value": "ek_test_fake_ephemeral_key", "expires_at": 0}
        return R()


async def _seed():
    users = [(OWNER_A, "owner"), (OWNER_B, "owner"), (ADMIN, "admin"), (STAFF, "staff")]
    await db.users.insert_many([{"user_id": u, "email": f"{u}@example.test", "name": u, "role": r}
                                for u, r in users])
    await db.aria_memories.insert_many([
        {"memory_id": f"{TAG}_m_a", "owner_user_id": OWNER_A, "bin": "standing", "text": MEMORY_A,
         "pinned": True, "importance": 5, "created_at": "2026-10-05T00:00:00+00:00"},
        {"memory_id": f"{TAG}_m_b", "owner_user_id": OWNER_B, "bin": "standing", "text": MEMORY_B,
         "pinned": True, "importance": 5, "created_at": "2026-10-05T00:00:00+00:00"},
    ])


async def _clean():
    await db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})
    await db.aria_memories.delete_many({"memory_id": {"$regex": f"^{TAG}"}})


@pytest.fixture(autouse=True)
def env(monkeypatch):
    fake_httpx = types.SimpleNamespace(AsyncClient=OpenAIRecorder)
    monkeypatch.setattr(realtime_routes, "httpx", fake_httpx)
    monkeypatch.setattr(realtime_resident_session, "httpx", fake_httpx)
    monkeypatch.setattr(realtime_routes, "OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("CAOSCARE_LOCAL_OWNER_BYPASS", raising=False)
    OpenAIRecorder.calls = []
    run(_seed())
    yield
    run(_clean())


def _post(path, body, user_id=None):
    app = FastAPI()
    app.include_router(realtime_routes.router, prefix="/api")
    headers = {"Authorization": f"Bearer {_issue_jwt(user_id)}"} if user_id else {}

    async def go():
        async with REAL_ASYNC_CLIENT(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as c:
            return await c.post(path, json=body, headers=headers)
    return run(go())


def _no_private_memory(resp):
    assert MEMORY_A not in resp.text and MEMORY_B not in resp.text


def test_anonymous_cannot_mint_owner_session_even_naming_an_owner():
    r = _post("/api/realtime/aria-session", {"owner_user_id": OWNER_A})
    assert r.status_code == 401
    _no_private_memory(r)
    assert OpenAIRecorder.calls == []


@pytest.mark.parametrize("who", [STAFF, ADMIN])
def test_non_owner_roles_cannot_mint_owner_session(who):
    r = _post("/api/realtime/aria-session", {"owner_user_id": OWNER_A}, user_id=who)
    assert r.status_code == 403
    _no_private_memory(r)
    assert OpenAIRecorder.calls == []


def test_owner_succeeds_with_own_memory_and_voice_kept():
    r = _post("/api/realtime/aria-session", {"voice": "sage"}, user_id=OWNER_A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["value"] == "ek_test_fake_ephemeral_key"
    caos = body["_caos"]
    assert caos["context"] == {"owner_user_id": OWNER_A}
    assert caos["voice"] == "sage"
    assert MEMORY_A in caos["instructions"] and MEMORY_B not in caos["instructions"]
    sent = OpenAIRecorder.calls[0]["json"]["session"]
    assert sent["audio"]["output"]["voice"] == "sage"
    assert MEMORY_A in sent["instructions"]


def test_invalid_voice_still_falls_back_to_default():
    r = _post("/api/realtime/aria-session", {"voice": "not-a-voice"}, user_id=OWNER_A)
    assert r.status_code == 200
    assert r.json()["_caos"]["voice"] == realtime_routes.DEFAULT_VOICE


def test_forged_owner_user_id_cannot_select_another_account():
    r = _post("/api/realtime/aria-session", {"owner_user_id": OWNER_B}, user_id=OWNER_A)
    assert r.status_code == 403
    _no_private_memory(r)
    assert OpenAIRecorder.calls == []


def test_matching_owner_user_id_in_body_is_accepted():
    r = _post("/api/realtime/aria-session", {"owner_user_id": OWNER_A}, user_id=OWNER_A)
    assert r.status_code == 200
    assert r.json()["_caos"]["context"]["owner_user_id"] == OWNER_A


def test_resident_session_unchanged_public_and_unauthenticated():
    r = _post("/api/realtime/session", {})
    assert r.status_code == 200, r.text
    caos = r.json()["_caos"]
    assert len(caos["tools"]) == 26
    assert "owner_user_id" not in (caos.get("context") or {})
    _no_private_memory(r)
