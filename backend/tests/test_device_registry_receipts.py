"""Device registry changes are receipted with provenance and limited to owner/admin (receipt law)."""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes device/receipt rows; scratch DB only", allow_module_level=True)

from deps import db  # noqa: E402
from models import SmartDeviceCreate  # noqa: E402
from routes import devices  # noqa: E402

ADMIN = {"user_id": f"u_{uuid.uuid4().hex[:6]}", "name": "Admin", "role": "admin"}
STAFF = {"user_id": "u_staff", "name": "Staff", "role": "staff", "department": "maintenance"}


async def _scenario():
    body = SmartDeviceCreate(label="Test TV", kind="tv", protocol="mock", room="T-REG", capabilities=["power"])
    d = await devices.create_device(body, user=ADMIN)
    did = d["device_id"]
    try:
        for call in (devices.create_device(body, user=STAFF), devices.update_device(did, body, user=STAFF),
                     devices.delete_device(did, user=STAFF)):
            with pytest.raises(HTTPException) as e:
                await call
            assert e.value.status_code == 403
        ir = SmartDeviceCreate(label="Test TV", kind="tv", protocol="ir_blaster", room="T-REG", endpoint="esphome.x",
                               ir_codeset="sony_sirc12", capabilities=["power", "volume_step"])
        await devices.update_device(did, ir, user=ADMIN)
        await devices.delete_device(did, user=ADMIN)
        rc = {r["action_type"]: r for r in await db.receipts.find({"related_object_id": did}).to_list(10)}
        assert set(rc) == {"device_record_created", "device_record_updated", "device_record_deleted"}
        up = rc["device_record_updated"]
        assert up["actor_id"] == ADMIN["user_id"] and up["authority"] == "admin_override:admin"
        assert up["before_state"]["protocol"] == "mock" and up["after_state"]["protocol"] == "ir_blaster"
        assert up["after_state"]["ir_codeset"] == "sony_sirc12"
        assert rc["device_record_deleted"].get("after_state") is None
    finally:
        await db.smart_devices.delete_many({"room": "T-REG"})
        await db.receipts.delete_many({"related_object_id": did})


def test_device_registry_changes_are_receipted_and_admin_only():
    asyncio.get_event_loop().run_until_complete(_scenario())
