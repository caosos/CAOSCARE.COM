"""Truth and provenance helpers for staged canonical community tickets."""

from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN


class CommunityTicketStageError(RuntimeError):
    """A task or receipt cannot prove the expected simulated ticket phase."""


def event_session(event: ExecutorEvent) -> str:
    return f"simulator:event:{event.workflow_event_id or event.event_id}"


def default_store():
    from deps import db

    return db


async def create_request(*, event: ExecutorEvent, context: ExecutionContext,
                         summary: str, priority: str) -> dict:
    if event.department == "front_desk":
        from simulation.community_front_desk_ticket import create_front_desk_request

        return await create_front_desk_request(
            event=event, context=context, summary=summary, priority=priority,
        )
    from routes.resident_requests import ResidentRequestInput, create_resident_request

    return await create_resident_request(
        ResidentRequestInput(
            category=event.department,
            resident_id=event.target_id,
            resident_words=None,
            summary=summary,
            priority=priority,
            source="aria_voice",
            conversation_session_id=event_session(event),
        ),
        simulation_run_id=context.run_id,
    )


async def load_task(task_id: str) -> dict:
    from routes.task_lifecycle import load

    return await load(task_id)


async def start_task(*, task_id: str, actor: ActorContext, user: dict):
    from routes.task_actions import start

    return await start(task_id, actor, user)


async def complete_task(*, task_id: str, note: str, actor: ActorContext, user: dict):
    from routes.task_actions import complete

    return await complete(task_id, note, actor, user)


async def write_receipt(**kwargs) -> dict:
    from routes.receipts import create_receipt

    return await create_receipt(**kwargs)


def summary(event: ExecutorEvent) -> str:
    return f"Scheduled simulated {event.action_type.replace('_', ' ')}."


def priority(event: ExecutorEvent) -> str:
    urgent = ("medication_reminder", "toileting", "transfer", "shower")
    return "high" if any(word in event.action_type for word in urgent) else "normal"


def completion_note(event: ExecutorEvent) -> str:
    action = event.action_type
    if action == "front_desk_message_follow_up":
        return (
            "Simulated Front Desk message coordination documented and queued for follow-up; "
            "no resident contact or outbound call is claimed."
        )
    if "medication_reminder" in action:
        return ("Simulated medication reminder delivered; no claim of administration, "
                "ingestion, dose completion, or adherence.")
    if action in {"breakfast", "lunch", "dinner"}:
        return "Simulated meal service offered; no claim that the resident ate or how much."
    if action == "transport_coordination":
        return ("Simulated transportation coordination completed; no driver, vehicle, "
                "pickup, or booking claimed.")
    if action == "family_call_coordination":
        return "Simulated family-call coordination completed; no call was placed or connected."
    if action == "activity_offer_and_escort":
        return ("Simulated activity offer and escort task completed; no schedule was "
                "published and attendance is not inferred.")
    return f"Simulated {action.replace('_', ' ')} task completed through the canonical lifecycle."


def actor(event: ExecutorEvent) -> ActorContext:
    resident_origin = event.task_phase == OPEN
    return ActorContext(
        actor_id=event.actor_id,
        actor_type=event.actor_type,
        identity_basis=event.identity_basis,
        channel="simulator",
        name=event.actor_name,
        role="resident" if resident_origin else "staff",
        department=None if resident_origin else event.department,
        simulated=True,
    )


def staff_user(event: ExecutorEvent) -> dict:
    return {
        "user_id": event.actor_id,
        "name": event.actor_name,
        "role": "staff",
        "department": event.department,
        "simulated": True,
    }


def validate_task(task: dict, event: ExecutorEvent, context: ExecutionContext) -> None:
    expected = {
        "resident_id": event.target_id,
        "category": event.department,
        "visibility_role": event.department,
        "conversation_session_id": event_session(event),
        "simulation_run_id": context.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulated": True,
    }
    if any(task.get(key) != value for key, value in expected.items()):
        raise CommunityTicketStageError("canonical task does not match the fenced event")


def validate_task_receipt(
    receipt: dict,
    task: dict,
    event: ExecutorEvent,
    context: ExecutionContext,
    *,
    action_type: str,
    status: str,
    staff_actor: bool,
) -> None:
    expected = {
        "related_object_type": "task",
        "related_object_id": task["task_id"],
        "action_type": action_type,
        "simulation_run_id": context.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "status": status,
    }
    if staff_actor:
        expected.update({
            "actor_id": event.actor_id,
            "actor_type": "simulated-agent",
            "identity_basis": "synthetic",
            "simulated": True,
        })
    else:
        expected.update({
            "actor_id": event.target_id,
            "actor_type": "simulated-agent",
            "identity_basis": "synthetic",
            "channel": "simulator",
            "simulated": True,
        })
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise CommunityTicketStageError(
            f"canonical {action_type} receipt does not prove this event task phase"
        )


def phase_result(event: ExecutorEvent) -> str:
    if event.task_phase == OPEN:
        return f"Simulated {event.action_type.replace('_', ' ')} ticket opened in the canonical queue."
    if event.task_phase == CLAIM:
        return f"{event.actor_name} claimed and started the simulated canonical ticket."
    return completion_note(event)


def next_phase(phase: str) -> str:
    return {
        OPEN: "awaiting_simulated_worker",
        CLAIM: "awaiting_simulated_completion",
        COMPLETE: "executor_cursor_ready",
    }[phase]
