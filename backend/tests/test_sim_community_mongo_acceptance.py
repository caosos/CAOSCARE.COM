import asyncio
from types import SimpleNamespace

import pytest

from simulation import community_mongo_acceptance as acceptance
from simulation.community_department_preflight import (
    DepartmentPreflightError,
    department_requirements,
)
from simulation.community_mongo_probe import (
    CommunityMongoAcceptanceError,
    classify_topology,
    probe_mongo,
    validate_scratch_database,
)


class FakeSession:
    def __init__(self):
        self.in_transaction = False
        self.aborted = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def start_transaction(self):
        self.in_transaction = True

    async def abort_transaction(self):
        self.aborted = True
        self.in_transaction = False


class FakeAdmin:
    def __init__(self, hello=None, error=None):
        self.hello = hello or {}
        self.error = error

    async def command(self, command):
        assert command == {"hello": 1}
        if self.error:
            raise self.error
        return dict(self.hello)


class ProbeClient:
    def __init__(self, hello=None, error=None):
        self.admin = FakeAdmin(hello, error)
        self.session = FakeSession()

    async def start_session(self):
        return self.session


class ProbeRuns:
    async def find_one(self, query, projection, *, session):
        assert query == {"_id": "__living_community_read_only_transaction_probe__"}
        assert projection == {"_id": 1}
        assert session.in_transaction
        return None


class ProbeStore:
    def __init__(self, hello=None, error=None):
        self.client = ProbeClient(hello, error)
        self.sim_runs = ProbeRuns()


def test_topology_classification_is_explicit():
    assert classify_topology({"setName": "rs0"}) == "replica_set"
    assert classify_topology({"msg": "isdbgrid", "setName": "ignored"}) == "sharded"
    assert classify_topology({"isWritablePrimary": True}) == "standalone"


def test_scratch_name_requires_strict_prefix_confirmation_and_prod_separation():
    good = "caoscare_sim_acceptance_20261013a"
    assert validate_scratch_database(
        good, production_db="caoscare", confirmed=True,
    ) == good
    for bad in ("caoscare_test", "caoscare_sim_acceptance_short", "CAOSCARE_SIM_ACCEPTANCE_20261013A"):
        with pytest.raises(CommunityMongoAcceptanceError, match="must match"):
            validate_scratch_database(bad, production_db="caoscare", confirmed=True)
    with pytest.raises(CommunityMongoAcceptanceError, match="confirm-scratch"):
        validate_scratch_database(good, production_db="caoscare", confirmed=False)
    with pytest.raises(CommunityMongoAcceptanceError, match="production"):
        validate_scratch_database(good, production_db=good, confirmed=True)


def test_probe_aborts_real_read_and_suppresses_connection_details():
    async def scenario():
        store = ProbeStore({"setName": "rs0"})
        report = await probe_mongo(store)
        assert report == {
            "status": "passed", "topology": "replica_set",
            "transaction_read_abort": True, "error_type": None,
        }
        assert store.client.session.aborted is True

        failed = await probe_mongo(
            ProbeStore(error=RuntimeError("mongodb://user:secret@example.invalid"))
        )
        assert failed["status"] == "failed" and failed["topology"] == "unknown"
        assert failed["error_type"] == "RuntimeError"
        assert "secret" not in repr(failed)

    asyncio.run(scenario())


class CountCollection:
    def __init__(self, count=0):
        self.count = count

    async def count_documents(self, query):
        assert query["simulation_scope"] == "living_community"
        return self.count


class DepartmentCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return [dict(row) for row in self.rows]


class DepartmentCatalog:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection):
        assert query == {}
        return DepartmentCursor(self.rows)


def canonical_department_rows():
    return [{"slug": item.slug, "active": True} for item in department_requirements()]


class WorkflowStore:
    def __init__(self, name, collections=(), departments=None):
        self.name = name
        self.collections = list(collections)
        self.departments = DepartmentCatalog(
            canonical_department_rows() if departments is None else departments
        )
        self.sim_runs = CountCollection()
        self.residents = CountCollection()
        self.staff_tasks = CountCollection()
        self.notifications = CountCollection()
        self.receipts = CountCollection(18)

    async def list_collection_names(self):
        return list(self.collections)


def test_non_pristine_scratch_stops_before_any_mutation(monkeypatch):
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("mutation boundary was reached")

    monkeypatch.setattr(acceptance, "prepare_required_indexes", forbidden)

    async def scenario():
        store = WorkflowStore("caoscare_sim_acceptance_20261013a", ["residents"])
        with pytest.raises(CommunityMongoAcceptanceError, match="not pristine"):
            await acceptance.run_scratch_acceptance(
                store, database_name=store.name, production_databases=("caoscare",),
                confirmed=True, operator_id="user:michael",
                operator_name="Michael", reopen_store=lambda: store,
            )

    asyncio.run(scenario())


