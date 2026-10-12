"""careops-dining-correction-versioning-001: correcting a PUBLISHED menu item
makes a replacement, it never overwrites the published one. The original
stays live (residents/Aria keep a menu) until the correction is published;
then the original is labelled superseded (superseded_by) and the corrected
item (replaces) is what staff, residents and Aria read. Each step is
receipted; a superseded or already-replaced item cannot be revived; another
department cannot edit. In-process, DB-direct; scratch DB only.
"""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes menu records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import MenuItemCreate, MenuItemUpdate  # noqa: E402
from routes import menu  # noqa: E402

TAG = f"mcv_{uuid.uuid4().hex[:8]}"
DAY = "2031-03-04"   # a synthetic future day nothing else uses
COOK = {"user_id": f"{TAG}_cook", "name": "Cook", "role": "staff", "department": "kitchen"}
NURSE = {"user_id": f"{TAG}_nurse", "name": "Nurse", "role": "staff", "department": "nursing"}


async def _names():
    return [i["item_name"] for i in await menu.public_today(date=DAY, meal_period="dinner")]


async def _rcpts(mid, action):
    return await db.receipts.find({"related_object_id": mid, "action_type": f"menu_content_{action}"}).to_list(5)


async def _scenario():
    await db.menu_items.delete_many({"date": DAY})
    try:
        v1 = (await menu.create_menu_item(MenuItemCreate(date=DAY, meal_period="dinner", item_name="Baked cod",
                                                         description="with rice"), user=COOK))["menu_id"]
        await menu.approve_menu_item(v1, user=COOK)
        assert await _names() == ["Baked cod"]

        # a correction saved as draft: a NEW item; the published one is untouched and stays live
        c1 = await menu.update_menu_item(v1, MenuItemUpdate(item_name="Grilled salmon"), user=COOK)
        assert c1["menu_id"] != v1 and c1["status"] == "draft" and c1["replaces"] == v1, c1
        assert c1["description"] == "with rice" and c1["date"] == DAY and c1["meal_period"] == "dinner"
        old = await db.menu_items.find_one({"menu_id": v1})
        assert old["status"] == "approved" and old["item_name"] == "Baked cod"
        assert await _names() == ["Baked cod"], "residents keep the published dinner until the correction is published"
        corr = await _rcpts(c1["menu_id"], "corrected")
        assert len(corr) == 1 and corr[0]["before_state"]["item_name"] == "Baked cod" and corr[0]["after_state"]["replaces"] == v1

        # a second, competing correction of the same item
        c2 = await menu.update_menu_item(v1, MenuItemUpdate(item_name="Fish tacos"), user=COOK)
        # a draft correction is edited in place (it was never published)
        c1b = await menu.update_menu_item(c1["menu_id"], MenuItemUpdate(description="with lemon rice"), user=COOK)
        assert c1b["menu_id"] == c1["menu_id"] and c1b["description"] == "with lemon rice"

        # publishing the correction supersedes the original
        await menu.approve_menu_item(c1["menu_id"], user=COOK)
        old = await db.menu_items.find_one({"menu_id": v1})
        assert old["status"] == "superseded" and old["superseded_by"] == c1["menu_id"] and old["item_name"] == "Baked cod"
        assert await _names() == ["Grilled salmon"]
        sup = await _rcpts(v1, "superseded")
        assert len(sup) == 1 and sup[0]["before_state"]["status"] == "approved" and sup[0]["after_state"]["superseded_by"] == c1["menu_id"]
        staff = {i["menu_id"]: i["status"] for i in await menu.list_menu(date=DAY, user=COOK)}
        assert staff[v1] == "superseded" and staff[c1["menu_id"]] == "approved"

        # the competing correction can no longer be published; the original cannot be revived
        for call in (menu.approve_menu_item(c2["menu_id"], user=COOK), menu.approve_menu_item(v1, user=COOK),
                     menu.update_menu_item(v1, MenuItemUpdate(item_name="x"), user=COOK)):
            with pytest.raises(HTTPException) as e:
                await call
            assert e.value.status_code == 409
        assert await _names() == ["Grilled salmon"]

        # correct-and-publish in one action: replacement live, previous superseded, at once
        c3 = await menu.update_menu_item(c1["menu_id"], MenuItemUpdate(item_name="Grilled salmon (no butter)", publish=True), user=COOK)
        assert c3["menu_id"] != c1["menu_id"] and c3["status"] == "approved" and c3["replaces"] == c1["menu_id"]
        assert (await db.menu_items.find_one({"menu_id": c1["menu_id"]}))["status"] == "superseded"
        assert await _names() == ["Grilled salmon (no butter)"]

        # another department may not correct the menu
        with pytest.raises(HTTPException) as e:
            await menu.update_menu_item(c3["menu_id"], MenuItemUpdate(item_name="y"), user=NURSE)
        assert e.value.status_code == 403
    finally:
        ids = [i["menu_id"] for i in await db.menu_items.find({"date": DAY}, {"menu_id": 1}).to_list(50)]
        await db.menu_items.delete_many({"date": DAY})
        await db.receipts.delete_many({"related_object_id": {"$in": ids}})


def test_published_menu_correction_is_a_versioned_replacement():
    asyncio.get_event_loop().run_until_complete(_scenario())
