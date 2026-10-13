"""`ir_blaster` adapter: a TV (any room) controlled by infrared through a Home Assistant
IR blaster (today: the XIAO IR Mate running room-node/ir_mate/caoscare_ir_mate.yaml).

Infrared is one-way: the TV never reports back. So every result is verified=False, and the
state it returns is what CAOSCare SENT, not what it saw:
  * power on/off   - the table's discrete codes (a toggle-only table cannot promise a state);
  * volume N       - from a known estimate, step the difference; with no estimate, step down
                     to zero then up N, so the level is known again (volume_estimated=True);
  * volume_step ±n - n presses; keeps the estimate when there is one, never invents one;
  * mute           - one press of mute.
device.endpoint is the blaster's ESPHome service prefix in HA (e.g.
"esphome.xiao_smart_ir_mate_812dfc"); device.ir_codeset names the table in ir_codesets.py.
"""
import asyncio
import os

import httpx

from ir_codesets import codeset

HA_BASE_URL = os.environ.get("HA_BASE_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
_sleep = asyncio.sleep                      # patched in tests


async def _press(client, device: dict, table: dict, key: str, times: int = 1) -> int:
    domain, prefix = device["endpoint"].split(".", 1)
    url = f"{HA_BASE_URL}/api/services/{domain}/{prefix}_{table['transmit']}"
    for i in range(times):
        r = await client.post(url, headers={"Authorization": f"Bearer {HA_TOKEN}"},
                              json={"data": table["codes"][key], "nbits": table["nbits"]})
        r.raise_for_status()
        if i < times - 1:
            await _sleep(table["step_gap_s"])
    return times


async def execute_ir_blaster(device: dict, action: str, value):
    if not HA_BASE_URL or not HA_TOKEN:
        raise RuntimeError("IR blaster adapter not configured (HA_BASE_URL/HA_TOKEN unset)")
    if not device.get("endpoint") or "." not in device["endpoint"]:
        raise RuntimeError("IR device has no blaster service (endpoint field)")
    table = codeset(device.get("ir_codeset") or "")
    state = dict(device.get("state") or {})
    async with httpx.AsyncClient(timeout=10.0) as client:
        if action == "power":
            if value not in ("on", "off"):
                raise RuntimeError(f"power value must be on/off, got {value!r}")
            key = f"power_{value}"
            if key not in table["codes"]:
                raise RuntimeError("this TV's code table only has a power toggle; it cannot promise on or off")
            await _press(client, device, table, key)
            state["power"] = value
            sent = f"power {value}"
        elif action == "volume":
            target = max(0, min(table["volume_steps"], int(value)))
            known = state.get("volume") if state.get("volume_estimated") else None
            if isinstance(known, int):
                diff = target - known
                if diff:
                    await _press(client, device, table, "volume_up" if diff > 0 else "volume_down", abs(diff))
                sent = f"volume {known}->{target} ({abs(diff)} steps)"
            else:
                await _press(client, device, table, "volume_down", table["volume_steps"])
                if target:
                    await _sleep(1.0)
                    await _press(client, device, table, "volume_up", target)
                sent = f"volume reset to 0 then up {target}"
            state.update(volume=target, volume_estimated=True)
        elif action == "volume_step":
            n = int(value)
            if n == 0 or abs(n) > table["volume_steps"]:
                raise RuntimeError(f"volume_step must be a non-zero step count, got {value!r}")
            await _press(client, device, table, "volume_up" if n > 0 else "volume_down", abs(n))
            if state.get("volume_estimated") and isinstance(state.get("volume"), int):
                state["volume"] = max(0, min(table["volume_steps"], state["volume"] + n))
            sent = f"volume {'up' if n > 0 else 'down'} {abs(n)} steps"
        elif action == "mute":
            await _press(client, device, table, "mute")
            sent = "mute"
        else:
            raise RuntimeError(f"IR blaster adapter does not support action={action!r}")
    return {
        "detail": f"ir_blaster: sent {sent} via {device['endpoint']} (one-way infrared; the TV does not report back)",
        "state": state, "verified": False,
    }
