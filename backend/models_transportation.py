"""Transportation resource-scheduling models (driver/vehicle/run) - kept out
of models.py (already over the 300-line cap) so this doesn't grow it.

Driver and vehicle are separate resources on purpose - a run references both
independently, so a driver can be paired with a different vehicle another
day rather than being permanently coupled to one. A TransportRun only ever
exists once actually confirmed against a real (driver, vehicle) pair or an
existing compatible run - there is no "pending run" state; a request with no
run yet is represented by the existing StaffTask having no transport_run_id
(same convention the old transport_slot_id used).

Capacity and buffer are configuration, not invented facts about any one
trip: TransportVehicle.capacity defaults to None (unconfigured) rather than
a guessed number, and TransportSchedulingConfig.buffer_minutes is an
explicit, admin-editable scheduling policy (the minimum gap assumed between
two runs on the same resource), not a claim about how long any specific
appointment takes.
"""
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field

from models import uid, now_utc

RunStatus = Literal["confirmed", "in_progress", "completed", "cancelled"]


class DriverHours(BaseModel):
    """A driver's regular working hours. work_days uses Python weekday
    numbers (0=Mon .. 6=Sun). Unset fields mean "not configured", which the
    engine treats as unrestricted - the admin screen shows "no hours set"
    rather than hiding that the schedule is open."""
    work_days: Optional[List[int]] = None
    shift_start: Optional[str] = None   # HH:MM 24h
    shift_end: Optional[str] = None     # HH:MM 24h


class TransportDriver(DriverHours):
    model_config = ConfigDict(extra="ignore")
    driver_id: str = Field(default_factory=lambda: uid("drv"))
    name: str
    is_flex: bool = False           # flex = never auto-booked; staff pick them explicitly
    enabled: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class TransportDriverCreate(DriverHours):
    name: str
    is_flex: bool = False
    enabled: bool = True


class TransportDriverUpdate(DriverHours):
    name: Optional[str] = None
    is_flex: Optional[bool] = None
    enabled: Optional[bool] = None


class TransportVehicle(BaseModel):
    model_config = ConfigDict(extra="ignore")
    vehicle_id: str = Field(default_factory=lambda: uid("veh"))
    name: str
    capacity: Optional[int] = None   # unset = not yet configured; treated as 1 (no sharing) until set
    enabled: bool = True
    created_at: datetime = Field(default_factory=now_utc)


class TransportVehicleCreate(BaseModel):
    name: str
    capacity: Optional[int] = None
    enabled: bool = True


class TransportVehicleUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    enabled: Optional[bool] = None


class TransportRun(BaseModel):
    """One real, resource-committed trip. depart_time is when the resource
    leaves (pickup); return_time is only set when actually known/estimated -
    left unset rather than guessed, per the no-invented-duration rule."""
    model_config = ConfigDict(extra="ignore")
    run_id: str = Field(default_factory=lambda: uid("run"))
    date: str                                    # YYYY-MM-DD
    depart_time: str                              # HH:MM 24h
    return_time: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    destination: Optional[str] = None             # from the first rider's request purpose
    resident_task_ids: List[str] = []              # StaffTask ids riding this run
    status: RunStatus = "confirmed"
    notes: Optional[str] = None
    departed_at: Optional[str] = None
    completed_at: Optional[str] = None
    closed_by_name: Optional[str] = None           # who marked it departed/completed
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TransportSchedulingConfig(BaseModel):
    """Singleton policy doc (one row, id fixed). buffer_minutes is a
    scheduling-policy knob (minimum gap kept between runs on the same
    resource), never presented as a fact about a specific trip's length."""
    model_config = ConfigDict(extra="ignore")
    config_id: Literal["transport_scheduling"] = "transport_scheduling"
    buffer_minutes: int = 30
    updated_at: datetime = Field(default_factory=now_utc)


class TransportSchedulingConfigUpdate(BaseModel):
    buffer_minutes: int
