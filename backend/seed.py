"""Seed data for first-run demo: admin user, zones, residents, kiosks, roadmap."""
import asyncio
import bcrypt
from datetime import datetime, timezone

from deps import db
from models import User, Resident, Kiosk, Zone, Pendant, RoadmapItem, now_utc


ROADMAP_SEED = [
    # Phase 1 — Core Pilot
    (1, "Resident help-request intake (kiosk)", "One-button kiosk UI with emergency / assist / comfort modes.", "done"),
    (1, "Pendant signal intake (hardware hook)", "Register pendants by frequency; Android bridge POSTs /api/pendants/event from USB RF receiver.", "in_progress"),
    (1, "Staff notification + acknowledgment", "Live feed polling every 3s; acknowledge + resolve actions.", "done"),
    (1, "Resident reassurance loop (Claude + voice)", "Claude Sonnet 4.5 with resident-specific context; OpenAI TTS (sage voice).", "done"),
    (1, "Event log storage", "All alerts persisted with timestamps, responders, outcomes.", "done"),

    # Phase 2 — Workflow Visibility
    (2, "Dashboard visibility", "Staff dashboard with alerts + locations + stats tiles.", "done"),
    (2, "Event timelines", "Per-alert created → paged → acked → resolved view.", "done"),
    (2, "Open/closed status tracking", "Close-out notes + outcome capture on every alert.", "done"),
    (2, "Handoff and follow-up logging", "Track who acknowledged, who resolved, timestamps.", "done"),
    (2, "Escalation timers", "Auto-escalate unacknowledged alerts at 60s / 3m / 7m.", "done"),
    (2, "Family notification options", "Opt-in family contacts + configurable notification scope.", "not_started"),

    # Phase 3 — Location & Mobility
    (3, "Zone mapping", "Admin-defined zones with floor + description.", "done"),
    (3, "Router/receiver-based location narrowing", "Android bridge reports the tablet's zone with every pendant event.", "in_progress"),
    (3, "Live latest-per-resident location view", "Staff dashboard shows last-seen zone for every resident.", "done"),
    (3, "Wearable support", "Optional wearable trigger + location.", "not_started"),
    (3, "Geofencing", "Restricted zones + wander alerts.", "not_started"),
    (3, "Wander / elopement alerting", "Automatic alerts when a resident breaches a restricted zone.", "not_started"),
    (3, "Movement trend collection", "Store location history for pattern analysis.", "in_progress"),

    # Phase 4 — Predictive Insight
    (4, "Baseline behavior profiles", "Nightly rollups per resident (help frequency, mobility, nighttime activity).", "not_started"),
    (4, "Nighttime activity change detection", "Surface deviations vs baseline.", "not_started"),
    (4, "Bathroom frequency / location drift indicators", "Non-diagnostic observations for staff review.", "not_started"),
    (4, "Mobility decline indicators", "Movement trend analysis.", "not_started"),
    (4, "Response burden patterns", "Which residents need the most help this week?", "not_started"),
    (4, "Confidence-scored risk flags", "\"Margaret's nighttime help requests up 3x this week\".", "not_started"),

    # Cross-cutting / infra
    (5, "Participation levels + consent", "Per-resident room-only / pendant / wearable / family-connected / full.", "done"),
    (5, "Pendant registry (frequency ↔ resident)", "Admin CRUD; each pendant has a unique frequency.", "done"),
    (5, "Pendant battery + signal status", "Surface low-battery + last-seen for every pendant.", "done"),
    (5, "Android tablet bridge app", "Native app that reads USB RF receiver and POSTs /api/pendants/event.", "not_started"),
    (5, "Two-way voice path via kiosk", "Resident can talk, AI responds with voice.", "done"),
    (5, "SMS pager integration (Twilio)", "Real pager channel for staff on their existing phones.", "not_started"),
    (5, "Email/SMS family notifications", "Resend or SendGrid for opt-in family updates.", "not_started"),
    (5, "Device-token auth on /api/locations + /api/pendants/event", "HMAC or signed device token for field sensors.", "not_started"),
    (5, "AI-vision glasses/earbuds integration", "Walking guidance for low-vision residents.", "not_started"),
    (5, "Family portal", "Opt-in family view with status + selected updates.", "not_started"),
]


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
        doc.pop("_id", None)
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
        doc.pop("_id", None)
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
            d.pop("_id", None)

    # Residents (now with preferences + memory for AI personalization)
    residents_data = [
        ("Margaret O'Brien", "Maggie", "101", "PEN-0101",
         "Low vision. Hypertension. Needs walker.",
         "Irish stew, her grandkids Liam & Aoife, piano hymns, rainy days.",
         "Her late husband Frank passed in 2019 — she still talks about him warmly. She loves when you ask about her years as a schoolteacher in Boston."),
        ("Frank Delgado", "Frank", "108", "PEN-0108",
         "Hearing impaired. Mild dementia.",
         "Baseball (Dodgers), Sunday cooking, his dog Bruno, old Spanish songs.",
         "Speak loudly and clearly. He gets confused about the year — just roll with it. His daughter Elena visits every Saturday."),
        ("Evelyn Park", "Evie", "112", "PEN-0112",
         "Diabetic. Falls risk.",
         "Gardening, Korean dramas, her daughter Sue, lavender tea.",
         "She's proud she grew up in Seoul and moved here at 22. Ask about her garden — she grew tomatoes last summer."),
        ("Raymond Chen", "Ray", "205", "PEN-0205",
         "Recent hip replacement. Wheelchair.",
         "WWII history, jazz, chess, his late wife Helen.",
         "He was a mechanical engineer. Loves when someone asks him to explain how engines work."),
        ("Dorothy Walsh", "Dot", "214", "PEN-0214",
         "Blind. Heart condition.",
         "Audiobooks (mysteries), Beethoven, her cat Marigold, strong coffee.",
         "She is completely blind. Use vivid auditory language. She was a radio host in the 70s."),
        ("Harold Bennett", "Hal", "231", "PEN-0231",
         "Anxiety. Bedridden most days.",
         "Crossword puzzles, NPR, his son David, warm blankets.",
         "Gets panicky alone. Keep talking to him until staff arrive; short calm sentences."),
    ]
    for full_name, pref_name, room, pid, notes, prefs, memory in residents_data:
        existing_r = await db.residents.find_one({"room": room}, {"_id": 0})
        if not existing_r:
            r = Resident(
                name=full_name,
                preferred_name=pref_name,
                room=room,
                pendant_id=pid,
                medical_notes=notes,
                preferences=prefs,
                memory=memory,
                participation_level="pendant_enhanced",
            )
            d = r.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            await db.residents.insert_one(d)
            d.pop("_id", None)
        else:
            # Backfill preferences / memory / preferred_name if missing
            patch = {}
            if not existing_r.get("preferred_name"):
                patch["preferred_name"] = pref_name
            if not existing_r.get("preferences"):
                patch["preferences"] = prefs
            if not existing_r.get("memory"):
                patch["memory"] = memory
            if not existing_r.get("participation_level"):
                patch["participation_level"] = "pendant_enhanced"
            if patch:
                await db.residents.update_one({"room": room}, {"$set": patch})

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
            d.pop("_id", None)

    # Pendants - assign a unique frequency to each resident
    base_freq = 916.000
    for idx, r in enumerate(await db.residents.find({}, {"_id": 0}).sort("room", 1).to_list(100)):
        freq = round(base_freq + idx * 0.0125, 4)
        if not await db.pendants.find_one({"frequency_mhz": freq}, {"_id": 0}):
            p = Pendant(
                pendant_id=r.get("pendant_id", f"PEN-{r['room']}"),
                frequency_mhz=freq,
                resident_id=r["resident_id"],
                battery_percent=85 + (idx % 3) * 5,
                status="active",
                notes="Seeded demo pendant — pairs with Android RF receiver bridge.",
            )
            d = p.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            d["last_seen_at"] = None
            await db.pendants.insert_one(d)
            d.pop("_id", None)

    # Roadmap items
    for order, (phase, title, desc, status) in enumerate(ROADMAP_SEED):
        if not await db.roadmap.find_one({"title": title}, {"_id": 0}):
            item = RoadmapItem(
                phase=phase,
                title=title,
                description=desc,
                status=status,
                order=order,
            )
            d = item.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            d["updated_at"] = d["updated_at"].isoformat()
            await db.roadmap.insert_one(d)
            d.pop("_id", None)

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
