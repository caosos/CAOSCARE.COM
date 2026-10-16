"""Focused proofs for the durable community runner adapters."""

import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from simulation import community_run_lifecycle as lifecycle
from simulation import community_runner_timeline as adapter
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_timeline import build_90_day_timeline


PLAN = build_90_day_timeline()
NOW = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc)
RUN_ID = "simrun:living:test"


def run_row(**changes):
    row = {
        "run_id": RUN_ID,
        "state": "RUNNING",
        "cursor": 12,
        "sim_minute": 100,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": lifecycle.RUN_KIND,
        "plan_revision": PLAN.plan_revision,
        "plan_digest_sha256": PLAN.digest_sha256,
        "event_count": PLAN.event_count,
        "timeline_end_minute": PLAN.day_count * 1440 - 1,
        "updated_at": (NOW - timedelta(seconds=2)).isoformat(),
    }
    row.update(changes)
    return row


def receipt(event_id, **changes):
    row = {
        "receipt_id": f"receipt:{event_id}",
        "simulation_run_id": RUN_ID,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "simulation_event_id": event_id,
        "status": "completed",
    }
    row.update(changes)
    return row


def matches(row, query):
    for key, wanted in query.items():
        if key == "$or":
            if not any(matches(row, clause) for clause in wanted):
                return False
            continue
        if isinstance(wanted, dict) and "$exists" in wanted:
            if (key in row) != wanted["$exists"]:
                return False
        elif isinstance(wanted, dict) and "$gt" in wanted:
            if row.get(key) is None or row[key] <= wanted["$gt"]:
                return False
        elif row.get(key) != wanted:
            return False
    return True


class Cursor:
    def __init__(self, rows, limits):
        self.rows = rows
        self.limits = limits

    async def to_list(self, limit):
        self.limits.append(limit)
        rows = self.rows if limit is None else self.rows[:limit]
        return deepcopy(rows)


class Collection:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []
        self.limits = []

    def find(self, query, projection):
        self.queries.append(deepcopy(query))
        selected = []
        for source in self.rows:
            if not matches(source, query):
                continue
            if projection:
                row = {key: value for key, value in source.items()
                       if projection.get(key, 1) and key != "_id"}
            else:
                row = dict(source)
            selected.append(row)
        return Cursor(selected, self.limits)


class Store:
    def __init__(self, runs=None, receipts=None):
        self.sim_runs = Collection(list(runs or []))
        self.receipts = Collection(list(receipts or []))


def test_reads_exact_run_canonical_stream_and_only_exact_event_receipts():
    async def case():
        first, second = PLAN.events[:2]
        store = Store([run_row()], [
            receipt(first.event_id),
            receipt(second.event_id, status="attempted"),
            receipt("wrong-run", simulation_run_id="other"),
            {"receipt_id": "lifecycle", "simulation_run_id": RUN_ID},
        ])
        timeline = adapter.DatabaseRunnerTimeline(store=store, plan=PLAN)
        loaded_run = await timeline.load_run(run_id=RUN_ID)
        events = await timeline.load_events(run_id=RUN_ID)
        receipts = await timeline.load_receipts(run_id=RUN_ID)
        assert loaded_run["run_id"] == RUN_ID
        assert events == PLAN.events and len(events) == PLAN.event_count
        assert [row["simulation_event_id"] for row in receipts] == [
            first.event_id, second.event_id,
        ]
        assert receipts[1]["status"] == "attempted"
    asyncio.run(case())


def test_event_receipt_with_wrong_scope_is_not_silently_ignored():
    async def case():
        event_id = PLAN.events[0].event_id
        timeline = adapter.DatabaseRunnerTimeline(
            store=Store(
                [run_row()],
                [receipt(event_id, simulation_scope="other")],
            ),
            plan=PLAN,
        )
        with pytest.raises(adapter.CommunityRunnerTimelineError, match="provenance"):
            await timeline.load_receipts(run_id=RUN_ID)
    asyncio.run(case())


