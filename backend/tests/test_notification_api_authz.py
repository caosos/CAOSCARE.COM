"""Notification API authorization: the delivery log, provider status and test-send are the admin
Communications surface only. Non-admin roles (staff of any department, front desk) and anonymous callers get
401/403 and no data, and an unauthorized test-send never reaches a provider or writes a notification.
In-process ASGI, scratch DB, both provider transports mocked, local-owner bypass off."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications, notification_delivery  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"nauth_{uuid.uuid4().hex[:6]}"
REAL = httpx.AsyncClient
ROLES = {"owner": ("owner", None), "admin": ("admin", None), "nurse": ("staff", "nursing"),
         "maint": ("staff", "maintenance"), "front": ("front_desk", None)}


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def call(method, path, who=None, **kw):
    app = FastAPI(); app.include_router(notifications.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(f'{TAG}_{who}')}"} if who else {}

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, path, headers=h, **kw)
    return run(go())


@pytest.fixture(autouse=True)
def seed(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LOCAL_OWNER_BYPASS", raising=False)
    run(db.users.insert_many([{"user_id": f"{TAG}_{k}", "email": f"{k}@x.t", "name": k, "role": r, "department": d} for k, (r, d) in ROLES.items()]))
    run(db.notifications.insert_many([
        {"notification_id": f"{TAG}_n1", "channel": "email", "to": "nurse-dept@x.test", "body": "SECRET-NURSING", "status": "sent", "department": "nursing", "related_object_type": "task", "related_object_id": f"{TAG}_t1", "created_at": "2026-10-10T10:00:00+00:00"},
        {"notification_id": f"{TAG}_n2", "channel": "email", "to": "maint-dept@x.test", "body": "SECRET-MAINT", "status": "failed", "department": "maintenance", "related_object_type": "task", "related_object_id": f"{TAG}_t2", "created_at": "2026-10-10T11:00:00+00:00"},
        {"notification_id": f"{TAG}_n3", "channel": "sms", "to": "+15550000", "body": "SECRET-TEST", "status": "logged", "created_at": "2026-10-10T12:00:00+00:00"}]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.notifications.delete_many({"notification_id": {"$regex": f"^{TAG}"}}))
    run(db.notifications.delete_many({"to": {"$in": ["probe@x.test", "+15559999", "admin-probe@x.test"]}}))


@pytest.fixture
def providers(monkeypatch):
    calls = []

    async def fake(*a, **k):
        calls.append((a, k))
        return {"status": "logged"}
    monkeypatch.setattr(notifications, "send_email", fake)
    monkeypatch.setattr(notifications, "send_sms", fake)
    monkeypatch.setattr(notification_delivery, "send_email", fake, raising=False)
    monkeypatch.setattr(notification_delivery, "send_sms", fake, raising=False)

    class Boom:
        def __init__(self, *a, **k): calls.append("network")
        async def __aenter__(self): calls.append("network"); raise AssertionError("network used")
    monkeypatch.setattr(notification_delivery.httpx, "AsyncClient", Boom, raising=False)
    return calls


DENIED = [None, "nurse", "maint", "front"]


@pytest.mark.parametrize("who", DENIED)
def test_log_status_denied_for_non_admin(who):
    for path in ("/api/notifications", "/api/notifications?department=nursing", f"/api/notifications?related_object_id={TAG}_t2",
                 "/api/notifications?status=failed", "/api/notifications/status"):
        r = call("GET", path, who)
        assert r.status_code == (401 if who is None else 403), (who, path, r.status_code)
        assert "SECRET" not in r.text and "x.test" not in r.text


@pytest.mark.parametrize("who", ["owner", "admin"])
def test_admin_tier_still_reads_log_and_filters(who):
    r = call("GET", "/api/notifications?limit=500", who)
    assert r.status_code == 200
    ids = {n["notification_id"] for n in r.json()}
    assert {f"{TAG}_n1", f"{TAG}_n2", f"{TAG}_n3"} <= ids
    assert [n["notification_id"] for n in call("GET", "/api/notifications?department=nursing", who).json()] == [f"{TAG}_n1"]
    assert [n["notification_id"] for n in call("GET", f"/api/notifications?related_object_id={TAG}_t2", who).json()] == [f"{TAG}_n2"]
    assert call("GET", "/api/notifications/status", who).status_code == 200


@pytest.mark.parametrize("who", DENIED)
def test_test_send_denied_before_provider_or_write(who, providers):
    before = run(db.notifications.count_documents({}))
    for body in ({"channel": "email", "to": "probe@x.test", "body": "x"}, {"channel": "sms", "to": "+15559999", "body": "x"},
                 {"channel": "inapp", "to": "probe@x.test", "body": "x"}):
        r = call("POST", "/api/notifications/test", who, json=body)
        assert r.status_code == (401 if who is None else 403), (who, body, r.status_code)
    assert providers == [], "a provider function or the network was reached"
    assert run(db.notifications.count_documents({})) == before, "a notification was written"


@pytest.mark.parametrize("who", ["owner", "admin"])
def test_admin_test_send_reaches_provider_with_fake_destination(who, providers):
    r = call("POST", "/api/notifications/test", who, json={"channel": "email", "to": "admin-probe@x.test", "body": "hi"})
    assert r.status_code == 200
    assert len(providers) == 1 and providers[0][0][0] == "admin-probe@x.test"
