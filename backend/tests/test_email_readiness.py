"""GET /api/notifications/readiness: reports what is missing for real email, never a secret, sends nothing."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import email_readiness  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"erd_{uuid.uuid4().hex[:6]}"
REAL = httpx.AsyncClient


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def get(who=None):
    app = FastAPI(); app.include_router(email_readiness.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"} if who else {}

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get("/api/notifications/readiness", headers=h)
    return run(go())


@pytest.fixture(autouse=True)
def seed(monkeypatch):
    for k in ("RESEND_API_KEY", "RESEND_FROM_EMAIL", "RESEND_WEBHOOK_SECRET"):
        monkeypatch.delenv(k, raising=False)
    run(db.users.insert_many([{"user_id": f"{TAG}_a", "email": "a@x.t", "name": "A", "role": "admin"},
                              {"user_id": f"{TAG}_s", "email": "s@x.t", "name": "S", "role": "staff"}]))
    run(db.departments.insert_one({"slug": f"{TAG}_dep", "label": "TagDept", "is_active": True}))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.departments.delete_many({"slug": {"$regex": f"^{TAG}"}}))
    run(db.email_allowlist.delete_many({"entry_id": {"$regex": f"^{TAG}"}}))


def test_nothing_configured_lists_every_gap_and_leaks_nothing(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_SECRETVALUE")
    monkeypatch.delenv("RESEND_API_KEY")
    r = get(f"{TAG}_a"); body = r.json()
    assert r.status_code == 200 and body["ready"] is False
    ok = {c["id"]: c["ok"] for c in body["checks"]}
    assert ok["resend_key"] is False and ok["sending_domain"] is False and ok["webhook_secret"] is False
    assert any(d["slug"] == f"{TAG}_dep" for d in body["departments_missing_inbox"])


def test_configured_values_turn_checks_green_without_printing_them(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_SECRETVALUE")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "care@facility.example")
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "whsec_SECRETVALUE")
    run(db.email_allowlist.insert_many([{"entry_id": f"{TAG}_m", "lane": "menu", "pattern": "@k.example", "active": True},
                                        {"entry_id": f"{TAG}_x", "lane": "activities", "pattern": "@a.example", "active": False}]))
    r = get(f"{TAG}_a"); body = r.json()
    ok = {c["id"]: c["ok"] for c in body["checks"]}
    assert ok["resend_key"] and ok["sending_domain"] and ok["webhook_secret"]
    assert ok["inbound_menu_sender"] is True and ok["inbound_activities_sender"] is False   # inactive entry does not count
    assert "SECRETVALUE" not in r.text and "facility.example" not in r.text


def test_admin_only():
    assert get().status_code == 401
    assert get(f"{TAG}_s").status_code == 403
