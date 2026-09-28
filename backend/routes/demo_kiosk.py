"""Demo kiosk: DEMO RESET for the public demo room.

The demo room is whichever kiosk an admin designated `public_demo`
(routes/kiosks.py). Its devices are ordinary SmartDevice records with
protocol "mock", so Aria and the kiosk control them through the normal
room-command path (/devices/public/room/{room}/command) and the simulated
adapter (simulated_device.py). Nothing here executes commands.

Reset restores a known baseline: one light, thermostat, TV and blinds in
the demo room (created if missing), baseline state, and open demo requests
closed with a history entry. It refuses when the room holds any
non-simulated device, so it can never touch a real room or real hardware.
"""
from fastapi import APIRouter, HTTPException

from deps import db
from models import SmartDevice, now_utc
from routes.receipts import create_receipt
from routes.task_history import task_event, update_task_with_history

router = APIRouter(prefix="/demo", tags=["demo"])

# One device per kind. Labels get the "Room <room> " prefix Aria's tools
# strip when naming a device.
DEMO_BASELINE = [
    {"kind": "light", "name": "light", "capabilities": ["power", "brightness"],
     "state": {"power": "off", "brightness": 80}},
    {"kind": "thermostat", "name": "thermostat", "capabilities": ["power", "temperature"],
     "state": {"power": "on", "temperature": 72}},
    {"kind": "tv", "name": "TV", "capabilities": ["power", "volume", "channel", "input"],
     "inputs": ["TV", "HDMI 1"], "state": {"power": "off", "volume": 20, "channel": 3, "input": "TV"}},
    {"kind": "blinds", "name": "blinds", "capabilities": ["position"], "state": {"position": 0}},
]
OPEN_TASK_STATUSES = ["pending", "in_progress"]


async def _demo_kiosk() -> dict:
    kiosk = await db.kiosks.find_one({"public_demo": True}, {"_id": 0})
    if not kiosk or not kiosk.get("room"):
        raise HTTPException(status_code=404, detail="No public demo kiosk is configured.")
    return kiosk


@router.post("/reset")
async def demo_reset():
    kiosk = await _demo_kiosk()
    room = kiosk["room"]
    devices = await db.smart_devices.find({"room": room}, {"_id": 0}).to_list(100)
    real = [d["device_id"] for d in devices if d.get("protocol") != "mock"]
    if real:
        raise HTTPException(
            status_code=409,
            detail=f"Demo reset refused: room {room} has non-simulated devices ({', '.join(real)}).",
        )
    resident = await db.residents.find_one({"room": room}, {"_id": 0, "resident_id": 1})
    resident_id = (resident or {}).get("resident_id")
    now = now_utc().isoformat()

    result = []
    for base in DEMO_BASELINE:
        fields = {
            "capabilities": base["capabilities"], "inputs": base.get("inputs", []),
            "state": dict(base["state"]), "online": True, "last_command_at": now,
        }
        existing = next((d for d in devices if d.get("kind") == base["kind"]), None)
        if existing:
            await db.smart_devices.update_one({"device_id": existing["device_id"]}, {"$set": fields})
            device_id = existing["device_id"]
        else:
            dev = SmartDevice(label=f"Room {room} {base['name']}", kind=base["kind"], protocol="mock",
                              room=room, resident_id=resident_id, **{k: v for k, v in fields.items()
                                                                     if k != "last_command_at"})
            doc = dev.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            doc["last_command_at"] = now
            await db.smart_devices.insert_one(doc)
            device_id = doc["device_id"]
        result.append({"device_id": device_id, "kind": base["kind"], "state": base["state"]})

    closed = 0
    async for task in db.staff_tasks.find({"room": room, "status": {"$in": OPEN_TASK_STATUSES}}, {"_id": 0}):
        await update_task_with_history(
            task["task_id"],
            {"status": "skipped", "completed_at": now, "notes": "Closed by demo reset"},
            [task_event("status", frm=task["status"], to="skipped", text="Demo reset",
                        by="demo_reset", by_name="Demo reset")],
        )
        closed += 1

    receipt = await create_receipt(
        action_type="demo_reset", related_object_type="kiosk", related_object_id=kiosk["kiosk_id"],
        source="system", resident_id=resident_id, room=room,
    )
    return {"room": room, "kiosk_id": kiosk["kiosk_id"], "devices": result,
            "requests_closed": closed, "receipt_id": receipt["receipt_id"]}
