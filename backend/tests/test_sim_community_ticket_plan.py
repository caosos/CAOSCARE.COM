"""Proof that routine tickets remain visible between accelerated runtime polls."""

from simulation.community_ticket_plan import (
    CLAIM_TO_COMPLETE_MINUTES,
    DEFAULT_ACCELERATION,
    OPEN_TO_CLAIM_MINUTES,
    ROUTINE_WORK_MINUTES,
    RUNTIME_POLL_SECONDS,
    minimum_real_dwell_seconds,
    work_minutes,
)


def test_every_dwell_spans_more_than_one_runtime_poll():
    shortest = min(OPEN_TO_CLAIM_MINUTES, CLAIM_TO_COMPLETE_MINUTES, *ROUTINE_WORK_MINUTES.values())
    assert minimum_real_dwell_seconds(shortest, DEFAULT_ACCELERATION) > RUNTIME_POLL_SECONDS


def test_work_minutes_are_explicit_per_routine_with_a_default():
    assert work_minutes("breakfast") == 3
    assert work_minutes("shower_assistance") == 20
    assert work_minutes("preventive_maintenance_check") == CLAIM_TO_COMPLETE_MINUTES
