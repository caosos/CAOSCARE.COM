"""Device command execution adapters - the one place that decides HOW a
logical command (action/value) actually reaches a device. routes/devices.py
and every conversational tool (realtime_device_tools.py, the frontend's
executeDeviceTool) only ever speak the logical contract - action/value/kind
- and never know or care which adapter ran. Adding a real transport later
means adding one function here; the resident UI and Aria's tools do not
change (2026-08-27, per Michael's "prepare for real physical hardware"
directive).

Two adapters exist today:
  mock            - executes synchronously, no physical device. The only
                    kind actually deployed to any room right now.
  home_assistant  - calls a real, running Home Assistant instance's REST
                    API. Verified against the EliteDesk's own HA VM (see
                    docs/reports/2026-08-27-*-integration.md for the exact
                    round-trip proof) but NOT assigned to any resident-
                    facing room's device record - infrastructure only,
                    per "do not pretend a physical device is connected."

Every other protocol (bluetooth/wifi/ir/zigbee/matter/rf_433/rf_915) keeps
the existing, unchanged bridge-tablet queue/ack path in devices.py - that
IS those protocols' real adapter, for when a physical Android bridge tablet
is deployed to a room. Nothing here replaces it.
"""
import os
import httpx

HA_BASE_URL = os.environ.get("HA_BASE_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

# power on/off is the only logical action mapped to HA services so far -
# deliberately not built out further (brightness/volume/input HA service
# mapping) until a real HA-backed room device actually needs it, per "do
# not overbuild."
_HA_POWER_SERVICE = {"on": "turn_on", "off": "turn_off"}


async def execute_mock(device: dict, action: str, value):
    """Always succeeds synchronously - no physical device exists to fail against."""
    return {"detail": "mock room device - executed synchronously, no bridge tablet"}


async def execute_home_assistant(device: dict, action: str, value):
    """`device.endpoint` must be a real HA entity_id (e.g.
    "input_boolean.test_lamp" or eventually "switch.bedroom_lamp"). Raises
    rather than silently succeeding if HA isn't configured, the device has
    no entity_id, or the action isn't mapped yet - a failed real command
    must never be reported as a success."""
    if not HA_BASE_URL or not HA_TOKEN:
        raise RuntimeError("Home Assistant adapter not configured (HA_BASE_URL/HA_TOKEN unset)")
    entity_id = device.get("endpoint")
    if not entity_id or "." not in entity_id:
        raise RuntimeError("Device has no valid Home Assistant entity_id (endpoint field)")
    if action != "power" or value not in _HA_POWER_SERVICE:
        raise RuntimeError(f"Home Assistant adapter does not support action={action!r} value={value!r} yet")
    domain = entity_id.split(".", 1)[0]
    service = _HA_POWER_SERVICE[value]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{HA_BASE_URL}/api/services/{domain}/{service}",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"},
            json={"entity_id": entity_id},
        )
        resp.raise_for_status()
        # HA's service-call endpoint returns 200 even when entity_id matches
        # NOTHING (a typo, a removed device, one that was never really
        # registered) - the response body is the list of entities that
        # actually changed state, which is the only real signal. A 200 with
        # an empty list is not success (confirmed live against this
        # EliteDesk's own HA instance, 2026-08-27) - must not be reported
        # as one.
        changed = resp.json()
        if not any(s.get("entity_id") == entity_id for s in changed):
            raise RuntimeError(f"Home Assistant has no entity '{entity_id}' - command had no effect")
    return {"detail": f"home_assistant: called {domain}.{service} on {entity_id}"}


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
