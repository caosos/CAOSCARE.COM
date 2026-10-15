"""CO-008 plan realism (v9): qualified roles, on-call call-in, whole-wait
blockers, and time-bound work that expires instead of being served late."""
from collections import Counter

import pytest

from simulation import community_capacity_schedule as capacity
from simulation import community_role_eligibility as eligibility
from simulation import community_wait_blockers as blockers
from simulation.community_day_queue import cohort_schedule
from simulation.community_on_call import CALL_IN_PRIORITIES, response_minutes
from simulation.community_service_windows import NOT_SERVED, SERVICE_WINDOW_ENDS, service_deadline
from simulation.community_staffing import active_assignments, on_call_assignments, worker_statuses
from simulation.community_ticket_plan import CLAIM, EXPIRE, OPEN, OPEN_TO_CLAIM_MINUTES
from simulation.community_timeline import (
    PLAN_REVISIONS, TimelineValidationError, build_90_day_timeline, cohort_of_revision,
)

DAY = 2 * 1440
MED_TECH, RN, AIDE = eligibility.MED_TECH, eligibility.RN, eligibility.CARE_AIDE


def _schedule(*tickets):
    return capacity.schedule_tickets(tickets)


def _ids(rows):
    return {row["actor_id"] for row in rows}


@pytest.fixture(scope="module")
def full():
    routines, scheduled = cohort_schedule("community_75")
    events = {event.event_id: event for day in routines.values() for event in day}
    return events, scheduled


# --- qualified roles -------------------------------------------------------

def test_every_claim_goes_to_a_qualified_worker_of_the_department(full):
    events, scheduled = full
    medication = Counter()
    for workflow, row in scheduled.items():
        if row.worker is None:
            continue
        event = events[workflow]
        assert row.worker["department"] == event.department
        assert row.worker["job_role"] in eligibility.eligible_roles(event.department, event.routine)
        if "medication_reminder" in event.routine:
            medication[row.worker["job_role"]] += 1
    # Never a care aide (or anyone outside nursing); the med tech does most.
    assert set(medication) == {MED_TECH, RN}
    assert medication[MED_TECH] > medication[RN]


def test_med_tech_is_preferred_and_aides_never_take_reminders():
    at = DAY + 8 * 60  # on site: 4 aides, 1 RN, the day med tech
    rows = _schedule(
        ("a", "nursing", "high", at, 3, "morning_medication_reminder"),
        ("b", "nursing", "high", at, 3, "morning_medication_reminder"),
        ("c", "nursing", "high", at, 3, "morning_medication_reminder"),
        ("d", "nursing", "high", at, 8, "toileting_transfer_support"),
    )
    assert rows["a"].worker["job_role"] == MED_TECH and rows["a"].claim_at == at + 5
    assert rows["b"].worker["job_role"] == RN and rows["b"].claim_at == at + 5
    # Four aides were free, but none may take a reminder: it waits for the med tech.
    assert rows["c"].worker["job_role"] == MED_TECH and rows["c"].claim_at == at + 8
    assert rows["c"].wait_reason == capacity.STAFF_BUSY
    assert rows["d"].worker["job_role"] == AIDE


def test_unlisted_nursing_routine_is_refused_not_guessed():
    with pytest.raises(eligibility.RoleEligibilityError):
        eligibility.eligible_roles("nursing", "ghost_routine")
    assert eligibility.eligible_roles("kitchen", "dinner") == ("dining_server", "meal_delivery_aide")
    assert eligibility.eligible_roles("nursing", "evening_medication_reminder") == (MED_TECH, RN)
    for (department, _routine), roles in eligibility.ROUTINE_ROLES.items():
        assert set(roles) <= set(eligibility.DEPARTMENT_ROLES[department])


def test_no_qualified_worker_on_site_waits_truthfully_or_calls_in(monkeypatch):
    monkeypatch.setitem(eligibility.ROUTINE_ROLES, ("nursing", "rn_only_review"), (RN,))
    at = DAY + 23 * 60  # aides and the night med tech on site; the RN is on call
    rows = _schedule(("n", "nursing", "normal", at, 10, "rn_only_review"),
                     ("h", "nursing", "high", at, 10, "rn_only_review"))
    normal, high = rows["n"], rows["h"]
    assert normal.worker["job_role"] == RN and normal.claim_at == DAY + 1440 + 6 * 60
    assert normal.wait_breakdown == ((blockers.QUALIFIED_ABSENT, 415),)
    assert normal.wait_reason == blockers.QUALIFIED_ABSENT and not normal.called_in_on_call
    assert high.called_in_on_call and high.claim_at == at + 5 + response_minutes("nursing")
    assert high.worker["actor_id"] in _ids(on_call_assignments(2, 23 * 60))
    assert high.wait_breakdown == ((blockers.ON_CALL_RESPONSE, response_minutes("nursing")),)


