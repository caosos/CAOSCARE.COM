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
    (2, "Family notification options", "Opt-in family contacts + configurable notification scope.", "done"),

    # Phase 3 — Location & Mobility
    (3, "Zone mapping", "Admin-defined zones with floor + description.", "done"),
    (3, "Router/receiver-based location narrowing", "Android bridge reports the tablet's zone with every pendant event.", "done"),
    (3, "Live latest-per-resident location view", "Staff dashboard shows last-seen zone for every resident.", "done"),
    (3, "Wearable support", "Optional wearable trigger + location via /api/wearables/event (smartwatch/earbuds/BLE beacon).", "done"),
    (3, "Geofencing", "Restricted zones + wander alerts.", "done"),
    (3, "Wander / elopement alerting", "Automatic alerts when a resident breaches a restricted zone.", "done"),
    (3, "Movement trend collection", "Store location history for pattern analysis.", "done"),
    (3, "Per-resident movement timeline", "Visualize each resident's zone-visit history.", "done"),

    # Phase 4 — Predictive Insight
    (4, "Baseline behavior profiles", "Last 7d vs prior 7d rollups per resident.", "done"),
    (4, "Nighttime activity change detection", "Surface deviations vs baseline.", "done"),
    (4, "Bathroom frequency / location drift indicators", "Count location pings in zones flagged is_bathroom; compare last 7d to prior 7d. Non-diagnostic.", "done"),
    (4, "Mobility decline indicators", "Movement trend analysis.", "done"),
    (4, "Response burden patterns", "Which residents need the most help this week?", "done"),
    (4, "Confidence-scored risk flags", "\"Margaret's nighttime help requests up 3x this week\".", "done"),

    # Cross-cutting / infra
    (5, "Participation levels + consent", "Per-resident room-only / pendant / wearable / family-connected / full.", "done"),
    (5, "Pendant registry (frequency ↔ resident)", "Admin CRUD; each pendant has a unique frequency.", "done"),
    (5, "Pendant battery + signal status", "Surface low-battery + last-seen for every pendant.", "done"),
    (5, "Android tablet bridge app", "Native Kotlin app that reads USB RF receiver and POSTs /api/pendants/event.", "in_progress"),
    (5, "Two-way voice path via kiosk", "Resident can talk, AI responds with voice.", "done"),
    (5, "SMS pager integration (Twilio)", "NotificationService ready; flip on by adding TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER to backend/.env.", "in_progress"),
    (5, "Email family notifications (Resend)", "NotificationService ready; flip on by adding RESEND_API_KEY to backend/.env.", "in_progress"),
    (5, "Device-token auth on /api/locations + /api/pendants/event", "HMAC or signed device token for field sensors.", "not_started"),
    (5, "AI-vision glasses/earbuds integration", "Walking guidance for low-vision residents.", "not_started"),
    (5, "Family portal", "Magic-link portal for family contacts: /family/{token} shows resident status, last-seen zone, recent alert summary, and bedtime haiku digest.", "done"),
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
        ("First Floor East", "1", "Rooms 101-120 + Dining", False, False),
        ("First Floor West", "1", "Rooms 121-140 + Chapel", False, False),
        ("Second Floor", "2", "Rooms 201-240 + Lounge", False, False),
        ("Common Areas", "1", "Lobby, Garden, Activity Room", False, False),
        ("Staff Only — Medication Room", "1", "Restricted. Med storage, staff only.", True, False),
        ("Outside — Parking Lot", "0", "Restricted — elopement risk beyond this point.", True, False),
        ("Communal Bathroom - East", "1", "Shared bathroom, east wing.", False, True),
        ("Communal Bathroom - West", "1", "Shared bathroom, west wing.", False, True),
    ]
    for name, floor, desc, restricted, bathroom in zones_data:
        existing_z = await db.zones.find_one({"name": name}, {"_id": 0})
        if not existing_z:
            z = Zone(name=name, floor=floor, description=desc, is_restricted=restricted, is_bathroom=bathroom)
            d = z.model_dump()
            d["created_at"] = d["created_at"].isoformat()
            await db.zones.insert_one(d)
            d.pop("_id", None)
        else:
            patch = {}
            if existing_z.get("is_restricted") is None:
                patch["is_restricted"] = restricted
            if existing_z.get("is_bathroom") is None:
                patch["is_bathroom"] = bathroom
            if patch:
                await db.zones.update_one({"name": name}, {"$set": patch})

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

    # Sample family contacts (for Margaret and Dorothy)
    residents_for_family = await db.residents.find({}, {"_id": 0}).to_list(100)
    existing_fam_count = await db.family_contacts.count_documents({})
    if existing_fam_count == 0 and residents_for_family:
        import random as _r
        samples = [
            {"name": "Liam O'Brien (son)", "relationship": "son", "email": "liam.obrien@example.com", "phone": "+15555551001"},
            {"name": "Elena Delgado (daughter)", "relationship": "daughter", "email": "elena.delgado@example.com", "phone": "+15555551002"},
            {"name": "Sue Park (daughter)", "relationship": "daughter", "email": "sue.park@example.com", "phone": "+15555551003"},
        ]
        for i, sample in enumerate(samples):
            if i >= len(residents_for_family):
                break
            fc_doc = {
                "contact_id": f"fam_{_r.randint(100000, 999999)}",
                "resident_id": residents_for_family[i]["resident_id"],
                "notify_on": ["emergency", "wander"],
                "created_at": now_utc().isoformat(),
                **sample,
            }
            await db.family_contacts.insert_one(fc_doc)
            fc_doc.pop("_id", None)

    # Seed historical alerts + locations so Insights has something to analyze
    from datetime import timedelta
    import random as _r
    if await db.alerts.count_documents({}) < 5 and residents_for_family:
        now_dt = now_utc()
        for i, r in enumerate(residents_for_family[:4]):
            base_count = 3 + (i % 3)  # 3..5
            current_count = base_count + (2 if i < 2 else 0)  # a couple of residents trend up
            # 7-14 days ago (baseline window)
            for _ in range(base_count):
                when = now_dt - timedelta(days=_r.uniform(7.5, 13.5), hours=_r.uniform(0, 23))
                hist_alert = {
                    "alert_id": f"alert_seed_{_r.randint(100000, 999999)}",
                    "resident_id": r["resident_id"],
                    "resident_name": r["name"],
                    "room": r.get("room"),
                    "zone": _r.choice(["Room", "Hallway A", "Dining Room"]),
                    "severity": _r.choice(["assist", "assist", "comfort"]),
                    "status": "resolved",
                    "escalation_level": 0,
                    "message": "Historical seed",
                    "triggered_by": "kiosk_button",
                    "outcome": "Attended",
                    "created_at": when.isoformat(),
                    "resolved_at": (when + timedelta(minutes=_r.randint(2, 8))).isoformat(),
                    "resolved_by": "Nurse Sarah",
                }
                await db.alerts.insert_one(hist_alert)
                hist_alert.pop("_id", None)
            # last 0-7 days (current window)
            for _ in range(current_count):
                when = now_dt - timedelta(days=_r.uniform(0.2, 6.8), hours=_r.uniform(0, 23))
                # give resident[0] more nighttime activity
                if i == 0:
                    when = when.replace(hour=_r.choice([23, 0, 1, 2, 3]))
                hist_alert = {
                    "alert_id": f"alert_seed_{_r.randint(100000, 999999)}",
                    "resident_id": r["resident_id"],
                    "resident_name": r["name"],
                    "room": r.get("room"),
                    "zone": _r.choice(["Room", "Hallway A", "Dining Room"]),
                    "severity": _r.choice(["assist", "assist", "comfort"]),
                    "status": "resolved",
                    "escalation_level": 0,
                    "message": "Historical seed",
                    "triggered_by": "kiosk_button",
                    "outcome": "Attended",
                    "created_at": when.isoformat(),
                    "resolved_at": (when + timedelta(minutes=_r.randint(2, 8))).isoformat(),
                    "resolved_by": "Nurse Sarah",
                }
                await db.alerts.insert_one(hist_alert)
                hist_alert.pop("_id", None)

        # Location pings across windows for mobility metric
        ZONES = ["Room", "Hallway A", "Dining Room", "Lounge", "Garden Patio", "Chapel"]
        for r in residents_for_family[:4]:
            for _ in range(25):
                when = now_dt - timedelta(days=_r.uniform(0, 14), hours=_r.uniform(0, 23))
                loc = {
                    "update_id": f"loc_seed_{_r.randint(100000, 999999)}",
                    "resident_id": r["resident_id"],
                    "zone": _r.choice(ZONES),
                    "room": r.get("room"),
                    "signal_strength": _r.randint(60, 100),
                    "source": "mock",
                    "created_at": when.isoformat(),
                }
                await db.locations.insert_one(loc)
                loc.pop("_id", None)

    # Backfill portal_token on any existing family contacts that don't have one
    async for fc in db.family_contacts.find({"portal_token": {"$in": [None, ""]}}, {"_id": 0}):
        tok = f"ptok_{_r.randint(10**11, 10**12-1):x}"
        await db.family_contacts.update_one({"contact_id": fc["contact_id"]}, {"$set": {"portal_token": tok}})

    # Seed a sample wearable for the first resident (demo)
    if residents_for_family and await db.wearables.count_documents({}) == 0:
        first = residents_for_family[0]
        w_doc = {
            "wearable_id": f"wear_demo_{_r.randint(100000, 999999)}",
            "device_label": f"{first.get('preferred_name') or first['name']}'s demo smartwatch",
            "device_type": "smartwatch",
            "mac_address": "AA:BB:CC:DD:EE:01",
            "resident_id": first["resident_id"],
            "battery_percent": 78,
            "status": "active",
            "notes": "Seeded demo — pair your real device in Admin → Wearables.",
            "created_at": now_utc().isoformat(),
            "last_seen_at": None,
        }
        await db.wearables.insert_one(w_doc)
        w_doc.pop("_id", None)

    # Seed a few bathroom-zone pings so the insights bathroom metric has data
    if residents_for_family and await db.locations.count_documents({"zone": {"$regex": "Bathroom"}}) == 0:
        bathroom_names = ["Communal Bathroom - East", "Communal Bathroom - West"]
        for i, r in enumerate(residents_for_family[:4]):
            # Baseline window: 2 pings
            for _ in range(2):
                when = now_dt - timedelta(days=_r.uniform(7.5, 13.5), hours=_r.uniform(6, 22))
                await db.locations.insert_one({
                    "update_id": f"loc_bath_{_r.randint(100000, 999999)}",
                    "resident_id": r["resident_id"],
                    "zone": _r.choice(bathroom_names),
                    "room": r.get("room"),
                    "signal_strength": _r.randint(60, 95),
                    "source": "mock",
                    "created_at": when.isoformat(),
                })
            # Current window: more for first resident (trending up signal)
            current_count = 6 if i == 0 else 3
            for _ in range(current_count):
                when = now_dt - timedelta(days=_r.uniform(0.2, 6.8), hours=_r.uniform(6, 22))
                await db.locations.insert_one({
                    "update_id": f"loc_bath_{_r.randint(100000, 999999)}",
                    "resident_id": r["resident_id"],
                    "zone": _r.choice(bathroom_names),
                    "room": r.get("room"),
                    "signal_strength": _r.randint(60, 95),
                    "source": "mock",
                    "created_at": when.isoformat(),
                })

    # Roadmap items (idempotent; advance status if this iteration marks done)
    for order, (phase, title, desc, status) in enumerate(ROADMAP_SEED):
        existing_item = await db.roadmap.find_one({"title": title}, {"_id": 0})
        if not existing_item:
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
        elif existing_item.get("status") != "done" and status == "done":
            await db.roadmap.update_one(
                {"title": title},
                {"$set": {"status": status, "description": desc, "phase": phase, "updated_at": now_utc().isoformat()}},
            )

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
