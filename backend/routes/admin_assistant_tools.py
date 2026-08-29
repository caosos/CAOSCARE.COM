"""Tool schemas (OpenAI function-calling definitions) for the Admin
configuration assistant - Aria's THIRD, distinct persona/tool catalog,
separate from the resident-facing companion (realtime_tools*.py) and from
Michael's personal operator build (routes/realtime.py's
_build_aria_instructions). This one runs over plain text chat, server-side
(see admin_assistant_executor.py - tools call domain route handlers
directly, in-process, never MongoDB directly), gated on owner/admin auth.

Every tool name here maps to a real, pre-existing domain capability
(residents.py, kiosks.py, devices.py, facilities.py, device_adapters.py) -
this file adds zero new domain concepts, only a catalog the model can call.
See admin_assistant_ui_tools.py for the separate, read-only semantic
UI-navigation/highlight tool catalog.
"""
from routes.admin_assistant_ui_tools import build_ui_action_tools


def build_admin_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_setup_status",
                "description": (
                    "Get a real, current snapshot of the whole facility's setup: "
                    "how many facilities/residents/rooms/devices exist, which "
                    "rooms have no resident or no devices yet, and whether Home "
                    "Assistant is reachable. Use this FIRST when the admin asks "
                    "something like 'what's going on' or 'what do I need to do' "
                    "or 'is everything set up' - answer from what this returns, "
                    "never guess."
                ),
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_facilities",
                "description": "List all facility records on file.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_residents",
                "description": "List every resident on file with their room, preferred name, and participation level.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_resident",
                "description": "Look up one resident by resident_id, or by name/room if the id isn't known yet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resident_id": {"type": "string"},
                        "name": {"type": "string", "description": "Full or partial name, case-insensitive."},
                        "room": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_resident",
                "description": (
                    "Create a new resident record. Room should be a real room "
                    "(check list_rooms/create_room first if unsure it exists). "
                    "pendant_id is auto-generated if omitted - only ask the "
                    "admin for one if they specifically mention a physical "
                    "pendant with a real code."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "room": {"type": "string"},
                        "preferred_name": {"type": "string"},
                        "pendant_id": {"type": "string"},
                        "participation_level": {
                            "type": "string",
                            "enum": ["full", "pendant_enhanced", "wearable_enhanced", "family_connected"],
                        },
                        "preferences": {"type": "string"},
                    },
                    "required": ["name", "room"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_resident",
                "description": "Update one or more fields on an existing resident (partial update - only send fields that are changing).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resident_id": {"type": "string"},
                        "name": {"type": "string"},
                        "room": {"type": "string"},
                        "preferred_name": {"type": "string"},
                        "participation_level": {"type": "string"},
                        "preferences": {"type": "string"},
                    },
                    "required": ["resident_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "assign_resident_to_room",
                "description": "Move/assign a resident to a room. The room should already exist (create_room first if it doesn't).",
                "parameters": {
                    "type": "object",
                    "properties": {"resident_id": {"type": "string"}, "room": {"type": "string"}},
                    "required": ["resident_id", "room"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_rooms",
                "description": "List every registered room (kiosk), with its assigned resident (if any) and how many devices it has.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_room",
                "description": "Register a brand-new room (creates its kiosk record) so residents/devices can be assigned to it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room": {"type": "string"},
                        "zone": {"type": "string", "description": "Optional area/wing label."},
                    },
                    "required": ["room"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_devices",
                "description": "List registered room devices, optionally filtered to one room or one resident. Shows kind, protocol, capabilities, and current state.",
                "parameters": {
                    "type": "object",
                    "properties": {"room": {"type": "string"}, "resident_id": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_device",
                "description": "Read one device's full current state and capabilities by device_id. ALWAYS call this after send_device_command to verify the real resulting state before telling the admin it worked.",
                "parameters": {
                    "type": "object",
                    "properties": {"device_id": {"type": "string"}},
                    "required": ["device_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_device",
                "description": (
                    "Register a new device in a room. Use protocol='mock' unless "
                    "the admin specifically has real Home Assistant/other "
                    "hardware to point it at (protocol='home_assistant' requires "
                    "a real HA entity_id as `endpoint`). Declare only the "
                    "capabilities this specific device actually has."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": ["light", "fan", "heater", "ac", "thermostat", "tv", "speaker", "blinds", "outlet", "humidifier", "bed", "door_lock", "generic"],
                        },
                        "protocol": {
                            "type": "string",
                            "enum": ["mock", "home_assistant", "bluetooth", "wifi", "rf_433", "rf_915", "ir", "zigbee", "matter"],
                        },
                        "room": {"type": "string"},
                        "resident_id": {"type": "string"},
                        "capabilities": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["power", "brightness", "temperature", "fan_speed", "volume", "channel", "input", "color", "position"]},
                        },
                        "inputs": {"type": "array", "items": {"type": "string"}, "description": "Only for a device with the 'input' capability - its real valid input names."},
                        "endpoint": {"type": "string", "description": "MAC/IP/RF code, or a Home Assistant entity_id when protocol='home_assistant'."},
                    },
                    "required": ["label", "kind", "protocol", "room", "capabilities"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_device",
                "description": "Change an existing device's room/resident assignment, capabilities, inputs, or endpoint (partial update).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "label": {"type": "string"},
                        "room": {"type": "string"},
                        "resident_id": {"type": "string"},
                        "capabilities": {"type": "array", "items": {"type": "string"}},
                        "inputs": {"type": "array", "items": {"type": "string"}},
                        "endpoint": {"type": "string"},
                        "protocol": {"type": "string"},
                    },
                    "required": ["device_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_device_command",
                "description": (
                    "Execute one real command against a device through the "
                    "actual device adapter/bridge boundary - the SAME path the "
                    "resident-facing voice tools use. Use this to test a newly "
                    "configured device. The result tells you whether it was "
                    "verified executed, merely sent (real hardware awaiting a "
                    "bridge ack), or failed - report that distinction honestly, "
                    "then call get_device to confirm the resulting state."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["power", "brightness", "temperature", "fan_speed", "volume", "channel", "input", "color", "position"]},
                        "value": {},
                    },
                    "required": ["device_id", "action", "value"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_home_assistant_status",
                "description": "Check real, live connectivity to the configured Home Assistant instance - never assume it's connected without calling this.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
    ] + build_ui_action_tools()
