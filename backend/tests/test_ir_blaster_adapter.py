"""ir_blaster adapter (any room's TV through an HA IR blaster). One-way infrared: results are
always verified=False and the state is what was SENT. HA is faked; no device is touched."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import device_ir_adapter as ir  # noqa: E402

TV = {"device_id": "dev_tv", "kind": "tv", "protocol": "ir_blaster", "ir_codeset": "sony_sirc12",
      "endpoint": "esphome.xiao_smart_ir_mate_812dfc", "state": {"power": "off"}}


class FakeClient:
    def __init__(self, *a, **k): self.sent = SENT
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, headers=None, json=None):
        self.sent.append((url, json["data"], json["nbits"]))
        class R:
            def raise_for_status(self): pass
        return R()


SENT = []


@pytest.fixture(autouse=True)
def fake_ha(monkeypatch):
    SENT.clear()
    monkeypatch.setattr(ir, "HA_BASE_URL", "http://ha.test")
    monkeypatch.setattr(ir, "HA_TOKEN", "t")
    monkeypatch.setattr(ir.httpx, "AsyncClient", FakeClient)
    async def no_sleep(_): pass
    monkeypatch.setattr(ir, "_sleep", no_sleep)


def run(device, action, value):
    return asyncio.get_event_loop().run_until_complete(ir.execute_ir_blaster(device, action, value))


def codes():
    return [c for _, c, _ in SENT]


def test_power_uses_discrete_codes_and_is_never_claimed_verified():
    r = run(TV, "power", "on")
    assert SENT == [("http://ha.test/api/services/esphome/xiao_smart_ir_mate_812dfc_send_sony", 0x750, 12)]
    assert r["verified"] is False and r["state"]["power"] == "on" and "does not report back" in r["detail"]
    SENT.clear(); run(TV, "power", "off")
    assert codes() == [0xF50]


def test_absolute_volume_without_an_estimate_resets_then_counts_up():
    r = run(TV, "volume", 50)
    assert codes() == [0xC90] * 100 + [0x490] * 50
    assert r["state"]["volume"] == 50 and r["state"]["volume_estimated"] is True and r["verified"] is False


def test_absolute_volume_with_an_estimate_steps_only_the_difference():
    tv = {**TV, "state": {"power": "on", "volume": 50, "volume_estimated": True}}
    r = run(tv, "volume", 30)
    assert codes() == [0xC90] * 20 and r["state"]["volume"] == 30


def test_relative_steps_keep_an_estimate_but_never_invent_one():
    r = run(TV, "volume_step", 3)
    assert codes() == [0x490] * 3 and "volume" not in r["state"]
    SENT.clear()
    tv = {**TV, "state": {"volume": 50, "volume_estimated": True}}
    assert run(tv, "volume_step", -4)["state"]["volume"] == 46 and codes() == [0xC90] * 4


def test_unknown_table_or_action_or_toggle_only_power_is_refused():
    for device, action, value in (({**TV, "ir_codeset": "nope"}, "power", "on"), (TV, "channel", 5),
                                  (TV, "power", "toggle"), (TV, "volume_step", 0)):
        with pytest.raises(RuntimeError):
            run(device, action, value)
    assert SENT == []


def test_registered_as_a_device_adapter():
    import device_adapters
    assert device_adapters.has_adapter("ir_blaster")
