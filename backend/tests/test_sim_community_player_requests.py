"""Every simulated request comes from a person in the system (Michael, 2026-10-14).

Residents raise calls in their own words; on-site workers open rounds,
preventive maintenance and the problems they report. Nobody on site -> the
work is not raised. Calls and reports are counted as resident requests and
staff-created work, not as scheduled routine.
"""
import asyncio
from collections import Counter

from routes.task_origin import kind_of, routine_name
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_cohort import resident_keys_for
from simulation.community_day_queue import build_day_queue, cohort_schedule, opener
from simulation.community_executor import ExecutionContext
from simulation.community_player_requests import WORDS, player_requests
from simulation.community_routines import plan_first_24_hours
from simulation.community_staff_ticket import create_staff_task
from simulation.community_staffing import active_assignments
from simulation.community_ticket_plan import OPEN


def test_about_one_hundred_resident_calls_a_day_in_their_own_words():
    keys = resident_keys_for("community_75")
    for day in (0, 17, 89):
        events = player_requests(keys, day_index=day)
        calls = [e for e in events if e.opened_by == "resident"]
        reports = [e for e in events if e.opened_by == "staff"]
        assert len(calls) == 100 and len(reports) == 15
        assert all(e.resident_words == WORDS[e.routine] for e in calls)
        assert all(e.opener_department and e.opener_department != e.department or
                   e.routine == "staff_report_activity_help" for e in reports)
        assert len({e.event_id for e in events}) == len(events)
    assert player_requests(keys, day_index=4) == player_requests(keys, day_index=4)


def test_staff_work_is_opened_by_a_worker_on_site_or_not_at_all():
    routines, scheduled = cohort_schedule("community_75")
    for day in (0, 6, 45):
        for event in routines[day]:
            if event.opened_by == "resident":
                assert opener(event) is None
                continue
            worker = opener(event)
            assert worker is not None, event.event_id
            on_site = {row["actor_id"] for row in active_assignments(event.day_index, event.minute)}
            assert worker["actor_id"] in on_site and worker["department"] == event.opener_department
    # Rounds are the department's own work, raised by that department.
    rounds = [e for e in plan_first_24_hours(resident_keys_for("burn_in_10"), day_index=0)
              if e.routine == "breakfast"]
    assert rounds and all(e.opened_by == "staff" and e.opener_department == "kitchen" for e in rounds)


def test_day_queue_open_phase_names_its_person():
    for row in build_day_queue(2, cohort="community_75"):
        if row.task_phase != OPEN:
            continue
        if row.opened_by == "resident":
            assert row.actor_id == row.target_id
        else:
            assert row.actor_id.startswith("sim:staff:")
    counts = Counter(row.opened_by for row in build_day_queue(2, cohort="community_75")
                     if row.task_phase == OPEN)
    assert counts["resident"] >= 100 and counts["staff"] > counts["resident"]


def test_calls_and_reports_are_not_counted_as_scheduled_routine():
    call = {"source": "simulator", "simulated": True,
            "conversation_session_id": "simulator:event:day-003:resident-012:resident_call_spill_007"}
    report = {"source": "staff", "simulated": True,
              "conversation_session_id": "simulator:event:day-003:resident-012:staff_report_linen_change_002"}
    round_ = {"source": "staff", "simulated": True,
              "conversation_session_id": "simulator:event:day-003:resident-012:breakfast"}
    assert kind_of(call) == "resident_request"
    assert kind_of(report) == "staff_generated"
    assert kind_of(round_) == "scheduled_routine"
    assert routine_name(call) == "resident_call_spill"
    assert routine_name(round_) == "breakfast"


class _Collection:
    def __init__(self, docs=()):
        self.docs = list(docs)

    async def find_one(self, query, projection=None):
        return next((dict(d) for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)

    async def insert_one(self, doc):
        self.docs.append(dict(doc))


class _Store:
    def __init__(self):
        self.residents = _Collection([{
            "resident_id": "sim:resident:001", "name": "SIM Resident 001", "room": "SIM-001",
            "synthetic": True, "simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
        }])
        self.staff_tasks = _Collection()


def test_staff_ticket_names_the_worker_as_origin():
    event = next(row for row in build_day_queue(0) if row.task_phase == OPEN and row.opened_by == "staff"
                 and row.target_id == "sim:resident:001")
    context = ExecutionContext(run_id="simrun:test", holder_id="h", fence=1, cursor=0,
                               simulation_scope=SIMULATION_SCOPE, simulation_community_id=COMMUNITY_ID)
    store, recorded = _Store(), []

    async def origin(task, actor):
        recorded.append((task, actor))
        return {"receipt_id": "rcpt_test"}

    out = asyncio.run(create_staff_task(event=event, context=context, summary="Room check.",
                                        priority="normal", store=store, origin_recorder=origin))
    task = store.staff_tasks.docs[0]
    assert out["task_id"] == task["task_id"]
    assert task["source"] == "staff" and task["created_by"] == event.actor_id
    assert task["simulation_run_id"] == "simrun:test" and task["simulated"] is True
    actor = recorded[0][1]
    assert actor.actor_id == event.actor_id and actor.role == "staff"
