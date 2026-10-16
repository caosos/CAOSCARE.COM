"""What Aria can control in THIS room, and how much she can know about it.

Owner directive 2026-10-16 (aria-room-runtime-fixes-001): asked "are my
blinds connected?", Room 214 Aria said she had no device list and told
Michael to look at the screen. Aria must know, from the server's own device
registry (db.smart_devices), without a resident ever inspecting the UI:

  A. the device-control functions she supports in general (CONTROL_FUNCTIONS)
  B. the devices actually configured and online in this room
  C. what each of those devices can do (its declared capabilities)
  D. the state it reports, when its transport can read state back
  E. when state cannot be verified (one-way infrared / RF, bridge queue,
     or a simulated device that is not physical hardware)

A capability Aria supports but this room lacks (e.g. motorized blinds in
Room 214 today) is listed under `not_connected`, so she says so plainly
instead of claiming or denying the product feature. The tool layer
(frontend realtimeDeviceTools.js get_room_status) speaks from `summary`.
"""
from fastapi import APIRouter

from deps import db
from device_adapters import simulation_fields

router = APIRouter(prefix="/devices", tags=["devices"])

# One table: capability -> the spoken action it enables. Unknown capabilities
# are ignored rather than guessed at.
CAPABILITY_ACTIONS = {
    "power": "turn it on or off",
    "brightness": "change its brightness",
    "color": "change its color",
    "color_temp": "make it warm or cool white",
    "temperature": "set its temperature",
    "hvac_mode": "change its mode (cool, heat, fan)",
    "fan_speed": "change the fan speed",
    "volume": "change the volume",
    "volume_step": "turn the volume up or down",
    "mute": "mute or unmute it",
    "channel": "change the channel",
    "input": "change the input",
    "position": "open it, close it, or set how far open",
}

# Device families Aria's tools can operate when a room has one connected
# (realtime_device_tools.py). Order = how she lists them.
CONTROL_FUNCTIONS = {
    "light": "lights",
    "ac": "air conditioning",
    "thermostat": "thermostat",
    "tv": "TV",
    "blinds": "motorized blinds",
}

# How much a transport can prove about the device's real state.
_ONE_WAY = {"ir_blaster", "ir", "rf_433", "rf_915"}
_BRIDGE = {"bluetooth", "wifi", "zigbee", "matter"}


def state_feedback(device: dict) -> str:
    """'reported' | 'one_way' | 'bridge_ack' | 'simulated'."""
    protocol = device.get("protocol")
    if simulation_fields(device):
        return "simulated"
    if protocol in _ONE_WAY:
        return "one_way"
    if protocol in _BRIDGE:
        return "bridge_ack"
    return "reported"


_FEEDBACK_WORDS = {
    "reported": "it reports its own state, so I can check it",
    "one_way": "it's one-way infrared/radio, so I can send commands but can't confirm what it actually did",
    "bridge_ack": "commands go through the room bridge, so I can confirm only once the bridge reports back",
    "simulated": "it's a simulated test device, not physical hardware",
}


def _name(device: dict) -> str:
    label = device.get("label") or device.get("kind") or "device"
    room = device.get("room")
    return label.replace(f"Room {room} ", "") if room else label


def _reported_state(device: dict, feedback: str) -> dict:
    """Only state the transport can stand behind: a real read-back, or the
    simulator's own state for a simulated device (labelled simulated). A
    one-way or bridge-queued device's stored state is the last command sent,
    never an observation."""
    if feedback not in ("reported", "simulated"):
        return {}
    return dict(device.get("state") or {})


def describe_device(device: dict) -> dict:
    caps = [c for c in (device.get("capabilities") or []) if c in CAPABILITY_ACTIONS]
    feedback = state_feedback(device)
    return {
        "device_id": device.get("device_id"),
        "name": _name(device),
        "kind": device.get("kind"),
        "protocol": device.get("protocol"),
        "capabilities": caps,
        "actions": [CAPABILITY_ACTIONS[c] for c in caps],
        "inputs": device.get("inputs") or [],
        "state_feedback": feedback,
        "state_feedback_note": _FEEDBACK_WORDS[feedback],
        "reported_state": _reported_state(device, feedback),
    }


def _join(words: list) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def build_room_inventory(room: str, devices: list) -> dict:
    """Pure: the inventory for one room from its registry rows."""
    connected = [describe_device(d) for d in devices if d.get("online", True)]
    offline = [_name(d) for d in devices if not d.get("online", True)]
    kinds_here = {d["kind"] for d in connected}
    not_connected = [CONTROL_FUNCTIONS[k] for k in CONTROL_FUNCTIONS
                     if k not in kinds_here and not (k in ("ac", "thermostat") and kinds_here & {"ac", "thermostat"})]
    if not connected:
        summary = "No controllable devices are connected in this room."
    else:
        lines = [f"the {d['name']}: I can {_join(d['actions'])} ({d['state_feedback_note']})" if d["actions"]
                 else f"the {d['name']} ({d['state_feedback_note']})" for d in connected]
        summary = "Connected in this room: " + "; ".join(lines) + "."
    if not_connected:
        summary += f" Not connected in this room: {_join(not_connected)}."
    if offline:
        summary += f" Registered but offline: {_join(offline)}."
    return {
        "ok": True, "room": room, "source": "device_registry",
        "supported_functions": list(CONTROL_FUNCTIONS.values()),
        "connected": connected, "not_connected": not_connected, "offline": offline,
        "summary": summary,
    }


@router.get("/public/room/{room}/inventory")
async def public_room_inventory(room: str):
    """Kiosk/Aria (no login): the same room scope as /public/by-room/{room}."""
    devices = await db.smart_devices.find({"room": room}, {"_id": 0}).sort("label", 1).to_list(50)
    return build_room_inventory(room, devices)
