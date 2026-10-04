"""SIM-1: the minimal simulated-actor scheduler, proven against the canonical
request / lifecycle / receipt services (docs/CAOSCARE_OPERATIONS_SIMULATOR.md §9).

Acceptance (one test or assertion block each):
 1 simulator starts                      7 step executes exactly one action
 2 simulated resident -> canonical request 8 resume continues
 3 request has an origin receipt         9 stop prevents further actions
 4 simulated staff acts on that request 10 history remains after stop
 5 lifecycle receipts chain to origin   11 real / simulated identity cannot be confused
 6 pause prevents the next scheduled action

In-process and DB-direct (no backend server needed). Demo room only (Round 5
scope): the demo room's synthetic resident (ensure_demo_room) and the
simulated staff id sim:staff:maintenance-1; other records are tagged with this
run. Refuses to run against the live `caoscare` DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_sim1_test \
      JWT_SECRET=x pytest tests/test_sim1_actor_scheduler.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("SIM-1 tests write simulator records; point DB_NAME at a scratch database",
                allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.demo_kiosk import DEMO_ROOM, ensure_demo_room  # noqa: E402
from simulation import roster, scenario, scheduler  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402

TAG = f"sim1_{uuid.uuid4().hex[:8]}"
ADMIN = {"user_id": f"{TAG}_admin", "name": f"{TAG} operator", "role": "admin"}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def operator():
    return actor_from_user(ADMIN), "admin_override:admin"


DEMO = {}


async def _reset():
    """Scratch-DB reset of SIM-1 state only: stop any active run, remove the
    demo resident's requests and any planted conflict records."""
    for t in scheduler._loops.values():
        t.cancel()
    scheduler._loops.clear()
    await db.sim_runs.update_many({"state": {"$in": list(scheduler.ACTIVE)}},
                                  {"$set": {"state": scheduler.STOPPED}})
    await db.residents.delete_many({"room": DEMO_ROOM, "resident_id": {"$regex": f"^{TAG}"}})
    DEMO.update(await ensure_demo_room())
    await db.residents.update_one({"resident_id": DEMO["resident_id"]}, {"$set": {"synthetic": True}})
    await db.staff_tasks.delete_many({"resident_id": DEMO["resident_id"]})
    await db.users.delete_many({"user_id": roster.STAFF["actor_id"]})
    await seed_default_departments()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(notifications, "RESEND_KEY", "")
    run(_reset())
    yield
    run(_reset())


async def task_of(task_id):
    return await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})


async def request_chain(task_id):
    return await db.receipts.find({"related_object_type": "task", "related_object_id": task_id},
                                  {"_id": 0}).to_list(100)


async def receipt(rid):
    return await db.receipts.find_one({"receipt_id": rid}, {"_id": 0})


async def walk(last_id):
    """Follow parent links from a chain's latest receipt back to its origin."""
    out, rid = [], last_id
    while rid:
        r = await receipt(rid)
        assert r, f"chain broken: receipt {rid} missing"
        out.append(r)
        rid = r.get("parent_receipt_id")
    return list(reversed(out))


def assert_simulated_actor(r, actor_id):
    assert r["actor_id"] == actor_id
    assert r["actor_type"] == "simulated-agent" and r["identity_basis"] == "synthetic"
    assert r["simulated"] is True


