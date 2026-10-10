"""Call approval authority: only owner/admin may set allow_calls, on creation as well as on update. No external calls."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"fca_{uuid.uuid4().hex[:6]}"
REAL = httpx.AsyncClient


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def call(method, path, who, body=None):
    app = FastAPI(); app.include_router(notifications.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"}

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, f"/api{path}", headers=h, json=body)
    return run(go())


def stored(cid):
    return run(db.family_contacts.find_one({"contact_id": cid}, {"_id": 0}))


@pytest.fixture(autouse=True)
def seed():
    run(db.users.insert_many([{"user_id": f"{TAG}_a", "email": "a@x.t", "name": "A", "role": "admin", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_o", "email": "o@x.t", "name": "O", "role": "owner", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_s", "email": "s@x.t", "name": "S", "role": "staff", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_f", "email": "f@x.t", "name": "F", "role": "front_desk", "auth_provider": "jwt"}]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.family_contacts.delete_many({"resident_id": {"$regex": f"^{TAG}"}}))


def body(**kw):
    return {"resident_id": f"{TAG}_r", "name": "Kin", "phone": "+15550100", **kw}


@pytest.mark.parametrize("who", ["s", "f"])
def test_non_admin_cannot_create_call_approved_contact(who):
    r = call("POST", "/family-contacts", f"{TAG}_{who}", body(allow_calls=True))
    assert r.status_code == 403
    assert run(db.family_contacts.count_documents({"resident_id": f"{TAG}_r"})) == 0   # nothing stored


@pytest.mark.parametrize("who", ["s", "f"])
@pytest.mark.parametrize("extra", [{}, {"allow_calls": False}])
def test_non_admin_can_still_create_ordinary_contact_unapproved(who, extra):
    r = call("POST", "/family-contacts", f"{TAG}_{who}", body(**extra))
    assert r.status_code == 200 and r.json()["allow_calls"] is False
    assert stored(r.json()["contact_id"])["allow_calls"] is False


@pytest.mark.parametrize("who", ["a", "o"])
def test_admin_and_owner_can_create_call_approved_contact(who):
    r = call("POST", "/family-contacts", f"{TAG}_{who}", body(allow_calls=True))
    assert r.status_code == 200 and r.json()["allow_calls"] is True
    assert stored(r.json()["contact_id"])["allow_calls"] is True


def test_update_authority_unchanged():
    cid = call("POST", "/family-contacts", f"{TAG}_a", body()).json()["contact_id"]
    assert call("PATCH", f"/family-contacts/{cid}/calls", f"{TAG}_s", {"allow_calls": True}).status_code == 403
    assert stored(cid)["allow_calls"] is False
    assert call("PATCH", f"/family-contacts/{cid}/calls", f"{TAG}_a", {"allow_calls": True}).status_code == 200
    assert stored(cid)["allow_calls"] is True
    assert call("PATCH", f"/family-contacts/{cid}/calls", f"{TAG}_a", {"allow_calls": False}).status_code == 200
    assert stored(cid)["allow_calls"] is False
