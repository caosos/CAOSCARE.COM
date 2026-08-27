"""Seed today's facility-note announcements + a same-day activity, through
the existing schedule domain (ScheduleItem, category="facility_note" for
building notices vs. "activity" for events) - NOT a new domain. Inspection
of models.py/schedule.py showed ScheduleCategory already has "facility_note"
and get_todays_schedule() already answers "what's going on today" from
whatever category is on file; two weeks of future schedule data already
exist with facility_note entries, but today itself had none. This just
fills that one gap through the same live POST /schedule endpoint the
Admin UI uses (not a direct DB write) - facility-scoped (single active
facility, per today_facility_date()), dated to today, tagged created_by
the seeding owner account and source="staff_entry" (the same provenance
any real staff-entered notice carries - ScheduleItemCreate has no
separate field for seed data, and inventing one for this alone would be
a schema change well past what this gap needs). Idempotent - skips a
title already on file for today.

Run with: python3 scripts/seed_demo_announcements.py
"""
import asyncio
import sys

import httpx

sys.path.insert(0, ".")
from routes.auth import _issue_jwt  # noqa: E402
from routes.realtime_facility import today_facility_date  # noqa: E402
from deps import db  # noqa: E402

BASE = "http://127.0.0.1:8000/api"

ANNOUNCEMENTS = [
    {"time_label": "All day", "title": "Elevator B out of service",
     "description": "Maintenance is working on Elevator B today - please use Elevator A or the stairs near the Dining Room.",
     "category": "facility_note"},
    {"time_label": "5:00 PM", "title": "Dinner moved to the Sunroom",
     "description": "Dining Room floors are being cleaned this evening - dinner service is in the Sunroom instead.",
     "category": "facility_note"},
    {"time_label": "3:00 PM", "title": "Ice Cream Social",
     "description": "Sundae bar in the Courtyard, weather permitting.",
     "category": "activity"},
]


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}
    today = today_facility_date()

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        existing_titles = {
            i["title"] for i in (await c.get("/schedule", params={"date": today})).json()
        }
        created, skipped = 0, 0
        for a in ANNOUNCEMENTS:
            if a["title"] in existing_titles:
                skipped += 1
                continue
            resp = await c.post("/schedule", json={**a, "date": today})
            resp.raise_for_status()
            print(f"  [{a['category']}] {a['title']} ({today})")
            created += 1
        print(f"\n=== Done: {created} announcements seeded for {today}, {skipped} already on file ===")


if __name__ == "__main__":
    asyncio.run(main())
