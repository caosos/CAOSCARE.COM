"""Housekeeping: one scheduled full clean per occupied apartment per week (owner 2026-10-15).

Replaces the earlier daily full clean of every resident's apartment, which was a
modelling artifact.  Each housekeeper keeps a fixed territory; each occupied
apartment in it gets one full clean a week, on one of that housekeeper's working
days, spread evenly across those days.  A clean is taken only by its territory's
housekeeper - the normal apartments are never reshuffled day to day.

Workload follows the actual occupied apartments: Housekeeper 01's territory has
40 occupied apartments over 5 shifts (8 per shift), Housekeeper 02's has 30 over 5
(6 per shift); vacant apartments get no routine clean.  The 30-minute full clean is an
owner-approved simulation assumption (Michael 2026-10-15: a conservative baseline; staff
may do it in 15-20); the request times are simulation assumptions too.
"""
from functools import lru_cache
from typing import Optional

from simulation.community_blueprint import APARTMENTS, RESIDENTS
from simulation.community_staffing import _day_rota, weekday_of

FULL_CLEAN = "housekeeping_full_clean"
FULL_CLEAN_MINUTES = 30
FIRST_CLEAN_MINUTE = 8 * 60 + 15   # 08:15, after the 08:00 shift start
CLEAN_SPACING = 35                 # 30 minutes of work plus moving to the next apartment

# Fixed territories (apartment numbers, inclusive) per housekeeper.
TERRITORIES = {
    "sim:staff:housekeeping:housekeeper:01": (1, 40),
    "sim:staff:housekeeping:housekeeper:02": (41, 80),
}


def _number(room: str) -> int:
    return int(room.removeprefix("SIM-"))


def occupied_rooms(actor_id: str) -> tuple[str, ...]:
    first, last = TERRITORIES[actor_id]
    return tuple(a.room for a in APARTMENTS if a.target_occupied and first <= _number(a.room) <= last)


@lru_cache(maxsize=None)
def working_weekdays(actor_id: str) -> tuple[int, ...]:
    """The weekdays this housekeeper works, read from the rota (one source of truth)."""
    return tuple(sorted({weekday_of(day) for day in range(7)
                         for row in _day_rota(day) if row["actor_id"] == actor_id}))


@lru_cache(maxsize=None)
def weekly_plan() -> dict:
    """room -> (housekeeper, weekday, order within that day's cleans)."""
    plan = {}
    for actor_id in TERRITORIES:
        days = working_weekdays(actor_id)
        for index, room in enumerate(occupied_rooms(actor_id)):
            plan[room] = (actor_id, days[index % len(days)], index // len(days))
    return plan


def territory_of(room: str) -> Optional[str]:
    number = _number(room)
    return next((actor for actor, (first, last) in TERRITORIES.items() if first <= number <= last), None)


@lru_cache(maxsize=None)
def _resident_for_room() -> dict:
    """The resident a clean ticket is raised for: the apartment's first occupant."""
    out = {}
    for resident in RESIDENTS:
        out.setdefault(resident.room, resident)
    return out


def cleans_on(day_index: int, *, actor_id: Optional[str] = None) -> list[dict]:
    """Full cleans scheduled on one day, in order (optionally for one housekeeper)."""
    weekday = weekday_of(day_index)
    rows = [{"room": room, "housekeeper": owner, "order": order,
             "resident_key": _resident_for_room()[room].resident_key,
             "minute": FIRST_CLEAN_MINUTE + order * CLEAN_SPACING}
            for room, (owner, day, order) in weekly_plan().items()
            if day == weekday and (actor_id is None or owner == actor_id)]
    return sorted(rows, key=lambda row: (row["minute"], row["room"]))


def clean_workflow(day_index: int, resident_key: str) -> str:
    return f"day-{day_index:03d}:{resident_key}:{FULL_CLEAN}"


def is_clean_resident(resident_key: str, room: str) -> bool:
    """A clean is raised once per apartment, for its first occupant."""
    return _resident_for_room().get(room) is not None and _resident_for_room()[room].resident_key == resident_key


def required_worker(routine: str, workflow_id: str) -> Optional[str]:
    """Only the territory's housekeeper may take that apartment's full clean."""
    if routine != FULL_CLEAN:
        return None
    resident_key = workflow_id.split(":")[1]
    room = next((r.room for r in RESIDENTS if r.resident_key == resident_key), None)
    return territory_of(room) if room else None


@lru_cache(maxsize=None)
def _room_of() -> dict:
    return {resident.resident_key: resident.room for resident in RESIDENTS}


def clean_minute(resident_key: str, day_index: int) -> Optional[int]:
    """Minute this resident's apartment is cleaned on ``day_index``, or None (not today)."""
    room = _room_of().get(resident_key)
    if room is None or not is_clean_resident(resident_key, room) or room not in weekly_plan():
        return None
    _owner, weekday, order = weekly_plan()[room]
    return FIRST_CLEAN_MINUTE + order * CLEAN_SPACING if weekday == weekday_of(day_index) else None
