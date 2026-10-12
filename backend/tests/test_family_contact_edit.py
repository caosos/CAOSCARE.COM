"""careops-family-edit-001: family contacts can be edited; an approved contact's phone (the number Aria
calls) changes only by owner/admin; allow_calls/resident_id cannot be edited here; every contact change
(create, edit, call approval, delete) writes one chained receipt with before/after. No external calls."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"fce_{uuid.uuid4().hex[:6]}"
REAL = httpx.AsyncClient


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def call(method, path, who, body=None):
    app = FastAPI(); app.include_router(notifications.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"} if who else {}

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.request(method, f"/api{path}", headers=h, json=body)
    return run(go())


def stored(cid): return run(db.family_contacts.find_one({"contact_id": cid}, {"_id": 0}))
def receipts(cid): return run(db.receipts.find({"related_object_id": cid}, {"_id": 0}).sort("created_at", 1).to_list(50))


@pytest.fixture(autouse=True)
def seed():
    run(db.users.insert_many([{"user_id": f"{TAG}_a", "email": "a@x.t", "name": "A", "role": "admin", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_s", "email": "s@x.t", "name": "S", "role": "staff", "auth_provider": "jwt"},
                              {"user_id": f"{TAG}_f", "email": "f@x.t", "name": "F", "role": "front_desk", "auth_provider": "jwt"}]))
    yield
    ids = [c["contact_id"] for c in run(db.family_contacts.find({"resident_id": {"$regex": f"^{TAG}"}}).to_list(50))]
    run(db.receipts.delete_many({"related_object_type": "family_contact"}))
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.family_contacts.delete_many({"resident_id": {"$regex": f"^{TAG}"}}))


def make(who="f", **kw):
    r = call("POST", "/family-contacts", f"{TAG}_{who}", {"resident_id": f"{TAG}_r", "name": "Kin", "phone": "+15550100", **kw})
    assert r.status_code == 200, r.text
    return r.json()["contact_id"]


def test_staff_edits_contact_with_a_receipt_carrying_before_and_after():
    cid = make()
    r = call("PATCH", f"/family-contacts/{cid}", f"{TAG}_f", {"name": "Kin Smith", "email": "kin@example.com", "notify_on": ["emergency"]})
    assert r.status_code == 200 and r.json()["changed"] == ["email", "name", "notify_on"]
    s = stored(cid)
    assert s["name"] == "Kin Smith" and s["email"] == "kin@example.com" and s["notify_on"] == ["emergency"]
    rc = receipts(cid)
    assert [x["action_type"] for x in rc] == ["family_contact_created", "family_contact_updated"]
    up = rc[1]
    assert up["before_state"]["name"] == "Kin" and up["after_state"]["name"] == "Kin Smith"
    assert up["parent_receipt_id"] == rc[0]["receipt_id"]
    assert up["correlation_id"] == rc[0]["receipt_id"]
    assert up["requested_by"] == f"{TAG}_f"


def test_no_change_writes_no_receipt_and_blank_name_is_refused():
    cid = make()
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_f", {"name": "Kin"}).json()["changed"] == []
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_f", {"name": "  "}).status_code == 422
    assert len(receipts(cid)) == 1 and stored(cid)["name"] == "Kin"


def test_allow_calls_and_resident_cannot_be_edited_here():
    cid = make()
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_a", {"allow_calls": True}).status_code == 422
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_a", {"resident_id": "other"}).status_code == 422
    s = stored(cid)
    assert s["allow_calls"] is False and s["resident_id"] == f"{TAG}_r"


def test_phone_of_call_approved_contact_is_owner_admin_only():
    cid = make(who="a", allow_calls=True)
    r = call("PATCH", f"/family-contacts/{cid}", f"{TAG}_s", {"phone": "+15559999"})
    assert r.status_code == 403 and stored(cid)["phone"] == "+15550100"
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_s", {"relationship": "son"}).status_code == 200   # other fields fine
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_a", {"phone": "+15559999"}).status_code == 200
    assert stored(cid)["phone"] == "+15559999"
    last = receipts(cid)[-1]
    assert last["authority"] == "admin_override:admin"
    assert last["before_state"]["phone"] == "+15550100" and last["after_state"]["phone"] == "+15559999"


def test_phone_of_unapproved_contact_can_be_changed_by_staff():
    cid = make()
    assert call("PATCH", f"/family-contacts/{cid}", f"{TAG}_s", {"phone": "+15551111"}).status_code == 200
    assert stored(cid)["phone"] == "+15551111"


def test_missing_and_anonymous():
    assert call("PATCH", "/family-contacts/fam_missing", f"{TAG}_f", {"name": "X"}).status_code == 404
    assert call("PATCH", "/family-contacts/fam_missing", None, {"name": "X"}).status_code == 401


def test_call_approval_and_delete_write_receipts():
    cid = make()
    assert call("PATCH", f"/family-contacts/{cid}/calls", f"{TAG}_a", {"allow_calls": True}).status_code == 200
    assert call("PATCH", f"/family-contacts/{cid}/calls", f"{TAG}_a", {"allow_calls": True}).status_code == 200   # no change, no receipt
    assert call("DELETE", f"/family-contacts/{cid}", f"{TAG}_a").status_code == 200
    kinds = [x["action_type"] for x in receipts(cid)]
    assert kinds == ["family_contact_created", "family_contact_call_approval_changed", "family_contact_deleted"]
    assert receipts(cid)[-1]["after_state"] is None
