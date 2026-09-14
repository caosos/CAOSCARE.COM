"""Coherent DEMO community for local visual break-testing.

Every entity is created through the SAME live endpoints the real Admin UI
uses (owner JWT, HTTP) and is clearly prefixed "Demo -" / lives in rooms
301-310 / uses @demo.caoscare emails, so it is never mistaken for real
data and can be removed with `--wipe`.

It does NOT touch:
  - real Room 214 / Helen Torres (Level-1 RF evidence)
  - the existing MOCK 4xx cohort, TEST-1xx nodes, or historical alerts
  - any RF / pendant / ResidentEvent / realtime code

The same residents/rooms/staff correlate across residents, kiosks,
smart devices, family, tasks, a maintenance work order, transportation,
a couple of (resolved) historical alerts, and the real Menu path so
Resident Aria can later answer "what's for dinner" from actual data.

Run from backend/:
    .venv/bin/python3 scripts/seed_demo_community.py          # create
    .venv/bin/python3 scripts/seed_demo_community.py --wipe   # remove
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

import httpx

sys.path.insert(0, ".")
from routes.auth import _issue_jwt  # noqa: E402
from routes.realtime_facility import today_facility_date  # noqa: E402
from deps import db  # noqa: E402

BASE = os.environ.get("SEED_API_BASE", "http://127.0.0.1:8000").rstrip("/") + "/api"
DEMO_PW = "demo-pass-1234"
# A dedicated "3 West" wing - room strings that CANNOT collide with any real
# or existing test room (214, 121, 304, 318, 512, 4xx MOCK, TEST-1xx/2xx).
DEMO_ROOMS = [f"3W{i:02d}" for i in range(1, 11)]
ROOM_RX = "^3W[0-9]{2}$"

RESIDENTS = [
    ("Demo - Alice Monroe", "Allie", DEMO_ROOMS[0], "full", "Watercolour painting, NPR, her tabby Mister Biggs"),
    ("Demo - Frank Delgado", "Frank", DEMO_ROOMS[1], "pendant_enhanced", "Cardinals baseball, dominoes, black coffee"),
    ("Demo - Betty Owusu", "Betty", DEMO_ROOMS[2], "wearable_enhanced", "Gospel choir, Scrabble, tending the courtyard roses"),
    ("Demo - Gene Piotrowski", "Gene", DEMO_ROOMS[3], "family_connected", "Big-band records, model trains, ham radio stories"),
    ("Demo - Rosa Marchetti", "Rosa", DEMO_ROOMS[4], "full", "Italian cooking shows, bocce, her grandkids' visits"),
    ("Demo - Willie Bradford", "Willie", DEMO_ROOMS[5], "pendant_enhanced", "Fishing tales, westerns, sweet tea"),
    ("Demo - Ingrid Halvorsen", "Ingrid", DEMO_ROOMS[6], "wearable_enhanced", "Knitting, mystery novels, birdwatching"),
    ("Demo - Marcus Bell", "Marcus", DEMO_ROOMS[7], "full", "Jazz trumpet, chess, documentaries"),
    ("Demo - Pearl Nakagawa", "Pearl", DEMO_ROOMS[8], "pendant_enhanced", "Origami, haiku, green tea and the morning news"),
    ("Demo - Otis Freeman", "Otis", DEMO_ROOMS[9], "family_connected", "Blues guitar, checkers, a good pastrami on rye"),
]

STAFF = [
    ("Demo - Nancy Reyes RN", "nancy.reyes@demo.caoscare", "staff", "nursing"),
    ("Demo - Carl Boone", "carl.boone@demo.caoscare", "staff", "maintenance"),
    ("Demo - Rosa Vega", "rosa.vega@demo.caoscare", "staff", "housekeeping"),
    ("Demo - Pete Nash", "pete.nash@demo.caoscare", "staff", "transportation"),
    ("Demo - Iris Kwan", "iris.kwan@demo.caoscare", "staff", "kitchen"),
    ("Demo - Dana Frost", "dana.frost@demo.caoscare", "front_desk", None),
]

MENU_7D = [
    (["Scrambled Eggs", "Turkey Bacon", "Wheat Toast", "Orange Juice"],
     ["Chicken Noodle Soup", "Turkey Sandwich", "Coleslaw"],
     ["Meatloaf", "Mashed Potatoes", "Green Beans", "Dinner Roll"]),
    (["Oatmeal with Brown Sugar", "Sausage Links", "Sliced Banana"],
     ["Grilled Cheese", "Tomato Soup", "Apple Sauce"],
     ["Baked Chicken Thighs", "Rice Pilaf", "Steamed Carrots"]),
    (["Buttermilk Pancakes", "Maple Syrup", "Scrambled Eggs", "Fruit Cup"],
     ["Beef Barley Soup", "Egg Salad Sandwich", "Pickle Spear"],
     ["Salisbury Steak", "Mashed Potatoes", "Peas and Carrots"]),
    (["French Toast", "Turkey Sausage", "Orange Slices"],
     ["Chicken Caesar Salad", "Dinner Roll", "Fruit Cocktail"],
     ["Roast Pork Loin", "Sweet Potatoes", "Green Beans"]),
    (["Cheese Omelet", "Hash Browns", "Wheat Toast"],
     ["Split Pea Soup", "Tuna Melt", "Carrot Sticks"],
     ["Baked Cod", "Wild Rice", "Broccoli", "Lemon Wedge"]),
    (["Blueberry Muffin", "Scrambled Eggs", "Yogurt Parfait"],
     ["Minestrone", "Roast Beef Sandwich", "Potato Salad"],
     ["Spaghetti and Meatballs", "Garlic Bread", "Tossed Salad"]),
    (["Waffles", "Warm Berry Compote", "Turkey Sausage"],
     ["Chicken Tortilla Soup", "Club Sandwich", "Fruit Salad"],
     ["Roast Turkey", "Herb Stuffing", "Mashed Potatoes", "Gravy", "Green Beans"]),
]


async def _owner_headers():
    o = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    return {"Authorization": f"Bearer {_issue_jwt(o['user_id'])}"}


async def wipe(c):
    """Precise wipe. Every delete is scoped to something the seed itself
    creates: a "Demo - " name/title, an @demo.caoscare email, or a 3Wxx
    room. It never uses a broad numeric room range that could touch a
    real/existing room."""
    print("=== Wiping demo community ===")
    res = await db.residents.find({"name": {"$regex": "^Demo - "}}, {"_id": 0, "resident_id": 1}).to_list(200)
    rid = [r["resident_id"] for r in res]
    r1 = await db.residents.delete_many({"name": {"$regex": "^Demo - "}})
    r2 = await db.kiosks.delete_many({"room": {"$regex": ROOM_RX}})
    r3 = await db.users.delete_many({"email": {"$regex": "@demo\\.caoscare$"}})
    r4 = await db.staff_tasks.delete_many({"$or": [
        {"title": {"$regex": "^Demo - "}}, {"room": {"$regex": ROOM_RX}}, {"resident_id": {"$in": rid}},
    ]})
    r5 = await db.smart_devices.delete_many({"$or": [{"room": {"$regex": ROOM_RX}}, {"resident_id": {"$in": rid}}]})
    r6 = await db.alerts.delete_many({"$or": [{"room": {"$regex": ROOM_RX}}, {"resident_id": {"$in": rid}}]})
    r7 = await db.family_contacts.delete_many({"resident_id": {"$in": rid}})
    r8 = await db.memories.delete_many({"resident_id": {"$in": rid}})
    r9 = await db.receipts.delete_many({"$or": [{"room": {"$regex": ROOM_RX}}, {"resident_id": {"$in": rid}}]})
    for name, r in [("residents", r1), ("kiosks", r2), ("users", r3), ("tasks", r4),
                    ("smart_devices", r5), ("alerts", r6), ("family", r7),
                    ("memories", r8), ("receipts", r9)]:
        print(f"  {name}: -{r.deleted_count}")
    print("  (menu items via the real ingestion path are left in place - re-runnable, harmless)")


async def seed(c):
    if await db.residents.find_one({"name": {"$regex": "^Demo - "}}):
        print("Demo community already present - run with --wipe first to rebuild.")
        return

    print("=== Demo residents + rooms + devices + family + memory ===")
    res_ids = {}
    for name, pref, room, level, prefs in RESIDENTS:
        rr = (await c.post("/residents", json={
            "name": name, "preferred_name": pref, "room": room, "participation_level": level,
            "preferences": prefs, "pendant_id": f"demo_pendant_{room}",
        })).json()
        res_ids[room] = rr["resident_id"]
        await c.post("/kiosks", json={"name": f"Room {room}", "room": room, "zone": "3rd floor"})
        await c.post("/devices", json={
            "label": f"{pref}'s bedside lamp", "kind": "light", "protocol": "mock",
            "room": room, "resident_id": rr["resident_id"], "capabilities": ["power", "brightness"],
        })
        await c.post("/family-contacts", json={
            "resident_id": rr["resident_id"], "name": f"{pref.split()[0]}'s daughter",
            "relationship": "daughter", "email": f"family.{room}@demo.caoscare",
        })
        await c.post("/memory", json={
            "resident_id": rr["resident_id"], "text": prefs, "category": "preferences",
            "importance": 3, "source": "admin",
        })
        print(f"  {room}: {name}")

    print("=== Demo staff (real departments) ===")
    staff_ids = {}
    for name, email, role, dept in STAFF:
        body = {"name": name, "email": email, "password": DEMO_PW, "role": role}
        if dept:
            body["department"] = dept
        u = (await c.post("/staff", json=body)).json()
        staff_ids[dept or "front_desk"] = u.get("user_id")
        print(f"  {name} - {role}/{dept or '-'}")

    print("=== Demo operational work ===")
    R = DEMO_ROOMS
    # department chores (some assigned, some done)
    await c.post("/tasks", json={"title": "Demo - AM rounds, 3 West", "description": "Vitals + check-in, 3 West wing",
                                 "category": "nursing", "visibility_role": "nursing", "priority": "normal",
                                 "assigned_to": staff_ids.get("nursing")})
    done = (await c.post("/tasks", json={"title": "Demo - restock linen cart 3W", "category": "housekeeping",
                                         "visibility_role": "housekeeping", "assigned_to": staff_ids.get("housekeeping")})).json()
    await c.post(f"/tasks/{done['task_id']}/start")
    await c.post(f"/tasks/{done['task_id']}/complete", json={"notes": "Demo - done, cart full"})
    # maintenance work orders (one open, one done)
    await c.post("/tasks", json={"title": f"Demo - dripping faucet Rm {R[2]}", "description": "Bathroom sink drips overnight",
                                 "category": "maintenance", "visibility_role": "maintenance", "room": R[2],
                                 "priority": "normal", "assigned_to": staff_ids.get("maintenance")})
    wo2 = (await c.post("/tasks", json={"title": f"Demo - loose handrail Rm {R[6]}", "category": "maintenance",
                                        "visibility_role": "maintenance", "room": R[6], "priority": "high",
                                        "assigned_to": staff_ids.get("maintenance")})).json()
    await c.post(f"/tasks/{wo2['task_id']}/start")
    await c.post(f"/tasks/{wo2['task_id']}/complete", json={"notes": "Demo - re-anchored, torqued"})
    # resident-originated requests
    await c.post("/tasks/resident-request", json={"category": "housekeeping", "room": R[4],
                 "resident_id": res_ids[R[4]], "summary": "Demo - extra towels please", "source": "aria_voice"})
    await c.post("/tasks/resident-request", json={"category": "nursing", "room": R[1],
                 "resident_id": res_ids[R[1]], "summary": "Demo - would like to talk to my nurse", "source": "aria_voice"})
    # transportation
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    await c.post("/transportation/request", json={"resident_id": res_ids[R[7]], "room": R[7],
                 "purpose": "pharmacy pickup", "requested_for_date": tomorrow, "source": "aria_voice"})

    print("=== Demo historical alerts (created then resolved - not left active) ===")
    for room in (R[3], R[8]):
        a = (await c.post("/alerts", json={"resident_id": res_ids[room], "severity": "assist",
                                           "message": "Demo - needed help to the bathroom", "triggered_by": "kiosk_button"})).json()
        if a.get("alert_id"):
            await c.post(f"/alerts/{a['alert_id']}/close", json={"outcome": "Demo - assisted, resolved", "close_notes": "demo history"})

    print("=== Menu (real ingestion + approve path, next 7 days) ===")
    for offset, (b, l, d) in enumerate(MENU_7D):
        day = (datetime.strptime(today_facility_date(), "%Y-%m-%d") + timedelta(days=offset)).strftime("%Y-%m-%d")
        body = f"Breakfast: {', '.join(b)}\nLunch: {', '.join(l)}\nDinner: {', '.join(d)}"
        up = (await c.post("/menu/ingest/dev-test", json={"service_date": day, "raw_text": body, "source_ref": "demo-community"})).json()
        if up.get("upload_id"):
            await c.post(f"/menu/uploads/{up['upload_id']}/approve")
        print(f"  {day}: dinner -> {d[0]}")

    print("\n=== Demo community ready. Residents 301-310, 6 demo staff, menu live. ===")


async def main():
    wipe_mode = "--wipe" in sys.argv
    headers = await _owner_headers()
    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=30.0) as c:
        if wipe_mode:
            await wipe(c)
        else:
            await seed(c)


if __name__ == "__main__":
    asyncio.run(main())
