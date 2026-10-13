"""Canonical, provider-fenced origin for simulated Front Desk work."""

from collections.abc import Awaitable, Callable
from typing import Optional

from models import StaffTask
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_ticket_plan import OPEN


class FrontDeskTicketError(RuntimeError):
    """The Front Desk task cannot be created with exact simulator provenance."""


def _default_store():
    from deps import db

    return db


async def _default_origin(task: dict, actor: ActorContext) -> dict:
    from routes.task_lifecycle import record_origin

    return await record_origin(
        task, actor, action_type="resident_request_created",
        authority="simulation_run",
    )


OriginRecorder = Callable[[dict, ActorContext], Awaitable[dict]]


def _actor(event: ExecutorEvent) -> ActorContext:
    return ActorContext(
        actor_id=event.target_id,
        actor_type="simulated-agent",
        identity_basis="synthetic",
        channel="simulator",
        name=event.actor_name,
        role="resident",
        simulated=True,
    )


async def create_front_desk_request(
    *,
    event: ExecutorEvent,
    context: ExecutionContext,
    summary: str,
    priority: str,
    store=None,
    origin_recorder: Optional[OriginRecorder] = None,
) -> dict:
    """Create one Front Desk StaffTask; never invoke a notification or call provider."""
    if (
        event.department != "front_desk"
        or event.task_phase != OPEN
        or event.actor_id != event.target_id
        or context.simulation_scope != SIMULATION_SCOPE
        or context.simulation_community_id != COMMUNITY_ID
        or context.providers_allowed
    ):
        raise FrontDeskTicketError("invalid Front Desk simulator request context")
    source = store if store is not None else _default_store()
    resident = await source.residents.find_one({
        "resident_id": event.target_id,
        "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }, {"_id": 0, "name": 1, "room": 1})
    if not resident:
        raise FrontDeskTicketError("Front Desk work requires an exact synthetic resident")

    task = StaffTask(
        title=summary[:120],
        description=summary,
        category="front_desk",
        priority=priority,
        source="simulator",
        visibility_role="front_desk",
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
    await source.staff_tasks.insert_one(task)
    recorder = origin_recorder or _default_origin
    receipt = await recorder(task, _actor(event))
    if not receipt or not receipt.get("receipt_id"):
        raise FrontDeskTicketError("Front Desk task origin produced no durable receipt")
    return {
        "task_id": task["task_id"],
        "receipt_id": receipt["receipt_id"],
        "status": task["status"],
    }
