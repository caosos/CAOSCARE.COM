"""Focused proof for the canonical community executor services adapter."""

import asyncio
from copy import deepcopy

import pytest

from simulation import community_executor as executor
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_execution_adapter import (
    CanonicalCommunityExecutionServices,
    CommunityExecutionAdapterError,
    EVENT_SESSION_PREFIX,
    EXECUTOR_AUTHORITY,
)
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_shift_execution import ShiftExecutionError


def _matches(row, query):
    return all(row.get(key) == value for key, value in query.items())


class Collection:
    def __init__(self, rows=()):
        self.rows = [deepcopy(row) for row in rows]

    async def find_one(self, query, _projection=None, **_kwargs):
        return next((deepcopy(row) for row in self.rows if _matches(row, query)), None)


class Store:
    def __init__(self, *, tasks=(), receipts=()):
        self.staff_tasks = Collection(tasks)
        self.receipts = Collection(receipts)


def event(**changes):
    values = {
        "event_id": "day-000:resident-001:morning_medication_reminder",
        "stream_kind": "routine_dispatch",
        "action_type": "morning_medication_reminder",
        "day_index": 0,
        "minute": 470,
        "actor_id": "sim:staff:nursing:med_tech:01",
        "actor_name": "SIM - Medication Technician 01",
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "department": "nursing",
        "target_type": "resident",
        "target_id": "sim:resident:001",
        "adapter": "canonical_staff_task",
        "blocked_capability": "medication_kiosk",
    }
    values.update(changes)
    return ExecutorEvent(**values)


def context(**changes):
    values = {
        "run_id": "run-1",
        "holder_id": "executor-a",
        "fence": 7,
        "cursor": 3,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "providers_allowed": False,
    }
    values.update(changes)
    return ExecutionContext(**values)


def shift_event(**changes):
    actor_id = changes.pop("actor_id", "sim:staff:nursing:med_tech:01")
    values = {
        "event_id": "sim:shift-event:0:0000:clock_in:sim-worker",
        "stream_kind": "canonical_shift_milestone",
        "action_type": "clock_in",
        "day_index": 0,
        "minute": 0,
        "actor_id": actor_id,
        "actor_name": "SIM - Medication Technician 01",
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "department": "nursing",
        "target_type": "staff_shift",
        "target_id": f"sim:shift:0:{actor_id}:night",
        "adapter": "canonical_shift_service",
    }
    values.update(changes)
    return ExecutorEvent(**values)


def task(item=None, ctx=None, **changes):
    item, ctx = item or event(), ctx or context()
    values = {
        "task_id": "task-1",
        "status": "pending",
        "resident_id": item.target_id,
        "category": item.department,
        "conversation_session_id": f"{EVENT_SESSION_PREFIX}{item.event_id}",
        "simulation_run_id": ctx.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulated": True,
    }
    values.update(changes)
    return values


def completion(item=None, ctx=None, **changes):
    item, ctx = item or event(), ctx or context()
    values = {
        "receipt_id": "rcpt-task-complete",
        "related_object_type": "task",
        "related_object_id": "task-1",
        "action_type": "task_completed",
        "simulation_run_id": ctx.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "actor_id": item.actor_id,
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "simulated": True,
        "status": "completed",
        "correlation_id": "rcpt-origin",
    }
    values.update(changes)
    return values


def harness(store):
    calls = {"create": [], "complete": [], "write": []}

    async def create(**kwargs):
        calls["create"].append(kwargs)
        created = task(kwargs["event"], kwargs["context"])
        store.staff_tasks.rows.append(deepcopy(created))
        return {"task_id": created["task_id"], "receipt_id": "rcpt-origin"}

    async def load(task_id):
        return await store.staff_tasks.find_one({"task_id": task_id})

    async def complete_task(**kwargs):
        calls["complete"].append(kwargs)
        stored = next(row for row in store.staff_tasks.rows if row["task_id"] == kwargs["task_id"])
        stored["status"] = "completed"
        proof = completion(kwargs["actor_event"] if "actor_event" in kwargs else event())
        # The injected boundary receives the canonical actor rather than an ExecutorEvent.
        proof["actor_id"] = kwargs["actor"].actor_id
        store.receipts.rows.append(deepcopy(proof))
        return deepcopy(stored), proof

    async def write(**kwargs):
        calls["write"].append(kwargs)
        doc = {key: value for key, value in kwargs.items() if key != "provenance"}
        doc.update(kwargs["provenance"])
        doc["receipt_id"] = "rcpt-event"
        store.receipts.rows.append(deepcopy(doc))
        return doc

    services = CanonicalCommunityExecutionServices(
        store=store,
        request_creator=create,
        task_loader=load,
        task_completer=complete_task,
        receipt_writer=write,
    )
    return services, calls


def test_executes_supported_routine_through_task_services_and_writes_exact_evidence():
    async def case():
        item, ctx, store = event(), context(), Store()
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)

        assert len(calls["create"]) == len(calls["complete"]) == len(calls["write"]) == 1
        assert calls["create"][0]["priority"] == "high"
        assert calls["complete"][0]["actor"].channel == "simulator"
        assert "no claim of administration" in calls["complete"][0]["note"]
        assert proof["simulation_event_id"] == item.event_id
        assert proof["execution_cursor"] == 3 and proof["execution_fence"] == 7
        assert proof["authority"] == EXECUTOR_AUTHORITY
        assert proof["parent_receipt_id"] == "rcpt-task-complete"
        assert proof["related_object_type"] == "resident"
        assert proof["related_object_id"] == item.target_id
        assert proof["after_state"]["blocked_capability_not_invoked"] == "medication_kiosk"
        assert proof["provider_refs"] == [] and proof["result_label"] == "simulated"
        assert executor._validate_evidence(proof, item, ctx) == proof

        loaded = await services.load_evidence(
            run_id=ctx.run_id, event_id=item.event_id,
            expected_cursor=ctx.cursor, execution_fence=ctx.fence,
        )
        assert loaded["receipt_id"] == "rcpt-event"

    asyncio.run(case())


