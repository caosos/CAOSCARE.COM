"""One-day proof that every canonical department is staffed and visibly works."""

import asyncio
from collections import defaultdict

from simulation.community_activity_view import activity_snapshot
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_day_queue import build_day_queue
from simulation.community_executor import ExecutionContext
from simulation.community_runtime_view import runtime_snapshot
from simulation.community_shift_events import planned_events_for_day
from simulation.community_shift_execution import record_shift_milestone
from simulation.community_coverage import coverage_summary, planned_coverage_gaps
from simulation.community_staffing import DEPARTMENT_LABELS, WORKERS, active_assignments, weekday_of
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN
from simulation.community_timeline import build_90_day_timeline
from tests.community_runtime_fake import Collection, RuntimeStore, _matches


RUN_ID = "department-activity-run"
DEPARTMENTS = set(DEPARTMENT_LABELS)
MEANINGFUL_WORK = {
    "nursing": "shower_assistance",
    "kitchen": "breakfast",
    "housekeeping": "housekeeping_full_clean",
    "maintenance": "preventive_maintenance_check",
    "transportation": "transport_coordination",
    # Service model: only escorts and one-to-one visits take activities staff time.
    "activities": ("activity_escort", "one_to_one_activity_visit"),
    "front_desk": "front_desk_message_follow_up",
    "administration": "appointment_coordination",
}


def _first(work):
    return work[0] if isinstance(work, tuple) else work


class CountCollection(Collection):
    async def count_documents(self, query):
        return sum(1 for row in self.documents if _matches(row, query))


def marked(**values):
    return {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        **values,
    }


def test_actual_rota_has_no_hidden_gap_during_representative_24_hours():
    """Departments may be CLOSED or ON CALL by design; none is ever UNCOVERED."""
    assert len(WORKERS) == 55
    assert planned_coverage_gaps(0) == []
    for minute in range(1440):
        summary = coverage_summary(0, minute)
        assert summary["gaps"] == []
        assert summary["coverage"]["nursing"]["status"] == "on_duty"
        assert {item["status"] for item in summary["coverage"].values()} <= {
            "on_duty", "on_call", "closed",
        }
    midday = {row["department"] for row in active_assignments(0, 12 * 60)}
    assert midday == DEPARTMENTS  # every department works during the day


def test_runtime_projection_shows_every_department_at_each_shift_boundary():
    async def scenario():
        queue = build_day_queue()
        for minute in (0, 359, 360, 839, 840, 1319, 1320, 1439):
            store = RuntimeStore()
            store.staff_tasks = CountCollection(store, "staff_tasks")
            store.sim_runs.docs.append(marked(
                run_id=RUN_ID, state="RUNNING", cursor=0, sim_minute=minute,
                residents_provisioned=False,
                created_at="2026-10-13T00:00:00+00:00",
            ))
            view = await runtime_snapshot(store=store, events=queue)
            assert view["status"] == "loaded"
            coverage = view["staffing"]["coverage"]
            assert view["staffing"]["gaps"] == []
            assert set(coverage) == DEPARTMENTS
            assert coverage["nursing"]["status"] == "on_duty"
            assert all((item["status"] == "on_duty") == (item["on_shift"] > 0)
                       for item in coverage.values())
            assert coverage["maintenance"]["status"] == (
                "on_duty" if 7 * 60 <= minute < 15 * 60 + 30 else "on_call")

    asyncio.run(scenario())


def test_shift_start_handoff_and_end_each_create_exact_department_receipts():
    async def scenario():
        events = planned_events_for_day(0)
        receipts = []

        async def write(**kwargs):
            row = {key: value for key, value in kwargs.items() if key != "provenance"}
            row.update(kwargs["provenance"])
            receipts.append(row)
            return row

        cursor = 0
        for department in sorted(DEPARTMENTS):
            for action in ("clock_in", "handoff", "clock_out"):
                event = next(row for row in events if (
                    row["department"] == department and row["event_type"] == action
                ))
                from simulation.community_executor import ExecutorEvent

                item = ExecutorEvent(
                    event_id=event["event_id"], stream_kind=event["stream_kind"],
                    action_type=event["event_type"], day_index=event["day_index"],
                    minute=event["minute"], actor_id=event["actor_id"],
                    actor_name=event["actor_name"], actor_type=event["actor_type"],
                    identity_basis=event["identity_basis"], department=department,
                    target_type=event["target_type"], target_id=event["target_id"],
                    adapter="canonical_shift_service", simulated=True,
                )
                context = ExecutionContext(
                    RUN_ID, "acceptance", 1, cursor, SIMULATION_SCOPE, COMMUNITY_ID,
                )
                receipt = await record_shift_milestone(
                    item, context, write, "living_community_executor",
                )
                assert receipt["actor_department"] == department
                assert receipt["action_type"] == action
                assert receipt["status"] == "completed"
                assert receipt["after_state"]["real_attendance_claimed"] is False
                cursor += 1

        assert len(receipts) == len(DEPARTMENTS) * 3
        assert {(row["actor_department"], row["action_type"]) for row in receipts} == {
            (department, action)
            for department in DEPARTMENTS
            for action in ("clock_in", "handoff", "clock_out")
        }

    asyncio.run(scenario())


