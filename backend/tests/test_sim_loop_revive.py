"""A RUNNING simulator run gets its scheduler loop back when the state is
read after a backend restart (loops live in the process). PAUSED runs are not
revived. Scratch DB only.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_simloop_test \
      JWT_SECRET=x pytest tests/test_sim_loop_revive.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes simulator records; point DB_NAME at a scratch database", allow_module_level=True)

import httpx  # noqa: E402

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402
from routes.demo_kiosk import ensure_demo_room  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from simulation import scheduler  # noqa: E402

TAG = f"simloop_{uuid.uuid4().hex[:8]}"
ADMIN = {"user_id": f"{TAG}_admin", "email": f"{TAG}@example.com", "name": "Operator", "role": "admin",
         "auth_provider": "jwt"}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _forget_loops():
    """What a backend restart does: the process's loops are gone."""
    for t in scheduler._loops.values():
        t.cancel()
    scheduler._loops.clear()


async def _reset():
    _forget_loops()
    await db.sim_runs.update_many({"state": {"$in": list(scheduler.ACTIVE)}}, {"$set": {"state": scheduler.STOPPED}})
    demo = await ensure_demo_room()
    await db.staff_tasks.delete_many({"resident_id": demo["resident_id"]})
    await db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})
    await db.users.insert_one({**ADMIN, "created_at": "2026-10-06T00:00:00+00:00"})
    await seed_default_departments()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setattr(scheduler, "TICK_SECONDS", 3600)   # revived loop must not tick during the test
    run(_reset())
    yield
    run(_reset())
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))


def test_running_run_gets_its_loop_back_on_state_read():
    async def go():
        from server import app
        hdr = {"Authorization": f"Bearer {_issue_jwt(ADMIN['user_id'])}"}
        started = await scheduler.start(actor_from_user(ADMIN), "admin_override:admin")
        _forget_loops()                                            # "restart"
        assert not scheduler.loop_alive(started["run_id"])
        before = await db.receipts.count_documents({})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            v = (await c.get("/api/simulator/state", headers=hdr)).json()
            assert v["state"] == "RUNNING" and v["loop_alive"] is True
            assert v["cursor"] == 0                                # nothing executed by the revival
            assert await db.receipts.count_documents({}) == before   # no state change, no receipt
            # a second read does not create a second loop
            task = scheduler._loops[started["run_id"]]
            await c.get("/api/simulator/state", headers=hdr)
            assert scheduler._loops[started["run_id"]] is task
            # a paused run is never revived
            await scheduler.pause(actor_from_user(ADMIN), "admin_override:admin")
            _forget_loops()
            v = (await c.get("/api/simulator/state", headers=hdr)).json()
            assert v["state"] == "PAUSED" and v["loop_alive"] is False
        await scheduler.stop(actor_from_user(ADMIN), "admin_override:admin")
    run(go())
