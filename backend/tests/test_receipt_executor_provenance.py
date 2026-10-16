"""Receipt model keeps exact fenced simulator-event provenance."""

from models import Receipt


def test_receipt_retains_executor_event_cursor_and_fence():
    receipt = Receipt(
        action_type="simulation_routine_completed",
        simulation_run_id="simrun:community:1",
        simulation_event_id="routine:day-0:event-1",
        execution_cursor=17,
        execution_fence=3,
    )

    stored = receipt.model_dump()

    assert stored["simulation_event_id"] == "routine:day-0:event-1"
    assert stored["execution_cursor"] == 17
    assert stored["execution_fence"] == 3


def test_old_receipts_remain_readable_without_executor_provenance():
    stored = Receipt(action_type="legacy_task_created").model_dump()

    assert stored["simulation_event_id"] is None
    assert stored["execution_cursor"] is None
    assert stored["execution_fence"] is None


def test_receipt_retains_real_principal_and_signed_work_context_separately():
    stored = Receipt(
        action_type="task_completed",
        actor_id="owner-1",
        actor_role="owner",
        acting_role="staff",
        acting_department="maintenance",
        work_context_id="wctx-1",
    ).model_dump()

    assert stored["actor_id"] == "owner-1"
    assert stored["actor_role"] == "owner"
    assert stored["acting_role"] == "staff"
    assert stored["acting_department"] == "maintenance"
    assert stored["work_context_id"] == "wctx-1"
