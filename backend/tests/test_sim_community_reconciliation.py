import pytest

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_reconciliation import ReconciliationError, reconcile_run
from simulation.community_routines import plan_first_24_hours


RUN_ID = "living-run-1"


def run_row(**overrides):
    row = {
        "run_id": RUN_ID,
        "state": "RUNNING",
        "cursor": 0,
        "sim_minute": 30,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    row.update(overrides)
    return row


def events(*minutes):
    return [
        {"event_id": f"event-{index}", "day_index": minute // 1440, "minute": minute % 1440}
        for index, minute in enumerate(minutes)
    ]


def receipt(event_id, suffix="1", status="completed", **overrides):
    row = {
        "receipt_id": f"receipt-{event_id}-{suffix}",
        "simulation_event_id": event_id,
        "simulation_run_id": RUN_ID,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "status": status,
    }
    row.update(overrides)
    return row


def by_id(plan):
    return {row["event_id"]: row for row in plan["classified_events"]}


def test_restart_plans_several_contiguous_missed_events_without_executing():
    plan = reconcile_run(run_row(sim_minute=35), events(10, 20, 30, 40))
    assert [step["event_id"] for step in plan["recovery_steps"]] == [
        "event-0", "event-1", "event-2"
    ]
    assert all(step["action"] == "execute_event_then_advance" for step in plan["recovery_steps"])
    assert by_id(plan)["event-3"]["classification"] == "future"
    assert plan["read_only"] is True and plan["represents_execution"] is False


def test_receipt_replay_advances_cursor_without_replaying_action():
    rows = events(10, 20, 30)
    plan = reconcile_run(
        run_row(cursor=1, sim_minute=30, last_event_id="event-0"),
        rows,
        [receipt("event-0"), receipt("event-1")],
    )
    assert plan["recovery_steps"][0] == {
        "action": "advance_cursor_from_receipt",
        "event_id": "event-1",
        "expected_cursor": 1,
        "next_cursor": 2,
        "receipt_id": "receipt-event-1-1",
        "represents_execution": False,
    }
    assert plan["recovery_steps"][1]["action"] == "execute_event_then_advance"


def test_cursor_gap_is_inconsistent_and_blocks_all_recovery():
    plan = reconcile_run(
        run_row(cursor=2, last_event_id="event-1"),
        events(10, 20, 30),
        [receipt("event-0")],
    )
    assert by_id(plan)["event-1"]["classification"] == "inconsistent"
    assert plan["status"] == "inconsistent"
    assert plan["recovery_steps"] == []


def test_receipt_after_unresolved_gap_is_inconsistent_and_never_skipped():
    plan = reconcile_run(run_row(), events(10, 20, 30), [receipt("event-1")])
    assert by_id(plan)["event-0"]["classification"] == "due_catch_up"
    assert by_id(plan)["event-1"]["classification"] == "inconsistent"
    assert plan["recovery_steps"] == []


def test_future_event_stops_recovery_window():
    plan = reconcile_run(run_row(sim_minute=15), events(10, 20, 30))
    assert [step["event_id"] for step in plan["recovery_steps"]] == ["event-0"]
    assert by_id(plan)["event-1"]["classification"] == "future"


def test_receipt_for_future_event_is_inconsistent_not_replayed():
    plan = reconcile_run(run_row(sim_minute=10), events(20), [receipt("event-0")])
    assert by_id(plan)["event-0"]["classification"] == "inconsistent"
    assert plan["recovery_steps"] == []


def test_explicitly_blocked_event_stops_without_skipping_later_due_event():
    rows = events(10, 20, 30)
    rows[1]["execution_state"] = "blocked"
    plan = reconcile_run(run_row(), rows)
    assert by_id(plan)["event-1"]["classification"] == "blocked"
    assert [step["event_id"] for step in plan["recovery_steps"]] == ["event-0"]


@pytest.mark.parametrize("state", ["PAUSED", "STOPPED"])
def test_non_running_state_never_emits_executable_recovery(state):
    plan = reconcile_run(run_row(state=state), events(10, 40))
    assert plan["recovery_steps"] == []
    assert plan["execution_allowed_now"] is False
    if state == "PAUSED":
        assert by_id(plan)["event-0"]["classification"] == "due_catch_up"
        assert plan["status"] == "paused"
    else:
        assert all(row["classification"] == "terminal" for row in plan["classified_events"])
        assert plan["status"] == "terminal"


def test_running_state_reports_truth_without_claiming_execution():
    plan = reconcile_run(run_row(), events(10))
    assert plan["status"] == "ready" and plan["execution_allowed_now"] is True
    assert plan["classified_events"][0]["represents_execution"] is False
    assert plan["recovery_steps"][0]["represents_execution"] is False


def test_nonterminal_or_multiple_receipts_are_inconsistent():
    pending = reconcile_run(run_row(), events(10), [receipt("event-0", status="attempted")])
    assert pending["status"] == "inconsistent"
    duplicated = reconcile_run(
        run_row(), events(10), [receipt("event-0", "1"), receipt("event-0", "2")]
    )
    assert duplicated["status"] == "inconsistent"
    assert duplicated["recovery_steps"] == []


@pytest.mark.parametrize("field,value", [
    ("cursor", -1), ("cursor", "0"), ("sim_minute", -1), ("sim_minute", None),
    ("state", "running"),
])
def test_malformed_run_state_is_refused(field, value):
    with pytest.raises(ReconciliationError):
        reconcile_run(run_row(**{field: value}), events(10))


def test_wrong_scope_or_community_is_refused():
    with pytest.raises(ReconciliationError, match="wrong simulation scope"):
        reconcile_run(run_row(simulation_scope="demo_room"), events(10))
    with pytest.raises(ReconciliationError, match="wrong simulation community"):
        reconcile_run(run_row(simulation_community_id="other"), events(10))
    with pytest.raises(ReconciliationError, match="different run"):
        reconcile_run(run_row(), events(10), [receipt("event-0", simulation_run_id="other")])


def test_duplicate_or_ambiguous_event_ids_are_refused():
    with pytest.raises(ReconciliationError, match="duplicate planned event_id"):
        reconcile_run(run_row(), [
            {"event_id": "same", "day_index": 0, "minute": 1},
            {"event_id": "same", "day_index": 0, "minute": 2},
        ])
    with pytest.raises(ReconciliationError, match="simulation_event_id"):
        reconcile_run(run_row(), events(10), [{
            **receipt("event-0"), "simulation_event_id": "",
        }])
    with pytest.raises(ReconciliationError, match="invalid minute"):
        reconcile_run(run_row(), [{"event_id": "boolean-time", "day_index": 0, "minute": True}])


def test_recovery_plan_is_bounded_and_preserves_cursor_order():
    plan = reconcile_run(run_row(sim_minute=100), events(*range(10)), max_recovery_events=3)
    assert [step["expected_cursor"] for step in plan["recovery_steps"]] == [0, 1, 2]
    assert plan["has_more_recovery"] is True

    exact = reconcile_run(run_row(sim_minute=100), events(1, 2, 3), max_recovery_events=3)
    assert exact["has_more_recovery"] is False


def test_day_89_drain_into_day_90_uses_absolute_simulated_time():
    residents = tuple(f"resident-{index:03d}" for index in range(1, 76))
    drained = [event for event in plan_first_24_hours(residents, day_index=89)
               if event.day_index == 90]
    assert drained
    plan = reconcile_run(
        run_row(sim_minute=max(event.absolute_minute for event in drained)),
        drained,
        max_recovery_events=100,
    )
    assert all(row["absolute_minute"] >= 90 * 1440 for row in plan["classified_events"])
    assert all(row["classification"] == "due_catch_up" for row in plan["classified_events"])
    assert [step["event_id"] for step in plan["recovery_steps"]] == [
        event.event_id for event in drained
    ]


def test_terminal_event_is_never_presented_as_recoverable_execution():
    rows = events(10, 20)
    rows[0]["terminal"] = True
    plan = reconcile_run(run_row(), rows)
    assert by_id(plan)["event-0"]["classification"] == "terminal"
    assert plan["recovery_steps"] == []


def test_last_event_id_and_cursor_must_agree():
    plan = reconcile_run(
        run_row(cursor=1, last_event_id="wrong"), events(10, 20), [receipt("event-0")]
    )
    assert plan["status"] == "inconsistent"
    assert "last_event_id" in plan["inconsistencies"][0]
