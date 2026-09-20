"""Real inbound email adapter - signature verification (pure unit tests,
no DB) plus the full webhook flow against an isolated real-Mongo instance
(same isolated-subprocess pattern as test_level1_session_fencing.py).

No live Resend account/network access is used anywhere here -
_fetch_received_email() (the one function that would call Resend's real
API) is monkeypatched to return a fabricated body, and every webhook
payload is hand-signed with a fabricated test secret using the exact same
Svix algorithm routes/email_inbound_signature.py implements - this is
what "simulated signed payloads" means for this task.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes.email_inbound_signature import verify_resend_webhook, WebhookVerificationError  # noqa: E402

TEST_SECRET = "whsec_" + base64.b64encode(b"test-signing-secret-32-bytes!!").decode()


def _sign(secret: str, svix_id: str, ts: str, body: bytes) -> str:
    secret_bytes = base64.b64decode(secret[len("whsec_"):])
    signed = f"{svix_id}.{ts}.".encode() + body
    return "v1," + base64.b64encode(hmac.new(secret_bytes, signed, hashlib.sha256).digest()).decode()


# ---------- Pure signature-verification unit tests (no DB, no network) ----------

def test_signature_accepts_a_correctly_signed_payload():
    body = b'{"type":"email.received"}'
    svix_id, ts = "msg_1", str(int(time.time()))
    sig = _sign(TEST_SECRET, svix_id, ts, body)
    verify_resend_webhook(secret=TEST_SECRET, svix_id=svix_id, svix_timestamp=ts,
                           svix_signature=sig, body=body)  # must not raise


def test_signature_rejects_a_tampered_body():
    body = b'{"type":"email.received"}'
    svix_id, ts = "msg_1", str(int(time.time()))
    sig = _sign(TEST_SECRET, svix_id, ts, body)
    with pytest.raises(WebhookVerificationError):
        verify_resend_webhook(secret=TEST_SECRET, svix_id=svix_id, svix_timestamp=ts,
                               svix_signature=sig, body=b'{"type":"email.received","x":1}')


def test_signature_rejects_wrong_secret():
    body = b"{}"
    svix_id, ts = "msg_1", str(int(time.time()))
    sig = _sign("whsec_" + base64.b64encode(b"a-totally-different-secret-here").decode(), svix_id, ts, body)
    with pytest.raises(WebhookVerificationError):
        verify_resend_webhook(secret=TEST_SECRET, svix_id=svix_id, svix_timestamp=ts,
                               svix_signature=sig, body=body)


def test_signature_rejects_expired_timestamp():
    body = b"{}"
    svix_id = "msg_1"
    old_ts = str(int(time.time()) - 3700)
    sig = _sign(TEST_SECRET, svix_id, old_ts, body)
    with pytest.raises(WebhookVerificationError):
        verify_resend_webhook(secret=TEST_SECRET, svix_id=svix_id, svix_timestamp=old_ts,
                               svix_signature=sig, body=body)


def test_signature_rejects_missing_headers():
    with pytest.raises(WebhookVerificationError):
        verify_resend_webhook(secret=TEST_SECRET, svix_id=None, svix_timestamp=None,
                               svix_signature=None, body=b"{}")


# ---------- Full webhook flow, isolated real Mongo, subprocess ----------

def test_inbound_email_full_flow():
    env = {**os.environ, "DB_NAME": f"caos_email_inbound_test_{uuid.uuid4().hex[:10]}",
           "RESEND_WEBHOOK_SECRET": TEST_SECRET, "RESEND_API_KEY": "unused-in-this-test"}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"],
                        env=env, capture_output=True, text=True, timeout=60)
    print(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr


MENU_BODY = "Date: 2026-09-25\n\nBreakfast: Oatmeal, Toast\nLunch: Soup, Salad\nDinner: Chicken, Rice\n"
ACTIVITIES_BODY = "Monday 2026-09-28:\n10:00 AM Chair Yoga - Sunroom\n2:00 PM Bingo [activity]\n"


async def run():
    assert os.environ["DB_NAME"].startswith("caos_email_inbound_test_")
    from deps import db
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from routes import email_inbound, email_inbound_allowlist

    app = FastAPI()
    app.include_router(email_inbound.router)
    app.include_router(email_inbound_allowlist.router)

    async def fake_fetch(email_id: str) -> dict:
        return fake_fetch.bodies[email_id]
    fake_fetch.bodies = {}
    email_inbound._fetch_received_email = fake_fetch

    await db.email_allowlist.insert_one({
        "entry_id": "a1", "lane": "menu", "pattern": "chef@thefacility.com",
        "active": True, "created_at": "now",
    })
    await db.email_allowlist.insert_one({
        "entry_id": "a2", "lane": "activities", "pattern": "@thefacility.com",
        "active": True, "created_at": "now",
    })

    def make_payload(email_id, frm, to, subject="Menu"):
        return {"type": "email.received", "created_at": "2026-09-19T12:00:00.000Z",
                "data": {"email_id": email_id, "from": frm, "to": [to] if isinstance(to, str) else to,
                         "subject": subject, "attachments": []}}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        async def post_signed(payload: dict):
            body = json.dumps(payload).encode()
            svix_id, ts = f"msg_{uuid.uuid4().hex[:8]}", str(int(time.time()))
            sig = _sign(TEST_SECRET, svix_id, ts, body)
            return await c.post("/email/inbound/resend", content=body,
                                 headers={"content-type": "application/json", "svix-id": svix_id,
                                          "svix-timestamp": ts, "svix-signature": sig})

        # 1) Approved sender, menu lane, explicit Date: line -> routed, MenuUpload created, parsed.
        eid1 = f"email_{uuid.uuid4().hex[:8]}"
        fake_fetch.bodies[eid1] = {"text": MENU_BODY, "html": ""}
        resp = await post_signed(make_payload(eid1, "chef@thefacility.com", "menu@inbound.caoscare.com"))
        assert resp.status_code == 200, resp.text
        r1 = resp.json()
        assert r1["status"] == "routed" and r1["routed_lane"] == "menu"
        upload = await db.menu_uploads.find_one({"upload_id": r1["linked_object_id"]}, {"_id": 0})
        assert upload["source"] == "email" and upload["service_date"] == "2026-09-25"
        assert upload["parse_status"] == "parsed"
        items = await db.menu_items.find({"upload_id": upload["upload_id"]}, {"_id": 0}).to_list(20)
        assert len(items) == 6 and all(i["source"] == "email" for i in items)

        # 2) Same email_id replayed (Resend retry) -> duplicate, no second upload.
        resp2 = await post_signed(make_payload(eid1, "chef@thefacility.com", "menu@inbound.caoscare.com"))
        assert resp2.json()["status"] == "duplicate"
        assert await db.menu_uploads.count_documents({}) == 1

        # 3) Unapproved sender to menu lane -> quarantined, no upload created.
        eid2 = f"email_{uuid.uuid4().hex[:8]}"
        fake_fetch.bodies[eid2] = {"text": MENU_BODY, "html": ""}
        resp3 = await post_signed(make_payload(eid2, "stranger@example.com", "menu@inbound.caoscare.com"))
        assert resp3.json()["status"] == "quarantined"
        assert await db.menu_uploads.count_documents({}) == 1
        stored = await db.inbound_emails.find_one({"provider_message_id": eid2}, {"_id": 0})
        assert stored["sender_trust"] == "quarantined" and stored["routed_lane"] == "menu"

        # 4) Unrecognized recipient -> unrecognized_recipient, nothing routed.
        eid3 = f"email_{uuid.uuid4().hex[:8]}"
        resp4 = await post_signed(make_payload(eid3, "chef@thefacility.com", "random@inbound.caoscare.com"))
        assert resp4.json()["status"] == "unrecognized_recipient"

        # 5) Approved sender, activities lane (domain-wildcard allowlist entry) -> routed, ScheduleItems created.
        eid4 = f"email_{uuid.uuid4().hex[:8]}"
        fake_fetch.bodies[eid4] = {"text": ACTIVITIES_BODY, "html": ""}
        resp5 = await post_signed(make_payload(eid4, "programs@thefacility.com",
                                                "activities@inbound.caoscare.com", subject="Activities"))
        r5 = resp5.json()
        assert r5["status"] == "routed" and r5["routed_lane"] == "activities"
        sched = await db.schedule_items.find({"source": "email"}, {"_id": 0}).to_list(20)
        assert len(sched) == 2
        assert all(s["source_ref"] == r5["inbound_id"] for s in sched)

        # 6) Bad signature -> 401, nothing recorded for this email_id.
        eid5 = f"email_{uuid.uuid4().hex[:8]}"
        body6 = json.dumps(make_payload(eid5, "chef@thefacility.com", "menu@inbound.caoscare.com")).encode()
        resp6 = await c.post("/email/inbound/resend", content=body6,
                              headers={"content-type": "application/json", "svix-id": "bad",
                                       "svix-timestamp": str(int(time.time())), "svix-signature": "v1,not-a-real-sig"})
        assert resp6.status_code == 401
        assert await db.inbound_emails.find_one({"provider_message_id": eid5}) is None

        # 7) No RESEND_WEBHOOK_SECRET configured -> 503, not a crash, nothing recorded.
        del email_inbound.os.environ["RESEND_WEBHOOK_SECRET"]
        try:
            resp7 = await post_signed(make_payload(f"email_{uuid.uuid4().hex[:8]}", "chef@thefacility.com",
                                                    "menu@inbound.caoscare.com"))
            assert resp7.status_code == 503
        finally:
            email_inbound.os.environ["RESEND_WEBHOOK_SECRET"] = TEST_SECRET

        # 8) Allowlist CRUD (admin) - listing both seeded lanes.
        from routes.email_inbound_allowlist import check_sender_allowed
        assert await check_sender_allowed("menu", "chef@thefacility.com") is True
        assert await check_sender_allowed("menu", "nobody@nowhere.com") is False
        assert await check_sender_allowed("activities", "anyone@thefacility.com") is True

    print(json.dumps({"database": db.name, "menu_uploads": 1, "quarantined": 1,
                       "unrecognized": 1, "schedule_items": 2, "duplicate_blocked": True}))


if __name__ == "__main__":
    asyncio.run(run())