def test_cursor_evidence_reads_are_exact_and_strictly_bounded():
    async def case():
        prior_event, current_event, future_event = PLAN.events[11:14]
        prior = receipt(
            prior_event.event_id, receipt_id="receipt:prior", execution_cursor=11,
        )
        exact = receipt(current_event.event_id, execution_cursor=12)
        cursor_mismatch = receipt(
            "wrong-event", receipt_id="receipt:mismatch", execution_cursor=12,
        )
        future = receipt(future_event.event_id, execution_cursor=13)
        store = Store([run_row()], [prior, exact, cursor_mismatch, future])
        timeline = adapter.DatabaseRunnerTimeline(store=store, plan=PLAN)
        window = await timeline.load_bounded_evidence(
            run_id=RUN_ID, cursor=12, event_id=current_event.event_id,
            last_event_id=prior_event.event_id, last_receipt_id="receipt:prior",
        )
        assert len(window["current"]) == 2
        assert [row["receipt_id"] for row in window["future"]] == [
            future["receipt_id"],
        ]
        assert [row["receipt_id"] for row in window["previous"]] == [
            "receipt:prior",
        ]
        assert store.receipts.limits == [2, 1, 2]
        for query in store.receipts.queries:
            assert query["simulation_run_id"] == RUN_ID

    asyncio.run(case())


@pytest.mark.parametrize("coordinate", ["current", "future"])
def test_bounded_evidence_surfaces_wrong_scope_instead_of_replaying(coordinate):
    async def case():
        current_event, future_event = PLAN.events[12:14:1]
        row = receipt(
            current_event.event_id if coordinate == "current" else future_event.event_id,
            execution_cursor=12 if coordinate == "current" else 13,
            simulation_scope="wrong",
        )
        timeline = adapter.DatabaseRunnerTimeline(
            store=Store([run_row(cursor=12)], [row]), plan=PLAN,
        )
        with pytest.raises(adapter.CommunityRunnerTimelineError, match="provenance"):
            await timeline.load_bounded_evidence(
                run_id=RUN_ID, cursor=12, event_id=current_event.event_id,
                last_event_id=PLAN.events[11].event_id,
                last_receipt_id="receipt:prior",
            )

    asyncio.run(case())


@pytest.mark.parametrize("runs", [[], [run_row(), run_row()]])
def test_missing_or_ambiguous_run_is_refused(runs):
    async def case():
        timeline = adapter.DatabaseRunnerTimeline(store=Store(runs), plan=PLAN)
        with pytest.raises(adapter.CommunityRunnerTimelineError, match="missing or ambiguous"):
            await timeline.load_run(run_id=RUN_ID)
    asyncio.run(case())


@pytest.mark.parametrize("change", [
    {"simulation_scope": "other"},
    {"simulation_community_id": "other"},
    {"run_kind": "other"},
    {"plan_revision": "other"},
    {"plan_digest_sha256": "0" * 64},
    {"event_count": 1},
    {"timeline_end_minute": 1},
    {"cursor": PLAN.event_count + 1},
    {"sim_minute": PLAN.day_count * 1440},
])
def test_scope_plan_and_coordinates_fail_closed(change):
    async def case():
        timeline = adapter.DatabaseRunnerTimeline(
            store=Store([run_row(**change)]), plan=PLAN,
        )
        with pytest.raises(adapter.CommunityRunnerTimelineError):
            await timeline.load_events(run_id=RUN_ID)
    asyncio.run(case())


def test_receipt_backed_completed_run_may_use_terminal_boundary_minute():
    async def case():
        completed = run_row(
            state="STOPPED", cursor=PLAN.event_count,
            sim_minute=PLAN.day_count * 1440,
            terminal_reason="completed", completion_receipt_id="receipt:complete",
        )
        timeline = adapter.DatabaseRunnerTimeline(
            store=Store([completed]), plan=PLAN,
        )
        assert (await timeline.load_run(run_id=RUN_ID))["sim_minute"] == 129600
    asyncio.run(case())


def test_noncanonical_injected_plan_is_refused_before_storage_read():
    bad = replace(PLAN, digest_sha256="0" * 64)
    with pytest.raises(adapter.CommunityRunnerTimelineError, match="validation"):
        adapter.DatabaseRunnerTimeline(store=Store(), plan=bad)


