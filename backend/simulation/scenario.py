"""SIM-1 scenario: a fixed, deterministic list of simulated actions, each
executed through a canonical CAOSCare service. Nothing here writes a task
or a task receipt itself.

Scenario "sink_leak" (SIM-1 acceptance, docs/CAOSCARE_OPERATIONS_SIMULATOR.md §9):
  minute 0   simulated resident reports a leaking sink
             -> resident_requests.create_resident_request (normal request bus)
  minute 5   simulated maintenance tech acknowledges -> task_actions.acknowledge
  minute 10  starts (claims it)                      -> task_actions.start
  minute 25  adds a progress note                    -> task_actions.add_note
  minute 40  completes                               -> task_actions.complete
  minute 50  the resident asks how it went  -> resident_requests history read
             (the answer comes from the canonical state, whoever did the work)

SIM-4 adds scenario "nursing_assist": the same steps for the Nursing
department ("I need help going to the bathroom." -> nursing request ->
simulated nurse or a real nurse -> resident checks). One registry
(SCENARIOS); a run records its scenario id and every step reads it.

SIM-3: a staff step only runs here when the role is held by its simulated
actor (staffing.fill_of). A role held by a real user is never acted for.

Each step returns the canonical receipt that recorded it; the scheduler
links that receipt to the simulation run (scheduler.py).
"""
from typing import Optional

from routes import task_actions
from routes.resident_requests import ResidentRequestInput, create_resident_request
from routes.resident_requests import resident_request_history
from routes.task_lifecycle import chain_head, load
from simulation import roster, staffing

SCENARIO_ID = "sink_leak"       # the default scenario
SINK_WORDS = "The bathroom sink keeps leaking."
NURSING_WORDS = "I need help going to the bathroom."

STEPS = [
    {"at": 0, "actor": "resident", "action": "raise_request"},
    {"at": 5, "actor": "maintenance_tech", "action": "acknowledge"},
    {"at": 10, "actor": "maintenance_tech", "action": "start"},
    {"at": 25, "actor": "maintenance_tech", "action": "note",
     "text": "Simulated: worn washer under the sink; replacing it."},
    {"at": 40, "actor": "maintenance_tech", "action": "complete",
     "text": "Simulated: replaced the washer, no more leaking."},
    {"at": 50, "actor": "resident", "action": "check_status"},
]

NURSING_STEPS = [
    {"at": 0, "actor": "resident", "action": "raise_request"},
    {"at": 2, "actor": "nurse", "action": "acknowledge"},
    {"at": 3, "actor": "nurse", "action": "start"},
    {"at": 8, "actor": "nurse", "action": "note", "text": "Simulated: walking with the resident to the bathroom."},
    {"at": 15, "actor": "nurse", "action": "complete",
     "text": "Simulated: resident back in their chair and comfortable."},
    {"at": 25, "actor": "resident", "action": "check_status"},
]

# One entry per scenario. `category` is the canonical request category (it
# picks the department); priority follows the request_staff_help contract
# (bathroom help is nursing, high).
SCENARIOS = {
    SCENARIO_ID: {"label": "Maintenance: leaking sink", "category": "maintenance", "priority": "normal",
                  "words": SINK_WORDS, "staff_roles": ("maintenance_tech",), "steps": STEPS},
    "nursing_assist": {"label": "Nursing: help to the bathroom", "category": "nursing", "priority": "high",
                       "words": NURSING_WORDS, "staff_roles": ("nurse",), "steps": NURSING_STEPS},
}
# Scenarios the Operations Simulator scheduler drives. Other writers of
# db.sim_runs (e.g. RQ-001 demo continuity) register runs under their own
# scenario id; the scheduler never treats those as its runs.
SCENARIO_IDS = tuple(SCENARIOS)


def spec(scenario_id: Optional[str]) -> dict:
    return SCENARIOS[scenario_id or SCENARIO_ID]


def steps_for(scenario_id: Optional[str]) -> list:
    return spec(scenario_id)["steps"]


def catalog() -> list:
    return [{"id": k, "label": v["label"], "category": v["category"], "steps_total": len(v["steps"]),
             "staff_roles": list(v["staff_roles"])} for k, v in SCENARIOS.items()]


