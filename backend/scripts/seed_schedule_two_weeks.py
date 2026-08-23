"""Resident-programs/activities calendar seed script (Terminal 8), matching
the "simulated inbound department email, not direct data entry" pattern
Michael asked for - the same way seed_transportation_pilot.py exercises the
transportation lane against the LIVE running backend.

Simulates the activities coordinator emailing in two consecutive weekly
calendars (14 days total, starting today) as raw email bodies, POSTed to
POST /schedule/ingest/dev-test (backend/routes/schedule_ingest.py) exactly
as a real inbound-email adapter eventually would deliver them. Each
ScheduleItem this produces is real, varied, live data - not placeholder
copy-pasted per day - and lands via the real parse -> create path, not a
direct DB write, so it's also a live acceptance test of the ingestion
endpoint itself.

Run with: python3 scripts/seed_schedule_two_weeks.py
(Only works once schedule_ingest_routes.router is registered in server.py
and the backend has been restarted - see the TODO in server.py.)
"""
import asyncio
import sys
from datetime import datetime, timedelta

import httpx

sys.path.insert(0, ".")
from routes.auth import _issue_jwt  # noqa: E402
from routes.realtime_facility import today_facility_date  # noqa: E402
from deps import db  # noqa: E402

BASE = "http://127.0.0.1:8000/api"


def day(offset: int) -> str:
    return (datetime.fromisoformat(today_facility_date()) + timedelta(days=offset)).strftime("%Y-%m-%d")


def weekday_name(offset: int) -> str:
    return (datetime.fromisoformat(today_facility_date()) + timedelta(days=offset)).strftime("%A")


# 14 days of varied, realistic senior-facility programming. Each entry is a
# list of (time_label, title, description, category) tuples for that day -
# real variety day to day, not the same activities repeated.
DAY_PLANS = [
    [  # day 0
        ("9:00 AM", "Chair Yoga", "Gentle stretching and mobility work, all levels welcome, Sunroom", "activity"),
        ("2:00 PM", "Bingo", "Prizes provided, Main Activity Room", "activity"),
    ],
    [  # day 1
        ("10:30 AM", "Hymn Sing", "Led by Chaplain Ruiz, Chapel", "activity"),
        ("1:00 PM", "Book Club", '"The Guernsey Literary and Potato Peel Pie Society", Library', "activity"),
        ("3:30 PM", "Art Therapy", "Watercolor painting, materials provided, Craft Room", "activity"),
    ],
    [  # day 2
        ("10:00 AM", "Gardening Club", "Raised-bed planting, courtyard garden", "activity"),
        ("2:30 PM", "Live Music Afternoon", "Local guitarist Sam Alvarez, Main Activity Room", "activity"),
    ],
    [  # day 3
        ("9:00 AM", "Chair Yoga", "Gentle stretching and mobility work, all levels welcome, Sunroom", "activity"),
        ("11:00 AM", "Cooking Demo", "No-bake summer desserts, Dining Room", "activity"),
        ("6:00 PM", "Movie Night", '"Singin\' in the Rain", popcorn served, Theater Room', "activity"),
    ],
    [  # day 4
        ("1:00 PM", "Birthday Celebration", "Cake and punch for August birthdays, Dining Room", "activity"),
        ("3:00 PM", "Family Visiting Hours", "Extended visiting window, all common areas", "facility_note"),
    ],
    [  # day 5
        ("10:00 AM", "Scenic Drive", "Van tour along the riverfront, sign up at the front desk", "activity"),
        ("2:00 PM", "Trivia Hour", "Team trivia with prizes, Main Activity Room", "activity"),
    ],
    [  # day 6
        ("10:30 AM", "Hymn Sing", "Led by Chaplain Ruiz, Chapel", "activity"),
        ("1:30 PM", "Ice Cream Social", "Sundae bar, Courtyard (weather permitting)", "activity"),
        ("5:00 PM", "Reduced weekend staffing", "Two aides on floor overnight, per usual weekend schedule", "staff_hours"),
    ],
    [  # day 7
        ("9:00 AM", "Chair Yoga", "Gentle stretching and mobility work, all levels welcome, Sunroom", "activity"),
        ("2:00 PM", "Bingo", "Prizes provided, Main Activity Room", "activity"),
        ("4:00 PM", "Pet Therapy Visit", "Certified therapy dogs from Riverside Pet Partners, Sunroom", "activity"),
    ],
    [  # day 8
        ("10:00 AM", "Resident Council Meeting", "Monthly open meeting, all residents welcome, Library", "facility_note"),
        ("1:00 PM", "Book Club", '"The Guernsey Literary and Potato Peel Pie Society" - discussion, Library', "activity"),
    ],
    [  # day 9
        ("10:00 AM", "Gardening Club", "Watering and weeding, courtyard garden", "activity"),
        ("2:30 PM", "Art Therapy", "Clay sculpting, materials provided, Craft Room", "activity"),
    ],
    [  # day 10
        ("9:00 AM", "Chair Yoga", "Gentle stretching and mobility work, all levels welcome, Sunroom", "activity"),
        ("11:30 AM", "Cooking Demo", "Fresh salsa and guacamole, Dining Room", "activity"),
        ("6:00 PM", "Movie Night", '"Casablanca", popcorn served, Theater Room', "activity"),
    ],
    [  # day 11
        ("2:00 PM", "Live Music Afternoon", "Duo performing jazz standards, Main Activity Room", "activity"),
        ("3:00 PM", "Family Visiting Hours", "Extended visiting window, all common areas", "facility_note"),
    ],
    [  # day 12
        ("10:00 AM", "Scenic Drive", "Van tour of the botanical gardens, sign up at the front desk", "activity"),
        ("1:30 PM", "Birthday Celebration", "Cake and punch for late-August birthdays, Dining Room", "activity"),
    ],
    [  # day 13
        ("10:30 AM", "Hymn Sing", "Led by Chaplain Ruiz, Chapel", "activity"),
        ("1:00 PM", "Trivia Hour", "Team trivia with prizes, Main Activity Room", "activity"),
        ("5:00 PM", "Reduced weekend staffing", "Two aides on floor overnight, per usual weekend schedule", "staff_hours"),
    ],
]