def test_every_department_has_meaningful_visible_ticket_phases_in_one_day():
    ticket_events = [
        event for event in build_day_queue()
        if event.stream_kind == "routine_ticket_phase"
    ]
    by_workflow = defaultdict(list)
    for event in ticket_events:
        by_workflow[event.workflow_event_id].append(event)

    assert len(BURN_IN_RESIDENTS) == 10
    assert {event.target_id for event in ticket_events if event.task_phase == OPEN} == {
        resident.resident_id for resident in BURN_IN_RESIDENTS
    }
    assert {event.department for event in ticket_events} == DEPARTMENTS
    for department, action in MEANINGFUL_WORK.items():
        workflows = [rows for rows in by_workflow.values()
                     if rows[0].department == department
                     and rows[0].action_type in (action if isinstance(action, tuple) else (action,))]
        assert workflows, department
        for phases in workflows:
            phases.sort(key=lambda row: row.day_index * 1440 + row.minute)
            assert [row.task_phase for row in phases] == [OPEN, CLAIM, COMPLETE]
            opened = phases[0]
            # Every ticket is raised by a person: the resident asks, or a worker
            # physically on site opens it (rounds, preventive maintenance, reports).
            if opened.opened_by == "resident":
                assert opened.actor_id == opened.target_id
            else:
                assert opened.actor_id in {
                    worker["actor_id"] for worker in active_assignments(opened.day_index, opened.minute)
                }
            for row in phases[1:]:
                active_ids = {
                    worker["actor_id"]
                    for worker in active_assignments(row.day_index, row.minute)
                }
                assert row.actor_id in active_ids

    front_desk = next(
        event for event in ticket_events
        if event.action_type == "front_desk_message_follow_up"
    )
    assert front_desk.blocked_capability == "outbound_front_desk_call"


def test_all_90_source_days_keep_meaningful_ticket_work_in_every_department():
    plan = build_90_day_timeline()
    departments_by_source_day = defaultdict(set)
    for event in plan.events:
        if event.stream_kind != "routine_ticket_phase":
            continue
        source_day = int(event.workflow_event_id.removeprefix("day-").split(":", 1)[0])
        departments_by_source_day[source_day].add(event.department)

    assert plan.day_count == 90 and plan.source_start_day == 0 and plan.source_end_day == 89
    assert set(departments_by_source_day) == set(range(90))
    # Owner (2026-10-15): one activities coordinator and the front office work business
    # days, so on Saturdays and Sundays no activity work is planned and family calls go to
    # the Front Desk; every other department works daily.
    for day in range(90):
        expected = DEPARTMENTS if weekday_of(day) < 5 else DEPARTMENTS - {"activities", "administration"}
        # The burn-in's ten apartments are all in Housekeeper 01's Mon-Fri territory: on a
        # weekend only a resident call can bring housekeeping work.
        if weekday_of(day) >= 5:
            expected = expected - {"housekeeping"} | (departments_by_source_day[day] & {"housekeeping"})
        assert departments_by_source_day[day] == expected, day


def test_activity_projection_can_show_ticket_work_from_all_departments():
    async def scenario():
        store = RuntimeStore()
        store.sim_runs.docs.append(marked(run_id=RUN_ID))
        for index, department in enumerate(sorted(DEPARTMENTS), start=1):
            resident_id = f"sim:resident:{index:03d}"
            task_id = f"task:{department}"
            store.residents.docs.append(marked(
                resident_id=resident_id, name=f"SIM Resident {index:03d}", synthetic=True,
            ))
            store.staff_tasks.docs.append(marked(
                task_id=task_id, simulation_run_id=RUN_ID, simulated=True,
                resident_id=resident_id, category=department,
                visibility_role=department, description=_first(MEANINGFUL_WORK[department]),
                priority="normal", status="completed",
                created_at=f"2026-10-13T{index:02d}:00:00+00:00",
                completed_at=f"2026-10-13T{index:02d}:15:00+00:00",
            ))
            for phase, action in enumerate(
                ("resident_request_created", "task_in_progress", "task_completed")
            ):
                is_origin = phase == 0
                store.receipts.docs.append(marked(
                    receipt_id=f"rcpt:{department}:{phase}", simulation_run_id=RUN_ID,
                    related_object_type="task", related_object_id=task_id,
                    action_type=action, status="created" if is_origin else (
                        "in_progress" if phase == 1 else "completed"
                    ),
                    actor_id=resident_id if is_origin else f"sim:staff:{department}:01",
                    actor_type="simulated-agent", actor_name=None if is_origin else department,
                    actor_role="resident" if is_origin else "staff",
                    actor_department=None if is_origin else department,
                    channel="simulator", identity_basis="synthetic", simulated=True,
                    authority="simulation_run" if is_origin else f"acts_for:{department}",
                    parent_receipt_id=None if is_origin else f"rcpt:{department}:{phase - 1}",
                    correlation_id=f"rcpt:{department}:0",
                    created_at=f"2026-10-13T{index:02d}:{phase:02d}:00+00:00",
                ))

        view = await activity_snapshot(run_id=RUN_ID, store=store)
        assert view["status"] == "loaded"
        assert {row["department"] for row in view["tasks"]["items"]} == DEPARTMENTS
        staff_transitions = [
            row for row in view["transitions"]["items"]
            if row["action_type"] != "resident_request_created"
        ]
        assert {row["actor"]["department"] for row in staff_transitions} == DEPARTMENTS
        assert all(row["provenance_status"] == "complete" for row in staff_transitions)

    asyncio.run(scenario())
