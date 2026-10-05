"""SIM-4: the Operations Simulator's first additional department, Nursing.

Scenario "nursing_assist": the demo room's simulated resident says "I need
help going to the bathroom." -> canonical nursing request (same StaffTask,
same request bus) -> the nurse role (simulated, or a real signed-in nurse via
the SIM-3 hand-off) acknowledges / starts / notes / completes -> the resident
asks how it went -> the run finishes. Acceptance:
 1 simulated resident creates a Nursing request    7 simulator recognises real receipts
 2 the request is visibly Nursing                  8 resident status names the real person
 3 the simulated nurse processes it                9 the simulator continues after completion
 4 a real authenticated nurse can take the role   10 provenance traceable (origin chain, run id)
 5 the simulator waits while the real nurse holds 11 no duplicate request/task
 6 normal staff routes claim/start/note/complete  12 no real provider side effects

In-process scheduler plus the real FastAPI app over ASGI with real JWTs.
Demo room only; refuses to run against the live DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_sim4_test \
      JWT_SECRET=x pytest tests/test_sim4_nursing.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("SIM-4 tests write simulator records; point DB_NAME at a scratch database",
                allow_module_level=True)

import httpx  # noqa: E402

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402
from routes.demo_kiosk import ensure_demo_room  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from simulation import roster, scenario, scheduler  # noqa: E402

SC = "nursing_assist"
ROLE = roster.NURSE["key"]
SIM_NURSE = roster.NURSE["actor_id"]
TAG = f"sim4_{uuid.uuid4().hex[:8]}"
ADMIN = {"user_id": f"{TAG}_admin", "email": f"{TAG}_admin@example.com", "name": f"{TAG} Operator",
         "role": "admin", "auth_provider": "jwt"}
NURSE = {"user_id": f"{TAG}_nurse", "email": f"{TAG}_nurse@example.com", "name": "Nora (test RN)",
         "role": "staff", "department": "nursing", "auth_provider": "jwt"}
TECH = {"user_id": f"{TAG}_tech", "email": f"{TAG}_tech@example.com", "name": f"{TAG} Tech",
        "role": "staff", "department": "maintenance", "auth_provider": "jwt"}
DEMO = {}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def operator():
    return actor_from_user(ADMIN), "admin_override:admin"


class ProviderSpy:
    """Stands in for httpx.AsyncClient on the provider path; records calls."""
    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def post(self, url, **kw):
        ProviderSpy.calls.append(url)

        class R:
            status_code = 200
            text = '{"id":"provider-accepted"}'
        return R()


async def _reset():
    for t in scheduler._loops.values():
        t.cancel()
    scheduler._loops.clear()
    await db.sim_runs.update_many({"state": {"$in": list(scheduler.ACTIVE)}}, {"$set": {"state": scheduler.STOPPED}})
    DEMO.update(await ensure_demo_room())
    await db.staff_tasks.delete_many({"resident_id": DEMO["resident_id"]})
    await db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})
    for u in (ADMIN, NURSE, TECH):
        await db.users.insert_one({**u, "created_at": "2026-10-05T00:00:00+00:00"})
    await seed_default_departments()


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(notifications, "RESEND_KEY", "")
    run(_reset())
    yield
    run(_reset())
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))


def client():
    from server import app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def auth(user):
    return {"Authorization": f"Bearer {_issue_jwt(user['user_id'])}"}


async def chain(task_id):
    return await db.receipts.find({"related_object_type": "task", "related_object_id": task_id,
                                   "action_type": {"$not": {"$regex": "_refused$"}}},
                                  {"_id": 0}).sort("created_at", 1).to_list(100)


async def receipt(rid):
    return await db.receipts.find_one({"receipt_id": rid}, {"_id": 0})


async def run_receipts(run_id):
    r = await db.sim_runs.find_one({"run_id": run_id}, {"_id": 0})
    return await db.receipts.find({"correlation_id": r["origin_receipt_id"]}, {"_id": 0}).to_list(200)


def _assert_traceable(chain_, task, run_id):
    """10: every request receipt links to the request's origin and the run."""
    origin = [r for r in chain_ if r["parent_receipt_id"] is None]
    assert len(origin) == 1 and origin[0]["action_type"] == "resident_request_created"
    ids = {r["receipt_id"] for r in chain_}
    for r in chain_:
        assert r["correlation_id"] == origin[0]["receipt_id"]
        assert r["simulation_run_id"] == run_id
        assert r["parent_receipt_id"] is None or r["parent_receipt_id"] in ids
    assert task["simulation_run_id"] == run_id and task["source"] == "simulator"


