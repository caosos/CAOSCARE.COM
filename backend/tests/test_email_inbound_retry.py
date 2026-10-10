"""Inbound email: a transient provider-body fetch failure must be retryable exactly once, without double ingestion.
Isolated real-Mongo subprocess, hand-signed webhooks, provider fetch stubbed. No network, no real email."""
import asyncio, base64, hashlib, hmac, json, os, subprocess, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
SECRET = "whsec_" + base64.b64encode(b"test-signing-secret-32-bytes!!").decode()
MENU = "Date: 2026-09-25\n\nBreakfast: Oatmeal, Toast\nLunch: Soup, Salad\nDinner: Chicken, Rice\n"


def test_inbound_retry_flow():
    env = {**os.environ, "DB_NAME": f"caos_email_retry_test_{uuid.uuid4().hex[:10]}",
           "RESEND_WEBHOOK_SECRET": SECRET, "RESEND_API_KEY": "unused"}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"], env=env,
                       capture_output=True, text=True, timeout=90)
    assert r.returncode == 0, r.stdout + r.stderr


async def run():
    assert os.environ["DB_NAME"].startswith("caos_email_retry_test_")
    from deps import db
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from routes import email_inbound

    app = FastAPI(); app.include_router(email_inbound.router)
    state = {"fail": set(), "calls": {}, "delay": 0.0, "bodies": {}}

    async def fake_fetch(email_id):
        state["calls"][email_id] = state["calls"].get(email_id, 0) + 1
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        if email_id in state["fail"]:
            raise RuntimeError("provider temporarily unavailable")
        return state["bodies"][email_id]
    email_inbound._fetch_received_email = fake_fetch
    await db.email_allowlist.insert_many([
        {"entry_id": "a1", "lane": "menu", "pattern": "chef@thefacility.com", "active": True, "created_at": "now"},
        {"entry_id": "a2", "lane": "activities", "pattern": "@thefacility.com", "active": True, "created_at": "now"}])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
        async def post(eid, frm="chef@thefacility.com", to="menu@inbound.caoscare.com"):
            body = json.dumps({"type": "email.received", "created_at": "2026-09-19T12:00:00.000Z",
                               "data": {"email_id": eid, "from": frm, "to": [to], "subject": "x", "attachments": []}}).encode()
            sid, ts = f"msg_{uuid.uuid4().hex[:8]}", str(int(time.time()))
            sig = "v1," + base64.b64encode(hmac.new(base64.b64decode(SECRET[6:]), f"{sid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
            return await c.post("/email/inbound/resend", content=body, headers={
                "content-type": "application/json", "svix-id": sid, "svix-timestamp": ts, "svix-signature": sig})

        def eid(): return f"email_{uuid.uuid4().hex[:8]}"
        async def uploads(): return await db.menu_uploads.count_documents({})
        async def receipts(iid): return [r["action_type"] async for r in db.receipts.find({"related_object_id": iid}, {"_id": 0}).sort("created_at", 1)]

        # 1) transient fetch failure -> 502; retry succeeds -> same inbound_id, one upload, linked receipts; later duplicate adds nothing
        e1 = eid(); state["bodies"][e1] = {"text": MENU, "html": ""}; state["fail"].add(e1)
        r = await post(e1); assert r.status_code == 502, r.text
        row = await db.inbound_emails.find_one({"provider_message_id": e1}, {"_id": 0})
        iid = row["inbound_id"]; assert row["status"] == "error" and row["retryable"] is True and await uploads() == 0
        state["fail"].discard(e1)
        r = await post(e1); assert r.status_code == 200 and r.json()["status"] == "routed", r.text
        assert r.json()["inbound_id"] == iid and await uploads() == 1
        assert await db.inbound_emails.count_documents({"provider_message_id": e1}) == 1
        row = await db.inbound_emails.find_one({"provider_message_id": e1}, {"_id": 0})
        assert row["status"] == "routed" and row["linked_object_type"] == "menu_upload" and row["retryable"] is False
        assert await receipts(iid) == ["inbound_email.error", "inbound_email.routed"]
        r = await post(e1); assert r.json()["status"] == "duplicate" and await uploads() == 1
        assert state["calls"][e1] == 2   # no third fetch

        # 2) retry that fails again stays retryable; a third delivery then succeeds, exactly once
        e2 = eid(); state["bodies"][e2] = {"text": MENU.replace("2026-09-25", "2026-09-26"), "html": ""}; state["fail"].add(e2)
        assert (await post(e2)).status_code == 502
        assert (await post(e2)).status_code == 502
        row = await db.inbound_emails.find_one({"provider_message_id": e2}, {"_id": 0}); assert row["retryable"] is True
        state["fail"].discard(e2)
        assert (await post(e2)).json()["status"] == "routed" and await uploads() == 2
        assert (await post(e2)).json()["status"] == "duplicate" and await uploads() == 2

        # 3) concurrent retries: exactly one ingests
        e3 = eid(); state["bodies"][e3] = {"text": MENU.replace("2026-09-25", "2026-09-27"), "html": ""}; state["fail"].add(e3)
        assert (await post(e3)).status_code == 502
        state["fail"].discard(e3); state["delay"] = 0.2
        rs = await asyncio.gather(*[post(e3) for _ in range(6)])
        state["delay"] = 0.0
        kinds = sorted(x.json()["status"] for x in rs)
        assert kinds.count("routed") == 1 and kinds.count("duplicate") == 5, kinds
        assert await uploads() == 3 and state["calls"][e3] == 2

        # 4) permanent parse error is acknowledged and NOT retried
        e4 = eid(); state["bodies"][e4] = {"text": "no day headers at all", "html": ""}
        r = await post(e4, to="activities@inbound.caoscare.com", frm="programs@thefacility.com")
        assert r.status_code == 200 and r.json()["status"] == "error"
        row = await db.inbound_emails.find_one({"provider_message_id": e4}, {"_id": 0}); assert not row.get("retryable")
        n = state["calls"][e4]; r = await post(e4, to="activities@inbound.caoscare.com", frm="programs@thefacility.com")
        assert r.json()["status"] == "duplicate" and state["calls"][e4] == n

        # 5) quarantine stays final
        e5 = eid(); state["bodies"][e5] = {"text": MENU, "html": ""}
        assert (await post(e5, frm="stranger@example.com")).json()["status"] == "quarantined"
        assert (await post(e5, frm="stranger@example.com")).json()["status"] == "duplicate" and state["calls"][e5] == 1

        # 6) a claim abandoned mid-retry (crash) is reclaimable after the stale window, not before
        e6 = eid(); state["bodies"][e6] = {"text": MENU.replace("2026-09-25", "2026-09-28"), "html": ""}; state["fail"].add(e6)
        assert (await post(e6)).status_code == 502
        await db.inbound_emails.update_one({"provider_message_id": e6}, {"$set": {"retryable": False, "status": "retrying", "retry_started_at": email_inbound.now_utc().isoformat()}})
        state["fail"].discard(e6)
        assert (await post(e6)).json()["status"] == "duplicate"
        await db.inbound_emails.update_one({"provider_message_id": e6}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
        assert (await post(e6)).json()["status"] == "routed"

        # 7) two simultaneous FIRST deliveries create one row
        e7 = eid(); state["bodies"][e7] = {"text": MENU.replace("2026-09-25", "2026-09-29"), "html": ""}; state["delay"] = 0.1
        before = await uploads()
        rs = await asyncio.gather(*[post(e7) for _ in range(4)]); state["delay"] = 0.0
        assert await db.inbound_emails.count_documents({"provider_message_id": e7}) == 1
        assert sum(1 for x in rs if x.status_code == 200 and x.json()["status"] == "routed") <= 1
        assert await uploads() - before <= 1
    print("OK")
    await db.client.drop_database(os.environ["DB_NAME"])


if __name__ == "__main__" and "--isolated" in sys.argv:
    asyncio.run(run())
