"""Generic recurring work must not target living-community residents."""
import asyncio
from copy import deepcopy
import os
import sys
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import StaffTaskTemplateCreate  # noqa: E402
from routes import task_recurrence, task_templates, tasks  # noqa: E402


ADMIN = {"user_id": "owner-1", "name": "Owner", "role": "owner"}


class _AsyncRows:
    def __init__(self, rows):
        self.rows = deepcopy(rows)

    def __aiter__(self):
        async def rows():
            for row in self.rows:
                yield deepcopy(row)

        return rows()


class _Residents:
    def __init__(self, rows=None, sequences=None):
        self.rows = deepcopy(rows or {})
        self.sequences = deepcopy(sequences or {})

    async def find_one(self, query, projection=None):
        rid = query.get("resident_id")
        if rid in self.sequences:
            sequence = self.sequences[rid]
            row = sequence.pop(0) if len(sequence) > 1 else sequence[0]
            return deepcopy(row)
        return deepcopy(self.rows.get(rid))


class _Departments:
    async def find_one(self, query, projection=None):
        return {"slug": query["slug"]}


class _Templates:
    def __init__(self, rows=None):
        self.rows = deepcopy(rows or [])
        self.inserted = []

    def find(self, query, projection=None):
        return _AsyncRows(self.rows)

    async def insert_one(self, doc):
        self.inserted.append(deepcopy(doc))
        return object()


class _StaffTasks:
    def __init__(self):
        self.inserted = []

    async def create_index(self, *args, **kwargs):
        return "occurrence_key"

    async def find_one(self, query, projection=None):
        return None

    async def insert_one(self, doc):
        self.inserted.append(deepcopy(doc))
        return object()


def _resident(rid, **markers):
    return {"resident_id": rid, "name": rid, "room": f"room-{rid}", **markers}


def _protected(rid="living"):
    return _resident(
        rid,
        synthetic=True,
        simulation_scope=task_recurrence.LIVING_COMMUNITY_SCOPE,
        simulation_community_id=task_recurrence.LIVING_COMMUNITY_ID,
    )


def _template(rid, suffix):
    return {
        "template_id": f"tpl-{suffix}",
        "title": f"Task {suffix}",
        "description": "",
        "category": "housekeeping",
        "shift": "any",
        "resident_id": rid,
        "room": f"room-{rid}",
        "recur": "daily",
        "department": "housekeeping",
        "active": True,
    }


def _template_input(rid):
    return StaffTaskTemplateCreate(
        title="Daily room clean",
        recur="daily",
        department="housekeeping",
        resident_id=rid,
    )


def _install_create(monkeypatch, residents_collection):
    templates_collection = _Templates()
    store = SimpleNamespace(
        residents=residents_collection,
        departments=_Departments(),
        task_templates=templates_collection,
    )
    monkeypatch.setattr(task_templates, "db", store)

    async def no_receipt(*args, **kwargs):
        return None

    monkeypatch.setattr(task_templates, "_receipt", no_receipt)
    return templates_collection


@pytest.mark.parametrize(
    "resident",
    [
        _protected(),
        _resident(
            "living",
            synthetic=True,
            simulation_scope=task_recurrence.LIVING_COMMUNITY_SCOPE,
        ),
        _resident(
            "living",
            synthetic=True,
            simulation_scope=task_recurrence.LIVING_COMMUNITY_SCOPE,
            simulation_community_id="sim:community:wrong",
        ),
    ],
)
def test_template_creation_refuses_exact_and_malformed_living_resident(monkeypatch, resident):
    templates_collection = _install_create(
        monkeypatch, _Residents(rows={resident["resident_id"]: resident})
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(task_templates.create_template(_template_input("living"), user=ADMIN))
    assert error.value.status_code == 409
    assert templates_collection.inserted == []


@pytest.mark.parametrize(
    "resident",
    [
        _resident("real"),
        _resident("demo", synthetic=True, simulation_scope="demo_room"),
        _resident(
            "not-synthetic",
            synthetic=False,
            simulation_scope=task_recurrence.LIVING_COMMUNITY_SCOPE,
            simulation_community_id=task_recurrence.LIVING_COMMUNITY_ID,
        ),
    ],
)
def test_non_managed_residents_preserve_template_creation(monkeypatch, resident):
    templates_collection = _install_create(
        monkeypatch, _Residents(rows={resident["resident_id"]: resident})
    )
    created = asyncio.run(
        task_templates.create_template(_template_input(resident["resident_id"]), user=ADMIN)
    )
    assert created["resident_id"] == resident["resident_id"]
    assert created["room"] == resident["room"]
    assert len(templates_collection.inserted) == 1


def test_template_creation_rechecks_resident_immediately_before_insert(monkeypatch):
    rid = "changes-during-create"
    templates_collection = _install_create(
        monkeypatch,
        _Residents(sequences={rid: [_resident(rid), _protected(rid)]}),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(task_templates.create_template(_template_input(rid), user=ADMIN))
    assert error.value.status_code == 409
    assert templates_collection.inserted == []


def _install_generation(monkeypatch, templates_rows, residents_collection):
    staff_tasks = _StaffTasks()
    store = SimpleNamespace(
        residents=residents_collection,
        task_templates=_Templates(templates_rows),
        staff_tasks=staff_tasks,
    )
    monkeypatch.setattr(task_recurrence, "db", store)

    async def no_index():
        return None

    async def no_denorms(payload):
        return payload

    async def no_receipt(*args, **kwargs):
        return None

    monkeypatch.setattr(task_recurrence, "_ensure_index", no_index)
    monkeypatch.setattr(task_recurrence, "record_origin", no_receipt)
    monkeypatch.setattr(tasks, "_resolve_denorms", no_denorms)
    return staff_tasks


def test_generation_skips_legacy_living_templates_and_preserves_real_demo(monkeypatch):
    rows = {
        "living": _protected(),
        "malformed": _resident(
            "malformed",
            synthetic=True,
            simulation_scope=task_recurrence.LIVING_COMMUNITY_SCOPE,
        ),
        "real": _resident("real"),
        "demo": _resident("demo", synthetic=True, simulation_scope="demo_room"),
    }
    staff_tasks = _install_generation(
        monkeypatch,
        [_template(rid, rid) for rid in rows],
        _Residents(rows=rows),
    )
    result = asyncio.run(task_recurrence.generate("2026-10-13"))
    assert result["living_community_templates_skipped"] == 2
    assert result["occurrences_created"] == 4
    assert {row["resident_id"] for row in staff_tasks.inserted} == {"real", "demo"}


def test_generation_rechecks_before_each_occurrence_insert(monkeypatch):
    rid = "changes-during-generation"
    staff_tasks = _install_generation(
        monkeypatch,
        [_template(rid, "race")],
        _Residents(sequences={rid: [_resident(rid), _protected(rid)]}),
    )
    result = asyncio.run(task_recurrence.generate("2026-10-13"))
    assert result["living_community_templates_skipped"] == 0
    assert result["living_community_occurrences_skipped"] == 2
    assert staff_tasks.inserted == []
