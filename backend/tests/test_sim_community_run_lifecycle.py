"""Atomic lifecycle proof for the living-community burn-in run."""
import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from routes.actor_context import ActorContext
from simulation import community_loop
from simulation import community_run_lifecycle as lifecycle
from simulation import community_runtime_view
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_runner import TickResult
from simulation.community_timeline import build_90_day_timeline


NOW = datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)
PLAN = build_90_day_timeline()


def _get(row, path):
    value = row
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _matches(row, query):
    for key, wanted in query.items():
        if key == "$or":
            if not any(_matches(row, branch) for branch in wanted):
                return False
            continue
        actual = _get(row, key)
        if isinstance(wanted, dict):
            if "$exists" in wanted and (_get(row, key) is not None) != wanted["$exists"]:
                return False
            if "$in" in wanted and actual not in wanted["$in"]:
                return False
        elif actual != wanted:
            return False
    return True


def _set(row, path, value):
    target = row
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = deepcopy(value)


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return deepcopy(self.rows)


class Collection:
    def __init__(self, store, name):
        self.store, self.name = store, name

    @property
    def rows(self):
        return self.store.data[self.name]

    def find(self, query, _projection=None, session=None):
        return Cursor([row for row in self.rows if _matches(row, query)])

    async def find_one(self, query, _projection=None, session=None):
        return next((deepcopy(row) for row in self.rows if _matches(row, query)), None)

    async def insert_one(self, row, session=None):
        if self.name == "receipts" and self.store.fail_receipt_insert:
            raise RuntimeError("receipt write failed")
        if any(existing.get("_id") == row.get("_id") for existing in self.rows):
            raise RuntimeError("duplicate _id")
        self.rows.append(deepcopy(row))

    async def find_one_and_update(self, query, update, **_kwargs):
        row = next((row for row in self.rows if _matches(row, query)), None)
        if row is None:
            return None
        for path, value in update.get("$set", {}).items():
            _set(row, path, value)
        for path in update.get("$unset", {}):
            row.pop(path, None)
        result = deepcopy(row)
        result.pop("_id", None)
        return result


class Transaction:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        self.before = deepcopy(self.store.data)
        return self

    async def __aexit__(self, exc_type, _exc, _tb):
        if exc_type:
            self.store.data = self.before


class Session:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def start_transaction(self):
        return Transaction(self.store)


class Client:
    def __init__(self, store):
        self.store = store

    async def start_session(self):
        return Session(self.store)


class Store:
    def __init__(self):
        self.data = {"sim_runs": [], "receipts": []}
        self.sim_runs = Collection(self, "sim_runs")
        self.receipts = Collection(self, "receipts")
        self.client = Client(self)
        self.fail_receipt_insert = False


OWNER = ActorContext(
    actor_id="user-michael", actor_type="real-human", identity_basis="authenticated",
    channel="staff_ui", name="Michael", role="owner", simulated=False,
)
AUTHORITY = "admin_override:owner"
RUNNER = ActorContext(
    actor_id=lifecycle.CLOCK_ACTOR_ID, actor_type="system", identity_basis="system",
    channel="system", name="Living Community Runner", role="system", simulated=False,
)


async def create(store, key="create-burn-in-1", plan=PLAN):
    return await lifecycle.create_burn_in_run(
        OWNER, AUTHORITY, key, plan, store=store, now=NOW,
    )


def test_create_is_paused_exactly_once_with_plan_and_real_actor_receipt():
    async def case():
        store = Store()
        first = await create(store)
        run, receipt = first["run"], first["receipt"]
        assert (run["state"], run["cursor"], run["sim_minute"]) == ("PAUSED", 0, 0)
        assert run["simulation_scope"] == SIMULATION_SCOPE
        assert run["simulation_community_id"] == COMMUNITY_ID
        assert run["plan_revision"] == PLAN.plan_revision
        assert run["plan_digest_sha256"] == PLAN.digest_sha256
        assert run["event_count"] == PLAN.event_count
        assert run["timeline_end_minute"] == PLAN.day_count * 1440 - 1
        assert run["resident_count"] == 10 and run["cohort"] == "burn_in_10"
        assert run["residents_provisioned"] is False
        assert run["created_by"]["actor_id"] == "user-michael"
        assert run["original_human_starter"] is None
        assert receipt["actor_id"] == "user-michael"
        assert receipt["actor_type"] == "real-human"
        assert receipt["identity_basis"] == "authenticated"
        assert receipt["authority"] == AUTHORITY
        replay = await create(store)
        assert replay["idempotent_replay"] is True
        assert len(store.data["sim_runs"]) == len(store.data["receipts"]) == 1
    asyncio.run(case())


