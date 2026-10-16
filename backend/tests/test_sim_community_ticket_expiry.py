"""CO-008: executing the expire phase and the called-in claim receipt.

Fake-store proofs of the executor adapter, plus one DB-direct proof that the
expire phase closes a real canonical StaffTask through ``task_actions.skip``
with a provenance receipt (scratch database only).
"""
import asyncio
import os
import uuid
from dataclasses import replace

import pytest

from simulation import community_ticket_staging as ticket
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_execution_adapter import (
    CanonicalCommunityExecutionServices, CommunityExecutionAdapterError, EXECUTOR_AUTHORITY,
)
from simulation.community_executor import ExecutorEvent
from simulation.community_service_windows import NOT_SERVED
from simulation.community_ticket_plan import CLAIM, EXPIRE, OPEN
from tests.test_sim_community_execution_adapter import (
    Store, completion, context, event, harness, task,
)

LEAD = "sim:staff:kitchen:dining_team_member:02"
BREAKDOWN = (("waiting_for_available_staff", 25),)


def _dinner(phase: str, **changes) -> ExecutorEvent:
    staff = phase != OPEN
    values = dict(
        event_id=f"day-002:resident-001:dinner:ticket_{phase}", stream_kind="routine_ticket_phase",
        action_type="dinner", day_index=2, minute=1170 if phase == EXPIRE else 1080,
        actor_id=LEAD, actor_name="SIM - Dining Team Member 02", actor_type="simulated-agent",
        identity_basis="synthetic", department="kitchen", target_type="resident",
        target_id="sim:resident:001", adapter="canonical_staff_task",
        workflow_event_id="day-002:resident-001:dinner", task_phase=phase, opened_by="staff",
        requested_at_minute=2 * 1440 + 1080,
        wait_reason=NOT_SERVED if staff else None, wait_breakdown=BREAKDOWN if staff else None,
    )
    values.update(changes)
    return ExecutorEvent(**values)


def _expiring_harness(store):
    services, calls = harness(store)
    calls["expire"] = []

    async def expire_task(**kwargs):
        calls["expire"].append(kwargs)
        stored = next(row for row in store.staff_tasks.rows if row["task_id"] == kwargs["task_id"])
        stored["status"] = "skipped"
        proof = completion(receipt_id="rcpt-task-skip", action_type="task_cancelled", status="cancelled",
                           actor_id=kwargs["actor"].actor_id)
        store.receipts.rows.append(dict(proof))
        return dict(stored), proof

    services.task_expirer = expire_task
    return services, calls


def test_expire_phase_closes_the_pending_ticket_unserved_with_a_receipt():
    async def case():
        item, ctx = _dinner(EXPIRE), context()
        store = Store(tasks=[task(item, ctx)])
        services, calls = _expiring_harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert store.staff_tasks.rows[0]["status"] == "skipped"
        assert len(calls["expire"]) == 1 and calls["start"] == calls["complete"] == []
        assert "Not served" in calls["expire"][0]["note"]
        assert calls["expire"][0]["actor"].department == "kitchen"
        assert proof["status"] == "completed" and proof["authority"] == EXECUTOR_AUTHORITY
        assert proof["parent_receipt_id"] == "rcpt-task-skip"
        assert proof["after_state"]["wait_reason"] == NOT_SERVED
        assert proof["after_state"]["wait_breakdown"] == dict(BREAKDOWN)
        assert proof["next_state"] == "executor_cursor_ready"
        assert "Not served" in proof["result"]
        # Replay after a crash finds the canonical skip receipt and does not skip twice.
        store.receipts.rows = [row for row in store.receipts.rows if row["receipt_id"] != proof["receipt_id"]]
        again = await services.execute_event(event=item, context=ctx)
        assert again["parent_receipt_id"] == "rcpt-task-skip" and len(calls["expire"]) == 1
    asyncio.run(case())


def test_expire_phase_refuses_a_ticket_someone_is_already_working():
    async def case():
        item, ctx = _dinner(EXPIRE), context()
        store = Store(tasks=[task(item, ctx, status="in_progress", assigned_to="sim:staff:kitchen:x")])
        services, calls = _expiring_harness(store)
        with pytest.raises(CommunityExecutionAdapterError, match="contradicts canonical task state"):
            await services.execute_event(event=item, context=ctx)
        assert calls["expire"] == [] and calls["write"] == []
    asyncio.run(case())


def test_called_in_claim_receipt_says_so_with_the_whole_wait():
    async def case():
        ctx, store = context(), Store()
        services, _calls = harness(store)
        opened = replace(event(task_phase=OPEN), requested_at_minute=470)
        await services.execute_event(event=opened, context=ctx)
        claim = replace(event(task_phase=CLAIM), requested_at_minute=470, called_in_on_call=True,
                        wait_reason="waiting_for_on_call_response", waited_minutes=40,
                        wait_breakdown=(("waiting_for_on_call_response", 40),))
        proof = await services.execute_event(event=claim, context=ctx)
        assert proof["after_state"]["called_in_on_call"] is True
        assert proof["after_state"]["wait_breakdown"] == {"waiting_for_on_call_response": 40}
        assert "called in from on-call" in proof["result"]
    asyncio.run(case())


# --- DB-direct: the real canonical lifecycle ---------------------------------

def test_expire_phase_skips_a_real_canonical_task_with_provenance():
    if os.environ.get("DB_NAME") in ("caoscare", "", None):
        pytest.skip("writes task records; point DB_NAME at a scratch database")
    from deps import db

    tag = f"co008x_{uuid.uuid4().hex[:8]}"
    resident_id = f"sim:resident:{tag}"
    ctx = context(run_id=f"simrun:{tag}")
    opened = _dinner(OPEN, target_id=resident_id)
    expire = _dinner(EXPIRE, target_id=resident_id)

    async def case():
        await db.residents.insert_one({
            "resident_id": resident_id, "name": f"SIM - {tag}", "room": f"SIM-{tag}", "synthetic": True,
            "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID})
        services = CanonicalCommunityExecutionServices(store=db)
        try:
            await services.execute_event(event=opened, context=ctx)
            proof = await services.execute_event(event=replace(expire), context=replace(ctx, cursor=4))
            stored = await db.staff_tasks.find_one({"simulation_run_id": ctx.run_id}, {"_id": 0})
            assert stored["status"] == "skipped" and stored["completed_by"] == LEAD
            assert "Not served" in stored["notes"]
            skip = await db.receipts.find_one(
                {"related_object_id": stored["task_id"], "action_type": "task_cancelled"}, {"_id": 0})
            assert skip["status"] == "cancelled" and skip["actor_id"] == LEAD
            assert skip["authority"] == "acts_for:kitchen"
            assert skip["simulation_run_id"] == ctx.run_id
            assert proof["parent_receipt_id"] == skip["receipt_id"]
            assert proof["after_state"]["status"] == "skipped"
        finally:
            task_ids = [row["task_id"] for row in await db.staff_tasks.find(
                {"simulation_run_id": ctx.run_id}, {"_id": 0, "task_id": 1}).to_list(None)]
            await db.receipts.delete_many({"$or": [{"simulation_run_id": ctx.run_id},
                                                   {"related_object_id": {"$in": task_ids}}]})
            await db.staff_tasks.delete_many({"simulation_run_id": ctx.run_id})
            await db.residents.delete_many({"resident_id": resident_id})
    asyncio.get_event_loop().run_until_complete(case())
