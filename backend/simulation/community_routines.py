"""Pure first-day routine plan for the living-community simulator.

This module describes *intent* only.  It does not import the database, call a
provider, or mutate CAOSCare state.  A scheduler may dispatch ``safe_now``
events through the canonical StaffTask origin/lifecycle.  Blocked adapters are
listed explicitly so a future driver cannot accidentally use an unsafe path.

Medication events are reminders, never medication administration or evidence
of ingestion/adherence.  Transportation and family-call events coordinate a
human workflow; they never book a vehicle or place a call.
"""

from dataclasses import dataclass, field
from typing import Optional


BURN_IN_RESIDENT_KEYS = tuple(f"resident-{index:03d}" for index in range(1, 11))

SAFE_NOW = "safe_now"
BLOCKED = "blocked"

# Adapter status is repository truth at the time this plan was introduced.
# The plan uses only canonical_staff_task; related blocked capabilities are
# attached to events so the execution layer knows where it must stop.
ADAPTER_CAPABILITIES = {
    "canonical_staff_task": {
        "status": SAFE_NOW,
        "reason": "Uses the receipted StaffTask request and lifecycle services.",
    },
    "medication_kiosk": {
        "status": BLOCKED,
        "reason": "Reminder acknowledgements lack simulator provenance and facility-local timing.",
    },
    "transport_resource_booking": {
        "status": BLOCKED,
        "reason": "Runs, drivers, and vehicles are not partitioned from real resources.",
    },
    "outbound_family_call": {
        "status": BLOCKED,
        "reason": "Outbound room calling is not configured or simulation-isolated.",
    },
    "outbound_front_desk_call": {
        "status": BLOCKED,
        "reason": "Front-desk outbound calling is not configured or simulation-isolated.",
    },
    "menu_content_publish": {
        "status": BLOCKED,
        "reason": "Menu content writes do not accept a simulated actor and run provenance.",
    },
    "activity_schedule_publish": {
        "status": BLOCKED,
        "reason": "Schedule content writes do not accept a simulated actor and run provenance.",
    },
    "resident_alert": {
        "status": BLOCKED,
        "reason": "Alert delivery can reach real escalation and family notification providers.",
    },
}


@dataclass(frozen=True)
class RoutineEvent:
    """One planned intent with an explicit, bounded execution coordinate.

    ``plan_day_index`` is the day whose routine recipe produced the event.
    ``day_index`` and ``minute`` are the event's scheduled day and minute of
    that day.  A staggered event may therefore drain into the following day
    without producing an invalid clock time or losing its source-day identity.
    """

    plan_day_index: int
    day_index: int
    minute: int
    resident_key: str
    routine: str
    department: str
    summary: str
    priority: str = "normal"
    adapter: str = "canonical_staff_task"
    blocked_adapter: Optional[str] = None
    truth_boundary: str = "Completion records only the described simulated work."
    possible_outcomes: tuple[str, ...] = field(
        default=("completed", "resident_refused", "resident_requested_reschedule")
    )
    event_id: str = field(default="", compare=False)

    @property
    def time_hhmm(self) -> str:
        return f"{self.minute // 60:02d}:{self.minute % 60:02d}"

    @property
    def absolute_minute(self) -> int:
        return self.day_index * 24 * 60 + self.minute

    @property
    def rollover_days(self) -> int:
        return self.day_index - self.plan_day_index

    @property
    def adapter_status(self) -> str:
        return ADAPTER_CAPABILITIES[self.adapter]["status"]


@dataclass(frozen=True)
class _RoutineSpec:
    routine: str
    department: str
    base_minute: int
    summary: str
    priority: str = "normal"
    stagger: int = 2
    blocked_adapter: Optional[str] = None
    truth_boundary: str = "Completion records only the described simulated work."


_DAILY_ROUTINES = (
    _RoutineSpec("overnight_room_check", "nursing", 30,
                 "Perform the scheduled overnight room check."),
    _RoutineSpec("toileting_transfer_support", "nursing", 390,
                 "Offer scheduled toileting or transfer support.", "high"),
    _RoutineSpec("morning_room_check", "nursing", 435,
                 "Perform the scheduled morning resident room check."),
    _RoutineSpec(
        "morning_medication_reminder", "nursing", 470,
        "Offer the scheduled morning medication reminder.", "high", blocked_adapter="medication_kiosk",
        truth_boundary="Records reminder delivery only; never medication administration, ingestion, or adherence.",
    ),
    _RoutineSpec(
        "breakfast", "kitchen", 490,
        "Offer scheduled breakfast service.",
        truth_boundary="Records meal service only; never claims that the resident ate or how much was consumed.",
    ),
    _RoutineSpec("shower_assistance", "nursing", 540,
                 "Offer scheduled shower assistance; the resident may decline or reschedule.", "high", stagger=5),
    _RoutineSpec("housekeeping_room_service", "housekeeping", 615,
                 "Offer scheduled room cleaning and linen service.", stagger=4),
    _RoutineSpec(
        "lunch", "kitchen", 720, "Offer scheduled lunch service.",
        truth_boundary="Records meal service only; never claims that the resident ate or how much was consumed.",
    ),
    _RoutineSpec("afternoon_toileting_transfer_support", "nursing", 780,
                 "Offer scheduled toileting or transfer support.", "high"),
    _RoutineSpec("activity_offer_and_escort", "activities", 840,
                 "Offer the planned activity and escort support; attendance remains unconfirmed until completed.",
                 blocked_adapter="activity_schedule_publish", stagger=3),
    _RoutineSpec(
        "dinner", "kitchen", 1020, "Offer scheduled dinner service.",
        truth_boundary="Records meal service only; never claims that the resident ate or how much was consumed.",
    ),
    _RoutineSpec(
        "evening_medication_reminder", "nursing", 1185,
        "Offer the scheduled evening medication reminder.", "high", blocked_adapter="medication_kiosk",
        truth_boundary="Records reminder delivery only; never medication administration, ingestion, or adherence.",
    ),
    _RoutineSpec("evening_toileting_transfer_support", "nursing", 1260,
                 "Offer scheduled toileting or transfer support.", "high"),
    _RoutineSpec("night_room_check", "nursing", 1350,
                 "Perform the scheduled night resident room check."),
)


