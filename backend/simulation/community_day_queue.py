"""One day's executable events: capacity-scheduled tickets plus shift milestones.

Every routine becomes a canonical ticket that opens at its real request time.
Claim and completion come from the capacity schedule
(:mod:`simulation.community_capacity_schedule`): one active ticket per
qualified worker, so excess requests wait in the department queue and the
claim phase records how long and why (minutes per blocker).  A meal or
activity whose service window closed first gets an ``expire`` phase instead
(closed unserved by the department lead).  Phases beyond the 90-day horizon
are not planned, so an unfinished ticket stays truthfully open at the end.
"""
from functools import lru_cache
from hashlib import sha256

from simulation.community_capacity_schedule import HORIZON_MINUTES, ScheduledTicket, schedule_tickets
from simulation.community_cohort import BURN_IN, COHORTS, resident_keys_for, residents_for
from simulation.community_executor import CommunityExecutorError, ExecutorEvent
from simulation.community_player_requests import player_requests
from simulation.community_routines import RoutineEvent, plan_first_24_hours
from simulation.community_staffing import active_assignments
from simulation.community_shift_events import planned_events_for_day
from simulation.community_ticket_plan import CLAIM, COMPLETE, EXPIRE, OPEN, work_minutes

TIMELINE_DAYS = 90
_RESIDENT_INDEX = {
    cohort: {row.resident_key: row for row in residents_for(cohort)}
    for cohort in COHORTS
}


def opener(event: RoutineEvent):
    """The on-site worker who raises a staff-opened ticket, or None.

    Every simulated request comes from a person in the system: the resident,
    or a worker of ``opener_department`` physically on site at that minute
    (chosen deterministically). With nobody on site it is not raised at all.
    """
    if event.opened_by != "staff":
        return None
    staff = sorted((row for row in active_assignments(event.day_index, event.minute)
                    if row["department"] == event.opener_department), key=lambda row: row["actor_id"])
    if not staff:
        return None
    pick = int(sha256(event.event_id.encode()).hexdigest(), 16) % len(staff)
    return staff[pick]


def _raised(events) -> tuple:
    """Resident asks, and staff-opened work that has an on-site opener."""
    return tuple(e for e in events if e.opened_by == "resident" or opener(e) is not None)


@lru_cache(maxsize=None)
def cohort_schedule(cohort: str = BURN_IN):
    """Routines and player requests per source day and their capacity schedule, built once."""
    keys = resident_keys_for(cohort)
    routines = {day: _raised(plan_first_24_hours(keys, day_index=day) + player_requests(keys, day_index=day))
                for day in range(TIMELINE_DAYS)}
    scheduled = schedule_tickets(
        (event.event_id, event.department, event.priority, event.absolute_minute,
         work_minutes(event.routine), event.routine)
        for day_routines in routines.values() for event in day_routines
    )
    return routines, scheduled


def event_sort_key(event: ExecutorEvent) -> tuple[int, int, str, str]:
    """The one stable total ordering used by build and validation.

    Within one minute every completion runs first: a worker whose ticket
    completes at minute m is free to claim the next one at m, and the
    persisted one-active-ticket rule must see the completion before that claim.
    """
    return (
        event.day_index * 1440 + event.minute,
        0 if event.task_phase == COMPLETE else 1,
        event.stream_kind,
        event.event_id,
    )


def ticket_events(event: RoutineEvent, ticket: ScheduledTicket,
                  cohort: str = BURN_IN) -> tuple[ExecutorEvent, ...]:
    """Open / claim / complete (or open / expire) events for one scheduled ticket."""
    resident = _RESIDENT_INDEX.get(cohort, {}).get(event.resident_key)
    if resident is None:
        raise CommunityExecutorError(f"event is outside the {cohort} residents: {event.event_id}")
    phases = [(OPEN, ticket.requested_at, opener(event))]
    if ticket.claim_at is not None and ticket.complete_at < HORIZON_MINUTES:
        phases += [(CLAIM, ticket.claim_at, ticket.worker), (COMPLETE, ticket.complete_at, ticket.worker)]
    elif ticket.expire_at is not None and ticket.expire_at < HORIZON_MINUTES:
        phases.append((EXPIRE, ticket.expire_at, ticket.expired_by))
    rows = []
    for phase, absolute, worker in phases:
        day_index, minute = divmod(absolute, 1440)
        rows.append(ExecutorEvent(
            event_id=f"{event.event_id}:ticket_{phase}",
            stream_kind="routine_ticket_phase",
            action_type=event.routine,
            day_index=day_index,
            minute=minute,
            actor_id=resident.resident_id if worker is None else worker["actor_id"],
            actor_name=resident.name if worker is None else worker["name"],
            opened_by=event.opened_by,
            actor_type="simulated-agent",
            identity_basis="synthetic",
            department=event.department,
            target_type="resident",
            target_id=resident.resident_id,
            adapter=event.adapter,
            blocked_capability=event.blocked_adapter,
            workflow_event_id=event.event_id,
            task_phase=phase,
            requested_at_minute=ticket.requested_at,
            wait_reason=ticket.wait_reason if phase in (CLAIM, EXPIRE) else None,
            waited_minutes=ticket.waited_minutes if phase == CLAIM else None,
            wait_breakdown=ticket.wait_breakdown if phase in (CLAIM, EXPIRE) else None,
            called_in_on_call=ticket.called_in_on_call and phase == CLAIM,
        ))
    return tuple(rows)


def build_day_queue(day_index: int = 0, *, cohort: str = BURN_IN) -> tuple[ExecutorEvent, ...]:
    """Capacity-scheduled tickets from this source day plus its shift milestones."""
    routines, scheduled = cohort_schedule(cohort)
    events = [
        phase
        for event in routines.get(day_index, ())
        if event.event_id in scheduled
        for phase in ticket_events(event, scheduled[event.event_id], cohort)
    ]
    for event in planned_events_for_day(day_index):
        if event["stream_kind"] != "canonical_shift_milestone":
            continue
        events.append(ExecutorEvent(
            event_id=event["event_id"],
            stream_kind=event["stream_kind"],
            action_type=event["event_type"],
            day_index=event["day_index"],
            minute=event["minute"],
            actor_id=event["actor_id"],
            actor_name=event["actor_name"],
            actor_type=event["actor_type"],
            identity_basis=event["identity_basis"],
            department=event["department"],
            target_type=event["target_type"],
            target_id=event["target_id"],
            adapter="canonical_shift_service",
            simulated=event["actor_simulated"],
        ))
    return tuple(sorted(events, key=event_sort_key))
