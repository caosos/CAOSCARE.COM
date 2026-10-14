"""Revisioned, deterministic 90-day living-community event timeline.

This is a pure planning boundary.  It combines the existing daily executor
queues, fingerprints their complete canonical content, and refuses duplicate,
reordered, truncated, or otherwise drifted plans.  It does not read storage,
call providers, expose routes, or claim that any event executed.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable

from simulation.community_executor import ExecutorEvent, build_day_queue


PLAN_REVISION = "living-community-timeline-v4-realistic-staffing"
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
) -> str:
    """Hash all plan metadata and event fields using canonical JSON."""
    rows = tuple(events)
    payload = {
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


def _canonical_events() -> tuple[ExecutorEvent, ...]:
    events = tuple(
        event
        for day_index in range(TIMELINE_DAYS)
        for event in build_day_queue(day_index)
    )
    return tuple(sorted(events, key=event_sort_key))


def _validate_shape(plan: CommunityTimeline) -> None:
    if not isinstance(plan, CommunityTimeline):
        raise TimelineValidationError("plan must be a CommunityTimeline")
    if plan.plan_revision != PLAN_REVISION:
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
    digest = timeline_digest(
        plan.events,
        plan_revision=plan.plan_revision,
        day_count=plan.day_count,
    )
    if plan.digest_sha256 != digest:
        raise TimelineValidationError("timeline digest does not match its content")


def validate_timeline(plan: CommunityTimeline) -> CommunityTimeline:
    """Fail closed unless ``plan`` exactly matches the current daily planners."""
    _validate_shape(plan)
    expected = _canonical_events()
    if plan.events != expected:
        raise TimelineValidationError(
            "timeline content drifted from the canonical daily planners; "
            "review the change and advance PLAN_REVISION"
        )
    return plan


def build_90_day_timeline() -> CommunityTimeline:
    """Build the exact source-day 0..89 plan without performing any action."""
    events = _canonical_events()
    plan = CommunityTimeline(
        plan_revision=PLAN_REVISION,
        digest_algorithm=DIGEST_ALGORITHM,
        digest_sha256=timeline_digest(events),
        source_start_day=0,
        source_end_day=TIMELINE_DAYS - 1,
        day_count=TIMELINE_DAYS,
        event_count=len(events),
        events=events,
    )
    _validate_shape(plan)
    return plan
