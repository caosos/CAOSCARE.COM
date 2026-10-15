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
# A time-bound ticket closed unserved when its service window ended.
EXPIRE = "expire"
PHASES = (OPEN, CLAIM, COMPLETE, EXPIRE)

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
    # Requests raised by residents and staff (community_player_requests).
    "resident_call_help_up": 8, "resident_call_bathroom": 8, "resident_call_check_on_me": 10,
    "resident_call_dressing": 15, "resident_call_reposition": 8, "resident_call_towels": 5,
    "resident_call_spill": 10, "resident_call_trash": 5, "resident_call_light_out": 15,
    "resident_call_toilet_running": 20, "resident_call_too_warm": 15, "resident_call_tv_remote": 10,
    "resident_call_snack": 5, "resident_call_tray": 10, "resident_call_package": 5,
    "resident_call_visitor": 3, "resident_call_ride": 10,
    "staff_report_bed_alarm": 20, "staff_report_call_cord": 20, "staff_report_linen_change": 15,
    "staff_report_missed_meal": 10, "staff_report_leaking_faucet": 30, "staff_report_broken_blind": 20,
    "staff_report_ride_follow_up": 10, "staff_report_activity_help": 10,
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
