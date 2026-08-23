"""Admin-dashboard engagement seed (Terminal 8 follow-on): gives the
Requests board / department queues real, varied, ongoing activity for the
10 MOCK residents (rooms 401-410, created this round) so Michael can
actually test and improve the admin UI instead of looking at an empty
system.

Same style as scripts/seed_transportation_pilot.py: owner JWT auth via
routes.auth._issue_jwt, httpx.AsyncClient against the LIVE backend,
real endpoints only (POST /tasks/resident-request, POST /transportation/
request) - never a direct DB write for the domain flow, since these need
to go through the real category validation / dedup / receipt / provenance
logic.

Two constraints discovered while building this, worth recording:

1. Source value. The instruction that produced this script asked for
   source="mock_seed" so these are never confused with real Aria-voice or
   kiosk activity. That value does not exist: /tasks/resident-request
   hard-rejects any source other than "aria_voice"/"kiosk_button" (see
   routes/resident_requests.py), and StaffTask.source itself is a Literal
   of exactly ["staff","aria_voice","kiosk_button","family","system",
   "front_desk"] (models.py) - "mock_seed" 400s/500s either way. Adding a
   new literal value would mean editing models.py and the route's own
   validation, which is out of scope here (script-only change). Used the
   least-misrepresenting value available at each endpoint instead:
   "kiosk_button" for /tasks/resident-request (the only non-"aria_voice"
   option that route accepts - avoids the specific "spoken to Aria live"
   claim the instruction called out), and "system" for /transportation/
   request (accepted there, and an existing convention in models.py for
   automated/non-live task origin). Full traceability is still preserved
   via conversation_session_id = "mock_seed_<room>_<n>", which nothing
   else in the system generates.

2. created_at cannot be backdated through either endpoint - both always
   stamp now_utc() server-side with no override field, so a real "spread
   over the past 3 days" can't be produced without a direct DB write
   (explicitly out of scope for the domain flow). Instead: transportation
   requests genuinely span requested_for_date from 3 days ago to 4 days
   out (past ones are then marked completed via the real /transportation/
   request/{id}/complete endpoint, so they read as done, not stuck-open),
   and the resident-request tasks are pushed through a realistic mix of
   pending / acknowledged / in_progress / completed via the real
   /tasks/{id}/acknowledge, /start, /complete endpoints - so the queue
   shows genuine stage variety even though every row's created_at is
   "now" (the moment this script ran).

Run with: python3 scripts/seed_department_engagement.py
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
SESSION_PREFIX = "mock_seed_"

# (room, resident_id, [items]) - each item is either
#   ("help", category, resident_words, summary, priority)
# or
#   ("ride", purpose, day_offset, time_label, priority)
# Content is deliberately varied and realistic for a senior-care facility;
# no clock-time claims embedded in prose (operational_provenance.py
# rejects an unconfirmed time claim in summary/purpose text - only
# requested_for_date carries the actual date, exactly as intended).
RESIDENTS = [
    ("401", "res_0d3ef4252ae2", [
        ("help", "nursing", "Eleanor says her knees have been stiff today", "Resident reports stiff knees, would like a nurse to check on her", "normal"),
        ("help", "maintenance", "the reading lamp by her bed keeps flickering", "Reading lamp flickering, needs repair", "normal"),
        ("help", "housekeeping", "could she get fresh towels", "Requesting fresh towels", "normal"),
        ("help", "resident_programs", "she'd like to join the watercolor class", "Wants to sign up for the watercolor class this week", "normal"),
        ("ride", "doctor's appointment", -2, "9 in the morning", "normal"),
    ]),
    ("402", "res_3740a793edd7", [
        ("help", "maintenance", "the thermostat is stuck and it's too cold", "Thermostat stuck, room too cold", "high"),
        ("help", "kitchen", "he'd like decaf instead of regular going forward", "Requesting decaf coffee instead of regular going forward", "normal"),
        ("help", "front_desk", "he has a question about a charge on his last statement", "Question about a charge on his last billing statement", "normal"),
        ("help", "therapy", "he wants to talk about rescheduling physical therapy", "Wants to discuss rescheduling his physical therapy session", "normal"),
        ("help", "complaint", "dinner has been arriving cold the last couple nights", "Complaint: dinner arriving cold the last couple of nights", "normal"),
        ("ride", "pharmacy pickup", 1, "9 in the morning", "normal"),
    ]),
    ("403", "res_796de5d588c3", [
        ("help", "resident_programs", "Dorothy would like to join the garden club", "Wants to join the garden club meeting", "normal"),
        ("help", "nursing", "some swelling in her ankles", "Resident reports ankle swelling, would like a nurse to take a look", "normal"),
        ("help", "housekeeping", "her wastebasket hasn't been emptied in a few days", "Wastebasket has not been emptied in a few days", "normal"),
        ("help", "maintenance", "the window in her room won't close all the way", "Window will not close all the way", "normal"),
        ("ride", "hair salon appointment", 2, "1 in the afternoon", "normal"),
    ]),
    ("404", "res_d9129c7d1f46", [
        ("help", "nursing", "Harold would like help getting dressed this morning", "Resident would like help getting dressed", "normal"),
        ("help", "maintenance", "the bathroom faucet is leaking", "Bathroom faucet leaking, needs repair", "normal"),
        ("help", "maintenance", "the faucet is still leaking, nobody's been by yet", "Bathroom faucet still leaking, asked again", "normal"),
        ("help", "kitchen", "he asked for a bit more variety at breakfast", "Would like more variety at breakfast", "low"),
        ("help", "front_desk", "he wants to know if a package has arrived for him", "Asking whether a package has arrived for him", "normal"),
        ("ride", "doctor's appointment", -3, "9 in the morning", "normal"),
    ]),
    ("405", "res_a7c0919ac67c", [
        ("help", "nursing", "Ruth is very uncomfortable in her chair and wants help repositioning", "Resident uncomfortable in her chair, would like help repositioning as soon as possible", "urgent"),
        ("help", "housekeeping", "her bed linens need to be changed", "Bed linens need to be changed", "normal"),
        ("help", "resident_programs", "Ruth wants to join the afternoon music session", "Wants to join the afternoon music session", "normal"),
        ("help", "complaint", "Ruth felt the aide was short with her yesterday", "Resident felt an aide was short with her yesterday, would like a follow-up", "high"),
        ("ride", "family visit", 3, "2 in the afternoon", "normal"),
    ]),
    ("406", "res_904689afc864", [
        ("help", "maintenance", "no hot water in the shower this morning", "No hot water in the shower this morning", "urgent"),
        ("help", "nursing", "Walter has a question about his next medication dose", "Resident has a question about the timing of his next medication dose", "normal"),
        ("help", "kitchen", "he'd like a lower sodium option at meals", "Requesting a lower sodium meal option", "normal"),
        ("help", "therapy", "he wants to confirm he's still on the schedule this week", "Wants to confirm he is still scheduled for physical therapy this week", "normal"),
        ("ride", "trip to the bank", -1, "11 in the morning", "normal"),
    ]),
    ("407", "res_eb052acb132c", [
        ("help", "housekeeping", "Margaret's room needs vacuuming", "Room needs vacuuming", "normal"),
        ("help", "maintenance", "the TV in her room isn't turning on", "TV will not turn on", "normal"),
        ("help", "front_desk", "she'd like to update her emergency contact", "Wants to speak with someone about updating her emergency contact", "normal"),
        ("help", "resident_programs", "Margaret wants to join the book club", "Wants to join the book club", "low"),
        ("ride", "doctor's appointment", 4, "10 in the morning", "normal"),
    ]),
    ("408", "res_632377728960", [
        ("help", "kitchen", "the food has been too bland lately", "Food has been too bland lately, would like more seasoning", "normal"),
        ("help", "complaint", "his call light took a while to be answered yesterday", "Frustrated that his call light took a while to be answered yesterday", "high"),
        ("help", "nursing", "Clarence would like his blood pressure checked", "Would like a blood pressure check", "normal"),
        ("help", "maintenance", "the closet door in his room is stuck", "Closet door stuck, needs repair", "normal"),
        ("ride", "pharmacy pickup", -3, "in the early morning", "normal"),
    ]),
    ("409", "res_5e00caaaa1ca", [
        ("help", "resident_programs", "Patricia would like to join the card games group", "Wants to join the card games group", "normal"),
        ("help", "housekeeping", "she'd like extra blankets brought to her room", "Requesting extra blankets", "normal"),
        ("help", "nursing", "feeling a little dizzy when standing up", "Resident reports feeling a little dizzy when standing up, would like a nurse to check on her", "high"),
        ("help", "front_desk", "she has a question about a delivery she's expecting", "Question about an expected delivery", "normal"),
        ("ride", "hair salon appointment", 1, "1 in the afternoon", "normal"),
    ]),
    ("410", "res_0dda77e0de0b", [
        ("help", "maintenance", "the reading light in his room flickers on and off", "Reading light flickers on and off, needs repair", "normal"),
        ("help", "maintenance", "the light is still flickering", "Reading light still flickering, asked again", "normal"),
        ("help", "kitchen", "Samuel asked if he could get a snack between meals", "Would like a snack between meals", "normal"),
        ("help", "therapy", "he wants to ask about his exercise plan", "Has a question about his exercise plan", "normal"),
        ("help", "complaint", "his room wasn't cleaned properly this week", "Feels his room was not cleaned properly this week", "normal"),
        ("ride", "doctor's appointment", 0, "3 in the afternoon", "normal"),
    ]),
]


def day(offset: int) -> str:
    return (datetime.fromisoformat(today_facility_date()) + timedelta(days=offset)).strftime("%Y-%m-%d")


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    created, duplicates, rejections = [], [], []

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        for room, resident_id, items in RESIDENTS:
            for n, item in enumerate(items, start=1):
                session_id = f"{SESSION_PREFIX}{room}_{n}"
                kind = item[0]
                if kind == "help":
                    _, category, words, summary, priority = item
                    resp = await c.post("/tasks/resident-request", json={
                        "category": category, "resident_id": resident_id, "room": room,
                        "resident_words": words, "summary": summary, "priority": priority,
                        "source": "kiosk_button", "conversation_session_id": session_id,
                    })
                else:
                    _, purpose, offset, time_label, priority = item
                    resp = await c.post("/transportation/request", json={
                        "resident_id": resident_id, "room": room, "purpose": purpose,
                        "requested_for_date": day(offset), "requested_for_time_label": time_label,
                        "priority": priority, "source": "system", "conversation_session_id": session_id,
                    })

                if resp.status_code != 200:
                    rejections.append((room, session_id, resp.status_code, resp.text))
                    print(f"  REJECTED {room}/{session_id}: {resp.status_code} {resp.text}")
                    continue

                result = resp.json()
                if result.get("duplicate"):
                    duplicates.append((room, session_id, result))
                    print(f"  DUP {room}/{session_id}: re_request_count={result.get('re_request_count')}")
                    continue

                task_id = result["task_id"]
                created.append((room, session_id, kind, task_id))
                print(f"  OK {room}/{session_id} -> {task_id}")

                if kind == "ride" and item[2] < 0:
                    # Past-dated ride: mark it as having actually happened
                    # rather than leaving a phantom "still pending" ride.
                    comp = await c.post(f"/transportation/request/{task_id}/complete")
                    if comp.status_code != 200:
                        rejections.append((room, session_id, comp.status_code, comp.text))
                elif kind == "help":
                    # Spread queue state so the board shows genuine stage
                    # variety (pending / acknowledged / in_progress /
                    # completed), not a wall of identical fresh rows.
                    stage = len(created) % 4
                    if stage == 1:
                        await c.post(f"/tasks/{task_id}/acknowledge")
                    elif stage == 2:
                        await c.post(f"/tasks/{task_id}/start")
                    elif stage == 3:
                        await c.post(f"/tasks/{task_id}/start")
                        await c.post(f"/tasks/{task_id}/complete")

        print("\n=== SUMMARY ===")
        print(f"  created: {len(created)}  duplicates(re-requests): {len(duplicates)}  rejections: {len(rejections)}")
        if rejections:
            print("  !! rejections detail:")
            for r in rejections:
                print("    ", r)

        print("\n=== DEPARTMENT / CATEGORY BREAKDOWN (mock_seed_ tasks only) ===")
        pipeline = [
            {"$match": {"conversation_session_id": {"$regex": f"^{SESSION_PREFIX}"}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}, "statuses": {"$push": "$status"}}},
            {"$sort": {"_id": 1}},
        ]
        total = 0
        async for row in db.staff_tasks.aggregate(pipeline):
            statuses = row["statuses"]
            status_counts = {s: statuses.count(s) for s in set(statuses)}
            total += row["count"]
            print(f"  {row['_id']:<18} {row['count']:>3}   {status_counts}")
        print(f"  TOTAL distinct tasks: {total}")


if __name__ == "__main__":
    asyncio.run(main())
