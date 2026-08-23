"""Transportation pilot seed + acceptance test script (Terminal 8).

Exercises the full transportation lane against the LIVE running backend
(not a mock, not direct DB writes for the request flow) - creates 5
obviously-synthetic TEST residents/rooms, seeds a 2-week availability
schedule, and runs realistic request/change/cancel/complete/no-slot/
re-request/concurrency scenarios exactly as a real conversation would
generate them. This is TEST/DEVELOPMENT DATA - every resident is prefixed
"TEST" and is meant to be left in place afterward so the daily report has
something real to show, per the pilot's own purpose (see
docs/TERMINAL_8_OPERATIONAL_LAYER.md for the full write-up).

Run with: python3 scripts/seed_transportation_pilot.py
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


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        print("=== Creating 5 TEST residents/rooms ===")
        rooms = [
            ("TEST Room 101 (Node A)", "TEST-101"), ("TEST Room 102 (Node B)", "TEST-102"),
            ("TEST Room 103 (Node C)", "TEST-103"), ("TEST Room 201 (Node D)", "TEST-201"),
            ("TEST Room 202 (Node E)", "TEST-202"),
        ]
        residents = {}
        for name, room in rooms:
            r = await c.post("/residents", json={"name": name, "room": room, "pendant_id": f"pendant_{room}"})
            r.raise_for_status()
            residents[room] = r.json()["resident_id"]
            print(f"  {room} -> {residents[room]}")

        print("=== Seeding 2-week transportation schedule ===")
        r = await c.post("/transportation/slots/seed-two-weeks")
        print(" ", r.json())

        results = {}

        async def request(room, purpose, d, time_label, start_time=None):
            resp = await c.post("/transportation/request", json={
                "resident_id": residents[room], "room": room, "purpose": purpose,
                "requested_for_date": d, "requested_for_time_label": time_label,
                "start_time": start_time, "source": "aria_voice",
            })
            return resp.json()

        print("\n=== A: TEST Room 101 - pharmacy ride tomorrow at 10 ===")
        a = await request("TEST-101", "pharmacy pickup", day(1), "10 in the morning", "10:00")
        print(" ", a)
        results["A"] = a

        print("\n=== B (concurrency): Room 102 vs Room 103 race for the SAME slot (day+3 14:00) ===")
        b1, b2 = await asyncio.gather(
            request("TEST-102", "doctor appointment", day(3), "2 in the afternoon", "14:00"),
            request("TEST-103", "doctor appointment", day(3), "2 in the afternoon", "14:00"),
        )
        booked_count = sum(1 for x in (b1, b2) if x.get("booked"))
        print("  Room 102:", b1)
        print("  Room 103:", b2)
        print(f"  >>> exactly one booked: {booked_count == 1} (booked_count={booked_count})")
        results["B_concurrency_exactly_one_booked"] = booked_count == 1

        print("\n=== C: Room 101 - 'change mine to 2 PM' ===")
        c_resp = await c.post("/transportation/request/change-mine", json={
            "resident_id": residents["TEST-101"], "requested_for_date": day(1),
            "requested_for_time_label": "2 in the afternoon", "start_time": "14:00",
        })
        c_result = c_resp.json()
        print(" ", c_result)
        results["C"] = c_result

        print("\n=== D: Room 101 - 'cancel my ride' ===")
        d_resp = await c.post("/transportation/request/cancel-mine", json={"resident_id": residents["TEST-101"]})
        d_result = d_resp.json()
        print(" ", d_result)
        results["D"] = d_result

        print("\n=== Additional synthetic activity across the 2 weeks ===")
        e1 = await request("TEST-201", "grocery shopping", day(2), "1 in the afternoon", "13:00")
        print("  Room 201 grocery:", e1)
        e2 = await request("TEST-202", "bank", day(7), "9 in the morning", "09:00")
        print("  Room 202 bank:", e2)
        e3 = await request("TEST-202", "hair appointment", day(6), "9 in the morning", "09:00")
        print("  Room 202 hair (grabs day+6 09:00 first):", e3)
        e4 = await request("TEST-103", "family visit", day(6), "9 in the morning", "09:00")
        print("  Room 103 family visit, SAME slot as Room 202's hair appt (should be no-slot):", e4)
        e5 = await request("TEST-103", "family visit", day(6), "9 in the morning", "09:00")
        print("  Room 103 asks AGAIN for the same day (should be duplicate/re-request):", e5)
        results["no_slot_declined"] = (e4.get("booked") is False and not e4.get("duplicate"))
        results["re_request_detected"] = bool(e5.get("duplicate"))

        print("\n=== Staff marks Room 201's grocery ride completed ===")
        complete_resp = await c.post(f"/transportation/request/{e1['task_id']}/complete")
        print(" ", complete_resp.json())

        print("\n=== E/F: Daily report for today ===")
        report = (await c.get("/transportation/report", params={"date": today_facility_date()})).json()
        print(f"  inbound: {len(report['inbound'])}")
        print(f"  outbound actions: {len(report['outbound'])}")
        print(f"  summary: {report['summary']}")
        print(f"  current_state: upcoming={len(report['current_state']['upcoming_rides'])} "
              f"waiting={len(report['current_state']['waiting_unbooked'])} "
              f"follow_ups={len(report['current_state']['follow_ups_required'])}")

        print("\n=== ACCEPTANCE CHECKS ===")
        print(f"  A booked=true: {'PASS' if results['A'].get('booked') else 'FAIL'}")
        print(f"  B concurrency - exactly one booked: {'PASS' if results['B_concurrency_exactly_one_booked'] else 'FAIL'}")
        print(f"  C changed + booked at new time: {'PASS' if results['C'].get('booked') else 'FAIL'}")
        print(f"  D cancelled: {'PASS' if results['D'].get('status') == 'skipped' else 'FAIL'}")
        print(f"  No-slot declined correctly: {'PASS' if results['no_slot_declined'] else 'FAIL'}")
        print(f"  Re-request detected: {'PASS' if results['re_request_detected'] else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
