"""Injection-first owner/admin controls for one living-community run.

This module selects no database, exposes no route, and starts nothing at
import time.  Human mutations delegate to the atomic lifecycle boundary;
automatic clock/completion mutations retain the named system actor.
"""

from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from hashlib import sha256
from typing import Awaitable, Callable, Optional

from routes.actor_context import ActorContext
from simulation.community_atomic_provision import provision_paused_burn_in_run
from simulation import community_run_lifecycle as lifecycle
from simulation import community_runner
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_department_preflight import preflight_living_community_run_start
from simulation.community_observed_state import observe_community_state
from simulation.community_timeline import CommunityTimeline, validate_timeline


StartGuard = Callable[..., Awaitable[dict]]
ExclusiveStep = Callable[[str], AbstractAsyncContextManager]


class CommunityControlError(RuntimeError):
    """A control request was refused before unsafe or ambiguous work."""


def runner_actor() -> ActorContext:
    return ActorContext(
        actor_id=lifecycle.CLOCK_ACTOR_ID,
        actor_type="system",
        identity_basis="system",
        channel="system",
        name="Living Community Runner",
        role="system",
        simulated=False,
    )


def _key(parent: str, action: str) -> str:
    raw = (parent or "").strip()
    if not raw:
        raise CommunityControlError("a stable operation key is required")
    return f"control:{action}:{sha256(raw.encode()).hexdigest()}"


async def canonical_start_guard(*, store, run: dict) -> dict:
    """Prove exact residents and active departments without writing state."""
    observed = await observe_community_state(store=store)
    provisioning = observed.get("provisioning") or {}
    if (
        observed.get("status") != "loaded"
        or provisioning.get("state") != "provisioned"
        or provisioning.get("exact_blueprint_residents") != 10
        or observed.get("marker_anomalies")
    ):
        raise CommunityControlError(
            "start requires ten exact canonical burn-in residents and no marker anomalies"
        )
    departments = await preflight_living_community_run_start(store=store)
    return {
        "run_id": run["run_id"],
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "plan_revision": run["plan_revision"],
        "plan_digest_sha256": run["plan_digest_sha256"],
        "cursor": run["cursor"],
        "sim_minute": run["sim_minute"],
        "resident_count": provisioning["exact_blueprint_residents"],
        "department_contract_version": departments.contract_version,
        "department_digest": departments.digest,
    }


