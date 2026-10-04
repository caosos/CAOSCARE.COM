"""SIM-1 control surface: the smallest HTTP API that drives the simulator
(Start / Pause / Resume / Step / Stop, state, history). Owner/admin only.
The operator is the signed-in user; every control is receipted by
simulation/scheduler.py with that operator as actor. The Live Operations UI is SIM-2.
"""
from fastapi import APIRouter, Depends

from deps import require_admin
from simulation import scheduler
from routes.actor_context import actor_from_user

router = APIRouter(prefix="/simulator", tags=["simulator"])


def _operator(user: dict):
    return actor_from_user(user, channel="staff_ui"), f"admin_override:{user['role']}"


@router.get("/state")
async def simulator_state(user=Depends(require_admin)):
    return await scheduler.view()


@router.get("/runs/{run_id}/history")
async def simulator_history(run_id: str, user=Depends(require_admin)):
    return await scheduler.history(run_id)


@router.post("/start")
async def simulator_start(user=Depends(require_admin)):
    run = await scheduler.start(*_operator(user))
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