def _build_week_email(day_offsets: list[int]) -> str:
    """Builds one raw email body covering the given days, in the exact
    format schedule_ingest.py expects: 'Weekday YYYY-MM-DD:' header per
    day, then one activity line per entry."""
    lines = []
    for offset in day_offsets:
        lines.append(f"{weekday_name(offset)} {day(offset)}:")
        for time_label, title, description, category in DAY_PLANS[offset]:
            tag = f" [{category}]" if category != "activity" else ""
            lines.append(f"{time_label} {title} - {description}{tag}")
        lines.append("")  # blank line between days, matches the documented format
    return "\n".join(lines)


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        print("=== Week 1 activities calendar email (days 0-6) ===")
        week1_text = _build_week_email(list(range(0, 7)))
        print(week1_text)
        r1 = await c.post("/schedule/ingest/dev-test", json={
            "raw_text": week1_text, "source_ref": "activities-coordinator-week1-dev-test",
        })
        r1.raise_for_status()
        res1 = r1.json()
        print(f"  created_count={res1['created_count']} skipped_lines={res1['skipped_lines']} notes={res1['notes']}")

        print("\n=== Week 2 activities calendar email (days 7-13) ===")
        week2_text = _build_week_email(list(range(7, 14)))
        print(week2_text)
        r2 = await c.post("/schedule/ingest/dev-test", json={
            "raw_text": week2_text, "source_ref": "activities-coordinator-week2-dev-test",
        })
        r2.raise_for_status()
        res2 = r2.json()
        print(f"  created_count={res2['created_count']} skipped_lines={res2['skipped_lines']} notes={res2['notes']}")

        expected = sum(len(plan) for plan in DAY_PLANS)
        actual = res1["created_count"] + res2["created_count"]

        print("\n=== ACCEPTANCE CHECKS ===")
        print(f"  Expected {expected} activities created across 14 days, got {actual}: "
              f"{'PASS' if actual == expected else 'FAIL'}")
        print(f"  No skipped/unparseable lines: "
              f"{'PASS' if not res1['skipped_lines'] and not res2['skipped_lines'] else 'FAIL'}")

        print("\n=== Verifying via GET /schedule/public/today ===")
        today_public = (await c.get("/schedule/public/today")).json()
        print(f"  {len(today_public)} item(s) visible for today: {today_public}")


if __name__ == "__main__":
    asyncio.run(main())
