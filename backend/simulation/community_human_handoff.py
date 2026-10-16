"""Real staff working inside the simulated community.

Owner/admin Work-as (or a real department account) works the same canonical
tickets the simulated community opened.  A simulated worker's planned phase
yields when a real person has taken that ticket over, when a real person is
covering that worker's shift, or when the ticket's claim was already given
up and it still waits.  Each yielded phase is a ``cancelled`` (refused)
executor receipt naming what it yields to, so the run advances with a
receipt for every event and never overwrites the person's work.
"""
from typing import Optional

from simulation.community_shift_cover import active_cover, cover_result

# Notes and repeat asks do not take a ticket over; state changes do.
_NOT_A_TAKEOVER = ("task_note_added", "resident_request_created", "resident_request_re_requested")


async def real_staff_takeover(store, task: dict, run_id: str) -> Optional[dict]:
    """The latest real-human transition receipt on this run's ticket, if any."""
    return await store.receipts.find_one({
        "related_object_type": "task",
        "related_object_id": task["task_id"],
        "simulation_run_id": run_id,
        "actor_type": "real-human",
        "action_type": {"$nin": list(_NOT_A_TAKEOVER)},
    }, {"_id": 0}, sort=[("created_at", -1), ("receipt_id", -1)])


def handoff_result(event, takeover: dict) -> str:
    who = takeover.get("actor_name") or takeover.get("actor_id") or "a real staff member"
    return (f"{event.actor_name} did not {event.task_phase} this ticket: {who} is working it "
            f"({takeover.get('action_type')}).")


async def _yielded_claim(store, event, run_id: str) -> Optional[dict]:
    """This ticket's planned claim, if it was given up to real staff."""
    return await store.receipts.find_one({
        "simulation_run_id": run_id,
        "simulation_event_id": f"{event.workflow_event_id}:ticket_claim",
        "authority": "living_community_executor",
        "status": "cancelled",
    }, {"_id": 0})


async def yielded_to_real_staff(store, event, run_id: str, task: dict):
    """(parent receipt, result, next state) when this simulated phase must not act.

    * a real person has taken the ticket over;
    * the worker's shift is covered by a real person;
    * the ticket's planned claim was given up and nobody has claimed it yet.
    """
    takeover = await real_staff_takeover(store, task, run_id)
    if takeover:
        return takeover, handoff_result(event, takeover), "handled_by_real_staff"
    cover = await active_cover(store, run_id, event.actor_id)
    if cover:
        parent = {"receipt_id": cover["start_receipt_id"], "correlation_id": cover["start_receipt_id"]}
        return parent, cover_result(event, cover), "left_for_covering_staff"
    if event.task_phase == "complete" and task.get("status") == "pending":
        claim = await _yielded_claim(store, event, run_id)
        if claim:
            return (claim, f"{event.actor_name} never claimed this ticket; it is still waiting in the queue.",
                    "left_in_queue")
    return None
