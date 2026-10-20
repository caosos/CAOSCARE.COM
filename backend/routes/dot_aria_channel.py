"""Default-off Home Assistant MCP channel for Michael's Dot Aria.

Home Assistant scripts call these narrow endpoints; CAOSCare remains the
authority for the one approved profile, published content, request routing,
deduplication, status and receipts. The credential cannot call other routes.
"""
import hashlib
import hmac
import ipaddress
import os
from datetime import date as Date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from deps import db
from routes.actor_context import actor_service_delegate
from routes.departments import get_active_departments
from routes.dot_aria_operations import claim, complete, mark_failed_unknown, request_fingerprint
from routes.menu import public_today as public_menu
from routes.realtime_facility import today_facility_date
from routes.resident_requests import (
    ResidentRequestInput,
    create_resident_request,
    resident_request_status_by_id,
)
from routes.resident_request_lookup import MAX_OFFSET, find_resident_requests
from routes.schedule import public_today as public_schedule

router = APIRouter(prefix="/dot-aria", tags=["dot-aria"])
APPROVED_ROOM = "214"


def _configured_hosts() -> set[str]:
    return {h.strip() for h in os.environ.get("CAOSCARE_DOT_ARIA_ALLOWED_HOSTS", "").split(",") if h.strip()}


async def require_dot_aria(request: Request) -> dict:
    expected = os.environ.get("CAOSCARE_DOT_ARIA_TOKEN_SHA256", "").strip().lower()
    owner_id = os.environ.get("CAOSCARE_DOT_ARIA_OWNER_USER_ID", "").strip()
    profile_id = os.environ.get("CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID", "").strip()
    hosts = _configured_hosts()
    if len(expected) != 64 or not owner_id or not profile_id or not hosts:
        raise HTTPException(503, "Dot Aria channel is disabled")
    host = request.client.host if request.client else ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise HTTPException(403, "Dot Aria source is not allowed")
    if host not in hosts:
        raise HTTPException(403, "Dot Aria source is not allowed")
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    actual = hashlib.sha256(token.encode()).hexdigest()
    if not token or not hmac.compare_digest(actual, expected):
        raise HTTPException(401, "Invalid Dot Aria credential")
    owner = await db.users.find_one({"user_id": owner_id, "role": "owner"}, {"_id": 0, "password_hash": 0})
    if not owner:
        raise HTTPException(503, "Configured Dot Aria owner is unavailable")
    await _approved_profile()
    return owner


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DateLookup(StrictInput):
    date: Optional[Date] = None


class MenuLookup(DateLookup):
    meal_period: Optional[Literal["breakfast", "lunch", "dinner"]] = None


class RequestCreate(StrictInput):
    operation_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]+$")
    category: str = Field(min_length=1, max_length=60)
    summary: str = Field(min_length=1, max_length=500)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class RequestStatus(StrictInput):
    request_id: str = Field(min_length=1, max_length=100)


class RequestLookup(StrictInput):
    department: Optional[str] = Field(default=None, min_length=1, max_length=60)
    issue: Optional[str] = Field(default=None, min_length=1, max_length=120)
    scope: Literal["recent", "open"] = "recent"
    limit: int = Field(default=10, ge=1, le=20, strict=True)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET, strict=True)


async def _approved_profile() -> dict:
    """Resolve only the server-configured profile; speech cannot select it."""
    resident_id = os.environ.get("CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID", "").strip()
    resident = await db.residents.find_one(
        {"resident_id": resident_id},
        {"_id": 0, "resident_id": 1, "name": 1, "preferred_name": 1, "room": 1, "synthetic": 1},
    )
    if not resident:
        raise HTTPException(503, "Configured Dot Aria test profile is unavailable")
    room = str(resident.get("room") or "").strip()
    if room == f"{APPROVED_ROOM}-HOME":
        # Preserve the established test identity's separate room label. Only
        # an existing server-owned physical-room pin authorizes that mapping;
        # a spoken room/name or the label alone cannot grant access.
        pin = await db.kiosks.find_one(
            {"room": APPROVED_ROOM, "resident_id": resident_id},
            {"_id": 0, "kiosk_id": 1},
        )
        if not pin:
            raise HTTPException(503, "Configured Dot Aria home-test profile is not pinned to Room 214")
    elif room != APPROVED_ROOM:
        raise HTTPException(503, "Configured Dot Aria profile is outside the approved Room 214 scope")
    return resident


