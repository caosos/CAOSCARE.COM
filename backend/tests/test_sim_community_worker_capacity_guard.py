"""SIM-006: one active ticket per worker is enforced against persisted state."""
import asyncio
from dataclasses import replace

import pytest
from pymongo.errors import DuplicateKeyError

from simulation.community_execution_adapter import CommunityExecutionAdapterError
from simulation.community_ticket_plan import CLAIM, OPEN
from tests.test_sim_community_execution_adapter import Store, context, event, harness, task


def _claim(**changes):
    return replace(event(task_phase=CLAIM), requested_at_minute=470,
                   wait_reason="waiting_for_available_staff", waited_minutes=12, **changes)


def test_claim_receipt_records_request_time_and_actual_wait():
    async def case():
        ctx, store = context(), Store()
        services, _calls = harness(store)
        await services.execute_event(event=replace(event(task_phase=OPEN), requested_at_minute=470),
                                     context=ctx)
        proof = await services.execute_event(event=_claim(), context=ctx)
        assert proof["after_state"]["requested_at_minute"] == 470
        assert proof["after_state"]["wait_reason"] == "waiting_for_available_staff"
        assert proof["after_state"]["waited_minutes"] == 12
    asyncio.run(case())


def test_worker_holding_an_active_ticket_cannot_claim_another():
    async def case():
        item, ctx = _claim(), context()
        held = task(item, ctx, task_id="task-held", status="in_progress",
                    assigned_to=item.actor_id, conversation_session_id="other-session")
        store = Store(tasks=[task(item, ctx), held])
        services, calls = harness(store)
        with pytest.raises(CommunityExecutionAdapterError, match="already holds active ticket task-held"):
            await services.execute_event(event=item, context=ctx)
        assert calls["start"] == [] and calls["write"] == []
        assert store.staff_tasks.rows[0]["status"] == "pending"
    asyncio.run(case())


def test_a_ticket_held_in_another_run_does_not_block_this_run():
    async def case():
        item, ctx = _claim(), context()
        other_run = task(item, ctx, task_id="task-other-run", status="in_progress",
                         assigned_to=item.actor_id, simulation_run_id="run-0")
        store = Store(tasks=[task(item, ctx), other_run])
        services, calls = harness(store)
        await services.execute_event(event=item, context=ctx)
        assert len(calls["start"]) == 1
    asyncio.run(case())


def test_database_unique_refusal_fails_closed_without_a_phase_receipt():
    async def case():
        item, ctx = _claim(), context()
        store = Store(tasks=[task(item, ctx)])
        services, calls = harness(store)

        async def refused(**_kwargs):
            raise DuplicateKeyError("E11000 living_tasks_one_active_per_worker")
        services.task_starter = refused
        with pytest.raises(CommunityExecutionAdapterError, match="database refused a second active ticket"):
            await services.execute_event(event=item, context=ctx)
        assert calls["write"] == []
    asyncio.run(case())
