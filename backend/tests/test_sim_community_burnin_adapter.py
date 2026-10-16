"""Focused unit tests for the paused-only canonical burn-in adapter."""

import asyncio
import importlib.util
import inspect
import sys
import types

import pytest

# This isolated execution image does not carry the backend's FastAPI/Pydantic
# dependencies.  Keep the focused adapter unit test runnable here by providing
# only its imported callable seams.  Normal repository CI has FastAPI and uses
# the real modules instead.
if importlib.util.find_spec("fastapi") is None:
    deps_stub = types.ModuleType("deps")
    deps_stub.db = None
    sys.modules["deps"] = deps_stub

    actions_stub = types.ModuleType("routes.task_actions")
    actions_stub.acknowledge = None
    sys.modules["routes.task_actions"] = actions_stub

    requests_stub = types.ModuleType("routes.resident_requests")

    class ResidentRequestInput:
        def __init__(self, **fields):
            self.__dict__.update(fields)

    requests_stub.ResidentRequestInput = ResidentRequestInput
    requests_stub.create_resident_request = None
    sys.modules["routes.resident_requests"] = requests_stub

    lifecycle_stub = types.ModuleType("routes.task_lifecycle")
    lifecycle_stub.load = None
    sys.modules["routes.task_lifecycle"] = lifecycle_stub

from routes.actor_context import ActorContext
from simulation import community_burnin_adapter as adapter


RUN_ID = "simrun-burnin-1"
RESIDENT_ID = "sim:resident:resident-001"
ROOM = "SIM-101"
TASK_ID = "task-shower-1"
ORIGIN = {
    "receipt_id": "rcpt-origin", "action_type": "resident_request_created",
    "parent_receipt_id": None, "correlation_id": "rcpt-origin",
}
ACK = {
    "receipt_id": "rcpt-ack", "action_type": "task_acknowledged",
    "parent_receipt_id": "rcpt-origin", "correlation_id": "rcpt-origin",
}
TASK = {
    "task_id": TASK_ID, "resident_id": RESIDENT_ID, "room": ROOM,
    "category": "nursing", "visibility_role": "nursing", "resident_words": adapter.SHOWER_WORDS,
    "simulated": True, "simulation_run_id": RUN_ID, "status": "pending",
    "simulation_scope": adapter.SIMULATION_SCOPE,
    "simulation_community_id": adapter.COMMUNITY_ID,
}


class Collection:
    def __init__(self, lookup):
        self.lookup = lookup

    async def find_one(self, query, projection=None, sort=None):
        return self.lookup(query)


class FakeDb:
    def __init__(self):
        self.task = None
        self.receipts = []
        self.sim_runs = Collection(lambda q: {
            "run_id": RUN_ID, "state": adapter.PAUSED,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
        } if q.get("run_id") == RUN_ID else None)
        self.residents = Collection(lambda q: {
            "resident_id": RESIDENT_ID, "room": ROOM, "synthetic": True,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
        }
                                    if q.get("resident_id") == RESIDENT_ID else None)
        self.staff_tasks = Collection(lambda q: self.task if self.task and q.get("simulation_run_id") == RUN_ID else None)
        self.receipts_collection = Collection(self._receipt)
        self.receipts = self.receipts_collection

    def _receipt(self, query):
        return next((item for item in getattr(self, "receipt_rows", [])
                     if item["action_type"] == query.get("action_type")
                     and query.get("related_object_id") == TASK_ID), None)


def nurse() -> ActorContext:
    return ActorContext(
        actor_id="sim:staff:nursing-1", actor_type="simulated-agent", identity_basis="synthetic",
        channel="simulator", name="SIM - Nursing staff", role="staff", department="nursing", simulated=True,
    )


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_request_is_canonical_simulated_and_idempotent(monkeypatch):
    fake = FakeDb()
    fake.receipt_rows = []
    calls = []
    monkeypatch.setattr(adapter, "db", fake)

    async def create(data, *, simulation_run_id=None):
        calls.append((data, simulation_run_id))
        fake.task = dict(TASK)
        fake.receipt_rows.append(dict(ORIGIN))
        return {"task_id": TASK_ID, "receipt_id": ORIGIN["receipt_id"], "status": "pending"}

    async def load(task_id):
        assert task_id == TASK_ID
        return dict(fake.task)

    monkeypatch.setattr(adapter, "create_resident_request", create)
    monkeypatch.setattr(adapter, "load", load)

    first = run(adapter.create_shower_help_request(RUN_ID, RESIDENT_ID, ROOM))
    replay = run(adapter.create_shower_help_request(RUN_ID, RESIDENT_ID, ROOM))

    assert len(calls) == 1
    data, run_id = calls[0]
    assert run_id == RUN_ID
    assert data.category == "nursing" and data.priority == "high"
    assert data.resident_words == adapter.SHOWER_WORDS
    assert first.receipt_id == ORIGIN["receipt_id"] and first.idempotent_replay is False
    assert replay.receipt_id == ORIGIN["receipt_id"] and replay.idempotent_replay is True


