"""Response-time thresholds for simulated tickets: one configurable table.

Every value here is a SIMULATION ASSUMPTION chosen to make the living
community's escalation behaviour believable.  None of it is a care standard,
a regulatory response time, or advice for a real facility.

Thresholds are simulated minutes on the facility clock:

* ``pickup_minutes``  - how long a ticket may wait unclaimed (from the
  simulated request minute) before its department lead is told;
* ``complete_minutes`` - how long a claimed ticket may stay in progress
  (from the simulated claim minute) before its department lead is told;
* ``clock`` - ``continuous`` counts every simulated minute; ``on_site``
  counts only while the department has someone physically on site, so a
  routine work order raised after hours is not "overdue" overnight while it
  waits, truthfully, for the department to open.  ``urgent`` always counts
  continuously.

Twice a threshold is escalation level 2 (see
:mod:`simulation.community_escalation`).

Only the ``normal`` row is authored per department; the other priorities
follow one rule so the table cannot drift: ``high`` = half of normal,
``urgent`` = half of high, ``low`` = twice normal (half-values round up).

An operator may override any cell with a JSON file named by the env var
``CAOSCARE_SIM_RESPONSE_THRESHOLDS``::

    {"maintenance": {"normal": {"pickup_minutes": 90, "complete_minutes": 300}}}

Unknown departments/priorities/keys and non-positive or absurd values are
refused (:class:`ResponseThresholdError`); a bad file never silently falls
back to defaults.
"""
import json
import math
import os
from typing import Optional

from simulation.community_staffing import DEPARTMENT_LABELS

THRESHOLDS_ENV = "CAOSCARE_SIM_RESPONSE_THRESHOLDS"
PRIORITIES = ("urgent", "high", "normal", "low")
CLOCKS = ("continuous", "on_site")
MAX_THRESHOLD_MINUTES = 7 * 1440
DEFAULT_PRIORITY = "normal"

# Simulation assumption: (pickup, complete) simulated minutes for a NORMAL
# ticket, and which clock the department's routine work is measured on.
# Nursing is staffed on site around the clock; every other department keeps
# operating hours (maintenance/RN after hours are on call, never on site).
_NORMAL = {
    "nursing": (20, 60, "continuous"),
    "kitchen": (15, 45, "on_site"),
    "housekeeping": (60, 240, "on_site"),
    "maintenance": (120, 480, "on_site"),
    "transportation": (120, 1440, "on_site"),
    "activities": (60, 240, "on_site"),
    "front_desk": (30, 90, "on_site"),
    "administration": (240, 1440, "on_site"),
}


class ResponseThresholdError(ValueError):
    """A threshold table or override is invalid; nothing was applied."""


def _half(value: int) -> int:
    return max(1, math.ceil(value / 2))


def default_table() -> dict:
    """The full department x priority table derived from the normal row."""
    table = {}
    for department, (pickup, complete, clock) in _NORMAL.items():
        high = (_half(pickup), _half(complete))
        rows = {
            "normal": (pickup, complete),
            "high": high,
            "urgent": (_half(high[0]), _half(high[1])),
            "low": (pickup * 2, complete * 2),
        }
        table[department] = {
            priority: {
                "pickup_minutes": rows[priority][0],
                "complete_minutes": rows[priority][1],
                "clock": "continuous" if priority == "urgent" else clock,
            }
            for priority in PRIORITIES
        }
    return table


def _minutes(value, label: str) -> int:
    if (not isinstance(value, int) or isinstance(value, bool)
            or not 1 <= value <= MAX_THRESHOLD_MINUTES):
        raise ResponseThresholdError(
            f"{label} must be an integer between 1 and {MAX_THRESHOLD_MINUTES} simulated minutes"
        )
    return value


def apply_overrides(table: dict, overrides) -> dict:
    """Return a new table with validated overrides merged cell by cell."""
    if not isinstance(overrides, dict):
        raise ResponseThresholdError("threshold overrides must be a JSON object")
    merged = {dept: {pri: dict(cell) for pri, cell in rows.items()} for dept, rows in table.items()}
    for department, rows in overrides.items():
        if department not in merged:
            raise ResponseThresholdError(f"unknown department in thresholds: {department!r}")
        if not isinstance(rows, dict):
            raise ResponseThresholdError(f"{department} thresholds must be an object")
        for priority, cell in rows.items():
            if priority not in PRIORITIES:
                raise ResponseThresholdError(f"unknown priority in thresholds: {priority!r}")
            if not isinstance(cell, dict) or not cell:
                raise ResponseThresholdError(f"{department}/{priority} must be a non-empty object")
            label = f"{department}/{priority}"
            for key, value in cell.items():
                if key in ("pickup_minutes", "complete_minutes"):
                    merged[department][priority][key] = _minutes(value, f"{label} {key}")
                elif key == "clock":
                    if value not in CLOCKS:
                        raise ResponseThresholdError(f"{label} clock must be one of {CLOCKS}")
                    merged[department][priority][key] = value
                else:
                    raise ResponseThresholdError(f"unknown threshold key {key!r} in {label}")
    return merged


def load_table(path: Optional[str] = None) -> dict:
    """Defaults, plus the override file at ``path`` (or the env var) if set."""
    path = path if path is not None else os.environ.get(THRESHOLDS_ENV, "").strip()
    table = default_table()
    if not path:
        return table
    try:
        with open(path, encoding="utf-8") as handle:
            overrides = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ResponseThresholdError(f"cannot read {THRESHOLDS_ENV} file: {type(exc).__name__}") from exc
    return apply_overrides(table, overrides)


_LOADED: dict = {}


def _active_table() -> dict:
    """Cached per configured path, so changing the env var takes effect."""
    path = os.environ.get(THRESHOLDS_ENV, "").strip()
    if path not in _LOADED:
        _LOADED.clear()
        _LOADED[path] = load_table(path)
    return _LOADED[path]


def thresholds_for(department: str, priority: Optional[str], table: Optional[dict] = None) -> Optional[dict]:
    """The threshold cell for one ticket, or None for an unknown department.

    An unknown/missing priority is measured as ``normal`` (never as urgent).
    """
    source = table if table is not None else _active_table()
    if department not in source:
        return None
    rows = source[department]
    return dict(rows.get(priority if priority in PRIORITIES else DEFAULT_PRIORITY))


if set(_NORMAL) != set(DEPARTMENT_LABELS):
    raise RuntimeError("every simulated department needs response thresholds")
