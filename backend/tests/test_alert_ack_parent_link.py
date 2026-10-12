"""careops-alerts-ack-parent-link-001: an alert_acknowledged receipt names the
alert's origin receipt (resident_assistance_event) as its parent, as
alert_completed already does; the history entry still carries the
acknowledgement receipt; a repeat acknowledgement writes nothing.
In-process, DB-direct; refuses to run against the live DB.
"""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import AlertClose, AlertCreate, uid, now_utc  # noqa: E402
from routes.alerts import acknowledge, close_alert, create_alert  # noqa: E402

TAG = f"apl_{uuid.uuid4().hex[:8]}"
NURSE = {"user_id": f"{TAG}_nurse", "name": f"{TAG} Nurse", "role": "staff", "department": "nursing"}


async def _scenario():
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R",
                                   "created_at": now_utc().isoformat()})
    aid = None
    try:
        a = await create_alert(AlertCreate(resident_id=rid, severity="assist", message="synthetic", triggered_by="manual"))
        aid = a["alert_id"]
        origin = await db.receipts.find_one({"related_object_id": aid, "action_type": "resident_assistance_event"})
        assert origin and (await db.alerts.find_one({"alert_id": aid}))["receipt_id"] == origin["receipt_id"]

        doc = await acknowledge(aid, user=NURSE)
        acks = await db.receipts.find({"related_object_id": aid, "action_type": "alert_acknowledged"}).to_list(5)
        assert len(acks) == 1
        assert acks[0].get("parent_receipt_id") == origin["receipt_id"], acks[0].get("parent_receipt_id")
        ev = [e for e in doc["event_log"] if e.get("to") == "acknowledged"]
        assert len(ev) == 1 and ev[0]["receipt_id"] == acks[0]["receipt_id"]

        with pytest.raises(HTTPException):
            await acknowledge(aid, user=NURSE)
        assert await db.receipts.count_documents({"related_object_id": aid, "action_type": "alert_acknowledged"}) == 1

        await close_alert(aid, AlertClose(outcome="resolved_no_action"), user=NURSE)
        done = await db.receipts.find_one({"related_object_id": aid, "action_type": "alert_completed"})
        assert done["parent_receipt_id"] == origin["receipt_id"]          # unchanged contract
        assert await db.notifications.count_documents({"related_object_id": aid, "status": "sent"}) == 0
    finally:
        await db.residents.delete_many({"resident_id": rid})
        if aid:
            await db.alerts.delete_many({"alert_id": aid})
            await db.receipts.delete_many({"related_object_id": aid})
            await db.notifications.delete_many({"$or": [{"alert_id": aid}, {"related_object_id": aid}]})
            await db.staff_dispatches.delete_many({"alert_id": aid})


def test_acknowledgement_receipt_names_the_origin():
    asyncio.get_event_loop().run_until_complete(_scenario())