def test_sim1_lifecycle_controls_and_history():
    async def go():
        op, auth = operator()
        # 1. starts
        started = await scheduler.start(op, auth)
        assert started["state"] == "RUNNING" and started["cursor"] == 0
        origin_run = await receipt(started["origin_receipt_id"])
        assert origin_run["action_type"] == "sim_run_started"
        assert origin_run["actor_id"] == ADMIN["user_id"] and origin_run["actor_type"] == "real-human"
        assert origin_run["correlation_id"] == origin_run["receipt_id"]

        # 2-3. the simulated resident raises a normal request with an origin receipt
        out = await scheduler.tick()
        assert out["executed"] and out["step"]["action"] == "raise_request"
        tid = out["task_id"]
        t = await task_of(tid)
        assert t["category"] == "maintenance" and t["visibility_role"] == "maintenance"
        assert t["status"] == "pending" and t["simulated"] is True and t["simulation_scope"] == "demo_room"
        assert t["resident_id"] == DEMO["resident_id"] and t["room"] == DEMO_ROOM
        origin = await receipt(out["canonical_receipt_id"])
        assert origin["action_type"] == "resident_request_created"
        assert origin["correlation_id"] == origin["receipt_id"] and origin["parent_receipt_id"] is None
        assert_simulated_actor(origin, DEMO["resident_id"])
        step_rcpt = await receipt(out["step_receipt_id"])
        assert step_rcpt["provider_refs"] == [origin["receipt_id"]]
        assert step_rcpt["correlation_id"] == started["origin_receipt_id"]

        # 4-5. the simulated staff member acts on that same request; receipt chains to origin
        out = await scheduler.tick()
        assert out["step"]["action"] == "acknowledge" and out["task_id"] == tid
        ack = await receipt(out["canonical_receipt_id"])
        assert ack["action_type"] == "task_acknowledged"
        assert ack["parent_receipt_id"] == origin["receipt_id"] and ack["correlation_id"] == origin["receipt_id"]
        assert ack["authority"] == "acts_for:maintenance" and ack["channel"] == "simulator"
        assert_simulated_actor(ack, roster.STAFF["actor_id"])
        assert (await task_of(tid))["acknowledged_by"] == roster.STAFF["actor_id"]

        # 6. pause prevents the next scheduled action
        await scheduler.pause(op, auth)
        before = len(await request_chain(tid))
        assert await scheduler.tick() is None
        assert len(await request_chain(tid)) == before
        assert (await scheduler.active_run())["cursor"] == 2

        # 7. step executes exactly one action and stays paused
        out = await scheduler.step(op, auth)
        assert out["executed"] and out["step"]["action"] == "start"
        assert len(await request_chain(tid)) == before + 1
        r = await scheduler.active_run()
        assert r["cursor"] == 3 and r["state"] == "PAUSED"
        t = await task_of(tid)
        assert t["status"] == "in_progress" and t["assigned_to"] == roster.STAFF["actor_id"]
        assert (await receipt(out["step_receipt_id"]))["actor_id"] == ADMIN["user_id"]   # operator stepped

        # 8. resume continues
        await scheduler.resume(op, auth)
        out = await scheduler.tick()
        assert out["step"]["action"] == "note"
        note_rid = out["canonical_receipt_id"]
        assert (await receipt(note_rid))["action_type"] == "task_note_added"

        # 9. stop prevents further actions
        stopped = await scheduler.stop(op, auth)
        assert stopped["state"] == "STOPPED"
        n = len(await request_chain(tid))
        assert await scheduler.tick() is None
        for control in (scheduler.step, scheduler.resume, scheduler.pause):
            with pytest.raises(scheduler.SimulatorError) as e:
                await control(op, auth)
            assert e.value.status_code == 409
        assert len(await request_chain(tid)) == n
        assert (await task_of(tid))["status"] == "in_progress"           # left as it was, not closed

        # 10. history remains after stop: run, request, both chains, unbroken
        hist = await scheduler.history(started["run_id"])
        assert hist["run"]["state"] == "STOPPED" and hist["run"]["cursor"] == 4
        run_chain = await walk(hist["run"]["last_receipt_id"])
        assert run_chain[0]["receipt_id"] == started["origin_receipt_id"]
        kinds = [r["action_type"] for r in run_chain]
        assert kinds[:1] == ["sim_run_started"] and kinds[-6:] == [
            "sim_step_executed", "sim_run_paused", "sim_step_executed", "sim_run_resumed",
            "sim_step_executed", "sim_run_stopped"]
        assert kinds.count("sim_step_executed") == 4
        assert {r["receipt_id"] for r in hist["run_chain"]} == {r["receipt_id"] for r in run_chain}
        req = await walk(note_rid)
        assert {r["receipt_id"] for r in hist["request_chain"]} == {r["receipt_id"] for r in req}
        assert [r["action_type"] for r in req] == [
            "resident_request_created", "task_acknowledged", "task_in_progress", "task_note_added"]
        assert all(r["correlation_id"] == origin["receipt_id"] for r in req)
        # every canonical receipt is referenced by exactly one run step receipt
        refs = [ref for r in run_chain for ref in r["provider_refs"]]
        assert sorted(refs) == sorted(r["receipt_id"] for r in req)
        # every task history entry carries an existing receipt
        for entry in (await task_of(tid))["event_log"]:
            assert entry.get("receipt_id") and await receipt(entry["receipt_id"])
    run(go())