def test_replay_and_crash_recovery_do_not_repeat_canonical_actions():
    async def case():
        item, ctx = event(), context()
        done_task = task(item, ctx, status="completed")
        store = Store(tasks=(done_task,), receipts=(completion(item, ctx),))
        services, calls = harness(store)

        first = await services.execute_event(event=item, context=ctx)
        assert first["receipt_id"] == "rcpt-event"
        assert calls["create"] == [] and calls["complete"] == []
        second = await services.execute_event(event=item, context=ctx)
        assert second["receipt_id"] == "rcpt-event"
        assert len(calls["write"]) == 1

    asyncio.run(case())


def test_shift_milestone_is_idempotent_receipt_only_simulated_evidence():
    async def case():
        item, ctx, store = shift_event(), context(cursor=0), Store()
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert calls["create"] == [] and calls["complete"] == []
        assert len(calls["write"]) == 1
        assert proof["action_type"] == "clock_in"
        assert proof["related_object_type"] == "staff_shift"
        assert proof["after_state"] == {
            "milestone": "clock_in", "simulated": True,
            "authenticated": False, "real_attendance_claimed": False,
        }
        assert proof["parent_receipt_id"] is None
        assert proof["result_label"] == "simulated" and proof["provider_refs"] == []
        assert "no authentication" in proof["result"]
        assert executor._validate_evidence(proof, item, ctx) == proof

        replay = await services.execute_event(event=item, context=ctx)
        assert replay["receipt_id"] == proof["receipt_id"]
        assert len(calls["write"]) == 1

    asyncio.run(case())


def test_real_day_zero_carry_in_shift_event_is_supported_exactly():
    async def case():
        queue = executor.build_day_queue()
        item = next(row for row in queue if row.stream_kind == "canonical_shift_milestone")
        assert item.event_id == (
            "sim:shift-event:0:0345:handoff:"
            "sim:staff:activities:activities_coordinator:04"
        )
        assert item.target_id == (
            "sim:shift:-1:sim:staff:activities:activities_coordinator:04:night"
        )
        ctx, store = context(cursor=queue.index(item)), Store()
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert len(calls["write"]) == 1
        assert calls["create"] == [] and calls["complete"] == []
        assert executor._validate_evidence(proof, item, ctx) == proof

    asyncio.run(case())


def test_existing_open_task_resumes_at_completion_instead_of_creating_again():
    async def case():
        store = Store(tasks=(task(),))
        services, calls = harness(store)
        proof = await services.execute_event(event=event(), context=context())
        assert proof["receipt_id"] == "rcpt-event"
        assert calls["create"] == []
        assert len(calls["complete"]) == 1

    asyncio.run(case())


def test_evidence_lookup_requires_the_exact_run_event_cursor_and_fence():
    async def case():
        near = {
            "receipt_id": "near",
            "simulation_run_id": "run-1",
            "simulation_event_id": event().event_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "execution_cursor": 3,
            "execution_fence": 8,
            "authority": EXECUTOR_AUTHORITY,
        }
        services, _calls = harness(Store(receipts=(near,)))
        assert await services.load_evidence(
            run_id="run-1", event_id=event().event_id,
            expected_cursor=3, execution_fence=7,
        ) is None

    asyncio.run(case())


@pytest.mark.parametrize("item", [
    event(adapter="outbound_family_call"),
    event(target_type="device"),
])
def test_unsupported_event_types_fail_closed_without_receipt(item):
    async def case():
        store = Store()
        services, calls = harness(store)
        with pytest.raises(CommunityExecutionAdapterError, match="unsupported"):
            await services.execute_event(event=item, context=context())
        assert calls == {"create": [], "complete": [], "write": []}
        assert store.receipts.rows == [] and store.staff_tasks.rows == []

    asyncio.run(case())


@pytest.mark.parametrize("item", [
    shift_event(action_type="shift_started"),
    shift_event(target_id="sim:shift:0:sim:staff:nursing:care_aide:02:night"),
    shift_event(department="maintenance"),
    shift_event(blocked_capability="external_timeclock"),
])
def test_mismatched_shift_milestones_fail_without_evidence(item):
    async def case():
        store = Store()
        services, calls = harness(store)
        with pytest.raises(ShiftExecutionError, match="mismatched"):
            await services.execute_event(event=item, context=context())
        assert calls == {"create": [], "complete": [], "write": []}
        assert store.receipts.rows == []

    asyncio.run(case())


def test_provider_permission_and_unproven_closed_task_fail_closed():
    async def case():
        services, calls = harness(Store())
        with pytest.raises(CommunityExecutionAdapterError, match="never permits provider"):
            await services.execute_event(event=event(), context=context(providers_allowed=True))
        assert calls["create"] == []

        store = Store(tasks=(task(status="completed"),))
        services, calls = harness(store)
        with pytest.raises(CommunityExecutionAdapterError, match="no matching completion"):
            await services.execute_event(event=event(), context=context())
        assert calls == {"create": [], "complete": [], "write": []}

    asyncio.run(case())
