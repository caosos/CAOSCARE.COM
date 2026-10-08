"""SC-16 / SC-17: simulated requests never reach a real provider, and a
simulator-raised request carries explicit provenance on the one canonical
StaffTask/receipt model.

SC-16  a simulated request's department notifications (resident request,
       re-request, transportation) are recorded "simulated", linked to the
       task, receipt and run, and never handed to Resend/Twilio - even with
       live provider keys configured. A real request is unchanged.
SC-17  create_resident_request(..., simulation_run_id=) (in-process only)
       records source/channel "simulator" and the run id on the task and on
       every receipt of its chain; a run's requests dedup only within that
       run; a real resident, an unknown run, a body-claimed "simulator"
       source or a body-supplied run id cannot produce simulator provenance.

In-process, DB-direct; refuses to run against the live `caoscare` DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_simprov_test \
      JWT_SECRET=x pytest tests/test_sim_provenance.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes simulator/test records; point DB_NAME at a scratch database",
                allow_module_level=True)

from deps import db  # noqa: E402
from routes import notifications  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.aria_operational_state import resolve_operational_state  # noqa: E402
from routes.demo_kiosk import ensure_demo_room  # noqa: E402
from routes.departments import seed_default_departments  # noqa: E402
from routes.resident_requests import (ResidentRequestInput, create_resident_request,  # noqa: E402
                                      resident_request_status)
from routes.transportation import TransportRequestInput, submit_transport_request  # noqa: E402
from simulation import roster  # noqa: E402

TAG = f"simprov_{uuid.uuid4().hex[:8]}"
RUN = f"{TAG}_run"
REAL_RES = f"{TAG}_real_res"
REAL_ROOM = f"{TAG}-R"
STAFF_EMAIL = f"{TAG}-tech@example.test"
DEMO = {}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class ProviderSpy:
    """Stands in for httpx.AsyncClient: records every provider call."""
    calls: list = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kw):
        ProviderSpy.calls.append(url)

        class R:
            status_code = 200
            text = '{"id":"provider-accepted"}'

            def json(self):
                return {"id": "accepted"}
        return R()


async def _clean():
    demo_rid = DEMO.get("resident_id")
    tasks = await db.staff_tasks.find(
        {"$or": [{"resident_id": {"$in": [REAL_RES, demo_rid]}}, {"simulation_run_id": RUN}]},
        {"_id": 0, "task_id": 1}).to_list(200)
    ids = [t["task_id"] for t in tasks]
    await db.receipts.delete_many({"related_object_id": {"$in": ids}})
    await db.notifications.delete_many({"$or": [{"task_id": {"$in": ids}}, {"to": STAFF_EMAIL}]})
    await db.staff_tasks.delete_many({"task_id": {"$in": ids}})
    await db.residents.delete_many({"resident_id": REAL_RES})
    await db.users.delete_many({"email": STAFF_EMAIL})
    await db.sim_runs.delete_many({"run_id": RUN})


async def _setup():
    await seed_default_departments()
    DEMO.update(await ensure_demo_room())
    await _clean()
    await db.residents.insert_one({"resident_id": REAL_RES, "name": f"{TAG} Real", "room": REAL_ROOM})
    # One staff recipient in each department the tests notify.
    for dept in ("maintenance", "transportation"):
        await db.departments.update_one({"slug": dept}, {"$unset": {"contact_email": ""}})
    await db.users.insert_many([{"user_id": f"{TAG}_{d}", "email": STAFF_EMAIL, "name": d, "role": "staff",
                                 "department": d} for d in ("maintenance", "transportation")])
    await db.sim_runs.insert_one({"run_id": RUN, "state": "running", "created_at": "2026-10-04T00:00:00+00:00"})


@pytest.fixture(autouse=True)
def env(monkeypatch):
    import httpx
    ProviderSpy.calls = []
    monkeypatch.setattr(httpx, "AsyncClient", ProviderSpy)
    # Live provider keys: anything not stopped by SC-16 would be "sent".
    monkeypatch.setenv("RESEND_API_KEY", "re_live_key_for_test")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15550000000")
    run(_setup())
    yield
    run(_clean())


def _sim_input(words="The bathroom sink keeps dripping."):
    return ResidentRequestInput(category="maintenance", resident_id=DEMO["resident_id"], room=DEMO["room"],
                                resident_words=words, summary=words, source=roster.RESIDENT_CHANNEL)


async def _notes(task_id):
    return await db.notifications.find({"task_id": task_id}, {"_id": 0}).to_list(50)


async def _receipts(task_id):
    return await db.receipts.find({"related_object_id": task_id}, {"_id": 0}).sort("created_at", 1).to_list(50)


def test_sc16_simulated_request_never_reaches_a_provider():
    async def go():
        out = await create_resident_request(_sim_input(), simulation_run_id=RUN)
        again = await create_resident_request(_sim_input(), simulation_run_id=RUN)
        assert again["duplicate"] and again["task_id"] == out["task_id"]
        notes = await _notes(out["task_id"])
        assert len(notes) == 2                                  # new request + re-request
        for n, rid in zip(sorted(notes, key=lambda n: n["created_at"]), (out["receipt_id"], again["receipt_id"])):
            assert n["status"] == "simulated" and n["simulated"] is True
            assert n["simulation_run_id"] == RUN and n["receipt_id"] == rid
            assert "never sent" in n["provider_response"]
        # Direct provider calls with a simulation context are also stopped.
        sim = {"simulated": True, "simulation_scope": "demo_room", "simulation_run_id": RUN,
               "task_id": out["task_id"], "receipt_id": out["receipt_id"]}
        assert (await notifications.send_sms("+15551112222", "x", simulation=sim))["status"] == "simulated"
        assert (await notifications.send_email(STAFF_EMAIL, "s", "b", simulation=sim))["status"] == "simulated"
        assert ProviderSpy.calls == []
    run(go())


def test_sc16_demo_kiosk_request_is_simulated_too():
    """A synthetic resident's ask from the demo kiosk (no run) is simulated
    work; its notification is not delivered either."""
    async def go():
        out = await create_resident_request(_sim_input())
        task = await db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0})
        assert task["simulated"] and task["source"] == "aria_voice" and not task.get("simulation_run_id")
        notes = await _notes(out["task_id"])
        assert notes and all(n["status"] == "simulated" and n["simulation_run_id"] is None for n in notes)
        assert ProviderSpy.calls == []
    run(go())


def test_sc16_simulated_ride_notifications_not_delivered():
    async def go():
        out = await submit_transport_request(TransportRequestInput(
            resident_id=DEMO["resident_id"], room=DEMO["room"], purpose="pharmacy",
            requested_for_date="2026-10-09"))
        notes = await _notes(out["task_id"])
        assert notes and all(n["status"] == "simulated" and n["receipt_id"] == out["receipt_id"] for n in notes)
        assert ProviderSpy.calls == []
    run(go())


def test_real_request_unchanged():
    async def go():
        out = await create_resident_request(ResidentRequestInput(
            category="maintenance", resident_id=REAL_RES, room=REAL_ROOM,
            resident_words="My sink is leaking", summary="My sink is leaking", source="aria_voice"))
        task = await db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0})
        assert task["source"] == "aria_voice" and task["simulated"] is False
        assert task.get("simulation_run_id") is None and task.get("simulation_scope") is None
        origin = (await _receipts(out["task_id"]))[0]
        assert origin["simulated"] is False and origin["channel"] == "aria_voice"
        assert origin.get("simulation_run_id") is None
        # The real department email still goes to the provider.
        sent = await db.notifications.find({"to": STAFF_EMAIL, "subject": {"$regex": "new maintenance"}},
                                           {"_id": 0}).to_list(10)
        assert sent and all(n["status"] == "sent" and not n.get("simulated") for n in sent)
        assert ProviderSpy.calls == ["https://api.resend.com/emails"] * len(sent)
    run(go())


def test_sc17_simulator_provenance_on_the_canonical_request():
    async def go():
        out = await create_resident_request(_sim_input(), simulation_run_id=RUN)
        task = await db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0})
        assert task["source"] == "simulator" and task["simulation_run_id"] == RUN
        assert task["simulated"] is True and task["simulation_scope"] == "demo_room"
        assert await db.staff_tasks.count_documents({"simulation_run_id": RUN}) == 1   # one canonical object
        origin = (await _receipts(out["task_id"]))[0]
        assert origin["receipt_id"] == out["receipt_id"]
        assert (origin["channel"], origin["source"], origin["simulation_run_id"]) == ("simulator", "simulator", RUN)
        assert origin["actor_type"] == "simulated-agent" and origin["identity_basis"] == "synthetic"
        assert origin["simulated"] is True and origin["authority"] == "simulation_run"
        # A later simulated staff step on the same request: same run, same chain.
        _, ack = await task_actions.acknowledge(out["task_id"], roster.staff_actor(), roster.staff_profile())
        assert ack["simulation_run_id"] == RUN and ack["correlation_id"] == origin["receipt_id"]
        # Same world: the synthetic resident's status lookups see it.
        status = await resident_request_status(resident_id=DEMO["resident_id"])
        assert status["found"] and status["task_id"] == out["task_id"]
        op = await resolve_operational_state(DEMO["resident_id"], None, None)
        assert any(i.get("ref") == out["task_id"] for i in op["current"] + op["background"])
    run(go())


def test_sc17_provenance_cannot_be_claimed_or_misapplied():
    async def go():
        before = await db.staff_tasks.count_documents({})
        real = ResidentRequestInput(category="maintenance", resident_id=REAL_RES, room=REAL_ROOM,
                                    summary="Light is out", source="aria_voice")
        with pytest.raises(HTTPException) as e:                 # real resident
            await create_resident_request(real, simulation_run_id=RUN)
        assert e.value.status_code == 400
        with pytest.raises(HTTPException) as e:                 # unknown run
            await create_resident_request(_sim_input(), simulation_run_id=f"{TAG}_nope")
        assert e.value.status_code == 400
        with pytest.raises(HTTPException) as e:                 # body-claimed simulator source
            await create_resident_request(ResidentRequestInput(**{**real.model_dump(), "source": "simulator"}))
        assert e.value.status_code == 400
        assert await db.staff_tasks.count_documents({}) == before
        # A body-supplied run id is not part of the request model.
        smuggled = ResidentRequestInput(**{**_sim_input().model_dump(), "simulation_run_id": RUN})
        out = await create_resident_request(smuggled)
        task = await db.staff_tasks.find_one({"task_id": out["task_id"]}, {"_id": 0})
        assert task.get("simulation_run_id") is None and task["source"] == "aria_voice"
    run(go())


def test_sc17_runs_dedup_only_within_the_run():
    async def go():
        kiosk = await create_resident_request(_sim_input())                     # demo kiosk ask, no run
        sim = await create_resident_request(_sim_input(), simulation_run_id=RUN)
        assert not sim["duplicate"] and sim["task_id"] != kiosk["task_id"]
        kiosk_again = await create_resident_request(_sim_input())
        assert kiosk_again["duplicate"] and kiosk_again["task_id"] == kiosk["task_id"]
        sim_again = await create_resident_request(_sim_input(), simulation_run_id=RUN)
        assert sim_again["duplicate"] and sim_again["task_id"] == sim["task_id"]
    run(go())
