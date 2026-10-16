"""Room device inventory and the blinds contract (aria-room-runtime-fixes-001).

Room 214 Aria said she had no device list. The inventory comes from the
device registry: what is connected, what each device can do, what state its
transport can actually report, and which supported device types this room
lacks. Blinds are a product capability whether or not a given room has them.

Pure tests use Room-214-shaped rows; DB/HTTP tests use a throwaway room.
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.room_device_inventory import build_room_inventory  # noqa: E402

BASE_URL = (os.environ.get("TEST_API_BASE") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")

ROOM_214 = [  # shapes copied from the live registry, 2026-10-16
    {"device_id": "dev_tv", "label": "Room 214 TV", "kind": "tv", "protocol": "ir_blaster", "room": "214",
     "capabilities": ["power", "volume", "volume_step", "mute"],
     "state": {"power": "on", "volume": 50, "volume_estimated": True}, "online": True},
    {"device_id": "dev_th", "label": "Room 214 thermostat", "kind": "thermostat", "protocol": "mock", "room": "214",
     "capabilities": ["power", "temperature"], "state": {"temperature": 72, "power": "on"}, "online": True},
    {"device_id": "dev_desk", "label": "Room 214 desk lamp", "kind": "light", "protocol": "home_assistant", "room": "214",
     "capabilities": ["power", "brightness", "color", "color_temp"], "state": {"power": "off"}, "online": True},
    {"device_id": "dev_oldac", "label": "Room 214 portable AC (MOCK, retired)", "kind": "ac", "protocol": "mock",
     "room": "214", "capabilities": ["power", "temperature", "fan_speed"], "state": {}, "online": False},
    {"device_id": "dev_ac", "label": "Room 214 AC (Midea)", "kind": "ac", "protocol": "home_assistant", "room": "214",
     "capabilities": ["power", "temperature", "hvac_mode"], "state": {"power": "on"}, "online": True},
]


def test_room_214_inventory_is_truthful():
    inv = build_room_inventory("214", ROOM_214)
    names = [c["name"] for c in inv["connected"]]
    assert names == ["TV", "thermostat", "desk lamp", "AC (Midea)"]          # offline mock excluded
    assert inv["offline"] == ["portable AC (MOCK, retired)"]
    assert inv["not_connected"] == ["motorized blinds"]                       # supported, not in this room
    tv = inv["connected"][0]
    assert tv["state_feedback"] == "one_way" and tv["reported_state"] == {}  # IR volume 50 is an estimate
    assert "turn the volume up or down" in tv["actions"] and "mute or unmute it" in tv["actions"]
    assert inv["connected"][1]["state_feedback"] == "simulated"
    assert inv["connected"][2]["reported_state"] == {"power": "off"}
    s = inv["summary"]
    assert "can't confirm what it actually did" in s
    assert "simulated test device, not physical hardware" in s
    assert "Not connected in this room: motorized blinds." in s
    assert "volume 50" not in s


@pytest.mark.parametrize("protocol,feedback", [("mock", "simulated"), ("home_assistant", "reported"),
                                               ("rf_433", "one_way"), ("zigbee", "bridge_ack")])
def test_blinds_room_lists_open_close_set(protocol, feedback):
    blinds = {"device_id": "b1", "label": "Room 9 blinds", "kind": "blinds", "protocol": protocol, "room": "9",
              "capabilities": ["position"], "state": {"position": 40}, "online": True}
    inv = build_room_inventory("9", [blinds])
    c = inv["connected"][0]
    assert c["actions"] == ["open it, close it, or set how far open"]
    assert c["state_feedback"] == feedback
    assert "motorized blinds" not in inv["not_connected"]
    assert ("position" in c["reported_state"]) == (feedback in ("reported", "simulated"))


def test_empty_room_says_so():
    inv = build_room_inventory("X", [])
    assert inv["connected"] == [] and inv["summary"].startswith("No controllable devices are connected")


@pytest.fixture()
def room():
    if not BASE_URL:
        pytest.skip("no backend named (TEST_API_BASE / REACT_APP_BACKEND_URL)")
    from deps import db
    name = f"T-INV-{uuid.uuid4().hex[:6]}"
    rows = [
        {"device_id": f"dev_{name}_b", "label": f"Room {name} blinds", "kind": "blinds", "protocol": "mock",
         "room": name, "capabilities": ["position"], "state": {"position": 0}, "online": True},
        {"device_id": f"dev_{name}_l", "label": f"Room {name} lamp", "kind": "light", "protocol": "mock",
         "room": name, "capabilities": ["power"], "state": {"power": "off"}, "online": True},
    ]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(db.smart_devices.insert_many([dict(r) for r in rows]))
    yield name
    loop.run_until_complete(db.smart_devices.delete_many({"room": name}))
    loop.run_until_complete(db.device_commands.delete_many({"device_id": {"$in": [r["device_id"] for r in rows]}}))


def test_inventory_route_and_blinds_command_through_the_real_path(room):
    inv = requests.get(f"{BASE_URL}/api/devices/public/room/{room}/inventory", timeout=10).json()
    assert {c["kind"] for c in inv["connected"]} == {"blinds", "light"}
    assert "motorized blinds" not in inv["not_connected"]
    r = requests.post(f"{BASE_URL}/api/devices/public/room/{room}/command",
                      json={"action": "position", "value": 100, "kind": "blinds"}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    # A mock device in a real room is simulated and never recorded as verified (SC-11).
    assert body["state"]["position"] == 100 and body["simulated"] is True and body["verified"] is False
    bad = requests.post(f"{BASE_URL}/api/devices/public/room/{room}/command",
                        json={"action": "position", "value": 150, "kind": "blinds"}, timeout=10)
    assert bad.status_code >= 400                                            # command validation
    none = requests.get(f"{BASE_URL}/api/devices/public/room/{room}-none/inventory", timeout=10).json()
    assert none["connected"] == [] and "motorized blinds" in none["not_connected"]


def test_simulated_tv_supports_the_call_duck_mute_and_steps():
    from simulated_device import apply_simulated_command
    tv = {"kind": "tv", "capabilities": ["mute", "volume_step"], "state": {"volume": 50}}
    muted = apply_simulated_command(tv, "mute", True)
    assert muted["mute"] is True
    assert apply_simulated_command({**tv, "state": muted}, "mute", True)["mute"] is False   # a toggle, like IR
    assert apply_simulated_command(tv, "volume_step", -15)["volume"] == 35
    assert apply_simulated_command(tv, "volume_step", 80)["volume"] == 100
