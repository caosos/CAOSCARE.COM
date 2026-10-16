"""Per-user dashboard layout: save, version conflict, reset, receipts."""
import asyncio
import uuid

import pytest
from fastapi import HTTPException

from deps import db
from routes import user_layout as ul

USER = {"user_id": f"ul_{uuid.uuid4().hex[:8]}", "role": "owner", "name": "Layout Tester"}
BOXES = [ul.Box(id="nursing.done", x=0, y=0, w=4, h=2), ul.Box(id="sim.controls", x=4, y=0, w=8, h=3, hidden=True)]


def run(c):
    return asyncio.run(c)


@pytest.fixture(autouse=True)
def clean():
    yield
    async def t():
        await db.user_layouts.delete_many({"user_id": USER["user_id"]})
        await db.receipts.delete_many({"related_object_id": {"$regex": f"^{USER['user_id']}:"}})
    run(t())


def test_save_reload_conflict_reset_with_receipts():
    assert run(ul.get_layout("live_ops", USER))["layout"] is None
    saved = run(ul.save_layout(ul.LayoutInput(version=0, boxes=BOXES), USER))["layout"]
    assert saved["version"] == 1
    got = run(ul.get_layout("live_ops", USER))["layout"]
    assert [b["id"] for b in got["boxes"]] == ["nursing.done", "sim.controls"] and got["boxes"][1]["hidden"]
    with pytest.raises(HTTPException) as e:            # another tab still on version 0
        run(ul.save_layout(ul.LayoutInput(version=0, boxes=BOXES[:1]), USER))
    assert e.value.status_code == 409
    assert run(ul.save_layout(ul.LayoutInput(version=1, boxes=BOXES[:1]), USER))["layout"]["version"] == 2
    run(ul.reset_layout("live_ops", USER))
    assert run(ul.get_layout("live_ops", USER))["layout"] is None

    async def receipts():
        return await db.receipts.find({"related_object_id": f"{USER['user_id']}:live_ops"}, {"_id": 0}) \
            .sort("created_at", 1).to_list(10)
    rs = run(receipts())
    assert [r["action_type"] for r in rs] == ["dashboard_layout_saved", "dashboard_layout_saved", "dashboard_layout_reset"]
    assert all(r.get("actor_id") == USER["user_id"] for r in rs)


def test_rejects_bad_input():
    with pytest.raises(HTTPException):
        run(ul.save_layout(ul.LayoutInput(version=0, boxes=[BOXES[0], BOXES[0]]), USER))
    with pytest.raises(HTTPException):
        run(ul.get_layout("someone_elses", USER))
    with pytest.raises(ValueError):
        ul.Box(id="Bad Id!", x=0, y=0, w=1, h=1)
