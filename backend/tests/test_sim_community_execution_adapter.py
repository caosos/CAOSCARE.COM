"""Focused proof for the canonical community executor services adapter."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from simulation import community_executor as executor
from simulation import community_ticket_staging as ticket
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_execution_adapter import (
    CanonicalCommunityExecutionServices,
    CommunityExecutionAdapterError,
    EXECUTOR_AUTHORITY,
)
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_shift_execution import ShiftExecutionError
from simulation.community_day_queue import build_day_queue
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN


NOW = datetime(2026, 10, 13, 16, 0, tzinfo=timezone.utc)


def _get(row, path):
    value = row
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(row, query):
    for key, wanted in query.items():
        actual = _get(row, key)
        if isinstance(wanted, dict) and "$gt" in wanted:
            if actual is None or actual <= wanted["$gt"]:
                return False
        elif isinstance(wanted, dict) and "$nin" in wanted:
            if actual in wanted["$nin"]:
                return False
        elif isinstance(wanted, dict) and "$ne" in wanted:
            if actual == wanted["$ne"]:
                return False
        elif actual != wanted:
            return False
    return True


def _set(row, path, value):
    target = row
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = deepcopy(value)


class Collection:
    def __init__(self, rows=()):
        self.rows = [deepcopy(row) for row in rows]

    async def find_one(self, query, _projection=None, **_kwargs):
        matches = [row for row in self.rows if _matches(row, query)]
        if not matches:
            return None
        row = matches[-1] if _kwargs.get("sort") else matches[0]
        return deepcopy(row)


class RunCollection:
    def __init__(self):
        self.row = {
            "run_id": "run-1", "state": "RUNNING", "cursor": 3,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "execution_lease_generation": 7,
            "execution_lease": {
                "holder_id": "executor-a",
                "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
            },
        }

    async def find_one(self, query, _projection=None):
        return deepcopy(self.row) if _matches(self.row, query) else None

    async def find_one_and_update(self, query, update, **_kwargs):
        if not _matches(self.row, query):
            return None
        for path, value in update.get("$set", {}).items():
            _set(self.row, path, value)
        return deepcopy(self.row)


class Store:
    def __init__(self, *, tasks=(), receipts=()):
        self.staff_tasks = Collection(tasks)
        self.receipts = Collection(receipts)
        self.sim_runs = RunCollection()
        self.sim_shift_covers = Collection()


def event(**changes):
    phase = changes.pop("task_phase", OPEN)
    minute = {OPEN: 470, CLAIM: 475, COMPLETE: 478}[phase]
    resident_origin = phase == OPEN
    values = {
        "event_id": f"day-000:resident-001:morning_medication_reminder:ticket_{phase}",
        "stream_kind": "routine_ticket_phase",
        "action_type": "morning_medication_reminder",
        "day_index": 0,
        "minute": minute,
        "actor_id": "sim:resident:001" if resident_origin else "sim:staff:nursing:med_tech:01",
        "actor_name": "SIM Resident 001" if resident_origin else "SIM - Medication Technician 01",
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "department": "nursing",
        "target_type": "resident",
        "target_id": "sim:resident:001",
        "adapter": "canonical_staff_task",
        "blocked_capability": "medication_kiosk",
        "workflow_event_id": "day-000:resident-001:morning_medication_reminder",
        "task_phase": phase,
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
        "visibility_role": item.department,
        "conversation_session_id": ticket.event_session(item),
        "simulation_run_id": ctx.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulated": True,
    }
    values.update(changes)
    return values


def completion(item=None, ctx=None, **changes):
    item, ctx = item or event(task_phase=COMPLETE), ctx or context()
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


def origin(item=None, ctx=None, **changes):
    item, ctx = item or event(), ctx or context()
    values = {
        "receipt_id": "rcpt-origin",
        "related_object_type": "task",
        "related_object_id": "task-1",
        "action_type": "resident_request_created",
        "simulation_run_id": ctx.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "actor_id": item.target_id,
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "channel": "simulator",
        "simulated": True,
        "status": "created",
        "correlation_id": "rcpt-origin",
    }
    values.update(changes)
    return values


def started(item=None, ctx=None, **changes):
    item, ctx = item or event(task_phase=CLAIM), ctx or context()
    values = completion(item, ctx,
        receipt_id="rcpt-task-start", action_type="task_in_progress",
        status="in_progress",
    )
    values.update(changes)
    return values


def harness(store):
    calls = {"create": [], "start": [], "complete": [], "write": []}

    async def create(**kwargs):
        calls["create"].append(kwargs)
        created = task(kwargs["event"], kwargs["context"])
        store.staff_tasks.rows.append(deepcopy(created))
        store.receipts.rows.append(origin(kwargs["event"], kwargs["context"]))
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

    async def start_task(**kwargs):
        calls["start"].append(kwargs)
        stored = next(row for row in store.staff_tasks.rows if row["task_id"] == kwargs["task_id"])
        stored.update(status="in_progress", assigned_to=kwargs["actor"].actor_id)
        proof = started()
        proof["actor_id"] = kwargs["actor"].actor_id
        store.receipts.rows.append(deepcopy(proof))
        return deepcopy(stored), proof

    async def write(**kwargs):
        calls["write"].append(kwargs)
        doc = {key: value for key, value in kwargs.items() if key != "provenance"}
        doc.update(kwargs["provenance"])
        doc["receipt_id"] = f"rcpt-event-{len(calls['write'])}"
        doc["created_at"] = f"2026-10-13T16:00:0{len(calls['write'])}+00:00"
        store.receipts.rows.append(deepcopy(doc))
        return doc

    services = CanonicalCommunityExecutionServices(
        store=store,
        request_creator=create,
        task_loader=load,
        task_starter=start_task,
        task_completer=complete_task,
        receipt_writer=write,
    )
    return services, calls


def test_routine_is_open_claimed_and_completed_as_three_visible_phases():
    async def case():
        opened_event = event(task_phase=OPEN)
        claimed_event = event(task_phase=CLAIM)
        completed_event = event(task_phase=COMPLETE)
        ctx, store = context(), Store()
        services, calls = harness(store)
        opened = await services.execute_event(event=opened_event, context=ctx)
        assert opened["status"] == "completed"
        assert store.staff_tasks.rows[0]["status"] == "pending"
        assert len(calls["create"]) == len(calls["write"]) == 1
        assert calls["start"] == calls["complete"] == []
        assert calls["create"][0]["priority"] == "high"

        claimed = await services.execute_event(event=claimed_event, context=ctx)
        assert claimed["status"] == "completed"
        assert store.staff_tasks.rows[0]["status"] == "in_progress"
        assert len(calls["start"]) == 1 and calls["complete"] == []

        proof = await services.execute_event(event=completed_event, context=ctx)
        assert proof["status"] == "completed"
        assert store.staff_tasks.rows[0]["status"] == "completed"
        assert len(calls["complete"]) == 1 and len(calls["write"]) == 3
        assert calls["complete"][0]["actor"].channel == "simulator"
        assert "no claim of administration" in calls["complete"][0]["note"]
        assert proof["simulation_event_id"] == completed_event.event_id
        assert proof["execution_cursor"] == 3 and proof["execution_fence"] == 7
        assert proof["authority"] == EXECUTOR_AUTHORITY
        assert proof["parent_receipt_id"] == "rcpt-task-complete"
        assert proof["related_object_type"] == "resident"
        assert proof["related_object_id"] == completed_event.target_id
        assert proof["after_state"]["blocked_capability_not_invoked"] == "medication_kiosk"
        assert proof["provider_refs"] == [] and proof["result_label"] == "simulated"
        assert executor._validate_evidence(proof, completed_event, ctx) == proof

        loaded = await services.load_evidence(
            run_id=ctx.run_id, event_id=completed_event.event_id,
            expected_cursor=ctx.cursor, execution_fence=ctx.fence,
        )
        assert loaded["receipt_id"] == "rcpt-event-3"

    asyncio.run(case())


def test_executor_ticks_expose_canonical_ticket_movement_across_phase_events():
    async def case():
        phases = tuple(event(task_phase=phase) for phase in (OPEN, CLAIM, COMPLETE))
        item, store = phases[0], Store()
        store.sim_runs.row["cursor"] = 0
        services, calls = harness(store)

        opened = await executor.execute_one(
            "run-1", "executor-a", 7, store=store, services=services,
            events=phases, now=NOW, clock=lambda: NOW,
        )
        assert opened.receipt_status == "completed"
        assert opened.cursor_before == 0 and opened.cursor_after == 1
        assert store.staff_tasks.rows[0]["status"] == "pending"

        claimed = await executor.execute_one(
            "run-1", "executor-a", 7, store=store, services=services,
            events=phases, now=NOW, clock=lambda: NOW,
        )
        assert claimed.receipt_status == "completed"
        assert claimed.cursor_before == 1 and claimed.cursor_after == 2
        assert store.staff_tasks.rows[0]["status"] == "in_progress"
        assert store.staff_tasks.rows[0]["assigned_to"] == phases[1].actor_id

        completed = await executor.execute_one(
            "run-1", "executor-a", 7, store=store, services=services,
            events=phases, now=NOW, clock=lambda: NOW,
        )
        assert completed.receipt_status == "completed"
        assert completed.cursor_before == 2 and completed.cursor_after == 3
        assert store.staff_tasks.rows[0]["status"] == "completed"
        assert len(calls["create"]) == len(calls["start"]) == len(calls["complete"]) == 1

    asyncio.run(case())


def test_retry_after_crash_between_canonical_start_and_phase_receipt_is_idempotent():
    async def case():
        phases = tuple(event(task_phase=phase) for phase in (OPEN, CLAIM, COMPLETE))
        item, store = phases[0], Store()
        store.sim_runs.row["cursor"] = 0
        services, calls = harness(store)
        await executor.execute_one(
            "run-1", "executor-a", 7, store=store, services=services,
            events=phases, now=NOW, clock=lambda: NOW,
        )

        task_id = store.staff_tasks.rows[0]["task_id"]
        await services.task_starter(
            task_id=task_id, actor=ticket.actor(phases[1]),
            user=ticket.staff_user(phases[1]),
        )
        assert len(calls["start"]) == 1

        recovered = await executor.execute_one(
            "run-1", "executor-a", 7, store=store, services=services,
            events=phases, now=NOW, clock=lambda: NOW,
        )
        assert recovered.receipt_status == "completed"
        assert recovered.cursor_before == 1 and recovered.cursor_after == 2
        assert len(calls["start"]) == 1
        assert calls["complete"] == []

    asyncio.run(case())


def test_replay_and_crash_recovery_do_not_repeat_canonical_actions():
    async def case():
        item, ctx = event(task_phase=COMPLETE), context()
        done_task = task(item, ctx, status="completed")
        store = Store(tasks=(done_task,), receipts=(completion(item, ctx),))
        services, calls = harness(store)

        first = await services.execute_event(event=item, context=ctx)
        assert first["receipt_id"] == "rcpt-event-1"
        assert calls["create"] == [] and calls["complete"] == []
        second = await services.execute_event(event=item, context=ctx)
        assert second["receipt_id"] == "rcpt-event-1"
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
        queue = build_day_queue()
        # SIM-005A: only overnight care staff carry in from day -1.
        item = next(row for row in queue if row.stream_kind == "canonical_shift_milestone"
                    and row.target_id.startswith("sim:shift:-1:"))
        assert item.event_id == (
            "sim:shift-event:0:0345:handoff:sim:staff:nursing:care_aide:14"
        )
        assert item.target_id == "sim:shift:-1:sim:staff:nursing:care_aide:14:night"
        ctx, store = context(cursor=queue.index(item)), Store()
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert len(calls["write"]) == 1
        assert calls["create"] == [] and calls["complete"] == []
        assert executor._validate_evidence(proof, item, ctx) == proof

    asyncio.run(case())


def test_existing_open_task_recovers_open_phase_before_claiming():
    async def case():
        store = Store(tasks=(task(),), receipts=(origin(),))
        services, calls = harness(store)
        proof = await services.execute_event(event=event(), context=context())
        assert proof["status"] == "completed"
        assert calls["create"] == []
        assert calls["start"] == calls["complete"] == []

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
        assert calls == {"create": [], "start": [], "complete": [], "write": []}
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
        assert calls == {"create": [], "start": [], "complete": [], "write": []}
        assert store.receipts.rows == []

    asyncio.run(case())


def test_provider_permission_and_unproven_closed_task_fail_closed():
    async def case():
        services, calls = harness(Store())
        with pytest.raises(CommunityExecutionAdapterError, match="never permits provider"):
            await services.execute_event(event=event(), context=context(providers_allowed=True))
        assert calls["create"] == []

        item = event(task_phase=COMPLETE)
        store = Store(tasks=(task(item, status="completed"),))
        services, calls = harness(store)
        with pytest.raises(CommunityExecutionAdapterError, match="no durable receipt"):
            await services.execute_event(event=item, context=context())
        assert calls == {"create": [], "start": [], "complete": [], "write": []}

    asyncio.run(case())