@pytest.mark.parametrize("operator,authority", [
    (ActorContext("sim", "simulated-agent", "synthetic", "simulator", role="admin", simulated=True),
     "admin_override:admin"),
    (OWNER, "admin_override:admin"),
])
def test_create_requires_authenticated_real_matching_owner_or_admin(operator, authority):
    async def case():
        store = Store()
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="authenticated|authority"):
            await lifecycle.create_burn_in_run(
                operator, authority, "key", PLAN, store=store, now=NOW,
            )
        assert store.data == {"sim_runs": [], "receipts": []}
    asyncio.run(case())


def test_bad_plan_and_other_run_fail_closed_before_mutation():
    async def case():
        store = Store()
        bad = replace(PLAN, digest_sha256="0" * 64)
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="timeline"):
            await create(store, plan=bad)
        store.data["sim_runs"].append({
            "_id": "other", "run_id": "other", "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        })
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="conflicts"):
            await create(store)
        assert store.data["receipts"] == []
    asyncio.run(case())


def test_only_allowed_cas_transitions_commit_receipts_and_clear_leases():
    async def case():
        store = Store()
        created = await create(store)
        run_id = created["run"]["run_id"]
        resumed = await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
            "resume-1", PLAN, store=store, now=NOW,
        )
        assert resumed["run"]["state"] == "RUNNING"
        assert resumed["run"]["original_human_starter"]["actor_id"] == "user-michael"
        store.data["sim_runs"][0]["execution_lease"] = {"holder_id": "worker"}
        paused = await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "RUNNING", "PAUSED", 0, 0,
            "pause-1", PLAN, store=store, now=NOW,
        )
        assert paused["run"]["state"] == "PAUSED"
        assert "execution_lease" not in store.data["sim_runs"][0]
        stopped = await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "STOPPED", 0, 0,
            "stop-1", PLAN, store=store, now=NOW,
        )
        assert stopped["run"]["state"] == "STOPPED"
        assert stopped["receipt"]["source"] == "staff"
        assert stopped["run"].get("terminal_reason") is None
        assert [row["action_type"] for row in store.data["receipts"]] == [
            "simulation_community_run_created", "simulation_community_run_resumed",
            "simulation_community_run_paused", "simulation_community_run_stopped",
        ]
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="invalid"):
            await lifecycle.transition_run(
                OWNER, AUTHORITY, run_id, "STOPPED", "RUNNING", 0, 0,
                "bad", PLAN, store=store, now=NOW,
            )
    asyncio.run(case())


def test_control_transition_can_atomically_require_no_execution_lease():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        store.data["sim_runs"][0]["execution_lease"] = {"holder_id": "active-loop"}
        before = len(store.data["receipts"])
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="stale"):
            await lifecycle.transition_run(
                OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
                "guarded-resume", PLAN, store=store, now=NOW,
                require_unleased=True,
            )
        assert store.data["sim_runs"][0]["state"] == "PAUSED"
        assert len(store.data["receipts"]) == before

    asyncio.run(case())


def test_stale_state_cursor_clock_and_changed_plan_never_write_receipt():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        original = len(store.data["receipts"])
        for cursor, minute in ((1, 0), (0, 1)):
            with pytest.raises(lifecycle.CommunityRunLifecycleError, match="stale"):
                await lifecycle.transition_run(
                    OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", cursor, minute,
                    f"stale-{cursor}-{minute}", PLAN, store=store, now=NOW,
                )
        store.data["sim_runs"][0]["plan_digest_sha256"] = "tampered"
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="persisted run plan"):
            await lifecycle.transition_run(
                OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
                "tampered", PLAN, store=store, now=NOW,
            )
        assert len(store.data["receipts"]) == original
    asyncio.run(case())


