"""Revisioned, deterministic 90-day living-community event timeline.

This is a pure planning boundary.  It combines the existing daily executor
queues, fingerprints their complete canonical content, and refuses duplicate,
reordered, truncated, or otherwise drifted plans.  It does not read storage,
call providers, expose routes, or claim that any event executed.
"""

from dataclasses import asdict, dataclass
from functools import lru_cache
from hashlib import sha256
import json
from typing import Iterable

from simulation.community_cohort import BURN_IN, FULL_COMMUNITY, residents_for
from simulation.community_executor import ExecutorEvent, build_day_queue


PLAN_REVISION_BASE = "living-community-timeline-v6"
# The revision names the cohort, so a run's persisted fingerprint says which
# residents it executes. The burn-in remains the default for pure builders.
PLAN_REVISIONS = {
    BURN_IN: f"{PLAN_REVISION_BASE}-{BURN_IN}",
    FULL_COMMUNITY: f"{PLAN_REVISION_BASE}-{FULL_COMMUNITY}",
}
PLAN_REVISION = PLAN_REVISIONS[BURN_IN]
TIMELINE_DAYS = 90
DIGEST_ALGORITHM = "sha256"


class TimelineValidationError(ValueError):
    """The supplied plan is not the exact canonical timeline revision."""


@dataclass(frozen=True)
class CommunityTimeline:
    plan_revision: str
    digest_algorithm: str
    digest_sha256: str
    source_start_day: int
    source_end_day: int
    day_count: int
    event_count: int
    events: tuple[ExecutorEvent, ...]
    cohort: str = BURN_IN

    @property
    def resident_count(self) -> int:
        return len(residents_for(self.cohort))


def cohort_of_revision(plan_revision: str) -> str:
    """The cohort a persisted plan revision belongs to (unknown -> error)."""
    for cohort, revision in PLAN_REVISIONS.items():
        if revision == plan_revision:
            return cohort
    raise TimelineValidationError("timeline plan revision is unsupported")


def event_sort_key(event: ExecutorEvent) -> tuple[int, str, str]:
    """The one stable total ordering used by build and validation."""
    return (
        event.day_index * 1440 + event.minute,
        event.stream_kind,
        event.event_id,
    )


def _event_payload(event: ExecutorEvent) -> dict:
    if not isinstance(event, ExecutorEvent):
        raise TimelineValidationError("timeline events must be ExecutorEvent values")
    return asdict(event)


def timeline_digest(
    events: Iterable[ExecutorEvent],
    *,
    plan_revision: str = PLAN_REVISION,
    day_count: int = TIMELINE_DAYS,
    cohort: str = BURN_IN,
) -> str:
    """Hash all plan metadata and event fields using canonical JSON."""
    rows = tuple(events)
    payload = {
        "cohort": cohort,
        "day_count": day_count,
        "events": [_event_payload(event) for event in rows],
        "plan_revision": plan_revision,
        "source_end_day": day_count - 1,
        "source_start_day": 0,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@lru_cache(maxsize=None)
def _canonical_events(cohort: str = BURN_IN) -> tuple[ExecutorEvent, ...]:
    """Built once per cohort per process; plans are immutable."""
    events = tuple(
        event
        for day_index in range(TIMELINE_DAYS)
        for event in build_day_queue(day_index, cohort=cohort)
    )
    return tuple(sorted(events, key=event_sort_key))


def _validate_shape(plan: CommunityTimeline) -> None:
    if not isinstance(plan, CommunityTimeline):
        raise TimelineValidationError("plan must be a CommunityTimeline")
    if plan.cohort not in PLAN_REVISIONS or plan.plan_revision != PLAN_REVISIONS[plan.cohort]:
        raise TimelineValidationError("timeline plan revision is unsupported")
    if plan.digest_algorithm != DIGEST_ALGORITHM:
        raise TimelineValidationError("timeline digest algorithm is unsupported")
    if (
        plan.source_start_day != 0
        or plan.source_end_day != TIMELINE_DAYS - 1
        or plan.day_count != TIMELINE_DAYS
    ):
        raise TimelineValidationError("timeline must contain source days 0 through 89")
    if plan.event_count != len(plan.events):
        raise TimelineValidationError("timeline event_count does not match its events")
    event_ids = [event.event_id for event in plan.events]
    if len(set(event_ids)) != len(event_ids):
        raise TimelineValidationError("timeline contains duplicate event IDs")
    if tuple(sorted(plan.events, key=event_sort_key)) != plan.events:
        raise TimelineValidationError("timeline events are not in canonical order")
    digest = _digest_for(plan)
    if plan.digest_sha256 != digest:
        raise TimelineValidationError("timeline digest does not match its content")


def validate_timeline(plan: CommunityTimeline) -> CommunityTimeline:
    """Fail closed unless ``plan`` exactly matches the current daily planners."""
    _validate_shape(plan)
    expected = _canonical_events(plan.cohort)
    if plan.events is not expected and plan.events != expected:
        raise TimelineValidationError(
            "timeline content drifted from the canonical daily planners; "
            "review the change and advance PLAN_REVISION"
        )
    return plan


@lru_cache(maxsize=None)
def _canonical_digest(cohort: str) -> str:
    """Hashed once per cohort: canonical events and metadata never change."""
    return timeline_digest(
        _canonical_events(cohort), plan_revision=PLAN_REVISIONS[cohort],
        day_count=TIMELINE_DAYS, cohort=cohort,
    )


def _digest_for(plan: CommunityTimeline) -> str:
    # Only the cached canonical tuple with canonical metadata may reuse the
    # cached digest; any other plan (tampered or rebuilt) is hashed in full.
    if (plan.events is _canonical_events(plan.cohort)
            and plan.plan_revision == PLAN_REVISIONS[plan.cohort]
            and plan.day_count == TIMELINE_DAYS):
        return _canonical_digest(plan.cohort)
    return timeline_digest(plan.events, plan_revision=plan.plan_revision,
                           day_count=plan.day_count, cohort=plan.cohort)


def build_90_day_timeline(cohort: str = BURN_IN) -> CommunityTimeline:
    """Build the exact source-day 0..89 plan without performing any action."""
    residents_for(cohort)
    events = _canonical_events(cohort)
    plan = CommunityTimeline(
        plan_revision=PLAN_REVISIONS[cohort],
        digest_algorithm=DIGEST_ALGORITHM,
        digest_sha256=_canonical_digest(cohort),
        source_start_day=0,
        source_end_day=TIMELINE_DAYS - 1,
        day_count=TIMELINE_DAYS,
        event_count=len(events),
        events=events,
        cohort=cohort,
    )
    _validate_shape(plan)
    return plan
