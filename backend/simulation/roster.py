"""SIM-1 roster: the simulated actors the scheduler may act as.

Scope (Round 5 board, until Michael lifts the ENGINEERING_CONTRACT gate):
the demo room only. The simulated resident is the demo room's existing
synthetic resident (routes/demo_kiosk.py::ensure_demo_room, run by
backend/scripts/setup_demo_room.py), so the canonical request path
(task_lifecycle.simulation_marker) marks its work simulated. The simulator
creates no resident record of its own.

The simulated staff member has a stable `sim:` id, a role/department and a
shift on the simulation clock. It is NOT a User: it cannot sign in and never
appears in the staff roster. Its role/department here is the authority it
acts under in the canonical lifecycle (task_lifecycle.authority_for).

Every simulated ActorContext is actor_type=simulated-agent,
identity_basis=synthetic, simulated=True (simulator doc §4).
`resolve_cast()` refuses to run when the demo room is missing, holds a real
resident, or a real user record occupies the simulated staff id.
"""
from deps import db
from routes.actor_context import ActorContext
from routes.demo_kiosk import DEMO_ROOM

# The resident speaks to Aria in the demo room; the request bus builds its
# actor (actor_resident_claim, synthetic) from the synthetic resident record.
RESIDENT_CHANNEL = "aria_voice"

STAFF = {
    "key": "maintenance_tech", "actor_id": "sim:staff:maintenance-1",
    "name": "SIM - Maintenance Tech 1", "role": "staff", "department": "maintenance",
    "shift": {"start_minute": 0, "end_minute": 480},   # simulation-clock minutes
}
# SIM-4. Same `sim:` id and name demo continuity uses for its simulated
# nursing staff (demo_continuity.staff_for), so the demo room has one
# simulated nurse identity, not two.
NURSE = {
    "key": "nurse", "actor_id": "sim:staff:nursing-1",
    "name": "SIM - Nursing staff", "role": "staff", "department": "nursing",
    "shift": {"start_minute": 0, "end_minute": 480},
}
STAFF_ROLES = {STAFF["key"]: STAFF, NURSE["key"]: NURSE}


class IdentityConflict(Exception):
    """The simulated cast cannot be resolved without touching a real identity."""


def staff_actor(key: str = STAFF["key"]) -> ActorContext:
    s = STAFF_ROLES[key]
    return ActorContext(actor_id=s["actor_id"], actor_type="simulated-agent",
                        identity_basis="synthetic", channel="simulator", name=s["name"],
                        role=s["role"], department=s["department"], simulated=True)


def staff_profile(key: str = STAFF["key"]) -> dict:
    """The role/department the lifecycle authorizes the simulated staff
    member against. Built here, never read from a request or from db.users."""
    s = STAFF_ROLES[key]
    return {"user_id": s["actor_id"], "name": s["name"], "role": s["role"],
            "department": s["department"], "simulated": True}


def on_shift(actor_key: str, sim_minute: int) -> bool:
    if actor_key not in STAFF_ROLES:
        return True     # residents have no shift
    shift = STAFF_ROLES[actor_key]["shift"]
    return shift["start_minute"] <= sim_minute < shift["end_minute"]


async def resolve_cast(staff_keys: tuple = (STAFF["key"],)) -> dict:
    """The simulated actors for one run, checked against real identities.
    `staff_keys`: the staff roles the run's scenario needs."""
    in_room = await db.residents.find({"room": DEMO_ROOM}, {"_id": 0}).to_list(20)
    if not in_room:
        raise IdentityConflict(f"no resident in demo room {DEMO_ROOM}; run backend/scripts/setup_demo_room.py")
    real = [r["resident_id"] for r in in_room if not r.get("synthetic")]
    if real:
        raise IdentityConflict(f"demo room {DEMO_ROOM} holds a non-synthetic resident ({', '.join(real)})")
    if len(in_room) > 1:
        raise IdentityConflict(f"demo room {DEMO_ROOM} holds {len(in_room)} residents; expected one")
    res = in_room[0]
    cast = {"resident": {"key": "resident", "actor_id": res["resident_id"], "name": res.get("name"),
                         "role": "resident", "room": DEMO_ROOM, "simulated": True}}
    for key in staff_keys:
        s = STAFF_ROLES[key]
        if await db.users.find_one({"user_id": s["actor_id"]}, {"_id": 1}):
            raise IdentityConflict(f"a real user record uses the simulated id {s['actor_id']}")
        cast[key] = {"key": key, "actor_id": s["actor_id"], "name": s["name"], "role": s["role"],
                     "department": s["department"], "shift": s["shift"], "simulated": True,
                     "filled_by": {"mode": "simulated"}}
    return cast
