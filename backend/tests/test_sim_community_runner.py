"""Focused fake-store proof for one fenced community runner tick."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from simulation import community_executor as executor
from simulation import community_run_lease as lease
from simulation import community_runner as runner
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)


def _get(row, path):
    value = row
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(row, query):
    for key, wanted in query.items():
        if key == "$or":
            if not any(_matches(row, item) for item in wanted):
                return False
            continue
        actual = _get(row, key)
        if isinstance(wanted, dict):
            if "$exists" in wanted and (actual is not None) != wanted["$exists"]:
                return False
            if "$in" in wanted and actual not in wanted["$in"]:
                return False
            if "$lte" in wanted and not (actual is not None and actual <= wanted["$lte"]):
                return False
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
        for path, amount in update.get("$inc", {}).items():
            _set(self.row, path, (_get(self.row, path) or 0) + amount)
        for path, value in update.get("$set", {}).items():
            _set(self.row, path, value)
        for path in update.get("$unset", {}):
            self.row.pop(path, None)
        return deepcopy(self.row)


class Store:
    def __init__(self, row):
        self.sim_runs = Runs(row)


def run_row(**changes):
    row = {
        "run_id": "run-1",
        "state": "RUNNING",
        "cursor": 0,
        "sim_minute": 100,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    row.update(changes)
    return row


def event(number=1, minute=10, **changes):
    values = {
        "event_id": f"event-{number}",
        "stream_kind": "routine_dispatch",
        "action_type": "shower_assistance",
        "day_index": 0,
        "minute": minute,
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


def proof(item, fence, **changes):
    values = {
        "receipt_id": f"receipt:{item.event_id}",
        "simulation_event_id": item.event_id,
        "simulation_run_id": "run-1",
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "execution_cursor": 0,
        "execution_fence": fence,
        "actor_id": item.actor_id,
        "actor_type": item.actor_type,
        "identity_basis": item.identity_basis,
        "simulated": True,
        "channel": "simulator",
        "authority": "living_community_executor",
        "action_type": item.action_type,
        "related_object_type": item.target_type,
        "related_object_id": item.target_id,
        "status": "completed",
    }
    values.update(changes)
    return values


class Timeline:
    def __init__(self, store, events, receipts=(), hook=None):
        self.store = store
        self.events = tuple(events)
        self.receipts = tuple(receipts)
        self.hook = hook

    async def load_events(self, **_query):
        return self.events

    async def load_receipts(self, **_query):
        if self.hook:
            self.hook(self.store)
        return deepcopy(self.receipts)

    async def load_run(self, **_query):
        return deepcopy(self.store.sim_runs.row)


class Services:
    def __init__(self):
        self.evidence = None
        self.executions = []

    async def load_evidence(self, **_query):
        return deepcopy(self.evidence)

    async def execute_event(self, *, event, context):
        self.executions.append(event.event_id)
        self.evidence = proof(event, context.fence)


def invoke(store, timeline, services=None):
    return runner.tick(
        "run-1", "worker-a", store=store, timeline=timeline,
        services=services or Services(), now=NOW, clock=lambda: NOW,
    )


def test_tick_executes_at_most_one_due_event_and_releases_lease():
    async def case():
        store, services = Store(run_row()), Services()
        result = await invoke(store, Timeline(store, (event(1), event(2, 20))), services)
        assert result.status == "executed" and result.cursor_after == 1
        assert services.executions == ["event-1"]
        assert store.sim_runs.row["cursor"] == 1
        assert "execution_lease" not in store.sim_runs.row
    asyncio.run(case())


def test_crash_receipt_from_prior_fence_advances_without_duplicate_execution():
    async def case():
        item = event(1)
        store = Store(run_row(
            execution_lease_generation=4,
            execution_lease={
                "holder_id": "crashed-worker",
                "expires_at": (NOW - timedelta(seconds=1)).isoformat(),
            },
        ))
        services = Services()
        result = await invoke(store, Timeline(store, (item,), (proof(item, 4),)), services)
        assert result.action == "advance_cursor_from_receipt"
        assert result.idempotent_replay is True and result.fence == 5
        assert services.executions == [] and store.sim_runs.row["cursor"] == 1
    asyncio.run(case())


def test_recovery_refuses_when_lease_expires_before_cursor_advance():
    async def case():
        item = event(1)
        store = Store(run_row())
        with pytest.raises(lease.RunLeaseError, match="heartbeat refused"):
            await runner.tick(
                "run-1",
                "worker-a",
                store=store,
                timeline=Timeline(store, (item,), (proof(item, 1),)),
                services=Services(),
                now=NOW,
                clock=lambda: NOW + timedelta(seconds=31),
            )
        assert store.sim_runs.row["cursor"] == 0
        assert "last_event_id" not in store.sim_runs.row
    asyncio.run(case())


@pytest.mark.parametrize("state,expected", [("PAUSED", "paused")])
def test_paused_run_is_reconciled_without_heartbeat_or_execution(state, expected):
    async def case():
        store, services = Store(run_row(state=state)), Services()
        result = await invoke(store, Timeline(store, (event(1),)), services)
        assert result.status == expected and result.action == "none"
        assert services.executions == [] and store.sim_runs.row["cursor"] == 0
        assert "execution_lease" not in store.sim_runs.row
    asyncio.run(case())


@pytest.mark.parametrize("item,expected", [
    (event(1, minute=101), "future"),
    (event(1, blocked_capability="outbound_call"), "blocked"),
])
def test_future_and_blocked_work_never_execute(item, expected):
    async def case():
        store, services = Store(run_row()), Services()
        result = await invoke(store, Timeline(store, (item,)), services)
        assert result.status == expected
        assert services.executions == [] and store.sim_runs.row["cursor"] == 0
    asyncio.run(case())


def test_inconsistent_evidence_fails_closed_and_releases():
    async def case():
        item = event(1)
        duplicated = (proof(item, 1), proof(item, 1, receipt_id="receipt:duplicate"))
        store, services = Store(run_row()), Services()
        with pytest.raises(runner.CommunityRunnerError, match="inconsistent"):
            await invoke(store, Timeline(store, (item,), duplicated), services)
        assert services.executions == [] and store.sim_runs.row["cursor"] == 0
        assert "execution_lease" not in store.sim_runs.row
    asyncio.run(case())


def test_stale_fence_during_snapshot_fails_before_execution_and_keeps_new_owner():
    async def case():
        def steal(store):
            store.sim_runs.row["execution_lease_generation"] += 1
            store.sim_runs.row["execution_lease"]["holder_id"] = "worker-b"

        store, services = Store(run_row()), Services()
        with pytest.raises(lease.RunLeaseError, match="heartbeat refused"):
            await invoke(store, Timeline(store, (event(1),), hook=steal), services)
        assert services.executions == [] and store.sim_runs.row["cursor"] == 0
        assert store.sim_runs.row["execution_lease"]["holder_id"] == "worker-b"
    asyncio.run(case())


def test_stale_timeline_snapshot_fails_before_execution():
    async def case():
        class StaleTimeline(Timeline):
            async def load_run(self, **_query):
                row = await super().load_run(**_query)
                row["sim_minute"] -= 1
                return row

        store, services = Store(run_row()), Services()
        with pytest.raises(runner.CommunityRunnerError, match="snapshot is stale"):
            await invoke(store, StaleTimeline(store, (event(1),)), services)
        assert services.executions == [] and store.sim_runs.row["cursor"] == 0
        assert "execution_lease" not in store.sim_runs.row
    asyncio.run(case())


def test_stopped_run_cannot_acquire_or_execute():
    async def case():
        store, services = Store(run_row(state="STOPPED")), Services()
        with pytest.raises(lease.RunLeaseError, match="stopped"):
            await invoke(store, Timeline(store, (event(1),)), services)
        assert services.executions == [] and store.sim_runs.row["cursor"] == 0
    asyncio.run(case())
