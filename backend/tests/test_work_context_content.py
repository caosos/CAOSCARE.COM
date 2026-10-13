"""Work-as proof for Kitchen menu and Activities schedule content lanes."""
import asyncio
import inspect
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import content_coverage, content_receipts, menu, menu_ingest, schedule, schedule_ingest  # noqa: E402
from routes.content_receipts import record_content_change, staff_actor  # noqa: E402
from routes.service_content_access import (  # noqa: E402
    MENU_DEPARTMENTS,
    SCHEDULE_DEPARTMENTS,
    require_content_editor,
)
from routes.work_context import get_department_user  # noqa: E402


def _effective(department: str) -> dict:
    return {
        "user_id": "owner_1",
        "name": "Michael",
        "role": "staff",
        "department": department,
        "_principal_role": "owner",
        "_principal_department": None,
        "_work_context_id": f"wctx_{department}",
        "_work_context_acting_role": "staff",
        "_work_context_acting_department": department,
    }


class _EmptyCursor:
    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, _limit):
        return []


class _Receipts:
    def find(self, *_args, **_kwargs):
        return _EmptyCursor()


class _Db:
    receipts = _Receipts()


def _dependency(function) -> object:
    return inspect.signature(function).parameters["user"].default.dependency


def test_every_content_workspace_route_revalidates_signed_work_context():
    routes = (
        menu.list_menu,
        menu.create_menu_item,
        menu.update_menu_item,
        menu.approve_menu_item,
        menu.delete_menu_item,
        menu_ingest.ingest_dev_test,
        menu_ingest.ingest_paste,
        menu_ingest.list_uploads,
        menu_ingest.approve_upload,
        content_coverage.menu_coverage,
        schedule.list_schedule,
        schedule.list_drafts,
        schedule.create_schedule_item,
        schedule.update_schedule_item,
        schedule.publish_schedule_item,
        schedule.publish_batch,
        schedule.delete_schedule_item,
        schedule_ingest.ingest_dev_test,
        schedule_ingest.ingest_paste,
        content_coverage.schedule_coverage,
    )
    assert all(_dependency(route) is get_department_user for route in routes)


@pytest.mark.parametrize(
    ("department", "kind", "allowed"),
    (("kitchen", "menu", MENU_DEPARTMENTS), ("activities", "schedule", SCHEDULE_DEPARTMENTS)),
)
def test_work_as_content_receipt_keeps_principal_and_names_scoped_authority(
    monkeypatch, department, kind, allowed,
):
    captured = {}

    async def create_receipt(**kwargs):
        captured.update(kwargs)
        return kwargs

    user = _effective(department)
    require_content_editor(user, allowed)
    monkeypatch.setattr(content_receipts, "db", _Db())
    monkeypatch.setattr(content_receipts, "create_receipt", create_receipt)

    asyncio.run(record_content_change(
        kind=kind,
        action="created",
        object_type=f"{kind}_item",
        object_id=f"{kind}_1",
        actor=staff_actor(user),
        after={"status": "draft"},
    ))

    provenance = captured["provenance"]
    assert provenance["actor_id"] == "owner_1"
    assert provenance["actor_role"] == "owner"
    assert provenance["actor_type"] == "real-human"
    assert provenance["simulated"] is False
    assert provenance["acting_role"] == "staff"
    assert provenance["acting_department"] == department
    assert provenance["work_context_id"] == f"wctx_{department}"
    assert provenance["authority"] == (
        f"admin_work_as:owner:as:staff:{department}:acts_for:{department}"
    )


def test_content_scope_does_not_grant_another_departments_authority():
    with pytest.raises(HTTPException) as menu_error:
        require_content_editor(_effective("activities"), MENU_DEPARTMENTS)
    assert menu_error.value.status_code == 403

    with pytest.raises(HTTPException) as schedule_error:
        require_content_editor(_effective("kitchen"), SCHEDULE_DEPARTMENTS)
    assert schedule_error.value.status_code == 403