def test_persisted_clock_calls_lifecycle_with_exact_system_provenance(monkeypatch):
    async def case():
        calls = []

        async def advance(*args, **kwargs):
            calls.append((args, kwargs))
            changed = dict(row)
            changed["sim_minute"] = args[5]
            changed["updated_at"] = kwargs["now"].isoformat()
            return {"run": changed, "receipt": {"status": "completed"}}

        monkeypatch.setattr(lifecycle, "advance_simulated_clock", advance)
        clock = adapter.PersistedRunClock(store=Store(), plan=PLAN)
        result = await clock(
            run_id=RUN_ID, observed_run=row, observed_at=NOW,
            acceleration=60.0, horizon_minutes=90 * 24 * 60,
        )
        args, kwargs = calls[0]
        actor = args[0]
        assert actor.actor_id == lifecycle.CLOCK_ACTOR_ID
        assert actor.actor_type == actor.identity_basis == actor.channel == "system"
        assert actor.simulated is False
        assert args[1] == f"simulation_run:{RUN_ID}:clock"
        assert args[2:6] == (RUN_ID, 12, 100, 102)
        assert args[7] is PLAN
        assert kwargs == {"store": clock.store, "now": NOW}
        assert result["sim_minute"] == 102

    row = run_row()
    asyncio.run(case())


def test_clock_noop_cap_and_invalid_inputs(monkeypatch):
    async def case():
        calls = []

        async def advance(*args, **kwargs):
            calls.append((args, kwargs))
            changed = dict(capped)
            changed["sim_minute"] = args[5]
            return {"run": changed}

        monkeypatch.setattr(lifecycle, "advance_simulated_clock", advance)
        clock = adapter.PersistedRunClock(store=Store(), plan=PLAN)
        quiet = run_row(updated_at=(NOW - timedelta(milliseconds=500)).isoformat())
        assert (await clock(
            run_id=RUN_ID, observed_run=quiet, observed_at=NOW,
            acceleration=60, horizon_minutes=129600,
        ))["sim_minute"] == 100
        assert calls == []

        result = await clock(
            run_id=RUN_ID, observed_run=capped, observed_at=NOW,
            acceleration=3600, horizon_minutes=129600,
        )
        assert result["sim_minute"] == PLAN.day_count * 1440 - 1
        assert calls[0][0][5] == PLAN.day_count * 1440 - 1

        with pytest.raises(adapter.CommunityRunnerTimelineError, match="horizon"):
            await clock(
                run_id=RUN_ID, observed_run=quiet, observed_at=NOW,
                acceleration=60, horizon_minutes=1,
            )
        future = run_row(updated_at=(NOW + timedelta(seconds=1)).isoformat())
        with pytest.raises(adapter.CommunityRunnerTimelineError, match="later"):
            await clock(
                run_id=RUN_ID, observed_run=future, observed_at=NOW,
                acceleration=60, horizon_minutes=129600,
            )

    capped = run_row(
        sim_minute=PLAN.day_count * 1440 - 2,
        updated_at=(NOW - timedelta(seconds=10)).isoformat(),
    )
    asyncio.run(case())


def test_clock_measures_from_sim_clock_anchor_not_lease_bookkeeping(monkeypatch):
    """SIM-003 (real Mongo): every lease acquire/heartbeat/release refreshes
    updated_at, so a clock anchored there never advanced while the loop polled.
    The anchor is sim_clock_at, written only when sim_minute is set."""
    async def case():
        calls = []

        async def advance(*args, **kwargs):
            calls.append(args)
            return {"run": {**row, "sim_minute": args[5]}}

        monkeypatch.setattr(lifecycle, "advance_simulated_clock", advance)
        clock = adapter.PersistedRunClock(store=Store(), plan=PLAN)
        result = await clock(
            run_id=RUN_ID, observed_run=row, observed_at=NOW,
            acceleration=60.0, horizon_minutes=90 * 24 * 60,
        )
        assert calls and calls[0][2:6] == (RUN_ID, 12, 100, 110)
        assert result["sim_minute"] == 110

    row = run_row(
        updated_at=(NOW - timedelta(milliseconds=200)).isoformat(),  # lease write just now
        sim_clock_at=(NOW - timedelta(seconds=10)).isoformat(),      # clock last set 10 s ago
    )
    asyncio.run(case())
