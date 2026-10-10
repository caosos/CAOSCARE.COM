"""Resend delivery events must never let a weaker/late event overwrite a terminal outcome, even when events race.
Deterministic interleaving (both events read the notification before either writes; one write is held back) through
the signed webhook route, isolated real Mongo, no provider. A simulated webhook is evidence the status logic works,
not proof that Resend delivered anything."""
import asyncio, json, os, subprocess, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_email_inbound import TEST_SECRET, _sign  # noqa: E402


def test_delivery_event_race():
    env = {**os.environ, "DB_NAME": f"caos_delivery_race_test_{uuid.uuid4().hex[:10]}", "RESEND_WEBHOOK_SECRET": TEST_SECRET}
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--isolated"], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


async def run():
    assert os.environ["DB_NAME"].startswith("caos_delivery_race_test_")
    import httpx
    from deps import db
    from fastapi import FastAPI
    from routes import notification_delivery, email_inbound

    real = notification_delivery.db
    cfg = {"barrier": 0, "slow": set()}   # barrier: how many readers must arrive before any proceeds; slow: statuses whose write is held back
    arrived, release = [], asyncio.Event()

    class Coll:
        def __init__(self, c): self.c = c
        async def find_one(self, *a, **k):
            doc = await self.c.find_one(*a, **k)
            if cfg["barrier"]:
                arrived.append(1)
                if len(arrived) >= cfg["barrier"]:
                    release.set()
                await release.wait()
            return doc
        async def update_one(self, flt, upd, *a, **k):
            st = (upd.get("$set") or {}).get("status")
            if st in cfg["slow"]:
                await asyncio.sleep(0.15)
            return await self.c.update_one(flt, upd, *a, **k)
        def __getattr__(self, n): return getattr(self.c, n)

    class DBProxy:
        notifications = Coll(real.notifications)
        def __getattr__(self, n): return getattr(real, n)
    notification_delivery.db = DBProxy()

    app = FastAPI(); app.include_router(email_inbound.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
        async def post(etype, eid, data=None):
            body = json.dumps({"type": etype, "created_at": "2026-10-10T12:00:00Z", "data": {"email_id": eid, **(data or {})}}).encode()
            sid, ts = f"msg_{uuid.uuid4().hex[:8]}", str(int(time.time()))
            return await c.post("/email/inbound/resend", content=body, headers={
                "content-type": "application/json", "svix-id": sid, "svix-timestamp": ts, "svix-signature": _sign(TEST_SECRET, sid, ts, body)})

        async def fresh():
            eid = f"re_{uuid.uuid4().hex[:8]}"
            await db.notifications.insert_one({"notification_id": f"n_{eid}", "provider_message_id": eid, "status": "sent", "delivery_events": []})
            return eid

        async def race(events, slow):
            eid = await fresh()
            arrived.clear(); release.clear(); cfg["barrier"] = len(events); cfg["slow"] = set(slow)
            rs = await asyncio.gather(*[post(t, eid, d) for t, d in events])
            cfg["barrier"] = 0; cfg["slow"] = set()
            assert all(r.status_code == 200 and r.json()["matched"] for r in rs), [r.text for r in rs]
            return await db.notifications.find_one({"provider_message_id": eid}, {"_id": 0})

        # A) delayed and delivered race; the DELAYED write lands last: delivered must survive
        n = await race([("email.delivery_delayed", None), ("email.delivered", None)], slow={"delayed"})
        assert n["status"] == "delivered" and sorted(e["type"] for e in n["delivery_events"]) == ["email.delivered", "email.delivery_delayed"], n
        # B) the other order: delivered write held back, delayed lands first
        n = await race([("email.delivery_delayed", None), ("email.delivered", None)], slow={"delivered"})
        assert n["status"] == "delivered" and len(n["delivery_events"]) == 2, n
        # C) concurrent duplicate delivered events: stays delivered; each delivery is still recorded as received
        n = await race([("email.delivered", None), ("email.delivered", None)], slow=set())
        assert n["status"] == "delivered" and [e["type"] for e in n["delivery_events"]] == ["email.delivered"] * 2, n
        # D) two terminal outcomes racing: the first to land stays, the other never overwrites it; both recorded
        n = await race([("email.bounced", {"bounce": {"type": "Permanent"}}), ("email.delivered", None)], slow={"delivered"})
        assert n["status"] == "bounced" and len(n["delivery_events"]) == 2, n
        n = await race([("email.bounced", {"bounce": {"type": "Permanent"}}), ("email.delivered", None)], slow={"bounced"})
        assert n["status"] == "delivered" and len(n["delivery_events"]) == 2, n
        # E) sequential, unchanged semantics: sent -> delayed -> delivered advances; terminal then delayed stays terminal
        eid = await fresh()
        assert (await post("email.delivery_delayed", eid)).json()["notification_status"] == "delayed"
        assert (await post("email.delivered", eid)).json()["notification_status"] == "delivered"
        r = await post("email.delivery_delayed", eid)
        assert r.json()["notification_status"] == "delivered"
        n = await db.notifications.find_one({"provider_message_id": eid}, {"_id": 0})
        assert n["status"] == "delivered" and len(n["delivery_events"]) == 3
        # F) an event with no status mapping (email.sent) only appends history; unknown id unmatched
        eid = await fresh(); assert (await post("email.sent", eid)).json()["notification_status"] == "sent"
        assert (await post("email.delivered", "re_unknown")).json()["matched"] is False
    print("OK")
    await db.client.drop_database(db.name)


if __name__ == "__main__" and "--isolated" in sys.argv:
    asyncio.run(run())