def test_clock_is_running_only_monotonic_capped_and_cursor_guarded():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
            "resume-clock", PLAN, store=store, now=NOW,
        )
        advanced = await lifecycle.advance_simulated_clock(
            RUNNER, f"simulation_run:{run_id}:clock", run_id, 0, 0, 60, "clock-60", PLAN,
            store=store, now=NOW,
        )
        assert advanced["run"]["sim_minute"] == 60
        assert advanced["receipt"]["actor_id"] == lifecycle.CLOCK_ACTOR_ID
        assert advanced["receipt"]["actor_type"] == "system"
        assert advanced["receipt"]["source"] == "system"
        assert advanced["run"]["original_human_starter"]["actor_id"] == "user-michael"
        for cursor, old, new, match in (
            (1, 60, 61, "stale"), (0, 60, 60, "monotonically"),
            (0, 60, PLAN.day_count * 1440, "timeline"),
        ):
            with pytest.raises(lifecycle.CommunityRunLifecycleError, match=match):
                await lifecycle.advance_simulated_clock(
                    RUNNER, f"simulation_run:{run_id}:clock", run_id, cursor, old, new,
                    f"clock-{cursor}-{old}-{new}", PLAN, store=store, now=NOW,
                )
    asyncio.run(case())


def test_clock_refuses_human_attribution_wrong_authority_and_live_executor_lease():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
            "resume-clock-guard", PLAN, store=store, now=NOW,
        )
        receipt_count = len(store.data["receipts"])
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="named runner"):
            await lifecycle.advance_simulated_clock(
                OWNER, AUTHORITY, run_id, 0, 0, 1, "human-clock", PLAN,
                store=store, now=NOW,
            )
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="named runner"):
            await lifecycle.advance_simulated_clock(
                RUNNER, "simulation_run:other:clock", run_id, 0, 0, 1,
                "wrong-authority", PLAN, store=store, now=NOW,
            )
        store.data["sim_runs"][0]["execution_lease"] = {"holder_id": "active-runner"}
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="stale"):
            await lifecycle.advance_simulated_clock(
                RUNNER, f"simulation_run:{run_id}:clock", run_id, 0, 0, 1,
                "leased-clock", PLAN, store=store, now=NOW,
            )
        assert len(store.data["receipts"]) == receipt_count
        assert store.data["sim_runs"][0]["sim_minute"] == 0
    asyncio.run(case())


def test_receipt_failure_rolls_back_run_creation_and_transition():
    async def case():
        store = Store()
        store.fail_receipt_insert = True
        with pytest.raises(RuntimeError, match="receipt write failed"):
            await create(store)
        assert store.data == {"sim_runs": [], "receipts": []}

        store.fail_receipt_insert = False
        run_id = (await create(store))["run"]["run_id"]
        store.fail_receipt_insert = True
        with pytest.raises(RuntimeError, match="receipt write failed"):
            await lifecycle.transition_run(
                OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
                "resume-fails", PLAN, store=store, now=NOW,
            )
        assert store.data["sim_runs"][0]["state"] == "PAUSED"
        assert len(store.data["receipts"]) == 1
    asyncio.run(case())


def test_system_completion_is_atomic_exact_and_idempotent():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
            "resume-to-complete", PLAN, store=store, now=NOW,
        )
        run = store.data["sim_runs"][0]
        run.update(cursor=PLAN.event_count, sim_minute=PLAN.day_count * 1440 - 1)
        authority = f"simulation_run:{run_id}:complete"
        completed = await lifecycle.complete_run(
            RUNNER, authority, run_id, PLAN.event_count, run["sim_minute"],
            "automatic-completion", PLAN, store=store, now=NOW,
        )
        final, receipt = completed["run"], completed["receipt"]
        assert (final["state"], final["cursor"], final["sim_minute"]) == (
            "STOPPED", PLAN.event_count, PLAN.day_count * 1440,
        )
        assert final["terminal_reason"] == "completed"
        assert final["completion_receipt_id"] == receipt["receipt_id"]
        assert receipt["action_type"] == "simulation_community_run_completed"
        assert receipt["source"] == "system"
        assert receipt["actor_id"] == lifecycle.CLOCK_ACTOR_ID
        assert receipt["actor_type"] == receipt["identity_basis"] == "system"
        assert receipt["authority"] == authority

        replay = await lifecycle.complete_run(
            RUNNER, authority, run_id, PLAN.event_count,
            PLAN.day_count * 1440 - 1, "automatic-completion", PLAN,
            store=store, now=NOW,
        )
        assert replay["idempotent_replay"] is True
        assert len([row for row in store.data["receipts"]
                    if row["action_type"] == "simulation_community_run_completed"]) == 1
    asyncio.run(case())


