"""Outbound notification delivery truth + department fallback routing +
Resend delivery-event webhook, against an isolated real-Mongo database
(same isolated-subprocess pattern as test_email_inbound.py).

No live provider is contacted: Resend's HTTP API is replaced with an
httpx.MockTransport, and webhook payloads are hand-signed with a
fabricated secret.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_email_inbound import TEST_SECRET, _sign  # noqa: E402


def test_notification_delivery_flow():
    env = {**os.environ, "DB_NAME": f"caos_notif_delivery_test_{uuid.uuid4().hex[:10]}",
           "RESEND_WEBHOOK_SECRET": TEST_SECRET}
    env.pop("RESEND_API_KEY", None)
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"],
                       env=env, capture_output=True, text=True, timeout=60)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr


async def run():
    assert os.environ["DB_NAME"].startswith("caos_notif_delivery_test_")
    import httpx
    from deps import db
    from fastapi import FastAPI
    from routes import notifications, notification_delivery, email_inbound

    await db.departments.insert_many([
        {"slug": "maintenance", "label": "Maintenance", "contact_email": "maint@facility.test"},
        {"slug": "nursing", "label": "Nursing / Care"},
        {"slug": "ghost", "label": "Ghost"},
    ])
    await db.users.insert_many([
        {"user_id": "u1", "email": "nurse1@facility.test", "department": "nursing", "role": "staff"},
        {"user_id": "u2", "email": "owner@facility.test", "role": "owner"},
    ])

    # 1) No provider configured -> "logged", tagged with department/route/task; never "sent".
    recs = await notifications.notify_department("maintenance", "S", "B",
                                                 related_object_type="task", related_object_id="task_1")
    assert [r["status"] for r in recs] == ["logged"]
    assert recs[0]["to"] == "maint@facility.test" and recs[0]["route"] == "department_contact"
    assert recs[0]["department"] == "maintenance" and recs[0]["related_object_id"] == "task_1"

    # 2) Provider configured via a mock Resend: accepted -> "sent" + provider id kept.
    calls = []

    def resend(request: httpx.Request) -> httpx.Response:
        to = json.loads(request.content)["to"][0]
        calls.append(to)
        if to == "maint@facility.test":
            return httpx.Response(422, json={"message": "invalid recipient"})
        return httpx.Response(200, json={"id": f"re_{to}"})

    real_client = httpx.AsyncClient
    notification_delivery.httpx.AsyncClient = lambda **kw: real_client(transport=httpx.MockTransport(resend), **kw)
    os.environ["RESEND_API_KEY"] = "test-key"
    try:
        # 3) Department contact rejected by provider -> falls through to staff, then admin (no staff).
        recs = await notifications.notify_department("maintenance", "S", "B")
        assert [(r["route"], r["status"]) for r in recs] == [
            ("department_contact", "failed"), ("admin_fallback", "sent")]
        assert recs[1]["provider_message_id"] == "re_owner@facility.test"

        # Department staff tier reached directly when no contact_email.
        recs = await notifications.notify_department("nursing", "S", "B")
        assert [(r["route"], r["to"], r["status"]) for r in recs] == [
            ("department_staff", "nurse1@facility.test", "sent")]
    finally:
        del os.environ["RESEND_API_KEY"]
        notification_delivery.httpx.AsyncClient = real_client

    # 4) Nobody reachable at all -> one explicit failed record, not silence.
    await db.users.delete_many({})
    recs = await notifications.notify_department("ghost", "S", "B")
    assert len(recs) == 1 and recs[0]["status"] == "failed" and recs[0]["to"] == ""

    # 5) Resend delivery events through the one signed webhook endpoint.
    app = FastAPI()
    app.include_router(email_inbound.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
        async def post_signed(payload: dict):
            body = json.dumps(payload).encode()
            svix_id, ts = f"msg_{uuid.uuid4().hex[:8]}", str(int(time.time()))
            return await c.post("/email/inbound/resend", content=body, headers={
                "content-type": "application/json", "svix-id": svix_id,
                "svix-timestamp": ts, "svix-signature": _sign(TEST_SECRET, svix_id, ts, body)})

        eid = "re_nurse1@facility.test"
        r = (await post_signed({"type": "email.delivered", "created_at": "2026-09-27T12:00:00Z",
                                "data": {"email_id": eid}})).json()
        assert r["status"] == "delivery_event" and r["matched"] and r["notification_status"] == "delivered"
        n = await db.notifications.find_one({"provider_message_id": eid}, {"_id": 0})
        assert n["status"] == "delivered" and n["delivery_events"][0]["type"] == "email.delivered"

        # A late weaker event is recorded but never downgrades a terminal outcome.
        await post_signed({"type": "email.delivery_delayed", "data": {"email_id": eid}})
        n = await db.notifications.find_one({"provider_message_id": eid}, {"_id": 0})
        assert n["status"] == "delivered" and len(n["delivery_events"]) == 2

        # Bounce keeps the provider's reason.
        bid = "re_owner@facility.test"
        await post_signed({"type": "email.bounced", "data": {"email_id": bid, "bounce": {
            "type": "Permanent", "subType": "General", "message": "mailbox does not exist"}}})
        n = await db.notifications.find_one({"provider_message_id": bid}, {"_id": 0})
        assert n["status"] == "bounced" and "mailbox does not exist" in n["delivery_events"][0]["detail"]

        # Unknown email id -> acknowledged, unmatched; never ingested as inbound mail.
        r = (await post_signed({"type": "email.delivered", "data": {"email_id": "re_unknown"}})).json()
        assert r["matched"] is False
        assert await db.inbound_emails.count_documents({}) == 0

    print(json.dumps({"database": db.name, "ok": True}))
    await db.client.drop_database(db.name)


if __name__ == "__main__":
    asyncio.run(run())
