"""send_device_command's executor - split out of admin_assistant_executor.py
(same 300-line discipline) because of how much telemetry a device command
carries on its own (requested capability/action, adapter/transport used,
command-sent result, post-command read-back, verified/unverified/failed,
latency, error - the DEVICE TELEMETRY requirement, 2026-08-27). Calls the
same devices.send_command() every other Aria surface uses - no parallel
execution path.
"""
import time
from fastapi import HTTPException

from deps import db
from models import DeviceCommandInput
from routes.receipts import create_receipt
from routes.events import log_event
from routes import devices as devices_routes


def _ok(status: str, **data) -> dict:
    return {"status": status, **data}


def _err(detail: str) -> dict:
    return {"status": "failed", "detail": detail}


async def send_device_command(admin_user: dict, args: dict) -> dict:
    device_id = args["device_id"]
    conversation_id, request_id = args.get("_conversation_id"), args.get("_request_id")
    dev = await db.smart_devices.find_one({"device_id": device_id}, {"_id": 0, "room": 1, "resident_id": 1, "protocol": 1})
    room = (dev or {}).get("room")
    resident_id = (dev or {}).get("resident_id")
    protocol = (dev or {}).get("protocol")
    cmd = DeviceCommandInput(action=args["action"], value=args["value"])
    started = time.monotonic()
    log_ctx = dict(source="admin_aria", actor_id=admin_user["user_id"], conversation_id=conversation_id,
                   request_id=request_id, resident_id=resident_id, room=room, target_type="device",
                   target_id=device_id, action=args["action"])

    try:
        result = await devices_routes.send_command(device_id, cmd, user=admin_user)
    except HTTPException as e:
        duration_ms = (time.monotonic() - started) * 1000
        receipt = await create_receipt(
            action_type="admin_assistant_device_command", related_object_type="device",
            related_object_id=device_id, source="aria_admin", requested_by=admin_user["user_id"],
            resident_id=resident_id, room=room, status="failed",
        )
        await log_event(event_type="device.command", status="failed", duration_ms=duration_ms,
                         error_message=str(e.detail), verification_status="failed", receipt_id=receipt["receipt_id"],
                         metadata={"protocol": protocol, "requested_value": args["value"]}, **log_ctx)
        return _err(f"{e.status_code}: {e.detail}")

    duration_ms = (time.monotonic() - started) * 1000
    verified = result.get("status") == "executed"
    receipt = await create_receipt(
        action_type="admin_assistant_device_command", related_object_type="device",
        related_object_id=device_id, source="aria_admin", requested_by=admin_user["user_id"],
        resident_id=resident_id, room=room, status="completed" if verified else "created",
    )
    await log_event(event_type="device.command", status=result.get("status"), duration_ms=duration_ms,
                     verification_status="verified" if verified else "unverified", receipt_id=receipt["receipt_id"],
                     metadata={"protocol": protocol, "requested_value": args["value"], "read_back_state": result.get("state")}, **log_ctx)
    return _ok("command_verified" if verified else "command_sent", command=result)
