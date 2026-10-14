"""Owner/admin Live Operations dashboard reads (SIM-007A). Read-only."""

from fastapi import APIRouter, Depends, HTTPException

from deps import require_admin
from simulation.community_dashboard_detail import (
    DashboardNotFound, department_detail, resident_detail, worker_detail,
)
from simulation.community_dashboard_view import dashboard_snapshot
from simulation.community_ticket_view import ticket_detail


router = APIRouter(prefix="/simulator/community/dashboard", tags=["simulator"])


async def _detail(loader, key: str):
    try:
        return await loader(key)
    except DashboardNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
async def summary(user=Depends(require_admin)):
    return await dashboard_snapshot()


@router.get("/departments/{slug}")
async def department(slug: str, user=Depends(require_admin)):
    return await _detail(department_detail, slug)


@router.get("/workers/{actor_id}")
async def worker(actor_id: str, user=Depends(require_admin)):
    return await _detail(worker_detail, actor_id)


@router.get("/residents/{resident_id}")
async def resident(resident_id: str, user=Depends(require_admin)):
    return await _detail(resident_detail, resident_id)


@router.get("/tickets/{task_id}")
async def ticket(task_id: str, user=Depends(require_admin)):
    return await _detail(ticket_detail, task_id)
