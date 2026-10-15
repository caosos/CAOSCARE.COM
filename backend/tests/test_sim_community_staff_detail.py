"""Staff On Duty -> worker detail, and the owner's role corrections (#153 / #166, 2026-10-15)."""
import asyncio
import os
import uuid
from collections import Counter

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_coverage import coverage_summary
from simulation.community_dashboard_detail import DashboardNotFound, worker_detail
from simulation.community_staffing import (
    WORKERS, active_assignments, assignments_for_day, weekday_of,
)
from simulation.community_timeline import PLAN_REVISIONS, build_90_day_timeline
from simulation.community_worker_detail import worker_state

REVISION = PLAN_REVISIONS["burn_in_10"]
NOW = 600  # Day 1 (a Monday), 10:00 simulated
HOUSEKEEPER_A = "sim:staff:housekeeping:housekeeper:01"
HOUSEKEEPER_B = "sim:staff:housekeeping:housekeeper:02"
AIDE = "sim:staff:nursing:care_aide:01"


def _roles(department):
    return Counter(w["job_role"] for w in WORKERS if w["department"] == department)


# --- role model (owner corrections) ------------------------------------------------

def test_activities_has_exactly_one_coordinator_and_no_assistant():
    assert _roles("activities") == {"activities_coordinator": 1}


def test_one_normal_maintenance_worker_on_site_on_business_days():
    assert _roles("maintenance")["maintenance_technician"] == 1
    for day in range(14):
        on_site = {r["actor_id"] for r in active_assignments(day, 10 * 60) if r["department"] == "maintenance"}
        assert on_site == ({"sim:staff:maintenance:maintenance_technician:01"} if weekday_of(day) < 5 else set())
        status = coverage_summary(day, 10 * 60)["coverage"]["maintenance"]["status"]
        assert status == ("on_duty" if weekday_of(day) < 5 else "on_call")


def test_two_housekeepers_on_the_owner_weekly_schedules():
    assert _roles("housekeeping") == {"housekeeper": 2}
    for day in range(90):
        on = {r["actor_id"] for r in assignments_for_day(day) if r["department"] == "housekeeping"}
        expected = set()
        if weekday_of(day) <= 4:   # Monday-Friday
            expected.add(HOUSEKEEPER_A)
        if weekday_of(day) >= 2:   # Wednesday-Sunday
            expected.add(HOUSEKEEPER_B)
        assert on == expected, day


def test_front_office_roles_are_recognizable_and_not_invented():
    assert _roles("administration") == {"business_office_manager": 1, "administrator": 1, "executive_director": 1}
    assert not any(w["job_role"] == "administration_leadership" for w in WORKERS)
    assert _roles("front_desk") == {"front_desk_coordinator": 4}


def test_nursing_staffing_is_unchanged_and_medication_support_stays_distinct():
    assert _roles("nursing") == {"registered_nurse": 4, "medication_reminder_support": 3, "care_aide": 15}


def test_state_is_never_guessed():
    assert worker_state("on_duty", True, False) == "working"
    assert worker_state("on_duty", False, False) == "free"
    assert worker_state("on_call", True, False) == "called_in"
    assert worker_state("on_call", False, False) == "on_call"
    assert worker_state("off_duty", False, False) == "off_duty"
    assert worker_state("on_duty", False, True) == "covered"


# --- worker detail on real MongoDB --------------------------------------------------

def _store():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[f"{os.environ['DB_NAME']}_staff_{uuid.uuid4().hex[:6]}"]


def _on_site(role):
    return sorted(r["actor_id"] for r in active_assignments(0, NOW) if r["job_role"] == role)[0]


