"""Composition stays inert and attributes completion to the named system."""

import asyncio
from datetime import datetime, timezone

from simulation import community_run_lifecycle as lifecycle
from simulation.community_control_composition import compose_community_controls


NOW = datetime(2026, 10, 13, 21, 0, tzinfo=timezone.utc)


class Store:
    pass


def test_composition_starts_nothing_and_completion_is_system_owned(monkeypatch):
    async def case():
        calls = []

        async def complete(*args, **kwargs):
            calls.append((args, kwargs))
            return {"run": {
                **kwargs.pop("observed", {}),
                "run_id": args[2], "state": "STOPPED",
                "cursor": args[3], "sim_minute": 129600,
            }}

        monkeypatch.setattr(lifecycle, "complete_run", complete)
        control = compose_community_controls(store=Store(), clock=lambda: NOW)
        assert control.loop.status("missing") is None
        run = {
            "run_id": "simrun-1", "state": "RUNNING",
            "cursor": control.plan.event_count,
            "sim_minute": control.plan.day_count * 1440 - 1,
            "updated_at": NOW.isoformat(),
        }
        result = await control.loop.complete_run(
            run_id="simrun-1", observed_run=run, observed_at=NOW,
            horizon_minutes=control.plan.day_count * 1440,
        )
        args, kwargs = calls[0]
        actor = args[0]
        assert actor.actor_id == lifecycle.CLOCK_ACTOR_ID
        assert actor.actor_type == actor.identity_basis == actor.channel == "system"
        assert args[1] == "simulation_run:simrun-1:complete"
        assert args[2:5] == ("simrun-1", control.plan.event_count, 129599)
        assert kwargs["store"] is control.store and kwargs["now"] == NOW
        assert result["state"] == "STOPPED"

    asyncio.run(case())
