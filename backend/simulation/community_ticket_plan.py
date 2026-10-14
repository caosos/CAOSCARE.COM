"""Simulated-time dwell for externally visible routine tickets.

A ticket opens at its request time, becomes claimable ``OPEN_TO_CLAIM_MINUTES``
later, and is held by one worker for its routine's hands-on minutes.  The
actual claim time comes from the capacity schedule
(:mod:`simulation.community_capacity_schedule`), so a busy department makes
the ticket wait longer, truthfully.
"""

OPEN = "open"
CLAIM = "claim"
COMPLETE = "complete"
PHASES = (OPEN, CLAIM, COMPLETE)

# The Live Operations surface polls every two real seconds. At the default
# 60x speed, one simulated minute passes per real second, so the shortest
# open dwell (5) and the shortest hands-on time (3) each span more than one
# poll without making the accelerated community feel stalled.
OPEN_TO_CLAIM_MINUTES = 5
CLAIM_TO_COMPLETE_MINUTES = 10
# Simulation assumption, not measured facility data: hands-on minutes one
# worker spends on one resident's ticket.  Routines not listed take the
# default ``CLAIM_TO_COMPLETE_MINUTES``.  Meals are plated service to one
# resident in a shared dining service, not cooking the meal.
ROUTINE_WORK_MINUTES = {
    "overnight_room_check": 3,
    "morning_room_check": 3,
    "night_room_check": 3,
    "morning_medication_reminder": 3,
    "evening_medication_reminder": 3,
    "toileting_transfer_support": 8,
    "afternoon_toileting_transfer_support": 8,
    "evening_toileting_transfer_support": 8,
    "shower_assistance": 20,
    "breakfast": 3,
    "lunch": 3,
    "dinner": 3,
}
DEFAULT_ACCELERATION = 60
RUNTIME_POLL_SECONDS = 2


def work_minutes(routine: str) -> int:
    """Hands-on minutes between claim and completion for one routine ticket."""
    return ROUTINE_WORK_MINUTES.get(routine, CLAIM_TO_COMPLETE_MINUTES)


def minimum_real_dwell_seconds(simulated_minutes: int, speed: int = DEFAULT_ACCELERATION) -> float:
    if simulated_minutes < 0 or speed <= 0:
        raise ValueError("dwell and speed must be non-negative and positive")
    return simulated_minutes * 60 / speed
