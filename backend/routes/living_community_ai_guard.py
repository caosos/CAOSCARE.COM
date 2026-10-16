"""Resolve living-community AI exclusions from server-owned resident truth."""
from living_community_boundary import (
    RESERVED_RESIDENT_IDS,
    is_living_community_resident,
)


RESIDENT_PROJECTION = {
    "_id": 0,
    "resident_id": 1,
    "simulation_scope": 1,
    "simulation_community_id": 1,
}


async def provider_excluded_for_resident(residents, resident_id: str | None) -> bool:
    """Fail closed for a reserved ID or either canonical marker on its row."""
    if resident_id in RESERVED_RESIDENT_IDS:
        return True
    if not resident_id:
        return False
    resident = await residents.find_one(
        {"resident_id": resident_id},
        RESIDENT_PROJECTION,
    )
    return bool(resident and is_living_community_resident(resident))
