"""Server-side room device tools (Voice PE bridge): grounding, "which one?",
read-back wording. In-process with a stand-in device list and command path;
no Mongo, no Home Assistant, nothing physical is commanded."""
import asyncio

import pytest

import routes.devices as devices_mod
import routes.room_device_tools as rdt
from routes.device_grounding import numbers_in, power_direction_mismatch, tv_power_grounded

ROOM = "214"
DEVICES = [
    {"device_id": "desk", "room": ROOM, "kind": "light", "label": "Room 214 Desk lamp",
     "capabilities": ["power", "brightness", "color"], "state": {"power": "on"}},
    {"device_id": "over", "room": ROOM, "kind": "light", "label": "Room 214 Overhead light",
     "capabilities": ["power", "brightness"], "state": {"power": "off"}},
    {"device_id": "tv", "room": ROOM, "kind": "tv", "label": "Room 214 TV", "protocol": "ir_blaster",
     "capabilities": ["power", "volume", "volume_step", "mute"], "state": {}},
]


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_):
        return self

    async def to_list(self, _n):
        return self.rows


class _Coll:
    def find(self, q, _proj=None):
        rows = [d for d in DEVICES if d["room"] == q.get("room") and ("kind" not in q or d["kind"] == q["kind"])]
        return _Cursor(rows)


class _Db:
    smart_devices = _Coll()


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_exec(room, cmd):
        calls.append((cmd.device_id, cmd.action, cmd.value))
        return {"verified": cmd.device_id != "tv", "state": {cmd.action: cmd.value}}

    monkeypatch.setattr(rdt, "db", _Db())
    monkeypatch.setattr(devices_mod, "execute_room_command", fake_exec)
    rdt._refusals.clear()
    return calls


def run(name, args, heard, session="s1"):
    return asyncio.run(rdt.run_room_device_tool(name, args, {"room": ROOM, "session_id": session,
                                                            "last_user_text": heard}))


def test_grounding_rules():
    assert power_direction_mismatch("off", "turn on my overhead light")
    assert power_direction_mismatch("off", "Overhead line")  # 2026-10-12 false wake
    assert power_direction_mismatch("on", "turn on the overhead light") is None
    assert power_direction_mismatch("on", "the overhead one", answering=True) is None
    assert tv_power_grounded("turn the TV off", "off") and not tv_power_grounded("make it quiet", "off")
    assert not tv_power_grounded("don't turn the TV off", "off")
    assert {11, 21} <= numbers_in("channel 11 or twenty one")


def test_named_light_turns_on_and_wrong_direction_is_refused(sent):
    r = run("toggle_light", {"state": "on"}, "turn on the overhead light")
    assert r["ok"] and r["message"] == "turned the overhead light on." and sent == [("over", "power", "on")]
    r = run("toggle_light", {"state": "off"}, "turn on the overhead light", session="s2")
    assert not r["ok"] and len(sent) == 1


def test_which_light_is_asked_once_then_answer_is_used(sent):
    r = run("toggle_light", {"state": "on"}, "turn on the light")
    assert r["ambiguous"] and set(r["choices"]) == {"desk lamp", "overhead light"} and not sent
    again = run("toggle_light", {"state": "on"}, "turn on the light")
    assert again["ambiguous"] and not sent
    r = run("toggle_light", {"state": "on", "device": "overhead light"}, "the overhead one")
    assert r["ok"] and sent == [("over", "power", "on")]


def test_unsupported_colour_changes_nothing(sent):
    r = run("toggle_light", {"color": "green", "device": "overhead light"}, "make the overhead light green")
    assert not r["ok"] and "doesn't support color" in r["message"] and not sent


def test_infrared_tv_is_sent_not_confirmed(sent):
    r = run("toggle_tv", {"state": "on"}, "turn the TV on")
    assert r["ok"] and "does not confirm" in r["message"] and sent == [("tv", "power", "on")]
    r = run("toggle_tv", {"state": "off"}, "it's too loud in here")
    assert not r["ok"] and len(sent) == 1
    r = run("adjust_tv_volume", {"direction": "down"}, "turn it down a bit")
    assert r["ok"] and sent[-1] == ("tv", "volume_step", -3) and "don't name a level" in r["message"]
