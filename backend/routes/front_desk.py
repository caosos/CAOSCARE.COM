"""Front Desk workspace reads that have no other role-appropriate endpoint.

The department list itself (/departments) is admin-only facility setup, but
Front Desk needs the same live list to route a request it enters on a
resident's behalf. This returns exactly the active departments
(routes/departments.get_active_departments - the list Aria's request tools
are built from), read-only, so Front Desk routes to the same departments
Aria does and nothing is hardcoded in the UI.
"""
from fastapi import APIRouter, Depends

from deps import require_front_desk_or_admin
from routes.departments import get_active_departments

router = APIRouter(prefix="/front-desk", tags=["front-desk"])


@router.get("/request-categories")
async def request_categories(user=Depends(require_front_desk_or_admin)):
    return [{"slug": d["slug"], "label": d["label"]} for d in await get_active_departments()]
