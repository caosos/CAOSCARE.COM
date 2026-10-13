"""P1A burn-in provisioning never collides with or disguises real data."""
import asyncio
from copy import deepcopy

import pytest

from routes.actor_context import ActorContext
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_provisioning import ProvisioningError, provision_burn_in_residents


RUN_ID = "simrun-living-markers-1"


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


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, limit):
        return deepcopy(self.docs[:limit])


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [deepcopy(doc) for doc in (docs or [])]
        self.inserts = 0

    async def find_one(self, query, projection=None, **_kwargs):
        return next((deepcopy(doc) for doc in self.docs if _matches(doc, query)), None)

    def find(self, query, projection=None):
        return FakeCursor([doc for doc in self.docs if _matches(doc, query)])

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))
        self.inserts += 1
        return object()


class FakeStore:
    def __init__(self, residents=None):
        self.residents = FakeCollection(residents)
        self.receipts = FakeCollection()
        self.users = FakeCollection()


def operator(role="owner"):
    return ActorContext(
        actor_id="user_real_owner",
        actor_type="real-human",
        identity_basis="authenticated",
        channel="staff_ui",
        name="Authenticated Operator",
        role=role,
    )


def document(recipe):
    return {
        **recipe.resident_payload(),
        "created_at": "2026-10-13T00:00:00+00:00",
        "simulation_scope": recipe.simulation_scope,
        "simulation_community_id": recipe.simulation_community_id,
    }


def receipt_writer(store):
    async def write(**kwargs):
        doc = {**kwargs, **kwargs.pop("provenance")}
        doc["receipt_id"] = kwargs.get("receipt_id")
        await store.receipts.insert_one(doc)
        return doc
    return write


async def provision(
    store, actor=None, authority="admin_override:owner", simulation_run_id=None,
):
    return await provision_burn_in_residents(
        actor or operator(), authority, store=store,
        receipt_writer=receipt_writer(store), document_factory=document,
        simulation_run_id=simulation_run_id,
    )


def test_creates_exactly_ten_canonical_residents_with_real_operator_receipts():
    async def run():
        store = FakeStore()
        result = await provision(store, simulation_run_id=RUN_ID)
        assert len(result["resident_ids"]) == len(result["created_ids"]) == 10
        assert result["reused_ids"] == []
        assert store.residents.inserts == 10
        assert store.users.inserts == 0
        assert len(store.receipts.docs) == 10
        for resident in store.residents.docs:
            assert resident["synthetic"] is True
            assert resident["simulation_scope"] == SIMULATION_SCOPE
            assert resident["simulation_community_id"] == COMMUNITY_ID
        for receipt in store.receipts.docs:
            assert receipt["actor_id"] == "user_real_owner"
            assert receipt["actor_type"] == "real-human"
            assert receipt["identity_basis"] == "authenticated"
            assert receipt["simulated"] is False
            assert receipt["authority"] == "admin_override:owner"
            assert receipt["result_label"] == "simulated"
            assert receipt["simulation_scope"] == SIMULATION_SCOPE
            assert receipt["simulation_community_id"] == COMMUNITY_ID
            assert receipt["simulation_run_id"] == RUN_ID
            assert receipt["after_state"]["simulation_community_id"] == COMMUNITY_ID
        return store, result

    store, first = asyncio.run(run())
    assert first["resident_ids"] == [r.resident_id for r in BURN_IN_RESIDENTS]


def test_top_level_target_markers_do_not_require_or_invent_a_run_id():
    async def run():
        store = FakeStore()
        await provision(store)
        assert all(r["simulation_scope"] == SIMULATION_SCOPE for r in store.receipts.docs)
        assert all(r["simulation_community_id"] == COMMUNITY_ID for r in store.receipts.docs)
        assert all("simulation_run_id" not in r for r in store.receipts.docs)
        assert all(r["simulated"] is False for r in store.receipts.docs)

    asyncio.run(run())


def test_second_run_reuses_residents_and_receipts_without_writes():
    async def run():
        store = FakeStore()
        first = await provision(store)
        second = await provision(store)
        assert store.residents.inserts == 10
        assert store.receipts.inserts == 10
        assert second["created_ids"] == []
        assert second["reused_ids"] == first["resident_ids"]
        assert [r["receipt_id"] for r in second["receipts"]] == [r["receipt_id"] for r in first["receipts"]]

    asyncio.run(run())


@pytest.mark.parametrize("field", ["resident_id", "room", "pendant_id"])
def test_unmarked_real_identity_collision_refuses_every_write(field):
    async def run():
        recipe = BURN_IN_RESIDENTS[4]
        real = {"resident_id": "real_resident", "room": "REAL-ROOM", "pendant_id": "real-pendant"}
        real[field] = getattr(recipe, field)
        store = FakeStore([real])
        with pytest.raises(ProvisioningError, match="collision"):
            await provision(store)
        assert store.residents.inserts == 0
        assert store.receipts.inserts == 0
        assert store.users.inserts == 0

    asyncio.run(run())


def test_wrong_community_marker_and_split_identity_are_refused():
    async def run():
        recipe = BURN_IN_RESIDENTS[0]
        wrong = {**document(recipe), "simulation_community_id": "sim:community:other"}
        store = FakeStore([wrong])
        with pytest.raises(ProvisioningError, match="collision"):
            await provision(store)
        assert store.residents.inserts == 0

        split = FakeStore([
            {**document(recipe), "room": "SIM-OTHER"},
            {"resident_id": "real", "room": recipe.room, "pendant_id": "real-pendant"},
        ])
        with pytest.raises(ProvisioningError, match="split identity"):
            await provision(split)
        assert split.residents.inserts == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    "actor,authority",
    [
        (operator("staff"), "admin_override:staff"),
        (ActorContext("sim", "simulated-agent", "synthetic", "simulator", role="admin", simulated=True), "admin_override:admin"),
        (operator("owner"), "admin_override:admin"),
    ],
)
def test_requires_matching_authenticated_real_admin_authority(actor, authority):
    store = FakeStore()
    with pytest.raises(ProvisioningError, match="authenticated|authority"):
        asyncio.run(provision(store, actor=actor, authority=authority))
    assert store.residents.inserts == 0
    assert store.receipts.inserts == 0


def test_marked_existing_row_without_receipt_gets_truthful_reconciliation_receipt():
    async def run():
        existing = document(BURN_IN_RESIDENTS[0])
        store = FakeStore([existing])
        result = await provision(store)
        assert result["reused_ids"] == [BURN_IN_RESIDENTS[0].resident_id]
        first_receipt = next(r for r in result["receipts"] if r["related_object_id"] == existing["resident_id"])
        assert first_receipt["action_type"] == "simulation_resident_reconciled"
        assert first_receipt["before_state"] == first_receipt["after_state"]

    asyncio.run(run())


def test_document_factory_cannot_change_blueprint_identity():
    async def run():
        store = FakeStore()
        with pytest.raises(ProvisioningError, match="document factory changed"):
            await provision_burn_in_residents(
                operator(), "admin_override:owner", store=store,
                receipt_writer=receipt_writer(store),
                document_factory=lambda recipe: {**document(recipe), "room": "REAL-ROOM"},
            )
        assert store.residents.inserts == 0
        assert store.receipts.inserts == 0

    asyncio.run(run())
