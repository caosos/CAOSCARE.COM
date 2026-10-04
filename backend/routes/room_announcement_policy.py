"""Who may make a room speak, and where a room announcement may go.

Uses the existing authority rules only: signed-in roles (deps / User.role),
department scope (staff_scope.acts_for), the Kiosk room mapping and its
voice_device_ids, and the facility record. Nothing here is a second
authorization or device registry.

Allowed (slice 1, Michael 2026-10-04): owner, admin and front desk staff;
department staff for a request or event in their own department's room;
named CAOSCare system workflows with a traceable origin object.
Not allowed: family, anonymous callers, unverified external agents,
speaker recognition. No quiet-hours or emergency-announcement policy exists
in CAOSCare, so none is applied: "routine" and "important" are accepted,
"emergency" is refused until such a policy is defined.
"""
from datetime import datetime, timezone
from typing import Optional

from deps import db
from routes.realtime_facility import get_active_facility
from routes.staff_scope import acts_for

DIRECT_ROLES = ("owner", "admin", "front_desk")
# Named in-process workflows allowed to announce; each must pass an origin object.
SYSTEM_WORKFLOWS = frozenset({"request_status_update", "transport_update", "staff_dispatch_update"})
SUPPORTED_PRIORITIES = ("routine", "important")


class Refusal(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


async def resolve_room(community_id: str, room: str) -> dict:
    """The room's voice endpoint, community and resident - or a Refusal."""
    kiosks = await db.kiosks.find({"room": room}, {"_id": 0}).to_list(10)
    if not kiosks:
        raise Refusal("unknown_room", f"no room endpoint for room {room!r}")
    active = (await get_active_facility() or {}).get("facility_id")
    in_community = [k for k in kiosks if (k.get("facility_id") or active) == community_id]
    if not in_community:
        raise Refusal("cross_community", "room is not in the requested community")
    with_voice = [k for k in in_community if k.get("voice_device_ids")]
    if not with_voice:
        raise Refusal("room_disconnected", "room has no mapped voice endpoint")
    if len(with_voice) > 1:
        raise Refusal("ambiguous_room", "room has more than one voice endpoint")
    kiosk = with_voice[0]
    ids = kiosk["voice_device_ids"]
    target = next((d for d in ids if d.startswith("assist_satellite.")), ids[0])
    resident = await db.residents.find_one({"room": room}, {"_id": 0, "resident_id": 1})
    return {"kiosk_id": kiosk["kiosk_id"], "target_device_id": target,
            "resident_id": (resident or {}).get("resident_id")}


async def origin_object(origin_type: str, origin_id: Optional[str], room: str) -> Optional[dict]:
    """The task/alert an announcement is about; it must be in the same room."""
    if origin_type == "staff_direct":
        return None
    if not origin_id:
        raise Refusal("missing_origin", f"{origin_type} announcements need an origin id")
    if origin_type == "task":
        obj = await db.staff_tasks.find_one({"task_id": origin_id}, {"_id": 0})
    elif origin_type == "alert":
        obj = await db.alerts.find_one({"alert_id": origin_id}, {"_id": 0})
    else:  # system_workflow: the workflow names its task or alert
        obj = (await db.staff_tasks.find_one({"task_id": origin_id}, {"_id": 0})
               or await db.alerts.find_one({"alert_id": origin_id}, {"_id": 0}))
    if not obj:
        raise Refusal("unknown_origin", f"{origin_type} {origin_id} not found")
    if obj.get("room") != room:
        raise Refusal("origin_room_mismatch", "origin object belongs to another room")
    return obj


def authorize(actor, user: Optional[dict], req, origin: Optional[dict]) -> dict:
    """The authority decision, or a Refusal. `actor` is an ActorContext."""
    if req.priority not in SUPPORTED_PRIORITIES:
        raise Refusal("no_emergency_announcement_policy",
                      "CAOSCare has no emergency announcement policy yet")
    if req.scheduled_for and req.scheduled_for > datetime.now(timezone.utc):
        raise Refusal("scheduling_not_available", "scheduled announcements are not supported yet")
    if actor.identity_basis == "system":
        if actor.name not in SYSTEM_WORKFLOWS:
            raise Refusal("unknown_system_workflow", str(actor.name))
        if req.origin_type == "staff_direct" or origin is None:
            raise Refusal("missing_origin", "system announcements need an origin object")
        return {"authority": f"system_workflow:{actor.name}", "rule": "named workflow with origin"}
    if actor.identity_basis != "authenticated" or not user:
        raise Refusal("unauthenticated", "a signed-in staff actor is required")
    role = user.get("role")
    if role in DIRECT_ROLES:
        return {"authority": f"role:{role}", "rule": "staff role may announce to a room"}
    if role == "staff" and origin is not None:
        dept = origin.get("visibility_role") or origin.get("category")
        if req.origin_type == "task" and acts_for(user, dept):
            return {"authority": f"acts_for:{dept}", "rule": "department staff, own request's room"}
    raise Refusal("not_authorized", f"role {role!r} may not announce this")
