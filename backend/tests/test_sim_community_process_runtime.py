"""Process composition proof for inert startup and one shared loop manager."""

import asyncio

from simulation import community_process_runtime as process_module
from simulation.community_process_runtime import CommunityProcessRuntime
from simulation.community_startup_recovery import StartupRecoveryResult


class Loop:
    def __init__(self):
        self.cancelled = 0

    async def cancel_all(self):
        self.cancelled += 1
        return ("stopped",)


class Controls:
    def __init__(self):
        self.loop = Loop()


def execute(awaitable):
    return asyncio.run(awaitable)


def test_default_off_never_composes_controls_or_touches_store(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_STARTUP_RECOVERY", raising=False)
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", raising=False)
    calls = []

    def compose(**kwargs):
        calls.append(kwargs)
        raise AssertionError("default-off startup must stay inert")

    runtime = CommunityProcessRuntime(store=object(), controls_factory=compose)
    result = execute(runtime.recover_startup())
    assert result.status == "disabled" and calls == []
    assert execute(runtime.shutdown()) == ()


def test_startup_gate_without_controls_never_composes_or_probes(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_STARTUP_RECOVERY", "true")
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", raising=False)
    calls = []

    def compose(**kwargs):
        calls.append(kwargs)
        raise AssertionError("controls gate must precede composition")

    result = execute(
        CommunityProcessRuntime(store=object(), controls_factory=compose).recover_startup()
    )
    assert result.status == "blocked"
    assert result.blockers == ("controls_not_enabled",) and calls == []


def test_http_controls_and_shutdown_share_one_exact_service(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_STARTUP_RECOVERY", raising=False)
    controls, calls = Controls(), []

    def compose(**kwargs):
        calls.append(kwargs)
        return controls

    store = object()
    runtime = CommunityProcessRuntime(store=store, controls_factory=compose)
    assert runtime.controls is controls
    assert runtime.controls.loop is controls.loop
    assert len(calls) == 1 and calls[0]["store"] is store
    assert execute(runtime.shutdown()) == ("stopped",)
    assert controls.loop.cancelled == 1


def test_enabled_startup_injects_the_same_manager_exposed_to_controls(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_STARTUP_RECOVERY", "true")
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    calls = []

    class Manager(Loop):
        advance_sim_clock = object()
        config = type("Config", (), {"acceleration": 60.0, "horizon_minutes": 129600})()

    manager = Manager()
    controls = type("Controls", (), {
        "loop": manager,
        "timeline": object(),
        "services": object(),
        "clock": staticmethod(lambda: None),
    })()

    class Coordinator:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        async def recover(self):
            return StartupRecoveryResult(status="no_running_run")

    monkeypatch.setattr(process_module, "CommunityStartupRecoveryCoordinator", Coordinator)
    runtime = CommunityProcessRuntime(
        store=object(), controls_factory=lambda **kwargs: controls,
    )
    result = execute(runtime.recover_startup())

    assert result.status == "no_running_run"
    assert runtime.controls.loop is manager
    assert calls[0]["loop_manager"] is manager
    assert calls[0]["advance_sim_clock"] is manager.advance_sim_clock
    assert calls[0]["config"].holder_id == runtime.holder_id
    assert runtime.holder_id.startswith("community-process:")
