"""Pure/fake-store proof for the one-event living-community executor."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from simulation import community_executor as executor
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_day_queue import build_day_queue
from simulation.community_staffing import active_assignments
from simulation.community_ticket_plan import OPEN_TO_CLAIM_MINUTES, work_minutes


NOW = datetime(2026, 10, 13, 16, 0, tzinfo=timezone.utc)
# Burn-in day zero: 146 tickets x open/claim/complete plus shift milestones (service model).
DAY_ZERO_EVENTS = 594


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
        if isinstance(wanted, dict):
            if "$gt" in wanted and not (actual is not None and actual > wanted["$gt"]):
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


class Runs:
    def __init__(self, row):
        self.row = deepcopy(row)

    async def find_one(self, query, _projection=None):
        return deepcopy(self.row) if _matches(self.row, query) else None

    async def find_one_and_update(self, query, update, **_kwargs):
        if not _matches(self.row, query):
            return None
        for path, value in update.get("$set", {}).items():
            _set(self.row, path, value)
        return deepcopy(self.row)


class Store:
    def __init__(self, row=None):
        self.sim_runs = Runs(row or run_row())


def run_row(**changes):
    row = {
        "run_id": "run-1",
        "state": "RUNNING",
        "cursor": 0,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "execution_lease_generation": 7,
        "execution_lease": {
            "holder_id": "worker-a",
            "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
        },
    }
    row.update(changes)
    return row


def event(number=1, **changes):
    values = {
        "event_id": f"event-{number}",
        "stream_kind": "routine_dispatch",
        "action_type": "shower_assistance",
        "day_index": 0,
        "minute": 540 + number,
        "actor_id": "sim:staff:nursing:care_aide:01",
        "actor_name": "SIM - Care Aide 01",
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "department": "nursing",
        "target_type": "resident",
        "target_id": "sim:resident:001",
        "adapter": "canonical_staff_task",
    }
    values.update(changes)
    return executor.ExecutorEvent(**values)


def proof(item, context, status="completed", **changes):
    values = {
        "receipt_id": f"receipt:{item.event_id}",
        "simulation_event_id": item.event_id,
        "simulation_run_id": context.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "execution_cursor": context.cursor,
        "execution_fence": context.fence,
        "actor_id": item.actor_id,
        "actor_type": item.actor_type,
        "identity_basis": item.identity_basis,
        "simulated": True,
        "channel": "simulator",
        "authority": "living_community_executor",
        "action_type": item.action_type,
        "related_object_type": item.target_type,
        "related_object_id": item.target_id,
        "status": status,
    }
    values.update(changes)
    return values


class Services:
    def __init__(self, prior=None, *, persist=True, status="completed", error=None):
        self.evidence = prior
        self.persist = persist
        self.status = status
        self.error = error
        self.executions = []
        self.loads = []

    async def load_evidence(self, **query):
        self.loads.append(query)
        return deepcopy(self.evidence)

    async def execute_event(self, *, event, context):
        self.executions.append((event, context))
        assert context.providers_allowed is False
        assert context.simulation_scope == SIMULATION_SCOPE
        assert context.simulation_community_id == COMMUNITY_ID
        if self.error:
            raise self.error
        if self.persist:
            self.evidence = proof(event, context, self.status)
        return {"claimed_success": True}  # Deliberately not accepted as evidence.


def step(store, services, events=None, **changes):
    changes.setdefault("now", NOW)
    changes.setdefault("clock", lambda: NOW)
    return executor.execute_one(
        "run-1", "worker-a", 7,
        store=store,
        services=services,
        events=events or (event(1), event(2)),
        **changes,
    )


def test_day_queue_combines_existing_plans_with_explicit_synthetic_staff():
    queue = build_day_queue()
    assert len(queue) == DAY_ZERO_EVENTS
    assert sum(row.stream_kind == "canonical_shift_milestone" for row in queue) == 111
    assert len({row.event_id for row in queue}) == len(queue)
    assert {row.stream_kind for row in queue} == {
        "routine_ticket_phase", "canonical_shift_milestone",
    }
    assert all(row.actor_type == "simulated-agent" for row in queue)
    assert all(row.identity_basis == "synthetic" and row.simulated for row in queue)
    assert all(
        row.actor_id.startswith("sim:staff:")
        or row.task_phase == "open" and row.opened_by == "resident" and row.actor_id == row.target_id
        for row in queue
    )
    assert all((queue[index].day_index, queue[index].minute)
               <= (queue[index + 1].day_index, queue[index + 1].minute)
               for index in range(len(queue) - 1))
    family = next(row for row in queue if row.action_type == "family_call_coordination")
    assert family.blocked_capability == "outbound_family_call"
    front_desk = next(row for row in queue if row.action_type == "front_desk_message_follow_up")
    assert front_desk.department == "front_desk"
    assert front_desk.blocked_capability == "outbound_front_desk_call"


def test_one_worker_claims_and_completes_while_on_site_after_a_truthful_wait():
    queue = build_day_queue()
    by_workflow = {}
    for row in queue:
        if row.stream_kind == "routine_ticket_phase":
            by_workflow.setdefault(row.workflow_event_id, []).append(row)
    for phases in by_workflow.values():
        opened, claimed, completed = phases
        assert [row.task_phase for row in phases] == ["open", "claim", "complete"]
        if opened.opened_by == "resident":
            assert opened.actor_id == opened.target_id
        else:
            on_site = {item["actor_id"] for item in active_assignments(opened.day_index, opened.minute)}
            assert opened.actor_id in on_site
        assert claimed.actor_id == completed.actor_id
        absolute = [row.day_index * 1440 + row.minute for row in phases]
        assert absolute[0] == opened.requested_at_minute == claimed.requested_at_minute
        assert claimed.waited_minutes == absolute[1] - absolute[0] - OPEN_TO_CLAIM_MINUTES >= 0
        assert (claimed.wait_reason == "none") is (claimed.waited_minutes == 0)
        assert absolute[2] - absolute[1] == work_minutes(claimed.action_type)
        for minute in (absolute[1], absolute[2] - 1):
            active = {item["actor_id"] for item in active_assignments(*divmod(minute, 1440))}
            assert claimed.actor_id in active


@pytest.mark.parametrize("status,meaning", sorted(executor.RECEIPT_RESULTS.items()))
def test_executes_one_event_then_advances_exact_cursor_on_durable_evidence(status, meaning):
    async def case():
        store, services = Store(), Services(status=status)
        result = await step(store, services)
        assert len(services.executions) == 1
        item, context = services.executions[0]
        assert item.event_id == "event-1" and context.cursor == 0 and context.fence == 7
        assert result == executor.StepResult(
            "event-1", "receipt:event-1", status, meaning, 0, 1, False,
        )
        assert store.sim_runs.row["cursor"] == 1
        assert store.sim_runs.row["last_event_id"] == "event-1"
        assert store.sim_runs.row["last_evidence_status"] == status
    asyncio.run(case())


def test_replay_uses_existing_durable_evidence_without_reexecuting():
    async def case():
        store = Store()
        context = executor.ExecutionContext(
            "run-1", "worker-a", 7, 0, SIMULATION_SCOPE, COMMUNITY_ID,
        )
        services = Services(prior=proof(event(1), context))
        result = await step(store, services)
        assert services.executions == []
        assert result.idempotent_replay is True
        assert store.sim_runs.row["cursor"] == 1
    asyncio.run(case())


def test_claimed_return_without_reloaded_durable_evidence_never_advances():
    async def case():
        store, services = Store(), Services(persist=False)
        with pytest.raises(executor.CommunityExecutorError, match="no durable evidence"):
            await step(store, services)
        assert len(services.executions) == 1
        assert store.sim_runs.row["cursor"] == 0
        assert "last_event_id" not in store.sim_runs.row
    asyncio.run(case())


@pytest.mark.parametrize("change", [
    {"status": "attempted"},
    {"simulation_event_id": "different"},
    {"simulation_run_id": "different"},
    {"simulation_scope": "demo_room"},
    {"simulation_community_id": "different"},
    {"execution_cursor": 9},
    {"execution_fence": 6},
    {"actor_id": "sim:staff:nursing:care_aide:02"},
    {"actor_type": "system"},
    {"identity_basis": "system"},
    {"simulated": False},
    {"channel": "staff_ui"},
    {"authority": "other"},
    {"action_type": "different"},
    {"related_object_type": "task"},
    {"related_object_id": "different"},
])
def test_mismatched_or_weak_evidence_never_advances(change):
    async def case():
        store = Store()
        context = executor.ExecutionContext(
            "run-1", "worker-a", 7, 0, SIMULATION_SCOPE, COMMUNITY_ID,
        )
        services = Services(prior=proof(event(1), context, **change))
        with pytest.raises(executor.CommunityExecutorError):
            await step(store, services)
        assert services.executions == []
        assert store.sim_runs.row["cursor"] == 0
    asyncio.run(case())


@pytest.mark.parametrize("row, message", [
    (run_row(state="PAUSED"), "paused"),
    (run_row(execution_lease_generation=8), "stale"),
    (run_row(execution_lease={
        "holder_id": "worker-b",
        "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
    }), "stale"),
    (run_row(execution_lease={
        "holder_id": "worker-a",
        "expires_at": (NOW - timedelta(seconds=1)).isoformat(),
    }), "expired"),
])
def test_paused_stale_wrong_owner_and_expired_lease_refuse_before_service(row, message):
    async def case():
        store, services = Store(row), Services()
        with pytest.raises(executor.CommunityExecutorError, match=message):
            await step(store, services)
        assert services.loads == [] and services.executions == []
        assert store.sim_runs.row["cursor"] == 0
    asyncio.run(case())


def test_service_failure_leaves_cursor_and_evidence_metadata_untouched():
    async def case():
        store, services = Store(), Services(error=RuntimeError("canonical failure"))
        with pytest.raises(RuntimeError, match="canonical failure"):
            await step(store, services)
        assert store.sim_runs.row["cursor"] == 0
        assert "last_evidence_receipt_id" not in store.sim_runs.row
    asyncio.run(case())


def test_cas_refusal_after_evidence_is_recoverable_by_replay():
    async def case():
        store, services = Store(), Services()
        original = services.load_evidence

        async def expire_after_evidence(**query):
            loaded = await original(**query)
            if loaded:
                store.sim_runs.row["execution_lease"]["expires_at"] = (
                    NOW - timedelta(seconds=1)
                ).isoformat()
            return loaded

        services.load_evidence = expire_after_evidence
        with pytest.raises(Exception, match="heartbeat refused"):
            await step(store, services)
        assert services.evidence and store.sim_runs.row["cursor"] == 0

        store.sim_runs.row["execution_lease_generation"] = 8
        store.sim_runs.row["execution_lease"] = {
            "holder_id": "worker-b",
            "expires_at": (NOW + timedelta(seconds=30)).isoformat(),
        }
        services.load_evidence = original
        services.evidence = None  # Exact-fence query excludes the prior receipt.
        result = await executor.execute_one(
            "run-1", "worker-b", 8, store=store, services=services,
            events=(event(1), event(2)), now=NOW, clock=lambda: NOW,
        )
        assert result.idempotent_replay is False
        assert len(services.executions) == 2
        assert store.sim_runs.row["cursor"] == 1
    asyncio.run(case())


def test_lease_expiring_during_service_work_refuses_fresh_heartbeat():
    async def case():
        store, services = Store(), Services()
        after_expiry = NOW + timedelta(seconds=31)
        with pytest.raises(Exception, match="heartbeat refused"):
            await step(store, services, clock=lambda: after_expiry)
        assert services.evidence and store.sim_runs.row["cursor"] == 0
        assert "last_event_id" not in store.sim_runs.row
    asyncio.run(case())


def test_default_services_invalid_queue_and_cursor_fail_closed():
    async def case():
        store = Store()
        with pytest.raises(executor.CommunityExecutorError, match="no default provider"):
            await executor.execute_one("run-1", "worker-a", 7, store=store, now=NOW)
        with pytest.raises(executor.CommunityExecutorError, match="unique ids"):
            await step(store, Services(), events=(event(1), event(1)))
        bad_actor = event(1, actor_type="system", simulated=False)
        with pytest.raises(executor.CommunityExecutorError, match="synthetic actor"):
            await step(store, Services(), events=(bad_actor,))
        store.sim_runs.row["cursor"] = 2
        with pytest.raises(executor.CommunityExecutorError, match="outside"):
            await step(store, Services(), events=(event(1), event(2)))
    asyncio.run(case())


def test_naive_timestamp_is_refused_before_any_store_or_service_call():
    async def case():
        store, services = Store(), Services()
        with pytest.raises(executor.CommunityExecutorError, match="timezone-aware"):
            await step(store, services, now=datetime(2026, 10, 13, 16, 0))
        assert services.loads == [] and services.executions == []
        assert store.sim_runs.row["cursor"] == 0
    asyncio.run(case())
