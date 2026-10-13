"""Acceptance-style proof across the living-community runtime boundaries.

These tests use an in-memory transactional fake.  They are not, and do not
claim to be, the still-required isolated direct-Mongo acceptance run.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from routes.actor_context import ActorContext
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import CommunityExecutorError, ExecutorEvent, execute_one
from simulation.community_provisioning import provision_burn_in_residents
from simulation.community_reconciliation import reconcile_run
from simulation.community_reset import CommunityResetError, reset_living_community
from tests.community_runtime_fake import RuntimeStore


NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)
RUN_ID = "simrun:runtime-acceptance"
HOLDER_ID = "executor:runtime-acceptance"
FENCE = 7


def operator():
    return ActorContext(
        actor_id="user:michael", actor_type="real-human",
        identity_basis="authenticated", channel="staff_ui",
        name="Michael", role="owner", simulated=False,
    )


def resident_document(recipe):
    return {
        **recipe.resident_payload(),
        "created_at": NOW.isoformat(),
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }


def receipt_writer(store):
    async def write(**fields):
        document = dict(fields)
        document.update(document.pop("provenance"))
        await store.receipts.insert_one(document)
        return document
    return write


def run_document(*, state="RUNNING", cursor=0):
    return {
        "run_id": RUN_ID,
        "state": state,
        "cursor": cursor,
        "sim_minute": 60,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "execution_lease_generation": FENCE,
        "execution_lease": {
            "holder_id": HOLDER_ID,
            "acquired_at": NOW.isoformat(),
            "heartbeat_at": NOW.isoformat(),
            "expires_at": (NOW + timedelta(minutes=5)).isoformat(),
        },
    }


def event(number):
    return ExecutorEvent(
        event_id=f"runtime-event-{number}", stream_kind="routine_dispatch",
        action_type=f"runtime_action_{number}", day_index=0, minute=10 * number,
        actor_id="sim:staff:care:01", actor_name="Synthetic Care Worker",
        actor_type="simulated-agent", identity_basis="synthetic",
        department="care", target_type="resident",
        target_id=BURN_IN_RESIDENTS[0].resident_id,
        adapter="canonical_staff_task_service",
    )


class CanonicalEvidenceServices:
    def __init__(self, store, *, crash_after_receipt=False, corrupt=None):
        self.store = store
        self.crash_after_receipt = crash_after_receipt
        self.corrupt = corrupt
        self.execution_calls = 0

    async def load_evidence(self, *, run_id, event_id, expected_cursor, execution_fence):
        return await self.store.receipts.find_one({
            "simulation_run_id": run_id,
            "simulation_event_id": event_id,
            "execution_cursor": expected_cursor,
            "execution_fence": execution_fence,
        })

    async def execute_event(self, *, event, context):
        self.execution_calls += 1
        document = {
            "receipt_id": f"rcpt:{context.run_id}:{event.event_id}",
            "simulation_event_id": event.event_id,
            "simulation_run_id": context.run_id,
            "simulation_scope": context.simulation_scope,
            "simulation_community_id": context.simulation_community_id,
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
        if self.corrupt:
            document[self.corrupt[0]] = self.corrupt[1]
        await self.store.receipts.insert_one(document)
        if self.crash_after_receipt:
            self.crash_after_receipt = False
            raise RuntimeError("injected crash after durable receipt")


async def provision(store):
    return await provision_burn_in_residents(
        operator(), "admin_override:owner", store=store,
        receipt_writer=receipt_writer(store), document_factory=resident_document,
        simulation_run_id=RUN_ID,
    )


def event_receipts(store):
    return [row for row in store.receipts.docs if row.get("simulation_event_id")]


def test_crash_retry_reconciles_once_then_atomic_reset_preserves_evidence_and_neighbors():
    async def scenario():
        store = RuntimeStore()
        store.residents.docs.extend([
            {"resident_id": "real:resident:1", "room": "101", "synthetic": False},
            {"resident_id": "demo:resident:1", "room": "DEMO-1", "synthetic": True,
             "simulation_scope": "public_demo"},
        ])
        store.sim_runs.docs.append({
            "run_id": "unrelated-run", "state": "RUNNING", "cursor": 3,
            "simulation_scope": "another_simulator",
        })
        result = await provision(store)
        assert len(result["created_ids"]) == 10
        store.sim_runs.docs.append(run_document())
        store.staff_tasks.docs.append({
            "task_id": "runtime-task", "resident_id": BURN_IN_RESIDENTS[0].resident_id,
            "simulated": True, "simulation_run_id": RUN_ID,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        })
        store.notifications.docs.append({
            "notification_id": "runtime-note", "status": "simulated", "simulated": True,
            "simulation_run_id": RUN_ID, "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        })
        events = (event(1), event(2))
        services = CanonicalEvidenceServices(store, crash_after_receipt=True)

        with pytest.raises(RuntimeError, match="crash after durable receipt"):
            await execute_one(
                RUN_ID, HOLDER_ID, FENCE, store=store, services=services,
                events=events, now=NOW, clock=lambda: NOW,
            )
        assert store.sim_runs.docs[-1]["cursor"] == 0
        assert services.execution_calls == 1
        assert len(event_receipts(store)) == 1

        recovery = reconcile_run(store.sim_runs.docs[-1], events, event_receipts(store))
        assert recovery["status"] == "ready"
        assert recovery["recovery_steps"][0]["action"] == "advance_cursor_from_receipt"

        replay = await execute_one(
            RUN_ID, HOLDER_ID, FENCE, store=store, services=services,
            events=events, now=NOW, clock=lambda: NOW,
        )
        assert replay.idempotent_replay is True
        assert replay.cursor_after == 1
        assert services.execution_calls == 1
        second = await execute_one(
            RUN_ID, HOLDER_ID, FENCE, store=store, services=services,
            events=events, now=NOW, clock=lambda: NOW,
        )
        assert second.idempotent_replay is False
        assert second.cursor_after == 2
        assert services.execution_calls == 2
        assert len(event_receipts(store)) == 2

        store.sim_runs.docs[-1]["state"] = "STOPPED"
        preserved_receipt_ids = {row.get("receipt_id") for row in store.receipts.docs}
        reset = await reset_living_community(
            operator(), "admin_override:owner", "runtime-acceptance-reset",
            store=store, now=NOW,
        )
        assert reset["deleted"] == {
            "notifications": 1, "staff_tasks": 1, "sim_runs": 1, "residents": 10,
        }
        assert preserved_receipt_ids <= {row.get("receipt_id") for row in store.receipts.docs}
        assert [row["resident_id"] for row in store.residents.docs] == [
            "real:resident:1", "demo:resident:1",
        ]
        assert [row["run_id"] for row in store.sim_runs.docs] == ["unrelated-run"]

    asyncio.run(scenario())


def test_cursor_refuses_missing_or_mismatched_durable_evidence():
    async def scenario():
        for corrupt in (("actor_id", "sim:staff:wrong"), None):
            store = RuntimeStore()
            store.sim_runs.docs.append(run_document())
            services = CanonicalEvidenceServices(store, corrupt=corrupt)
            if corrupt is None:
                async def no_receipt(**_kwargs):
                    services.execution_calls += 1
                services.execute_event = no_receipt
            with pytest.raises(CommunityExecutorError, match="evidence"):
                await execute_one(
                    RUN_ID, HOLDER_ID, FENCE, store=store, services=services,
                    events=(event(1),), now=NOW, clock=lambda: NOW,
                )
            assert store.sim_runs.docs[0]["cursor"] == 0

    asyncio.run(scenario())


def test_reset_failure_rolls_back_every_delete_and_reset_receipt():
    async def scenario():
        store = RuntimeStore(fail_delete="staff_tasks")
        await provision(store)
        store.sim_runs.docs.append(run_document(state="STOPPED"))
        store.staff_tasks.docs.append({
            "task_id": "rollback-task", "simulated": True,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        })
        before = deepcopy(store.snapshot())
        with pytest.raises(CommunityResetError, match="rolled back"):
            await reset_living_community(
                operator(), "admin_override:owner", "rollback-reset",
                store=store, now=NOW,
            )
        assert store.snapshot() == before

    asyncio.run(scenario())
