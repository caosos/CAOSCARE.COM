"""Seed data for first-run demo: admin user, zones, residents, kiosks, roadmap."""
import asyncio
import os
import bcrypt
from datetime import datetime, timezone

from deps import db
from models import User, Resident, Kiosk, Zone, Pendant, RoadmapItem, SmartDevice, now_utc


ROADMAP_SEED = [
    # Phase 1 — Core Pilot
    (1, "Resident help-request intake (kiosk)", "One-button kiosk UI with emergency / assist / comfort modes.", "done"),
    (1, "Pendant signal intake (hardware hook)", "Register pendants by frequency; Android bridge POSTs /api/pendants/event from USB RF receiver.", "in_progress"),
    (1, "Staff notification + acknowledgment", "Live feed polling every 3s; acknowledge + resolve actions.", "done"),
    (1, "Resident reassurance loop (Claude + voice)", "Claude Sonnet 4.5 with resident-specific context; OpenAI TTS (sage voice).", "done"),
    (1, "Event log storage", "All alerts persisted with timestamps, responders, outcomes.", "done"),
    (1, "Smart-room device control (lights/fan/heater/TV)", "Tablet as per-room hub. BLE / WiFi / RF_915 / IR / Zigbee / Matter devices. Admin Devices tab + kiosk big-button controls + command queue for bridge.", "done"),

    # Phase 2 — Workflow Visibility (unchanged)

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
    (5, "AI-vision glasses/earbuds integration", "Vuzix M400 + Android generic fallback. POST /api/vision/describe + /frame use Claude image-vision; companion app pairs to tablet via BLE.", "in_progress"),
    (5, "Family portal", "Magic-link portal for family contacts: /family/{token} shows resident status, last-seen zone, recent alert summary, and bedtime haiku digest.", "done"),
    (5, "Panic-press → hands-free voice", "Pendant pressed ≥2x in 60s (or fall event) upgrades to emergency + auto_voice=True. Kiosk polls /api/kiosks/{id}/active-emergency and auto-enables its mic when a match is found.", "done"),
    (5, "Central nurse-station kiosk", "Kiosk.is_central=true listens for ANY facility-wide emergency, not just its room/zone.", "done"),
    (5, "Staff task management", "Daily templates spawn into assigned tasks. Start → in_progress → Complete → audit trail (who, when, duration, notes).", "done"),
    (5, "Daily haiku generator", "POST /api/haiku/generate-today uses Claude to write one bedtime haiku per resident, surfaced on the family portal.", "done"),
    (5, "Pager RF emulation", "Facility paging system bridged via /api/paging/event; live feed /api/paging/feed shown on every staff tablet.", "done"),
    (5, "Medication reminder voice", "Scheduled per-resident reminders; kiosk polls /api/medications/due/by-room and speaks at the right minute.", "done"),
    (5, "Floor-plan heatmap", "Admin → Map shows each resident's live zone as dots on a simple SVG floor plan.", "done"),
]


