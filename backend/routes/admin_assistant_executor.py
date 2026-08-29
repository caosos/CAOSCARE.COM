"""Executes one admin-assistant tool call by calling the REAL domain route
handlers directly (in-process, not a self-HTTP round trip, not a MongoDB
write) - the same functions the normal Admin UI's own HTTP requests hit.
A gap here is a gap to report, never a reason to write to `db` directly.
Every mutation is receipted via create_receipt() (source="aria_admin") for
audit and, for device commands, logged to routes.events for telemetry.
"""
from fastapi import HTTPException

from models import ResidentCreate, KioskCreate, SmartDeviceCreate
from deps import db
from device_adapters import ha_health
from routes.receipts import create_receipt
from routes import residents as residents_routes
from routes import kiosks as kiosks_routes
from routes import devices as devices_routes
from routes import facilities as facilities_routes
from routes.admin_assistant_ui_executor import UI_TOOL_FUNCTIONS
from routes.admin_assistant_device_executor import send_device_command
from routes.admin_assistant_util import normalize_room


def _ok(status: str, **data) -> dict:
    return {"status": status, **data}


def _err(detail: str) -> dict:
    return {"status": "failed", "detail": detail}


async def _call(fn, *args, **kwargs) -> dict:
    """Normalizes a domain handler's HTTPExceptions into a tool-shaped failure instead of an unhandled crash."""
    try:
        result = await fn(*args, **kwargs)
        return {"status": "ok", "result": result}
    except HTTPException as e:
        return _err(f"{e.status_code}: {e.detail}")


async def get_setup_status(admin_user: dict, args: dict) -> dict:
    facilities = await db.facilities.find({}, {"_id": 0}).to_list(50)
    residents = await residents_routes.list_residents(user=admin_user)
    kiosks = await kiosks_routes.list_kiosks()
    devices = await devices_routes.list_devices(user=admin_user)
    ha = await ha_health()

    rooms_with_devices = {d["room"] for d in devices if d.get("room")}
    rooms_with_residents = {r["room"] for r in residents if r.get("room")}
    all_rooms = {k["room"] for k in kiosks}
    gaps = []
    for room in sorted(all_rooms):
        if room not in rooms_with_residents:
            gaps.append(f"Room {room} has no resident assigned")
        if room not in rooms_with_devices:
            gaps.append(f"Room {room} has no devices registered")
    for r in residents:
        if r.get("room") not in all_rooms:
            gaps.append(f"{r['name']} is assigned to room {r.get('room')!r}, which has no kiosk/room record")

    active = next((f["name"] for f in facilities if f.get("is_active")), None)
    return _ok("discovered", facility_count=len(facilities), active_facility=active,
                resident_count=len(residents), room_count=len(all_rooms),
                device_count=len(devices), home_assistant=ha, gaps=gaps)


async def list_facilities(admin_user: dict, args: dict) -> dict:
    return await _call(facilities_routes.list_facilities, user=admin_user)


async def list_residents(admin_user: dict, args: dict) -> dict:
    return await _call(residents_routes.list_residents, user=admin_user)


async def get_resident(admin_user: dict, args: dict) -> dict:
    if args.get("resident_id"):
        return await _call(residents_routes.get_resident, args["resident_id"], user=admin_user)
    all_r = await db.residents.find({}, {"_id": 0}).to_list(1000)
    name = (args.get("name") or "").strip().lower()
    room = (args.get("room") or "").strip()
    matches = [
        r for r in all_r
        if (not name or name in r.get("name", "").lower() or name in (r.get("preferred_name") or "").lower())
        and (not room or r.get("room") == room)
    ]
    if not matches:
        return _err("No resident matches that name/room.")
    return _ok("discovered", residents=matches)


async def create_resident(admin_user: dict, args: dict) -> dict:
    room = args["room"]
    pendant_id = args.get("pendant_id") or f"pendant_{room}_{admin_user['user_id'][-6:]}"
    payload = ResidentCreate(
        name=args["name"], room=room, pendant_id=pendant_id,
        preferred_name=args.get("preferred_name") or "",
        participation_level=args.get("participation_level") or "pendant_enhanced",
        preferences=args.get("preferences") or "",
    )
    out = await _call(residents_routes.create_resident, payload, user=admin_user)
    if out["status"] == "ok":
        await create_receipt(
            action_type="admin_assistant_resident_created", related_object_type="resident",
            related_object_id=out["result"]["resident_id"], source="aria_admin",
            resident_id=out["result"]["resident_id"], room=room, requested_by=admin_user["user_id"],
        )
        out["status"] = "configured"
    return out


async def update_resident(admin_user: dict, args: dict) -> dict:
    resident_id = args["resident_id"]
    existing = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not existing:
        return _err(f"No resident with id {resident_id}")
    merged = {**existing, **{k: v for k, v in args.items() if k != "resident_id" and v is not None}}
    payload = ResidentCreate(**{k: merged.get(k) for k in ResidentCreate.model_fields})
    out = await _call(residents_routes.update_resident, resident_id, payload, user=admin_user)
    if out["status"] == "ok":
        await create_receipt(
            action_type="admin_assistant_resident_updated", related_object_type="resident",
            related_object_id=resident_id, source="aria_admin",
            resident_id=resident_id, room=out["result"].get("room"), requested_by=admin_user["user_id"],
        )
        out["status"] = "configured"
    return out


async def assign_resident_to_room(admin_user: dict, args: dict) -> dict:
    return await update_resident(admin_user, {"resident_id": args["resident_id"], "room": args["room"]})


