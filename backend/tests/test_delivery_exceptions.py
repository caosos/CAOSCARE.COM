"""careops-frontdesk-failed-deliveries-001: deliveries about an alert that were
not sent or failed (escalation SMS / live-line calls, family alert updates)
are listed for the front desk at GET /ops/delivery-exceptions: current (72 h)
only, newest first, no message text, recipients masked and labelled, an
honest status label, linked to the alert. Sent/delivered, request-linked
(already in routing exceptions) and older records are excluded. Front desk
and owner/admin may read it; other staff 403, anonymous 401. The admin
delivery log stays admin-only. Uses the backend test gate's server.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"dex_{uuid.uuid4().hex[:8]}"


def _up():
    try:
        return requests.get(f"{API}/health", timeout=3).ok
    except Exception:
        return False


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "dex-pw-12345678"
    for k, (role, dept) in {"fd": ("front_desk", None), "nurse": ("staff", "nursing"), "admin": ("admin", None)}.items():
        await db.users.insert_one({"user_id": uid("user"), "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid, aid = f"{TAG}_res", f"{TAG}_alert"
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": "Q12", "created_at": now_utc().isoformat()})
    await db.alerts.insert_one({"alert_id": aid, "resident_id": rid, "resident_name": f"{TAG} Resident", "room": "Q12",
                                "severity": "emergency", "status": "active", "created_at": now_utc().isoformat()})
    await db.family_contacts.insert_one({"contact_id": f"{TAG}_fc", "resident_id": rid, "name": "Liam Example", "relationship": "son",
                                         "email": "liam.example@example.com", "phone": "+15550001234", "notify_on": ["emergency"]})
    now = datetime.now(timezone.utc)
    secret = "Resident fell in the bathroom; possible hip injury"
    def n(name, **kw):
        return {"notification_id": f"{TAG}_{name}", "subject": "CAOS Care update", "body": secret,
                "created_at": kw.pop("created_at", now.isoformat()), **kw}
    await db.notifications.insert_many([
        n("fam_logged", channel="email", to="liam.example@example.com", alert_id=aid, resident_id=rid, status="logged",
          provider_response="Resend not configured - recorded only, not sent", created_at=(now - timedelta(minutes=5)).isoformat()),
        n("sms_failed", channel="sms", to="+15559876543", alert_id=aid, resident_id=rid, status="failed",
          related_object_type="alert", related_object_id=aid, provider_response="exception: 401 bad credentials", receipt_id=f"{TAG}_r1"),
        n("sent", channel="email", to="liam.example@example.com", alert_id=aid, resident_id=rid, status="sent"),
        n("task", channel="email", to="desk@example.com", status="logged", related_object_type="task", related_object_id=f"{TAG}_t", task_id=f"{TAG}_t"),
        n("old", channel="email", to="liam.example@example.com", alert_id=aid, resident_id=rid, status="logged",
          created_at=(now - timedelta(days=5)).isoformat()),
    ])
    try:
        H = {k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
             for k in ("fd", "nurse", "admin")}
        r = requests.get(f"{API}/ops/delivery-exceptions", headers=H["fd"], timeout=5)
        assert r.status_code == 200, (r.status_code, r.text)
        mine = [i for i in r.json()["items"] if i["notification_id"].startswith(TAG)]
        assert [i["notification_id"].removeprefix(f"{TAG}_") for i in mine] == ["sms_failed", "fam_logged"], mine
        sms, fam = mine
        for i in mine:
            assert secret not in str(i) and "CAOS Care update" not in str(i), i          # no message text
            assert "liam.example@example.com" not in str(i) and "+1555" not in str(i), i  # recipients masked
            assert i["alert_id"] == aid and i["resident_name"] == f"{TAG} Resident" and i["room"] == "Q12"
        assert fam["recipient"] == "Family: Liam Example (son)" and fam["channel"] == "email"
        assert fam["state"] == "not_sent" and "not sent" in fam["label"].lower()
        assert sms["state"] == "failed" and sms["channel"] == "sms" and sms["recipient"].endswith("6543")
        assert "credentials" not in sms["label"]                                         # provider internals not shown
        assert sms["receipt_id"] == f"{TAG}_r1"
        assert r.json()["counts"]["failed"] >= 1 and r.json()["counts"]["not_sent"] >= 1
        a = requests.get(f"{API}/ops/delivery-exceptions", headers=H["admin"], timeout=5).json()
        assert [i["notification_id"] for i in a["items"] if i["notification_id"].startswith(TAG)] == [sms["notification_id"], fam["notification_id"]]
        assert requests.get(f"{API}/ops/delivery-exceptions", headers=H["nurse"], timeout=5).status_code == 403
        assert requests.get(f"{API}/ops/delivery-exceptions", timeout=5).status_code == 401
        assert requests.get(f"{API}/notifications", headers=H["fd"], timeout=5).status_code == 403         # admin log unchanged
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.alerts.delete_many({"alert_id": aid})
        await db.family_contacts.delete_many({"contact_id": f"{TAG}_fc"})
        await db.notifications.delete_many({"notification_id": {"$regex": f"^{TAG}_"}})


def test_front_desk_sees_alert_delivery_failures_redacted():
    if os.environ.get("DB_NAME") in ("caoscare", "", None):
        pytest.skip("point DB_NAME at a scratch database")
    if not _up():
        pytest.skip(f"backend not reachable at {API}")
    asyncio.new_event_loop().run_until_complete(_run())