def demo_seed_enabled() -> bool:
    """Return true only when demo seed data is explicitly enabled.

    The safe default is disabled so production/server boot cannot silently create
    known demo accounts with published passwords. Local demos may opt in by
    setting CAOSCARE_ENABLE_DEMO_SEED=true.
    """
    return os.environ.get("CAOSCARE_ENABLE_DEMO_SEED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def seed():
    if not demo_seed_enabled():
        print(
            "Demo seed skipped; set CAOSCARE_ENABLE_DEMO_SEED=true only for local/demo environments."
        )
        return

    # System owner (highest tier — you, the product owner)
    owner_email = "owner@caoscare.com"
    existing = await db.users.find_one({"email": owner_email}, {"_id": 0})
    if not existing:
        owner = User(
            email=owner_email,
            name="System Owner",
            role="owner",
            auth_provider="jwt",
            password_hash=bcrypt.hashpw(b"owner1234", bcrypt.gensalt()).decode(),
        )
        doc = owner.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.users.insert_one(doc)
        print(f"Created owner: {owner_email} / owner1234")

    # Admin (clinical admin / admin nurse) — facility leadership
    admin_email = "admin@caoscare.com"
    existing = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if not existing:
        admin = User(
            email=admin_email,
            name="Admin Nurse",
            role="admin",
            auth_provider="jwt",
            password_hash=bcrypt.hashpw(b"admin1234", bcrypt.gensalt()).decode(),
        )
        doc = admin.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.users.insert_one(doc)
        doc.pop("_id", None)
        print(f"Created admin nurse: {admin_email} / admin1234")

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

    # Kiosks - one per resident room + one central nurse station
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

    # Central nurse-station kiosk (listens facility-wide for emergencies)
    if not await db.kiosks.find_one({"is_central": True}, {"_id": 0}):
        k = Kiosk(
            name="Central Nurse Station",
            room="NS-01",
            zone="Common Areas",
            mac_address="AA:BB:CC:NS:01:01",
            is_central=True,
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

    # Seed smart-room devices for the first 2 residents (demo)
    if residents_for_family and await db.smart_devices.count_documents({}) == 0:
        for r in residents_for_family[:2]:
            room = r["room"]
            sample_devs = [
                ("Bedside lamp", "light", "bluetooth", ["power", "brightness"], {"power": "off", "brightness": 60}),
                ("Ceiling fan", "fan", "rf_915", ["power", "fan_speed"], {"power": "off", "fan_speed": 1}),
                ("Heater", "heater", "wifi", ["power", "temperature"], {"power": "off", "temperature": 22}),
                ("TV", "tv", "ir", ["power", "volume", "channel"], {"power": "off", "volume": 15}),
            ]
            for label, kind, proto, caps, state in sample_devs:
                d = SmartDevice(
                    label=f"Room {room} {label}",
                    kind=kind,
                    protocol=proto,
                    room=room,
                    resident_id=r["resident_id"],
                    capabilities=caps,
                    state=state,
                    endpoint="demo",
                    vendor="Seed",
                )
                doc = d.model_dump()
                doc["created_at"] = doc["created_at"].isoformat()
                doc["last_command_at"] = None
                await db.smart_devices.insert_one(doc)
                doc.pop("_id", None)

    # Seed task templates (recurring daily work)
    if await db.task_templates.count_documents({}) == 0:
        default_templates = [
            ("Morning med pass", "Deliver scheduled morning medications.", "meds", "day"),
            ("Evening med pass", "Deliver scheduled evening medications.", "meds", "evening"),
            ("Breakfast round", "Assist residents to the dining room or deliver trays.", "meal", "day"),
            ("Dinner round", "Assist with dinner service.", "meal", "evening"),
            ("Laundry — Floor 1", "Collect and start floor-1 laundry.", "laundry", "day"),
            ("Laundry — Floor 2", "Collect and start floor-2 laundry.", "laundry", "day"),
            ("Hourly safety rounds", "Walk each wing, check on residents.", "rounds", "any"),
            ("Night check-in rounds", "Quiet walk-through — confirm each resident safe.", "rounds", "night"),
            ("Bathing — Margaret", "Assist with morning bathing.", "bathing", "day"),
            ("Activity — afternoon social", "Run the lounge activity.", "activity", "day"),
        ]
        for title, desc, cat, shift in default_templates:
            tpl = {
                "template_id": f"ttpl_{_r.randint(100000, 999999)}",
                "title": title,
                "description": desc,
                "category": cat,
                "shift": shift,
                "recur": "daily",
                "active": True,
                "created_at": now_utc().isoformat(),
            }
            await db.task_templates.insert_one(tpl)

    # Spawn today's tasks from templates (idempotent)
    today = now_utc().date().isoformat()
    start_iso = f"{today}T00:00:00+00:00"
    end_iso = f"{today}T23:59:59+00:00"
    staff_pool = await db.users.find({"role": "staff"}, {"_id": 0, "user_id": 1, "name": 1}).to_list(20)
    async for tpl in db.task_templates.find({"active": True}, {"_id": 0}):
        existing_task = await db.staff_tasks.find_one({
            "template_id": tpl["template_id"],
            "created_at": {"$gte": start_iso, "$lte": end_iso},
        }, {"_id": 0})
        if existing_task:
            continue
        assigned = _r.choice(staff_pool) if staff_pool else None
        task_doc = {
            "task_id": f"task_{_r.randint(100000, 999999)}",
            "title": tpl["title"],
            "description": tpl.get("description", ""),
            "category": tpl.get("category", "other"),
            "shift": tpl.get("shift", "any"),
            "assigned_to": assigned["user_id"] if assigned else None,
            "assigned_name": assigned["name"] if assigned else None,
            "resident_id": tpl.get("resident_id"),
            "room": tpl.get("room"),
            "status": "pending",
            "template_id": tpl["template_id"],
            "created_at": now_utc().isoformat(),
        }
        await db.staff_tasks.insert_one(task_doc)

    # Seed medication reminders (1-2 per resident)
    if residents_for_family and await db.med_reminders.count_documents({}) == 0:
        med_samples = [
            ("Blood pressure pill", "08:00", "One white tablet with water"),
            ("Morning vitamins", "08:30", "Multivitamin + calcium"),
            ("Evening heart pill", "20:00", "Blue tablet — take with food"),
        ]
        for i, r in enumerate(residents_for_family[:4]):
            title, hhmm, notes = med_samples[i % len(med_samples)]
            await db.med_reminders.insert_one({
                "reminder_id": f"med_{_r.randint(100000, 999999)}",
                "resident_id": r["resident_id"],
                "resident_name": r["name"],
                "room": r.get("room"),
                "title": title,
                "time_hhmm": hhmm,
                "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "dose_notes": notes,
                "active": True,
                "created_at": now_utc().isoformat(),
            })

    # Seed a couple of historical pager events for demo
    if await db.pager_events.count_documents({}) == 0 and residents_for_family:
        sample_pages = [
            ("Call bell — Room 101", "page", residents_for_family[0]),
            ("Assist bathroom — Room 108", "page", residents_for_family[1] if len(residents_for_family) > 1 else None),
        ]
        for msg, urgency, res in sample_pages:
            when = now_utc() - timedelta(minutes=_r.randint(1, 25))
            await db.pager_events.insert_one({
                "page_id": f"page_{_r.randint(100000, 999999)}",
                "source": "facility_rf",
                "cap_code": res.get("pendant_id") if res else None,
                "resident_id": res["resident_id"] if res else None,
                "resident_name": res["name"] if res else None,
                "room": res.get("room") if res else None,
                "zone": None,
                "message": msg,
                "urgency": urgency,
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
