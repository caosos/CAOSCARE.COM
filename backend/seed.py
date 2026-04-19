"""Seed data for first-run demo: admin user, zones, residents, kiosks."""
import asyncio
import bcrypt
from datetime import datetime, timezone

from deps import db
from models import User, Resident, Kiosk, Zone, now_utc


async def seed():
    # Admin user
    admin_email = "admin@caoscare.com"
    existing = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if not existing:
        admin = User(
            email=admin_email,
            name="Admin",
            role="admin",
            auth_provider="jwt",
            password_hash=bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode(),
        )
        doc = admin.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.users.insert_one(doc)
        print(f"Created admin: {admin_email} / admin1234")

    # Staff user
    staff_email = "nurse@caoscare.com"
    existing = await db.users.find_one({"email": staff_email}, {"_id": 0})
    if not existing:
        staff = User(
            email=staff_email,
            name="Nurse Sarah",
            role="staff",
            auth_provider="jwt",
            password_hash=bcrypt.hashpw(b"nurse1234", bcrypt.gensalt()).decode(),
        )
        doc = staff.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.users.insert_one(doc)
        print(f"Created staff: {staff_email} / nurse1234")

    # Zones
    zones_data = [
        ("First Floor East", "1", "Rooms 101-120 + Dining"),
        ("First Floor West", "1", "Rooms 121-140 + Chapel"),
        ("Second Floor", "2", "Rooms 201-240 + Lounge"),
        ("Common Areas", "1", "Lobby, Garden, Activity Room"),
    ]
    for name, floor, desc in zones_data:
        if not await db.zones.find_one({"name": name}, {"_id": 0}):
            z = Zone(name=name, floor=floor, description=desc)
            d = z.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            await db.zones.insert_one(d)

    # Residents
    residents_data = [
        ("Margaret O'Brien", "101", "PEN-0101", "Low vision. Hypertension. Needs walker."),
        ("Frank Delgado", "108", "PEN-0108", "Hearing impaired. Mild dementia."),
        ("Evelyn Park", "112", "PEN-0112", "Diabetic. Falls risk."),
        ("Raymond Chen", "205", "PEN-0205", "Recent hip replacement. Wheelchair."),
        ("Dorothy Walsh", "214", "PEN-0214", "Blind. Heart condition."),
        ("Harold Bennett", "231", "PEN-0231", "Anxiety. Bedridden most days."),
    ]
    for name, room, pid, notes in residents_data:
        if not await db.residents.find_one({"room": room}, {"_id": 0}):
            r = Resident(name=name, room=room, pendant_id=pid, medical_notes=notes)
            d = r.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            await db.residents.insert_one(d)

    # Kiosks - one per resident room
    residents = await db.residents.find({}, {"_id": 0}).to_list(100)
    for r in residents:
        room = r["room"]
        if not await db.kiosks.find_one({"room": room}, {"_id": 0}):
            zone_name = "First Floor East" if room.startswith("1") else "Second Floor"
            k = Kiosk(
                name=f"Kiosk Room {room}",
                room=room,
                zone=zone_name,
                mac_address=f"AA:BB:CC:00:{room[:2]}:{room[-2:]}",
            )
            d = k.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            await db.kiosks.insert_one(d)

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
