"""Device truth (SC-10, SC-11, SC-12) through the real room-command path.

SC-11: a mock device in a real room is recorded as simulated and never as
verified - command, receipt and event all say so - while the demo-only room
keeps its verified simulator read-back, also marked simulated.
SC-10 (backend side): an unsupported light attribute is refused and the
light's state is unchanged.
SC-12: TV and thermostat commands record the conversation session_id on the
command and its receipt; a command without one records None.

The real room here is a throwaway room with a unique name; Room 214 and every
other existing room are snapshotted and must be unchanged. Needs a backend
named explicitly and its DB (MONGO_URL/DB_NAME), like test_demo_kiosk.py:

    TEST_API_BASE=http://127.0.0.1:8097 pytest tests/test_device_truth.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("TEST_API_BASE") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from device_adapters import execute_mock, simulation_fields  # noqa: E402


def test_mock_adapter_scope_unit():
    from routes.demo_kiosk import DEMO_ROOM
    light = {"protocol": "mock", "kind": "light", "capabilities": ["power"], "state": {"power": "off"}}
    real = asyncio.run(execute_mock({**light, "room": "R-unit"}, "power", "on"))
    demo = asyncio.run(execute_mock({**light, "room": DEMO_ROOM}, "power", "on"))
    assert real["verified"] is False and real["simulated"] is True and real["simulation_scope"] == "real_room"
    assert demo["verified"] is True and demo["simulated"] is True and demo["simulation_scope"] == "demo_room"
    assert real["state"] == demo["state"] == {"power": "on"}
    assert simulation_fields({"protocol": "home_assistant", "room": "R-unit"}) == {}


async def _db_run(fn):
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        return await fn(client[os.environ["DB_NAME"]])
    finally:
        client.close()


@pytest.fixture(scope="module")
def rooms():
    if not BASE_URL:
        pytest.skip("no backend named (TEST_API_BASE)")
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip(f"backend unreachable at {BASE_URL}")
    from routes.demo_kiosk import ensure_demo_room
    tag = uuid.uuid4().hex[:8]
    real_room = f"T-{tag}"
    devices = [
        {"device_id": f"dt_{tag}_light", "kind": "light", "capabilities": ["power", "brightness"],
         "state": {"power": "off", "brightness": 80}},
        {"device_id": f"dt_{tag}_tv", "kind": "tv", "capabilities": ["power", "volume"],
         "state": {"power": "off", "volume": 20}},
        {"device_id": f"dt_{tag}_thermo", "kind": "thermostat", "capabilities": ["power", "temperature"],
         "state": {"power": "on", "temperature": 72}},
    ]

    async def snapshot_others(db):
        q = {"room": {"$ne": real_room}}
        devs = await db.smart_devices.find(q, {"_id": 0}).sort("device_id").to_list(500)
        ids = [d["device_id"] for d in devs if d.get("room") != "DEMO"]
        cmds = await db.device_commands.count_documents({"device_id": {"$in": ids}})
        return [d for d in devs if d.get("room") != "DEMO"], cmds

    async def setup(db):
        demo = await ensure_demo_room(db)
        await db.smart_devices.insert_many([{**d, "label": f"Room {real_room} {d['kind']}", "protocol": "mock",
                                             "room": real_room, "online": True} for d in devices])
        return demo["room"]

    before = asyncio.run(_db_run(snapshot_others))
    demo_room = asyncio.run(_db_run(setup))
    requests.post(f"{API}/demo/reset", timeout=5).raise_for_status()
    yield {"real": real_room, "demo": demo_room, "tag": tag}

    async def cleanup(db):
        ids = [d["device_id"] for d in devices]
        await db.smart_devices.delete_many({"device_id": {"$in": ids}})
        await db.device_commands.delete_many({"device_id": {"$in": ids}})
        await db.receipts.delete_many({"related_object_id": {"$in": ids}})
    asyncio.run(_db_run(cleanup))
    # No other room's devices or commands changed (Room 214 included, if present).
    assert asyncio.run(_db_run(snapshot_others)) == before


def _cmd(room, action, value, kind, session_id=None):
    return requests.post(f"{API}/devices/public/room/{room}/command", timeout=5,
                         json={"action": action, "value": value, "kind": kind, "session_id": session_id})


def _records(command_id, device_id):
    async def go(db):
        cmd = await db.device_commands.find_one({"command_id": command_id}, {"_id": 0})
        rcpt = await db.receipts.find_one({"related_object_id": device_id}, {"_id": 0}, sort=[("created_at", -1)])
        ev = await db.events.find_one({"target_id": device_id}, {"_id": 0}, sort=[("timestamp", -1)])
        return cmd, rcpt, ev
    return asyncio.run(_db_run(go))


def test_sc11_real_room_mock_is_simulated_not_verified(rooms):
    r = _cmd(rooms["real"], "power", "on", "light", "rt_sc11")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is False and body["simulated"] is True and body["simulation_scope"] == "real_room"
    assert body["state"]["power"] == "on"  # the simulator still holds the state
    cmd, rcpt, ev = _records(body["command_id"], body["device_id"])
    assert cmd["verified"] is False and cmd["simulated"] is True and cmd["simulation_scope"] == "real_room"
    assert rcpt["simulated"] is True and rcpt["result_label"] == "simulated"
    if ev:  # event log present on this backend
        assert ev["verification_status"] == "simulated"


def test_sc11_demo_room_mock_stays_verified_and_marked_simulated(rooms):
    r = _cmd(rooms["demo"], "power", "on", "light", "rt_sc11_demo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True and body["simulated"] is True and body["simulation_scope"] == "demo_room"
    cmd, rcpt, _ = _records(body["command_id"], body["device_id"])
    assert cmd["verified"] is True and cmd["simulated"] is True
    assert rcpt["simulated"] is True and rcpt["result_label"] == "simulated"
    _cmd(rooms["demo"], "power", "off", "light")


def test_sc10_unsupported_light_attribute_changes_nothing(rooms):
    light = f"dt_{rooms['tag']}_light"

    async def state(db):
        return (await db.smart_devices.find_one({"device_id": light}, {"_id": 0, "state": 1}))["state"]
    _cmd(rooms["real"], "power", "off", "light")
    before = asyncio.run(_db_run(state))
    r = requests.post(f"{API}/devices/public/room/{rooms['real']}/command", timeout=5,
                      json={"action": "color", "value": [0, 200, 0], "device_id": light})
    assert r.status_code == 502 and "does not support color" in r.text
    assert asyncio.run(_db_run(state)) == before == {"power": "off", "brightness": 80}

    async def last_receipt(db):
        return await db.receipts.find_one({"related_object_id": light}, {"_id": 0}, sort=[("created_at", -1)])
    rcpt = asyncio.run(_db_run(last_receipt))
    assert rcpt["status"] == "failed" and rcpt["result_label"] == "failed" and rcpt["simulated"] is True


@pytest.mark.parametrize("kind,action,value", [("tv", "power", "on"), ("tv", "volume", 30),
                                               ("thermostat", "temperature", 70)])
def test_sc12_tv_and_thermostat_record_session_id(rooms, kind, action, value):
    r = _cmd(rooms["real"], action, value, kind, f"rt_sc12_{kind}")
    assert r.status_code == 200, r.text
    cmd, rcpt, _ = _records(r.json()["command_id"], r.json()["device_id"])
    assert cmd["session_id"] == f"rt_sc12_{kind}"
    assert rcpt["conversation_session_id"] == f"rt_sc12_{kind}"


def test_sc12_missing_session_stays_missing(rooms):
    r = _cmd(rooms["real"], "power", "off", "tv")
    assert r.status_code == 200, r.text
    cmd, rcpt, _ = _records(r.json()["command_id"], r.json()["device_id"])
    assert cmd["session_id"] is None and rcpt["conversation_session_id"] is None