def test_completion_refuses_incomplete_cursor_wrong_authority_and_live_lease():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
            "resume-guarded-completion", PLAN, store=store, now=NOW,
        )
        run = store.data["sim_runs"][0]
        run.update(cursor=PLAN.event_count, sim_minute=PLAN.day_count * 1440 - 1)
        receipt_count = len(store.data["receipts"])
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="every planned"):
            await lifecycle.complete_run(
                RUNNER, f"simulation_run:{run_id}:complete", run_id,
                PLAN.event_count - 1, run["sim_minute"], "incomplete", PLAN,
                store=store, now=NOW,
            )
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="named runner"):
            await lifecycle.complete_run(
                OWNER, AUTHORITY, run_id, PLAN.event_count,
                run["sim_minute"], "human-completion", PLAN, store=store, now=NOW,
            )
        run["execution_lease"] = {"holder_id": "still-executing"}
        with pytest.raises(lifecycle.CommunityRunLifecycleError, match="stale"):
            await lifecycle.complete_run(
                RUNNER, f"simulation_run:{run_id}:complete", run_id,
                PLAN.event_count, run["sim_minute"], "leased-completion", PLAN,
                store=store, now=NOW,
            )
        assert len(store.data["receipts"]) == receipt_count
        assert run["state"] == "RUNNING"
    asyncio.run(case())


def test_loop_completion_commits_lifecycle_terminal_state_accepted_by_runtime_view():
    async def case():
        store = Store()
        run_id = (await create(store))["run"]["run_id"]
        await lifecycle.transition_run(
            OWNER, AUTHORITY, run_id, "PAUSED", "RUNNING", 0, 0,
            "resume-loop-completion", PLAN, store=store, now=NOW,
        )
        stored = store.data["sim_runs"][0]
        stored.update(cursor=PLAN.event_count, sim_minute=PLAN.day_count * 1440 - 1)

        async def load_run(*, run_id):
            return await store.sim_runs.find_one({"run_id": run_id}, {"_id": 0})

        async def advance_sim_clock(**call):
            return call["observed_run"]

        async def complete_run(**call):
            observed = call["observed_run"]
            result = await lifecycle.complete_run(
                RUNNER, f"simulation_run:{run_id}:complete", run_id,
                observed["cursor"], observed["sim_minute"],
                f"loop-complete:{run_id}:{observed['cursor']}", PLAN,
                store=store, now=call["observed_at"],
            )
            return result["run"]

        async def tick(*_args, **_kwargs):
            return TickResult(
                run_id, "complete", "none", None, None,
                PLAN.event_count, PLAN.event_count, 1, False,
            )

        manager = community_loop.CommunityLoopManager(
            store=store, timeline=object(), services=object(),
            load_run=load_run, advance_sim_clock=advance_sim_clock,
            complete_run=complete_run, tick=tick, clock=lambda: NOW,
        )
        assert manager.start(run_id, "integration-loop") is True
        status = await manager.wait(run_id)
        final = store.data["sim_runs"][0]
        assert status.phase == "complete" and status.run_state == "STOPPED"
        assert final["state"] == "STOPPED"
        assert final["sim_minute"] == community_loop.HORIZON_MINUTES
        errors = []
        projected = community_runtime_view._run_projection(final, PLAN.events, errors)
        assert errors == []
        assert projected["status"] == "loaded"
        assert projected["state"] == "STOPPED"
        assert projected["progress"]["percent"] == 100.0
        assert projected["simulated_time"]["day_index"] == 90
    asyncio.run(case())
