"""Focused proof for safe, receipt-backed simulator index preparation."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from routes.actor_context import ActorContext
from simulation.community_index_contract import REQUIRED_INDEXES
from simulation.community_index_evidence import (
    COMPLETED, FAILED, RECONCILED, REQUESTED, contract_digest,
)
from simulation.community_index_inspection import inspect_index_contract
from simulation.community_index_preparation import (
    IndexPreparationError, prepare_required_indexes,
)


NOW = datetime(2026, 10, 13, 19, 30, tzinfo=timezone.utc)
OWNER = ActorContext(
    actor_id="user-michael", actor_type="real-human",
    identity_basis="authenticated", channel="staff_ui", name="Michael",
    role="owner", simulated=False,
)
AUTHORITY = "admin_override:owner"


def _matches(row, query):
    return all(row.get(key) == value for key, value in query.items())


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return deepcopy(self.rows)


class Collection:
    def __init__(self, name, indexes=None):
        self.name = name
        self.indexes = deepcopy(indexes or {"_id_": {"key": [("_id", 1)], "v": 2}})
        self.rows = []
        self.calls = []
        self.fail_probe = False
        self.fail_create = {}
        self.crash_create = set()
        self.fail_insert = 0

    async def index_information(self, session=None):
        self.calls.append(("inspect", session))
        if self.fail_probe:
            raise RuntimeError("secret database address")
        return deepcopy(self.indexes)

    async def create_index(self, keys, *, name, unique, session=None, partialFilterExpression=None):
        self.calls.append(("create", name, tuple(keys), unique, session))
        self.indexes[name] = {"key": list(keys), "unique": unique, "v": 2,
                              **({"partialFilterExpression": partialFilterExpression}
                                 if partialFilterExpression else {})}
        if name in self.crash_create:
            self.crash_create.remove(name)
            raise KeyboardInterrupt("injected crash")
        if name in self.fail_create:
            mode = self.fail_create.pop(name)
            if mode == "rollback":
                self.indexes.pop(name, None)
            raise RuntimeError("index build failed")
        return name

    def find(self, query, _projection=None, session=None):
        self.calls.append(("find", session))
        return Cursor([row for row in self.rows if _matches(row, query)])

    async def insert_one(self, row, session=None):
        self.calls.append(("insert", row.get("action_type"), session))
        if self.fail_insert:
            self.fail_insert -= 1
            raise RuntimeError("receipt unavailable")
        if any(existing.get("_id") == row.get("_id") for existing in self.rows):
            raise RuntimeError("duplicate _id")
        self.rows.append(deepcopy(row))


class Store:
    def __init__(self):
        self.sim_runs = Collection("sim_runs")
        self.receipts = Collection("receipts")
        self.staff_tasks = Collection("staff_tasks")


def _install_all(store, *, except_name=None):
    for row in REQUIRED_INDEXES:
        if row["name"] == except_name:
            continue
        collection = getattr(store, row["collection"])
        collection.indexes[row["name"]] = {
            "key": list(row["keys"]), "unique": row["unique"], "v": 2,
            **({"partialFilterExpression": row["partial"]} if row.get("partial") else {}),
        }


def _actions(store):
    return [row["action_type"] for row in store.receipts.rows]


def _run(coro):
    return asyncio.run(coro)


def test_creates_only_the_missing_required_indexes_and_writes_exact_provenance_chain():
    store = Store()
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "prepare-v1", store=store, now=NOW,
    ))

    assert result["status"] == "ready"
    assert result["action_type"] == COMPLETED
    assert set(result["created_indexes"]) == {row["name"] for row in REQUIRED_INDEXES}
    assert _actions(store) == [REQUESTED, COMPLETED]
    requested, completed = store.receipts.rows
    assert requested["actor_id"] == OWNER.actor_id
    assert requested["actor_type"] == "real-human"
    assert requested["identity_basis"] == "authenticated"
    assert requested["authority"] == AUTHORITY
    assert completed["actor_id"] == "system:living-community-index-preparer"
    assert completed["identity_basis"] == "system"
    assert completed["parent_receipt_id"] == requested["receipt_id"]
    assert completed["correlation_id"] == requested["receipt_id"]
    assert completed["index_contract_sha256"] == contract_digest()
    assert completed["result_label"] == "verified"
    assert all(not any(call[0] == "drop" for call in coll.calls)
               for coll in (store.sim_runs, store.receipts, store.staff_tasks))


def test_exact_existing_contract_is_verified_as_reconciled_without_ddl():
    store = Store()
    _install_all(store)
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "verify-existing", store=store, now=NOW,
    ))
    assert result["action_type"] == RECONCILED
    assert _actions(store) == [REQUESTED, RECONCILED]
    assert not any(call[0] == "create" for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    ) for call in collection.calls)


@pytest.mark.parametrize("mutation", ["keys", "unique", "partial", "equivalent_name"])
def test_conflicting_named_or_equivalent_definition_fails_closed(mutation):
    store = Store()
    _install_all(store)
    target = REQUIRED_INDEXES[1]
    collection = getattr(store, target["collection"])
    row = collection.indexes[target["name"]]
    if mutation == "keys":
        row["key"] = [("wrong", 1)]
    elif mutation == "unique":
        row["unique"] = True
    elif mutation == "partial":
        row["partialFilterExpression"] = {"simulation_run_id": {"$exists": True}}
    else:
        collection.indexes["same_keys_other_name"] = collection.indexes.pop(target["name"])

    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, f"conflict-{mutation}", store=store, now=NOW,
    ))
    assert result["status"] == "failed"
    assert result["action_type"] == FAILED
    assert _actions(store) == [REQUESTED, FAILED]
    assert store.receipts.rows[-1]["result_label"] == "failed"
    assert not any(call[0] == "create" for call in collection.calls)


def test_probe_failure_is_sanitized_and_no_index_is_created():
    store = Store()
    store.staff_tasks.fail_probe = True
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "probe-fail", store=store, now=NOW,
    ))
    assert result["status"] == "failed"
    snapshot = store.receipts.rows[-1]["after_state"]
    assert "secret database address" not in str(snapshot)
    assert any(row["error_type"] == "RuntimeError" for row in snapshot["indexes"])
    assert not any(call[0] == "create" for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    ) for call in collection.calls)


def test_create_failure_records_failed_state_and_never_claims_ready():
    store = Store()
    name = REQUIRED_INDEXES[2]["name"]
    store.receipts.fail_create[name] = "rollback"
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "build-fail", store=store, now=NOW,
    ))
    assert result["status"] == "failed"
    assert name in result["inspection"]["indexes"][2]["name"]
    failure = store.receipts.rows[-1]
    assert failure["action_type"] == FAILED
    assert failure["failure_reason"] == "index creation failed (RuntimeError)"


@pytest.mark.parametrize("operator,authority", [
    (ActorContext("sim", "simulated-agent", "synthetic", "simulator",
                  role="owner", simulated=True), AUTHORITY),
    (OWNER, "admin_override:admin"),
])
def test_requires_matching_authenticated_real_owner_or_admin(operator, authority):
    store = Store()
    with pytest.raises(IndexPreparationError, match="authenticated|authority"):
        _run(prepare_required_indexes(
            operator, authority, "unauthorized", store=store, now=NOW,
        ))
    assert store.receipts.rows == []
    assert not any(call[0] in {"inspect", "create"} for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    ) for call in collection.calls)


def test_operation_key_is_bound_to_original_authenticated_requester():
    store = Store()
    _run(prepare_required_indexes(
        OWNER, AUTHORITY, "bound-key", store=store, now=NOW,
    ))
    other = ActorContext(
        actor_id="user-other", actor_type="real-human",
        identity_basis="authenticated", channel="staff_ui", role="owner",
    )
    with pytest.raises(IndexPreparationError, match="another authenticated request"):
        _run(prepare_required_indexes(
            other, AUTHORITY, "bound-key", store=store, now=NOW,
        ))


def test_malformed_existing_evidence_fails_before_inspection_or_ddl():
    store = Store()
    with pytest.raises(KeyboardInterrupt):
        missing = REQUIRED_INDEXES[0]
        getattr(store, missing["collection"]).crash_create.add(missing["name"])
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "bad-evidence", store=store, now=NOW,
        ))
    store.receipts.rows[0]["authority"] = "admin_override:someone-else"
    prior_calls = sum(len(collection.calls) for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    ))
    with pytest.raises(IndexPreparationError, match="identity or provenance"):
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "bad-evidence", store=store, now=NOW,
            recover_interrupted=True,
        ))
    assert sum(len(collection.calls) for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    )) == prior_calls + 1  # exact evidence read only


def test_request_receipt_failure_prevents_every_index_change():
    store = Store()
    store.receipts.fail_insert = 1
    with pytest.raises(IndexPreparationError, match="no index change"):
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "request-write-fail", store=store, now=NOW,
        ))
    assert store.receipts.rows == []
    assert not any(call[0] == "create" for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    ) for call in collection.calls)


def test_session_is_forwarded_to_all_reads_writes_and_index_builds():
    store = Store()
    session = object()
    _run(prepare_required_indexes(
        OWNER, AUTHORITY, "session", store=store, session=session, now=NOW,
    ))
    for collection in (store.sim_runs, store.receipts, store.staff_tasks):
        relevant = [call for call in collection.calls if call[0] in {"inspect", "create", "find", "insert"}]
        assert relevant
        assert all(call[-1] is session for call in relevant)


def test_read_only_inspection_reports_all_exact_contract_entries():
    store = Store()
    _install_all(store)
    report = _run(inspect_index_contract(store, session="read-session"))
    assert report["ready"] is True
    assert [row["name"] for row in report["required"]] == [
        row["name"] for row in REQUIRED_INDEXES
    ]
    assert all(call == ("inspect", "read-session") for collection in (
        store.sim_runs, store.receipts, store.staff_tasks
    ) for call in collection.calls)
