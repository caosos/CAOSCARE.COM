"""SIM-007A Live Operations dashboard read models, on real MongoDB (test DB)."""
import asyncio
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_dashboard_common import plan_events
from simulation.community_dashboard_detail import (
    DashboardNotFound, department_detail, resident_detail, worker_detail,
)
from simulation.community_dashboard_view import dashboard_snapshot
from simulation.community_ticket_view import ticket_detail
from simulation.community_timeline import PLAN_REVISIONS, build_90_day_timeline

REVISION = PLAN_REVISIONS["burn_in_10"]
NOW = 600  # day 1, 10:00 simulated


def _store():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[f"{os.environ['DB_NAME']}_dash_{uuid.uuid4().hex[:6]}"]


def _phase(workflow, phase):
    return plan_events(REVISION)[f"{workflow}:ticket_{phase}"]


async def _seed(db):
    events = build_90_day_timeline("burn_in_10").events
    cursor = next(i for i, e in enumerate(events) if e.day_index * 1440 + e.minute >= NOW)
    run = {"run_id": "run-dash", "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
           "state": "RUNNING", "plan_revision": REVISION, "cohort": "burn_in_10", "resident_count": 10,
           "cursor": cursor, "sim_minute": NOW, "event_count": len(events)}
    await db.sim_runs.insert_one(run)
    scope = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
             "simulation_run_id": "run-dash", "simulated": True}

    def task(task_id, workflow, status, dept, **extra):
        return {**scope, "task_id": task_id, "status": status, "category": dept,
                "title": f"Scheduled simulated {workflow.split(':')[-1].replace('_', ' ')}.",
                "description": f"Scheduled simulated {workflow.split(':')[-1].replace('_', ' ')}.",
                "resident_id": "sim:resident:001", "resident_name": "SIM Resident 001", "room": "SIM-001",
                "conversation_session_id": f"simulator:event:{workflow}", "priority": "normal", **extra}

    breakfast = "day-000:resident-001:breakfast"
    claim = _phase(breakfast, "claim")
    await db.staff_tasks.insert_many([
        task("t-done", breakfast, "completed", "kitchen", assigned_to=claim.actor_id,
             assigned_name=claim.actor_name, completed_by_name=claim.actor_name),
        task("t-wait", "day-000:resident-001:housekeeping_room_service", "pending", "housekeeping"),
        task("t-work", "day-000:resident-001:shower_assistance", "in_progress", "nursing",
             assigned_to="sim:staff:nursing:care_aide:01", assigned_name="SIM - Care Aide 01"),
    ])
    receipts = []
    for phase, status in (("open", "pending"), ("claim", "in_progress"), ("complete", "completed")):
        event = _phase(breakfast, phase)
        receipts.append({"receipt_id": f"r-exec-{phase}", "simulation_run_id": "run-dash",
                         "simulation_event_id": event.event_id, "authority": "living_community_executor",
                         "status": "completed", "actor_id": event.actor_id, "actor_name": event.actor_name,
                         "actor_type": "simulated-agent", "action_type": "breakfast",
                         "after_state": {"status": status, "wait_reason": "none"},
                         "created_at": f"2026-10-14T10:0{len(receipts)}:00+00:00"})
    receipts.append({"receipt_id": "r-canon-done", "related_object_type": "task", "related_object_id": "t-done",
                     "action_type": "task_completed", "status": "completed", "actor_type": "simulated-agent",
                     "created_at": "2026-10-14T10:05:00+00:00"})
    await db.receipts.insert_many(receipts)
    await db.residents.insert_one({"resident_id": "sim:resident:001", "name": "SIM Resident 001",
                                   "room": "SIM-001", "simulation_scope": SIMULATION_SCOPE, "synthetic": True})
    return claim


def _run(test):
    async def case():
        db = _store()
        try:
            claim = await _seed(db)
            await test(db, claim)
        finally:
            await db.client.drop_database(db.name)
    asyncio.run(case())


