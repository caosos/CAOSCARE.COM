"""Agent Control Plane routes (docs/CAOSCARE_AGENT_CONTROL_PLANE.md §6).

Owner only. Every route returns 404 unless CAOSCARE_AGENT_CONTROL_ENABLED is
set (default off), so production / any host without local agents is
unaffected. No route accepts a shell command, path, session name or
executable: the browser names an agent_id; the delivery target comes from
agent_control.registry.BINDINGS.

Not mounted in server.py by this lane (shared file) - see the shared-core
request in the design doc.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from deps import require_owner
from agent_control import commands, discovery, registry
from agent_control.models import CommandInput


def enabled() -> bool:
    return os.environ.get("CAOSCARE_AGENT_CONTROL_ENABLED", "").strip().lower() in ("1", "true", "yes")


async def require_enabled_owner(request: Request) -> dict:
    if not enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return await require_owner(request)


router = APIRouter(prefix="/agent-control", tags=["agent-control"])


@router.get("/agents")
async def get_agents(user: dict = Depends(require_enabled_owner)):
    return {"agents": await registry.list_agents()}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, user: dict = Depends(require_enabled_owner)):
    await registry.ensure_seeded()
    agent = await registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return {"agent": await registry.with_status(agent),
            "commands": await commands.list_commands(agent_id, limit=20)}


@router.post("/commands")
async def post_command(data: CommandInput, user: dict = Depends(require_enabled_owner)):
    return await commands.issue(data, user)


@router.get("/commands")
async def get_commands(agent_id: str | None = None, user: dict = Depends(require_enabled_owner)):
    return {"commands": await commands.list_commands(agent_id)}


@router.get("/commands/{command_id}")
async def get_command(command_id: str, user: dict = Depends(require_enabled_owner)):
    cmd = await commands.get_command(command_id)
    if not cmd:
        raise HTTPException(status_code=404, detail="Unknown command")
    return {"command": cmd, "receipts": await commands.receipt_chain(cmd)}


@router.get("/sessions")
async def get_sessions(user: dict = Depends(require_enabled_owner)):
    """Read-only list of Claude Code sessions on this host. Does not bind
    them to agents and cannot send them anything."""
    return {"sessions": discovery.discover(), "read_only": True}
