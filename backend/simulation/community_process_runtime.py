"""One inert-by-default process registry for living-community execution."""

import os
from uuid import uuid4

from simulation.community_control_capability import controls_explicitly_enabled
from simulation.community_control_composition import compose_community_controls
from simulation.community_startup_recovery import (
    CommunityStartupRecoveryCoordinator,
    StartupRecoveryConfig,
    StartupRecoveryResult,
    bounded_runner_reconciler,
)


STARTUP_ENV = "CAOSCARE_LIVING_COMMUNITY_STARTUP_RECOVERY"


def startup_explicitly_enabled() -> bool:
    return os.environ.get(STARTUP_ENV, "").strip().lower() == "true"


class CommunityProcessRuntime:
    """Share one control service and loop manager inside one server process."""

    def __init__(
        self, *, store, controls_factory=compose_community_controls,
        process_id=None, holder_id=None,
    ):
        self.store = store
        self.controls_factory = controls_factory
        self.process_id = process_id or f"{os.getpid()}:{uuid4().hex}"
        self.holder_id = holder_id or f"community-process:{self.process_id}"
        self._controls = None
        self._startup = None

    @property
    def controls(self):
        if self._controls is None:
            self._controls = self.controls_factory(store=self.store)
        return self._controls

    async def recover_startup(self) -> StartupRecoveryResult:
        """Recover only after both explicit environment gates are true."""
        if not startup_explicitly_enabled():
            return StartupRecoveryResult(
                status="disabled", blockers=("startup_recovery_not_enabled",),
            )
        if not controls_explicitly_enabled():
            return StartupRecoveryResult(
                status="blocked", blockers=("controls_not_enabled",),
            )
        if self._startup is None:
            service = self.controls
            manager = service.loop
            self._startup = CommunityStartupRecoveryCoordinator(
                store=self.store,
                loop_manager=manager,
                advance_sim_clock=manager.advance_sim_clock,
                reconcile_tick=bounded_runner_reconciler(
                    store=self.store,
                    timeline=service.timeline,
                    services=service.services,
                    clock=service.clock,
                ),
                config=StartupRecoveryConfig(
                    enabled=True,
                    startup_id=f"startup:{self.process_id}",
                    holder_id=self.holder_id,
                    acceleration=manager.config.acceleration,
                    horizon_minutes=manager.config.horizon_minutes,
                ),
                clock=service.clock,
            )
        return await self._startup.recover()

    async def shutdown(self):
        """Cancel only loops owned by the already-composed shared manager."""
        if self._controls is None:
            return ()
        return await self._controls.loop.cancel_all()
