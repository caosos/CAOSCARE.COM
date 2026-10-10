"""Dial-target token security (isolated ASGI, scratch DB, fake secret; no Asterisk/provider/call).
Deterministic 120 s expiry boundary, exactly-one concurrent redemption, valid secret from a non-local client
is refused without consuming the token, and a missing configured secret is 503 without consuming."""
import asyncio, os, sys, uuid
from datetime import datetime, timedelta, timezone
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import telephony_local  # noqa: E402

REAL = httpx.AsyncClient
SECRET = "fake-telephony-secret"
NOW = datetime(2031, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
TAG = f"dts_{uuid.uuid4().hex[:6]}"


def run(c): return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("CAOS_TELEPHONY_TOKEN", SECRET)
    monkeypatch.delenv("CAOS_TELEPHONY_ALLOWED_HOSTS", raising=False)
    monkeypatch.setattr(telephony_local, "now_utc", lambda: NOW)    # fixed clock: no timing flake
    yield
    run(db.call_sessions.delete_many({"call_id": {"$regex": f"^{TAG}"}}))


def _call(name, age_s):
    return {"call_id": f"{TAG}_{name}", "dial_token": f"{TAG}tok{name}", "state": "requested", "kind": "front_desk",
            "target_extension": "200", "created_at": (NOW - timedelta(seconds=age_s)).isoformat()}


def get(token, secret=SECRET, client=("127.0.0.1", 5000), n=1):
    app = FastAPI(); app.include_router(telephony_local.router, prefix="/api")
    h = {"x-caos-telephony-token": secret} if secret else {}

    async def one(c): return await c.get(f"/api/telephony/local/dial-target/{token}", headers=h)

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app, client=client), base_url="http://t") as c:
            return await asyncio.gather(*[one(c) for _ in range(n)])
    return run(go())


async def _token_left(name):
    d = await db.call_sessions.find_one({"call_id": f"{TAG}_{name}"})
    return d["dial_token"]


def test_expiry_boundary_is_exactly_120_seconds():
    run(db.call_sessions.insert_many([_call("in", 119), _call("edge", 120), _call("out", 121)]))
    assert get(f"{TAG}tokin")[0].text.endswith("|PJSIP/200")      # 119 s old: valid
    assert get(f"{TAG}tokedge")[0].text.endswith("|PJSIP/200")    # exactly 120 s: still valid (>= cutoff)
    r = get(f"{TAG}tokout")[0]
    assert r.status_code == 200 and r.text == ""                  # 121 s: refused
    assert run(_token_left("out")) == f"{TAG}tokout"              # an expired token is not "consumed"


def test_concurrent_redemption_yields_exactly_one_target():
    run(db.call_sessions.insert_one(_call("race", 5)))
    rs = get(f"{TAG}tokrace", n=12)
    winners = [r for r in rs if r.text]
    assert len(winners) == 1 and winners[0].text.endswith("|PJSIP/200")
    assert run(_token_left("race")) is None


def test_valid_secret_from_a_non_local_client_is_403_and_does_not_consume():
    run(db.call_sessions.insert_one(_call("remote", 5)))
    r = get(f"{TAG}tokremote", client=("10.20.30.40", 5000))[0]
    assert r.status_code == 403
    assert run(_token_left("remote")) == f"{TAG}tokremote"
    assert get(f"{TAG}tokremote")[0].text.endswith("|PJSIP/200")  # still redeemable locally


def test_wrong_or_missing_secret_is_403_and_does_not_consume():
    run(db.call_sessions.insert_one(_call("badsec", 5)))
    assert get(f"{TAG}tokbadsec", secret="nope")[0].status_code == 403
    assert get(f"{TAG}tokbadsec", secret=None)[0].status_code == 403
    assert run(_token_left("badsec")) == f"{TAG}tokbadsec"


def test_unconfigured_secret_is_503_and_does_not_consume(monkeypatch):
    run(db.call_sessions.insert_one(_call("unconf", 5)))
    monkeypatch.delenv("CAOS_TELEPHONY_TOKEN")
    assert get(f"{TAG}tokunconf", secret="anything")[0].status_code == 503
    assert run(_token_left("unconf")) == f"{TAG}tokunconf"
    monkeypatch.setenv("CAOS_TELEPHONY_TOKEN", SECRET)
    assert get(f"{TAG}tokunconf")[0].text.endswith("|PJSIP/200")
