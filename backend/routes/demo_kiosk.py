"""Demo kiosk: the demo-only room and DEMO RESET.

The public demo kiosk lives in its own demo-only room, DEMO_ROOM, with a
synthetic resident (DEMO_RESIDENT_NAME, "Demo - " like every demo record).
`ensure_demo_room()` creates that resident and kiosk as ordinary Resident
and Kiosk records and makes the kiosk the `public_demo` one (Michael,
2026-10-03: "Use a demo-only room for the demo kiosk"). Requests made there
go through the normal request workflow; only the room is synthetic.

The demo room's devices are ordinary SmartDevice records with
protocol "mock", so Aria and the kiosk control them through the normal
room-command path (/devices/public/room/{room}/command) and the simulated
adapter (simulated_device.py). Nothing here executes commands.

Reset restores a known baseline: one light, thermostat, TV and blinds in
the demo room (created if missing), baseline state, and open requests
marked simulated for the demo room closed through the lifecycle, each with
its own receipt; any other open request there is left untouched. It refuses
unless the public demo kiosk is in DEMO_ROOM, and when that room holds any
non-simulated device, so it can never touch a real room, real requests or
real hardware.
"""
from fastapi import APIRouter, HTTPException

from deps import db
from models import Kiosk, Resident, SmartDevice, now_utc
from routes.receipts import create_receipt
from routes import task_actions
from routes.actor_context import actor_system

router = APIRouter(prefix="/demo", tags=["demo"])

DEMO_ROOM = "DEMO"
DEMO_RESIDENT_NAME = "Demo - Sample Resident"
DEMO_KIOSK_NAME = "Demo room (simulated devices)"

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


def _iso(doc: dict) -> dict:
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


async def ensure_demo_room(database=None) -> dict:
    """Create the demo-only resident and kiosk if missing and make that kiosk
    the single public demo kiosk. Idempotent. Touches no other room's data:
    other kiosks only lose the `public_demo` flag (as routes/kiosks.py does)."""
    database = database if database is not None else db
    resident = await database.residents.find_one({"room": DEMO_ROOM}, {"_id": 0})
    if not resident:
        resident = _iso(Resident(name=DEMO_RESIDENT_NAME, preferred_name="Sam", room=DEMO_ROOM,
                                 pendant_id="DEMO-NONE", synthetic=True,
                                 memory="Synthetic demo resident for the public demo kiosk.").model_dump())
        await database.residents.insert_one(dict(resident))
    elif not resident.get("synthetic"):
        # Mark the existing demo resident synthetic (SIM-0): work created for
        # it is then marked simulated, and only that work is reset.
        await database.residents.update_one({"resident_id": resident["resident_id"]},
                                            {"$set": {"synthetic": True}})
    kiosk = await database.kiosks.find_one({"room": DEMO_ROOM}, {"_id": 0})
    if not kiosk:
        kiosk = _iso(Kiosk(name=DEMO_KIOSK_NAME, room=DEMO_ROOM, zone="Demo").model_dump())
        await database.kiosks.insert_one(dict(kiosk))
    await database.kiosks.update_many({"kiosk_id": {"$ne": kiosk["kiosk_id"]}, "public_demo": True},
                                      {"$set": {"public_demo": False}})
    await database.kiosks.update_one({"kiosk_id": kiosk["kiosk_id"]}, {"$set": {"public_demo": True}})
    return {"room": DEMO_ROOM, "kiosk_id": kiosk["kiosk_id"], "resident_id": resident["resident_id"]}


async def _demo_kiosk() -> dict:
    kiosk = await db.kiosks.find_one({"public_demo": True}, {"_id": 0})
    if not kiosk or not kiosk.get("room"):
        raise HTTPException(status_code=404, detail="No public demo kiosk is configured.")
    return kiosk


@router.post("/reset")
async def demo_reset():
    kiosk = await _demo_kiosk()
    room = kiosk["room"]
    if room != DEMO_ROOM:
        raise HTTPException(
            status_code=409,
            detail=f"Demo reset refused: the public demo kiosk is in room {room}, not the demo-only room {DEMO_ROOM}.",
        )
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

    # Only work marked simulated for the demo room is closed, each through the
    # lifecycle with its own receipt. Any other open request in the room
    # (unmarked, unverified, or older than the marker) is left exactly as it
    # is and counted, never silently closed.
    actor = actor_system("demo_reset")
    open_q = {"room": room, "status": {"$in": OPEN_TASK_STATUSES}}
    marked = {**open_q, "simulated": True, "simulation_scope": "demo_room"}
    closed = 0
    async for task in db.staff_tasks.find(marked, {"_id": 0, "task_id": 1}):
        try:
            await task_actions.skip(task["task_id"], "Closed by demo reset", actor, None,
                                    authority="system:demo_reset")
            closed += 1
        except HTTPException:
            pass   # refused (e.g. no recorded origin): left open, counted below
    left_open = await db.staff_tasks.count_documents(open_q)

    receipt = await create_receipt(
        action_type="demo_reset", related_object_type="kiosk", related_object_id=kiosk["kiosk_id"],
        source="system", resident_id=resident_id, room=room,
    )
    return {"room": room, "kiosk_id": kiosk["kiosk_id"], "devices": result,
            "requests_closed": closed, "left_open": left_open, "receipt_id": receipt["receipt_id"]}
