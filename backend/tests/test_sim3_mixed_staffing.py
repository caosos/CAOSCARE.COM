"""SIM-3: mixed real + simulated staffing (docs/CAOSCARE_OPERATIONS_SIMULATOR.md §9).

A simulated resident raises a canonical request; the maintenance role is
handed to a REAL signed-in user who works it through the normal staff routes
(claim, start, note, complete). The simulator observes the real receipts and
continues from that state. Proves:
 1 a simulated role is scheduled normally
 2 the role can be handed to a real authenticated user
 3 the simulated request reaches that real user (normal staff task list)
 4 claim / start / note / complete work through the normal lifecycle routes
 5 those receipts identify the real actor (authenticated, real-human)
 6 the simulator sees the completion (observed steps cite the real receipts)
 7 the simulator continues afterwards from the real state
 8 the simulator cannot act as / for the real user, and records nothing while waiting
 9 returning the role to the simulated actor resumes simulated work from the current state
10 exactly one request exists for the run

In-process scheduler calls plus the real FastAPI app over ASGI with real JWTs
(no auth overrides). Demo room only; refuses to run against the live DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_sim3_test \
      JWT_SECRET=x pytest tests/test_sim3_mixed_staffing.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("SIM-3 tests write simulator records; point DB_NAME at a scratch database",
                allow_module_level=True)

import httpx  # noqa: E402

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402
from routes.demo_kiosk import ensure_demo_room  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from simulation import roster, scenario, scheduler  # noqa: E402

TAG = f"sim3_{uuid.uuid4().hex[:8]}"
ADMIN = {"user_id": f"{TAG}_admin", "email": f"{TAG}_admin@example.com", "name": f"{TAG} Operator",
         "role": "admin", "auth_provider": "jwt"}
MICHAEL = {"user_id": f"{TAG}_michael", "email": f"{TAG}_michael@example.com", "name": "Michael (test)",
           "role": "staff", "department": "maintenance", "auth_provider": "jwt"}
HOUSEKEEPER = {"user_id": f"{TAG}_hk", "email": f"{TAG}_hk@example.com", "name": f"{TAG} Housekeeper",
               "role": "staff", "department": "housekeeping", "auth_provider": "jwt"}
ROLE = roster.STAFF["key"]
DEMO = {}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def operator():
    return actor_from_user(ADMIN), "admin_override:admin"


async def _reset():
    for t in scheduler._loops.values():
        t.cancel()
    scheduler._loops.clear()
    await db.sim_runs.update_many({"state": {"$in": list(scheduler.ACTIVE)}}, {"$set": {"state": scheduler.STOPPED}})
    DEMO.update(await ensure_demo_room())
    await db.staff_tasks.delete_many({"resident_id": DEMO["resident_id"]})
    await db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})
    for u in (ADMIN, MICHAEL, HOUSEKEEPER):
        await db.users.insert_one({**u, "created_at": "2026-10-04T00:00:00+00:00"})
    await seed_default_departments()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    run(_reset())
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(_reset())
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))


def client():
    from server import app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def auth(user):
    return {"Authorization": f"Bearer {_issue_jwt(user['user_id'])}"}


async def chain(task_id):
    return await db.receipts.find({"related_object_type": "task", "related_object_id": task_id,
                                   "action_type": {"$not": {"$regex": "_refused$"}}}, {"_id": 0}).to_list(100)


async def receipt(rid):
    return await db.receipts.find_one({"receipt_id": rid}, {"_id": 0})


async def run_receipts(run_id):
    r = await db.sim_runs.find_one({"run_id": run_id}, {"_id": 0})
    return await db.receipts.find({"correlation_id": r["origin_receipt_id"]}, {"_id": 0}).to_list(200)


def test_simulated_role_is_scheduled_normally():
    async def go():
        started = await scheduler.start(*operator())
        assert started["cast"][ROLE]["filled_by"] == {"mode": "simulated"}
        await scheduler.tick()                                   # resident raises the request
        out = await scheduler.tick()                             # simulated tech acknowledges
        assert out["executed"] and out["step"]["action"] == "acknowledge"
        r = await receipt(out["canonical_receipt_id"])
        assert r["actor_id"] == roster.STAFF["actor_id"] and r["actor_type"] == "simulated-agent"
        await scheduler.stop(*operator())
    run(go())


def test_real_user_works_the_simulated_request_and_the_simulator_continues():
    async def go():
        async with client() as c:
            # 2. hand the role to a real user at start, through the operator API
            s = (await c.post("/api/simulator/start", headers=auth(ADMIN),
                              json={"roles": {ROLE: {"mode": "real", "user_id": MICHAEL["user_id"]}}})).json()
            assert s["state"] == "RUNNING"
            assert s["cast"][ROLE]["filled_by"]["mode"] == "real"
            assert s["cast"][ROLE]["filled_by"]["user_id"] == MICHAEL["user_id"]
            run_id = s["run_id"]
            assigned = [r for r in await run_receipts(run_id) if r["action_type"] == "sim_role_assigned"]
            assert len(assigned) == 1 and assigned[0]["actor_id"] == ADMIN["user_id"]

            out = await scheduler.tick()                         # resident raises the request
            tid = out["task_id"]
            before = len(await chain(tid))

            # 8. the role is real: the scheduler waits and records nothing
            for _ in range(3):
                w = await scheduler.tick()
                assert w["executed"] is False and w["waiting"]["user_id"] == MICHAEL["user_id"]
            assert len(await chain(tid)) == before
            assert (await scheduler.active_run())["cursor"] == 1
            assert (await c.get("/api/simulator/state", headers=auth(ADMIN))).json()["waiting_on"]["mode"] == "real"

            # 3. the request reaches the real user through the normal staff task list
            mine = (await c.get("/api/tasks", headers=auth(MICHAEL))).json()
            assert tid in {t["task_id"] for t in mine}

            # 4. claim / start / note / complete through the normal routes
            assert (await c.post(f"/api/tasks/{tid}/assign", headers=auth(MICHAEL),
                                 json={"assigned_to": MICHAEL["user_id"]})).status_code == 200
            assert (await c.post(f"/api/tasks/{tid}/start", headers=auth(MICHAEL))).status_code == 200
            assert (await c.patch(f"/api/tasks/{tid}", headers=auth(MICHAEL),
                                  json={"notes": "Real tech: worn washer."})).status_code == 200
            assert (await c.post(f"/api/tasks/{tid}/complete", headers=auth(MICHAEL),
                                 json={"notes": "Real tech: replaced it."})).status_code == 200

        # 5. the real receipts identify the real actor
        real = [r for r in await chain(tid) if r["actor_id"] == MICHAEL["user_id"]]
        assert [r["action_type"] for r in sorted(real, key=lambda r: r["created_at"])] == [
            "task_assigned", "task_in_progress", "task_note_added", "task_completed"]
        for r in real:
            assert r["actor_type"] == "real-human" and r["identity_basis"] == "authenticated"
            assert r["simulated"] is False and r["channel"] == "staff_ui"
        # 8. nothing in the request chain was done by the simulated tech
        assert not [r for r in await chain(tid) if r["actor_id"] == roster.STAFF["actor_id"]]

        # 6. the simulator observes each staff step, citing the real receipt
        observed = []
        for expected in ("acknowledge", "start", "note", "complete"):
            o = await scheduler.tick()
            assert o["observed"] and o["step"]["action"] == expected
            ref = await receipt(o["canonical_receipt_id"])
            assert ref["actor_id"] == MICHAEL["user_id"]
            observed.append(o)
        assert (await receipt(observed[0]["step_receipt_id"]))["action_type"] == "sim_step_observed"

        # 7. it continues from the real state: the resident asks and is told the real outcome
        o = await scheduler.tick()
        assert o["executed"] and o["step"]["action"] == "check_status"
        step = await receipt(o["step_receipt_id"])
        assert "Michael (test)" in step["result"]
        assert (await db.sim_runs.find_one({"run_id": run_id}))["state"] == "STOPPED"

        # 8. no run receipt was written as the real user except by the real user
        for r in await run_receipts(run_id):
            assert r["actor_id"] in (ADMIN["user_id"], "system:simulator")
        # 10. one request for the run
        assert await db.staff_tasks.count_documents({"simulation_run_id": run_id}) == 1
    run(go())


def test_returning_the_role_resumes_simulated_work_from_the_current_state():
    async def go():
        op, auth_ = operator()
        started = await scheduler.start(op, auth_, roles={ROLE: {"mode": "real", "user_id": MICHAEL["user_id"]}})
        tid = (await scheduler.tick())["task_id"]
        async with client() as c:                                # the real tech claims and starts
            await c.post(f"/api/tasks/{tid}/assign", headers=auth(MICHAEL), json={"assigned_to": MICHAEL["user_id"]})
            await c.post(f"/api/tasks/{tid}/start", headers=auth(MICHAEL))
            # 9. the operator returns the role to the simulated actor
            v = (await c.post(f"/api/simulator/roles/{ROLE}", headers=auth(ADMIN), json={"mode": "simulated"})).json()
            assert v["cast"][ROLE]["filled_by"] == {"mode": "simulated"}
        outs = []
        while (o := await scheduler.tick()) is not None:
            outs.append(o)
        kinds = [("observed" if o.get("observed") else "executed", o["step"]["action"]) for o in outs]
        assert kinds == [("observed", "acknowledge"), ("observed", "start"), ("executed", "note"),
                         ("executed", "complete"), ("executed", "check_status")]
        t = await db.staff_tasks.find_one({"task_id": tid})
        assert t["status"] == "completed" and t["completed_by"] == roster.STAFF["actor_id"]
        note = await receipt(outs[2]["canonical_receipt_id"])
        assert note["actor_type"] == "simulated-agent"
        assert await db.staff_tasks.count_documents({"simulation_run_id": started["run_id"]}) == 1
    run(go())


def test_role_assignment_rules_and_impersonation_guards():
    async def go():
        op, auth_ = operator()
        await scheduler.start(op, auth_)
        for bad in ({"mode": "real", "user_id": "nobody"}, {"mode": "real", "user_id": HOUSEKEEPER["user_id"]},
                    {"mode": "real", "user_id": roster.STAFF["actor_id"]}, {"mode": "real"}, {"mode": "boss"}):
            with pytest.raises(scheduler.SimulatorError) as e:
                await scheduler.assign_role(op, auth_, ROLE, bad["mode"], bad.get("user_id"))
            assert e.value.status_code == 400
        with pytest.raises(scheduler.SimulatorError):
            await scheduler.assign_role(op, auth_, "resident", "unassigned")
        # unassigned: the work waits, nothing is done
        await scheduler.assign_role(op, auth_, ROLE, "unassigned")
        tid = (await scheduler.tick())["task_id"]
        n = len(await chain(tid))
        w = await scheduler.tick()
        assert w["waiting"]["mode"] == "unassigned" and len(await chain(tid)) == n
        # the scenario itself refuses to act for a role it does not hold
        cast = (await scheduler.active_run())["cast"]
        with pytest.raises(RuntimeError, match="will not act"):
            await scenario.execute(scenario.STEPS[1], {"task_id": tid}, cast)
        assert len(await chain(tid)) == n
        async with client() as c:
            cands = (await c.get(f"/api/simulator/roles/{ROLE}/candidates", headers=auth(ADMIN))).json()
            ids = {u["user_id"] for u in cands}
            assert MICHAEL["user_id"] in ids and ADMIN["user_id"] in ids and HOUSEKEEPER["user_id"] not in ids
            assert (await c.post(f"/api/simulator/roles/{ROLE}", headers=auth(MICHAEL),
                                 json={"mode": "simulated"})).status_code == 403   # staff cannot reassign roles
        await scheduler.stop(op, auth_)
    run(go())
