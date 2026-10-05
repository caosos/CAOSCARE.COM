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


class IdentityConflict(Exception):
    """The simulated cast cannot be resolved without touching a real identity."""


def staff_actor() -> ActorContext:
    return ActorContext(actor_id=STAFF["actor_id"], actor_type="simulated-agent",
                        identity_basis="synthetic", channel="simulator", name=STAFF["name"],
                        role=STAFF["role"], department=STAFF["department"], simulated=True)


def staff_profile() -> dict:
    """The role/department the lifecycle authorizes the simulated staff
    member against. Built here, never read from a request or from db.users."""
    return {"user_id": STAFF["actor_id"], "name": STAFF["name"], "role": STAFF["role"],
            "department": STAFF["department"], "simulated": True}


def on_shift(actor_key: str, sim_minute: int) -> bool:
    if actor_key != STAFF["key"]:
        return True     # residents have no shift
    shift = STAFF["shift"]
    return shift["start_minute"] <= sim_minute < shift["end_minute"]


async def resolve_cast() -> dict:
    """The simulated actors for one run, checked against real identities."""
    in_room = await db.residents.find({"room": DEMO_ROOM}, {"_id": 0}).to_list(20)
    if not in_room:
        raise IdentityConflict(f"no resident in demo room {DEMO_ROOM}; run backend/scripts/setup_demo_room.py")
    real = [r["resident_id"] for r in in_room if not r.get("synthetic")]
    if real:
        raise IdentityConflict(f"demo room {DEMO_ROOM} holds a non-synthetic resident ({', '.join(real)})")
    if len(in_room) > 1:
        raise IdentityConflict(f"demo room {DEMO_ROOM} holds {len(in_room)} residents; expected one")
    if await db.users.find_one({"user_id": STAFF["actor_id"]}, {"_id": 1}):
        raise IdentityConflict(f"a real user record uses the simulated id {STAFF['actor_id']}")
    res = in_room[0]
    return {
        "resident": {"key": "resident", "actor_id": res["resident_id"], "name": res.get("name"),
                     "role": "resident", "room": DEMO_ROOM, "simulated": True},
        "maintenance_tech": {"key": STAFF["key"], "actor_id": STAFF["actor_id"], "name": STAFF["name"],
                             "role": STAFF["role"], "department": STAFF["department"],
                             "shift": STAFF["shift"], "simulated": True,
                             "filled_by": {"mode": "simulated"}},
    }