# --- on-call call-in -------------------------------------------------------

def test_high_maintenance_after_hours_calls_in_on_call_after_the_response_delay():
    at = DAY + 16 * 60
    rows = _schedule(("h", "maintenance", "high", at, 20, "staff_report_bed_alarm"),
                     ("n", "maintenance", "normal", at, 20, "resident_call_light_out"))
    high, normal = rows["h"], rows["n"]
    delay = response_minutes("maintenance")
    assert high.called_in_on_call and high.claim_at == at + OPEN_TO_CLAIM_MINUTES + delay
    assert high.worker["actor_id"] in _ids(on_call_assignments(2, 16 * 60))
    assert high.wait_reason == blockers.ON_CALL_RESPONSE and high.waited_minutes == delay
    # Normal priority keeps waiting for on-site hours.
    assert not normal.called_in_on_call and normal.claim_at == DAY + 1440 + 7 * 60
    assert normal.worker["actor_id"] in _ids(active_assignments(3, 7 * 60))
    assert normal.wait_reason == blockers.ON_CALL_ONLY
    assert sum(minutes for _reason, minutes in normal.wait_breakdown) == normal.waited_minutes


def test_called_in_worker_holds_one_ticket_and_is_not_present_before_claiming():
    at = DAY + 17 * 60
    rows = _schedule(("x", "maintenance", "urgent", at, 20, "staff_report_call_cord"),
                     ("y", "maintenance", "high", at, 20, "staff_report_bed_alarm"))
    first, second = rows["x"], rows["y"]
    assert first.worker == second.worker and first.called_in_on_call and second.called_in_on_call
    # Already on site from the first call-in: the second needs no new drive in.
    assert second.claim_at == first.complete_at
    assert set(capacity.peak_active_tickets(rows.values()).values()) == {1}
    actor = first.worker["actor_id"]
    before = first.claim_at - 1
    status = next(row for row in worker_statuses(*divmod(before, 1440)) if row["actor_id"] == actor)
    assert status["status"] == "on_call" and status["physically_present"] is False
    assert actor not in _ids(active_assignments(*divmod(before, 1440)))


def test_no_call_in_when_the_on_site_shift_arrives_first():
    at = DAY + 6 * 60 + 30  # on-call response would land after the 07:00 day shift
    row = _schedule(("h", "maintenance", "high", at, 20, "staff_report_bed_alarm"))["h"]
    assert not row.called_in_on_call and row.claim_at == DAY + 7 * 60
    assert row.wait_reason == blockers.ON_CALL_ONLY


def test_full_plan_call_ins_are_high_priority_and_never_overlap(full):
    events, scheduled = full
    called = [row for row in scheduled.values() if row.called_in_on_call]
    assert called
    for row in called:
        assert events[row.workflow_id].priority in CALL_IN_PRIORITIES
        day, minute = divmod(row.claim_at, 1440)
        assert row.worker["actor_id"] in _ids(on_call_assignments(day, minute))
        assert row.worker["actor_id"] not in _ids(active_assignments(day, minute))
    assert set(capacity.peak_active_tickets(scheduled.values()).values()) == {1}
    plan = build_90_day_timeline("community_75")
    claims = [e for e in plan.events if e.task_phase == CLAIM and e.called_in_on_call]
    assert len(claims) == len(called)


# --- whole-wait blockers ---------------------------------------------------

def test_wait_breakdown_sums_to_waited_minutes_and_reason_is_dominant(full):
    _events, scheduled = full
    for row in scheduled.values():
        total = sum(minutes for _reason, minutes in row.wait_breakdown)
        if row.claim_at is not None:
            assert total == row.waited_minutes
            assert row.wait_reason == blockers.dominant(row.wait_breakdown)
        elif row.expire_at is not None:
            eligible = row.requested_at + OPEN_TO_CLAIM_MINUTES
            assert total == max(0, row.expire_at - eligible)


