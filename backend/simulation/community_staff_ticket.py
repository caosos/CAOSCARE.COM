"""Canonical origin for simulated work a staff member raises.

Rounds (room checks, meal service, reminders), preventive maintenance and
problems staff notice are opened by the on-site worker named on the event
(:func:`simulation.community_day_queue.opener`), never by the resident and
never by "the system". Same StaffTask shape and origin receipt as the Front
Desk path (:mod:`community_front_desk_ticket`), with the worker as actor and
``source="staff"``. No notification or provider is called.
"""
from typing import Optional

from models import StaffTask
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_ticket_plan import OPEN


class StaffTicketError(RuntimeError):
    """The staff-raised task cannot be created with exact simulator provenance."""


def _default_store():
    from deps import db

    return db


def staff_actor(event: ExecutorEvent) -> ActorContext:
    department = event.actor_id.split(":")[2] if event.actor_id.count(":") >= 3 else None
    return ActorContext(
        actor_id=event.actor_id,
        actor_type="simulated-agent",
        identity_basis="synthetic",
        channel="simulator",
        name=event.actor_name,
        role="staff",
        department=department,
        simulated=True,
    )


async def _default_origin(task: dict, actor: ActorContext) -> dict:
    from routes.task_lifecycle import record_origin

    return await record_origin(task, actor, action_type="task_created", authority="simulation_run")


async def create_staff_task(*, event: ExecutorEvent, context: ExecutionContext, summary: str,
                            priority: str, store=None, origin_recorder=None) -> dict:
    """Create one StaffTask raised by an on-site simulated worker."""
    if (event.opened_by != "staff" or event.task_phase != OPEN
            or not event.actor_id.startswith("sim:staff:")
            or context.simulation_scope != SIMULATION_SCOPE
            or context.simulation_community_id != COMMUNITY_ID
            or context.providers_allowed):
        raise StaffTicketError("invalid staff-raised simulator request context")
    source = store if store is not None else _default_store()
    resident = await source.residents.find_one({
        "resident_id": event.target_id, "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
    }, {"_id": 0, "name": 1, "room": 1})
    if not resident:
        raise StaffTicketError("staff-raised work requires an exact synthetic resident apartment")
    task = StaffTask(
        title=summary[:120],
        description=summary,
        category=event.department,
        priority=priority,
        source="staff",
        visibility_role=event.department,
        resident_id=event.target_id,
        resident_name=resident.get("name"),
        room=resident.get("room"),
        conversation_session_id=f"simulator:event:{event.workflow_event_id}",
        simulated=True,
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        simulation_run_id=context.run_id,
    ).model_dump()
    task["created_at"] = task["created_at"].isoformat()
    task["created_by"] = event.actor_id
    task["created_by_name"] = event.actor_name
    await source.staff_tasks.insert_one(task)
    receipt = await (origin_recorder or _default_origin)(task, staff_actor(event))
    if not receipt or not receipt.get("receipt_id"):
        raise StaffTicketError("staff-raised task origin produced no durable receipt")
    return {"task_id": task["task_id"], "receipt_id": receipt["receipt_id"], "status": task["status"]}
