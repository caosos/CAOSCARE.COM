"""P1A cleanup is exact, receipted, idempotent, and synthetic-only."""
import asyncio
from copy import deepcopy

import pytest

from routes.actor_context import ActorContext
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_cleanup import CleanupError, cleanup_burn_in_residents
from simulation.community_provisioning import provision_burn_in_residents


def _matches(doc, query):
    for key, wanted in query.items():
        if key == "$or":
            if not any(_matches(doc, alternative) for alternative in wanted):
                return False
            continue
        actual = doc.get(key)
        if isinstance(wanted, dict) and "$in" in wanted:
            if actual not in wanted["$in"]:
                return False
        elif actual != wanted:
            return False
    return True


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, limit):
        return deepcopy(self.docs[:limit])


class DeleteResult:
    def __init__(self, count):
        self.deleted_count = count


class Collection:
    def __init__(self, docs=None):
        self.docs = [deepcopy(doc) for doc in (docs or [])]
        self.inserts = 0
        self.deletes = 0

    def find(self, query, projection=None):
        return Cursor([doc for doc in self.docs if _matches(doc, query)])

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc)); self.inserts += 1
        return object()

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if _matches(doc, query):
                self.docs.pop(index); self.deletes += 1
                return DeleteResult(1)
        return DeleteResult(0)


class Store:
    def __init__(self, residents=None):
        self.residents = Collection(residents)
        self.receipts = Collection()
        self.users = Collection()


def operator(role="owner"):
    return ActorContext(
        "user_owner", "real-human", "authenticated", "staff_ui",
        name="Authenticated Operator", role=role,
    )


def resident_doc(recipe):
    return {
        **recipe.resident_payload(),
        "created_at": "2026-10-13T00:00:00+00:00",
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }


def writer(store):
    async def write(**kwargs):
        provenance = kwargs.pop("provenance")
        doc = {**kwargs, **provenance}
        await store.receipts.insert_one(doc)
        return doc
    return write


async def provision(store):
    return await provision_burn_in_residents(
        operator(), "admin_override:owner", store=store,
        receipt_writer=writer(store), document_factory=resident_doc,
    )


async def cleanup(store, actor=None, authority="admin_override:owner"):
    return await cleanup_burn_in_residents(
        actor or operator(), authority, store=store, receipt_writer=writer(store)
    )


def test_cleanup_removes_exactly_ten_residents_and_preserves_evidence():
    async def run():
        store = Store(); await provision(store)
        result = await cleanup(store)
        assert result["removed_ids"] == [r.resident_id for r in BURN_IN_RESIDENTS]
        assert result["already_absent_ids"] == result["reconciled_ids"] == []
        assert store.residents.docs == []
        assert store.residents.deletes == 10
        assert store.users.deletes == store.users.inserts == 0
        actions = [r["action_type"] for r in store.receipts.docs]
        assert actions.count("simulation_resident_cleanup_requested") == 10
        assert actions.count("simulation_resident_removed") == 10
        removed = [r for r in store.receipts.docs if r["action_type"] == "simulation_resident_removed"]
        assert all(r["actor_type"] == "real-human" for r in removed)
        assert all(r["authority"] == "admin_override:owner" for r in removed)
        assert all(r["before_state"]["simulation_community_id"] == COMMUNITY_ID for r in removed)
        assert all(r["after_state"]["state"] == "absent" for r in removed)
        return store

    store = asyncio.run(run())
    # Provisioning receipts remain as append-only history after resident deletion.
    assert sum(r["action_type"] == "simulation_resident_provisioned" for r in store.receipts.docs) == 10


def test_cleanup_replay_is_idempotent_and_reuses_outcome_receipts():
    async def run():
        store = Store(); await provision(store)
        first = await cleanup(store)
        receipt_count = len(store.receipts.docs)
        second = await cleanup(store)
        assert second["removed_ids"] == []
        assert second["already_absent_ids"] == first["removed_ids"]
        assert len(store.receipts.docs) == receipt_count
        assert [r["receipt_id"] for r in second["receipts"]] == [r["receipt_id"] for r in first["receipts"]]

    asyncio.run(run())


