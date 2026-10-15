"""Requests raised by people in the community, not by the schedule.

Michael, 2026-10-14: "all simulations need to come from players in the
system, not outta simulated air" and "this has to operate as a real company".
Two kinds of unscheduled work, each with a named origin:

  resident calls  - a resident asks for something in their own words
                    (call button / Aria). About 100 a day across 75 residents,
                    the owner's estimate for an 80-apartment community.
  staff reports   - an on-site worker notices something and raises a ticket
                    for another department (a light out, a spill, a leak).

Preventive maintenance and rounds stay in :mod:`community_routines`, opened by
the on-duty worker of their department. Everything here is deterministic per
(day, resident) so the 90-day plan and its fingerprint are reproducible. The
opener of a staff report is chosen later, from who is actually on site at that
minute (:mod:`community_day_queue`); with nobody on site it is not raised.
Truth boundary: completion records the simulated work only - no clinical
assessment, no medication, no outbound call, no vehicle booked.
"""
from random import Random

from simulation.community_routines import RoutineEvent

# Owner estimate: ~100 resident calls/day in an 80-apartment community.
RESIDENT_CALLS_PER_DAY = 100
STAFF_REPORTS_PER_DAY = 15

# (routine, department, priority, weight, resident's words, ticket summary)
RESIDENT_CALLS = (
    ("resident_call_help_up", "nursing", "high", 14,
     "Can someone help me get up out of my chair?", "Resident asked for help getting up."),
    ("resident_call_bathroom", "nursing", "high", 12,
     "I need help to the bathroom, please.", "Resident asked for help to the bathroom."),
    ("resident_call_check_on_me", "nursing", "high", 8,
     "I don't feel quite right, could someone come check on me?",
     "Resident asked for a staff check-in (no clinical assessment is recorded by the simulator)."),
    ("resident_call_dressing", "nursing", "normal", 6,
     "Could someone help me get dressed?", "Resident asked for help getting dressed."),
    ("resident_call_reposition", "nursing", "normal", 5,
     "Can somebody help me get comfortable in bed?", "Resident asked for help repositioning in bed."),
    ("resident_call_towels", "housekeeping", "normal", 6,
     "Could I get some fresh towels?", "Resident asked for fresh towels."),
    ("resident_call_spill", "housekeeping", "normal", 5,
     "I spilled my coffee on the floor.", "Resident reported a spill in the apartment."),
    ("resident_call_trash", "housekeeping", "low", 4,
     "My trash is full, can someone take it out?", "Resident asked for the trash to be taken out."),
    ("resident_call_light_out", "maintenance", "normal", 5,
     "The lamp by my bed won't turn on.", "Resident reported a light that will not turn on."),
    ("resident_call_toilet_running", "maintenance", "normal", 4,
     "My toilet keeps running.", "Resident reported a running toilet."),
    ("resident_call_too_warm", "maintenance", "normal", 3,
     "It's too warm in here and the thermostat isn't helping.", "Resident reported the apartment is too warm."),
    ("resident_call_tv_remote", "maintenance", "low", 3,
     "My TV remote stopped working.", "Resident asked for help with the TV remote."),
    ("resident_call_snack", "kitchen", "normal", 6,
     "Could I get a snack and something to drink?", "Resident asked for a snack and a drink."),
    ("resident_call_tray", "kitchen", "normal", 4,
     "I'm not up to going to dinner, can I have a tray?", "Resident asked for a meal tray in the apartment."),
    ("resident_call_package", "front_desk", "low", 4,
     "Did a package come for me today?", "Resident asked whether a package has arrived."),
    ("resident_call_visitor", "front_desk", "low", 3,
     "My daughter is coming at two, can you let the front desk know?",
     "Resident asked the front desk to expect a visitor."),
    ("resident_call_ride", "transportation", "normal", 3,
     "I need a ride to the pharmacy tomorrow.",
     "Resident asked for a ride to be arranged (coordination only; no vehicle is booked)."),
)

