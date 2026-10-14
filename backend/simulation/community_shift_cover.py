"""A real staff member covers a simulated worker's shift.

While a cover is active, the simulation does not act for that worker: their
planned claims and completions are recorded as ``cancelled`` executor
receipts naming who covers the shift, and the tickets stay in the
department's canonical queue for the person covering to work (owner/admin
Work-as or a department account).  Ending the cover hands the worker back to
the simulation.  Start and end are receipted with the real person as actor.
"""
from typing import Optional

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_runtime_staffing import staffing_at

COLLECTION = "sim_shift_covers"


class ShiftCoverError(RuntimeError):
    """The cover request cannot be honoured truthfully."""


def _covers(store):
    return getattr(store, COLLECTION)


async def active_cover(store, run_id: str, worker_actor_id: str) -> Optional[dict]:
    return await _covers(store).find_one(
        {"run_id": run_id, "worker_actor_id": worker_actor_id, "ended_at_sim_minute": None}, {"_id": 0})


async def active_covers(store, run_id: str) -> list[dict]:
    return await _covers(store).find(
        {"run_id": run_id, "ended_at_sim_minute": None}, {"_id": 0}).to_list(None)


async def _run(store, run_id: str) -> dict:
    run = await store.sim_runs.find_one(
        {"run_id": run_id, "simulation_scope": SIMULATION_SCOPE}, {"_id": 0})
    if not run or run.get("state") not in ("RUNNING", "PAUSED"):
        raise ShiftCoverError("no running or paused living-community run with that id")
    return run


async def _receipt(write, *, action_type: str, cover: dict, actor, run: dict, result: str) -> dict:
    return await write(
        action_type=action_type, related_object_type="sim_shift_cover",
        related_object_id=cover["cover_id"], source="staff",
        assigned_role=cover["department"], assigned_user=actor.actor_id,
        status="completed", result=result,
        provenance={
            **actor.receipt_fields(), "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID, "simulation_run_id": run["run_id"],
            "authority": f"admin_override:{actor.role}", "result_label": "verified",
            "after_state": {k: cover.get(k) for k in (
                "worker_actor_id", "covered_by_actor_id", "started_at_sim_minute",
                "ended_at_sim_minute")},
            "provider_refs": [],
        },
    )


async def start_cover(store, write, *, run_id: str, worker_actor_id: str, actor) -> dict:
    """Cover an on-site simulated worker's shift from the run's current minute."""
    run = await _run(store, run_id)
    minute = run["sim_minute"]
    worker = next((row for row in staffing_at(minute)["workers"]
                   if row["actor_id"] == worker_actor_id), None)
    if worker is None:
        raise ShiftCoverError(f"{worker_actor_id} is not on site at the run's current time")
    if await active_cover(store, run_id, worker_actor_id):
        raise ShiftCoverError(f"{worker['name']}'s shift is already covered")
    cover = {
        "cover_id": f"cover:{run_id}:{worker_actor_id}:{minute}",
        "run_id": run_id, "worker_actor_id": worker_actor_id, "worker_name": worker["name"],
        "department": worker["department"], "job_role": worker["job_role"], "shift": worker["shift"],
        "covered_by_actor_id": actor.actor_id, "covered_by_name": actor.name,
        "started_at_sim_minute": minute, "ended_at_sim_minute": None,
    }
    await _covers(store).insert_one(dict(cover))
    receipt = await _receipt(write, action_type="sim_shift_cover_started", cover=cover, actor=actor,
                             run=run, result=f"{actor.name} is covering {worker['name']}'s shift.")
    await _covers(store).update_one({"cover_id": cover["cover_id"]},
                                    {"$set": {"start_receipt_id": receipt["receipt_id"]}})
    return {**cover, "start_receipt_id": receipt["receipt_id"]}


async def end_cover(store, write, *, run_id: str, worker_actor_id: str, actor) -> dict:
    run = await _run(store, run_id)
    cover = await active_cover(store, run_id, worker_actor_id)
    if cover is None:
        raise ShiftCoverError("that shift is not being covered")
    cover["ended_at_sim_minute"] = run["sim_minute"]
    receipt = await _receipt(write, action_type="sim_shift_cover_ended", cover=cover, actor=actor,
                             run=run, result=f"{actor.name} handed {cover['worker_name']}'s shift back.")
    await _covers(store).update_one(
        {"cover_id": cover["cover_id"], "ended_at_sim_minute": None},
        {"$set": {"ended_at_sim_minute": cover["ended_at_sim_minute"],
                  "end_receipt_id": receipt["receipt_id"]}})
    return {**cover, "end_receipt_id": receipt["receipt_id"]}


def cover_result(event, cover: dict) -> str:
    return (f"{event.actor_name} did not {event.task_phase} this ticket: "
            f"{cover['covered_by_name']} is covering the shift; the ticket stays in the queue for them.")