def _event(spec: _RoutineSpec, resident_key: str, resident_index: int, day_index: int) -> RoutineEvent:
    scheduled_offset = spec.base_minute + (resident_index - 1) * spec.stagger
    rollover_days, minute = divmod(scheduled_offset, 24 * 60)
    return RoutineEvent(
        plan_day_index=day_index,
        day_index=day_index + rollover_days,
        minute=minute,
        resident_key=resident_key,
        routine=spec.routine,
        department=spec.department,
        summary=spec.summary,
        priority=spec.priority,
        blocked_adapter=spec.blocked_adapter,
        truth_boundary=spec.truth_boundary,
        event_id=f"day-{day_index:03d}:{resident_key}:{spec.routine}",
    )


def plan_first_24_hours(
    resident_keys: tuple[str, ...] = BURN_IN_RESIDENT_KEYS,
    *,
    day_index: int = 0,
) -> tuple[RoutineEvent, ...]:
    """Return one source day's deterministic plan without performing actions.

    The returned plan includes its complete drain: resident staggering may put
    late work on the next scheduled day, but ``minute`` always remains a valid
    minute-of-day value.
    """
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    if not resident_keys or len(set(resident_keys)) != len(resident_keys):
        raise ValueError("resident_keys must be a non-empty unique sequence")

    events: list[RoutineEvent] = []
    for resident_index, resident_key in enumerate(resident_keys, start=1):
        if not resident_key:
            raise ValueError("resident keys must be non-empty")
        events.extend(_event(spec, resident_key, resident_index, day_index) for spec in _DAILY_ROUTINES)

        # A subset has a planned appointment.  These are coordination tasks,
        # deliberately not calls to the unpartitioned transport booking engine.
        if resident_index in (2, 5, 8):
            events.append(_event(_RoutineSpec(
                "appointment_coordination", "administration", 555,
                "Confirm the simulated appointment details with staff; do not claim provider confirmation.",
                stagger=4,
            ), resident_key, resident_index, day_index))
            events.append(_event(_RoutineSpec(
                "transport_coordination", "transportation", 645,
                "Coordinate requested ride details for the appointment.",
                blocked_adapter="transport_resource_booking", stagger=4,
                truth_boundary="Records coordination only; never claims a driver, vehicle, pickup, or booking.",
            ), resident_key, resident_index, day_index))

        if resident_index in (1, 6):
            events.append(_event(_RoutineSpec(
                "preventive_maintenance_check", "maintenance", 690,
                "Inspect the simulated room fixture listed for preventive maintenance.", stagger=5,
            ), resident_key, resident_index, day_index))

        if resident_index % 2 == 0:
            events.append(_event(_RoutineSpec(
                "family_call_coordination", "administration", 960,
                "Coordinate an approved family-call request for the resident.",
                blocked_adapter="outbound_family_call", stagger=3,
                truth_boundary="Records coordination only; never claims that a call was placed, rang, or connected.",
            ), resident_key, resident_index, day_index))

        if resident_index in (3, 7):
            events.append(_event(_RoutineSpec(
                "front_desk_message_follow_up", "front_desk", 900,
                "Review and route the simulated resident message for staff follow-up.",
                blocked_adapter="outbound_front_desk_call", stagger=4,
                truth_boundary=(
                    "Records message coordination only; never claims that the resident "
                    "was contacted or that an outbound call was placed."
                ),
            ), resident_key, resident_index, day_index))

    return tuple(sorted(events, key=lambda item: (
        item.day_index, item.minute, item.resident_key, item.routine, item.event_id,
    )))


def blocked_adapters() -> tuple[str, ...]:
    """Stable list for UI/tests; blocked capabilities are never dispatchable."""
    return tuple(sorted(name for name, info in ADAPTER_CAPABILITIES.items() if info["status"] == BLOCKED))
