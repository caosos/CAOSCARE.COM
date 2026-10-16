"""Side-by-side proof that burn-in work cannot mutate canonical real records."""

import asyncio
import importlib.util
import json
import sys
import types


# The focused execution image omits FastAPI.  Stub only the adapter's imported
# seams when it has not already been imported by the adjacent adapter tests.
if (
    importlib.util.find_spec("fastapi") is None
    and "simulation.community_burnin_adapter" not in sys.modules
):
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
from simulation.community_outcomes import plan_routine_outcomes
from simulation.community_routines import plan_first_24_hours


RUN_ID = "simrun-side-by-side-1"
SIM_RESIDENT_ID = "sim:resident:resident-001"
SIM_ROOM = "SIM-101"
SIM_TASK_ID = "sim:task:shower-001"


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _matches(row, query):
    return all(row.get(key) == value for key, value in query.items())


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    async def find_one(self, query, projection=None, sort=None):
        return next((row for row in self.rows if _matches(row, query)), None)


class _World:
    """One fake canonical store holding both real and synthetic records."""

    def __init__(self):
        self.resident_rows = [
            {
                "resident_id": "resident-real-001",
                "name": "Real Resident",
                "room": "101",
                "synthetic": False,
                "care_notes": ["Transfer assist"],
            },
            {
                "resident_id": SIM_RESIDENT_ID,
                "name": "SIM - Ada Resident",
                "room": SIM_ROOM,
                "synthetic": True,
                "simulation_run_id": RUN_ID,
                "simulation_scope": adapter.SIMULATION_SCOPE,
                "simulation_community_id": adapter.COMMUNITY_ID,
            },
        ]
        self.task_rows = [{
            "task_id": "task-real-001",
            "resident_id": "resident-real-001",
            "room": "101",
            "category": "nursing",
            "visibility_role": "nursing",
            "resident_words": adapter.SHOWER_WORDS,
            "summary": "Real resident requested transfer help.",
            "status": "pending",
            "simulated": False,
            "simulation_run_id": None,
            "version": 4,
        }]
        self.receipt_rows = [{
            "receipt_id": "receipt-real-001",
            "related_object_type": "task",
            "related_object_id": "task-real-001",
            "action_type": "resident_request_created",
            "actor_id": "resident-real-001",
            "actor_type": "real-human",
            "identity_basis": "unverified_room_claim",
            "simulated": False,
            "simulation_run_id": None,
            "parent_receipt_id": None,
            "correlation_id": "receipt-real-001",
            "created_at": "2026-10-13T08:00:00Z",
        }]
        self.run_rows = [{
            "run_id": RUN_ID, "state": adapter.PAUSED, "synthetic": True,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
        }]
        self.residents = _Collection(self.resident_rows)
        self.staff_tasks = _Collection(self.task_rows)
        self.receipts = _Collection(self.receipt_rows)
        self.sim_runs = _Collection(self.run_rows)

    def real_records(self):
        return {
            "resident": next(row for row in self.resident_rows if not row["synthetic"]),
            "request": next(row for row in self.task_rows if not row["simulated"]),
            "receipt": next(row for row in self.receipt_rows if not row["simulated"]),
        }