def test_overnight_wait_is_attributed_to_the_closed_department():
    at = DAY + 16 * 60 + 20  # eligible 16:25; housekeeping closes 16:30
    rows = _schedule(*[(f"t{n}", "housekeeping", "normal", at, 10, "resident_call_towels")
                       for n in range(6)])
    last = max(rows.values(), key=lambda row: (row.claim_at, row.workflow_id))
    assert last.claim_at == DAY + 1440 + 8 * 60 + 20
    # The minute before the claim was staffed, but the wait was mostly a closed department.
    assert dict(last.wait_breakdown) == {blockers.STAFF_BUSY: 25, blockers.DEPARTMENT_CLOSED: 930}
    assert last.wait_reason == blockers.DEPARTMENT_CLOSED


# --- time-bound work -------------------------------------------------------

def test_dinner_not_claimed_in_its_window_expires_to_the_department_lead():
    at = DAY + 19 * 60
    rows = _schedule(*[(f"d{n:02d}", "kitchen", "normal", at, 3, "dinner") for n in range(80)])
    served = [row for row in rows.values() if row.claim_at is not None]
    missed = [row for row in rows.values() if row.expire_at is not None]
    deadline = DAY + 19 * 60 + 30
    assert served and missed and len(served) + len(missed) == 80
    assert all(row.claim_at < deadline for row in served)
    lead = _ids(active_assignments(2, 19 * 60 + 29))
    for row in missed:
        assert row.expire_at == deadline and row.claim_at is None and row.worker is None
        assert row.wait_reason == NOT_SERVED and row.expired_by["actor_id"] in lead
        assert row.expired_by["department"] == "kitchen"


def test_only_meals_and_activities_in_the_window_table_expire(full):
    events, scheduled = full
    assert set(SERVICE_WINDOW_ENDS) == {"dinner", "dinner_room_service", "activity_escort", "one_to_one_activity_visit"}
    for routine in ("resident_call_bathroom", "toileting_transfer_support", "breakfast",
                    "evening_medication_reminder", "staff_report_call_cord"):
        assert service_deadline(routine, DAY) is None
    expired = Counter(events[row.workflow_id].routine for row in scheduled.values() if row.expire_at)
    # v11 room-delivery staffing serves every meal in its window; expiry itself is proven above.
    assert set(expired) <= set(SERVICE_WINDOW_ENDS)
    for workflow, row in scheduled.items():
        if events[workflow].routine in SERVICE_WINDOW_ENDS and row.claim_at is not None:
            assert row.claim_at < service_deadline(events[workflow].routine, row.requested_at)
            assert row.claim_at // 1440 == row.requested_at // 1440


def test_expired_ticket_is_open_then_expire_by_the_lead_in_the_timeline(full):
    _events, scheduled = full
    plan = build_90_day_timeline("community_75")
    by_workflow = {}
    for event in plan.events:
        if event.workflow_event_id:
            by_workflow.setdefault(event.workflow_event_id, []).append(event)
    expired = [row for row in scheduled.values() if row.expire_at is not None][:200]
    for row in expired:
        phases = by_workflow[row.workflow_id]
        assert [event.task_phase for event in phases] == [OPEN, EXPIRE]
        expire = phases[1]
        assert expire.day_index * 1440 + expire.minute == row.expire_at
        assert expire.actor_id == row.expired_by["actor_id"] and expire.actor_id.startswith("sim:staff:")
        assert expire.wait_reason == NOT_SERVED and expire.waited_minutes is None


# --- revision and determinism ----------------------------------------------

def test_v9_plan_is_deterministic_and_v8_runs_are_not_loadable():
    tickets = [(f"t{n}", "kitchen", "normal", DAY + 19 * 60 + n % 4, 3, "dinner") for n in range(30)]
    assert _schedule(*tickets) == _schedule(*reversed(tickets))
    assert PLAN_REVISIONS["community_75"] == "living-community-timeline-v12-staff-roles-community_75"
    # One plan revision per cohort: a v8 run must be cut over before v9 is deployed.
    with pytest.raises(TimelineValidationError):
        cohort_of_revision("living-community-timeline-v8-player-raised-community_75")
