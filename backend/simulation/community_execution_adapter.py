"""Provider-fenced canonical services for one community executor event."""

from collections.abc import Awaitable, Callable
from typing import Optional

from pymongo.errors import DuplicateKeyError

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent
from simulation.community_human_handoff import yielded_to_real_staff
from simulation.community_shift_execution import is_shift_event, record_shift_milestone, validate_shift_event
from simulation import community_run_start as run_start, community_ticket_staging as ticket
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN, PHASES


EXECUTOR_AUTHORITY = "living_community_executor"
SUPPORTED_ADAPTER = "canonical_staff_task"


class CommunityExecutionAdapterError(RuntimeError):
    """The event was refused before any completion claim."""


def _validate(event: ExecutorEvent, context: ExecutionContext) -> None:
    if context.providers_allowed:
        raise CommunityExecutionAdapterError("community execution never permits provider calls")
    if (context.simulation_scope != SIMULATION_SCOPE
            or context.simulation_community_id != COMMUNITY_ID):
        raise CommunityExecutionAdapterError("execution context is outside the living community")
    if (event.actor_type != "simulated-agent" or event.identity_basis != "synthetic"
            or not event.simulated):
        raise CommunityExecutionAdapterError("event lacks explicit synthetic provenance")
    if is_shift_event(event):
        validate_shift_event(event)
        return
    # OPEN is raised by its person: the resident, or the on-site worker who
    # opened it; claim/complete are always a simulated worker.
    resident_opens = event.task_phase == OPEN and event.opened_by == "resident"
    actor_matches = (event.actor_id == event.target_id if resident_opens
                     else event.actor_id.startswith("sim:staff:"))
    if (event.stream_kind != "routine_ticket_phase" or event.adapter != SUPPORTED_ADAPTER
            or event.target_type != "resident" or event.task_phase not in PHASES
            or not event.workflow_event_id or not actor_matches):
        raise CommunityExecutionAdapterError(
            f"unsupported community executor event: {event.stream_kind}/{event.adapter}"
        )
RequestCreator = ReceiptWriter = Callable[..., Awaitable[dict]]
TaskLoader = Callable[[str], Awaitable[dict]]
TaskTransition = Callable[..., Awaitable[tuple[dict, Optional[dict]]]]


