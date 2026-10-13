"""Explicit composition root for living-community controls.

The caller supplies storage, clock and any exclusive step capability.  This
module does not import ``deps``, register a route, or create background work.
"""

from datetime import datetime, timezone
from hashlib import sha256

from simulation import community_run_lifecycle as lifecycle
from simulation.community_control_service import (
    CommunityControlService,
    canonical_start_guard,
    runner_actor,
)
from simulation.community_execution_adapter import CanonicalCommunityExecutionServices
from simulation.community_loop import CommunityLoopManager
from simulation.community_loop_contract import LoopConfig
from simulation.community_runner_timeline import (
    DatabaseRunnerTimeline,
    PersistedRunClock,
    canonical_plan,
)


def _completion_key(run_id: str, run: dict) -> str:
    source = (
        f"{run_id}:{run.get('cursor')}:{run.get('sim_minute')}:"
        f"{run.get('updated_at')}"
    )
    return f"auto-complete:{sha256(source.encode()).hexdigest()}"


def compose_community_controls(
    *, store, clock=lambda: datetime.now(timezone.utc),
    config: LoopConfig = LoopConfig(), start_guard=canonical_start_guard,
    services=None,
) -> CommunityControlService:
    """Wire canonical adapters around injected storage without starting them."""
    plan = canonical_plan()
    timeline = DatabaseRunnerTimeline(store=store, plan=plan)
    run_clock = PersistedRunClock(store=store, plan=plan)
    execution = services or CanonicalCommunityExecutionServices(store=store)
    system = runner_actor()

    async def complete_run(
        *, run_id, observed_run, observed_at, horizon_minutes,
    ) -> dict:
        if horizon_minutes != plan.day_count * 1440:
            raise lifecycle.CommunityRunLifecycleError(
                "completion horizon does not match the canonical plan"
            )
        result = await lifecycle.complete_run(
            system, f"simulation_run:{run_id}:complete", run_id,
            observed_run["cursor"], observed_run["sim_minute"],
            _completion_key(run_id, observed_run), plan,
            store=store, now=observed_at,
        )
        return result["run"]

    manager = CommunityLoopManager(
        store=store,
        timeline=timeline,
        services=execution,
        load_run=timeline.load_run,
        advance_sim_clock=run_clock,
        complete_run=complete_run,
        clock=clock,
        config=config,
    )
    return CommunityControlService(
        store=store,
        plan=plan,
        timeline=timeline,
        services=execution,
        loop_manager=manager,
        start_guard=start_guard,
        clock=clock,
    )
