"""Generic resident CRUD must not mutate simulator-managed residents."""
import asyncio
from copy import deepcopy
import os
import sys
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ResidentCreate  # noqa: E402
from routes import admin_assistant_executor, residents  # noqa: E402


RID = "sim:resident:001"
USER = {"user_id": "owner-1", "name": "Owner", "role": "owner"}


class _Result:
    def __init__(self, count):
        self.matched_count = count
        self.deleted_count = count


class _Residents:
    def __init__(self, doc, *, protect_on_write=False):
        self.doc = deepcopy(doc)
        self.protect_on_write = protect_on_write
        self.last_mutation_filter = None

    async def find_one(self, query, projection=None):
        if not self.doc or query.get("resident_id") != self.doc.get("resident_id"):
            return None
        return deepcopy(self.doc)

    def _become_protected(self):
        if self.protect_on_write:
            self.doc.update(
                synthetic=True,
                simulation_scope=residents.LIVING_COMMUNITY_SCOPE,
                simulation_community_id=residents.LIVING_COMMUNITY_ID,
            )
            self.protect_on_write = False

    def _matches(self, query):
        if not self.doc or query.get("resident_id") != self.doc.get("resident_id"):
            return False
        outside_scope = self.doc.get("simulation_scope") != residents.LIVING_COMMUNITY_SCOPE
        allowed_living_row = (
            self.doc.get("simulation_scope") == residents.LIVING_COMMUNITY_SCOPE
            and self.doc.get("simulation_community_id") == residents.LIVING_COMMUNITY_ID
            and self.doc.get("synthetic") is not True
        )
        return outside_scope or allowed_living_row

    async def update_one(self, query, update):
        self._become_protected()
        self.last_mutation_filter = deepcopy(query)
        if not self._matches(query):
            return _Result(0)
        self.doc.update(deepcopy(update["$set"]))
        return _Result(1)

    async def delete_one(self, query):
        self._become_protected()
        self.last_mutation_filter = deepcopy(query)
        if not self._matches(query):
            return _Result(0)
        self.doc = None
        return _Result(1)


def _doc(**extra):
    return {
        "resident_id": RID,
        "name": "Resident One",
        "room": "SIM-001",
        "pendant_id": "sim:pendant:001",
        "preferred_name": "One",
        "participation_level": "pendant_enhanced",
        "aria_guidance_profile": "supportive_guided",
        **extra,
    }


def _payload(name="Changed"):
    return ResidentCreate(
        name=name,
        room="SIM-001",
        pendant_id="sim:pendant:001",
        preferred_name="One",
    )


def _install(monkeypatch, doc, *, protect_on_write=False):
    collection = _Residents(doc, protect_on_write=protect_on_write)
    store = SimpleNamespace(residents=collection)
    monkeypatch.setattr(residents, "db", store)
    monkeypatch.setattr(admin_assistant_executor, "db", store)

    async def receipt(**kwargs):
        return kwargs

    monkeypatch.setattr(residents, "create_receipt", receipt)
    return collection


async def _invoke(kind):
    if kind == "put":
        return await residents.update_resident(RID, _payload(), user=USER)
    if kind == "delete":
        return await residents.delete_resident(RID, user=USER)
    return await residents.update_preferred_name(RID, {"preferred_name": "New name"})


@pytest.mark.parametrize("kind", ["put", "delete", "preferred_name"])
def test_exact_living_community_resident_is_refused(monkeypatch, kind):
    collection = _install(
        monkeypatch,
        _doc(
            synthetic=True,
            simulation_scope=residents.LIVING_COMMUNITY_SCOPE,
            simulation_community_id=residents.LIVING_COMMUNITY_ID,
        ),
    )
    before = deepcopy(collection.doc)
    with pytest.raises(HTTPException) as error:
        asyncio.run(_invoke(kind))
    assert error.value.status_code == 409
    assert "living-community simulator" in error.value.detail
    assert collection.doc == before
    assert collection.last_mutation_filter is None


@pytest.mark.parametrize("community_id", [None, "sim:community:other"])
def test_living_scope_with_invalid_community_id_fails_closed(monkeypatch, community_id):
    collection = _install(
        monkeypatch,
        _doc(
            synthetic=True,
            simulation_scope=residents.LIVING_COMMUNITY_SCOPE,
            simulation_community_id=community_id,
        ),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(residents.update_resident(RID, _payload(), user=USER))
    assert error.value.status_code == 409
    assert "markers are invalid" in error.value.detail
    assert collection.doc["name"] == "Resident One"


@pytest.mark.parametrize(
    "markers",
    [
        {},
        {"synthetic": True, "simulation_scope": "demo_room"},
        {
            "synthetic": False,
            "simulation_scope": residents.LIVING_COMMUNITY_SCOPE,
            "simulation_community_id": residents.LIVING_COMMUNITY_ID,
        },
    ],
)
def test_non_managed_residents_keep_existing_crud_behavior(monkeypatch, markers):
    collection = _install(monkeypatch, _doc(**markers))
    updated = asyncio.run(residents.update_resident(RID, _payload("Updated"), user=USER))
    assert updated["name"] == "Updated"
    renamed = asyncio.run(
        residents.update_preferred_name(RID, {"preferred_name": "Preferred"})
    )
    assert renamed["preferred_name"] == "Preferred"
    assert asyncio.run(residents.delete_resident(RID, user=USER)) == {"ok": True}
    assert collection.doc is None


@pytest.mark.parametrize("kind", ["put", "delete", "preferred_name"])
def test_atomic_filter_blocks_row_that_becomes_managed_after_read(monkeypatch, kind):
    collection = _install(monkeypatch, _doc(), protect_on_write=True)
    with pytest.raises(HTTPException) as error:
        asyncio.run(_invoke(kind))
    assert error.value.status_code == 409
    assert collection.doc is not None
    assert collection.doc["name"] == "Resident One"
    assert "$or" in collection.last_mutation_filter


def test_admin_assistant_inherits_shared_route_guard(monkeypatch):
    collection = _install(
        monkeypatch,
        _doc(
            synthetic=True,
            simulation_scope=residents.LIVING_COMMUNITY_SCOPE,
            simulation_community_id=residents.LIVING_COMMUNITY_ID,
        ),
    )
    result = asyncio.run(
        admin_assistant_executor.update_resident(USER, {"resident_id": RID, "room": "SIM-009"})
    )
    assert result["status"] == "failed"
    assert result["detail"].startswith("409:")
    assert collection.doc["room"] == "SIM-001"
