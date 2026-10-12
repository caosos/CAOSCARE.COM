"""careops-dining-dietary-allergen-truth-001: a menu item carries staff-entered
`dietary_labels` and `allergens` ("contains") on the same MenuItem. They are
normalized (trimmed, whitespace collapsed, case-insensitively de-duplicated,
first spelling kept), bounded (12 per list, 40 characters each, plain
characters only - otherwise refused), carried through draft, publish and
correction, receipted, and repeated verbatim to residents/Aria by
/menu/public/today - nothing is added or inferred (no "safe", no "free of").
In-process, DB-direct; scratch DB only.
"""
import asyncio
import os
import sys
import uuid

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import MenuItemCreate, MenuItemUpdate, normalize_menu_labels  # noqa: E402


def test_labels_are_normalized_and_deduplicated():
    assert normalize_menu_labels(["  Gluten   free ", "gluten free", "Vegetarian", "", "  "]) == ["Gluten free", "Vegetarian"]
    assert normalize_menu_labels(None) is None
    assert normalize_menu_labels([]) == []
    item = MenuItemCreate(date="2031-03-05", meal_period="lunch", item_name="Soup",
                          dietary_labels=["Low sodium"], allergens=["Milk", "MILK", " tree  nuts "])
    assert item.dietary_labels == ["Low sodium"] and item.allergens == ["Milk", "tree nuts"]
    assert MenuItemCreate(date="2031-03-05", meal_period="lunch", item_name="Soup").allergens == []
    assert MenuItemUpdate().allergens is None   # absent on an edit = unchanged


@pytest.mark.parametrize("bad", [["x" * 41], [f"label {i}" for i in range(13)], ["<b>milk</b>"], ["milk; drop"]])
def test_out_of_bounds_labels_are_refused(bad):
    with pytest.raises(ValidationError):
        MenuItemCreate(date="2031-03-05", meal_period="lunch", item_name="Soup", allergens=bad)
    with pytest.raises(ValidationError):
        MenuItemUpdate(dietary_labels=bad)


def _db_ready():
    return os.environ.get("DB_NAME") not in ("caoscare", "", None)


TAG = f"mdl_{uuid.uuid4().hex[:8]}"
DAY = "2031-03-05"   # a synthetic future day nothing else uses
COOK = {"user_id": f"{TAG}_cook", "name": "Cook", "role": "staff", "department": "kitchen"}
NURSE = {"user_id": f"{TAG}_nurse", "name": "Nurse", "role": "staff", "department": "nursing"}


async def _scenario():
    from fastapi import HTTPException
    from deps import db
    from routes import menu

    await db.menu_items.delete_many({"date": DAY})
    try:
        v1 = (await menu.create_menu_item(MenuItemCreate(date=DAY, meal_period="lunch", item_name="Mac and cheese",
                                                         dietary_labels=["Vegetarian"], allergens=["Milk", "Wheat"]),
                                          user=COOK))["menu_id"]
        draft = await db.menu_items.find_one({"menu_id": v1})
        assert draft["dietary_labels"] == ["Vegetarian"] and draft["allergens"] == ["Milk", "Wheat"]
        assert await menu.public_today(date=DAY) == [], "a draft's labels are not shown to residents"

        await menu.approve_menu_item(v1, user=COOK)
        pub = await menu.public_today(date=DAY)
        assert pub == [{"meal_period": "lunch", "item_name": "Mac and cheese", "description": "", "availability": None,
                        "dietary_labels": ["Vegetarian"], "allergens": ["Milk", "Wheat"]}], pub

        # a correction that does not touch the labels carries them forward
        c1 = await menu.update_menu_item(v1, MenuItemUpdate(description="baked", publish=True), user=COOK)
        assert c1["dietary_labels"] == ["Vegetarian"] and c1["allergens"] == ["Milk", "Wheat"]
        # a correction of the labels is a new version; the superseded one keeps what it said
        c2 = await menu.update_menu_item(c1["menu_id"], MenuItemUpdate(allergens=["Milk", "Wheat", "Egg"], publish=True), user=COOK)
        assert (await menu.public_today(date=DAY))[0]["allergens"] == ["Milk", "Wheat", "Egg"]
        assert (await db.menu_items.find_one({"menu_id": c1["menu_id"]}))["allergens"] == ["Milk", "Wheat"]
        rc = await db.receipts.find_one({"related_object_id": c2["menu_id"], "action_type": "menu_content_corrected"})
        assert rc["before_state"]["allergens"] == ["Milk", "Wheat"] and rc["after_state"]["allergens"] == ["Milk", "Wheat", "Egg"]

        # clearing labels is an explicit empty list
        c3 = await menu.update_menu_item(c2["menu_id"], MenuItemUpdate(dietary_labels=[], publish=True), user=COOK)
        assert c3["dietary_labels"] == [] and (await menu.public_today(date=DAY))[0]["dietary_labels"] == []

        with pytest.raises(HTTPException) as e:
            await menu.update_menu_item(c3["menu_id"], MenuItemUpdate(allergens=["Peanut"]), user=NURSE)
        assert e.value.status_code == 403
    finally:
        ids = [i["menu_id"] for i in await db.menu_items.find({"date": DAY}, {"menu_id": 1}).to_list(50)]
        await db.menu_items.delete_many({"date": DAY})
        await db.receipts.delete_many({"related_object_id": {"$in": ids}})


@pytest.mark.skipif(not _db_ready(), reason="writes menu records; point DB_NAME at a scratch database")
def test_labels_ride_the_menu_lifecycle_and_reach_residents_verbatim():
    asyncio.get_event_loop().run_until_complete(_scenario())