def _profile_view(resident: dict) -> dict:
    return {k: resident.get(k) for k in ("resident_id", "name", "preferred_name", "room")}


@router.get("/capabilities")
async def capabilities(owner=Depends(require_dot_aria)):
    return {"ok": True, "channel": "home_assistant_mcp", "profile_scope": "configured_one_profile", "tools": [
        "caoscare_get_my_profile", "caoscare_get_departments", "caoscare_get_menu",
        "caoscare_get_schedule", "caoscare_make_request", "caoscare_check_request_status",
        "caoscare_find_my_requests",
    ]}


@router.get("/profile")
async def profile(owner=Depends(require_dot_aria)):
    return {"ok": True, "profile": _profile_view(await _approved_profile())}


@router.post("/menu")
async def menu(data: MenuLookup, owner=Depends(require_dot_aria)):
    day = data.date.isoformat() if data.date else None
    items = await public_menu(date=day, meal_period=data.meal_period)
    return {"ok": True, "date": day or today_facility_date(), "meal_period": data.meal_period, "items": items}


@router.post("/schedule")
async def schedule(data: DateLookup, owner=Depends(require_dot_aria)):
    day = data.date.isoformat() if data.date else None
    items = await public_schedule(date=day, category=None)
    return {"ok": True, "date": day or today_facility_date(), "items": items}


@router.get("/departments")
async def departments(owner=Depends(require_dot_aria)):
    return {"ok": True, "departments": await get_active_departments()}


@router.post("/requests")
async def make_request(data: RequestCreate, owner=Depends(require_dot_aria)):
    resident = await _approved_profile()
    fingerprint = request_fingerprint(
        resident_id=resident["resident_id"], room=APPROVED_ROOM, category=data.category,
        summary=data.summary, priority=data.priority,
    )
    replay = await claim(data.operation_id, fingerprint)
    if replay is not None:
        return replay
    actor = actor_service_delegate(owner, "Dot Aria via Home Assistant", "dot_aria")
    try:
        result = await create_resident_request(
            ResidentRequestInput(
                category=data.category,
                resident_id=resident["resident_id"],
                room=APPROVED_ROOM,
                summary=data.summary,
                priority=data.priority,
                source="dot_aria",
            ),
            trusted_actor=actor,
            trusted_authority="owner_delegated:home_assistant_mcp:room_214",
            trusted_operation_id=data.operation_id,
        )
    except Exception as exc:
        await mark_failed_unknown(data.operation_id, type(exc).__name__)
        raise
    duplicate = bool(result.get("duplicate"))
    status = result.get("status")
    response = {
        "ok": True,
        "accepted": True,
        "outcome": "existing_request_updated" if duplicate else "request_created",
        "request_id": result.get("task_id"),
        "task_id": result.get("task_id"),
        "receipt_id": result.get("receipt_id"),
        "status": status,
        "lifecycle": result.get("lifecycle"),
        "duplicate": duplicate,
        "delivery": result.get("delivery_evidence"),
        "operation_id": data.operation_id,
        "idempotent_replay": False,
        "message": f"Request accepted with status {status}. This does not mean service has started or completed.",
    }
    await complete(data.operation_id, response)
    return response


@router.post("/requests/status")
async def request_status(data: RequestStatus, owner=Depends(require_dot_aria)):
    resident = await _approved_profile()
    result = await resident_request_status_by_id(resident["resident_id"], data.request_id)
    return {"ok": True, "request_id": data.request_id, "request": result}


@router.post("/requests/find")
async def find_requests(data: RequestLookup, owner=Depends(require_dot_aria)):
    resident = await _approved_profile()
    return await find_resident_requests(resident["resident_id"], **data.model_dump())
