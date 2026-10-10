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

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://localhost") as c:
        async def post(eid, frm="chef@thefacility.com", to="menu@inbound.caoscare.com"):
            body = json.dumps({"type": "email.received", "created_at": "2026-09-19T12:00:00.000Z",
                               "data": {"email_id": eid, "from": frm, "to": [to], "subject": "x", "attachments": []}}).encode()
            sid, ts = f"msg_{uuid.uuid4().hex[:8]}", str(int(time.time()))
            sig = "v1," + base64.b64encode(hmac.new(base64.b64decode(SECRET[6:]), f"{sid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
            return await c.post("/email/inbound/resend", content=body, headers={
                "content-type": "application/json", "svix-id": sid, "svix-timestamp": ts, "svix-signature": sig})

        # 0) required uniqueness unavailable -> fail closed (503), nothing written; legacy duplicates are never altered
        eid0 = "email_legacy_dup"
        await db.inbound_emails.insert_many([{"inbound_id": f"legacy{i}", "provider_message_id": eid0, "status": "routed", "from_address": "x@y.z", "to_addresses": []} for i in range(2)])
        state["bodies"][eid0] = {"text": MENU, "html": ""}
        r = await post("email_other_1")
        assert r.status_code == 503 and "manual migration" in r.text, (r.status_code, r.text)
        assert await db.inbound_emails.count_documents({"provider_message_id": eid0}) == 2   # legacy rows untouched
        assert await db.inbound_emails.count_documents({"provider_message_id": "email_other_1"}) == 0
        assert email_inbound._index_ready is False   # not remembered as ready
        await db.inbound_emails.delete_many({"provider_message_id": eid0})   # the "manual migration"
        state["bodies"]["email_other_1"] = {"text": MENU, "html": ""}
        assert (await post("email_other_1")).json()["status"] == "routed" and email_inbound._index_ready is True
        await db.menu_uploads.delete_many({}); await db.menu_items.delete_many({})

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
        kinds = sorted(str(x.json()["status"] if x.status_code == 200 else x.status_code) for x in rs)
        assert kinds.count("routed") == 1 and kinds.count("409") == 5, kinds   # in-flight is retryable, not a "duplicate"
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
        assert (await post(e6)).status_code == 409   # fresh in-flight claim: retryable, not a duplicate
        await db.inbound_emails.update_one({"provider_message_id": e6}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
        assert (await post(e6)).json()["status"] == "routed"

        # 7) two simultaneous FIRST deliveries create one row
        e7 = eid(); state["bodies"][e7] = {"text": MENU.replace("2026-09-25", "2026-09-29"), "html": ""}; state["delay"] = 0.1
        before = await uploads()
        rs = await asyncio.gather(*[post(e7) for _ in range(4)]); state["delay"] = 0.0
        assert await db.inbound_emails.count_documents({"provider_message_id": e7}) == 1
        kinds = sorted(str(x.json()["status"] if x.status_code == 200 else x.status_code) for x in rs)
        assert kinds.count("routed") == 1 and kinds.count("409") == 3 and len(kinds) == 4, kinds
        assert await uploads() - before == 1 and state["calls"][e7] == 1
        assert len([r for r in await receipts((await db.inbound_emails.find_one({"provider_message_id": e7}))["inbound_id"]) if r == "inbound_email.routed"]) == 1

        # 8) crash AFTER the domain output exists but BEFORE the inbound row is finalized: reclaim reconciles, one output
        real_record = email_inbound._record_outcome
        crash = {"on": True}
        async def flaky(inbound_id, **patch):
            if crash["on"] and patch.get("status") == "routed":
                crash["on"] = False
                raise RuntimeError("simulated crash before finalization")
            return await real_record(inbound_id, **patch)
        email_inbound._record_outcome = flaky
        for lane_to, frm, body, kind in [
            ("menu@inbound.caoscare.com", "chef@thefacility.com", MENU.replace("2026-09-25", "2026-10-01"), "menu"),
            ("activities@inbound.caoscare.com", "programs@thefacility.com", "Monday 2026-09-28:\n10:00 AM Chair Yoga - Sunroom\n2:00 PM Bingo [activity]\n", "act")]:
            crash["on"] = True
            e8 = eid(); state["bodies"][e8] = {"text": body, "html": ""}
            assert (await post(e8, frm=frm, to=lane_to)).status_code == 500
            row = await db.inbound_emails.find_one({"provider_message_id": e8}, {"_id": 0}); iid = row["inbound_id"]
            assert row["status"] == "received"   # never finalized
            if kind == "menu":
                assert await db.menu_uploads.count_documents({"source_ref": iid}) == 1
            else:
                assert await db.schedule_items.count_documents({"source_ref": iid}) == 2
            blocked = await post(e8, frm=frm, to=lane_to)   # fresh in-flight claim blocks a second run, retryably
            assert blocked.status_code == 409 and "in_progress" in blocked.text
            await db.inbound_emails.update_one({"provider_message_id": e8}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
            r = await post(e8, frm=frm, to=lane_to); assert r.status_code == 200 and r.json()["status"] == "routed", r.text
            assert r.json()["inbound_id"] == iid
            if kind == "menu":
                assert await db.menu_uploads.count_documents({"source_ref": iid}) == 1
                up = await db.menu_uploads.find_one({"source_ref": iid}, {"_id": 0})
                assert await db.menu_items.count_documents({"upload_id": up["upload_id"]}) == 6
                assert r.json()["linked_object_id"] == up["upload_id"]
                ro, rt = up["upload_id"], "menu_upload"
            else:
                assert await db.schedule_items.count_documents({"source_ref": iid}) == 2
                assert r.json()["linked_object_id"] == (await db.schedule_items.find_one({"source_ref": iid}))["ingest_id"]
                ro, rt = r.json()["linked_object_id"], "schedule_batch"
            assert await db.receipts.count_documents({"related_object_type": rt, "related_object_id": ro}) == 1   # content receipt not repeated
            assert (await receipts(iid)).count("inbound_email.routed") == 1
            assert (await post(e8, frm=frm, to=lane_to)).json()["status"] == "duplicate"
        # 8b) output written but its content receipt lost in the crash: reconcile adds exactly the missing receipt
        e9 = eid(); state["bodies"][e9] = {"text": MENU.replace("2026-09-25", "2026-10-02"), "html": ""}
        crash["on"] = True
        assert (await post(e9)).status_code == 500
        iid9 = (await db.inbound_emails.find_one({"provider_message_id": e9}))["inbound_id"]
        await db.receipts.delete_many({"related_object_type": "menu_upload", "related_object_id": f"mupload_{iid9}"})
        await db.inbound_emails.update_one({"provider_message_id": e9}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
        assert (await post(e9)).json()["status"] == "routed"
        assert await db.receipts.count_documents({"related_object_type": "menu_upload", "related_object_id": f"mupload_{iid9}"}) == 1
        assert await db.menu_uploads.count_documents({"source_ref": iid9}) == 1
        # 8c) half-written menu (items but no upload) is repaired without duplicates
        e10 = eid(); state["bodies"][e10] = {"text": MENU.replace("2026-09-25", "2026-10-03"), "html": ""}
        crash["on"] = True
        assert (await post(e10)).status_code == 500
        iid10 = (await db.inbound_emails.find_one({"provider_message_id": e10}))["inbound_id"]
        await db.menu_uploads.delete_many({"upload_id": f"mupload_{iid10}"})   # simulate upload doc never written
        await db.inbound_emails.update_one({"provider_message_id": e10}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
        assert (await post(e10)).json()["status"] == "routed"
        assert await db.menu_items.count_documents({"upload_id": f"mupload_{iid10}"}) == 6
        email_inbound._record_outcome = real_record

        # 9) crash after ONE of TWO activities was inserted: retry completes only the missing row, no replay, no deletion
        from routes import schedule_ingest
        real_db = schedule_ingest.db
        class Coll:
            def __init__(self, c): self.c = c
            async def insert_many(self, docs, *a, **k):
                await self.c.insert_one(dict(docs[0])); raise RuntimeError("simulated crash after the first row")
            def __getattr__(self, n): return getattr(self.c, n)
        class DBProxy:
            schedule_items = Coll(real_db.schedule_items)
            def __getattr__(self, n): return getattr(real_db, n)
        TWO = "Monday 2026-09-28:\n10:00 AM Chair Yoga - Sunroom\n2:00 PM Bingo [activity]\n"
        e9a = eid(); state["bodies"][e9a] = {"text": TWO, "html": ""}
        schedule_ingest.db = DBProxy()
        assert (await post(e9a, frm="programs@thefacility.com", to="activities@inbound.caoscare.com")).status_code == 500
        schedule_ingest.db = real_db
        iid = (await db.inbound_emails.find_one({"provider_message_id": e9a}))["inbound_id"]; ing = f"sched_ingest_{iid}"
        first = await db.schedule_items.find({"ingest_id": ing}, {"_id": 0}).to_list(10)
        assert [r["schedule_id"] for r in first] == [f"{ing}_0"]
        await db.inbound_emails.update_one({"provider_message_id": e9a}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
        r = await post(e9a, frm="programs@thefacility.com", to="activities@inbound.caoscare.com")
        assert r.status_code == 200 and r.json()["status"] == "routed" and r.json()["inbound_id"] == iid, r.text
        rows = await db.schedule_items.find({"ingest_id": ing}, {"_id": 0}).sort("schedule_id", 1).to_list(10)
        assert [x["schedule_id"] for x in rows] == [f"{ing}_0", f"{ing}_1"]
        assert rows[0] == first[0]   # the earlier row is byte-identical: not replaced, not rewritten
        assert {x["title"] for x in rows} == {"Chair Yoga", "Bingo"}
        assert await db.receipts.count_documents({"related_object_type": "schedule_batch", "related_object_id": ing}) == 1
        assert (await receipts(iid)).count("inbound_email.routed") == 1

        # 9b) rows we cannot account for -> hold for a person (not routed), nothing deleted, final
        e9b = eid(); state["bodies"][e9b] = {"text": TWO, "html": ""}
        crash["on"] = True; email_inbound._record_outcome = flaky
        assert (await post(e9b, frm="programs@thefacility.com", to="activities@inbound.caoscare.com")).status_code == 500
        email_inbound._record_outcome = real_record
        iidb = (await db.inbound_emails.find_one({"provider_message_id": e9b}))["inbound_id"]; ingb = f"sched_ingest_{iidb}"
        await db.schedule_items.insert_one({"schedule_id": "stray_row", "ingest_id": ingb, "date": "2026-09-28", "title": "Mystery", "status": "draft"})
        await db.inbound_emails.update_one({"provider_message_id": e9b}, {"$set": {"retry_started_at": "2000-01-01T00:00:00+00:00"}})
        r = await post(e9b, frm="programs@thefacility.com", to="activities@inbound.caoscare.com")
        assert r.status_code == 200 and r.json()["status"] == "reconciliation_required", r.text
        row = await db.inbound_emails.find_one({"provider_message_id": e9b}, {"_id": 0})
        assert row["status"] == "reconciliation_required" and not row.get("retryable") and not row.get("linked_object_id")
        assert await db.schedule_items.count_documents({"ingest_id": ingb}) == 3   # 2 written before the hold + stray, none deleted
        assert (await post(e9b, frm="programs@thefacility.com", to="activities@inbound.caoscare.com")).json()["status"] == "duplicate"
        assert "inbound_email.routed" not in await receipts(iidb)

        # 10) an early concurrent delivery during a slow attempt that then FAILS: not a 200 "duplicate"; the later retry recovers
        e10x = eid(); state["bodies"][e10x] = {"text": MENU.replace("2026-09-25", "2026-10-04"), "html": ""}; state["fail"].add(e10x)
        state["delay"] = 0.4
        orig = asyncio.create_task(post(e10x)); await asyncio.sleep(0.15)
        early = await post(e10x)
        assert early.status_code == 409 and "in_progress" in early.text and early.headers.get("retry-after") == "60"
        first = await orig; state["delay"] = 0.0
        assert first.status_code == 502
        state["fail"].discard(e10x)
        rr = await post(e10x); assert rr.status_code == 200 and rr.json()["status"] == "routed", rr.text
        assert await db.menu_uploads.count_documents({"source_ref": rr.json()["inbound_id"]}) == 1
        assert (await post(e10x)).json()["status"] == "duplicate"   # terminal success -> true duplicate
    print("OK")
    await db.client.drop_database(os.environ["DB_NAME"])


if __name__ == "__main__" and "--isolated" in sys.argv:
    asyncio.run(run())
