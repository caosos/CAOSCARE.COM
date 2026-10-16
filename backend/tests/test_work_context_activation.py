"""Focused proof for the HTTP/dependency Work-as activation seam."""
import os
import sys
import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import work_context as route  # noqa: E402
from routes import task_lifecycle  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.task_lifecycle import authority_for  # noqa: E402
from routes.tasks import staff_visibility_query  # noqa: E402
from simulation.work_context import issue  # noqa: E402


OWNER = {"user_id": "owner_1", "name": "Michael", "role": "owner", "department": None}
ACTIVE = [{"slug": "maintenance", "label": "Maintenance"},
          {"slug": "administration", "label": "Administration"}]


def request():
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [],
                    "client": ("127.0.0.1", 1234), "server": ("test", 80)})


def test_signed_header_scopes_authorization_but_receipt_keeps_real_principal(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "work-as-route-test-secret-at-least-32-bytes")
    monkeypatch.setattr(route, "_active", lambda: _async_value(ACTIVE))
    monkeypatch.setattr(route, "get_current_user", lambda _request: _async_value(OWNER))
    token, context = issue(OWNER, acting_role="staff", acting_department="maintenance",
                           known_departments={"maintenance", "administration"})

    effective = asyncio.run(route.get_department_user(request(), token))
    actor = actor_from_user(effective)
    authority = authority_for({"visibility_role": "maintenance"}, actor, effective)
    wrong_department = authority_for(
        {"visibility_role": "nursing", "assigned_to": "owner_1"}, actor, effective,
    )

    assert effective["user_id"] == "owner_1"
    assert effective["role"] == "staff" and effective["department"] == "maintenance"
    assert staff_visibility_query(effective) == {"visibility_role": {"$in": ["maintenance", "all_staff"]}}
    assert authority == "admin_work_as:owner:as:staff:maintenance:acts_for:maintenance"
    assert wrong_department is None
    assert actor.receipt_fields() == {
        "actor_id": "owner_1", "actor_type": "real-human", "actor_name": "Michael",
        "actor_role": "owner", "actor_department": None, "channel": "staff_ui",
        "identity_basis": "authenticated", "simulated": False,
        "acting_role": "staff", "acting_department": "maintenance",
        "work_context_id": context.context_id,
    }


def test_inactive_department_and_non_admin_principal_fail_closed(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "work-as-route-test-secret-at-least-32-bytes")
    monkeypatch.setattr(route, "get_current_user", lambda _request: _async_value(OWNER))
    token, _ = issue(OWNER, acting_role="staff", acting_department="maintenance",
                     known_departments={"maintenance"})
    monkeypatch.setattr(route, "_active", lambda: _async_value([ACTIVE[1]]))

    with pytest.raises(HTTPException) as error:
        asyncio.run(route.get_department_user(request(), token))
    assert error.value.status_code == 400
    assert error.value.detail["code"] == "unknown_department"

    with pytest.raises(HTTPException) as error:
        asyncio.run(route.create_context(
            route.WorkContextInput(acting_role="staff", acting_department="administration"),
            {**OWNER, "role": "staff"},
        ))
    assert error.value.status_code == 403
    assert error.value.detail["code"] == "principal_not_admin"


async def _async_value(value):
    return value


def test_task_origin_passes_dual_identity_into_receipt_builder(monkeypatch):
    captured = {}

    async def create_receipt(**kwargs):
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(task_lifecycle, "create_receipt", create_receipt)
    actor = actor_from_user({
        **OWNER,
        "role": "staff",
        "department": "maintenance",
        "_principal_role": "owner",
        "_principal_department": None,
        "_work_context_id": "wctx_receipt",
        "_work_context_acting_role": "staff",
        "_work_context_acting_department": "maintenance",
    })
    asyncio.run(task_lifecycle.record_origin(
        {"task_id": "task_1", "visibility_role": "maintenance", "status": "pending"},
        actor,
        action_type="task_created",
        authority="admin_work_as:owner:as:staff:maintenance:dept_member:maintenance",
    ))

    provenance = captured["provenance"]
    assert provenance["actor_id"] == "owner_1" and provenance["actor_role"] == "owner"
    assert provenance["acting_role"] == "staff"
    assert provenance["acting_department"] == "maintenance"
    assert provenance["work_context_id"] == "wctx_receipt"


def test_real_owner_completes_simulated_ticket_under_explicit_department_authority(monkeypatch):
    """The Work-as seam never turns the owner into a synthetic employee."""
    task = {
        "task_id": "task_sim_1", "visibility_role": "maintenance", "status": "in_progress",
        "assigned_to": "owner_1", "assigned_name": "Michael", "resident_id": "sim_resident_1",
        "simulation_run_id": "sim_run_1", "simulation_scope": "living_community",
        "simulation_community_id": "community_1", "simulated": True,
    }
    owner_as_maintenance = {
        **OWNER, "role": "staff", "department": "maintenance",
        "_principal_role": "owner", "_principal_department": None,
        "_work_context_id": "wctx_complete", "_work_context_acting_role": "staff",
        "_work_context_acting_department": "maintenance",
    }
    actor = actor_from_user(owner_as_maintenance)
    captured = {}
    after = {**task, "status": "completed", "completed_by": "owner_1", "completed_by_name": "Michael"}

    async def check(*_args, **_kwargs):
        authority = task_lifecycle.authority_for(task, actor, owner_as_maintenance)
        return task, authority, {"receipt_id": "rcpt_origin", "correlation_id": "rcpt_origin"}

    async def update(*_args, **_kwargs):
        return None

    async def load(_task_id):
        return after

    async def create_receipt(**kwargs):
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(task_lifecycle, "check", check)
    monkeypatch.setattr(task_lifecycle, "update_task_with_history", update)
    monkeypatch.setattr(task_lifecycle, "load", load)
    monkeypatch.setattr(task_lifecycle, "create_receipt", create_receipt)

    completed, _ = asyncio.run(task_actions.complete(
        task["task_id"], "Repaired during owner takeover", actor, owner_as_maintenance,
    ))

    assert completed["completed_by"] == OWNER["user_id"]
    assert captured["action_type"] == "task_completed"
    assert captured["provenance"]["authority"] == (
        "admin_work_as:owner:as:staff:maintenance:assignee"
    )
    assert captured["provenance"]["actor_id"] == OWNER["user_id"]
    assert captured["provenance"]["actor_type"] == "real-human"
    assert captured["provenance"]["identity_basis"] == "authenticated"
    assert captured["provenance"]["simulated"] is False
    assert captured["provenance"]["acting_department"] == "maintenance"
    assert captured["provenance"]["simulation_run_id"] == "sim_run_1"


def test_work_as_owner_cannot_act_on_another_departments_ticket():
    owner_as_maintenance = {
        **OWNER, "role": "staff", "department": "maintenance",
        "_principal_role": "owner", "_work_context_id": "wctx_scope",
        "_work_context_acting_role": "staff", "_work_context_acting_department": "maintenance",
    }
    actor = actor_from_user(owner_as_maintenance)
    assert task_lifecycle.authority_for(
        {"task_id": "task_nursing", "visibility_role": "nursing"}, actor, owner_as_maintenance,
    ) is None
