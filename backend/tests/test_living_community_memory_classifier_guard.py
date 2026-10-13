"""Living-community text never reaches memory/classifier AI providers."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from routes import ai, memory
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


def _matches(row, query):
    return all(row.get(key) == value for key, value in query.items())


class Cursor:
    def __init__(self, rows):
        self.rows = [deepcopy(row) for row in rows]

    def sort(self, *_args):
        return self

    async def to_list(self, limit):
        return deepcopy(self.rows[:limit])


class Collection:
    def __init__(self, rows=()):
        self.rows = [deepcopy(row) for row in rows]

    async def find_one(self, query, _projection=None, **_kwargs):
        return next(
            (deepcopy(row) for row in self.rows if _matches(row, query)),
            None,
        )

    def find(self, query, _projection=None):
        return Cursor(row for row in self.rows if _matches(row, query))

    async def update_one(self, query, update):
        for row in self.rows:
            if _matches(row, query):
                row.update(deepcopy(update.get("$set") or {}))
                return


def _store(residents, alerts=()):
    return SimpleNamespace(
        residents=Collection(residents),
        alerts=Collection(alerts),
        conversations=Collection(),
    )


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("resident_id,resident", [
    ("sim:resident:001", None),
    ("living-exact", {
        "resident_id": "living-exact", "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }),
    ("living-partial-scope", {
        "resident_id": "living-partial-scope", "synthetic": False,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": "wrong-community",
    }),
    ("living-partial-community", {
        "resident_id": "living-partial-community", "synthetic": False,
        "simulation_scope": "wrong-scope",
        "simulation_community_id": COMMUNITY_ID,
    }),
])
def test_memory_extractor_excludes_reserved_exact_and_partial_rows(
    monkeypatch, resident_id, resident,
):
    provider_calls = []

    async def provider(*args, **kwargs):
        provider_calls.append((args, kwargs))
        raise AssertionError("living-community memory reached provider")

    monkeypatch.setattr(memory, "db", _store([resident] if resident else []))
    monkeypatch.setattr(memory, "OPENAI_API_KEY", "configured")
    monkeypatch.setattr(memory, "_openai_chat", provider)

    saved = _run(memory.extract_and_store_memories(
        resident_id, "session-1", "I like jazz", "I'll remember that.",
    ))

    assert saved == 0
    assert provider_calls == []


@pytest.mark.parametrize("resident", [
    {"resident_id": "real-resident", "synthetic": False},
    {"resident_id": "legacy-demo", "synthetic": True,
     "simulation_scope": "demo_room"},
])
def test_memory_extractor_preserves_real_and_legacy_demo_provider_path(
    monkeypatch, resident,
):
    provider_calls = []

    async def provider(*args, **kwargs):
        provider_calls.append((args, kwargs))
        return "[]"

    monkeypatch.setattr(memory, "db", _store([resident]))
    monkeypatch.setattr(memory, "OPENAI_API_KEY", "configured")
    monkeypatch.setattr(memory, "_openai_chat", provider)

    saved = _run(memory.extract_and_store_memories(
        resident["resident_id"], "session-1", "Hello", "Hello.",
    ))

    assert saved == 0
    assert len(provider_calls) == 1


@pytest.mark.parametrize("resident_id,resident", [
    ("sim:resident:075", None),
    ("living-exact", {
        "resident_id": "living-exact", "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }),
    ("living-partial-scope", {
        "resident_id": "living-partial-scope", "synthetic": False,
        "simulation_scope": SIMULATION_SCOPE,
    }),
    ("living-partial-community", {
        "resident_id": "living-partial-community", "synthetic": False,
        "simulation_community_id": COMMUNITY_ID,
    }),
])
def test_alert_classifier_excludes_reserved_exact_and_partial_resident_truth(
    monkeypatch, resident_id, resident,
):
    provider_calls = []
    alert = {"alert_id": "alert-1", "resident_id": resident_id, "severity": "assist"}

    async def provider(*args, **kwargs):
        provider_calls.append((args, kwargs))
        raise AssertionError("living-community alert reached provider")

    store = _store([resident] if resident else [], [alert])
    monkeypatch.setattr(ai, "db", store)
    monkeypatch.setattr(ai, "_openai_chat", provider)

    _run(ai.classify_alert_background("alert-1"))

    assert provider_calls == []
    assert "ai_summary" not in store.alerts.rows[0]


@pytest.mark.parametrize("resident", [
    {"resident_id": "real-resident", "synthetic": False},
    {"resident_id": "legacy-demo", "synthetic": True,
     "simulation_scope": "demo_room"},
])
def test_alert_classifier_preserves_real_and_legacy_demo_provider_path(
    monkeypatch, resident,
):
    provider_calls = []
    alert = {
        "alert_id": "alert-1", "resident_id": resident["resident_id"],
        "severity": "assist",
        # Caller-controlled alert markers are deliberately ignored.
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }

    async def provider(*args, **kwargs):
        provider_calls.append((args, kwargs))
        return (
            '{"category":"comfort","summary":"Wanted company.",'
            '"resident_stated_reason":"Wanted company"}'
        )

    store = _store([resident], [alert])
    monkeypatch.setattr(ai, "db", store)
    monkeypatch.setattr(ai, "_openai_chat", provider)

    _run(ai.classify_alert_background("alert-1"))

    assert len(provider_calls) == 1
    assert store.alerts.rows[0]["ai_summary"] == "Wanted company."
    assert store.alerts.rows[0]["category"] == "comfort"


def test_resident_lookup_failure_stops_both_provider_paths(monkeypatch):
    class BrokenResidents:
        async def find_one(self, *_args, **_kwargs):
            raise RuntimeError("resident truth unavailable")

    provider_calls = []

    async def provider(*args, **kwargs):
        provider_calls.append((args, kwargs))
        return "[]"

    store = _store([], [{
        "alert_id": "alert-1", "resident_id": "unknown-resident",
        "severity": "assist",
    }])
    store.residents = BrokenResidents()
    monkeypatch.setattr(memory, "db", store)
    monkeypatch.setattr(memory, "OPENAI_API_KEY", "configured")
    monkeypatch.setattr(memory, "_openai_chat", provider)
    monkeypatch.setattr(ai, "db", store)
    monkeypatch.setattr(ai, "_openai_chat", provider)

    assert _run(memory.extract_and_store_memories(
        "unknown-resident", "session-1", "Hello", "Hello.",
    )) == 0
    _run(ai.classify_alert_background("alert-1"))
    assert provider_calls == []
