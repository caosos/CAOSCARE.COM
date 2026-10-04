"""SIM-1 scheduler: one simulation run, its state, and its controls.

States: STOPPED -> (start) RUNNING <-> (pause/resume) PAUSED -> (stop) STOPPED.
Only RUNNING lets the scheduler loop act; only PAUSED allows a manual step.
STOPPED is final for a run: nothing is deleted, a new run is a new start.

Two receipt chains prove every simulated action:
- the run chain (correlation id = the run's start receipt): start, pause,
  resume, stop, and one receipt per scheduled step,
  each parented to the previous one.
  A step receipt names the canonical receipt that recorded the actual work
  in provider_refs.
- the request chain, written by the canonical services the step called
  (resident_requests / task_lifecycle), as for any real request.

Mongo is a standalone server (no transactions), as in task_lifecycle: the
canonical action is written first and the run's step receipt right after.
Controls and steps are serialised by one in-process lock; this backend runs
as a single process.
"""
import asyncio
import os
from typing import Optional

from fastapi import HTTPException

from deps import db
from models import now_utc, uid
from routes import notifications
from routes.actor_context import ActorContext, actor_system
from routes.receipts import create_receipt
from simulation import roster, scenario

RUNNING, PAUSED, STOPPED = "RUNNING", "PAUSED", "STOPPED"
ACTIVE = (RUNNING, PAUSED)
TICK_SECONDS = float(os.environ.get("SIM_TICK_SECONDS", "3"))

_lock = asyncio.Lock()
_loops: dict = {}


