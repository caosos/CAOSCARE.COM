"""Seed 10 realistic MOCK residents + kiosks for active system testing.

All fake/synthetic, clearly named "MOCK" so they're never confused with a
real resident. Creates one resident + one matching kiosk per room via the
same live endpoints the real Admin UI uses (POST /residents, POST
/kiosks) - not direct DB writes - so "Enter Room" works immediately for
each, same as any real resident. Rooms 401-410, distinct from the
existing TEST-1xx/2xx rooms and Chauncey's 304.

Run with: python3 scripts/seed_mock_residents.py
"""
import asyncio
import sys

import httpx

sys.path.insert(0, ".")
from routes.auth import _issue_jwt  # noqa: E402
from deps import db  # noqa: E402

BASE = "http://127.0.0.1:8000/api"

# Varied participation levels, preferences, and memory so Voice testing has
# real personality variety to work with - not 10 identical blank records.
RESIDENTS = [
    {"name": "MOCK Eleanor Whitfield", "preferred_name": "Ellie", "room": "401",
     "participation_level": "full",
     "preferences": "Big band music, crossword puzzles, her cat Whiskers back home",
     "memory": "Widowed 2018, husband Tom was a postman for 30 years. Two grandkids in Denver."},
    {"name": "MOCK Robert Castillo", "preferred_name": "Bobby", "room": "402",
     "participation_level": "pendant_enhanced",
     "preferences": "Baseball, especially the Cardinals, dominoes with the other guys",
     "memory": "Retired machinist. Diabetic, watches his sugar closely."},
    {"name": "MOCK Dorothy Nakamura", "preferred_name": "Dottie", "room": "403",
     "participation_level": "wearable_enhanced",
     "preferences": "Gardening, orchids especially, classical piano",
     "memory": "Former schoolteacher, taught 3rd grade for 35 years in Sacramento."},
    {"name": "MOCK Harold Jefferson", "preferred_name": "Harold", "room": "404",
     "participation_level": "family_connected",
     "preferences": "Fishing stories, old westerns, black coffee only",
     "memory": "Korean War veteran. Daughter Linda visits most Sundays."},
    {"name": "MOCK Ruth Ableman", "preferred_name": "Ruthie", "room": "405",
     "participation_level": "full",
     "preferences": "Knitting, mystery novels, her late husband's jazz records",
     "memory": "Married 52 years before losing her husband Sam last year."},
    {"name": "MOCK Walter Ochieng", "preferred_name": "Walt", "room": "406",
     "participation_level": "pendant_enhanced",
     "preferences": "Chess, documentaries, strong tea",
     "memory": "Immigrated from Kenya in the 1970s, worked as an engineer."},
    {"name": "MOCK Margaret Fiore", "preferred_name": "Maggie", "room": "407",
     "participation_level": "wearable_enhanced",
     "preferences": "Cooking shows, Italian recipes, her grandkids' visits",
     "memory": "Ran a family bakery for 40 years. Recently had a hip replacement."},
    {"name": "MOCK Clarence Boudreaux", "preferred_name": "Clarence", "room": "408",
     "participation_level": "full",
     "preferences": "Zydeco music, card games, spicy food when allowed",
     "memory": "From Louisiana originally. Loves telling stories about Mardi Gras."},
    {"name": "MOCK Patricia Lindqvist", "preferred_name": "Pat", "room": "409",
     "participation_level": "pendant_enhanced",
     "preferences": "Quilting, church hymns, watching the birds outside her window",
     "memory": "Widowed, one son in the Navy stationed overseas."},
    {"name": "MOCK Samuel Greenberg", "preferred_name": "Sam", "room": "410",
     "participation_level": "family_connected",
     "preferences": "Old radio shows, chess by mail, a good pastrami sandwich",
     "memory": "Retired accountant. Slightly hard of hearing, speaks loudly."},
]


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        print("=== Creating 10 MOCK residents + kiosks ===")
        created = []
        for r in RESIDENTS:
            payload = {**r, "pendant_id": f"pendant_mock_{r['room']}"}
            resp = await c.post("/residents", json=payload)
            resp.raise_for_status()
            resident = resp.json()
            kiosk_resp = await c.post("/kiosks", json={"name": r["room"], "room": r["room"], "zone": ""})
            kiosk_resp.raise_for_status()
            kiosk = kiosk_resp.json()
            print(f"  Room {r['room']}: {resident['name']} -> resident_id={resident['resident_id']} kiosk_id={kiosk['kiosk_id']}")
            created.append({"resident_id": resident["resident_id"], "room": r["room"], "name": r["name"]})

        print(f"\n=== Done: {len(created)} residents + kiosks created ===")
        for r in created:
            print(f"  {r['room']}: {r['name']} ({r['resident_id']})")


if __name__ == "__main__":
    asyncio.run(main())