def test_on_shift_simulated_nurse_acknowledges_with_parent_link_once(monkeypatch):
    fake = FakeDb()
    fake.task = dict(TASK)
    fake.receipt_rows = [dict(ORIGIN)]
    calls = []
    monkeypatch.setattr(adapter, "db", fake)
    monkeypatch.setattr(adapter, "load", lambda task_id: _async_value(dict(fake.task)))

    async def acknowledge(task_id, actor, profile):
        calls.append((task_id, actor, profile))
        fake.receipt_rows.append(dict(ACK))
        return dict(fake.task), dict(ACK)

    monkeypatch.setattr(adapter.task_actions, "acknowledge", acknowledge)
    shift = adapter.ShiftWindow(360, 900)
    first = run(adapter.acknowledge_shower_help_request(
        RUN_ID, RESIDENT_ID, TASK_ID, actor=nurse(), shift=shift, sim_minute=540,
    ))
    replay = run(adapter.acknowledge_shower_help_request(
        RUN_ID, RESIDENT_ID, TASK_ID, actor=nurse(), shift=shift, sim_minute=541,
    ))

    assert len(calls) == 1
    assert calls[0][2] == {
        "user_id": nurse().actor_id, "name": nurse().name, "role": "staff",
        "department": "nursing", "simulated": True,
    }
    assert first.parent_receipt_id == ORIGIN["receipt_id"]
    assert first.correlation_id == ORIGIN["receipt_id"]
    assert replay.receipt_id == first.receipt_id and replay.idempotent_replay is True


def _async_value(value):
    async def get():
        return value
    return get()


@pytest.mark.parametrize("state", ["RUNNING", "STOPPED"])
def test_running_or_stopped_run_is_refused_before_canonical_write(monkeypatch, state):
    fake = FakeDb()
    fake.sim_runs = Collection(lambda _q: {"run_id": RUN_ID, "state": state})
    monkeypatch.setattr(adapter, "db", fake)
    called = []

    async def create(*args, **kwargs):
        called.append(True)

    monkeypatch.setattr(adapter, "create_resident_request", create)
    with pytest.raises(adapter.BurnInAdapterError, match="require PAUSED"):
        run(adapter.create_shower_help_request(RUN_ID, RESIDENT_ID, ROOM))
    assert called == []


@pytest.mark.parametrize("wrong", ["run_scope", "run_community", "resident_scope", "resident_community"])
def test_cross_scope_run_or_resident_is_refused_before_canonical_write(monkeypatch, wrong):
    fake = FakeDb()
    if wrong.startswith("run_"):
        run_doc = {
            "run_id": RUN_ID, "state": adapter.PAUSED,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
        }
        run_doc["simulation_scope" if wrong == "run_scope" else "simulation_community_id"] = "other"
        fake.sim_runs = Collection(lambda _q: run_doc)
    else:
        resident = {
            "resident_id": RESIDENT_ID, "room": ROOM, "synthetic": True,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
        }
        resident["simulation_scope" if wrong == "resident_scope" else "simulation_community_id"] = "other"
        fake.residents = Collection(lambda _q: resident)
    monkeypatch.setattr(adapter, "db", fake)
    calls = []

    async def create(*args, **kwargs):
        calls.append(True)

    monkeypatch.setattr(adapter, "create_resident_request", create)
    with pytest.raises(adapter.BurnInAdapterError, match="living-community"):
        run(adapter.create_shower_help_request(RUN_ID, RESIDENT_ID, ROOM))
    assert calls == []


def test_off_shift_or_non_simulated_staff_is_refused(monkeypatch):
    fake = FakeDb()
    fake.task = dict(TASK)
    fake.receipt_rows = [dict(ORIGIN)]
    monkeypatch.setattr(adapter, "db", fake)
    monkeypatch.setattr(adapter, "load", lambda task_id: _async_value(dict(fake.task)))
    called = []

    async def acknowledge(*args, **kwargs):
        called.append(True)

    monkeypatch.setattr(adapter.task_actions, "acknowledge", acknowledge)
    with pytest.raises(adapter.BurnInAdapterError, match="off shift"):
        run(adapter.acknowledge_shower_help_request(
            RUN_ID, RESIDENT_ID, TASK_ID, actor=nurse(), shift=adapter.ShiftWindow(360, 480), sim_minute=540,
        ))
    real_actor = ActorContext(
        actor_id="real-user", actor_type="real-human", identity_basis="authenticated", channel="staff_ui",
        name="Real Nurse", role="staff", department="nursing", simulated=False,
    )
    with pytest.raises(adapter.BurnInAdapterError, match="simulated Nursing"):
        run(adapter.acknowledge_shower_help_request(
            RUN_ID, RESIDENT_ID, TASK_ID, actor=real_actor,
            shift=adapter.ShiftWindow(360, 900), sim_minute=540,
        ))
    assert called == []


def test_adapter_has_no_direct_write_provider_or_user_creation_code():
    source = inspect.getsource(adapter)
    assert ".insert_one(" not in source and ".update_one(" not in source
    assert "httpx" not in source and "send_email" not in source and "place_call" not in source
    assert "db.users" not in source
    with pytest.raises(ValueError):
        adapter.ShiftWindow(-1, 480)
    with pytest.raises(ValueError):
        adapter.ShiftWindow(480, 480)
