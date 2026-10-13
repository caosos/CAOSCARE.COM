"""Proof that routine tickets remain visible between accelerated runtime polls."""

from simulation.community_ticket_plan import (
    CLAIM_TO_COMPLETE_MINUTES,
    DEFAULT_ACCELERATION,
    OPEN_TO_CLAIM_MINUTES,
    RUNTIME_POLL_SECONDS,
    minimum_real_dwell_seconds,
    plan_ticket_phases,
)


def test_phases_have_distinct_absolute_minutes_and_poll_visible_dwell():
    opened, claimed, completed = plan_ticket_phases("routine-1", 3, 100)
    assert (opened.phase, claimed.phase, completed.phase) == ("open", "claim", "complete")
    assert claimed.absolute_minute - opened.absolute_minute == OPEN_TO_CLAIM_MINUTES
    assert completed.absolute_minute - claimed.absolute_minute == CLAIM_TO_COMPLETE_MINUTES
    assert minimum_real_dwell_seconds(
        OPEN_TO_CLAIM_MINUTES, DEFAULT_ACCELERATION,
    ) > RUNTIME_POLL_SECONDS
    assert minimum_real_dwell_seconds(
        CLAIM_TO_COMPLETE_MINUTES, DEFAULT_ACCELERATION,
    ) > RUNTIME_POLL_SECONDS


def test_phase_schedule_rolls_over_day_without_losing_total_order():
    opened, claimed, completed = plan_ticket_phases("routine-late", 9, 1437)
    assert (opened.day_index, opened.minute) == (9, 1437)
    assert (claimed.day_index, claimed.minute) == (10, 2)
    assert (completed.day_index, completed.minute) == (10, 12)
    assert opened.absolute_minute < claimed.absolute_minute < completed.absolute_minute
    assert len({opened.event_id, claimed.event_id, completed.event_id}) == 3