# (routine, reporter department, target department, priority, weight, summary)
STAFF_REPORTS = (
    ("staff_report_bed_alarm", "nursing", "maintenance", "high", 3,
     "Care staff reported a bed or chair alarm not working in the apartment."),
    ("staff_report_call_cord", "nursing", "maintenance", "high", 2,
     "Care staff reported a damaged pull cord in the apartment bathroom."),
    ("staff_report_linen_change", "nursing", "housekeeping", "normal", 4,
     "Care staff asked for a full linen change in the apartment."),
    ("staff_report_missed_meal", "nursing", "kitchen", "normal", 3,
     "Care staff asked the kitchen for a tray: the resident missed the meal."),
    ("staff_report_leaking_faucet", "housekeeping", "maintenance", "normal", 3,
     "Housekeeping reported a leaking faucet while cleaning the apartment."),
    ("staff_report_broken_blind", "housekeeping", "maintenance", "low", 2,
     "Housekeeping reported a broken window blind in the apartment."),
    ("staff_report_ride_follow_up", "front_desk", "transportation", "normal", 2,
     "Front desk passed on a resident's ride question (coordination only; no vehicle is booked)."),
    ("staff_report_activity_help", "activities", "nursing", "normal", 2,
     "Activities asked care staff to help the resident to the afternoon activity."),
)

# Calls cluster in waking hours; a few come overnight.
_HOUR_WEIGHTS = (1, 1, 1, 1, 1, 2, 4, 7, 9, 9, 8, 7, 6, 7, 8, 8, 7, 6, 7, 8, 7, 5, 3, 2)


def _minute(rng: Random) -> int:
    hour = rng.choices(range(24), weights=_HOUR_WEIGHTS)[0]
    return hour * 60 + rng.randrange(60)


def _staff_minute(rng: Random) -> int:
    """Reports are raised during staffed daytime hours (08:00-19:59)."""
    return rng.randrange(8 * 60, 20 * 60)


def player_requests(resident_keys: tuple[str, ...], *, day_index: int) -> tuple[RoutineEvent, ...]:
    """One day's resident calls and staff reports, deterministic per day."""
    if not resident_keys:
        return ()
    scale = len(resident_keys) / 75
    rng = Random(f"living-community-player-requests:{day_index}")
    events = []
    for n in range(max(1, round(RESIDENT_CALLS_PER_DAY * scale))):
        routine, dept, prio, _w, words, summary = rng.choices(RESIDENT_CALLS, weights=[r[3] for r in RESIDENT_CALLS])[0]
        key = rng.choice(resident_keys)
        minute = _minute(rng)
        events.append(RoutineEvent(
            plan_day_index=day_index, day_index=day_index, minute=minute, resident_key=key,
            routine=routine, department=dept, summary=summary, priority=prio,
            blocked_adapter="transport_resource_booking" if dept == "transportation" else None,
            truth_boundary="Records the simulated response to the resident's request only.",
            event_id=f"day-{day_index:03d}:{key}:{routine}_{n:03d}",
            opened_by="resident", resident_words=words,
        ))
    for n in range(max(1, round(STAFF_REPORTS_PER_DAY * scale))):
        routine, reporter, dept, prio, _w, summary = rng.choices(STAFF_REPORTS, weights=[r[4] for r in STAFF_REPORTS])[0]
        key = rng.choice(resident_keys)
        events.append(RoutineEvent(
            plan_day_index=day_index, day_index=day_index, minute=_staff_minute(rng), resident_key=key,
            routine=routine, department=dept, summary=summary, priority=prio,
            blocked_adapter="transport_resource_booking" if dept == "transportation" else None,
            truth_boundary="Records the simulated follow-up to the staff report only.",
            event_id=f"day-{day_index:03d}:{key}:{routine}_{n:03d}",
            opened_by="staff", opener_department=reporter,
        ))
    return tuple(events)


SUMMARIES = {r[0]: r[5] for r in RESIDENT_CALLS} | {r[0]: r[5] for r in STAFF_REPORTS}
WORDS = {r[0]: r[4] for r in RESIDENT_CALLS}
PRIORITIES = {r[0]: r[2] for r in RESIDENT_CALLS} | {r[0]: r[3] for r in STAFF_REPORTS}


def base_routine(routine: str) -> str:
    """'resident_call_spill_007' -> 'resident_call_spill' (event ids carry a sequence)."""
    head, _, tail = routine.rpartition("_")
    return head if tail.isdigit() and head in SUMMARIES else routine
