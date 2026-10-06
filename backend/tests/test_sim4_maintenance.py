"""SIM-4 Maintenance: the existing `sink_leak` scenario held to the SIM-4 bar,
with the owner (real Michael's role) taking over the maintenance role.

The simulated resident says "The bathroom sink keeps leaking." -> canonical
maintenance request -> the maintenance role (sim:staff:maintenance-1, or a
real authenticated owner via the SIM-3 hand-off) acknowledges / starts /
notes / completes -> the resident checks status -> the run finishes.
Acceptance:
 1 one canonical Maintenance task          6 resident status matches the real state
 2 the simulated tech works it              at every stage (never "on the way")
 3 a real owner can take over the role     7 the simulator continues after completion
 4 the simulator waits for the real action 8 no duplicate task (a repeat ask attaches)
 5 real receipts identify the owner        9 no real provider side effects
Every request receipt chains to the origin and carries the run id.

In-process scheduler plus the real FastAPI app over ASGI with real JWTs.
Demo room only; refuses to run against the live DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_sim4m_test \
      JWT_SECRET=x pytest tests/test_sim4_maintenance.py -q
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
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
from simulation import roster, scenario, scheduler  # noqa: E402

SC = scenario.SCENARIO_ID          # "sink_leak"
ROLE = roster.STAFF["key"]
SIM_TECH = roster.STAFF["actor_id"]
TAG = f"sim4m_{uuid.uuid4().hex[:8]}"
ADMIN = {"user_id": f"{TAG}_admin", "email": f"{TAG}_admin@example.com", "name": f"{TAG} Operator",
         "role": "admin", "auth_provider": "jwt"}
OWNER = {"user_id": f"{TAG}_owner", "email": f"{TAG}_owner@example.com", "name": "Michael (test owner)",
         "role": "owner", "auth_provider": "jwt"}                       # no department, like real Michael
NURSE = {"user_id": f"{TAG}_nurse", "email": f"{TAG}_nurse@example.com", "name": f"{TAG} Nurse",
         "role": "staff", "department": "nursing", "auth_provider": "jwt"}
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
    for u in (ADMIN, OWNER, NURSE):
        await db.users.insert_one({**u, "created_at": "2026-10-06T00:00:00+00:00"})
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
    origin = [r for r in chain_ if r["parent_receipt_id"] is None]
    assert len(origin) == 1 and origin[0]["action_type"] == "resident_request_created"
    ids = {r["receipt_id"] for r in chain_}
    for r in chain_:
        assert r["correlation_id"] == origin[0]["receipt_id"]
        assert r["simulation_run_id"] == run_id
        assert r["parent_receipt_id"] is None or r["parent_receipt_id"] in ids
    assert task["simulation_run_id"] == run_id and task["source"] == "simulator"


async def _status(c, history=False):
    path = "history" if history else "status"
    return (await c.get(f"/api/tasks/resident-request/{path}",
                        params={"resident_id": DEMO["resident_id"], "category": "maintenance"})).json()


def test_simulated_tech_works_the_leak(monkeypatch):
    async def go():
        started = await scheduler.start(*operator(), scenario_id=SC)
        run_id = started["run_id"]
        assert set(started["cast"]) == {"resident", ROLE}
        # 9: a live provider configured after start, provider client replaced by a spy
        import httpx as hx
        ProviderSpy.calls = []
        monkeypatch.setattr(hx, "AsyncClient", ProviderSpy)
        monkeypatch.setattr(notifications, "RESEND_KEY", "re_live_key_for_test")

        first = await scheduler.tick()                            # resident raises the request
        tid = first["task_id"]
        # 8: the resident asks again before anyone acts -> same task, counted
        again = await create_resident_request(ResidentRequestInput(
            category="maintenance", resident_id=DEMO["resident_id"], room=roster.DEMO_ROOM,
            resident_words=scenario.SINK_WORDS, summary=scenario.SINK_WORDS, source=roster.RESIDENT_CHANNEL),
            simulation_run_id=run_id)
        assert again["duplicate"] is True and again["task_id"] == tid

        outs = [first]
        while (o := await scheduler.tick()) is not None:
            outs.append(o)
        # 2, 7
        assert [(o["executed"], o["step"]["action"]) for o in outs] == [
            (True, "raise_request"), (True, "acknowledge"), (True, "start"), (True, "note"),
            (True, "complete"), (True, "check_status")]
        task = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        # 1
        assert task["category"] == "maintenance" and task["visibility_role"] == "maintenance"
        assert task["resident_words"] == "The bathroom sink keeps leaking." and task["simulated"] is True
        assert task["status"] == "completed" and task["completed_by"] == SIM_TECH
        steps = [r for r in await chain(tid) if r["actor_id"] == SIM_TECH]
        assert [r["action_type"] for r in steps] == [
            "task_acknowledged", "task_in_progress", "task_note_added", "task_completed"]
        for r in steps:
            assert r["actor_type"] == "simulated-agent" and r["actor_department"] == "maintenance"
        _assert_traceable(await chain(tid), task, run_id)
        assert roster.STAFF["name"] in (await receipt(outs[-1]["step_receipt_id"]))["result"]
        assert (await db.sim_runs.find_one({"run_id": run_id}))["state"] == "STOPPED"
        assert await db.staff_tasks.count_documents({"simulation_run_id": run_id}) == 1
        notes = await db.notifications.find({"task_id": tid}, {"_id": 0}).to_list(50)
        assert notes and all(n["status"] == "simulated" for n in notes)
        assert ProviderSpy.calls == []
    run(go())


def test_owner_takes_over_with_truthful_status_at_every_stage():
    async def go():
        async with client() as c:
            # 3: hand the role to the owner (no department) through the operator API
            cands = None
            s = (await c.post("/api/simulator/start", headers=auth(ADMIN), json={"scenario": SC})).json()
            run_id = s["run_id"]
            cands = {u["user_id"] for u in (await c.get(f"/api/simulator/roles/{ROLE}/candidates",
                                                        headers=auth(ADMIN))).json()}
            assert OWNER["user_id"] in cands and NURSE["user_id"] not in cands
            v = (await c.post(f"/api/simulator/roles/{ROLE}", headers=auth(ADMIN),
                              json={"mode": "real", "user_id": OWNER["user_id"]})).json()
            assert v["cast"][ROLE]["filled_by"]["user_id"] == OWNER["user_id"]

            tid = (await scheduler.tick())["task_id"]
            n = len(await chain(tid))
            # 4: waits, nothing recorded, nothing done for him
            for _ in range(3):
                w = await scheduler.tick()
                assert w["executed"] is False and w["waiting"]["user_id"] == OWNER["user_id"]
            assert len(await chain(tid)) == n

            spoken = []
            # 6: before claim
            st = await _status(c)
            assert st["found"] and "no one has picked it up yet" in st["spoken"]
            spoken.append(st["spoken"])
            # the request is visible to the owner, not to nursing staff
            assert tid in {t["task_id"] for t in (await c.get("/api/tasks", headers=auth(OWNER))).json()}
            assert tid not in {t["task_id"] for t in (await c.get("/api/tasks", headers=auth(NURSE))).json()}
            assert (await c.post(f"/api/tasks/{tid}/start", headers=auth(NURSE))).status_code == 403

            # claim
            assert (await c.post(f"/api/tasks/{tid}/assign", headers=auth(OWNER),
                                 json={"assigned_to": OWNER["user_id"]})).status_code == 200
            st = await _status(c)
            assert "Michael (test owner) has taken it on" in st["spoken"] and "hasn't started" in st["spoken"]
            spoken.append(st["spoken"])
            # start + progress note
            assert (await c.post(f"/api/tasks/{tid}/start", headers=auth(OWNER))).status_code == 200
            assert (await c.patch(f"/api/tasks/{tid}", headers=auth(OWNER),
                                  json={"notes": "Tightening the trap under the sink."})).status_code == 200
            st = await _status(c)
            assert "Michael (test owner) is working on it now" in st["spoken"]
            assert "Tightening the trap under the sink" in st["spoken"]
            spoken.append(st["spoken"])
            # complete
            assert (await c.post(f"/api/tasks/{tid}/complete", headers=auth(OWNER),
                                 json={"notes": "Fixed, no more leak."})).status_code == 200
            assert (await _status(c))["found"] is False                # nothing open any more
            hist = await _status(c, history=True)
            done = next(r for r in hist["requests"] if r["task_id"] == tid)
            assert "taken care of by Michael (test owner)" in done["spoken"]
            spoken.append(done["spoken"])
            for line in spoken:
                assert "on the way" not in line.lower() and "coming" not in line.lower()

        # 5: his receipts identify him
        real = [r for r in await chain(tid) if r["actor_id"] == OWNER["user_id"]]
        assert [r["action_type"] for r in real] == [
            "task_assigned", "task_in_progress", "task_note_added", "task_completed"]
        for r in real:
            assert r["actor_type"] == "real-human" and r["identity_basis"] == "authenticated"
            assert r["simulated"] is False and r["channel"] == "staff_ui"
        assert not [r for r in await chain(tid) if r["actor_id"] == SIM_TECH]
        # the simulator observes each step, citing his receipts, then continues
        for expected in ("acknowledge", "start", "note", "complete"):
            o = await scheduler.tick()
            assert o["observed"] and o["step"]["action"] == expected
            assert (await receipt(o["canonical_receipt_id"]))["actor_id"] == OWNER["user_id"]
        o = await scheduler.tick()
        assert o["executed"] and o["step"]["action"] == "check_status"
        assert "Michael (test owner)" in (await receipt(o["step_receipt_id"]))["result"]
        assert (await db.sim_runs.find_one({"run_id": run_id}))["state"] == "STOPPED"
        for r in await run_receipts(run_id):
            assert r["actor_id"] in (ADMIN["user_id"], "system:simulator")
        task = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        _assert_traceable(await chain(tid), task, run_id)
        assert await db.staff_tasks.count_documents({"simulation_run_id": run_id}) == 1
    run(go())
