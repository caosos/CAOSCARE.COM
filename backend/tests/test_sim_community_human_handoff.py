"""A real person working a simulated ticket takes it over; the run keeps going."""
import asyncio

from simulation.community_ticket_plan import CLAIM, COMPLETE
from tests.test_sim_community_execution_adapter import Store, context, event, harness, task


def _human(action_type, task_id="task-1", **changes):
    return {"receipt_id": f"rcpt-human-{action_type}", "related_object_type": "task",
            "related_object_id": task_id, "action_type": action_type, "simulation_run_id": "run-1",
            "actor_type": "real-human", "actor_id": "user_michael", "actor_name": "Michael",
            "correlation_id": "rcpt-origin", "created_at": "2026-10-14T17:00:00+00:00", **changes}


def test_planned_claim_yields_to_real_staff_with_a_refused_receipt():
    async def case():
        item, ctx = event(task_phase=CLAIM), context()
        store = Store(tasks=[task(item, ctx, status="in_progress", assigned_to="user_michael")],
                      receipts=[_human("task_in_progress")])
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert proof["status"] == "cancelled" and calls["start"] == []
        assert proof["parent_receipt_id"] == "rcpt-human-task_in_progress"
        assert proof["next_state"] == "handled_by_real_staff"
        assert "Michael is working it" in proof["result"]
        assert store.staff_tasks.rows[0]["assigned_to"] == "user_michael"
    asyncio.run(case())


def test_planned_completion_never_closes_real_staff_work():
    async def case():
        item, ctx = event(task_phase=COMPLETE), context()
        store = Store(tasks=[task(item, ctx, status="in_progress", assigned_to="user_michael")],
                      receipts=[_human("task_in_progress")])
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert proof["status"] == "cancelled" and calls["complete"] == []
        assert store.staff_tasks.rows[0]["status"] == "in_progress"
    asyncio.run(case())


def test_a_real_note_does_not_take_the_ticket_over():
    async def case():
        item, ctx = event(task_phase=CLAIM), context()
        store = Store(tasks=[task(item, ctx)], receipts=[_human("task_note_added")])
        services, calls = harness(store)
        proof = await services.execute_event(event=item, context=ctx)
        assert proof["status"] == "completed" and len(calls["start"]) == 1
    asyncio.run(case())
