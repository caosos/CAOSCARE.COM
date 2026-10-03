"""Demo kiosk: simulated devices through the normal room-command path, and
DEMO RESET (routes/demo_kiosk.py, simulated_device.py).

Proves: the demo light turns on/off through /devices/public/room/{room}/command
with a verified simulated read-back; repeated commands are stable; an
unsupported or invalid command fails instead of being reported as done;
reset restores the baseline and closes open demo requests with a history
entry; reset refuses a room holding any non-simulated device; a demo
command never touches another room's devices.

Also proves (2026-10-03, demo-only room): the demo kiosk lives in its own
demo room with a synthetic resident; demo commands, a demo request and
DEMO RESET leave another room's requests and devices exactly as they were;
reset refuses while the public demo kiosk is in any other room.

Needs a backend named explicitly and its DB (the gate's fresh test DB).
Each test creates the demo-only room itself. Skips when unreachable.

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
    """Create the demo-only room in the backend's DB and return its room, or
    None when no backend was named or it is unreachable."""
    if not BASE_URL:
        return None
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
    except Exception:
        return None
    from routes.demo_kiosk import ensure_demo_room
    info = asyncio.run(_db_run(ensure_demo_room))
    r = requests.get(f"{API}/kiosks/public-demo", timeout=3)
    assert r.status_code == 200 and r.json()["room"] == info["room"]
    return info["room"]


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


def test_demo_room_leaves_other_rooms_untouched():
    room = _demo_room()
    if not room:
        pytest.skip(f"no backend named or reachable at {BASE_URL or '(none)'}")
    from routes.demo_kiosk import DEMO_ROOM, DEMO_RESIDENT_NAME
    assert room == DEMO_ROOM
    assert requests.post(f"{API}/demo/reset", timeout=5).status_code == 200

    tag = f"nd_{uuid.uuid4().hex[:8]}"
    other = f"{tag}-room"

    async def seed(db):
        demo_res = await db.residents.find_one({"room": DEMO_ROOM}, {"_id": 0})
        assert demo_res["name"] == DEMO_RESIDENT_NAME and demo_res["name"].startswith("Demo - ")
        await db.smart_devices.insert_many([
            {"device_id": f"{tag}_light", "label": "other light", "kind": "light", "protocol": "mock",
             "room": other, "capabilities": ["power"], "state": {"power": "on"}, "online": True},
            {"device_id": f"{tag}_ha", "label": "other real light", "kind": "light", "protocol": "home_assistant",
             "room": other, "capabilities": ["power"], "state": {"power": "off"}, "online": True},
        ])
        await db.staff_tasks.insert_many([
            {"task_id": f"{tag}_t{i}", "title": f"other room request {i}", "room": other,
             "status": status, "category": "maintenance", "visibility_role": "maintenance",
             "created_at": "2026-10-01T00:00:00+00:00"}
            for i, status in enumerate(["pending", "in_progress"])])
        await db.kiosks.insert_one({"kiosk_id": f"{tag}_k", "name": "other kiosk", "room": other,
                                    "zone": "x", "public_demo": False, "created_at": "2026-10-01T00:00:00+00:00"})
        return demo_res["resident_id"]

    async def snapshot(db):
        devs = await db.smart_devices.find({"room": other}, {"_id": 0}).sort("device_id").to_list(10)
        tasks = await db.staff_tasks.find({"room": other}, {"_id": 0}).sort("task_id").to_list(10)
        cmds = await db.device_commands.count_documents({"device_id": {"$regex": f"^{tag}"}})
        return devs, tasks, cmds

    demo_resident = asyncio.run(_db_run(seed))
    try:
        before = asyncio.run(_db_run(snapshot))
        # Demo interactions through the normal paths: device commands and a
        # resident request (canonical request workflow), then DEMO RESET.
        assert _cmd(room, "power", "on", "light").json()["verified"] is True
        assert _cmd(room, "temperature", 70, "thermostat").status_code == 200
        req = requests.post(f"{API}/tasks/resident-request", timeout=5, json={
            "category": "maintenance", "resident_id": demo_resident, "room": room,
            "resident_words": "My sink is leaking", "summary": "My sink is leaking",
            "priority": "normal", "source": "aria_voice"})
        assert req.status_code == 200, req.text
        demo_task = req.json()["task_id"]
        body = requests.post(f"{API}/demo/reset", timeout=5).json()
        assert body["room"] == DEMO_ROOM and body["requests_closed"] >= 1

        async def demo_task_state(db):
            return await db.staff_tasks.find_one({"task_id": demo_task}, {"_id": 0, "status": 1, "room": 1})
        t = asyncio.run(_db_run(demo_task_state))
        assert t == {"status": "skipped", "room": DEMO_ROOM}
        assert asyncio.run(_db_run(snapshot)) == before  # other room: requests, devices, commands unchanged

        # Reset refuses while the public demo kiosk points at any other room.
        async def point_demo_elsewhere(db):
            await db.kiosks.update_many({"public_demo": True}, {"$set": {"public_demo": False}})
            await db.kiosks.update_one({"kiosk_id": f"{tag}_k"}, {"$set": {"public_demo": True}})
        asyncio.run(_db_run(point_demo_elsewhere))
        refused = requests.post(f"{API}/demo/reset", timeout=5)
        assert refused.status_code == 409 and DEMO_ROOM in refused.text
        assert asyncio.run(_db_run(snapshot)) == before
    finally:
        async def cleanup(db):
            from routes.demo_kiosk import ensure_demo_room
            for coll in (db.smart_devices, db.device_commands):
                await coll.delete_many({"device_id": {"$regex": f"^{tag}"}})
            await db.staff_tasks.delete_many({"task_id": {"$regex": f"^{tag}"}})
            await db.kiosks.delete_many({"kiosk_id": f"{tag}_k"})
            await ensure_demo_room(db)
        asyncio.run(_db_run(cleanup))
