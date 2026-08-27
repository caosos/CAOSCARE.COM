"""Seed one mock thermostat + one mock TV per resident room, so Aria's
device tools (get_room_status/adjust_room_temperature/toggle_light/
toggle_tv) have something real to read and change instead of 404ing.

Individualized per room: varied starting temperature/TV state so each
room is verifiably its own record, not a shared/copied default. Creates
devices via the same live POST /devices endpoint the Admin UI uses (not
direct DB writes), protocol="mock" (see models.py's DeviceProtocol) so
devices.py executes commands synchronously instead of queuing for a
bridge tablet that doesn't exist yet. Idempotent - skips any room that
already has devices.

Run with: python3 scripts/seed_mock_devices.py
"""
import asyncio
import sys

import httpx

sys.path.insert(0, ".")
from routes.auth import _issue_jwt  # noqa: E402
from deps import db  # noqa: E402

BASE = "http://127.0.0.1:8000/api"


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    residents = await db.residents.find({}, {"_id": 0, "resident_id": 1, "room": 1, "name": 1}).to_list(200)
    residents = [r for r in residents if r.get("room")]
    residents.sort(key=lambda r: r["room"])

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        print(f"=== Seeding mock devices for {len(residents)} rooms ===")
        created, skipped = 0, 0
        for i, r in enumerate(residents):
            room = r["room"]
            existing = await db.smart_devices.find_one({"room": room}, {"_id": 0, "device_id": 1})
            if existing:
                skipped += 1
                continue

            # Individualized starting state per room - not a copy-pasted default.
            start_temp = 68 + (i % 8)  # 68-75F, varies by room
            thermostat = {
                "label": f"Room {room} thermostat",
                "kind": "thermostat",
                "protocol": "mock",
                "room": room,
                "resident_id": r["resident_id"],
                "capabilities": ["power", "temperature"],
                "vendor": "CAOS Mock",
                "notes": "Demo/mock device - no bridge tablet deployed for this room yet.",
            }
            resp = await c.post("/devices", json=thermostat)
            resp.raise_for_status()
            dev = resp.json()
            await c.post(f"/devices/{dev['device_id']}/command", json={"action": "power", "value": "on"})
            await c.post(f"/devices/{dev['device_id']}/command", json={"action": "temperature", "value": start_temp})

            tv = {
                "label": f"Room {room} TV",
                "kind": "tv",
                "protocol": "mock",
                "room": room,
                "resident_id": r["resident_id"],
                "capabilities": ["power", "volume", "channel", "input"],
                "inputs": ["TV", "HDMI 1", "HDMI 2", "HDMI 3"],
                "vendor": "CAOS Mock",
                "notes": "Demo/mock device - no bridge tablet deployed for this room yet.",
            }
            resp = await c.post("/devices", json=tv)
            resp.raise_for_status()
            tv_dev = resp.json()
            await c.post(f"/devices/{tv_dev['device_id']}/command", json={"action": "power", "value": "off"})
            await c.post(f"/devices/{tv_dev['device_id']}/command", json={"action": "input", "value": "TV"})

            print(f"  Room {room} ({r['name']}): thermostat @ {start_temp}F, TV off")
            created += 1

        print(f"\n=== Done: {created} rooms seeded, {skipped} already had devices ===")


if __name__ == "__main__":
    asyncio.run(main())
