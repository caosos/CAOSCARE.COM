"""Focused proof for the pure revisioned living-community timeline."""

from collections import Counter
from dataclasses import replace

import pytest

from simulation import community_timeline as timeline


EXPECTED_EVENT_COUNT = 52_873
EXPECTED_DIGEST = "798135a8a1de9053b28da1baf3764204008e3b20c3b987dbb004cf9051a97969"


@pytest.fixture(scope="module")
def plan():
    return timeline.build_90_day_timeline()


def test_builds_exact_stable_90_day_plan(plan):
    again = timeline.build_90_day_timeline()

    assert plan == again
    assert plan.plan_revision == "living-community-timeline-v9-plan-realism-burn_in_10"
    assert plan.digest_algorithm == "sha256"
    assert plan.source_start_day == 0
    assert plan.source_end_day == 89
    assert plan.day_count == 90
    assert plan.event_count == EXPECTED_EVENT_COUNT
    assert plan.digest_sha256 == EXPECTED_DIGEST
    assert timeline.validate_timeline(plan) is plan


def test_ids_are_unique_and_stream_counts_are_exact(plan):
    ids = [event.event_id for event in plan.events]
    assert len(ids) == len(set(ids))
    assert Counter(event.stream_kind for event in plan.events) == {
        "routine_ticket_phase": 45_853,  # rounds + resident calls + staff reports
        "canonical_shift_milestone": 7_020,  # 26 on-site shifts x 3 milestones x 90 days
    }

    # Every day carries its rounds plus that day's resident calls and staff
    # reports; the call volume varies by day but is fixed by the plan.
    per_day = [sum(event.event_id.startswith(f"day-{day_index:03d}:") for event in plan.events)
               for day_index in range(90)]
    assert min(per_day) == 502 and max(per_day) == 510


def test_timeline_uses_one_exact_total_order(plan):
    assert plan.events == tuple(sorted(plan.events, key=timeline.event_sort_key))
    assert all(
        timeline.event_sort_key(left) < timeline.event_sort_key(right)
        for left, right in zip(plan.events, plan.events[1:])
    )


def test_duplicate_ids_are_refused_before_digest_drift(plan):
    duplicated = replace(plan, events=(plan.events[0],) + plan.events)
    duplicated = replace(duplicated, event_count=len(duplicated.events))
    with pytest.raises(timeline.TimelineValidationError, match="duplicate event IDs"):
        timeline.validate_timeline(duplicated)


def test_reordered_events_are_refused(plan):
    reordered = replace(
        plan,
        events=(plan.events[1], plan.events[0], *plan.events[2:]),
    )
    reordered = replace(
        reordered,
        digest_sha256=timeline.timeline_digest(reordered.events),
    )
    with pytest.raises(timeline.TimelineValidationError, match="canonical order"):
        timeline.validate_timeline(reordered)


def test_content_drift_is_refused_even_with_a_matching_new_digest(plan):
    changed_event = replace(plan.events[0], actor_name="SIM - Drifted Worker")
    changed = replace(plan, events=(changed_event, *plan.events[1:]))
    changed = replace(
        changed,
        digest_sha256=timeline.timeline_digest(changed.events),
    )
    with pytest.raises(timeline.TimelineValidationError, match="content drifted"):
        timeline.validate_timeline(changed)


@pytest.mark.parametrize("changes", [
    {"day_count": 89},
    {"source_start_day": 1},
    {"source_end_day": 90},
])
def test_any_non_90_day_shape_is_refused(plan, changes):
    with pytest.raises(timeline.TimelineValidationError, match="source days 0 through 89"):
        timeline.validate_timeline(replace(plan, **changes))


def test_revision_and_digest_tampering_are_refused(plan):
    with pytest.raises(timeline.TimelineValidationError, match="revision"):
        timeline.validate_timeline(replace(plan, plan_revision="other"))
    with pytest.raises(timeline.TimelineValidationError, match="digest"):
        timeline.validate_timeline(replace(plan, digest_sha256="0" * 64))