def test_scratch_workflow_proves_two_events_reconnect_and_reset(monkeypatch):
    database = "caoscare_sim_acceptance_20261013a"
    store, reopened = WorkflowStore(database), WorkflowStore(database)
    calls = []
    plan = SimpleNamespace(events=(SimpleNamespace(event_id="one"),), cohort="burn_in_10",
                           resident_count=10, event_count=1)

    async def fake_probe(selected):
        calls.append(("probe", selected.name))
        return {"status": "passed", "topology": "replica_set",
                "transaction_read_abort": True, "error_type": None}

    async def fake_seed():
        calls.append(("seed", None))

    async def fake_indexes(*_args, **_kwargs):
        calls.append(("indexes", _kwargs["store"].name))
        return {"status": "ready", "receipt_id": "rcpt:indexes"}

    async def fake_create(*_args, **_kwargs):
        calls.append(("create", _kwargs["store"].name))
        return {"run": {"run_id": "run-1", "state": "PAUSED", "cursor": 0,
                        "sim_minute": 0},
                "receipt": {"receipt_id": "rcpt:create"}}

    async def fake_provision(*_args, **_kwargs):
        calls.append(("provision", _kwargs["store"].name))
        return {"run": {"run_id": "run-1", "state": "PAUSED", "cursor": 0,
                        "sim_minute": 0},
                "receipt": {"receipt_id": "rcpt:provision"}}

    transition_number = 0

    async def fake_transition(_operator, _authority, run_id, _before, after,
                              cursor, minute, *_args, **kwargs):
        nonlocal transition_number
        transition_number += 1
        calls.append((f"transition-{after}", kwargs["store"].name))
        return {"run": {"run_id": run_id, "state": after, "cursor": cursor,
                        "sim_minute": minute},
                "receipt": {"receipt_id": f"rcpt:transition:{transition_number}"}}

    tick_number = 0

    async def fake_tick(selected, _plan, run, _phase, _now):
        nonlocal tick_number
        tick_number += 1
        calls.append((f"tick-{tick_number}", selected.name))
        changed = {**run, "cursor": run["cursor"] + 1, "sim_minute": 30 + tick_number}
        return {"run": changed,
                "tick": SimpleNamespace(event_id=f"event-{tick_number}",
                                        receipt_id=f"rcpt:event:{tick_number}")}

    class FakeTimeline:
        def __init__(self, *, store, plan):
            calls.append(("restart-load", store.name))

        async def load_run(self, *, run_id):
            return {"run_id": run_id, "state": "PAUSED", "cursor": 1, "sim_minute": 31}

    async def fake_reset(
        _operator, _authority, _reset_key, expected_run_id, *, store, now,
    ):
        assert expected_run_id == "run-1"
        assert now is not None
        calls.append(("reset", store.name))
        return {"receipt_id": "rcpt:reset"}

    monkeypatch.setattr(acceptance, "probe_mongo", fake_probe)
    monkeypatch.setattr(acceptance, "canonical_plan", lambda cohort=None: plan)
    monkeypatch.setattr(acceptance, "prepare_required_indexes", fake_indexes)
    monkeypatch.setattr(acceptance.lifecycle, "create_burn_in_run", fake_create)
    monkeypatch.setattr(acceptance, "provision_paused_burn_in_run", fake_provision)
    monkeypatch.setattr(acceptance.lifecycle, "transition_run", fake_transition)
    monkeypatch.setattr(acceptance, "_advance_and_tick", fake_tick)
    monkeypatch.setattr(acceptance, "DatabaseRunnerTimeline", FakeTimeline)
    monkeypatch.setattr(acceptance, "reset_living_community", fake_reset)

    async def scenario():
        result = await acceptance.run_scratch_acceptance(
            store, database_name=database, production_databases=("caoscare",),
            confirmed=True, operator_id="user:michael",
            operator_name="Michael", reopen_store=lambda: reopened,
            seed_catalog=fake_seed,
        )
        assert result["status"] == "passed"
        assert calls.index(("seed", None)) < calls.index(("indexes", database))
        assert result["departments"] == sorted(
            item.slug for item in department_requirements()
        )
        assert result["events_executed"] == ["event-1", "event-2"]
        assert result["restart_reloaded_state"] == "PAUSED"
        assert result["final_run_state_before_reset"] == "STOPPED"
        assert result["reset"]["mutable_counts"] == {
            "sim_runs": 0, "residents": 0, "staff_tasks": 0, "notifications": 0,
        }
        assert result["reset"]["preserved_receipts"] == 18
        assert ("tick-1", database) in calls
        assert ("restart-load", database) in calls
        assert ("tick-2", database) in calls
        assert calls[-1] == ("reset", database)

    asyncio.run(scenario())


def test_missing_department_stops_scratch_acceptance_before_any_mutation(monkeypatch):
    """SIM-003: a fresh scratch database has no catalog; without the seed the
    real preflight must refuse before index preparation or any run write."""
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("mutation boundary was reached")

    async def fake_probe(_selected):
        return {"status": "passed", "topology": "replica_set",
                "transaction_read_abort": True, "error_type": None}

    monkeypatch.setattr(acceptance, "probe_mongo", fake_probe)
    monkeypatch.setattr(acceptance, "prepare_required_indexes", forbidden)
    monkeypatch.setattr(acceptance.lifecycle, "create_burn_in_run", forbidden)

    async def scenario():
        store = WorkflowStore("caoscare_sim_acceptance_20261013b", departments=[])
        with pytest.raises(DepartmentPreflightError):
            await acceptance.run_scratch_acceptance(
                store, database_name=store.name, production_databases=("caoscare",),
                confirmed=True, operator_id="user:michael",
                operator_name="Michael", reopen_store=lambda: store,
            )

    asyncio.run(scenario())