def test_summary_counts_departments_staff_and_residents():
    async def check(db, _claim):
        out = await dashboard_snapshot(store=db)
        assert out["run"]["as_of"] == {"absolute_minute": NOW, "day": 1, "hh_mm": "10:00"}
        assert out["counts"]["pending"] == 1 and out["counts"]["in_progress"] == 1
        assert out["counts"]["completed"] == 1 and out["counts"]["residents"] == 10
        depts = {d["slug"]: d for d in out["departments"]}
        assert len(depts) == 8
        assert depts["kitchen"]["completed_today"] == 1
        assert depts["housekeeping"]["waiting"] == 1 and depts["nursing"]["in_progress"] == 1
        aide = next(s for s in out["staff"] if s["actor_id"] == "sim:staff:nursing:care_aide:01")
        assert aide["current_task_id"] == "t-work"
        assert len(out["staff"]) == 66
    _run(check)


def test_department_worker_and_resident_details_use_canonical_tickets():
    async def check(db, claim):
        dept = await department_detail("housekeeping", store=db)
        assert [r["task_id"] for r in dept["work"]["waiting"]] == ["t-wait"]
        assert dept["work"]["waiting"][0]["what"] == "Scheduled simulated housekeeping room service."
        assert dept["schedule_today"] and all(u["planned"] for u in dept["work"]["upcoming"])
        worker = await worker_detail(claim.actor_id, store=db)
        assert [r["task_id"] for r in worker["completed"]] == ["t-done"]
        assert worker["worker"]["identity_basis"] == "synthetic"
        resident = await resident_detail("sim:resident:001", store=db)
        assert resident["requests"]["completed_total"] == 1
        assert {r["task_id"] for r in resident["care_today"]["done_or_open"]} == {"t-done", "t-wait", "t-work"}
        with pytest.raises(DashboardNotFound):
            await department_detail("spa", store=db)
        with pytest.raises(DashboardNotFound):
            await worker_detail("sim:staff:ghost", store=db)
    _run(check)


def test_completed_ticket_tells_times_duration_outcome_and_receipts():
    async def check(db, claim):
        out = await ticket_detail("t-done", store=db)
        complete = _phase("day-000:resident-001:breakfast", "complete")
        assert out["timeline"]["started"]["absolute_minute"] == claim.day_index * 1440 + claim.minute
        assert out["timeline"]["work_minutes"] == 3 and out["timeline"]["basis"] == "simulated"
        assert out["timeline"]["finished"]["absolute_minute"] == complete.day_index * 1440 + complete.minute
        assert out["outcome"].startswith(f"Completed by {claim.actor_name}")
        assert [r["receipt_id"] for r in out["receipts"]] == [
            "r-exec-open", "r-exec-claim", "r-exec-complete", "r-canon-done"]
        assert out["receipts"][1]["simulated_at"]["absolute_minute"] == out["timeline"]["started"]["absolute_minute"]
        waiting = await ticket_detail("t-wait", store=db)
        assert waiting["timeline"]["started"] is None and waiting["timeline"]["work_minutes"] is None
        assert waiting["outcome"] == "Waiting in the department queue for an available worker."
    _run(check)


def test_overnight_shift_carried_from_yesterday_counts_as_today():
    from simulation.community_dashboard_detail import _shifts

    night = [s for s in _shifts(1, department="nursing") if s["start"]["day"] == 1]
    assert night and all(s["start"]["hh_mm"] == "22:00" or s["start"]["hh_mm"] == "19:00" for s in night)
    assert all(s["end"]["day"] == 2 for s in night)


def test_today_lists_never_include_tomorrow():
    async def check(db, _claim):
        dept = await department_detail("nursing", store=db)
        assert dept["work"]["upcoming"] and all(u["at"]["day"] == 1 for u in dept["work"]["upcoming"])
        resident = await resident_detail("sim:resident:001", store=db)
        assert all(u["at"]["day"] == 1 for u in resident["care_today"]["upcoming"])
    _run(check)
