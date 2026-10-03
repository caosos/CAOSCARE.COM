"""Who or what is acting, and on what basis we know it (ENGINEERING_CONTRACT
decision 3; SIM-0 receipt law, 2026-10-02).

Every state change on a staff request goes through task_lifecycle.py with
one of these. It is built server-side only - from the authenticated user,
from the room a public request came in through, or by code that runs as a
named system process - never from a request body.

identity_basis says how much we actually know about the actor:
  authenticated            signed-in user (JWT/session)
  unverified_room_claim    a room screen / voice request; the room is known,
                           the speaker is not verified (Michael D3)
  synthetic                a demo/simulated identity, never a real person
  system                   a named CAOSCare process (e.g. demo_reset)
"""
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    actor_type: str                 # real-human / simulated-agent / system / external-provider
    identity_basis: str
    channel: str                    # staff_ui / aria_voice / kiosk_button / front_desk / system
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    simulated: bool = False

    def receipt_fields(self) -> dict:
        """The provenance fields a receipt carries for this actor."""
        d = asdict(self)
        return {
            "actor_id": d["actor_id"], "actor_type": d["actor_type"],
            "actor_name": d["name"], "actor_role": d["role"],
            "actor_department": d["department"], "channel": d["channel"],
            "identity_basis": d["identity_basis"], "simulated": d["simulated"],
        }


def actor_from_user(user: dict, channel: str = "staff_ui") -> ActorContext:
    """A signed-in user. Their identity is verified by authentication."""
    return ActorContext(
        actor_id=user["user_id"], actor_type="real-human", identity_basis="authenticated",
        channel=channel, name=user.get("name"), role=user.get("role"),
        department=user.get("department"),
    )


def actor_resident_claim(resident_id: Optional[str], room: Optional[str], channel: str,
                         synthetic: bool = False) -> ActorContext:
    """A request that came in through a room (voice or screen). The room is
    known; who spoke is a claim, not a verified identity. A synthetic (demo)
    resident is marked as such and is never presented as a real person."""
    return ActorContext(
        actor_id=resident_id or f"room:{room or 'unknown'}",
        actor_type="simulated-agent" if synthetic else "real-human",
        identity_basis="synthetic" if synthetic else "unverified_room_claim",
        channel=channel, role="resident", simulated=synthetic,
    )


def actor_system(name: str) -> ActorContext:
    """A named CAOSCare process acting on its own authority."""
    return ActorContext(actor_id=f"system:{name}", actor_type="system", identity_basis="system",
                        channel="system", name=name, role="system")
