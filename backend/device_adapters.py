"""Device command execution adapters - the one place that decides HOW a
logical command (action/value) actually reaches a device. routes/devices.py
and every conversational tool (realtime_device_tools.py, the frontend's
executeDeviceTool) only ever speak the logical contract - action/value/kind
- and never know or care which adapter ran. Adding a real transport later
means adding one function here; the resident UI and Aria's tools do not
change (2026-08-27, per Michael's "prepare for real physical hardware"
directive).

Two adapters exist today:
  mock            - executes synchronously, no physical device.
  home_assistant  - calls a real, running Home Assistant instance's REST
                    API, then reads the entity back to prove the physical
                    device actually reflects the change - HA returning 200
                    is never treated as proof by itself (2026-09-05, real
                    Matter light work: a resident-facing "I turned it green"
                    must be true, not just "the API call didn't error").

Every other protocol (bluetooth/wifi/ir/zigbee/matter/rf_433/rf_915) keeps
the existing, unchanged bridge-tablet queue/ack path in devices.py - that
IS those protocols' real adapter, for when a physical Android bridge tablet
is deployed to a room. Nothing here replaces it. "matter" stays in that
list for a future direct-radio bridge tablet - a Matter device reached
THROUGH Home Assistant (today's only real one) uses protocol="home_assistant"
like any other HA-backed device, not protocol="matter".
"""
import asyncio
import colorsys
import os
from typing import Optional

import httpx

HA_BASE_URL = os.environ.get("HA_BASE_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

_HA_POWER_SERVICE = {"on": "turn_on", "off": "turn_off"}
# Natural verification tolerances for a real device's read-back vs. the
# requested value - HA's 0-255<->0-100 brightness rounding and a real
# bulb's own internal color-point quantization mean "close" is the honest
# bar, not byte-exact (confirmed against the real Tapo L535E, 2026-09-05).
_BRIGHTNESS_TOLERANCE_PCT = 6
_HUE_TOLERANCE_DEG = 30
_KELVIN_TOLERANCE = 150
_VERIFY_RETRIES = 3
_VERIFY_DELAY_S = 0.4


async def execute_mock(device: dict, action: str, value):
    """Always succeeds synchronously - no physical device exists to fail against."""
    return {"detail": "mock room device - executed synchronously, no bridge tablet"}


def _brightness255_to_pct(raw) -> Optional[int]:
    return round(raw * 100 / 255) if isinstance(raw, (int, float)) else None


def _read_light_state(attrs: dict, ha_state: str) -> dict:
    """Normalize one HA light entity's attributes into CAOSCare's generic
    state contract - only the fields meaningful for the entity's CURRENT
    color_mode, so a stale color never lingers in state after switching to
    color_temp (or vice versa) - both real modes on the same real bulb,
    confirmed live."""
    state: dict = {"power": "on" if ha_state == "on" else "off"}
    pct = _brightness255_to_pct(attrs.get("brightness"))
    if pct is not None:
        state["brightness"] = pct
    mode = attrs.get("color_mode")
    if mode in ("hs", "rgb", "xy") and attrs.get("rgb_color"):
        state["color"] = list(attrs["rgb_color"])
    elif mode == "color_temp" and attrs.get("color_temp_kelvin"):
        state["color_temp"] = attrs["color_temp_kelvin"]
    return state


async def _ha_get_state(client: httpx.AsyncClient, entity_id: str) -> dict:
    resp = await client.get(
        f"{HA_BASE_URL}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {HA_TOKEN}"},
    )
    resp.raise_for_status()
    return resp.json()


def _hue_degrees(rgb: list) -> Optional[float]:
    h, s, _v = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    return None if s < 0.08 else h * 360  # near-white/gray has no meaningful hue


def _verifies(action: str, requested, after: dict) -> bool:
    attrs = after.get("attributes", {})
    ha_state = after.get("state")
    if action == "power":
        return ha_state == requested
    if ha_state != "on":
        return False  # brightness/color/color_temp are meaningless on an off light
    if action == "brightness":
        pct = _brightness255_to_pct(attrs.get("brightness"))
        return pct is not None and abs(pct - int(requested)) <= _BRIGHTNESS_TOLERANCE_PCT
    if action == "color":
        # Real device proof (2026-09-05, the actual Tapo L535E): a color
        # request gets gamut-remapped to the device's own full-saturation
        # rendering of that hue - hs_color for a requested [0,200,0] came
        # back [119.055, 100.0], not the requested RGB triplet. Comparing
        # raw RGB distance produced false verification failures on a
        # command that had genuinely, visibly succeeded. Hue is the part
        # of "color" a resident's request is actually about ("make it
        # green") and the part real RGB/HS lights reliably preserve;
        # saturation/value are legitimately theirs to renormalize.
        requested_hue = _hue_degrees(requested)
        hs = attrs.get("hs_color")
        if requested_hue is None:  # requested white/gray - verify low saturation instead
            return isinstance(hs, list) and hs[1] <= 15
        if not (isinstance(hs, list) and len(hs) == 2):
            return False
        diff = abs(hs[0] - requested_hue) % 360
        return min(diff, 360 - diff) <= _HUE_TOLERANCE_DEG
    if action == "color_temp":
        kelvin = attrs.get("color_temp_kelvin")
        return isinstance(kelvin, (int, float)) and abs(kelvin - int(requested)) <= _KELVIN_TOLERANCE
    return True