def _nurse():
    return ActorContext(
        actor_id="sim:staff:nursing-1",
        actor_type="simulated-agent",
        identity_basis="synthetic",
        channel="simulator",
        name="SIM - Nursing staff",
        role="staff",
        department="nursing",
        simulated=True,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_planning_and_manual_burn_in_leave_real_records_byte_identical(monkeypatch):
    world = _World()
    before = {name: _bytes(row) for name, row in world.real_records().items()}
    create_calls = []
    acknowledge_calls = []
    monkeypatch.setattr(adapter, "db", world)

    async def canonical_create(data, *, simulation_run_id=None):
        assert simulation_run_id == RUN_ID
        assert data.resident_id == SIM_RESIDENT_ID
        create_calls.append(data)
        task = {
            "task_id": SIM_TASK_ID,
            "resident_id": data.resident_id,
            "room": data.room,
            "category": data.category,
            "visibility_role": "nursing",
            "resident_words": data.resident_words,
            "summary": data.summary,
            "status": "pending",
            "simulated": True,
            "simulation_run_id": simulation_run_id,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
        }
        origin = {
            "receipt_id": "sim:receipt:origin-001",
            "related_object_type": "task",
            "related_object_id": SIM_TASK_ID,
            "action_type": "resident_request_created",
            "actor_id": SIM_RESIDENT_ID,
            "actor_type": "simulated-agent",
            "identity_basis": "synthetic",
            "simulated": True,
            "simulation_run_id": simulation_run_id,
            "simulation_scope": adapter.SIMULATION_SCOPE,
            "simulation_community_id": adapter.COMMUNITY_ID,
            "parent_receipt_id": None,
            "correlation_id": "sim:receipt:origin-001",
        }
        world.task_rows.append(task)
        world.receipt_rows.append(origin)
        return {"task_id": SIM_TASK_ID, "receipt_id": origin["receipt_id"]}

    async def canonical_load(task_id):
        return next(row for row in world.task_rows if row["task_id"] == task_id)

    async def canonical_acknowledge(task_id, actor, profile):
        assert actor.simulated and profile["simulated"]
        acknowledge_calls.append(task_id)
        task = await canonical_load(task_id)
        task["status"] = "acknowledged"
        receipt = {
            "receipt_id": "sim:receipt:ack-001",
            "related_object_type": "task",
            "related_object_id": task_id,
            "action_type": "task_acknowledged",
            **actor.receipt_fields(),
            "simulation_run_id": RUN_ID,
            "parent_receipt_id": "sim:receipt:origin-001",
            "correlation_id": "sim:receipt:origin-001",
        }
        world.receipt_rows.append(receipt)
        return task, receipt

    monkeypatch.setattr(adapter, "create_resident_request", canonical_create)
    monkeypatch.setattr(adapter, "load", canonical_load)
    monkeypatch.setattr(adapter.task_actions, "acknowledge", canonical_acknowledge)

    # Planning/provisioning precursors are pure and do not touch the store.
    events = plan_first_24_hours()
    assert plan_routine_outcomes(events)
    assert {name: _bytes(row) for name, row in world.real_records().items()} == before

    created = _run(adapter.create_shower_help_request(RUN_ID, SIM_RESIDENT_ID, SIM_ROOM))
    replay_created = _run(adapter.create_shower_help_request(RUN_ID, SIM_RESIDENT_ID, SIM_ROOM))
    acknowledged = _run(adapter.acknowledge_shower_help_request(
        RUN_ID,
        SIM_RESIDENT_ID,
        created.task_id,
        actor=_nurse(),
        shift=adapter.ShiftWindow(360, 900),
        sim_minute=540,
    ))
    replay_acknowledged = _run(adapter.acknowledge_shower_help_request(
        RUN_ID,
        SIM_RESIDENT_ID,
        created.task_id,
        actor=_nurse(),
        shift=adapter.ShiftWindow(360, 900),
        sim_minute=541,
    ))

    assert len(create_calls) == 1 and replay_created.idempotent_replay
    assert len(acknowledge_calls) == 1 and replay_acknowledged.idempotent_replay
    assert acknowledged.parent_receipt_id == created.receipt_id
    assert acknowledged.correlation_id == created.receipt_id
    assert {name: _bytes(row) for name, row in world.real_records().items()} == before

    synthetic_tasks = [row for row in world.task_rows if row["simulated"]]
    synthetic_receipts = [row for row in world.receipt_rows if row["simulated"]]
    assert len(synthetic_tasks) == 1 and synthetic_tasks[0]["simulation_run_id"] == RUN_ID
    assert synthetic_tasks[0]["resident_id"] == SIM_RESIDENT_ID
    assert len(synthetic_receipts) == 2
    assert all(row["simulation_run_id"] == RUN_ID for row in synthetic_receipts)
    assert [row["related_object_id"] for row in synthetic_receipts] == [SIM_TASK_ID, SIM_TASK_ID]
    assert len([row for row in world.task_rows if not row["simulated"]]) == 1
    assert len([row for row in world.receipt_rows if not row["simulated"]]) == 1
