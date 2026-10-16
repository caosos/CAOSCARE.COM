"""Focused orchestration proofs for unregistered community controls."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from routes.actor_context import ActorContext
from simulation import community_run_lifecycle as lifecycle
from simulation import community_runner
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation import community_control_service as control_module
from simulation.community_control_service import CommunityControlError, CommunityControlService
from simulation.community_timeline import build_90_day_timeline


NOW = datetime(2026, 10, 13, 20, 30, tzinfo=timezone.utc)
PLAN = build_90_day_timeline()
RUN_ID = "simrun:living:control-test"
OWNER = ActorContext(
    "owner-1", "real-human", "authenticated", "staff_ui",
    name="Michael", role="owner",
)
AUTHORITY = "admin_override:owner"


def row(**changes):
    value = {
        "run_id": RUN_ID,
        "state": "PAUSED",
        "cursor": 0,
        "sim_minute": 0,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": lifecycle.RUN_KIND,
        "plan_revision": PLAN.plan_revision,
        "plan_digest_sha256": PLAN.digest_sha256,
        "event_count": PLAN.event_count,
        "timeline_end_minute": PLAN.day_count * 1440 - 1,
        "updated_at": NOW.isoformat(),
    }
    value.update(changes)
    return value


def readiness(value):
    return {
        "run_id": value["run_id"],
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "plan_revision": PLAN.plan_revision,
        "plan_digest_sha256": PLAN.digest_sha256,
        "cursor": value["cursor"],
        "sim_minute": value["sim_minute"],
        "resident_count": 10,
        "department_digest": "departments-exact",
    }


class Timeline:
    def __init__(self, value=None, events=None):
        self.row = row() if value is None else value
        self.events = tuple(events or PLAN.events)

    async def load_run(self, *, run_id):
        assert run_id == RUN_ID
        return deepcopy(self.row)

    async def load_events(self, *, run_id):
        assert run_id == RUN_ID
        return self.events


class Loop:
    def __init__(self, timeline, *, starts=True, move_on_cancel=None):
        self.timeline = timeline
        self.starts = starts
        self.move_on_cancel = move_on_cancel
        self.calls = []

    def start(self, run_id, holder_id):
        self.calls.append(("start", run_id, holder_id))
        return self.starts

    def wake(self, run_id):
        self.calls.append(("wake", run_id))

    async def cancel(self, run_id):
        self.calls.append(("cancel", run_id))
        if self.move_on_cancel:
            self.timeline.row.update(self.move_on_cancel)
        self.timeline.row.pop("execution_lease", None)
        return {"phase": "cancelled"}


def service(timeline, loop, *, guard=None, manual_step=None, tick=None):
    async def ready(*, store, run):
        return readiness(run)

    return CommunityControlService(
        store=object(), plan=PLAN, timeline=timeline, services=object(),
        loop_manager=loop, start_guard=guard or ready,
        manual_step=manual_step or control_module.community_manual_step.execute_one,
        tick=tick or community_runner.tick,
        clock=lambda: NOW,
    )


def test_create_paused_delegates_to_atomic_lifecycle(monkeypatch):
    async def case():
        calls = []

        async def create(*args, **kwargs):
            calls.append((args, kwargs))
            return {"run": row(), "receipt": {"receipt_id": "create"}}

        monkeypatch.setattr(lifecycle, "create_burn_in_run", create)
        timeline = Timeline()
        result = await service(timeline, Loop(timeline)).create_paused(
            OWNER, AUTHORITY, "create-key", now=NOW,
        )
        args, kwargs = calls[0]
        assert args[:3] == (OWNER, AUTHORITY, "create-key")
        assert args[3] is PLAN
        assert kwargs["now"] == NOW and kwargs["store"] is not None
        assert result["receipt"]["receipt_id"] == "create"

    asyncio.run(case())


def test_provision_residents_delegates_exact_position_to_atomic_boundary(monkeypatch):
    async def case():
        calls = []

        async def provision(*args, **kwargs):
            calls.append((args, kwargs))
            return {"run": row(residents_provisioned=True),
                    "receipt": {"receipt_id": "ready"}}

        monkeypatch.setattr(control_module, "provision_paused_burn_in_run", provision)
        timeline = Timeline(row(cursor=8, sim_minute=500))
        control = service(timeline, Loop(timeline))
        result = await control.provision_residents(
            OWNER, AUTHORITY, RUN_ID, 8, 500, "provision-key", now=NOW,
        )
        args, kwargs = calls[0]
        assert args[:7] == (
            OWNER, AUTHORITY, RUN_ID, 8, 500, "provision-key", PLAN,
        )
        assert kwargs == {"store": control.store, "now": NOW}
        assert result["receipt"]["receipt_id"] == "ready"

    asyncio.run(case())


def test_resume_reserves_loop_then_receipt_transitions_and_wakes(monkeypatch):
    async def case():
        timeline, calls = Timeline(row(cursor=4, sim_minute=60)), []
        loop = Loop(timeline)

        async def transition(*args, **kwargs):
            calls.append((args, kwargs))
            timeline.row["state"] = "RUNNING"
            return {"run": deepcopy(timeline.row), "receipt": {"receipt_id": "resume"}}

        monkeypatch.setattr(lifecycle, "transition_run", transition)
        result = await service(timeline, loop).resume_and_start(
            OWNER, AUTHORITY, RUN_ID, 4, 60, "resume-key", "loop-1", now=NOW,
        )
        assert loop.calls == [("start", RUN_ID, "loop-1"), ("wake", RUN_ID)]
        assert calls[0][0][3:7] == ("PAUSED", "RUNNING", 4, 60)
        assert calls[0][1]["require_unleased"] is True
        assert result["loop_started"] is True
        assert result["readiness"]["department_digest"] == "departments-exact"

    asyncio.run(case())


def test_stale_resume_and_active_local_loop_never_mutate(monkeypatch):
    async def case():
        calls = []

        async def transition(*args, **kwargs):
            calls.append((args, kwargs))

        monkeypatch.setattr(lifecycle, "transition_run", transition)
        timeline = Timeline(row(cursor=2))
        with pytest.raises(CommunityControlError, match="stale"):
            await service(timeline, Loop(timeline)).resume_and_start(
                OWNER, AUTHORITY, RUN_ID, 1, 0, "resume", "loop",
            )
        with pytest.raises(CommunityControlError, match="already owns"):
            await service(timeline, Loop(timeline, starts=False)).resume_and_start(
                OWNER, AUTHORITY, RUN_ID, 2, 0, "resume", "loop",
            )
        assert calls == []

    asyncio.run(case())


def test_pause_waits_for_inflight_tick_then_uses_fresh_exact_coordinates(monkeypatch):
    async def case():
        timeline = Timeline(row(
            state="RUNNING", cursor=4, sim_minute=60,
            execution_lease={"holder_id": "loop-1"},
        ))
        loop = Loop(timeline, move_on_cancel={"cursor": 5, "sim_minute": 61})
        calls = []

        async def transition(*args, **kwargs):
            calls.append((args, kwargs))
            timeline.row["state"] = "PAUSED"
            return {"run": deepcopy(timeline.row), "receipt": {"receipt_id": "pause"}}

        monkeypatch.setattr(lifecycle, "transition_run", transition)
        result = await service(timeline, loop).pause(
            OWNER, AUTHORITY, RUN_ID, 4, 60, "pause-key", now=NOW,
        )
        assert loop.calls == [("cancel", RUN_ID)]
        assert calls[0][0][3:7] == ("RUNNING", "PAUSED", 5, 61)
        assert calls[0][1]["require_unleased"] is True
        assert result["run"]["state"] == "PAUSED"

    asyncio.run(case())


def test_stop_cancels_loop_and_uses_receipt_backed_transition(monkeypatch):
    async def case():
        timeline = Timeline(row(
            state="RUNNING", cursor=7, sim_minute=90,
            execution_lease={"holder_id": "loop-1"},
        ))
        loop = Loop(timeline)
        calls = []

        async def transition(*args, **kwargs):
            calls.append((args, kwargs))
            timeline.row["state"] = "STOPPED"
            return {"run": deepcopy(timeline.row), "receipt": {"receipt_id": "stop"}}

        monkeypatch.setattr(lifecycle, "transition_run", transition)
        result = await service(timeline, loop).stop(
            OWNER, AUTHORITY, RUN_ID, "RUNNING", 7, 90, "stop-key",
        )
        assert loop.calls == [("cancel", RUN_ID)]
        assert calls[0][0][3:7] == ("RUNNING", "STOPPED", 7, 90)
        assert calls[0][1]["require_unleased"] is True
        assert result["receipt"]["receipt_id"] == "stop"

    asyncio.run(case())


def test_step_delegates_exact_position_and_durable_dependencies():
    async def case():
        calls = []
        async def manual(*args, **kwargs):
            calls.append((args, kwargs))
            return {"run": row(cursor=1), "receipt": {"receipt_id": "step"}}

        timeline = Timeline()
        control = service(timeline, Loop(timeline), manual_step=manual)
        result = await control.step_one(
            OWNER, AUTHORITY, RUN_ID, 0, 0, "step-key", "stepper", now=NOW,
        )
        args, kwargs = calls[0]
        assert args == (OWNER, AUTHORITY, RUN_ID, 0, 0, "step-key", "stepper")
        assert kwargs["store"] is control.store
        assert kwargs["plan"] is PLAN and kwargs["timeline"] is timeline
        assert kwargs["services"] is control.services
        assert kwargs["tick"] is control.tick and kwargs["clock"] is control.clock
        assert kwargs["now"] == NOW and callable(kwargs["ready"])
        assert result["receipt"]["receipt_id"] == "step"

    asyncio.run(case())


def test_canonical_start_guard_refuses_unknown_and_returns_exact_proof(monkeypatch):
    async def case():
        async def unknown(**_kwargs):
            return {"status": "unknown", "provisioning": {"state": None}}

        monkeypatch.setattr(control_module, "observe_community_state", unknown)
        with pytest.raises(CommunityControlError, match="every burn_in_10 canonical resident exactly"):
            await control_module.canonical_start_guard(store=object(), run=row())

        async def observed(**_kwargs):
            return {
                "status": "loaded", "marker_anomalies": [],
                "provisioning": {
                    "state": "provisioned", "exact_blueprint_residents": 10,
                },
            }

        class Departments:
            contract_version = "departments-v1"
            digest = "exact-department-digest"

        async def departments(**_kwargs):
            return Departments()

        monkeypatch.setattr(control_module, "observe_community_state", observed)
        monkeypatch.setattr(
            control_module, "preflight_living_community_run_start", departments,
        )
        proof = await control_module.canonical_start_guard(store=object(), run=row())
        assert proof["resident_count"] == 10
        assert proof["department_digest"] == "exact-department-digest"
        assert proof["plan_digest_sha256"] == PLAN.digest_sha256

    asyncio.run(case())