def test_sim1_runs_to_completion():
    async def go():
        op, auth = operator()
        started = await scheduler.start(op, auth)
        outs = []
        while (o := await scheduler.tick()) is not None:
            outs.append(o)
        assert [o["step"]["action"] for o in outs] == [s["action"] for s in scenario.STEPS]
        tid = outs[0]["task_id"]
        t = await task_of(tid)
        assert t["status"] == "completed" and t["completed_by"] == roster.STAFF["actor_id"]
        chain = await walk(outs[-1]["canonical_receipt_id"])
        assert [r["action_type"] for r in chain] == [
            "resident_request_created", "task_acknowledged", "task_in_progress", "task_note_added",
            "task_completed"]
        run_doc = (await scheduler.history(started["run_id"]))["run"]
        assert run_doc["state"] == "STOPPED"
        assert (await receipt(run_doc["last_receipt_id"]))["action_type"] == "sim_run_completed"
        assert await scheduler.active_run() is None
    run(go())


def test_sim1_background_loop_obeys_pause():
    async def go():
        op, auth = operator()
        started = await scheduler.start(op, auth)
        scheduler.ensure_loop(started["run_id"], interval=0.05)
        for _ in range(100):
            if (await scheduler.active_run())["cursor"] >= 2:
                break
            await asyncio.sleep(0.05)
        await scheduler.pause(op, auth)
        held = (await scheduler.active_run())["cursor"]
        assert held >= 2
        await asyncio.sleep(0.4)
        assert (await scheduler.active_run())["cursor"] == held
        assert not scheduler.loop_alive(started["run_id"])
        await scheduler.stop(op, auth)
    run(go())


