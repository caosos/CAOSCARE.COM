"""Durable read and clock adapters for the living-community runner.

The timeline side performs read-only Mongo-shaped queries and returns the one
canonical, revisioned event stream.  The clock side delegates its only write
to ``community_run_lifecycle`` so the simulated-time mutation and provenance
receipt remain atomic.  No database, route, loop, provider, or startup hook is
selected here; callers inject storage and invoke these adapters explicitly.
"""

from datetime import datetime, timezone
from functools import lru_cache
import math
from typing import Optional

from routes.actor_context import ActorContext
from simulation import community_run_lifecycle as lifecycle
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_timeline import (
    CommunityTimeline,
    build_90_day_timeline,
    validate_timeline,
)


class CommunityRunnerTimelineError(RuntimeError):
    """Persisted state cannot prove one canonical community-run timeline."""


@lru_cache(maxsize=1)
def canonical_plan() -> CommunityTimeline:
    """Build and validate the current immutable 90-day plan once per process."""
    return validate_timeline(build_90_day_timeline())


def _text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommunityRunnerTimelineError(f"{label} must be non-empty text")
    return value.strip()


def _integer(value, label: str, *, maximum: Optional[int] = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CommunityRunnerTimelineError(f"{label} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise CommunityRunnerTimelineError(f"{label} exceeds the canonical plan")
    return value


def _validated_plan(plan: Optional[CommunityTimeline]) -> CommunityTimeline:
    try:
        return validate_timeline(plan or canonical_plan())
    except (TypeError, ValueError) as exc:
        raise CommunityRunnerTimelineError("canonical timeline validation failed") from exc


def _validate_run(row: dict, run_id: str, plan: CommunityTimeline) -> dict:
    if not isinstance(row, dict) or row.get("run_id") != run_id:
        raise CommunityRunnerTimelineError("storage did not return the exact requested run")
    expected = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": lifecycle.RUN_KIND,
        "plan_revision": plan.plan_revision,
        "plan_digest_sha256": plan.digest_sha256,
        "event_count": plan.event_count,
        "timeline_end_minute": plan.day_count * 1440 - 1,
    }
    if any(row.get(key) != value for key, value in expected.items()):
        raise CommunityRunnerTimelineError(
            "persisted run scope, community, kind, or plan fingerprint is invalid"
        )
    _integer(row.get("cursor"), "run cursor", maximum=plan.event_count)
    sim_minute = _integer(row.get("sim_minute"), "run simulated minute")
    terminal_minute = plan.day_count * 1440
    if sim_minute > terminal_minute:
        raise CommunityRunnerTimelineError("run simulated minute exceeds the canonical plan")
    if sim_minute == terminal_minute and not (
        row.get("state") == lifecycle.STOPPED
        and row.get("cursor") == plan.event_count
        and row.get("terminal_reason") == "completed"
        and isinstance(row.get("completion_receipt_id"), str)
        and row["completion_receipt_id"].strip()
    ):
        raise CommunityRunnerTimelineError(
            "only a receipt-backed completed run may reach the terminal minute"
        )
    return dict(row)


async def _rows(
    collection, query: dict, projection: dict, *, limit: Optional[int] = None,
) -> list[dict]:
    cursor = collection.find(query, projection)
    return await cursor.to_list(limit)


class DatabaseRunnerTimeline:
    """Read one exact run, its canonical events, and its event receipts."""

    def __init__(self, *, store, plan: Optional[CommunityTimeline] = None):
        self.store = store
        self.plan = _validated_plan(plan)

    async def load_run(self, *, run_id: str) -> dict:
        run_id = _text(run_id, "run_id")
        rows = await _rows(
            self.store.sim_runs, {"run_id": run_id}, {"_id": 0}, limit=2,
        )
        if len(rows) != 1:
            raise CommunityRunnerTimelineError(
                "the requested run is missing or ambiguous"
            )
        return _validate_run(rows[0], run_id, self.plan)

    async def load_events(self, *, run_id: str):
        await self.load_run(run_id=run_id)
        return self.plan.events

    @property
    def event_count(self) -> int:
        return self.plan.event_count

    def event_at(self, cursor: int):
        cursor = _integer(cursor, "event cursor", maximum=self.plan.event_count)
        return None if cursor == self.plan.event_count else self.plan.events[cursor]

    async def load_bounded_evidence(
        self, *, run_id: str, cursor: int, event_id: Optional[str],
        last_event_id: Optional[str], last_receipt_id: Optional[str],
    ) -> dict:
        """Read at most two current, one prior, and one future receipt.

        The OR on current event/cursor intentionally exposes a mismatch rather
        than hiding it.  The future sentinel proves that execution cannot cross
        an unresolved cursor gap.  Every read is bound to one run and the exact
        simulator scope/community.  Queries intentionally surface malformed
        same-run evidence so it cannot be hidden by a bad provenance field.
        """
        run_id = _text(run_id, "run_id")
        cursor = _integer(cursor, "receipt cursor", maximum=self.plan.event_count)
        run_scope = {"simulation_run_id": run_id}
        clauses = [{"execution_cursor": cursor}]
        if event_id is not None:
            clauses.insert(0, {"simulation_event_id": _text(event_id, "event_id")})
        current = tuple(await _rows(
            self.store.receipts,
            {**run_scope, "$or": clauses},
            {"_id": 0},
            limit=2,
        ))
        future = tuple(await _rows(
            self.store.receipts,
            {**run_scope, "simulation_event_id": {"$exists": True},
             "execution_cursor": {"$gt": cursor}},
            {"_id": 0},
            limit=1,
        ))
        previous = ()
        if cursor:
            prior_receipt = _text(last_receipt_id, "last receipt_id")
            prior_event = _text(last_event_id, "last event_id")
            previous = tuple(await _rows(
                self.store.receipts,
                {**run_scope, "$or": [
                    {"receipt_id": prior_receipt},
                    {"simulation_event_id": prior_event,
                     "execution_cursor": cursor - 1},
                ]},
                {"_id": 0},
                limit=2,
            ))
        window = {"current": current, "previous": previous, "future": future}
        for rows in window.values():
            for row in rows:
                if (
                    row.get("simulation_run_id") != run_id
                    or row.get("simulation_scope") != SIMULATION_SCOPE
                    or row.get("simulation_community_id") != COMMUNITY_ID
                ):
                    raise CommunityRunnerTimelineError(
                        "bounded event evidence has invalid run, scope, or community provenance"
                    )
        return window

    async def load_receipts(self, *, run_id: str):
        run = await self.load_run(run_id=run_id)
        query = {
            "simulation_run_id": run["run_id"],
            "simulation_event_id": {"$exists": True},
        }
        # Include terminal and nonterminal event receipts. Reconciliation must
        # see a nonterminal or duplicate record so it can fail closed rather
        # than replaying an ambiguously attempted event.
        rows = tuple(await _rows(self.store.receipts, query, {"_id": 0}))
        for row in rows:
            if (
                row.get("simulation_run_id") != run["run_id"]
                or row.get("simulation_scope") != SIMULATION_SCOPE
                or row.get("simulation_community_id") != COMMUNITY_ID
            ):
                raise CommunityRunnerTimelineError(
                    "event receipt has invalid run, scope, or community provenance"
                )
        return rows


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CommunityRunnerTimelineError("observed_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _persisted_time(value) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CommunityRunnerTimelineError("run clock anchor is invalid") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CommunityRunnerTimelineError("run clock anchor must be timezone-aware")
    return value.astimezone(timezone.utc)


class PersistedRunClock:
    """Advance simulated time from the persisted run update timestamp."""

    def __init__(self, *, store, plan: Optional[CommunityTimeline] = None):
        self.store = store
        self.plan = _validated_plan(plan)
        self.actor = ActorContext(
            actor_id=lifecycle.CLOCK_ACTOR_ID,
            actor_type="system",
            identity_basis="system",
            channel="system",
            name="Living Community Runner",
            role="system",
            simulated=False,
        )

    async def __call__(
        self, *, run_id: str, observed_run: dict, observed_at: datetime,
        acceleration: float, horizon_minutes: int,
    ) -> dict:
        run_id = _text(run_id, "run_id")
        row = _validate_run(observed_run, run_id, self.plan)
        now = _utc(observed_at)
        if (
            isinstance(acceleration, bool)
            or not isinstance(acceleration, (int, float))
            or not math.isfinite(acceleration)
            or acceleration <= 0
        ):
            raise CommunityRunnerTimelineError("acceleration must be finite and positive")
        if horizon_minutes != self.plan.day_count * 1440:
            raise CommunityRunnerTimelineError("clock horizon must match the canonical plan")
        if row.get("state") != lifecycle.RUNNING:
            return row

        # Measure from when sim_minute was last set, not from updated_at: every
        # lease acquire/heartbeat/release also refreshes updated_at, which would
        # reset the anchor each poll and freeze the clock. Rows written before
        # sim_clock_at existed fall back to updated_at.
        anchor = _persisted_time(row.get("sim_clock_at") or row.get("updated_at"))
        elapsed = (now - anchor).total_seconds()
        if elapsed < 0:
            raise CommunityRunnerTimelineError("run clock anchor is later than observed_at")
        advance = int(elapsed * float(acceleration) / 60.0)
        last_minute = self.plan.day_count * 1440 - 1
        next_minute = min(last_minute, row["sim_minute"] + advance)
        if next_minute <= row["sim_minute"]:
            return row

        key = (
            f"clock:{run_id}:{row['cursor']}:{row['sim_minute']}:"
            f"{next_minute}:{anchor.isoformat()}"
        )
        result = await lifecycle.advance_simulated_clock(
            self.actor,
            f"simulation_run:{run_id}:clock",
            run_id,
            row["cursor"],
            row["sim_minute"],
            next_minute,
            key,
            self.plan,
            store=self.store,
            now=now,
        )
        return result["run"]
