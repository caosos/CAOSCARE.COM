"""Simulator control surface: the smallest HTTP API that drives the
simulator (Start / Pause / Resume / Step / Stop, state, history; SIM-3 role
assignment). Owner/admin only.
The operator is the signed-in user; every control is receipted by
simulation/scheduler.py with that operator as actor. The Live Operations UI is SIM-2.
"""
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import require_admin
from simulation import scenario, scheduler, staffing
from routes.actor_context import actor_from_user

router = APIRouter(prefix="/simulator", tags=["simulator"])


class RoleFill(BaseModel):
    mode: str                       # simulated / real / unassigned
    user_id: Optional[str] = None   # the real staff account, when mode is "real"


class StartBody(BaseModel):
    roles: Dict[str, RoleFill] = {}
    scenario: Optional[str] = None  # scenario id (GET /simulator/scenarios); default sink_leak


def _operator(user: dict):
    return actor_from_user(user, channel="staff_ui"), f"admin_override:{user['role']}"


@router.get("/state")
async def simulator_state(user=Depends(require_admin)):
    return await scheduler.view()


@router.get("/scenarios")
async def simulator_scenarios(user=Depends(require_admin)):
    """The scenarios the simulator can run. Read-only."""
    return scenario.catalog()


@router.get("/runs/{run_id}/history")
async def simulator_history(run_id: str, user=Depends(require_admin)):
    return await scheduler.history(run_id)


@router.post("/start")
async def simulator_start(body: Optional[StartBody] = None, user=Depends(require_admin)):
    roles = {k: v.model_dump() for k, v in (body.roles if body else {}).items()}
    run = await scheduler.start(*_operator(user), roles=roles, scenario_id=body.scenario if body else None)
    scheduler.ensure_loop(run["run_id"])
    return await scheduler.view(run)


@router.post("/pause")
async def simulator_pause(user=Depends(require_admin)):
    return await scheduler.view(await scheduler.pause(*_operator(user)))


@router.post("/resume")
async def simulator_resume(user=Depends(require_admin)):
    run = await scheduler.resume(*_operator(user))
    scheduler.ensure_loop(run["run_id"])
    return await scheduler.view(run)


@router.post("/step")
async def simulator_step(user=Depends(require_admin)):
    out = await scheduler.step(*_operator(user))
    return {**await scheduler.view(out["run"]),
            "step_result": {k: v for k, v in out.items() if k != "run"}}


@router.post("/stop")
async def simulator_stop(user=Depends(require_admin)):
    return await scheduler.view(await scheduler.stop(*_operator(user)))


@router.post("/roles/{role_key}")
async def simulator_assign_role(role_key: str, body: RoleFill, user=Depends(require_admin)):
    """SIM-3: hand a staff role to a real signed-in user, return it to its
    simulated actor, or leave it unassigned. The real user then works the
    request through the normal staff UI; the simulator never acts for them."""
    run = await scheduler.assign_role(*_operator(user), role_key, body.mode, body.user_id)
    return await scheduler.view(run)


@router.get("/roles/{role_key}/candidates")
async def simulator_role_candidates(role_key: str, user=Depends(require_admin)):
    """Real staff accounts that act for the role's department. Read-only."""
    run = await scheduler.active_run() or await scheduler.latest_run()
    role = ((run or {}).get("cast") or {}).get(role_key)
    if not role or role.get("role") == "resident":
        raise scheduler.SimulatorError(404, f"No staff role {role_key}")
    return await staffing.candidates(role)