def test_sim1_real_and_simulated_identity_cannot_be_confused():
    async def go():
        op, auth = operator()
        # a real request through the same bus: real-human room claim, not simulated
        real = await create_resident_request(ResidentRequestInput(
            category="maintenance", room=f"{TAG}-REAL", summary="Light is out", source="aria_voice"))
        real_rcpt = await receipt(real["receipt_id"])
        assert real_rcpt["actor_type"] == "real-human" and real_rcpt["simulated"] is False
        assert (await task_of(real["task_id"]))["simulated"] is False
        # a simulated actor refuses to act on real work; nothing changes
        before = await task_of(real["task_id"])
        with pytest.raises(RuntimeError, match="not simulated"):
            await scenario.execute(scenario.STEPS[1], {"task_id": real["task_id"]}, {})
        assert await task_of(real["task_id"]) == before
        # the simulated staff member is not a user and cannot sign in
        assert await db.users.find_one({"user_id": roster.STAFF["actor_id"]}) is None
        staff = roster.staff_actor()
        assert staff.simulated and staff.actor_type == "simulated-agent" and staff.identity_basis == "synthetic"

        # a real resident in the demo room blocks the start; the refusal is recorded
        squatter = {"resident_id": f"{TAG}_real", "name": f"{TAG} Real Person", "room": DEMO_ROOM,
                    "pendant_id": "x", "synthetic": False}
        await db.residents.insert_one(dict(squatter))
        with pytest.raises(scheduler.SimulatorError) as e:
            await scheduler.start(op, auth)
        assert e.value.status_code == 409 and "identity conflict" in e.value.detail
        assert await scheduler.active_run() is None
        assert (await db.residents.find_one({"resident_id": squatter["resident_id"]}, {"_id": 0}))["synthetic"] is False
        refused = await db.receipts.find_one({"action_type": "sim_run_start_refused", "actor_id": ADMIN["user_id"]},
                                             {"_id": 0}, sort=[("created_at", -1)])
        assert refused and "identity conflict" in refused["failure_reason"]
        await db.residents.delete_one({"resident_id": squatter["resident_id"]})

        # the demo resident itself no longer marked synthetic: refused
        await db.residents.update_one({"resident_id": DEMO["resident_id"]}, {"$set": {"synthetic": False}})
        with pytest.raises(scheduler.SimulatorError):
            await scheduler.start(op, auth)
        await db.residents.update_one({"resident_id": DEMO["resident_id"]}, {"$set": {"synthetic": True}})

        # a real user record on the simulated staff id blocks it too
        await db.users.insert_one({"user_id": roster.STAFF["actor_id"], "name": "real", "role": "staff"})
        with pytest.raises(scheduler.SimulatorError):
            await scheduler.start(op, auth)
        await db.users.delete_one({"user_id": roster.STAFF["actor_id"]})

        # a simulated run's receipts: operator real-human, every simulated actor explicit
        started = await scheduler.start(op, auth)
        while await scheduler.tick():
            pass
        hist = await scheduler.history(started["run_id"])
        for r in hist["request_chain"]:
            assert r["simulated"] is True and r["actor_type"] == "simulated-agent"
            assert r["actor_id"] in (DEMO["resident_id"], roster.STAFF["actor_id"])
        for r in hist["run_chain"]:
            assert r["actor_type"] in ("real-human", "system") and r["simulated"] is False
    run(go())


def test_sim1_refuses_start_with_live_email_provider(monkeypatch):
    async def go():
        monkeypatch.setattr(notifications, "RESEND_KEY", "re_live_key")
        with pytest.raises(scheduler.SimulatorError) as e:
            await scheduler.start(*operator())
        assert "email provider" in e.value.detail
        assert await scheduler.active_run() is None
    run(go())


def test_sim1_http_controls(monkeypatch):
    import httpx
    from fastapi import FastAPI
    from deps import require_admin
    from routes import simulation as sim_routes

    monkeypatch.setattr(scheduler, "TICK_SECONDS", 3600)    # drive it by Step only
    app = FastAPI()
    app.include_router(sim_routes.router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: ADMIN

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            s = (await c.post("/api/simulator/start")).json()
            assert s["state"] == "RUNNING" and s["loop_alive"] is True
            assert (await c.post("/api/simulator/step")).status_code == 409      # only while paused
            assert (await c.post("/api/simulator/pause")).json()["state"] == "PAUSED"
            stepped = (await c.post("/api/simulator/step")).json()
            assert stepped["cursor"] == 1 and stepped["step_result"]["executed"] is True
            assert (await c.post("/api/simulator/resume")).json()["state"] == "RUNNING"
            assert (await c.post("/api/simulator/stop")).json()["state"] == "STOPPED"
            state = (await c.get("/api/simulator/state")).json()
            assert state["state"] == "STOPPED" and state["next_step"] is None
            hist = (await c.get(f"/api/simulator/runs/{s['run_id']}/history")).json()
            assert [r["action_type"] for r in hist["request_chain"]] == ["resident_request_created"]
            ops = {r["action_type"]: r for r in hist["run_chain"]}
            assert ops["sim_run_stopped"]["actor_id"] == ADMIN["user_id"]
            assert ops["sim_run_stopped"]["authority"] == "admin_override:admin"
    run(go())
