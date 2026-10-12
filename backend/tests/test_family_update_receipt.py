"""careops-alerts-family-update-receipt-001: every family alert update attempt
(email and SMS from notify_family_for_alert) has exactly one receipt: system
actor, authority naming the family contact and preference, parent = the
alert's origin receipt, the notification it cites, an honest result label
(logged -> unverified, never sent/delivered), and the notification carries
that receipt id and the alert link. In-process, DB-direct; scratch DB only.
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import AlertCreate, uid, now_utc  # noqa: E402
from routes.alerts import create_alert  # noqa: E402

TAG = f"fur_{uuid.uuid4().hex[:8]}"


async def _scenario(monkeypatch):
    for k in ("RESEND_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)                       # no provider: attempts are "logged"
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R", "created_at": now_utc().isoformat()})
    cid = f"{TAG}_fc"
    await db.family_contacts.insert_one({"contact_id": cid, "resident_id": rid, "name": "Liam", "relationship": "son",
                                         "email": f"{TAG}@example.com", "phone": "+15550004321", "notify_on": ["emergency"]})
    aid = None
    try:
        a = await create_alert(AlertCreate(resident_id=rid, severity="emergency", message="synthetic", triggered_by="manual"))
        aid = a["alert_id"]
        origin = (await db.alerts.find_one({"alert_id": aid}))["receipt_id"]
        notes = await db.notifications.find({"alert_id": aid}, {"_id": 0}).to_list(10)
        assert sorted(n["channel"] for n in notes) == ["email", "sms"], notes
        for n in notes:
            assert n["status"] == "logged"
            assert n.get("receipt_id"), n
            assert n.get("related_object_type") == "alert" and n.get("related_object_id") == aid
            rs = await db.receipts.find({"related_object_id": aid, "action_type": "family_alert_update_attempt",
                                         "after_state.notification_id": n["notification_id"]}).to_list(5)
            assert len(rs) == 1 and rs[0]["receipt_id"] == n["receipt_id"]
            r = rs[0]
            assert r["actor_type"] == "system" and r["actor_id"] == "system:family_notify"
            assert r["authority"] == f"family_contact:{cid}:notify_on:emergency"
            assert r["parent_receipt_id"] == origin
            assert r["result_label"] == "unverified" and r["after_state"]["notification_status"] == "logged"
            assert r["channel"] == n["channel"]
            assert f"{TAG}@example.com" not in (r.get("result") or "") and "+15550004321" not in (r.get("result") or "")
    finally:
        await db.residents.delete_many({"resident_id": rid})
        await db.family_contacts.delete_many({"contact_id": cid})
        if aid:
            await db.alerts.delete_many({"alert_id": aid})
            await db.receipts.delete_many({"related_object_id": aid})
            await db.notifications.delete_many({"alert_id": aid})
            await db.staff_dispatches.delete_many({"alert_id": aid})


def test_each_family_update_attempt_is_receipted(monkeypatch):
    asyncio.get_event_loop().run_until_complete(_scenario(monkeypatch))
