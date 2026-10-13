"""Receipt-only execution boundary for synthetic shift milestones."""

import re
from collections.abc import Awaitable, Callable

from models import uid
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_executor import ExecutionContext, ExecutorEvent


SHIFT_ACTIONS = frozenset({"clock_in", "handoff", "clock_out"})
SHIFT_ADAPTER = "canonical_shift_service"
SHIFT_STREAM = "canonical_shift_milestone"
_TARGET = re.compile(
    r"^sim:shift:-?\d+:(sim:staff:([^:]+):[^:]+:\d+):(day|evening|night)$"
)
ReceiptWriter = Callable[..., Awaitable[dict]]


class ShiftExecutionError(RuntimeError):
    """The milestone cannot be represented truthfully as synthetic evidence."""


def is_shift_event(event: ExecutorEvent) -> bool:
    return event.stream_kind == SHIFT_STREAM or event.adapter == SHIFT_ADAPTER


def validate_shift_event(event: ExecutorEvent) -> None:
    match = _TARGET.fullmatch(event.target_id)
    if (
        event.stream_kind != SHIFT_STREAM
        or event.adapter != SHIFT_ADAPTER
        or event.action_type not in SHIFT_ACTIONS
        or event.target_type != "staff_shift"
        or not match
        or match.group(1) != event.actor_id
        or match.group(2) != event.department
        or event.blocked_capability is not None
    ):
        raise ShiftExecutionError("unsupported or mismatched synthetic shift milestone")


async def record_shift_milestone(
    event: ExecutorEvent,
    context: ExecutionContext,
    receipt_writer: ReceiptWriter,
    authority: str,
) -> dict:
    """Record simulated milestone evidence; never authenticate or mark attendance."""
    validate_shift_event(event)
    actor = ActorContext(
        actor_id=event.actor_id,
        actor_type=event.actor_type,
        identity_basis=event.identity_basis,
        channel="simulator",
        name=event.actor_name,
        role="staff",
        department=event.department,
        simulated=True,
    )
    receipt_id = uid("rcpt")
    return await receipt_writer(
        action_type=event.action_type,
        related_object_type="staff_shift",
        related_object_id=event.target_id,
        source="simulator",
        assigned_role=event.department,
        assigned_user=event.actor_id,
        status="completed",
        result=(f"Simulated {event.action_type.replace('_', ' ')} milestone recorded; "
                "no authentication, User session, or real attendance is claimed."),
        receipt_id=receipt_id,
        provenance={
            **actor.receipt_fields(),
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "simulation_run_id": context.run_id,
            "simulation_event_id": event.event_id,
            "execution_cursor": context.cursor,
            "execution_fence": context.fence,
            "authority": authority,
            "parent_receipt_id": None,
            "correlation_id": receipt_id,
            "before_state": None,
            "after_state": {
                "milestone": event.action_type,
                "simulated": True,
                "authenticated": False,
                "real_attendance_claimed": False,
            },
            "result_label": "simulated",
            "provider_refs": [],
            "next_state": "executor_cursor_ready",
        },
    )
