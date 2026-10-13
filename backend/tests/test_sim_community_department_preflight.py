"""Living-community run start requires an active canonical department set."""

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from simulation.community_department_preflight import (
    CONTRACT_VERSION,
    DepartmentPreflightError,
    department_requirements,
    preflight_living_community_run_start,
    validate_active_department_contract,
)


EXPECTED_SLUGS = (
    "activities",
    "administration",
    "front_desk",
    "housekeeping",
    "kitchen",
    "maintenance",
    "nursing",
    "transportation",
)


def active_catalog():
    return [
        {"slug": slug, "label": slug.replace("_", " ").title(), "active": True}
        for slug in EXPECTED_SLUGS
    ]


def test_requirements_are_derived_from_both_routines_and_staffing():
    requirements = department_requirements()
    assert tuple(item.slug for item in requirements) == EXPECTED_SLUGS
    sources = {item.slug: item.used_by for item in requirements}
    assert sources["front_desk"] == ("routines", "staffing")
    assert sources["nursing"] == ("routines", "staffing")
    assert sources["administration"] == ("routines", "staffing")


def test_valid_catalog_returns_deterministic_immutable_snapshot_and_digest():
    first = validate_active_department_contract(active_catalog())
    second = validate_active_department_contract(list(reversed(active_catalog())) + [
        {"slug": "unused_department", "active": False},
    ])

    assert first == second
    assert first.contract_version == CONTRACT_VERSION
    assert first.active_slugs == EXPECTED_SLUGS
    assert len(first.digest) == 64
    with pytest.raises(FrozenInstanceError):
        first.digest = "changed"
    with pytest.raises(FrozenInstanceError):
        first.departments[0].slug = "changed"


def test_missing_department_fails_with_exact_reason():
    catalog = [row for row in active_catalog() if row["slug"] != "front_desk"]
    with pytest.raises(DepartmentPreflightError) as error:
        validate_active_department_contract(catalog)

    assert error.value.missing_slugs == ("front_desk",)
    assert error.value.inactive_slugs == ()
    assert str(error.value) == (
        "living-community run start blocked: "
        "missing canonical departments: front_desk"
    )


def test_inactive_department_fails_with_exact_reason():
    catalog = active_catalog()
    next(row for row in catalog if row["slug"] == "nursing")["active"] = False
    with pytest.raises(DepartmentPreflightError) as error:
        validate_active_department_contract(catalog)

    assert error.value.missing_slugs == ()
    assert error.value.inactive_slugs == ("nursing",)
    assert str(error.value) == (
        "living-community run start blocked: "
        "inactive canonical departments: nursing"
    )


def test_missing_and_inactive_reasons_are_complete_and_stably_ordered():
    catalog = [
        row for row in active_catalog()
        if row["slug"] not in {"front_desk", "transportation"}
    ]
    next(row for row in catalog if row["slug"] == "nursing")["active"] = False
    next(row for row in catalog if row["slug"] == "activities").pop("active")

    with pytest.raises(DepartmentPreflightError) as error:
        validate_active_department_contract(reversed(catalog))

    assert error.value.missing_slugs == ("front_desk", "transportation")
    assert error.value.inactive_slugs == ("activities", "nursing")
    assert str(error.value) == (
        "living-community run start blocked: "
        "missing canonical departments: front_desk, transportation; "
        "inactive canonical departments: activities, nursing"
    )


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, limit):
        assert limit == 1000
        return list(self.rows)


class ReadOnlyDepartments:
    def __init__(self, rows):
        self.rows = rows
        self.reads = []

    def find(self, query, projection):
        self.reads.append((query, projection))
        return Cursor(self.rows)


class Store:
    def __init__(self, rows):
        self.departments = ReadOnlyDepartments(rows)


def test_injectable_preflight_reads_all_canonical_states_and_never_writes():
    async def run():
        store = Store(active_catalog())
        snapshot = await preflight_living_community_run_start(store=store)
        assert snapshot.active_slugs == EXPECTED_SLUGS
        assert store.departments.reads == [(
            {}, {"_id": 0, "slug": 1, "active": 1},
        )]

        async def reader():
            return active_catalog()

        assert await preflight_living_community_run_start(
            department_reader=reader
        ) == snapshot
        with pytest.raises(ValueError, match="either store or department_reader"):
            await preflight_living_community_run_start(
                store=store, department_reader=reader
            )

    asyncio.run(run())
