"""Canonical department defaults and established-facility backfills."""

import asyncio
from copy import deepcopy

from routes import departments
from routes.resident_requests import CATEGORY_ALIASES
from routes.staff_scope import acting_departments, members_query
from simulation.community_department_preflight import (
    validate_active_department_contract,
)


class FakeCollection:
    def __init__(self, rows=()):
        self.rows = [deepcopy(row) for row in rows]

    async def count_documents(self, query):
        assert query == {}
        return len(self.rows)

    async def find_one(self, query, projection=None):
        row = next(
            (row for row in self.rows if all(row.get(k) == v for k, v in query.items())),
            None,
        )
        if row is None:
            return None
        if projection == {"_id": 1}:
            return {"_id": row.get("_id", "fake")}
        return deepcopy(row)

    async def insert_one(self, document):
        self.rows.append(deepcopy(document))

    async def update_one(self, query, update):
        row = next(
            (row for row in self.rows if all(row.get(k) == v for k, v in query.items())),
            None,
        )
        if row is not None:
            row.update(deepcopy(update["$set"]))


class FakeDb:
    def __init__(self, rows=()):
        self.departments = FakeCollection(rows)


def run(coro):
    return asyncio.run(coro)


def test_default_catalog_includes_active_front_desk_and_passes_preflight():
    catalog = [
        {"slug": slug, "label": label, "active": True}
        for slug, label in departments.DEFAULT_DEPARTMENTS
    ]

    snapshot = validate_active_department_contract(catalog)

    assert "front_desk" in snapshot.active_slugs
    assert next(row for row in catalog if row["slug"] == "front_desk") == {
        "slug": "front_desk",
        "label": "Front Desk",
        "active": True,
    }


def test_front_desk_role_and_requests_still_act_for_administration():
    assert CATEGORY_ALIASES["front_desk"] == "administration"
    assert acting_departments({"role": "front_desk"}) == {"administration"}
    assert members_query("administration") == {
        "$or": [
            {"department": "administration"},
            {"role": "front_desk"},
        ]
    }


def test_empty_catalog_seeds_each_default_once(monkeypatch):
    fake_db = FakeDb()
    monkeypatch.setattr(departments, "db", fake_db)

    run(departments.seed_default_departments())
    run(departments.seed_default_departments())

    slugs = [row["slug"] for row in fake_db.departments.rows]
    assert slugs == [slug for slug, _ in departments.DEFAULT_DEPARTMENTS]
    assert len(slugs) == len(set(slugs))


def test_seed_backfills_front_desk_once_without_overwriting_existing_facility(monkeypatch):
    existing = [
        {
            "department_id": "dept-admin",
            "slug": "administration",
            "label": "Community Office",
            "active": False,
            "created_at": "existing",
        },
        {
            "department_id": "dept-activities",
            "slug": "activities",
            "label": "Life Enrichment",
            "active": False,
            "created_at": "existing",
        },
    ]
    fake_db = FakeDb(existing)
    monkeypatch.setattr(departments, "db", fake_db)

    run(departments.seed_default_departments())
    run(departments.seed_default_departments())

    rows = fake_db.departments.rows
    assert [row["slug"] for row in rows].count("front_desk") == 1
    front_desk = next(row for row in rows if row["slug"] == "front_desk")
    assert front_desk["label"] == "Front Desk" and front_desk["active"] is True
    assert next(row for row in rows if row["slug"] == "administration") == existing[0]
    assert next(row for row in rows if row["slug"] == "activities") == existing[1]


def test_seed_preserves_existing_inactive_front_desk(monkeypatch):
    existing = {
        "department_id": "dept-front",
        "slug": "front_desk",
        "label": "Reception",
        "active": False,
        "created_at": "existing",
    }
    fake_db = FakeDb([existing])
    monkeypatch.setattr(departments, "db", fake_db)

    run(departments.seed_default_departments())

    front_rows = [row for row in fake_db.departments.rows if row["slug"] == "front_desk"]
    assert front_rows == [existing]
