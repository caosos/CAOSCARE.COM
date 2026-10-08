"""Which resident a room screen speaks for.

By default a kiosk's resident is whoever is registered in the kiosk's room.
A kiosk may instead be PINNED to one resident (`Kiosk.resident_id`, admin-set):
then that resident is the identity for the screen, and the room string is
used only for devices and the room's session lease. A pinned resident that no
longer exists resolves to nobody - never silently back to the room's resident.
"""
from typing import Optional

from deps import db


async def resident_for_kiosk(kiosk: dict, projection: Optional[dict] = None) -> Optional[dict]:
    proj = {"_id": 0, **(projection or {})}
    pinned = kiosk.get("resident_id")
    if pinned:
        return await db.residents.find_one({"resident_id": pinned}, proj)
    if not kiosk.get("room"):
        return None
    return await db.residents.find_one({"room": kiosk["room"]}, proj)
