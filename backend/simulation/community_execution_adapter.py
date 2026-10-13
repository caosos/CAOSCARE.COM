"""Provider-fenced canonical services for one community executor event."""

from collections.abc import Awaitable, Callable
from typing import Optional

from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_shift_execution import is_shift_event, record_shift_milestone, validate_shift_event


EXECUTOR_AUTHORITY = "living_community_executor"
EVENT_SESSION_PREFIX = "simulator:event:"
SUPPORTED_ADAPTER = "canonical_staff_task"


class CommunityExecutionAdapterError(RuntimeError):
    """The event was refused before any completion claim."""


def _default_store():
    from deps import db

    return db


async def _default_request_creator(*, event: ExecutorEvent, context: ExecutionContext,
                                   summary: str, priority: str) -> dict:
    from routes.resident_requests import ResidentRequestInput, create_resident_request

    return await create_resident_request(
        ResidentRequestInput(
            category=event.department,
            resident_id=event.target_id,
            resident_words=None,
            summary=summary,
            priority=priority,
            source="aria_voice",
            conversation_session_id=_event_session(event),
        ),
        simulation_run_id=context.run_id,
    )


async def _default_task_loader(task_id: str) -> dict:
    from routes.task_lifecycle import load

    return await load(task_id)


async def _default_task_completer(*, task_id: str, note: str,
                                  actor: ActorContext, user: dict):
    from routes.task_actions import complete

    return await complete(task_id, note, actor, user)


async def _default_receipt_writer(**kwargs) -> dict:
    from routes.receipts import create_receipt

    return await create_receipt(**kwargs)


def _event_session(event: ExecutorEvent) -> str:
    return f"{EVENT_SESSION_PREFIX}{event.event_id}"


def _summary(event: ExecutorEvent) -> str:
    label = event.action_type.replace("_", " ")
    return f"Scheduled simulated {label}."


def _priority(event: ExecutorEvent) -> str:
    urgent_routines = ("medication_reminder", "toileting", "transfer", "shower")
    return "high" if any(word in event.action_type for word in urgent_routines) else "normal"


def _completion_note(event: ExecutorEvent) -> str:
    action = event.action_type
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


def _actor(event: ExecutorEvent) -> ActorContext:
    return ActorContext(
        actor_id=event.actor_id,
        actor_type=event.actor_type,
        identity_basis=event.identity_basis,
        channel="simulator",
        name=event.actor_name,
        role="staff",
        department=event.department,
        simulated=True,
    )


def _staff_user(event: ExecutorEvent) -> dict:
    return {"user_id": event.actor_id, "name": event.actor_name, "role": "staff", "department": event.department, "simulated": True}


def _validate(event: ExecutorEvent, context: ExecutionContext) -> None:
    if context.providers_allowed:
        raise CommunityExecutionAdapterError("community execution never permits provider calls")
    if (context.simulation_scope != SIMULATION_SCOPE
            or context.simulation_community_id != COMMUNITY_ID):
        raise CommunityExecutionAdapterError("execution context is outside the living community")
    if (event.actor_type != "simulated-agent" or event.identity_basis != "synthetic"
            or not event.simulated or not event.actor_id.startswith("sim:staff:")):
        raise CommunityExecutionAdapterError("event lacks explicit synthetic staff provenance")
    if is_shift_event(event):
        validate_shift_event(event)
        return
    if (event.stream_kind != "routine_dispatch" or event.adapter != SUPPORTED_ADAPTER
            or event.target_type != "resident"):
        raise CommunityExecutionAdapterError(
            f"unsupported community executor event: {event.stream_kind}/{event.adapter}"
        )


def _validate_task(task: dict, event: ExecutorEvent, context: ExecutionContext) -> None:
    expected = {
        "resident_id": event.target_id,
        "category": event.department,
        "conversation_session_id": _event_session(event),
        "simulation_run_id": context.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulated": True,
    }
    if any(task.get(key) != value for key, value in expected.items()):
        raise CommunityExecutionAdapterError("canonical task does not match the fenced event")


RequestCreator = ReceiptWriter = Callable[..., Awaitable[dict]]
TaskLoader = Callable[[str], Awaitable[dict]]
TaskCompleter = Callable[..., Awaitable[tuple[dict, Optional[dict]]]]


