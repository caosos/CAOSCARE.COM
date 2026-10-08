"""RQ-021: blinds and TV channel/volume through the real room-command path.

Demo room: the baseline already holds blinds (position) and a TV (channel,
volume); a command changes the stored state, reads it back (verified, but
always labelled simulated) and files a receipt. Refused commands - a range
the device rejects, a capability it lacks - change nothing and are recorded
as failed. A mock in a real room is simulated and never verified (SC-11).
Needs a named backend + its DB, like test_device_truth.py:

    TEST_API_BASE=http://127.0.0.1:8097 MONGO_URL=... DB_NAME=... pytest tests/test_rq021_room_controls.py -q
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
    real = f"T-{tag}"
    devs = [
        {"device_id": f"rq21_{tag}_blinds", "kind": "blinds", "capabilities": ["position"], "state": {"position": 0}},
        {"device_id": f"rq21_{tag}_tv", "kind": "tv", "capabilities": ["power", "volume"],
         "state": {"power": "on", "volume": 20}},
    ]

    async def setup(db):
        demo = await ensure_demo_room(db)
        await db.smart_devices.insert_many([{**d, "label": f"Room {real} {d['kind']}", "protocol": "mock",
                                             "room": real, "online": True} for d in devs])
        return demo["room"]
    demo_room = asyncio.run(_db_run(setup))
    requests.post(f"{API}/demo/reset", timeout=5).raise_for_status()
    yield {"real": real, "demo": demo_room, "tag": tag}
    requests.post(f"{API}/demo/reset", timeout=5)

    async def cleanup(db):
        ids = [d["device_id"] for d in devs]
        await db.smart_devices.delete_many({"device_id": {"$in": ids}})
        await db.device_commands.delete_many({"device_id": {"$in": ids}})
        await db.receipts.delete_many({"related_object_id": {"$in": ids}})
    asyncio.run(_db_run(cleanup))


def _cmd(room, action, value, kind, session_id="rt_rq021", device_id=None):
    return requests.post(f"{API}/devices/public/room/{room}/command", timeout=5,
                         json={"action": action, "value": value, "kind": kind,
                               "session_id": session_id, "device_id": device_id})


def _receipt(device_id):
    async def go(db):
        return await db.receipts.find_one({"related_object_id": device_id}, {"_id": 0}, sort=[("created_at", -1)])
    return asyncio.run(_db_run(go))


def _state(device_id):
    async def go(db):
        return (await db.smart_devices.find_one({"device_id": device_id}, {"_id": 0, "state": 1}))["state"]
    return asyncio.run(_db_run(go))


def test_demo_blinds_open_close_set_read_back_and_receipt(rooms):
    for value in (100, 0, 35):
        r = _cmd(rooms["demo"], "position", value, "blinds")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["state"]["position"] == value
        assert body["simulated"] is True and body["simulation_scope"] == "demo_room" and body["verified"] is True
        assert _state(body["device_id"])["position"] == value
    rcpt = _receipt(body["device_id"])
    assert rcpt["simulated"] is True and rcpt["result_label"] == "simulated"
    assert rcpt["conversation_session_id"] == "rt_rq021" and rcpt["status"] == "completed"


def test_demo_tv_channel_and_volume_step(rooms):
    ch = _cmd(rooms["demo"], "channel", 11, "tv")
    assert ch.status_code == 200, ch.text
    assert ch.json()["state"]["channel"] == 11 and ch.json()["simulated"] is True
    vol = _cmd(rooms["demo"], "volume", 30, "tv")
    assert vol.status_code == 200 and vol.json()["state"]["volume"] == 30
    assert vol.json()["state"]["channel"] == 11  # a volume step keeps the channel
    assert _receipt(vol.json()["device_id"])["result_label"] == "simulated"


@pytest.mark.parametrize("action,value,kind,needle", [
    ("position", 150, "blinds", "between 0 and 100"),
    ("position", "up", "blinds", "must be a number"),
    ("channel", 0, "tv", "between 1 and 999"),
    ("volume", 101, "tv", "between 0 and 100"),
])
def test_refused_value_changes_nothing_and_is_recorded(rooms, action, value, kind, needle):
    before = requests.get(f"{API}/devices/public/by-room/{rooms['demo']}", timeout=5).json()
    r = _cmd(rooms["demo"], action, value, kind)
    assert r.status_code == 502 and needle in r.text, r.text
    after = requests.get(f"{API}/devices/public/by-room/{rooms['demo']}", timeout=5).json()
    assert [d["state"] for d in after] == [d["state"] for d in before]
    target = next(d for d in after if d["kind"] == kind)
    rcpt = _receipt(target["device_id"])
    assert rcpt["status"] == "failed" and rcpt["result_label"] == "failed" and rcpt["simulated"] is True


def test_missing_capability_is_refused_and_real_room_is_never_verified(rooms):
    # The throwaway TV has no channel capability.
    r = _cmd(rooms["real"], "channel", 5, "tv")
    assert r.status_code == 400 and "supports channel" in r.text  # no TV there has the capability
    assert _state(f"rq21_{rooms['tag']}_tv") == {"power": "on", "volume": 20}
    # A mock blinds in a real room moves but is simulated, not verified.
    ok = _cmd(rooms["real"], "position", 70, "blinds")
    assert ok.status_code == 200
    body = ok.json()
    assert body["simulated"] is True and body["simulation_scope"] == "real_room" and body["verified"] is False
    assert body["state"]["position"] == 70


def test_demo_reset_restores_blinds_and_tv_baseline(rooms):
    _cmd(rooms["demo"], "position", 80, "blinds")
    _cmd(rooms["demo"], "channel", 42, "tv")
    requests.post(f"{API}/demo/reset", timeout=5).raise_for_status()
    devs = {d["kind"]: d for d in requests.get(f"{API}/devices/public/by-room/{rooms['demo']}", timeout=5).json()}
    assert devs["blinds"]["state"] == {"position": 0}
    assert devs["tv"]["state"]["channel"] == 3 and devs["tv"]["state"]["power"] == "off"
