"""One canonical lifecycle transition per simulated ticket phase.

Given the canonical task's current state, perform (or, on replay, find) the
one StaffTask transition a phase stands for and return its canonical receipt:

* open     - the origin receipt the request service already wrote;
* claim    - ``task_actions.start`` (pending -> in_progress);
* complete - ``task_actions.complete`` (in_progress -> completed);
* expire   - ``task_actions.skip`` (pending -> skipped): a time-bound ticket
  whose service window closed is closed unserved by the department lead.

Any other combination contradicts the plan and is refused.
"""
from pymongo.errors import DuplicateKeyError

from simulation import community_ticket_staging as ticket
from simulation.community_ticket_plan import CLAIM, COMPLETE, EXPIRE, OPEN

# phase -> (state it acts on, canonical action, receipt status, before status)
_TRANSITIONS = {
    CLAIM: ("pending", "task_in_progress", "in_progress", "pending"),
    COMPLETE: ("in_progress", "task_completed", "completed", "in_progress"),
    EXPIRE: ("pending", "task_cancelled", "cancelled", "pending"),
}
# phase -> state the task is in once the transition already happened (replay)
_DONE = {CLAIM: "in_progress", COMPLETE: "completed", EXPIRE: "skipped"}


class TicketPhaseError(RuntimeError):
    """The phase contradicts the canonical task state."""


async def transition(services, event, context, task: dict, actor, user, origin_action: str):
    """(task, canonical receipt, action type, receipt status, before status)."""
    state, phase = task.get("status"), event.task_phase
    if phase == OPEN:
        if state != "pending":
            raise TicketPhaseError("open phase task is not pending")
        receipt = await services._task_receipt(task["task_id"], event, context, origin_action)
        return task, receipt, origin_action, "created", None
    if phase not in _TRANSITIONS:
        raise TicketPhaseError(f"unknown ticket phase {phase}")
    acts_on, action_type, status, before = _TRANSITIONS[phase]
    if state == _DONE[phase]:
        receipt = await services._task_receipt(task["task_id"], event, context, action_type)
        return task, receipt, action_type, status, before
    if state != acts_on:
        raise TicketPhaseError(f"ticket {phase} phase contradicts canonical task state {state}")
    if phase == CLAIM:
        await services._refuse_second_active_ticket(task, event, context)
        try:
            task, receipt = await services.task_starter(task_id=task["task_id"], actor=actor, user=user)
        except DuplicateKeyError as exc:
            raise TicketPhaseError(
                f"database refused a second active ticket for {event.actor_id}") from exc
    elif phase == COMPLETE:
        task, receipt = await services.task_completer(
            task_id=task["task_id"], note=ticket.completion_note(event), actor=actor, user=user)
    else:
        task, receipt = await services.task_expirer(
            task_id=task["task_id"], note=ticket.expiry_note(event), actor=actor, user=user)
    return task, receipt, action_type, status, before