def test_simulated_nurse_processes_the_nursing_request(monkeypatch):
    async def go():
        started = await scheduler.start(*operator(), scenario_id=SC)
        run_id = started["run_id"]
        assert started["scenario"] == SC and set(started["cast"]) == {"resident", ROLE}
        assert started["cast"][ROLE]["department"] == "nursing"

        # 12: a live provider configured after start, provider client replaced by a spy
        import httpx as hx
        ProviderSpy.calls = []
        monkeypatch.setattr(hx, "AsyncClient", ProviderSpy)
        monkeypatch.setattr(notifications, "RESEND_KEY", "re_live_key_for_test")

        outs = []
        while (o := await scheduler.tick()) is not None:
            outs.append(o)
        # 3, 9: every step executed by the simulator, through to the resident's follow-up
        assert [(o["executed"], o["step"]["action"]) for o in outs] == [
            (True, "raise_request"), (True, "acknowledge"), (True, "start"), (True, "note"),
            (True, "complete"), (True, "check_status")]
        tid = outs[0]["task_id"]
        task = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        # 1, 2: a canonical, visibly Nursing request in the demo room
        assert task["category"] == "nursing" and task["visibility_role"] == "nursing"
        assert task["priority"] == "high" and task["resident_words"] == scenario.NURSING_WORDS
        assert task["simulated"] is True and task["room"] == roster.DEMO_ROOM
        assert task["status"] == "completed" and task["completed_by"] == SIM_NURSE
        staff_steps = [r for r in await chain(tid) if r["actor_id"] == SIM_NURSE]
        assert [r["action_type"] for r in staff_steps] == [
            "task_acknowledged", "task_in_progress", "task_note_added", "task_completed"]
        for r in staff_steps:
            assert r["actor_type"] == "simulated-agent" and r["actor_department"] == "nursing"
            assert r["authority"] in ("acts_for:nursing", "assignee")
        _assert_traceable(await chain(tid), task, run_id)
        # 8: the resident is told the real outcome and who did it
        assert roster.NURSE["name"] in (await receipt(outs[-1]["step_receipt_id"]))["result"]
        assert (await db.sim_runs.find_one({"run_id": run_id}))["state"] == "STOPPED"
        # 11, 12
        assert await db.staff_tasks.count_documents({"simulation_run_id": run_id}) == 1
        notes = await db.notifications.find({"task_id": tid}, {"_id": 0}).to_list(50)
        assert notes and all(n["status"] == "simulated" for n in notes)
        assert ProviderSpy.calls == []
    run(go())


