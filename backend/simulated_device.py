"""Simulated device state - what the `mock` adapter (device_adapters.py)
does instead of reaching physical hardware.

It speaks the exact same logical contract as a real device (action/value
against the device's own declared capabilities) and holds the resulting
state as the simulator's truth. That makes the demo kiosk and every mock
room behave like a real room would, including refusing what the device
can't do: an unsupported action or an out-of-range value raises, so the
command fails and Aria cannot claim it worked.

Pure function - no database, no network. devices.py persists the returned
state. The mock adapter (device_adapters.execute_mock) records the command
as simulated everywhere, and as verified against the simulator only in the
demo-only room: a mock device in a real resident room is scaffolding, never
proof that anything physical happened (SC-11).
"""


class SimulatedDeviceError(ValueError):
    """The simulated device rejected the command (unsupported or invalid)."""


def _int_in(value, lo: int, hi: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulatedDeviceError(f"{what} must be a number")
    if not lo <= value <= hi:
        raise SimulatedDeviceError(f"{what} must be between {lo} and {hi}")
    return round(value)


def _power(value, _device):
    if value not in ("on", "off"):
        raise SimulatedDeviceError("power must be 'on' or 'off'")
    return value


def _input(value, device):
    inputs = device.get("inputs") or []
    match = next((i for i in inputs if i.lower() == str(value).lower()), None)
    if not match:
        raise SimulatedDeviceError(f"this device has no '{value}' input")
    return match


def _color(value, _device):
    if not (isinstance(value, (list, tuple)) and len(value) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in value)):
        raise SimulatedDeviceError("color must be three 0-255 values")
    return list(value)


# action -> validator returning the value to store. Ranges follow the room
# contract the tools already use (thermostat 60-85 F, percentages 0/1-100).
_ACTIONS = {
    "power": _power,
    "brightness": lambda v, d: _int_in(v, 1, 100, "brightness"),
    "temperature": lambda v, d: _int_in(v, 60, 85, "temperature"),
    "volume": lambda v, d: _int_in(v, 0, 100, "volume"),
    "channel": lambda v, d: _int_in(v, 1, 999, "channel"),
    "position": lambda v, d: _int_in(v, 0, 100, "position"),
    "fan_speed": lambda v, d: _int_in(v, 0, 5, "fan speed"),
    "color_temp": lambda v, d: _int_in(v, 2000, 7000, "color temperature"),
    "color": _color,
    "input": _input,
}


def apply_simulated_command(device: dict, action: str, value) -> dict:
    """Return the device's full state after `action`=`value`, or raise
    SimulatedDeviceError. Never mutates `device`."""
    if device.get("online") is False:
        raise SimulatedDeviceError("device is offline")
    if action not in (device.get("capabilities") or []):
        raise SimulatedDeviceError(f"this {device.get('kind', 'device')} does not support {action}")
    validate = _ACTIONS.get(action)
    if validate is None:
        raise SimulatedDeviceError(f"{action} is not simulated")
    return {**(device.get("state") or {}), action: validate(value, device)}