class SimulatorError(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


def _scheduler() -> ActorContext:
    return actor_system("simulator")


def _snap(run: dict) -> dict:
    return {"state": run["state"], "cursor": run["cursor"], "sim_minute": run["sim_minute"],
            "task_id": (run.get("workflow") or {}).get("task_id")}


def _next_state(run: dict) -> str:
    if run["state"] == STOPPED:
        return "stopped"
    step = scenario.describe(run["cursor"])
    nxt = f"step {step['index']}: {step['actor']} {step['action']} at minute {step['at']}" if step else "end"
    return f"{run['state'].lower()}; next {nxt}"


async def _record(run: dict, actor: ActorContext, authority: str, action_type: str, *, before: dict,
                  status: str = "completed", result: Optional[str] = None,
                  failure_reason: Optional[str] = None, refs: Optional[list] = None,
                  receipt_id: Optional[str] = None) -> dict:
    """Append one receipt to the run chain and point the run at it."""
    receipt = await create_receipt(
        action_type=action_type, related_object_type="simulation_run", related_object_id=run["run_id"],
        room=roster.DEMO_ROOM, status=status, result=result, failure_reason=failure_reason,
        receipt_id=receipt_id,
        provenance={**actor.receipt_fields(), "authority": authority,
                    "parent_receipt_id": run.get("last_receipt_id"),
                    "correlation_id": run.get("origin_receipt_id") or receipt_id,
                    "before_state": before, "after_state": _snap(run),
                    "result_label": "failed" if status == "failed" else "verified",
                    "provider_refs": list(refs or []), "next_state": _next_state(run)})
    run["last_receipt_id"] = receipt["receipt_id"]
    await db.sim_runs.update_one({"run_id": run["run_id"]}, {"$set": {
        "last_receipt_id": receipt["receipt_id"], "updated_at": now_utc().isoformat()}})
    return receipt


async def _save(run: dict, **fields) -> None:
    run.update(fields)
    await db.sim_runs.update_one({"run_id": run["run_id"]}, {"$set": {**fields, "updated_at": now_utc().isoformat()}})


async def active_run() -> Optional[dict]:
    return await db.sim_runs.find_one({"state": {"$in": list(ACTIVE)}}, {"_id": 0}, sort=[("created_at", -1)])


async def latest_run() -> Optional[dict]:
    return await db.sim_runs.find_one({}, {"_id": 0}, sort=[("created_at", -1)])


async def _refuse_start(operator: ActorContext, authority: str, reason: str) -> None:
    """A refused start is evidence too; no run is created."""
    await create_receipt(
        action_type="sim_run_start_refused", related_object_type="simulation_run",
        related_object_id="none", room=roster.DEMO_ROOM, status="failed", failure_reason=reason,
        provenance={**operator.receipt_fields(), "authority": authority, "result_label": "failed"})
    raise SimulatorError(409, f"Simulator not started: {reason}. The attempt was recorded.")


async def start(operator: ActorContext, authority: str) -> dict:
    async with _lock:
        if await active_run():
            raise SimulatorError(409, "A simulation run is already active; stop it first.")
        if notifications.RESEND_KEY:
            # SHARED CORE REQUEST: department notifications do not yet mark a
            # simulated request, so a live email provider would send real mail.
            await _refuse_start(operator, authority, "a live email provider is configured and "
                                "department notifications cannot yet mark simulated requests")
        try:
            cast = await roster.resolve_cast()
        except roster.IdentityConflict as e:
            await _refuse_start(operator, authority, f"identity conflict: {e}")
        now = now_utc().isoformat()
        run = {"run_id": uid("simrun"), "scenario": scenario.SCENARIO_ID, "state": RUNNING,
               "cursor": 0, "sim_minute": 0, "workflow": {}, "cast": cast, "started_by": operator.receipt_fields(),
               "origin_receipt_id": None, "last_receipt_id": None, "created_at": now, "updated_at": now}
        await db.sim_runs.insert_one(dict(run))
        origin_id = uid("rcpt")
        await _record(run, operator, authority, "sim_run_started", receipt_id=origin_id, status="created",
                      before={"state": STOPPED}, result=f"scenario {run['scenario']} started")
        await _save(run, origin_receipt_id=origin_id)
        return run


async def _control(operator: ActorContext, authority: str, *, frm: tuple, to: str, action_type: str) -> dict:
    async with _lock:
        run = await active_run()
        if not run or run["state"] not in frm:
            have = run["state"] if run else STOPPED
            raise SimulatorError(409, f"Cannot {action_type.removeprefix('sim_run_')} while {have}.")
        before = _snap(run)
        await _save(run, state=to)
        await _record(run, operator, authority, action_type, before=before, result=f"{before['state']} -> {to}")
        return run


async def pause(operator: ActorContext, authority: str) -> dict:
    return await _control(operator, authority, frm=(RUNNING,), to=PAUSED, action_type="sim_run_paused")


async def resume(operator: ActorContext, authority: str) -> dict:
    return await _control(operator, authority, frm=(PAUSED,), to=RUNNING, action_type="sim_run_resumed")


async def stop(operator: ActorContext, authority: str) -> dict:
    """Stops new simulated actions. History (run, tasks, receipts) is kept."""
    return await _control(operator, authority, frm=ACTIVE, to=STOPPED, action_type="sim_run_stopped")


async def step(operator: ActorContext, authority: str) -> dict:
    """Execute exactly one scheduled action. Only while PAUSED."""
    async with _lock:
        run = await active_run()
        if not run or run["state"] != PAUSED:
            raise SimulatorError(409, f"Step is only allowed while PAUSED (now {run['state'] if run else STOPPED}).")
        return await _execute_next(run, operator, authority)


async def tick(run_id: Optional[str] = None) -> Optional[dict]:
    """One scheduler beat: execute the next action if, and only if, the run
    is RUNNING. Returns the step outcome, or None when nothing was done."""
    async with _lock:
        run = await active_run()
        if not run or run["state"] != RUNNING or (run_id and run["run_id"] != run_id):
            return None
        return await _execute_next(run, _scheduler(), f"sim_run:{run['run_id']}")


async def _execute_next(run: dict, actor: ActorContext, authority: str) -> dict:
    before = _snap(run)
    nxt = scenario.describe(run["cursor"])
    if not nxt:
        await _save(run, state=STOPPED)
        await _record(run, actor, authority, "sim_run_completed", before=before, result="scenario finished")
        return {"executed": False, "run": run}
    if not roster.on_shift(nxt["actor"], nxt["at"]):
        await _save(run, state=PAUSED)
        await _record(run, actor, authority, "sim_step_refused", before=before, status="failed",
                      failure_reason=f"{nxt['actor']} is off shift at minute {nxt['at']}; run paused")
        return {"executed": False, "run": run}
    try:
        out = await scenario.execute(nxt, run.get("workflow") or {}, run["cast"])
    except Exception as e:     # a canonical refusal (HTTPException) or a guard
        reason = getattr(e, "detail", None) or str(e)
        await _save(run, state=PAUSED)
        await _record(run, actor, authority, "sim_step_failed", before=before, status="failed",
                      failure_reason=f"step {nxt['index']} {nxt['action']}: {reason}; run paused")
        return {"executed": False, "run": run, "error": str(reason)}
    await _save(run, cursor=run["cursor"] + 1, sim_minute=nxt["at"],
                workflow=out.get("workflow") or run.get("workflow") or {})
    receipt = await _record(
        run, actor, authority, "sim_step_executed", before=before,
        result=f"step {nxt['index']}: {nxt['actor']} {out['result']}",
        refs=[out["receipt_id"]] if out.get("receipt_id") else [])
    if run["cursor"] >= len(scenario.STEPS):
        done_before = _snap(run)
        await _save(run, state=STOPPED)
        await _record(run, _scheduler(), f"sim_run:{run['run_id']}", "sim_run_completed",
                      before=done_before, result="scenario finished")
    return {"executed": True, "run": run, "step": nxt, "step_receipt_id": receipt["receipt_id"],
            "canonical_receipt_id": out.get("receipt_id"), "task_id": out.get("task_id")}


async def _loop(run_id: str, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        await tick(run_id)
        run = await db.sim_runs.find_one({"run_id": run_id}, {"_id": 0, "state": 1})
        if not run or run["state"] != RUNNING:
            return    # paused or stopped: resume starts a new loop


def ensure_loop(run_id: str, interval: Optional[float] = None) -> None:
    task = _loops.get(run_id)
    if task and not task.done():
        return
    _loops[run_id] = asyncio.create_task(_loop(run_id, TICK_SECONDS if interval is None else interval))


def loop_alive(run_id: str) -> bool:
    task = _loops.get(run_id)
    return bool(task and not task.done())


async def view(run: Optional[dict] = None) -> dict:
    run = run or await latest_run()
    if not run:
        return {"state": STOPPED, "run_id": None, "steps_total": len(scenario.STEPS)}
    return {"state": run["state"], "run_id": run["run_id"], "scenario": run["scenario"],
            "cursor": run["cursor"], "sim_minute": run["sim_minute"],
            "next_step": scenario.describe(run["cursor"]) if run["state"] != STOPPED else None,
            "steps_total": len(scenario.STEPS), "workflow": run.get("workflow") or {},
            "origin_receipt_id": run.get("origin_receipt_id"), "last_receipt_id": run.get("last_receipt_id"),
            "started_by": run.get("started_by"), "loop_alive": loop_alive(run["run_id"]),
            "cast": run.get("cast")}


async def history(run_id: str) -> dict:
    """The run chain and the simulated request's own chain. Read-only."""
    run = await db.sim_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise SimulatorError(404, "Simulation run not found")
    q = {"correlation_id": run["origin_receipt_id"]}
    run_chain = await db.receipts.find(q, {"_id": 0}).sort("created_at", 1).to_list(500)
    wf = (run.get("workflow") or {}).get("origin_receipt_id")
    request_chain = await db.receipts.find({"correlation_id": wf}, {"_id": 0}).sort(
        "created_at", 1).to_list(500) if wf else []
    return {"run": run, "run_chain": run_chain, "request_chain": request_chain}
