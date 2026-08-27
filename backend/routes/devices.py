"""Smart-room device control — CRUD + command dispatch.

Two execution paths, chosen by the device's own `protocol` (see
device_adapters.py for the first, this file's docstring for the second):

1. Adapters (mock, home_assistant): the backend executes the command
   itself, synchronously, in this request - no bridge tablet involved.
2. Physical-transport protocols (bluetooth, wifi, rf_915 via RFM69 TX on
   the Android bridge, rf_433, ir, zigbee, matter): the backend does NOT
   talk to the hardware directly - commands are persisted and fetched by
   the room's bridge tablet app, which executes them locally (BLE GATT /
   HTTP GET / RF transmit) and reports back via /queue/{id}/ack. This
   keeps the cloud side protocol-agnostic and lets any Android tablet act
   as the per-room execution hub.

Either way, Aria's tools and the resident UI only ever see the same
action/value/state contract - which path ran is invisible above this file.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from models import SmartDevice, SmartDeviceCreate, DeviceCommandInput, now_utc
from deps import db, get_current_user
from device_adapters import has_adapter, execute as execute_adapter

router = APIRouter(prefix="/devices", tags=["devices"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "last_command_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_devices(user=Depends(get_current_user)):
    items = await db.smart_devices.find({}, {"_id": 0}).sort("label", 1).to_list(500)
    for d in items:
        _iso(d)
        if d.get("resident_id"):
            r = await db.residents.find_one({"resident_id": d["resident_id"]}, {"_id": 0, "name": 1})
            if r:
                d["resident_name"] = r["name"]
    return items


@router.post("")
async def create_device(data: SmartDeviceCreate, user=Depends(get_current_user)):
    dev = SmartDevice(**data.model_dump())
    doc = dev.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["last_command_at"] = None
    await db.smart_devices.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{device_id}")
async def update_device(device_id: str, data: SmartDeviceCreate, user=Depends(get_current_user)):
    r = await db.smart_devices.update_one({"device_id": device_id}, {"$set": data.model_dump()})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    doc = await db.smart_devices.find_one({"device_id": device_id}, {"_id": 0})
    return _iso(doc)


@router.delete("/{device_id}")
async def delete_device(device_id: str, user=Depends(get_current_user)):
    r = await db.smart_devices.delete_one({"device_id": device_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}


async def _dispatch_command(dev: dict, cmd: DeviceCommandInput, issued_by: str) -> dict:
    """Persist + apply one command against an already-loaded device doc.

    Protocols with a real adapter (device_adapters.py - currently "mock"
    and "home_assistant"): execute synchronously through that adapter right
    now, in this request - Aria gets a real, truthful ack (or a real
    failure) in the same turn, never a command left "queued" forever.

    Every other protocol (real physical-transport hardware: bluetooth,
    wifi, ir, zigbee, matter, rf_433, rf_915): unchanged behavior - queue
    the command for the room's bridge tablet and optimistically set state,
    leaving truth of actual execution to the bridge's later /queue/{id}/ack.
    """
    protocol = dev.get("protocol")
    command = {
        "command_id": f"cmd_{datetime.now(timezone.utc).timestamp()}",
        "device_id": dev["device_id"],
        "action": cmd.action,
        "value": cmd.value,
        "issued_by": issued_by,
        "issued_at": now_utc().isoformat(),
        "protocol": protocol,
        "endpoint": dev.get("endpoint"),
    }
    new_state = dev.get("state") or {}
    if has_adapter(protocol):
        try:
            result = await execute_adapter(dev, cmd.action, cmd.value)
            command["status"] = "executed"
            command["acked_at"] = command["issued_at"]
            command["ack_detail"] = result.get("detail", "")
            new_state = {**new_state, cmd.action: cmd.value}
        except Exception as e:
            command["status"] = "failed"
            command["acked_at"] = command["issued_at"]
            command["ack_detail"] = str(e)
            await db.device_commands.insert_one(command)
            command.pop("_id", None)
            command["state"] = new_state
            raise HTTPException(status_code=502, detail=f"Device command failed: {e}") from e
    else:
        command["status"] = "queued"
        new_state = {**new_state, cmd.action: cmd.value}

    await db.device_commands.insert_one(command)
    command.pop("_id", None)
    await db.smart_devices.update_one(
        {"device_id": dev["device_id"]},
        {"$set": {"state": new_state, "last_command_at": now_utc().isoformat()}},
    )
    command["state"] = new_state
    return command


@router.post("/{device_id}/command")
async def send_command(device_id: str, cmd: DeviceCommandInput, user=Depends(get_current_user)):
    dev = await db.smart_devices.find_one({"device_id": device_id}, {"_id": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    if cmd.action not in (dev.get("capabilities") or []):
        raise HTTPException(status_code=400, detail=f"Device does not support {cmd.action}")
    return await _dispatch_command(dev, cmd, user.get("name"))


@router.get("/public/by-room/{room}")
async def public_list_room_devices(room: str):
    """Kiosk (no login) needs to know which buttons to show."""
    items = await db.smart_devices.find({"room": room}, {"_id": 0}).sort("label", 1).to_list(50)
    for d in items:
        _iso(d)
    return items


@router.post("/public/room/{room}/command")
async def public_room_command(room: str, request: Request, cmd: DeviceCommandInput):
    """Kiosk path: big-button presses on the resident tablet. No auth — limited to devices
    assigned to that room. HMAC optional."""
    from routes.device_auth import verify_device_token
    await verify_device_token(request, "locations.ingest")  # reuse the locations scope

    devices = await db.smart_devices.find({"room": room}, {"_id": 0}).to_list(50)
    if not devices:
        raise HTTPException(status_code=404, detail=f"No devices in room {room}")

    # Pick the matching device by capability, disambiguated by kind when
    # given (a room commonly has >1 device sharing a capability, e.g. both
    # thermostat and TV expose "power" - matching on capability alone would
    # pick whichever device happens to sort first, silently acting on the
    # wrong one).
    candidates = [d for d in devices if cmd.action in (d.get("capabilities") or [])]
    if cmd.kind:
        target = next((d for d in candidates if d.get("kind") == cmd.kind), None)
    else:
        target = candidates[0] if len(candidates) == 1 else None
    if not target:
        detail = (
            f"No {cmd.kind} device in room {room} supports {cmd.action}" if cmd.kind
            else f"{'No' if not candidates else 'More than one'} device in room {room} supports {cmd.action} - pass `kind` to disambiguate"
        )
        raise HTTPException(status_code=400, detail=detail)
    return await _dispatch_command(target, cmd, f"kiosk:room:{room}")


@router.get("/queue/{room}")
async def pull_queue(room: str, request: Request):
    """Bridge tablet calls this to fetch pending commands for devices in its room.
    Marks them 'delivered' atomically. HMAC optional."""
    from routes.device_auth import verify_device_token
    await verify_device_token(request, "locations.ingest")

    devices = await db.smart_devices.find({"room": room}, {"_id": 0, "device_id": 1}).to_list(50)
    dev_ids = [d["device_id"] for d in devices]
    pending = await db.device_commands.find(
        {"device_id": {"$in": dev_ids}, "status": "queued"},
        {"_id": 0},
    ).to_list(100)
    for p in pending:
        await db.device_commands.update_one(
            {"command_id": p["command_id"]},
            {"$set": {"status": "delivered", "delivered_at": now_utc().isoformat()}},
        )
    return pending


@router.post("/queue/{command_id}/ack")
async def ack_command(command_id: str, request: Request):
    """Bridge reports that a command succeeded or failed on the physical device."""
    from routes.device_auth import verify_device_token
    await verify_device_token(request, "locations.ingest")

    body = await request.json()
    status = body.get("status", "executed")  # executed | failed
    detail = body.get("detail", "")
    r = await db.device_commands.update_one(
        {"command_id": command_id},
        {"$set": {"status": status, "acked_at": now_utc().isoformat(), "ack_detail": detail}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Command not found")
    return {"ok": True}
