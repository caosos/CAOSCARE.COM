"""Living-community residents never cross the automatic haiku AI boundary."""
import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException

from routes import haiku
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


class Cursor:
    def __init__(self, docs):
        self.docs = deepcopy(docs)
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.docs):
            raise StopAsyncIteration
        row = self.docs[self.index]
        self.index += 1
        return deepcopy(row)


class Collection:
    def __init__(self, docs=None):
        self.docs = [deepcopy(doc) for doc in (docs or [])]

    def find(self, query, projection=None):
        return Cursor(self.docs)

    async def find_one(self, query, projection=None, **kwargs):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return deepcopy(doc)
        return None

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))


class Store:
    def __init__(self, residents):
        self.residents = Collection(residents)
        self.haikus = Collection()


def _resident(resident_id, **fields):
    return {
        "resident_id": resident_id,
        "name": fields.pop("name", resident_id),
        "preferred_name": fields.pop("preferred_name", resident_id),
        **fields,
    }


def test_generate_today_skips_exact_and_malformed_community_rows(monkeypatch):
    residents = [
        _resident(
            "sim:resident:001", synthetic=True,
            simulation_scope=SIMULATION_SCOPE,
            simulation_community_id=COMMUNITY_ID,
        ),
        _resident(
            "malformed-community", synthetic=True,
            simulation_scope=SIMULATION_SCOPE,
            simulation_community_id="wrong-community",
        ),
        _resident("real-resident", synthetic=False),
        _resident("legacy-demo", synthetic=True, simulation_scope="demo_room"),
    ]
    store = Store(residents)
    provider_residents = []

    async def provider(_system, prompt):
        provider_residents.append(prompt)
        return "quiet evening\nold songs drift softly\nnight settles gently"

    monkeypatch.setattr(haiku, "db", store)
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", "configured")
    monkeypatch.setattr(haiku, "_openai_chat", provider)
    result = asyncio.run(haiku.generate_today(user={"role": "admin"}))

    assert result["created"] == 2
    assert result["skipped"] == 2
    assert result["failed"] == 0
    assert len(provider_residents) == 2
    assert {row["resident_id"] for row in store.haikus.docs} == {
        "real-resident", "legacy-demo",
    }


def test_all_community_bulk_is_a_skip_even_without_provider_configuration(monkeypatch):
    store = Store([
        _resident("sim:resident:001"),
        _resident("malformed", simulation_community_id=COMMUNITY_ID),
    ])
    provider_calls = []

    async def provider(*args):
        provider_calls.append(args)

    monkeypatch.setattr(haiku, "db", store)
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", "")
    monkeypatch.setattr(haiku, "_openai_chat", provider)
    result = asyncio.run(haiku.generate_today(user={"role": "admin"}))
    assert result["created"] == result["failed"] == 0
    assert result["skipped"] == 2
    assert provider_calls == []
    assert store.haikus.docs == []


@pytest.mark.parametrize("resident", [
    _resident("sim:resident:003"),
    _resident("partial-scope", synthetic=False, simulation_scope=SIMULATION_SCOPE),
    _resident("partial-community", synthetic=False, simulation_community_id=COMMUNITY_ID),
])
def test_direct_generation_refuses_before_provider_or_insert(monkeypatch, resident):
    store = Store([resident])
    provider_calls = []

    async def provider(*args):
        provider_calls.append(args)
        raise AssertionError("provider boundary must not be reached")

    monkeypatch.setattr(haiku, "db", store)
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", "configured")
    monkeypatch.setattr(haiku, "_openai_chat", provider)
    with pytest.raises(HTTPException) as error:
        asyncio.run(haiku.generate_for_resident(resident["resident_id"], user={"role": "admin"}))
    assert error.value.status_code == 409
    assert "living-community" in error.value.detail
    assert provider_calls == []
    assert store.haikus.docs == []


@pytest.mark.parametrize("resident", [
    _resident("real-resident", synthetic=False),
    _resident("legacy-demo", synthetic=True, simulation_scope="demo_room"),
])
def test_direct_generation_preserves_real_and_legacy_demo_behavior(monkeypatch, resident):
    store = Store([resident])
    provider_calls = []

    async def provider(*args):
        provider_calls.append(args)
        return "window light softens\nevening gathers old songs\npeace rests in the room"

    monkeypatch.setattr(haiku, "db", store)
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", "configured")
    monkeypatch.setattr(haiku, "_openai_chat", provider)
    result = asyncio.run(
        haiku.generate_for_resident(resident["resident_id"], user={"role": "admin"})
    )
    assert result["resident_id"] == resident["resident_id"]
    assert len(provider_calls) == 1
    assert len(store.haikus.docs) == 1
