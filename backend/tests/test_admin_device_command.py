"""careops-good-surfaces-review-001: the Admin Devices command is owner/admin only and every command,
success or failure, writes a receipt naming the user. In-process, scratch DB, mock device only."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import devices  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402

TAG = f"adc_{uuid.uuid4().hex[:6]}"
DEV = f"{TAG}_light"
def run(c): return asyncio.get_event_loop().run_until_complete(c)


def post(who, body):
    app = FastAPI(); app.include_router(devices.router, prefix="/api")
    h = {"Authorization": f"Bearer {_issue_jwt(who)}"} if who else {}
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.post(f"/api/devices/{DEV}/command", headers=h, json=body)
    return run(go())


@pytest.fixture(autouse=True)
def seed():
    roles = {"admin": ("admin", None), "owner": ("owner", None), "nurse": ("staff", "nursing"), "desk": ("front_desk", None)}
    run(db.users.insert_many([{"user_id": f"{TAG}_{k}", "email": f"{k}@x.t", "name": f"{k} name", "role": r, "department": d, "auth_provider": "jwt"}
                              for k, (r, d) in roles.items()]))
    run(db.smart_devices.insert_one({"device_id": DEV, "label": "T light", "kind": "light", "protocol": "mock", "room": f"{TAG}-R",
                                     "capabilities": ["power", "brightness"], "state": {"power": "off", "brightness": 50}}))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})); run(db.smart_devices.delete_many({"device_id": DEV}))
    run(db.device_commands.delete_many({"device_id": DEV})); run(db.receipts.delete_many({"related_object_id": DEV}))


def receipts(): return run(db.receipts.find({"related_object_id": DEV}, {"_id": 0}).to_list(20))


@pytest.mark.parametrize("who,code", [("nurse", 403), ("desk", 403), (None, 401)])
def test_non_admin_refused_and_nothing_happens(who, code):
    assert post(f"{TAG}_{who}" if who else None, {"action": "power", "value": "on"}).status_code == code
    assert run(db.device_commands.count_documents({"device_id": DEV})) == 0 and receipts() == []
    assert run(db.smart_devices.find_one({"device_id": DEV}))["state"]["power"] == "off"


@pytest.mark.parametrize("who", ["admin", "owner"])
def test_admin_command_writes_a_receipt_naming_the_user(who):
    r = post(f"{TAG}_{who}", {"action": "power", "value": "on"})
    assert r.status_code == 200, r.text
    rc = receipts()
    assert len(rc) == 1 and rc[0]["action_type"] == "staff_device_command" and rc[0]["status"] == "completed"
    assert rc[0]["requested_by"] == f"{TAG}_{who}" and rc[0]["actor_role"] == who
    assert rc[0]["simulated"] is True and rc[0]["result_label"] == "simulated" and rc[0]["authority"] == f"admin_override:{who}"
    assert rc[0]["before_state"]["power"] == "off" and rc[0]["after_state"]["requested_value"] == "on" and rc[0]["after_state"]["state"]["power"] == "on"


def test_failed_command_writes_a_failed_receipt():
    r = post(f"{TAG}_admin", {"action": "brightness", "value": 500})
    assert r.status_code >= 400
    rc = receipts()
    assert len(rc) == 1 and rc[0]["status"] == "failed" and rc[0]["result_label"] == "failed"