async def _seed(db):
    events = build_90_day_timeline("burn_in_10").events
    cursor = next(i for i, e in enumerate(events) if e.day_index * 1440 + e.minute >= NOW)
    await db.sim_runs.insert_one({
        "run_id": "run-staff", "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
        "state": "RUNNING", "plan_revision": REVISION, "cohort": "burn_in_10", "resident_count": 10,
        "cursor": cursor, "sim_minute": NOW, "event_count": len(events)})
    scope = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
             "simulation_run_id": "run-staff", "simulated": True}

    def task(task_id, workflow, status, dept, worker, resident="001"):
        return {**scope, "task_id": task_id, "status": status, "category": dept, "priority": "normal",
                "title": workflow, "description": workflow, "resident_id": f"sim:resident:{resident}",
                "resident_name": f"SIM Resident {resident}", "room": f"SIM-{resident}",
                "conversation_session_id": f"simulator:event:{workflow}",
                "assigned_to": worker, "assigned_name": next(w["name"] for w in WORKERS if w["actor_id"] == worker)
                if worker else None}

    server, driver = _on_site("dining_server"), _on_site("driver")
    await db.staff_tasks.insert_many([
        task("t-tray", "day-000:resident-002:breakfast_room_service", "in_progress", "kitchen", server, "002"),
        task("t-meal", "day-000:resident-001:breakfast", "completed", "kitchen", server),
        task("t-ride", "day-000:resident-002:transport_coordination", "in_progress", "transportation", driver, "002"),
        task("t-care", "day-000:resident-004:shower_assistance", "in_progress", "nursing", AIDE, "004"),
        task("t-clean", "day-000:resident-005:housekeeping_room_service", "in_progress", "housekeeping",
             HOUSEKEEPER_A, "005"),
        task("t-fix", "day-000:resident-006:preventive_maintenance_check", "pending", "maintenance", None, "006"),
        # Another worker's ticket: must never appear in anyone else's detail.
        task("t-other", "day-000:resident-007:shower_assistance", "completed", "nursing",
             "sim:staff:nursing:care_aide:02", "007"),
    ])
    return server, driver


def _run(test):
    async def case():
        db = _store()
        try:
            await test(db, *await _seed(db))
        finally:
            await db.client.drop_database(db.name)
    asyncio.run(case())


def test_dining_server_detail_is_the_clicked_worker_with_meal_service_truth():
    async def check(db, server, _driver):
        out = await worker_detail(server, store=db)
        assert out["worker"]["actor_id"] == server and out["simulated"] is True
        assert out["worker"]["actor_type"] == "simulated-agent"
        assert out["state"] == "working" and out["duty"] == "on_duty"
        assert [r["task_id"] for r in out["current"]] == ["t-tray"]
        assert out["today"]["weekday"] == "Monday" and out["today"]["assigned_total"] == 2
        assert out["today"]["completed_total"] == 1 and out["completed_total"] == 1
        assert out["role_details"]["current_service"] == "Breakfast delivery to the apartment"
        assert out["role_details"]["served_today"] == {"breakfast · dining room": 1}
        assert out["on_break"] is None and out["location"] is None   # unknown, never guessed
        assert all(r["task_id"] != "t-other" for r in out["today"]["assigned"] + out["completed"])
    _run(check)


def test_driver_housekeeper_and_care_aide_show_role_specific_detail():
    async def check(db, _server, driver):
        ride = await worker_detail(driver, store=db)
        assert ride["role_details"] == {"kind": "transportation", "rides_today": ["t-ride"]}
        clean = await worker_detail(HOUSEKEEPER_A, store=db)
        assert clean["role_details"]["assigned_rooms"] == "SIM-001 to SIM-040"
        assert [r["task_id"] for r in clean["current"]] == ["t-clean"]
        assert {d["weekday"] for d in clean["week"]} == {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
        other = await worker_detail(HOUSEKEEPER_B, store=db)
        assert other["role_details"]["assigned_rooms"] == "SIM-041 to SIM-080" and other["state"] == "off_duty"
        care = await worker_detail(AIDE, store=db)
        assert care["role_details"]["residents_today"] == ["SIM Resident 004"]
        assert "t-other" not in {r["task_id"] for r in care["completed"] + care["current"]}
        fix = await worker_detail("sim:staff:maintenance:maintenance_technician:01", store=db)
        assert fix["role_details"]["open_queue_total"] == 1 and fix["state"] == "free"
    _run(check)


def test_unknown_worker_is_refused_not_guessed():
    async def check(db, _server, _driver):
        with pytest.raises(DashboardNotFound):
            await worker_detail("sim:staff:activities:activities_assistant:01", store=db)
        with pytest.raises(DashboardNotFound):
            await worker_detail("user_real_person", store=db)
    _run(check)
