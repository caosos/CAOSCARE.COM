"""Living-community reset is transactional, exact, and append-only."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_reset import (
    CommunityResetError,
    OUTCOME_ACTION,
    REPLAY_ACTION,
    REQUEST_ACTION,
    reset_living_community,
)


NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def _value(doc, path):
    value = doc
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _matches(doc, query):
    for key, wanted in query.items():
        if key == "$or":
            if not any(_matches(doc, option) for option in wanted):
                return False
            continue
        actual = _value(doc, key)
        if isinstance(wanted, dict) and "$in" in wanted:
            if actual not in wanted["$in"]:
                return False
        elif actual != wanted:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, _limit):
        return deepcopy(self.docs)


class DeleteResult:
    def __init__(self, count):
        self.deleted_count = count


class Collection:
    def __init__(self, store, name, docs=None):
        self.store, self.name = store, name
        self.docs = [deepcopy(row) for row in (docs or [])]

    def find(self, query, projection=None, session=None):
        assert session is self.store.session
        return Cursor([row for row in self.docs if _matches(row, query)])

    async def insert_one(self, doc, session=None):
        assert session is self.store.session
        self.docs.append(deepcopy(doc))

    async def delete_many(self, query, session=None):
        assert session is self.store.session
        kept, count = [], 0
        for row in self.docs:
            if _matches(row, query):
                count += 1
            else:
                kept.append(row)
        self.docs = kept
        if self.store.fail_delete == self.name:
            raise RuntimeError("injected transactional delete failure")
        return DeleteResult(count)


class Transaction:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.snapshot = {
            name: deepcopy(getattr(self.session.store, name).docs)
            for name in self.session.store.collection_names
        }
        return self

    async def __aexit__(self, exc_type, _exc, _tb):
        if exc_type:
            for name, docs in self.session.snapshot.items():
                getattr(self.session.store, name).docs = docs
        return False


class Session:
    def __init__(self, store):
        self.store, self.snapshot = store, None

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False

    def start_transaction(self):
        return Transaction(self)


class Client:
    def __init__(self, store):
        self.store = store

    async def start_session(self):
        return self.store.session


class Store:
    collection_names = ("residents", "staff_tasks", "notifications", "sim_runs", "receipts")

    def __init__(self, *, fail_delete=None):
        self.fail_delete = fail_delete
        self.session = Session(self)
        self.client = Client(self)
        for name in self.collection_names:
            setattr(self, name, Collection(self, name))


def operator(role="owner", **changes):
    values = {
        "actor_id": "owner-1", "actor_type": "real-human",
        "identity_basis": "authenticated", "channel": "staff_ui",
        "name": "Owner", "role": role, "simulated": False,
    }
    values.update(changes)
    return ActorContext(**values)


def marked(**fields):
    return {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        **fields,
    }


def populate(store):
    store.residents.docs.extend([
        marked(resident_id="sim:resident:001", room="SIM-001", pendant_id="sim:pendant:001", synthetic=True),
        {"resident_id": "real-1", "room": "101", "synthetic": False},
        {"resident_id": "demo-1", "room": "DEMO", "synthetic": True,
         "simulation_scope": "demo_room"},
    ])
    store.staff_tasks.docs.extend([
        marked(task_id="task-sim", resident_id="sim:resident:001", simulated=True,
               simulation_run_id="run-1"),
        {"task_id": "task-real", "resident_id": "real-1", "simulated": False},
    ])
    store.notifications.docs.extend([
        marked(notification_id="note-sim", resident_id="sim:resident:001",
               simulated=True, status="simulated", simulation_run_id="run-1"),
        {"notification_id": "note-demo", "simulated": True, "status": "simulated",
         "simulation_scope": "demo_room"},
    ])
    store.sim_runs.docs.extend([
        marked(run_id="run-1", state="STOPPED"),
        {"run_id": "old-demo", "state": "STOPPED", "simulation_scope": "demo_room"},
    ])
    store.receipts.docs.extend([
        marked(receipt_id="history-1", action_type="resident_request_created",
               related_object_type="task", related_object_id="task-sim",
               resident_id="sim:resident:001", simulation_run_id="run-1"),
        {"receipt_id": "real-history", "related_object_id": "task-real"},
    ])


async def reset(store, key="operator-reset-1", actor=None, authority="admin_override:owner"):
    return await reset_living_community(
        actor or operator(), authority, key, store=store, now=NOW,
    )


def test_reset_commits_exact_scope_and_never_touches_real_or_demo_rows():
    async def run():
        store = Store(); populate(store)
        result = await reset(store)
        assert result["deleted"] == {
            "notifications": 1, "staff_tasks": 1, "sim_runs": 1, "residents": 1,
        }
        assert [row["resident_id"] for row in store.residents.docs] == ["real-1", "demo-1"]
        assert [row["task_id"] for row in store.staff_tasks.docs] == ["task-real"]
        assert [row["notification_id"] for row in store.notifications.docs] == ["note-demo"]
        assert [row["run_id"] for row in store.sim_runs.docs] == ["old-demo"]
        actions = [row.get("action_type") for row in store.receipts.docs]
        assert actions[-2:] == [REQUEST_ACTION, OUTCOME_ACTION]
        request, outcome = store.receipts.docs[-2:]
        assert request["before_state"]["counts"]["residents"] == 1
        assert outcome["after_state"]["counts"] == {
            "residents": 0, "staff_tasks": 0, "notifications": 0, "sim_runs": 0,
        }
        assert outcome["parent_receipt_id"] == request["receipt_id"]
        assert outcome["actor_type"] == "real-human"
        assert outcome["authority"] == "admin_override:owner"
        assert outcome["simulation_community_id"] == COMMUNITY_ID
        assert any(row["receipt_id"] == "history-1" for row in store.receipts.docs)
    asyncio.run(run())


def test_retry_is_idempotent_and_appends_replay_evidence():
    async def run():
        store = Store(); populate(store)
        first = await reset(store)
        second = await reset(store)
        assert first["reset_id"] == second["reset_id"]
        assert first["reset_generation"] == second["reset_generation"] == 1
        assert second["idempotent_replay"] is True
        assert second["deleted"] == {name: 0 for name in (
            "residents", "staff_tasks", "notifications", "sim_runs",
        )}
        replay = store.receipts.docs[-1]
        assert replay["action_type"] == REPLAY_ACTION
        assert replay["parent_receipt_id"] == first["receipt_id"]
        assert replay["before_state"] == replay["after_state"]
    asyncio.run(run())


@pytest.mark.parametrize("state", ["RUNNING", "PAUSED", None])
def test_reset_requires_stopped_run(state):
    async def run():
        store = Store(); populate(store)
        store.sim_runs.docs[0]["state"] = state
        with pytest.raises(CommunityResetError, match="STOPPED"):
            await reset(store)
        assert len(store.receipts.docs) == 2
        assert any(row.get("run_id") == "run-1" for row in store.sim_runs.docs)
    asyncio.run(run())


def test_partial_marker_or_real_linked_dependency_fails_before_write():
    async def run():
        store = Store(); populate(store)
        store.staff_tasks.docs.append({
            "task_id": "ambiguous", "resident_id": "sim:resident:001",
            "simulated": False,
        })
        before = deepcopy({name: getattr(store, name).docs for name in store.collection_names})
        with pytest.raises(CommunityResetError, match="unmarked dependency"):
            await reset(store)
        assert before == {name: getattr(store, name).docs for name in store.collection_names}
    asyncio.run(run())


def test_transaction_failure_rolls_back_deletes_and_request_receipt():
    async def run():
        store = Store(fail_delete="staff_tasks"); populate(store)
        before = deepcopy({name: getattr(store, name).docs for name in store.collection_names})
        with pytest.raises(CommunityResetError, match="rolled back"):
            await reset(store)
        assert before == {name: getattr(store, name).docs for name in store.collection_names}
    asyncio.run(run())


def test_missing_transaction_support_and_wrong_actor_fail_closed():
    async def run():
        store = Store(); populate(store)
        store.client = None
        with pytest.raises(CommunityResetError, match="transaction-capable"):
            await reset(store)
        store.client = Client(store)
        with pytest.raises(CommunityResetError, match="authenticated real owner or admin"):
            await reset(store, actor=operator(actor_type="simulated-agent", simulated=True))
        with pytest.raises(CommunityResetError, match="authority"):
            await reset(store, authority="admin_override:admin")
        assert len(store.receipts.docs) == 2
    asyncio.run(run())


def test_new_key_advances_generation_after_new_exact_data_exists():
    async def run():
        store = Store(); populate(store)
        first = await reset(store, "generation-one")
        store.residents.docs.append(marked(
            resident_id="sim:resident:002", room="SIM-002",
            pendant_id="sim:pendant:002", synthetic=True,
        ))
        second = await reset(store, "generation-two")
        assert first["reset_generation"] == 1
        assert second["reset_generation"] == 2
        assert second["deleted"]["residents"] == 1
    asyncio.run(run())