def test_empty_community_is_an_idempotent_noop_without_receipts():
    async def run():
        store = Store(); result = await cleanup(store)
        assert result["removed_ids"] == result["reconciled_ids"] == []
        assert len(result["already_absent_ids"]) == 10
        assert store.receipts.docs == []
        assert store.residents.deletes == 0

    asyncio.run(run())


@pytest.mark.parametrize("field", ["resident_id", "room", "pendant_id"])
def test_any_unmarked_real_collision_blocks_every_delete(field):
    async def run():
        residents = [resident_doc(r) for r in BURN_IN_RESIDENTS]
        target = BURN_IN_RESIDENTS[5]
        residents[5] = {"resident_id": "real", "room": "REAL", "pendant_id": "real-pendant"}
        residents[5][field] = getattr(target, field)
        store = Store(residents)
        with pytest.raises(CleanupError, match="collision"):
            await cleanup(store)
        assert store.residents.deletes == 0
        assert store.receipts.docs == []

    asyncio.run(run())


@pytest.mark.parametrize(("field", "value"), [
    ("simulation_scope", None),
    ("simulation_scope", "other-scope"),
    ("simulation_community_id", "other-community"),
    ("synthetic", False),
])
def test_partial_or_wrong_markers_block_every_delete(field, value):
    async def run():
        residents = [resident_doc(r) for r in BURN_IN_RESIDENTS]
        if value is None:
            residents[-1].pop(field)
        else:
            residents[-1][field] = value
        store = Store(residents)
        with pytest.raises(CleanupError, match="collision"):
            await cleanup(store)
        assert len(store.residents.docs) == 10
        assert store.residents.deletes == 0

    asyncio.run(run())


def test_split_identity_is_ambiguous_and_blocks_every_delete():
    async def run():
        residents = [resident_doc(r) for r in BURN_IN_RESIDENTS]
        residents.append({
            "resident_id": "real-resident",
            "room": "REAL",
            "pendant_id": BURN_IN_RESIDENTS[0].pendant_id,
        })
        store = Store(residents)
        with pytest.raises(CleanupError, match="split identity collision"):
            await cleanup(store)
        assert store.residents.deletes == 0
        assert store.receipts.docs == []

    asyncio.run(run())


def test_reprovisioned_resident_gets_a_new_cleanup_authorization_cycle():
    async def run():
        store = Store(); await provision(store)
        first = await cleanup(store)
        await provision(store)
        provisioned = [r for r in store.receipts.docs if r["action_type"] ==
                       "simulation_resident_provisioned"]
        assert len(provisioned) == 20
        assert len({r["receipt_id"] for r in provisioned}) == 20
        second = await cleanup(store)
        assert second["removed_ids"] == first["removed_ids"]
        requests = [r for r in store.receipts.docs if r["action_type"] ==
                    "simulation_resident_cleanup_requested"]
        assert len(requests) == 20
        assert len({r["receipt_id"] for r in requests}) == 20

    asyncio.run(run())


def test_missing_completion_after_recorded_request_is_reconciled_truthfully():
    async def run():
        store = Store([resident_doc(r) for r in BURN_IN_RESIDENTS])
        await cleanup(store)
        # Recreate the crash boundary for one identity: keep its request, remove its completion.
        target = BURN_IN_RESIDENTS[0]
        store.receipts.docs = [r for r in store.receipts.docs if not (
            r["related_object_id"] == target.resident_id
            and r["action_type"] == "simulation_resident_removed"
        )]
        second = await cleanup(store)
        assert second["reconciled_ids"] == [target.resident_id]
        receipt = next(r for r in second["receipts"] if r["related_object_id"] == target.resident_id)
        assert receipt["action_type"] == "simulation_resident_cleanup_reconciled"
        assert receipt["result_label"] == "unverified"
        assert "already absent" in receipt["result"]

    asyncio.run(run())


def test_cleanup_requires_real_authenticated_admin_authority():
    store = Store()
    with pytest.raises(CleanupError, match="authenticated"):
        asyncio.run(cleanup(store, actor=operator("staff"), authority="admin_override:staff"))
    assert store.residents.deletes == 0