def test_real_nurse_takes_over_and_the_simulator_continues():
    async def go():
        async with client() as c:
            # 4: hand the nurse role to a real nurse at start, through the operator API
            s = (await c.post("/api/simulator/start", headers=auth(ADMIN),
                              json={"scenario": SC, "roles": {ROLE: {"mode": "real", "user_id": NURSE["user_id"]}}})).json()
            assert s["scenario"] == SC and s["cast"][ROLE]["filled_by"]["user_id"] == NURSE["user_id"]
            run_id = s["run_id"]
            tid = (await scheduler.tick())["task_id"]
            n = len(await chain(tid))
            # 5: the simulator waits and records nothing while the real nurse holds the role
            for _ in range(3):
                w = await scheduler.tick()
                assert w["executed"] is False and w["waiting"]["user_id"] == NURSE["user_id"]
            assert len(await chain(tid)) == n
            state = (await c.get("/api/simulator/state", headers=auth(ADMIN))).json()
            assert state["waiting_on"]["role"] == ROLE and state["scenario_label"].startswith("Nursing")
            # 2: visible to Nursing, not to Maintenance
            assert tid in {t["task_id"] for t in (await c.get("/api/tasks", headers=auth(NURSE))).json()}
            assert tid not in {t["task_id"] for t in (await c.get("/api/tasks", headers=auth(TECH))).json()}
            assert (await c.post(f"/api/tasks/{tid}/start", headers=auth(TECH))).status_code == 403
            # 6: the normal staff routes
            assert (await c.post(f"/api/tasks/{tid}/assign", headers=auth(NURSE),
                                 json={"assigned_to": NURSE["user_id"]})).status_code == 200
            assert (await c.post(f"/api/tasks/{tid}/start", headers=auth(NURSE))).status_code == 200
            assert (await c.patch(f"/api/tasks/{tid}", headers=auth(NURSE),
                                  json={"notes": "Walking with her now."})).status_code == 200
            assert (await c.post(f"/api/tasks/{tid}/complete", headers=auth(NURSE),
                                 json={"notes": "Back in her chair."})).status_code == 200

        real = [r for r in await chain(tid) if r["actor_id"] == NURSE["user_id"]]
        assert [r["action_type"] for r in real] == [
            "task_assigned", "task_in_progress", "task_note_added", "task_completed"]
        for r in real:
            assert r["actor_type"] == "real-human" and r["identity_basis"] == "authenticated"
            assert r["simulated"] is False and r["channel"] == "staff_ui"
        assert not [r for r in await chain(tid) if r["actor_id"] == SIM_NURSE]
        # 7: each staff step observed, citing the real nurse's receipt
        for expected in ("acknowledge", "start", "note", "complete"):
            o = await scheduler.tick()
            assert o["observed"] and o["step"]["action"] == expected
            assert (await receipt(o["canonical_receipt_id"]))["actor_id"] == NURSE["user_id"]
        # 8, 9: the resident's follow-up names the real nurse; the run finishes
        o = await scheduler.tick()
        assert o["executed"] and o["step"]["action"] == "check_status"
        assert "Nora (test RN)" in (await receipt(o["step_receipt_id"]))["result"]
        assert (await db.sim_runs.find_one({"run_id": run_id}))["state"] == "STOPPED"
        # 10: run receipts only from the operator or the simulator; request chain traceable
        for r in await run_receipts(run_id):
            assert r["actor_id"] in (ADMIN["user_id"], "system:simulator")
        task = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        _assert_traceable(await chain(tid), task, run_id)
        # 11
        assert await db.staff_tasks.count_documents({"simulation_run_id": run_id}) == 1
    run(go())


def test_scenarios_and_role_rules():
    async def go():
        async with client() as c:
            cat = (await c.get("/api/simulator/scenarios", headers=auth(ADMIN))).json()
            assert {s["id"] for s in cat} >= {"sink_leak", SC}
            assert (await c.post("/api/simulator/start", headers=auth(ADMIN),
                                 json={"scenario": "nope"})).status_code == 404
            await c.post("/api/simulator/start", headers=auth(ADMIN), json={"scenario": SC})
            cands = {u["user_id"] for u in (await c.get(f"/api/simulator/roles/{ROLE}/candidates",
                                                        headers=auth(ADMIN))).json()}
            assert NURSE["user_id"] in cands and TECH["user_id"] not in cands
            # a maintenance worker cannot take the nurse role
            r = await c.post(f"/api/simulator/roles/{ROLE}", headers=auth(ADMIN),
                             json={"mode": "real", "user_id": TECH["user_id"]})
            assert r.status_code == 400
        # the sim nurse acts only for nursing: on a maintenance request the lifecycle refuses it
        tid = (await scheduler.tick())["task_id"]
        await db.staff_tasks.update_one({"task_id": tid}, {"$set": {"visibility_role": "maintenance"}})
        with pytest.raises(Exception):
            await scenario.execute(scenario.describe(1, SC), {"task_id": tid},
                                   (await scheduler.active_run())["cast"], scenario_id=SC)
        await scheduler.stop(*operator())
    run(go())