class CanonicalCommunityExecutionServices:
    def __init__(self, *, store=None, request_creator: Optional[RequestCreator] = None,
                 task_loader: Optional[TaskLoader] = None,
                 task_completer: Optional[TaskCompleter] = None,
                 receipt_writer: Optional[ReceiptWriter] = None):
        self.store = store if store is not None else _default_store()
        self.request_creator = request_creator or _default_request_creator
        self.task_loader = task_loader or _default_task_loader
        self.task_completer = task_completer or _default_task_completer
        self.receipt_writer = receipt_writer or _default_receipt_writer

    async def load_evidence(self, *, run_id: str, event_id: str,
                            expected_cursor: int, execution_fence: int) -> Optional[dict]:
        """Load only the receipt for this exact fenced cursor coordinate."""
        return await self.store.receipts.find_one({
            "simulation_run_id": run_id,
            "simulation_event_id": event_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "execution_cursor": expected_cursor,
            "execution_fence": execution_fence,
            "authority": EXECUTOR_AUTHORITY,
        }, {"_id": 0})

    async def _event_task(self, event: ExecutorEvent, context: ExecutionContext) -> Optional[dict]:
        return await self.store.staff_tasks.find_one({
            "conversation_session_id": _event_session(event),
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "resident_id": event.target_id,
            "category": event.department,
            "simulated": True,
        }, {"_id": 0})

    async def _completion_receipt(self, task_id: str, event: ExecutorEvent,
                                  context: ExecutionContext) -> Optional[dict]:
        return await self.store.receipts.find_one({
            "related_object_type": "task",
            "related_object_id": task_id,
            "action_type": "task_completed",
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "actor_id": event.actor_id,
            "actor_type": "simulated-agent",
            "identity_basis": "synthetic",
            "simulated": True,
        }, {"_id": 0}, sort=[("created_at", -1)])

    @staticmethod
    def _validate_completion(receipt: dict, task: dict, event: ExecutorEvent,
                             context: ExecutionContext) -> None:
        expected = {
            "related_object_type": "task",
            "related_object_id": task["task_id"],
            "action_type": "task_completed",
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "actor_id": event.actor_id,
            "actor_type": "simulated-agent",
            "identity_basis": "synthetic",
            "simulated": True,
            "status": "completed",
        }
        if task.get("status") != "completed" or any(
            receipt.get(key) != value for key, value in expected.items()
        ):
            raise CommunityExecutionAdapterError(
                "canonical completion does not prove this event task completed"
            )

    async def execute_event(self, *, event: ExecutorEvent,
                            context: ExecutionContext) -> dict:
        """Execute or recover one routine via canonical StaffTask services."""
        _validate(event, context)
        existing = await self.load_evidence(
            run_id=context.run_id,
            event_id=event.event_id,
            expected_cursor=context.cursor,
            execution_fence=context.fence,
        )
        if existing:
            return existing
        if is_shift_event(event):
            return await record_shift_milestone(
                event, context, self.receipt_writer, EXECUTOR_AUTHORITY,
            )
        task = await self._event_task(event, context)
        if task is None:
            created = await self.request_creator(
                event=event,
                context=context,
                summary=_summary(event),
                priority=_priority(event),
            )
            task_id = created.get("task_id")
            if not task_id:
                raise CommunityExecutionAdapterError("canonical request service returned no task id")
            task = await self.task_loader(task_id)
        _validate_task(task, event, context)

        completion = await self._completion_receipt(task["task_id"], event, context)
        before_status = task.get("status")
        if completion is None:
            if before_status in {"completed", "skipped"}:
                raise CommunityExecutionAdapterError("closed event task has no matching completion receipt")
            task, completion = await self.task_completer(
                task_id=task["task_id"], note=_completion_note(event),
                actor=_actor(event), user=_staff_user(event),
            )
        if not completion or not completion.get("receipt_id"):
            raise CommunityExecutionAdapterError("canonical completion produced no durable receipt")
        self._validate_completion(completion, task, event, context)

        actor = _actor(event)
        return await self.receipt_writer(
            action_type=event.action_type,
            related_object_type=event.target_type,
            related_object_id=event.target_id,
            source="simulator",
            resident_id=event.target_id,
            assigned_role=event.department,
            assigned_user=event.actor_id,
            status="completed",
            result=_completion_note(event),
            provenance={
                **actor.receipt_fields(),
                "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
                "simulation_run_id": context.run_id,
                "simulation_event_id": event.event_id,
                "execution_cursor": context.cursor,
                "execution_fence": context.fence,
                "authority": EXECUTOR_AUTHORITY,
                "parent_receipt_id": completion["receipt_id"],
                "correlation_id": completion.get("correlation_id") or completion["receipt_id"],
                "before_state": {"task_id": task["task_id"], "status": before_status},
                "after_state": {
                    "task_id": task["task_id"],
                    "status": task.get("status"),
                    "blocked_capability_not_invoked": event.blocked_capability,
                },
                "result_label": "simulated",
                "provider_refs": [],
                "next_state": "executor_cursor_ready",
            },
        )
