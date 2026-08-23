"""Two-week menu seed script (Terminal 8, menu lane).

Exercises the REAL kitchen-email ingestion pathway against the LIVE running
backend - not a shortcut, not a direct DB write. For each of the next 14
facility-local days (today_facility_date() + 0 .. +13) this builds ONE
simulated inbound kitchen email (the same shape a real IMAP/webhook adapter
would eventually hand to routes/menu_ingest.py: a plain-text body with
Breakfast:/Lunch:/Dinner: section headers) and POSTs it to
/api/menu/ingest/dev-test, then immediately POSTs to
/api/menu/uploads/{upload_id}/approve so the batch clears the approval gate
and becomes visible to residents/Aria via /api/menu/public/today.

Content is realistic senior-facility fare with a weekly-ish rotation
(meatloaf Mondays, fish Fridays, roast Sundays) but no two days are
identical - see MEALS below.

Run with (from backend/):
    .venv/bin/python3 scripts/seed_menu_two_weeks.py
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

# 14 days of (breakfast, lunch, dinner) items. Real variety with a
# recognizable weekly pattern (meatloaf Mon, fish Fri, roast Sun) but no
# exact repeats across the two weeks.
MEALS = [
    # Week 1
    (["Scrambled Eggs", "Turkey Bacon", "Wheat Toast", "Orange Juice"],
     ["Chicken Noodle Soup", "Turkey Sandwich", "Coleslaw"],
     ["Meatloaf", "Mashed Potatoes", "Green Beans", "Dinner Roll"]),
    (["Oatmeal with Brown Sugar", "Sausage Links", "Sliced Banana"],
     ["Grilled Cheese", "Tomato Soup", "Apple Sauce"],
     ["Baked Chicken Thighs", "Rice Pilaf", "Steamed Carrots"]),
    (["Buttermilk Pancakes", "Maple Syrup", "Scrambled Eggs", "Fresh Fruit Cup"],
     ["Beef Barley Soup", "Egg Salad Sandwich", "Pickle Spear"],
     ["Salisbury Steak", "Mashed Potatoes", "Peas and Carrots", "Dinner Roll"]),
    (["French Toast", "Turkey Sausage", "Orange Slices"],
     ["Chicken Caesar Salad", "Dinner Roll", "Fruit Cocktail"],
     ["Roast Pork Loin", "Sweet Potatoes", "Green Beans"]),
    (["Cheese Omelet", "Hash Browns", "Wheat Toast"],
     ["New England Clam Chowder", "Grilled Cheese", "Coleslaw"],
     ["Baked Cod", "Rice Pilaf", "Steamed Broccoli", "Lemon Wedge"]),
    (["Belgian Waffles", "Bacon", "Mixed Berries"],
     ["Chicken Salad Sandwich", "Vegetable Soup", "Potato Chips"],
     ["Roast Turkey", "Stuffing", "Mashed Potatoes", "Cranberry Sauce"]),
    (["Biscuits and Sausage Gravy", "Scrambled Eggs", "Fresh Fruit Cup"],
     ["Ham and Swiss Sandwich", "Macaroni Salad", "Sliced Peaches"],
     ["Pot Roast", "Roasted Potatoes", "Glazed Carrots", "Dinner Roll"]),
    # Week 2
    (["Scrambled Eggs", "Diced Ham", "Wheat Toast", "Apple Juice"],
     ["Split Pea Soup", "Turkey Club Sandwich", "Carrot Sticks"],
     ["Meatloaf with Gravy", "Garlic Mashed Potatoes", "Steamed Broccoli", "Dinner Roll"]),
    (["Cream of Wheat", "Turkey Sausage", "Sliced Banana"],
     ["Grilled Chicken Wrap", "Minestrone Soup", "Fresh Fruit Cup"],
     ["Chicken and Dumplings", "Buttered Corn", "Dinner Roll"]),
    (["Blueberry Pancakes", "Scrambled Eggs", "Sausage Links"],
     ["Tuna Salad Sandwich", "Tomato Basil Soup", "Coleslaw"],
     ["Salisbury Steak with Mushroom Gravy", "Rice Pilaf", "Green Beans"]),
    (["French Toast Sticks", "Bacon", "Orange Juice"],
     ["Cobb Salad", "Dinner Roll", "Fruit Cup"],
     ["Herb Roasted Chicken", "Sweet Potato Mash", "Buttered Peas"]),
    (["Veggie Omelet", "Hash Browns", "Wheat Toast"],
     ["New England Clam Chowder", "Egg Salad Sandwich", "Pickle Spear"],
     ["Lemon Baked Tilapia", "Wild Rice", "Steamed Asparagus"]),
    (["Buttermilk Waffles", "Turkey Bacon", "Mixed Berries"],
     ["BLT Sandwich", "Vegetable Beef Soup", "Potato Salad"],
     ["Roast Turkey Breast", "Mashed Potatoes", "Green Bean Casserole", "Cranberry Sauce"]),
    (["Sausage Gravy and Biscuits", "Scrambled Eggs", "Fresh Fruit Cup"],
     ["Roast Beef Sandwich", "Macaroni Salad", "Sliced Peaches"],
     ["Sunday Pot Roast", "Roasted Red Potatoes", "Honey Glazed Carrots", "Dinner Roll"]),
]


def day(offset: int) -> str:
    return (datetime.fromisoformat(today_facility_date()) + timedelta(days=offset)).strftime("%Y-%m-%d")


def build_email(breakfast: list, lunch: list, dinner: list) -> str:
    """Builds a raw plain-text body shaped like a real inbound kitchen
    email, matching the section-header format menu_ingest.py's parser
    expects (Breakfast:/Lunch:/Dinner: headers, comma-separated items)."""
    return (
        "Breakfast:\n" + ", ".join(breakfast) + "\n\n"
        "Lunch:\n" + ", ".join(lunch) + "\n\n"
        "Dinner:\n" + ", ".join(dinner) + "\n"
    )


async def main():
    owner = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    token = _issue_jwt(owner["user_id"])
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=15.0) as c:
        print("=== Seeding 14 days of menu via kitchen-email ingestion ===")
        seeded_dates = []
        total_items = 0

        for offset, (breakfast, lunch, dinner) in enumerate(MEALS):
            service_date = day(offset)
            raw_text = build_email(breakfast, lunch, dinner)

            ingest_resp = await c.post("/menu/ingest/dev-test", json={
                "service_date": service_date,
                "raw_text": raw_text,
                "source_ref": f"kitchen@example-facility.test msg-{service_date}",
            })
            ingest_resp.raise_for_status()
            upload = ingest_resp.json()
            parse_status = upload.get("parse_status")
            upload_id = upload["upload_id"]
            item_count = len(upload.get("item_ids", []))

            if parse_status != "parsed":
                print(f"  Day {offset + 1} ({service_date}): parse_status={parse_status} "
                      f"notes={upload.get('parse_notes')!r} -- SKIPPING APPROVAL")
                continue

            approve_resp = await c.post(f"/menu/uploads/{upload_id}/approve")
            approve_resp.raise_for_status()
            approved = approve_resp.json()

            seeded_dates.append(service_date)
            total_items += item_count
            print(f"  Day {offset + 1} ({service_date}): parsed+approved, "
                  f"upload_id={upload_id}, items={item_count}, status={approved.get('status')}")

        print(f"\n=== Seeded {len(seeded_dates)}/14 days, {total_items} total menu items ===")

        print("\n=== Verification: GET /menu/public/today for several dates ===")
        check_offsets = [0, 3, 7, 10, 13]
        async with httpx.AsyncClient(base_url=BASE, timeout=15.0) as anon:
            for offset in check_offsets:
                service_date = day(offset)
                resp = await anon.get("/menu/public/today", params={"date": service_date})
                resp.raise_for_status()
                items = resp.json()
                meals_present = sorted({i["meal_period"] for i in items})
                print(f"  {service_date} (day {offset + 1}): {len(items)} approved items, "
                      f"meals={meals_present}")
                for i in items:
                    print(f"      [{i['meal_period']}] {i['item_name']}")


if __name__ == "__main__":
    asyncio.run(main())
