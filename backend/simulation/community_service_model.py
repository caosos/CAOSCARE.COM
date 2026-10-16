"""How dining and activities are served (CO-008 service model, owner 2026-10-15).

Owner direction: one evening kitchen worker plating 75 dinners one at a time,
and a dedicated escort for every resident going to an activity, are not how a
senior-living community runs. This module is the one source of truth for the
corrected model; routines, care plans, work minutes and ticket text read it.

Dining
  * The kitchen has cooks and dining servers. Cooking, plating and dish/bussing
    work are the cook's shift (held by the cook role, never a resident ticket).
    Each resident's meal is one service ticket taken by a dining server; several
    servers work the same seating in parallel.
  * Residents arrive across the first hour of a seating (one per simulated
    minute), not across the whole evening.
  * Most residents eat in the dining room (about 3 server-minutes each: carry
    the plate, settle the place, clear).
  * Room delivery (owner estimate, Michael 2026-10-15): about 30 of 75
    residents (40%) have each meal delivered to the apartment. One delivery is
    one tray carried by one staff member: pick up the tray, walk to the
    apartment, hand off and set up, walk back (``ROOM_DELIVERY_STEPS``). Meal
    delivery aides take deliveries first and dining servers help; dining
    servers take the dining room first and delivery aides help.

Activities
  * The activity itself is a group session run by the activities coordinator
    (coordinator's shift, not a resident ticket).
  * Residents who move independently (with or without a walker) attend on
    their own and create no staff ticket. Residents who need an escort or use a
    wheelchair get one escort ticket shortly before the session starts.
  * About one in seven prefers a one-to-one visit instead of the group; those
    are 20-minute coordinator visits through the afternoon.
  * Not everyone attends every day: attendance rotates deterministically
    (three days in five per resident).

Every number here is a labelled simulation assumption, not facility data or an
assessment. Mobility is synthetic and used only to decide whether moving to an
activity takes staff time; it never represents a clinical finding. Meals record
service only, never what anyone ate.
"""
from typing import Optional

MEALS = ("breakfast", "lunch", "dinner")
ROOM_SERVICE = "_room_service"
MEAL_ROUTINES = MEALS + tuple(meal + ROOM_SERVICE for meal in MEALS)

ACTIVITY_ESCORT = "activity_escort"
ACTIVITY_VISIT = "one_to_one_activity_visit"
ACTIVITY_ROUTINES = (ACTIVITY_ESCORT, ACTIVITY_VISIT)

# Seating starts (minute of day); residents arrive one per minute after it.
MEAL_SEATING = {"breakfast": 450, "lunch": 690, "dinner": 1020}
ACTIVITY_SESSION_START = 840          # 14:00 group session
ESCORT_LEAD_MINUTES = 25              # escorts run 13:35 onward, before the session
ONE_TO_ONE_FIRST = 870                # 14:30
ONE_TO_ONE_SPACING = 30

# Simulation assumption: minutes for one room delivery, one tray per trip.
ROOM_DELIVERY_STEPS = {
    "tray_pickup": 2,          # collect the plated tray and check it against the resident
    "walk_to_apartment": 4,    # kitchen to apartment, including the elevator
    "handoff_and_setup": 3,    # knock, greet, set the tray down and open it
    "return_to_kitchen": 4,    # walk back for the next tray
}
ROOM_DELIVERY_MINUTES = sum(ROOM_DELIVERY_STEPS.values())

# Simulation assumption: hands-on staff minutes per resident ticket.
WORK_MINUTES = {
    **{meal: 3 for meal in MEALS},
    **{meal + ROOM_SERVICE: ROOM_DELIVERY_MINUTES for meal in MEALS},
    ACTIVITY_ESCORT: 8,
    ACTIVITY_VISIT: 20,
}

MOBILITY_LEVELS = ("independent", "independent_with_walker", "needs_escort", "wheelchair_needs_escort")
_NEEDS_ESCORT = frozenset(("needs_escort", "wheelchair_needs_escort"))


def mobility_for(resident_index: int) -> str:
    """Synthetic mobility (planning only): 60% independent, 15% walker, 20% escort, 5% wheelchair."""
    # Spread through the building, not grouped by room number.
    slot = (resident_index - 1) % 20
    if slot in (3, 8, 13, 17):
        return "needs_escort"
    if slot == 11:
        return "wheelchair_needs_escort"
    if slot in (1, 6, 15):
        return "independent_with_walker"
    return "independent"


def needs_escort(resident_index: int) -> bool:
    return mobility_for(resident_index) in _NEEDS_ESCORT


def meal_location_for(resident_index: int) -> str:
    """Two residents in five (30 of 75) have meals delivered, spread through the building."""
    return "room_service_offer" if (resident_index - 1) % 5 in (1, 3) else "dining_room"


def activity_style_for(resident_index: int) -> str:
    """About one resident in seven prefers one-to-one visits to group activities."""
    return "one_to_one_offer" if (resident_index - 1) % 7 == 6 else "group_offer"


def attends_activity(resident_index: int, day_index: int) -> bool:
    """Deterministic attendance: three days in five per resident."""
    return (resident_index + day_index) % 5 < 3


def meal_routine(meal: str, resident_index: int) -> str:
    return meal + ROOM_SERVICE if meal_location_for(resident_index) == "room_service_offer" else meal


def is_meal(routine: str) -> bool:
    return routine in MEAL_ROUTINES


def meal_of(routine: str) -> Optional[str]:
    base = routine[: -len(ROOM_SERVICE)] if routine.endswith(ROOM_SERVICE) else routine
    return base if base in MEALS else None   # "housekeeping_room_service" is not a meal