class CommunityControlService:
    """Coordinate lifecycle writes with an explicitly injected loop."""

    def __init__(
        self, *, store, plan: CommunityTimeline, timeline, services, loop_manager,
        start_guard: StartGuard = canonical_start_guard,
        exclusive_step: Optional[ExclusiveStep] = None,
        tick=community_runner.tick,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self.store = store
        self.plan = validate_timeline(plan)
        self.timeline = timeline
        self.services = services
        self.loop = loop_manager
        self.start_guard = start_guard
        self.exclusive_step = exclusive_step
        self.tick = tick
        self.clock = clock

    def _now(self, value: Optional[datetime]) -> datetime:
        instant = value or self.clock()
        if not isinstance(instant, datetime) or instant.tzinfo is None:
            raise CommunityControlError("control timestamps must be timezone-aware")
        return instant.astimezone(timezone.utc)

    async def _exact(
        self, run_id: str, state: str, cursor: int, sim_minute: int,
        *, require_unleased: bool = True,
    ) -> dict:
        try:
            row = await self.timeline.load_run(run_id=run_id)
        except Exception as exc:
            raise CommunityControlError(f"run validation failed: {exc}") from exc
        if row.get("state") != state:
            raise CommunityControlError(f"expected {state} run state")
        if row.get("cursor") != cursor or row.get("sim_minute") != sim_minute:
            raise CommunityControlError("expected cursor or simulated clock is stale")
        if require_unleased and row.get("execution_lease"):
            raise CommunityControlError("run has an active execution lease")
        return row

    async def _ready(self, row: dict) -> dict:
        proof = await self.start_guard(store=self.store, run=dict(row))
        expected = {
            "run_id": row["run_id"],
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "plan_revision": self.plan.plan_revision,
            "plan_digest_sha256": self.plan.digest_sha256,
            "cursor": row["cursor"],
            "sim_minute": row["sim_minute"],
        }
        if not isinstance(proof, dict) or any(proof.get(k) != v for k, v in expected.items()):
            raise CommunityControlError("start-readiness proof does not match the exact run")
        if not proof.get("department_digest") or proof.get("resident_count") != 10:
            raise CommunityControlError("start-readiness proof is incomplete")
        return proof

    async def create_paused(
        self, operator: ActorContext, authority: str, operation_key: str,
        *, now: Optional[datetime] = None,
    ) -> dict:
        return await lifecycle.create_burn_in_run(
            operator, authority, operation_key, self.plan,
            store=self.store, now=self._now(now),
        )

    async def provision_residents(
        self, operator: ActorContext, authority: str, run_id: str,
        expected_cursor: int, expected_sim_minute: int, operation_key: str,
        *, now: Optional[datetime] = None,
    ) -> dict:
        return await provision_paused_burn_in_run(
            operator, authority, run_id, expected_cursor, expected_sim_minute,
            operation_key, self.plan, store=self.store, now=self._now(now),
        )

    async def resume_and_start(
        self, operator: ActorContext, authority: str, run_id: str,
        expected_cursor: int, expected_sim_minute: int, operation_key: str,
        holder_id: str, *, now: Optional[datetime] = None,
    ) -> dict:
        row = await self._exact(
            run_id, lifecycle.PAUSED, expected_cursor, expected_sim_minute,
        )
        readiness = await self._ready(row)
        if not self.loop.start(run_id, holder_id):
            raise CommunityControlError("a local loop already owns this run")
        try:
            changed = await lifecycle.transition_run(
                operator, authority, run_id, lifecycle.PAUSED, lifecycle.RUNNING,
                expected_cursor, expected_sim_minute, operation_key, self.plan,
                store=self.store, now=self._now(now), require_unleased=True,
            )
        except BaseException:
            await self.loop.cancel(run_id)
            raise
        self.loop.wake(run_id)
        return {**changed, "loop_started": True, "holder_id": holder_id,
                "readiness": readiness}

    async def pause(
        self, operator: ActorContext, authority: str, run_id: str,
        expected_cursor: int, expected_sim_minute: int, operation_key: str,
        *, now: Optional[datetime] = None,
    ) -> dict:
        await self._exact(
            run_id, lifecycle.RUNNING, expected_cursor, expected_sim_minute,
            require_unleased=False,
        )
        loop_status = await self.loop.cancel(run_id)
        row = await self.timeline.load_run(run_id=run_id)
        if row.get("state") != lifecycle.RUNNING or row.get("execution_lease"):
            raise CommunityControlError("run changed or remained leased while pausing")
        changed = await lifecycle.transition_run(
            operator, authority, run_id, lifecycle.RUNNING, lifecycle.PAUSED,
            row["cursor"], row["sim_minute"], operation_key, self.plan,
            store=self.store, now=self._now(now), require_unleased=True,
        )
        return {**changed, "loop_status": loop_status}

    async def stop(
        self, operator: ActorContext, authority: str, run_id: str,
        expected_state: str, expected_cursor: int, expected_sim_minute: int,
        operation_key: str, *, now: Optional[datetime] = None,
    ) -> dict:
        if expected_state not in (lifecycle.RUNNING, lifecycle.PAUSED):
            raise CommunityControlError("stop expects RUNNING or PAUSED")
        await self._exact(
            run_id, expected_state, expected_cursor, expected_sim_minute,
            require_unleased=False,
        )
        loop_status = await self.loop.cancel(run_id)
        row = await self.timeline.load_run(run_id=run_id)
        if row.get("state") != expected_state or row.get("execution_lease"):
            raise CommunityControlError("run changed or remained leased while stopping")
        changed = await lifecycle.transition_run(
            operator, authority, run_id, expected_state, lifecycle.STOPPED,
            row["cursor"], row["sim_minute"], operation_key, self.plan,
            store=self.store, now=self._now(now), require_unleased=True,
        )
        return {**changed, "loop_status": loop_status}

    async def step_one(
        self, operator: ActorContext, authority: str, run_id: str,
        expected_cursor: int, expected_sim_minute: int, operation_key: str,
        holder_id: str, *, now: Optional[datetime] = None,
    ) -> dict:
        if self.exclusive_step is None:
            raise CommunityControlError("step is disabled without an exclusive-run capability")
        async with self.exclusive_step(run_id):
            row = await self._exact(
                run_id, lifecycle.PAUSED, expected_cursor, expected_sim_minute,
            )
            readiness = await self._ready(row)
            events = tuple(await self.timeline.load_events(run_id=run_id))
            if row["cursor"] >= len(events):
                raise CommunityControlError("no event remains to step")
            instant = self._now(now)
            await lifecycle.transition_run(
                operator, authority, run_id, lifecycle.PAUSED, lifecycle.RUNNING,
                row["cursor"], row["sim_minute"], _key(operation_key, "step-resume"),
                self.plan, store=self.store, now=instant, require_unleased=True,
            )
            result = None
            failure = None
            try:
                target = (
                    events[row["cursor"]].day_index * 1440
                    + events[row["cursor"]].minute
                )
                if target > row["sim_minute"]:
                    advanced = await lifecycle.advance_simulated_clock(
                        runner_actor(), f"simulation_run:{run_id}:clock", run_id,
                        row["cursor"], row["sim_minute"], target,
                        _key(operation_key, "step-clock"), self.plan,
                        store=self.store, now=instant,
                    )
                    row = advanced["run"]
                result = await self.tick(
                    run_id, holder_id, store=self.store, timeline=self.timeline,
                    services=self.services, now=instant, clock=self.clock,
                )
            except BaseException as exc:
                failure = exc
            current = await self.timeline.load_run(run_id=run_id)
            if current.get("state") == lifecycle.RUNNING:
                await lifecycle.transition_run(
                    operator, authority, run_id, lifecycle.RUNNING, lifecycle.PAUSED,
                    current["cursor"], current["sim_minute"],
                    _key(operation_key, "step-pause"), self.plan,
                    store=self.store, now=instant, require_unleased=True,
                )
            if failure:
                raise failure
            final = await self.timeline.load_run(run_id=run_id)
            delta = result.cursor_after - result.cursor_before
            if (
                result.run_id != run_id
                or result.cursor_before != row["cursor"]
                or delta not in (0, 1)
                or final.get("state") != lifecycle.PAUSED
                or final.get("cursor") != result.cursor_after
                or result.status not in {"executed", "advanced", "blocked"}
                or (delta == 1 and not result.receipt_id)
                or (delta == 0 and result.status != "blocked")
            ):
                raise CommunityControlError("step result does not prove one exact event attempt")
            return {"run": final, "tick": result, "readiness": readiness}
