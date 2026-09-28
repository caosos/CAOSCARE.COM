"""Demo kiosk: simulated devices through the normal room-command path, and
DEMO RESET (routes/demo_kiosk.py, simulated_device.py).

Proves: the demo light turns on/off through /devices/public/room/{room}/command
with a verified simulated read-back; repeated commands are stable; an
unsupported or invalid command fails instead of being reported as done;
reset restores the baseline and closes open demo requests with a history
entry; reset refuses a room holding any non-simulated device; a demo
command never touches another room's devices.

Needs a backend whose DB has a kiosk marked public_demo in a room of mock
devices (the Lane G test DB). Skips when unreachable or not configured.

    TEST_API_BASE=http://127.0.0.1:8095 pytest tests/test_demo_kiosk.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

# No default URL on purpose: this test changes the demo room's devices and
# closes its open requests, so it must only ever run against a backend that
# was named explicitly (the gate sets REACT_APP_BACKEND_URL), never a live
# dev backend picked by default.
BASE_URL = (os.environ.get("TEST_API_BASE") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulated_device import SimulatedDeviceError, apply_simulated_command  # noqa: E402


def test_simulated_device_rules():
    light = {"kind": "light", "capabilities": ["power", "brightness"], "state": {"power": "off", "brightness": 80}}
    assert apply_simulated_command(light, "power", "on") == {"power": "on", "brightness": 80}
    assert light["state"]["power"] == "off"  # input never mutated
    for action, value in [("color", [0, 200, 0]), ("power", "maybe"), ("brightness", 0), ("brightness", "high")]:
        with pytest.raises(SimulatedDeviceError):
            apply_simulated_command(light, action, value)
    tv = {"kind": "tv", "capabilities": ["input", "channel"], "inputs": ["TV", "HDMI 1"], "state": {}}
    assert apply_simulated_command(tv, "input", "hdmi 1")["input"] == "HDMI 1"
    with pytest.raises(SimulatedDeviceError):
        apply_simulated_command(tv, "input", "Netflix")
    with pytest.raises(SimulatedDeviceError):
        apply_simulated_command({**light, "online": False}, "power", "on")


def _demo_room():
    if not BASE_URL:
        return None
    try:
        r = requests.get(f"{API}/kiosks/public-demo", timeout=3)
    except Exception:
        return None
    return r.json()["room"] if r.status_code == 200 else None


def _cmd(room, action, value, kind):
    return requests.post(f"{API}/devices/public/room/{room}/command",
                         json={"action": action, "value": value, "kind": kind}, timeout=5)


def _state(room, kind):
    devs = requests.get(f"{API}/devices/public/by-room/{room}", timeout=5).json()
    return next(d for d in devs if d["kind"] == kind)["state"]


async def _db_run(fn):
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        return await fn(client[os.environ["DB_NAME"]])
    finally:
        client.close()


def test_demo_light_reset_and_guards():
    room = _demo_room()
    if not room:
        pytest.skip(f"no backend named, or no public demo kiosk at {BASE_URL or '(none)'}")
    r = requests.post(f"{API}/demo/reset", timeout=5)
    assert r.status_code == 200, r.text
    assert _state(room, "light")["power"] == "off"

    for _ in range(2):  # repeated commands stay truthful and stable
        on = _cmd(room, "power", "on", "light").json()
        assert on["status"] == "executed" and on["verified"] is True and on["state"]["power"] == "on"
    assert _state(room, "light")["power"] == "on"
    off = _cmd(room, "power", "off", "light").json()
    assert off["verified"] is True and _state(room, "light")["power"] == "off"

    assert _cmd(room, "color", [0, 200, 0], "light").status_code == 400      # light has no color
    bad = _cmd(room, "temperature", 99, "thermostat")
    assert bad.status_code == 502 and "between 60 and 85" in bad.text
    assert _state(room, "thermostat")["temperature"] == 72                  # unchanged

    tag = f"demo_{uuid.uuid4().hex[:8]}"

    async def seed(db):
        other = f"{tag}-other"
        await db.smart_devices.insert_one({"device_id": f"{tag}_o", "label": "other light", "kind": "light",
                                           "protocol": "mock", "room": other, "capabilities": ["power"],
                                           "state": {"power": "off"}, "online": True})
        await db.staff_tasks.insert_one({"task_id": f"{tag}_t", "title": "demo request", "room": room,
                                         "status": "pending", "category": "maintenance",
                                         "visibility_role": "maintenance", "created_at": "2026-09-28T00:00:00+00:00"})
        return other

    other_room = asyncio.run(_db_run(seed))
    try:
        _cmd(room, "power", "on", "light")
        assert _state(other_room, "light")["power"] == "off"                # other room untouched
        body = requests.post(f"{API}/demo/reset", timeout=5).json()
        assert body["requests_closed"] >= 1

        async def check(db):
            t = await db.staff_tasks.find_one({"task_id": f"{tag}_t"}, {"_id": 0})
            assert t["status"] == "skipped"
            assert t["event_log"][-1]["by"] == "demo_reset" and t["event_log"][-1]["to"] == "skipped"
            await db.smart_devices.insert_one({"device_id": f"{tag}_real", "label": "real", "kind": "light",
                                               "protocol": "home_assistant", "room": room, "capabilities": ["power"],
                                               "state": {}, "online": True})
        asyncio.run(_db_run(check))
        refused = requests.post(f"{API}/demo/reset", timeout=5)
        assert refused.status_code == 409 and f"{tag}_real" in refused.text
    finally:
        async def cleanup(db):
            await db.smart_devices.delete_many({"device_id": {"$regex": f"^{tag}"}})
            await db.staff_tasks.delete_many({"task_id": {"$regex": f"^{tag}"}})
        asyncio.run(_db_run(cleanup))
        requests.post(f"{API}/demo/reset", timeout=5)
