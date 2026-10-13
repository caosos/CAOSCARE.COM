"""Durable cross-process proof for owner/admin manual STEP."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from routes.actor_context import ActorContext
from simulation import community_run_lease as lease
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_manual_step import COMPLETED, REQUESTED, execute_one
from simulation.community_timeline import build_90_day_timeline
from tests.community_runtime_fake import RuntimeStore


NOW = datetime(2026, 10, 13, 22, 0, tzinfo=timezone.utc)
PLAN = build_90_day_timeline()
RUN_ID = "simrun:living:manual-step"
OWNER = ActorContext(
    "owner-1", "real-human", "authenticated", "staff_ui",
    name="Michael", role="owner",
)
AUTHORITY = "admin_override:owner"


def run_row():
    return {
        "_id": RUN_ID,
        "run_id": RUN_ID,
        "state": "PAUSED",
        "cursor": 0,
        "sim_minute": 0,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": "living_community_burn_in",
        "plan_revision": PLAN.plan_revision,
        "plan_digest_sha256": PLAN.digest_sha256,
        "event_count": PLAN.event_count,
        "timeline_days": PLAN.day_count,
        "timeline_end_minute": PLAN.day_count * 1440 - 1,
        "residents_provisioned": True,
        "origin_receipt_id": "receipt:origin",
        "last_transition_receipt_id": "receipt:ready",
        "updated_at": NOW.isoformat(),
    }


class Timeline:
    event_count = PLAN.event_count

    def __init__(self, store):
        self.store = store

    def event_at(self, cursor):
        return PLAN.events[cursor] if 0 <= cursor < PLAN.event_count else None

    async def load_run(self, *, run_id):
        return await self.store.sim_runs.find_one({"run_id": run_id}, {"_id": 0})

    async def load_bounded_evidence(
        self, *, run_id, cursor, event_id, last_event_id, last_receipt_id,
    ):
        rows = [row for row in self.store.receipts.docs
                if row.get("simulation_run_id") == run_id]
        return {
            "current": deepcopy([row for row in rows
                                 if row.get("simulation_event_id") == event_id]),
            "previous": deepcopy([row for row in rows
                                  if row.get("receipt_id") == last_receipt_id]),
            "future": deepcopy([row for row in rows
                                if isinstance(row.get("execution_cursor"), int)
                                and row["execution_cursor"] > cursor][:1]),
        }


class Services:
    def __init__(self, store, *, fail=False, on_execute=None):
        self.store = store
        self.fail = fail
        self.on_execute = on_execute

    async def load_evidence(self, *, run_id, event_id, **_query):
        return next((deepcopy(row) for row in self.store.receipts.docs if (
            row.get("simulation_run_id") == run_id
            and row.get("simulation_event_id") == event_id
        )), None)

    async def execute_event(self, *, event, context):
        if self.on_execute:
            await self.on_execute(context)
        if self.fail:
            raise RuntimeError("injected canonical event failure")
        assert context.lease_mode == lease.MANUAL_STEP_MODE
        proof = {
            "_id": f"receipt:{event.event_id}",
            "receipt_id": f"receipt:{event.event_id}",
            "simulation_event_id": event.event_id,
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "execution_cursor": context.cursor,
            "execution_fence": context.fence,
            "actor_id": event.actor_id,
            "actor_type": event.actor_type,
            "identity_basis": event.identity_basis,
            "simulated": True,
            "channel": "simulator",
            "authority": "living_community_executor",
            "action_type": event.action_type,
            "related_object_type": event.target_type,
            "related_object_id": event.target_id,
            "status": "completed",
        }
        await self.store.receipts.insert_one(proof)


async def ready(row):
    return {"run_id": row["run_id"], "resident_count": 10,
            "department_digest": "departments-exact"}


async def invoke(store, services, *, operation_key="manual-step-1"):
    return await execute_one(
        OWNER, AUTHORITY, RUN_ID, 0, 0, operation_key, "http-stepper-1",
        store=store, plan=PLAN, timeline=Timeline(store), services=services,
        ready=ready, now=NOW, clock=lambda: NOW,
    )


def test_manual_step_keeps_run_paused_and_blocks_other_processes():
    async def case():
        store = RuntimeStore()
        store.sim_runs.docs.append(run_row())

        async def competing_process(context):
            row = await store.sim_runs.find_one({"run_id": RUN_ID}, {"_id": 0})
            assert row["state"] == "PAUSED"
            assert row["execution_lease"]["mode"] == lease.MANUAL_STEP_MODE
            with pytest.raises(lease.RunLeaseError, match="already leased"):
                await lease.acquire(
                    RUN_ID, "other-process", store=store, now=NOW,
                )
            with pytest.raises(lease.RunLeaseError, match="already leased"):
                await lease.acquire(
                    RUN_ID, "other-manual-step", store=store, now=NOW,
                    mode=lease.MANUAL_STEP_MODE,
                    expected_cursor=0, expected_sim_minute=0,
                )
            assert context.fence == row["execution_lease_generation"]

        result = await invoke(store, Services(store, on_execute=competing_process))
        final = result["run"]
        assert final["state"] == "PAUSED" and final["cursor"] == 1
        assert "execution_lease" not in store.sim_runs.docs[0]
        assert result["tick"].cursor_before == 0
        assert result["tick"].cursor_after == 1
        actions = [row.get("action_type") for row in store.receipts.docs]
        assert REQUESTED in actions and COMPLETED in actions
        completed = next(row for row in store.receipts.docs
                         if row.get("action_type") == COMPLETED)
        assert completed["actor_id"] == OWNER.actor_id
        assert completed["authority"] == AUTHORITY
        assert completed["after_state"]["last_evidence_receipt_id"] == result["tick"].receipt_id

    asyncio.run(case())


def test_failed_manual_step_releases_lease_without_unpausing_or_advancing():
    async def case():
        store = RuntimeStore()
        store.sim_runs.docs.append(run_row())
        with pytest.raises(RuntimeError, match="injected canonical event failure"):
            await invoke(store, Services(store, fail=True))
        row = store.sim_runs.docs[0]
        assert row["state"] == "PAUSED" and row["cursor"] == 0
        assert "execution_lease" not in row
        actions = [item.get("action_type") for item in store.receipts.docs]
        assert REQUESTED in actions and COMPLETED not in actions

    asyncio.run(case())


def test_completed_operation_replays_without_claiming_or_executing_next_event():
    async def case():
        store = RuntimeStore()
        store.sim_runs.docs.append(run_row())
        services = Services(store)
        first = await invoke(store, services)
        replay = await invoke(store, Services(store, fail=True))
        assert replay["idempotent_replay"] is True and replay["tick"] is None
        assert replay["run"]["cursor"] == first["run"]["cursor"] == 1
        assert "execution_lease" not in store.sim_runs.docs[0]

    asyncio.run(case())
