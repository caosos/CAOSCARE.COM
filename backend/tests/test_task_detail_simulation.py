"""GET /tasks/{id}/detail tells a simulated living-community ticket's simulated clock (#168).

The `simulation` block comes only from canonical records: the run row, the run's validated plan and the
executor's phase receipts. Request minute and wait come from the OPEN/CLAIM receipts; start/finish only from
phases that executed; elapsed waiting/working is measured against the run's executed position. A real task gets
`simulation: None`. In-process ASGI, scratch DB, local-owner bypass off."""
import asyncio, os, sys, uuid
import httpx, pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import task_detail  # noqa: E402
from routes.auth import _issue_jwt  # noqa: E402
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE  # noqa: E402
from simulation.community_dashboard_common import plan_events  # noqa: E402
from simulation.community_timeline import PLAN_REVISIONS, build_90_day_timeline  # noqa: E402

TAG = f"tds_{uuid.uuid4().hex[:6]}"
RUN = f"{TAG}_run"
REVISION = PLAN_REVISIONS["burn_in_10"]
NOW = 600                                   # executed position: day 1, 10:00 simulated
BREAKFAST = "day-000:resident-001:breakfast"
SHOWER = "day-000:resident-001:shower_assistance"
SCOPE = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
         "simulation_run_id": RUN, "simulated": True}


def run(c): return asyncio.get_event_loop().run_until_complete(c)


def phase(workflow, name): return plan_events(REVISION)[f"{workflow}:ticket_{name}"]


def at(event): return event.day_index * 1440 + event.minute


def detail(task_id):
    app = FastAPI(); app.include_router(task_detail.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(f"/api/tasks/{task_id}/detail", headers={"Authorization": f"Bearer {_issue_jwt(f'{TAG}_owner')}"})
    r = run(go())
    assert r.status_code == 200, r.text
    return r.json()


def receipt(workflow, name, **after):
    event = phase(workflow, name)
    return {"receipt_id": f"{TAG}_{workflow[-6:]}_{name}", "simulation_run_id": RUN, "simulation_event_id": event.event_id,
            "authority": "living_community_executor", "status": "completed", "actor_id": event.actor_id,
            "actor_name": event.actor_name, "actor_type": "simulated-agent", "action_type": event.action_type,
            "after_state": after, "created_at": f"2026-10-14T10:0{len(name)}:00+00:00"}


def task(task_id, workflow, status, **extra):
    return {**SCOPE, "task_id": f"{TAG}_{task_id}", "status": status, "category": "nursing", "visibility_role": "nursing",
            "title": f"Scheduled simulated {workflow.rsplit(':', 1)[-1]}", "resident_id": "sim:resident:001",
            "resident_name": "SIM Resident 001", "room": "SIM-001", "priority": "normal",
            "conversation_session_id": f"simulator:event:{workflow}", "created_at": "2026-10-14T10:00:00+00:00", **extra}


@pytest.fixture(autouse=True)
def seed(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LOCAL_OWNER_BYPASS", raising=False)
    events = build_90_day_timeline("burn_in_10").events
    cursor = next(i for i, e in enumerate(events) if at(e) >= NOW)
    run(db.users.insert_one({"user_id": f"{TAG}_owner", "email": f"{TAG}@x.t", "name": "Owner", "role": "owner"}))
    run(db.sim_runs.insert_one({"run_id": RUN, "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
                                "state": "RUNNING", "plan_revision": REVISION, "cursor": cursor, "sim_minute": NOW}))
    claim = phase(BREAKFAST, "claim")
    run(db.staff_tasks.insert_many([
        task("done", BREAKFAST, "completed", assigned_to=claim.actor_id, assigned_name=claim.actor_name),
        task("work", SHOWER, "in_progress", assigned_to="sim:staff:nursing:care_aide:01", assigned_name="SIM - Care Aide 01"),
        task("wait", "day-000:resident-001:housekeeping_room_service", "pending"),
        {"task_id": f"{TAG}_real", "title": "Change a light bulb", "status": "pending", "visibility_role": "maintenance",
         "source": "staff", "created_at": "2026-10-14T10:00:00+00:00"},
    ]))
    run(db.receipts.insert_many([
        receipt(BREAKFAST, "open", status="pending", requested_at_minute=at(phase(BREAKFAST, "open")) - 2),
        receipt(BREAKFAST, "claim", status="in_progress", wait_reason="waiting_for_available_staff", waited_minutes=7),
        receipt(BREAKFAST, "complete", status="completed"),
        receipt(SHOWER, "open", status="pending"),
        receipt(SHOWER, "claim", status="in_progress", wait_reason="none", waited_minutes=0),
    ]))
    yield
    run(db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.sim_runs.delete_many({"run_id": RUN}))
    run(db.staff_tasks.delete_many({"task_id": {"$regex": f"^{TAG}"}}))
    run(db.receipts.delete_many({"receipt_id": {"$regex": f"^{TAG}"}}))


def test_completed_ticket_tells_simulated_request_start_finish_wait_and_who_raised_it():
    sim = detail(f"{TAG}_done")["simulation"]
    requested = at(phase(BREAKFAST, "open")) - 2           # the OPEN receipt's recorded minute wins over the plan
    started, finished = at(phase(BREAKFAST, "claim")), at(phase(BREAKFAST, "complete"))
    assert sim["requested"]["absolute_minute"] == requested and sim["requested"]["day"] == 1
    assert sim["started"]["absolute_minute"] == started and sim["finished"]["absolute_minute"] == finished
    assert sim["wait_minutes"] == started - requested and sim["waiting_minutes"] == started - requested
    assert sim["wait_reason"] == "waiting_for_available_staff" and sim["recorded_waited_minutes"] == 7
    assert sim["work_minutes"] == finished - started == sim["working_minutes"]
    assert sim["expected_work_minutes"] == 3 and sim["routine"] == "breakfast"
    assert sim["origin"] == {"kind": "scheduled_routine", "label": "Scheduled routine"}
    assert sim["raised_by"]["name"] == phase(BREAKFAST, "open").actor_name
    assert sim["now"] == {"absolute_minute": NOW, "day": 1, "hh_mm": "10:00"} and sim["run_state"] == "RUNNING"


def test_open_tickets_measure_elapsed_simulated_time_against_the_run_clock():
    work = detail(f"{TAG}_work")["simulation"]
    assert work["finished"] is None and work["work_minutes"] is None
    assert work["working_minutes"] == NOW - work["started"]["absolute_minute"]
    assert work["expected_work_minutes"] == 20
    wait = detail(f"{TAG}_wait")["simulation"]
    assert wait["started"] is None and wait["raised_by"] is None and wait["wait_reason"] is None
    assert wait["waiting_minutes"] == max(0, NOW - wait["requested"]["absolute_minute"])
    assert wait["working_minutes"] is None


def test_real_task_has_no_simulation_block_and_a_missing_run_is_stated_not_guessed():
    real = detail(f"{TAG}_real")
    assert real["simulation"] is None and real["origin"] == {"kind": "staff_generated", "label": "Staff / system created"}
    run(db.sim_runs.delete_many({"run_id": RUN}))
    sim = detail(f"{TAG}_done")["simulation"]
    assert sim["run_found"] is False and sim["requested"] is None and sim["now"] is None
    assert sim["expected_work_minutes"] == 3            # still known from the routine itself