async def execute_home_assistant(device: dict, action: str, value):
    """`device.endpoint` must be a real HA entity_id. Raises rather than
    silently succeeding if HA isn't configured, the device has no
    entity_id, the action isn't mapped, or - critically - the post-command
    read-back doesn't actually show the change: a failed or partial real
    command must never be reported as a success."""
    if not HA_BASE_URL or not HA_TOKEN:
        raise RuntimeError("Home Assistant adapter not configured (HA_BASE_URL/HA_TOKEN unset)")
    entity_id = device.get("endpoint")
    if not entity_id or "." not in entity_id:
        raise RuntimeError("Device has no valid Home Assistant entity_id (endpoint field)")
    domain = entity_id.split(".", 1)[0]

    async with httpx.AsyncClient(timeout=10.0) as client:
        before = await _ha_get_state(client, entity_id)

        if action == "power":
            if value not in _HA_POWER_SERVICE:
                raise RuntimeError(f"Home Assistant power adapter does not support value={value!r}")
            service, payload = _HA_POWER_SERVICE[value], {"entity_id": entity_id}
        elif action == "brightness" and domain == "light":
            pct = max(1, min(100, int(value)))
            service, payload = "turn_on", {"entity_id": entity_id, "brightness_pct": pct}
        elif action == "color" and domain == "light":
            if not (isinstance(value, list) and len(value) == 3 and all(isinstance(c, int) for c in value)):
                raise RuntimeError(f"color action requires an [r,g,b] int triplet, got {value!r}")
            service, payload = "turn_on", {"entity_id": entity_id, "rgb_color": value}
        elif action == "color_temp" and domain == "light":
            lo = before.get("attributes", {}).get("min_color_temp_kelvin", 2000)
            hi = before.get("attributes", {}).get("max_color_temp_kelvin", 6500)
            kelvin = max(lo, min(hi, int(value)))
            service, payload = "turn_on", {"entity_id": entity_id, "color_temp_kelvin": kelvin}
        else:
            raise RuntimeError(f"Home Assistant adapter does not support action={action!r} on domain={domain!r}")

        resp = await client.post(
            f"{HA_BASE_URL}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        # NOTE (2026-08-27, real input_boolean test): HA's service-call
        # response body lists entities that changed state, and an empty
        # list used to mean "no such entity". That check was REMOVED
        # 2026-09-05 after proving it wrong against this real Matter bulb:
        # `light.turn_on` on `light.smart_multicolor_bulb` returns `[]`
        # even on genuine, confirmed success (the read-back below shows
        # `state: "on"` regardless). The independent read-back is strictly
        # more correct than trusting the service call's own response body,
        # so it is now the ONLY verification - never re-add a hard fail on
        # an empty `changed` list without re-proving it against real
        # hardware first.

        # Real read-back, independent of the service call's own response -
        # the actual acceptance bar for this whole feature. A real Matter
        # device can lag the service call by a beat, so retry briefly
        # rather than declaring failure on the first still-stale read.
        after = None
        for attempt in range(_VERIFY_RETRIES):
            after = await _ha_get_state(client, entity_id)
            if _verifies(action, value, after):
                break
            if attempt < _VERIFY_RETRIES - 1:
                await asyncio.sleep(_VERIFY_DELAY_S)
        if not _verifies(action, value, after):
            raise RuntimeError(
                f"Home Assistant accepted the command but the read-back state does not "
                f"confirm it: entity={entity_id} action={action} requested={value!r} "
                f"actual_state={after.get('state')!r} actual_attrs={after.get('attributes')!r}"
            )

    verified_state = (
        _read_light_state(after.get("attributes", {}), after.get("state", ""))
        if domain == "light" else {"power": after.get("state")}
    )
    return {
        "detail": f"home_assistant: called {domain}.{service} on {entity_id}, verified by read-back",
        "state": verified_state,
    }


ADAPTERS = {"mock": execute_mock, "home_assistant": execute_home_assistant}


def has_adapter(protocol: str) -> bool:
    return protocol in ADAPTERS


async def execute(device: dict, action: str, value) -> dict:
    """Raises on failure - the caller decides what that means for the
    command's persisted status. Only called for protocols in ADAPTERS;
    every other (real, physical-transport) protocol uses devices.py's
    existing bridge-tablet queue path instead."""
    return await ADAPTERS[device["protocol"]](device, action, value)


async def ha_health() -> dict:
    """Real connectivity check against the configured Home Assistant
    instance - used by the admin assistant's get_home_assistant_status
    tool (routes/admin_assistant_executor.py) so it never has to guess or
    assume HA is reachable. Never raises - always returns a status the
    caller can report honestly."""
    if not HA_BASE_URL or not HA_TOKEN:
        return {"status": "not_configured", "base_url": HA_BASE_URL or None}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{HA_BASE_URL}/api/states",
                headers={"Authorization": f"Bearer {HA_TOKEN}"},
            )
        if resp.status_code == 401:
            return {"status": "unauthorized", "base_url": HA_BASE_URL}
        resp.raise_for_status()
        entities = resp.json()
        return {"status": "connected", "base_url": HA_BASE_URL, "entity_count": len(entities)}
    except Exception as e:
        return {"status": "unreachable", "base_url": HA_BASE_URL, "detail": str(e)}
