"""Seed data and per-room conversation scripts for voice-bridge load runs.

Every room gets its own community (facility), apartment (room/kiosk),
resident, Voice PE device id and conversation id. The resident's preferred
name is a unique token (LTnnnXX) so any reply or model context that carries
another room's token is detectable as cross-resident leakage.
"""
import random
import string

from routes.realtime_facility import today_facility_date

ENDINGS = ["That'll be all.", "That'll be all, Aria.", "Goodbye, Aria.", "I'm done.", "Thank you, goodbye."]

# (text, kind). kind names the test-mix category; "retry" resends the
# previous utterance immediately, as Home Assistant would after a timeout.
SCRIPTS = [
    [("Hello Aria, how are you today?", "conversation"), ("What's for dinner tonight?", "menu"),
     ("What time is that?", "conversation")],
    [("Good morning Aria.", "conversation"), ("What activities are on today?", "activities")],
    [("Please turn on the light.", "lighting"), ("Now turn the light off.", "lighting")],
    [("Can you set the thermostat to 72 degrees?", "thermostat")],
    [("My sink is leaking.", "maintenance"), ("My sink is leaking.", "retry"),
     ("What's the status of my request?", "status")],
    [("I need a ride to my doctor tomorrow.", "transportation")],
    [("Could the front desk send some fresh towels?", "staff_help")],
    [("I need a nurse, I need help getting up.", "nursing"), ("Is anyone coming? What's the status?", "status")],
    [("I fell and I can't get up.", "emergency"), ("Please stay with me.", "conversation")],
    [("Tell me a story about a garden.", "conversation"), ("That was lovely, tell me another.", "conversation")],
]


def token(i: int) -> str:
    rnd = random.Random(i)
    return f"LT{i:03d}{rnd.choice(string.ascii_uppercase)}{rnd.choice(string.ascii_uppercase)}"


def room_script(i: int) -> list:
    return SCRIPTS[i % len(SCRIPTS)] + [(ENDINGS[i % len(ENDINGS)], "ending")]


def room_ids(i: int) -> dict:
    return {"facility_id": f"fac_lt_{i:03d}", "kiosk_id": f"kio_lt_{i:03d}", "room": f"LT-{i:03d}",
            "resident_id": f"res_lt_{i:03d}", "device_id": f"lt-voicepe-{i:03d}", "token": token(i)}


async def seed(db, rooms: int):
    from routes.departments import seed_default_departments
    from routes.voice_bridge_session import ensure_indexes
    await ensure_indexes()
    await seed_default_departments()
    today = today_facility_date()
    fac, kio, res, dev = [], [], [], []
    for i in range(rooms):
        r = room_ids(i)
        fac.append({"facility_id": r["facility_id"], "name": f"Load Test Community {i:03d}",
                    "is_active": i == 0, "created_at": "2026-10-03T00:00:00"})
        kio.append({"kiosk_id": r["kiosk_id"], "name": r["room"], "room": r["room"], "zone": "lt",
                    "voice_device_ids": [r["device_id"]], "facility_id": r["facility_id"]})
        res.append({"resident_id": r["resident_id"], "name": f"Resident {r['token']}",
                    "preferred_name": r["token"], "room": r["room"]})
        dev += [{"device_id": f"dev_lt_light_{i:03d}", "label": "lamp", "kind": "light", "protocol": "mock",
                 "room": r["room"], "resident_id": r["resident_id"], "capabilities": ["power", "brightness"],
                 "state": {"power": "off", "brightness": 80}, "online": True},
                {"device_id": f"dev_lt_therm_{i:03d}", "label": "thermostat", "kind": "thermostat",
                 "protocol": "mock", "room": r["room"], "resident_id": r["resident_id"],
                 "capabilities": ["power", "temperature"], "state": {"power": "on", "temperature": 74},
                 "online": True}]
    await db.facilities.insert_many(fac)
    await db.kiosks.insert_many(kio)
    await db.residents.insert_many(res)
    await db.smart_devices.insert_many(dev)
    await db.menu_items.insert_many([
        {"menu_id": "lt_m1", "date": today, "meal_period": "dinner", "item_name": "Roast chicken", "status": "approved"},
        {"menu_id": "lt_m2", "date": today, "meal_period": "lunch", "item_name": "Tomato soup", "status": "approved"}])
    await db.schedule_items.insert_one({"schedule_id": "lt_s1", "date": today, "time_label": "2:00 PM",
                                        "title": "Chair yoga", "category": "activity"})