async def list_rooms(admin_user: dict, args: dict) -> dict:
    kiosks = await kiosks_routes.list_kiosks()
    residents = await residents_routes.list_residents(user=admin_user)
    devices = await devices_routes.list_devices(user=admin_user)
    rooms = []
    for k in kiosks:
        room = k["room"]
        resident = next((r for r in residents if r.get("room") == room), None)
        room_devices = [d for d in devices if d.get("room") == room]
        rooms.append({
            "room": room, "zone": k.get("zone"), "kiosk_id": k["kiosk_id"],
            "resident_name": resident["name"] if resident else None,
            "resident_id": resident["resident_id"] if resident else None,
            "device_count": len(room_devices),
            "device_kinds": [d["kind"] for d in room_devices],
        })
    return _ok("discovered", rooms=rooms)


async def create_room(admin_user: dict, args: dict) -> dict:
    existing = await db.kiosks.find_one({"room": args["room"]}, {"_id": 0})
    if existing:
        return _ok("discovered", note="Room already exists", kiosk=existing)
    payload = KioskCreate(name=args["room"], room=args["room"], zone=args.get("zone") or "")
    out = await _call(kiosks_routes.create_kiosk, payload, user=admin_user)
    if out["status"] == "ok":
        await create_receipt(
            action_type="admin_assistant_room_created", related_object_type="kiosk",
            related_object_id=out["result"]["kiosk_id"], source="aria_admin",
            room=args["room"], requested_by=admin_user["user_id"],
        )
        out["status"] = "configured"
    return out


async def list_devices(admin_user: dict, args: dict) -> dict:
    devices = await devices_routes.list_devices(user=admin_user)
    if args.get("room"):
        devices = [d for d in devices if d.get("room") == args["room"]]
    if args.get("resident_id"):
        devices = [d for d in devices if d.get("resident_id") == args["resident_id"]]
    return _ok("discovered", devices=devices)


async def get_device(admin_user: dict, args: dict) -> dict:
    devices = await devices_routes.list_devices(user=admin_user)
    dev = next((d for d in devices if d["device_id"] == args["device_id"]), None)
    if not dev:
        return _err(f"No device with id {args['device_id']}")
    return _ok("discovered", device=dev)


async def create_device(admin_user: dict, args: dict) -> dict:
    payload = SmartDeviceCreate(
        label=args["label"], kind=args["kind"], protocol=args["protocol"], room=args["room"],
        resident_id=args.get("resident_id"), capabilities=args.get("capabilities") or [],
        inputs=args.get("inputs") or [], endpoint=args.get("endpoint"),
    )
    out = await _call(devices_routes.create_device, payload, user=admin_user)
    if out["status"] == "ok":
        await create_receipt(
            action_type="admin_assistant_device_created", related_object_type="device",
            related_object_id=out["result"]["device_id"], source="aria_admin",
            resident_id=args.get("resident_id"), room=args["room"], requested_by=admin_user["user_id"],
        )
        out["status"] = "configured" if payload.protocol in ("mock", "home_assistant") else "configured_unverified"
    return out


async def update_device(admin_user: dict, args: dict) -> dict:
    device_id = args["device_id"]
    devices = await devices_routes.list_devices(user=admin_user)
    existing = next((d for d in devices if d["device_id"] == device_id), None)
    if not existing:
        return _err(f"No device with id {device_id}")
    merged = {**existing, **{k: v for k, v in args.items() if k != "device_id" and v is not None}}
    payload = SmartDeviceCreate(**{k: merged.get(k) for k in SmartDeviceCreate.model_fields})
    out = await _call(devices_routes.update_device, device_id, payload, user=admin_user)
    if out["status"] == "ok":
        await create_receipt(
            action_type="admin_assistant_device_updated", related_object_type="device",
            related_object_id=device_id, source="aria_admin",
            resident_id=payload.resident_id, room=payload.room, requested_by=admin_user["user_id"],
        )
        out["status"] = "configured"
    return out


async def get_home_assistant_status(admin_user: dict, args: dict) -> dict:
    return await ha_health()


TOOL_FUNCTIONS = {
    "get_setup_status": get_setup_status,
    "list_facilities": list_facilities,
    "list_residents": list_residents,
    "get_resident": get_resident,
    "create_resident": create_resident,
    "update_resident": update_resident,
    "assign_resident_to_room": assign_resident_to_room,
    "list_rooms": list_rooms,
    "create_room": create_room,
    "list_devices": list_devices,
    "get_device": get_device,
    "create_device": create_device,
    "update_device": update_device,
    "send_device_command": send_device_command,
    "get_home_assistant_status": get_home_assistant_status,
    **UI_TOOL_FUNCTIONS,
}


async def execute_admin_tool(name: str, args: dict, admin_user: dict, conversation_id: str = None, request_id: str = None) -> dict:
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return _err(f"Unknown tool: {name}")
    if args.get("room"):
        # Applied once, for every tool, rather than in each function body -
        # the model occasionally passes a human label like "Room 214"
        # instead of the bare "214" actually stored on the record (a real,
        # confirmed live bug: a real query silently matched nothing).
        args = {**args, "room": normalize_room(args["room"])}
    # Threaded through as reserved keys (not real tool arguments) purely so
    # send_device_command's own dedicated device.command telemetry event
    # can be joined back to the conversation/turn that caused it - every
    # other event already gets this from admin_assistant.py's log_kwargs.
    args = {**args, "_conversation_id": conversation_id, "_request_id": request_id}
    try:
        return await fn(admin_user, args)
    except Exception as e:
        return _err(f"Tool {name} raised an unexpected error: {e}")
