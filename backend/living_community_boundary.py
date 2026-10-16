"""Shared read boundary for the server-owned living-community identities.

Bulk legacy/demo services must not infer eligibility from caller-controlled
payloads.  The canonical blueprint owns the reserved resident IDs and marker
values.  A partial marker is treated as malformed living-community state and
therefore remains protected until the simulator can reconcile it.
"""
from collections.abc import Iterable

from simulation.community_blueprint import COMMUNITY_ID, RESIDENTS, SIMULATION_SCOPE


RESERVED_RESIDENT_IDS = frozenset(recipe.resident_id for recipe in RESIDENTS)


def is_living_community_resident(resident: dict) -> bool:
    """Return true for canonical or partially malformed community rows."""
    return bool(
        resident.get("resident_id") in RESERVED_RESIDENT_IDS
        or resident.get("simulation_scope") == SIMULATION_SCOPE
        or resident.get("simulation_community_id") == COMMUNITY_ID
    )


def eligible_bulk_residents(residents: Iterable[dict]) -> list[dict]:
    """Keep real and legacy-demo residents outside the simulator boundary."""
    return [row for row in residents if not is_living_community_resident(row)]


def protected_resident_ids(residents: Iterable[dict]) -> frozenset[str]:
    """IDs bulk child-record operations must preserve and never target."""
    discovered = {
        row.get("resident_id")
        for row in residents
        if is_living_community_resident(row) and row.get("resident_id")
    }
    return RESERVED_RESIDENT_IDS | frozenset(discovered)