class CanonicalCommunityExecutionServices:
    def __init__(self, *, store=None, request_creator: Optional[RequestCreator] = None,
                 task_loader: Optional[TaskLoader] = None,
                 task_starter: Optional[TaskTransition] = None,
                 task_completer: Optional[TaskTransition] = None,
                 receipt_writer: Optional[ReceiptWriter] = None):
        self.store = store if store is not None else ticket.default_store()
        self._run_starts: dict = {}
        self.request_creator = request_creator or ticket.create_request
        self.task_loader = task_loader or ticket.load_task
        self.task_starter = task_starter or ticket.start_task
        self.task_completer = task_completer or ticket.complete_task
        self.receipt_writer = receipt_writer or ticket.write_receipt

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
        }, {"_id": 0}, sort=[("created_at", -1), ("receipt_id", -1)])

    async def _event_task(self, event: ExecutorEvent, context: ExecutionContext) -> Optional[dict]:
        return await self.store.staff_tasks.find_one({
            "conversation_session_id": ticket.event_session(event),
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "resident_id": event.target_id,
            "category": event.department,
            "simulated": True,
        }, {"_id": 0})

    async def _refuse_second_active_ticket(self, task: dict, event: ExecutorEvent,
                                           context: ExecutionContext) -> None:
        """One active ticket per worker, checked against persisted state."""
        held = await self.store.staff_tasks.find_one({
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulated": True,
            "status": "in_progress",
            "assigned_to": event.actor_id,
            "task_id": {"$ne": task["task_id"]},
        }, {"_id": 0, "task_id": 1})
        if held:
            raise CommunityExecutionAdapterError(
                f"worker {event.actor_id} already holds active ticket {held['task_id']}"
            )

    async def _task_receipt(self, task_id: str, event: ExecutorEvent,
                            context: ExecutionContext, action_type: str) -> Optional[dict]:
        query = {
            "related_object_type": "task",
            "related_object_id": task_id,
            "action_type": action_type,
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        }
        if action_type != "resident_request_created":
            query.update({
                "actor_id": event.actor_id,
                "actor_type": "simulated-agent",
                "identity_basis": "synthetic",
                "simulated": True,
            })
        return await self.store.receipts.find_one(
            query, {"_id": 0}, sort=[("created_at", -1), ("receipt_id", -1)],
        )

    async def _write_phase(self, *, event: ExecutorEvent, context: ExecutionContext,
                           task: dict, parent: dict,
                           before_status: Optional[str], status: str = "completed",
                           result: Optional[str] = None,
                           next_state: Optional[str] = None) -> dict:
        actor = ticket.actor(event)
        return await self.receipt_writer(
            action_type=event.action_type,
            related_object_type=event.target_type,
            related_object_id=event.target_id,
            source="simulator",
            resident_id=event.target_id,
            assigned_role=event.department,
            assigned_user=None if event.task_phase == OPEN else event.actor_id,
            status=status,
            result=result or ticket.phase_result(event),
            provenance={
                **actor.receipt_fields(),
                "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
                "simulation_run_id": context.run_id,
                "simulation_event_id": event.event_id,
                "execution_cursor": context.cursor,
                "execution_fence": context.fence,
                "authority": EXECUTOR_AUTHORITY,
                "parent_receipt_id": parent["receipt_id"],
                "correlation_id": parent.get("correlation_id") or parent["receipt_id"],
                "before_state": {"task_id": task["task_id"], "status": before_status},
                "after_state": {
                    "task_id": task["task_id"],
                    "status": task.get("status"),
                    "blocked_capability_not_invoked": event.blocked_capability,
                    **ticket.queue_fields(event),
                },
                "result_label": "simulated",
                "provider_refs": [],
                "next_state": next_state or ticket.next_phase(event.task_phase),
            },
        )

    async def execute_event(self, *, event: ExecutorEvent,
                            context: ExecutionContext) -> dict:
        """Advance one canonical ticket phase; never open and close in one tick."""
        _validate(event, context)
        start = await run_start.run_start_minute(self.store, context.run_id, self._run_starts)
        if run_start.before_start(event, start):
            existing = await self.load_evidence(
                run_id=context.run_id, event_id=event.event_id,
                expected_cursor=context.cursor, execution_fence=context.fence,
            )
            return existing or await run_start.record_before_start(
                self.receipt_writer, EXECUTOR_AUTHORITY, event, context, start)
        if is_shift_event(event):
            existing = await self.load_evidence(
                run_id=context.run_id, event_id=event.event_id,
                expected_cursor=context.cursor, execution_fence=context.fence,
            )
            if existing:
                return existing
            return await record_shift_milestone(
                event, context, self.receipt_writer, EXECUTOR_AUTHORITY,
            )
        exact = await self.load_evidence(
            run_id=context.run_id, event_id=event.event_id,
            expected_cursor=context.cursor, execution_fence=context.fence,
        )
        if exact:
            return exact
        task = await self._event_task(event, context)
        if event.task_phase == OPEN and task is None:
            created = await self.request_creator(
                event=event, context=context,
                summary=ticket.summary(event), priority=ticket.priority(event),
            )
            task_id = created.get("task_id")
            if not task_id:
                raise CommunityExecutionAdapterError("canonical request service returned no task id")
            task = await self.task_loader(task_id)
            try:
                ticket.validate_task(task, event, context)
            except ticket.CommunityTicketStageError as exc:
                raise CommunityExecutionAdapterError(str(exc)) from exc
            origin_action = ticket.origin_action(event)
            origin = await self._task_receipt(task_id, event, context, origin_action)
            if not origin:
                raise CommunityExecutionAdapterError("canonical request has no durable origin receipt")
            try:
                ticket.validate_task_receipt(
                    origin, task, event, context, action_type=origin_action,
                    status="created", staff_actor=event.opened_by == "staff",
                )
            except ticket.CommunityTicketStageError as exc:
                raise CommunityExecutionAdapterError(str(exc)) from exc
            return await self._write_phase(
                event=event, context=context, task=task, parent=origin,
                before_status=None,
            )

        if task is None:
            raise CommunityExecutionAdapterError("ticket phase has no canonical task")
        try:
            ticket.validate_task(task, event, context)
        except ticket.CommunityTicketStageError as exc:
            raise CommunityExecutionAdapterError(str(exc)) from exc
        state = task.get("status")
        actor, user = ticket.actor(event), ticket.staff_user(event)
        if event.task_phase != OPEN:
            yielded = await yielded_to_real_staff(self.store, event, context.run_id, task)
            if yielded:
                parent, result, next_state = yielded
                return await self._write_phase(
                    event=event, context=context, task=task, parent=parent,
                    before_status=state, status="cancelled", result=result, next_state=next_state,
                )

        if event.task_phase == OPEN:
            if state != "pending":
                raise CommunityExecutionAdapterError("open phase task is not pending")
            origin_action = ticket.origin_action(event)
            phase_receipt = await self._task_receipt(
                task["task_id"], event, context, origin_action,
            )
            action_type, phase_status, before_status = (origin_action, "created", None)
        elif event.task_phase == CLAIM and state == "pending":
            await self._refuse_second_active_ticket(task, event, context)
            try:
                task, phase_receipt = await self.task_starter(
                    task_id=task["task_id"], actor=actor, user=user,
                )
            except DuplicateKeyError as exc:
                raise CommunityExecutionAdapterError(
                    f"database refused a second active ticket for {event.actor_id}"
                ) from exc
            action_type, phase_status, before_status = "task_in_progress", "in_progress", "pending"
        elif event.task_phase == CLAIM and state == "in_progress":
            phase_receipt = await self._task_receipt(
                task["task_id"], event, context, "task_in_progress",
            )
            action_type, phase_status, before_status = "task_in_progress", "in_progress", "pending"
        elif event.task_phase == COMPLETE and state == "in_progress":
            task, phase_receipt = await self.task_completer(
                task_id=task["task_id"], note=ticket.completion_note(event),
                actor=actor, user=user,
            )
            action_type, phase_status, before_status = "task_completed", "completed", "in_progress"
        elif event.task_phase == COMPLETE and state == "completed":
            phase_receipt = await self._task_receipt(
                task["task_id"], event, context, "task_completed",
            )
            action_type, phase_status, before_status = "task_completed", "completed", "in_progress"
        else:
            raise CommunityExecutionAdapterError(
                f"ticket {event.task_phase} phase contradicts canonical task state {state}"
            )

        if not phase_receipt or not phase_receipt.get("receipt_id"):
            raise CommunityExecutionAdapterError(f"canonical {action_type} produced no durable receipt")
        try:
            ticket.validate_task_receipt(
                phase_receipt, task, event, context, action_type=action_type,
                status=phase_status, staff_actor=event.task_phase != OPEN or event.opened_by == "staff",
            )
        except ticket.CommunityTicketStageError as exc:
            raise CommunityExecutionAdapterError(str(exc)) from exc
        return await self._write_phase(
            event=event, context=context, task=task, parent=phase_receipt,
            before_status=before_status,
        )
