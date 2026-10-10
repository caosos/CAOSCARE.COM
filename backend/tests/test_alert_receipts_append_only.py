"""Test-reality gap 3 (docs/reports/2026-10-09-test-reality-audit.md): alert close-out and
failed/accepted page outcomes append NEW receipts and never rewrite the earlier one
(ENGINEERING_CONTRACT decision 5). In-process, DB-direct; refuses to run against the live DB."""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes receipts; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes.alerts import _close_out  # noqa: E402
from routes.receipts import create_receipt  # noqa: E402
from routes.staff_dispatch import _transition  # noqa: E402

TAG = f"arcpt_{uuid.uuid4().hex[:8]}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _receipts(alert_id):
    return await db.receipts.find({"related_object_type": "alert", "related_object_id": alert_id},
                                  {"_id": 0}).sort("created_at", 1).to_list(50)


async def _alert(name):
    aid = f"{TAG}_{name}"
    r = await create_receipt(action_type="alert_created", related_object_type="alert", related_object_id=aid,
                             source="system", room=f"{TAG}-R", status="created")
    doc = {"alert_id": aid, "room": f"{TAG}-R", "receipt_id": r["receipt_id"] if isinstance(r, dict) else r.receipt_id,
           "status": "active", "press_count": 2, "outcome": "nurse attended"}
    await db.alerts.insert_one(dict(doc))
    return doc


def teardown_module(_m):
    run(db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}"}}))
    run(db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}"}}))
    run(db.staff_dispatches.delete_many({"dispatch_id": {"$regex": f"^{TAG}"}}))


def test_close_out_appends_a_completed_receipt_and_keeps_the_first():
    doc = run(_alert("close"))
    before = run(_receipts(doc["alert_id"]))
    run(_close_out(doc))
    after = run(_receipts(doc["alert_id"]))
    assert len(before) == 1 and len(after) == 2
    assert after[0] == before[0]  # the earlier receipt is byte-identical
    assert after[1]["action_type"] == "alert_completed" and after[1]["status"] == "completed"
    assert after[1]["result"] == "nurse attended" and after[1]["room"] == f"{TAG}-R"


def test_failed_page_appends_alert_failed_and_a_later_accept_is_a_third_receipt():
    doc = run(_alert("page"))
    did = f"{TAG}_dsp"
    run(db.staff_dispatches.insert_one({"dispatch_id": did, "alert_id": doc["alert_id"], "receipt_id": doc["receipt_id"],
                                        "department": "Care/Nursing", "status": "sent", "events": []}))
    first = run(_receipts(doc["alert_id"]))[0]
    run(_transition(did, "failed", failure_reason="gateway down"))
    run(_transition(did, "accepted"))
    rs = run(_receipts(doc["alert_id"]))
    assert [r["action_type"] for r in rs] == ["alert_created", "alert_failed", "alert_completed"]
    assert rs[0] == first
    assert "page failed" in rs[1]["result"] and "page accepted" in rs[2]["result"]


def test_object_without_a_receipt_gets_nothing_invented():
    doc = {"alert_id": f"{TAG}_none", "room": "x", "receipt_id": "r", "status": "active"}
    run(_close_out(doc))
    assert run(_receipts(doc["alert_id"])) == []
