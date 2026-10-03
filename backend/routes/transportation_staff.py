"""Staff-entered transportation - Front Desk (or Admin) booking, changing and
cancelling a ride on a resident's behalf (phone call, walk-up, a note from
family). Authenticated, and recorded as source "front_desk" with the staff
member as requester, so the history shows who did it.

Every action delegates to the same core functions Aria's resident path
uses (routes/transportation.py: submit_transport_request, change_request,
cancel_request), which in turn use the one booking engine - a staff-entered
ride and a resident-requested one can never disagree about "booked".

Staff can additionally name a destination (the only way a ride can share a
run with another resident) and pick a specific driver/vehicle.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, require_front_desk_or_admin
from models import TaskPriority
from routes.transportation import (
    TransportRequestInput, TransportChangeInput, submit_transport_request, change_request, cancel_request,
)
from transportation_engine import to_minutes

router = APIRouter(prefix="/transportation/staff", tags=["transportation-staff"])


class ResourceChoice(BaseModel):
    start_time: Optional[str] = None     # exact HH:MM pickup time staff commit to
    destination: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None


class StaffRequestInput(ResourceChoice):
    resident_id: str
    purpose: str
    requested_for_date: str
    requested_for_time_label: Optional[str] = None
    priority: TaskPriority = "normal"


class StaffChangeInput(ResourceChoice):
    requested_for_date: str
    requested_for_time_label: Optional[str] = None


class StaffCancelInput(BaseModel):
    reason: Optional[str] = None


def _check_time(start_time: Optional[str]) -> None:
    if start_time and to_minutes(start_time) is None:
        raise HTTPException(status_code=422, detail="start_time must be HH:MM 24h")


@router.post("/request")
async def staff_create_request(data: StaffRequestInput, user=Depends(require_front_desk_or_admin)):
    _check_time(data.start_time)
    resident = await db.residents.find_one({"resident_id": data.resident_id}, {"_id": 0, "room": 1})
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    req = TransportRequestInput(
        resident_id=data.resident_id, room=resident.get("room"), purpose=data.purpose,
        requested_for_date=data.requested_for_date, requested_for_time_label=data.requested_for_time_label,
        start_time=data.start_time, priority=data.priority, source="front_desk",
    )
    return await submit_transport_request(
        req, actor=user, destination=data.destination,
        driver_id=data.driver_id, vehicle_id=data.vehicle_id,
    )


@router.post("/request/{task_id}/change")
async def staff_change_request(task_id: str, data: StaffChangeInput, user=Depends(require_front_desk_or_admin)):
    _check_time(data.start_time)
    change = TransportChangeInput(
        requested_for_date=data.requested_for_date,
        requested_for_time_label=data.requested_for_time_label, start_time=data.start_time,
    )
    return await change_request(
        task_id, change, source="front_desk", actor=user,
        destination=data.destination, driver_id=data.driver_id, vehicle_id=data.vehicle_id,
    )


@router.post("/request/{task_id}/cancel")
async def staff_cancel_request(task_id: str, data: StaffCancelInput = StaffCancelInput(), user=Depends(require_front_desk_or_admin)):
    return await cancel_request(task_id, source="front_desk", actor=user, reason=data.reason)
