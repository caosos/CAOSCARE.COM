"""Atomic, exact-run proof for the ten-resident burn-in gate."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from routes.actor_context import ActorContext
from simulation import community_run_lifecycle as lifecycle
from simulation.community_atomic_provision import (
    CommunityAtomicProvisionError,
    READY_ACTION,
    provision_paused_burn_in_run,
)
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_provisioning import provision_burn_in_residents
from simulation.community_timeline import build_90_day_timeline
from tests.community_runtime_fake import RuntimeStore


NOW = datetime(2026, 10, 13, 19, 0, tzinfo=timezone.utc)
PLAN = build_90_day_timeline()
AUTHORITY = "admin_override:owner"
OWNER = ActorContext(
    actor_id="user:michael", actor_type="real-human",
    identity_basis="authenticated", channel="staff_ui",
    name="Michael", role="owner", simulated=False,
)


async def create_run(store, key="atomic-provision-run"):
    return await lifecycle.create_burn_in_run(
        OWNER, AUTHORITY, key, PLAN, store=store, now=NOW,
    )


async def provision(store, run_id, key="atomic-provision-1", **kwargs):
    return await provision_paused_burn_in_run(
        OWNER, AUTHORITY, run_id, 0, 0, key, PLAN,
        store=store, now=NOW, **kwargs,
    )


def test_exact_paused_run_commits_ten_residents_and_current_run_evidence_once():
    async def scenario():
        store = RuntimeStore()
        run_id = (await create_run(store))["run"]["run_id"]
        first = await provision(store, run_id)
        assert first["idempotent_replay"] is False
        assert len(first["created_ids"]) == 10
        assert first["reused_ids"] == []
        assert first["run"]["residents_provisioned"] is True
        assert first["receipt"]["action_type"] == READY_ACTION
        assert first["receipt"]["actor_id"] == OWNER.actor_id
        assert first["receipt"]["authority"] == AUTHORITY
        assert first["receipt"]["before_state"]["residents_provisioned"] is False
        assert first["receipt"]["after_state"]["residents_provisioned"] is True
        assert len(store.residents.docs) == 10
        resident_receipts = [
            row for row in store.receipts.docs
            if row.get("related_object_type") == "resident"
            and row.get("simulation_run_id") == run_id
        ]
        assert len(resident_receipts) == 10
        assert all(row["parent_receipt_id"] == first["run"]["origin_receipt_id"]
                   for row in resident_receipts)
        assert all(row["correlation_id"] == first["run"]["origin_receipt_id"]
                   for row in resident_receipts)
        before = deepcopy(store.snapshot())
        replay = await provision(store, run_id)
        assert replay["idempotent_replay"] is True
        assert replay["receipt"]["receipt_id"] == first["receipt"]["receipt_id"]
        assert store.snapshot() == before

        other_owner = ActorContext(
            actor_id="user:other-owner", actor_type="real-human",
            identity_basis="authenticated", channel="staff_ui",
            name="Other Owner", role="owner", simulated=False,
        )
        with pytest.raises(CommunityAtomicProvisionError, match="conflicts"):
            await provision_paused_burn_in_run(
                other_owner, AUTHORITY, run_id, 0, 0, "atomic-provision-1", PLAN,
                store=store, now=NOW,
            )
        assert store.snapshot() == before

    asyncio.run(scenario())


def test_prior_run_residents_get_new_reconcile_receipts_for_current_run():
    async def scenario():
        store = RuntimeStore()

        async def old_writer(**fields):
            document = dict(fields)
            document.update(document.pop("provenance"))
            await store.receipts.insert_one(document)
            return document

        await provision_burn_in_residents(
            OWNER, AUTHORITY, store=store, receipt_writer=old_writer,
            simulation_run_id="simrun:old-generation", now=NOW,
        )
        old_ids = {row["receipt_id"] for row in store.receipts.docs}
        run_id = (await create_run(store))["run"]["run_id"]
        result = await provision(store, run_id)
        assert result["created_ids"] == []
        assert result["reused_ids"] == [row.resident_id for row in BURN_IN_RESIDENTS]
        current = [
            row for row in store.receipts.docs
            if row.get("related_object_type") == "resident"
            and row.get("simulation_run_id") == run_id
        ]
        assert len(current) == 10
        assert all(row["action_type"] == "simulation_resident_reconciled" for row in current)
        assert old_ids.isdisjoint({row["receipt_id"] for row in current})

    asyncio.run(scenario())


def test_receipt_failure_rolls_back_residents_receipts_and_run_readiness():
    async def scenario():
        store = RuntimeStore()
        run_id = (await create_run(store))["run"]["run_id"]
        before = deepcopy(store.snapshot())
        original_insert = store.receipts.insert_one
        current_run_writes = 0

        async def fail_midway(document, session=None):
            nonlocal current_run_writes
            if document.get("related_object_type") == "resident":
                current_run_writes += 1
                if current_run_writes == 4:
                    raise RuntimeError("injected resident receipt failure")
            return await original_insert(document, session=session)

        store.receipts.insert_one = fail_midway
        with pytest.raises(RuntimeError, match="injected resident receipt failure"):
            await provision(store, run_id)
        assert store.snapshot() == before

    asyncio.run(scenario())


@pytest.mark.parametrize("bad_state,leased", [("RUNNING", False), ("PAUSED", True)])
def test_wrong_state_or_lease_refuses_before_any_resident_write(bad_state, leased):
    async def scenario():
        store = RuntimeStore()
        run_id = (await create_run(store))["run"]["run_id"]
        store.sim_runs.docs[0]["state"] = bad_state
        if leased:
            store.sim_runs.docs[0]["execution_lease"] = {"holder_id": "runner"}
        before = deepcopy(store.snapshot())
        with pytest.raises(CommunityAtomicProvisionError, match="PAUSED|unleased"):
            await provision(store, run_id)
        assert store.snapshot() == before

    asyncio.run(scenario())


def test_wrong_actor_and_identity_collision_fail_closed():
    async def scenario():
        simulated = ActorContext(
            actor_id="sim:admin", actor_type="simulated-agent",
            identity_basis="synthetic", channel="simulator",
            role="owner", simulated=True,
        )
        store = RuntimeStore()
        run_id = (await create_run(store))["run"]["run_id"]
        before = deepcopy(store.snapshot())
        with pytest.raises(CommunityAtomicProvisionError, match="authenticated"):
            await provision_paused_burn_in_run(
                simulated, AUTHORITY, run_id, 0, 0, "bad-actor", PLAN,
                store=store, now=NOW,
            )
        assert store.snapshot() == before

        recipe = BURN_IN_RESIDENTS[3]
        store.residents.docs.append({
            "resident_id": "real:resident", "room": recipe.room,
            "pendant_id": "real:pendant", "synthetic": False,
        })
        before = deepcopy(store.snapshot())
        with pytest.raises(CommunityAtomicProvisionError, match="collision"):
            await provision(store, run_id)
        assert store.snapshot() == before

    asyncio.run(scenario())


def test_wrong_plan_cursor_clock_and_different_replay_key_are_refused():
    async def scenario():
        for cursor, minute in ((1, 0), (0, 1)):
            store = RuntimeStore()
            run_id = (await create_run(store))["run"]["run_id"]
            with pytest.raises(CommunityAtomicProvisionError, match="stale"):
                await provision_paused_burn_in_run(
                    OWNER, AUTHORITY, run_id, cursor, minute, "stale", PLAN,
                    store=store, now=NOW,
                )
            assert store.residents.docs == []

        store = RuntimeStore()
        run_id = (await create_run(store))["run"]["run_id"]
        bad_plan = replace(PLAN, digest_sha256="0" * 64)
        with pytest.raises(CommunityAtomicProvisionError, match="timeline"):
            await provision_paused_burn_in_run(
                OWNER, AUTHORITY, run_id, 0, 0, "bad-plan", bad_plan,
                store=store, now=NOW,
            )
        await provision(store, run_id)
        with pytest.raises(CommunityAtomicProvisionError, match="conflicts"):
            await provision(store, run_id, key="different-key")

    asyncio.run(scenario())


def test_missing_transaction_support_is_rejected():
    class StoreWithoutClient:
        pass

    with pytest.raises(CommunityAtomicProvisionError, match="transaction-capable"):
        asyncio.run(provision_paused_burn_in_run(
            OWNER, AUTHORITY, "run", 0, 0, "key", PLAN,
            store=StoreWithoutClient(), now=NOW,
        ))