def describe(index: int, scenario_id: Optional[str] = None) -> Optional[dict]:
    """The step at `index` of the scenario, with its position, or None past the end."""
    steps = steps_for(scenario_id)
    if index >= len(steps):
        return None
    return {"index": index, **steps[index]}


async def _require_simulated(task_id: str) -> None:
    """A simulated actor only ever touches simulated work."""
    task = await load(task_id)
    if not task.get("simulated"):
        raise RuntimeError(f"request {task_id} is not simulated; a simulated actor will not act on it")


async def _raise_request(step: dict, workflow: dict, cast: dict, sc: dict, run_id: Optional[str] = None) -> dict:
    """The simulated resident speaks through the same canonical request bus a
    real resident's Aria call uses. The synthetic resident record makes the
    actor and the task simulated (task_lifecycle.simulation_marker); the run
    id records the request as simulator-raised, on this run (SC-17)."""
    r = cast["resident"]
    out = await create_resident_request(ResidentRequestInput(
        category=sc["category"], resident_id=r["actor_id"], room=r["room"], priority=sc["priority"],
        resident_words=sc["words"], summary=sc["words"], source=roster.RESIDENT_CHANNEL),
        simulation_run_id=run_id)
    await _require_simulated(out["task_id"])
    return {"task_id": out["task_id"], "receipt_id": out["receipt_id"],
            "result": "re-request on an open request" if out.get("duplicate") else "request created",
            "workflow": {"task_id": out["task_id"], "origin_receipt_id": out["receipt_id"]}}


async def _staff_action(step: dict, workflow: dict, cast: dict, sc: dict, run_id: Optional[str] = None) -> dict:
    task_id = workflow.get("task_id")
    if not task_id:
        raise RuntimeError("no simulated request to act on yet")
    await _require_simulated(task_id)
    if staffing.fill_of(cast, step["actor"])["mode"] != "simulated":
        raise RuntimeError(f"{step['actor']} is held by a real user or unassigned; "
                           "the simulator will not act for them")
    actor, profile = roster.staff_actor(step["actor"]), roster.staff_profile(step["actor"])
    action = step["action"]
    if action == "acknowledge":
        _, receipt = await task_actions.acknowledge(task_id, actor, profile)
    elif action == "start":
        _, receipt = await task_actions.start(task_id, actor, profile)
    elif action == "note":
        _, receipt = await task_actions.add_note(task_id, step["text"], actor, profile)
    elif action == "complete":
        _, receipt = await task_actions.complete(task_id, step["text"], actor, profile)
    else:
        raise RuntimeError(f"unknown staff action {action}")
    # A lifecycle call that changes nothing writes no receipt (e.g. already
    # acknowledged); the scheduler records that outcome as "no change".
    return {"task_id": task_id, "receipt_id": (receipt or {}).get("receipt_id"),
            "result": action if receipt else f"{action}: no change"}


async def _check_status(step: dict, workflow: dict, cast: dict, sc: dict, run_id: Optional[str] = None) -> dict:
    """The simulated resident asks how their request went. The answer is the
    canonical resident-facing view of the request, read, not written."""
    task_id = workflow.get("task_id")
    if not task_id:
        raise RuntimeError("no simulated request to ask about")
    hist = await resident_request_history(resident_id=cast["resident"]["actor_id"], category=sc["category"])
    view = next((r for r in hist.get("requests", []) if r.get("task_id") == task_id), None)
    spoken = (view or {}).get("spoken") or "the request is still open"
    head = await chain_head(task_id)
    return {"task_id": task_id, "receipt_id": (head or {}).get("receipt_id"),
            "result": f"asked for an update; told: {spoken}"}


_HANDLERS = {"check_status": _check_status, "raise_request": _raise_request, "acknowledge": _staff_action, "start": _staff_action,
             "note": _staff_action, "complete": _staff_action}


async def execute(step: dict, workflow: dict, cast: dict, run_id: Optional[str] = None,
                  scenario_id: Optional[str] = None) -> dict:
    """Run one step of the scenario through its canonical service. Raises on
    refusal or failure (the canonical refusal is itself recorded by the lifecycle)."""
    return await _HANDLERS[step["action"]](step, workflow, cast, spec(scenario_id), run_id=run_id)
