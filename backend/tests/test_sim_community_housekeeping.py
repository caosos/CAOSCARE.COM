"""Weekly full clean per occupied apartment, by fixed territory (owner 2026-10-15)."""
import asyncio
import os
import uuid
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorClient

from simulation import community_housekeeping as hk
from simulation.community_blueprint import APARTMENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_day_queue import cohort_schedule
from simulation.community_ticket_plan import work_minutes
from simulation.community_worker_detail import clean_counts, housekeeping_today

A, B = "sim:staff:housekeeping:housekeeper:01", "sim:staff:housekeeping:housekeeper:02"


def test_every_occupied_apartment_is_cleaned_once_a_week_and_vacant_ones_never():
    occupied = {a.room for a in APARTMENTS if a.target_occupied}
    assert len(occupied) == 70
    for week_start in (0, 7, 35, 77):
        rooms = Counter(row["room"] for day in range(week_start, week_start + 7) for row in hk.cleans_on(day))
        assert set(rooms) == occupied and set(rooms.values()) == {1}


def test_territories_are_fixed_and_workload_follows_their_occupied_rooms():
    assert hk.occupied_rooms(A) == tuple(f"SIM-{n:03d}" for n in range(1, 41))
    assert hk.occupied_rooms(B) == tuple(f"SIM-{n:03d}" for n in range(41, 71))   # 071-080 are vacant
    assert hk.working_weekdays(A) == (0, 1, 2, 3, 4) and hk.working_weekdays(B) == (2, 3, 4, 5, 6)
    for day in range(7):
        per = Counter(row["housekeeper"] for row in hk.cleans_on(day))
        assert per[A] in ((8,) if day < 5 else (0,)) and per[B] in ((6,) if day >= 2 else (0,))
        # Same room, same housekeeper and weekday every week: territories are never reshuffled.
        assert hk.cleans_on(day) == [{**r} for r in hk.cleans_on(day + 7)]
    assert work_minutes(hk.FULL_CLEAN) == hk.FULL_CLEAN_MINUTES == 30   # owner, 2026-10-15


def test_over_90_days_each_clean_is_taken_only_by_its_territory_housekeeper():
    routines, scheduled = cohort_schedule("community_75")
    events = {e.event_id: e for day in routines.values() for e in day}
    cleans = [row for row in scheduled.values() if events[row.workflow_id].routine == hk.FULL_CLEAN]
    assert len(cleans) == 12 * 70 + (8 + 8 + 14 + 14 + 14 + 6)   # 12 weeks + Monday-Saturday
    assert all(row.claim_at is not None for row in cleans)
    for row in cleans:
        room = next(r.room for r in hk.RESIDENTS if r.resident_key == row.workflow_id.split(":")[1])
        assert row.worker["actor_id"] == hk.territory_of(room)
        assert row.complete_at - row.claim_at == 30


def test_today_answers_scheduled_assigned_completed_in_progress_remaining_not_simulated():
    async def case():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[f"{os.environ['DB_NAME']}_hk_{uuid.uuid4().hex[:6]}"]
        try:
            scope = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
                     "simulation_run_id": "run-hk", "simulated": True}
            first, second = hk.cleans_on(0, actor_id=A)[:2]
            await db.staff_tasks.insert_many([
                {**scope, "task_id": "t1", "status": "completed",
                 "conversation_session_id": f"simulator:event:{hk.clean_workflow(0, first['resident_key'])}"},
                {**scope, "task_id": "t2", "status": "in_progress",
                 "conversation_session_id": f"simulator:event:{hk.clean_workflow(0, second['resident_key'])}"},
            ])
            rows = await housekeeping_today(db, {"run_id": "run-hk"}, 0, A)
            assert len(rows) == 8 and {r["housekeeper"] for r in rows} == {A}
            assert clean_counts(rows) == {"completed": 1, "in_progress": 1, "remaining": 6, "not_simulated": 0}
            assert rows[0]["room"] == first["room"] and rows[0]["task_id"] == "t1"
            # A run started at 10:00 never ran the 09:25 clean: it is not "remaining".
            late = await housekeeping_today(db, {"run_id": "run-hk", "started_at_minute": 600}, 0, A)
            assert [r["state"] for r in late][:4] == ["completed", "in_progress", "not_simulated", "remaining"]
            assert clean_counts(late) == {"completed": 1, "in_progress": 1, "remaining": 5, "not_simulated": 1}
            everyone = await housekeeping_today(db, {"run_id": "run-hk"}, 2, None)   # Wednesday: both work
            assert Counter(r["housekeeper"] for r in everyone) == {A: 8, B: 6}
        finally:
            await db.client.drop_database(db.name)
    asyncio.run(case())
