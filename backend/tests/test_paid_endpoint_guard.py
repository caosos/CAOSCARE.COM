"""Public routes that spend OpenAI money: admin-only where nothing calls them, rate-limited where the kiosk/glasses do."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import ai, paid_endpoint_guard, vision  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"peg_{uuid.uuid4().hex[:6]}"
REAL = httpx.AsyncClient


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def call(method, path, who=None, **kw):
    app = FastAPI(); app.include_router(ai.router, prefix="/api"); app.include_router(vision.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(f'{TAG}_{who}')}"} if who else {}
    h.update(kw.pop("headers", {}))

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, path, headers=h, **kw)
    return run(go())


@pytest.fixture(scope="module", autouse=True)
def seed():
    run(db.users.insert_many([{"user_id": f"{TAG}_admin", "email": "a@x.t", "name": "A", "role": "admin"},
                              {"user_id": f"{TAG}_staff", "email": "s@x.t", "name": "S", "role": "staff"}]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    paid_endpoint_guard.reset()
    monkeypatch.setattr(ai, "OPENAI_API_KEY", "")   # never reach OpenAI: a missing key is a 503 after the guard


def test_chat_history_and_stt_need_admin():
    for m, p, kw in (("POST", "/api/ai/chat", {"json": {"message": "hi", "session_id": "s"}}),
                     ("GET", "/api/ai/chat/history/abc", {}),
                     ("POST", "/api/ai/stt", {"files": {"audio": ("a.webm", b"x", "audio/webm")}})):
        assert call(m, p, None, **kw).status_code == 401, p
        assert call(m, p, "staff", **kw).status_code == 403, p
    assert call("GET", "/api/ai/chat/history/abc", "admin").status_code == 200


def test_tts_is_rate_limited_per_client(monkeypatch):
    monkeypatch.setenv("CAOSCARE_TTS_RATE_PER_MIN", "3")
    codes = [call("POST", "/api/ai/tts", None, json={"text": "hello"}).status_code for _ in range(5)]
    assert codes[:3] == [503, 503, 503] and codes[3:] == [429, 429]   # 503 = reached the (keyless) provider check; 429 = blocked first


def test_vision_is_rate_limited_and_buckets_are_separate(monkeypatch):
    monkeypatch.setenv("CAOSCARE_VISION_RATE_PER_MIN", "2")
    body = {"image_base64": "AAAA"}
    codes = [call("POST", "/api/vision/describe", None, json=body).status_code for _ in range(4)]
    assert codes[2:] == [429, 429] and 429 not in codes[:2]
    assert call("POST", "/api/ai/tts", None, json={"text": "hi"}).status_code != 429   # tts bucket untouched by vision


def test_forwarded_for_separates_clients(monkeypatch):
    monkeypatch.setenv("CAOSCARE_TTS_RATE_PER_MIN", "1")
    h = lambda ip: {"x-forwarded-for": ip}
    a = [call("POST", "/api/ai/tts", None, json={"text": "x"}, headers=h("1.1.1.1")).status_code for _ in range(2)]
    b = call("POST", "/api/ai/tts", None, json={"text": "x"}, headers=h("2.2.2.2")).status_code
    assert a[1] == 429 and b != 429
