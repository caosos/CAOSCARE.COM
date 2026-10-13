"""Guarded HTTP contract for the manual P1A provisioning control."""
from copy import deepcopy
import asyncio
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import require_admin  # noqa: E402
from routes import simulation_burnin_control as control  # noqa: E402


ADMIN = {"user_id": "owner-1", "name": "Michael", "role": "owner", "department": None}
PLAN = {
    "community_id": "sim:community:living-80-v1",
    "resident_count": 10,
    "created_ids": ["sim:resident:001"],
    "reused_ids": ["sim:resident:002"],
    "new_receipt_targets": ["sim:resident:001"],
    "writes_planned": 2,
}


def app_with(dependency):
    app = FastAPI()
    app.include_router(control.router)
    app.dependency_overrides[require_admin] = dependency
    return TestClient(app)


async def owner():
    return dict(ADMIN)


class _Runs:
    def __init__(self, row):
        self.row = row

    async def find_one(self, query, projection=None):
        return deepcopy(self.row) if self.row and self.row.get("run_id") == query.get("run_id") else None


class _Store:
    def __init__(self, row):
        self.sim_runs = _Runs(row)


@pytest.mark.parametrize("status", [401, 403])
def test_anonymous_and_staff_are_refused_by_admin_dependency(status):
    async def refused():
        raise HTTPException(status_code=status, detail="Admin access required")

    response = app_with(refused).post(
        "/simulator/community/burn-in/provision", json={"run_id": "simrun-1"}
    )
    assert response.status_code == status


def test_default_is_safe_preflight_and_performs_no_execution(monkeypatch):
    calls = []

    async def paused(run_id, store=None):
        return {"run_id": run_id, "state": control.PAUSED,
                "simulation_scope": control.SIMULATION_SCOPE,
                "simulation_community_id": control.COMMUNITY_ID}

    async def preflight(operator, authority, store=None):
        calls.append((operator.actor_id, authority))
        return deepcopy(PLAN)

    monkeypatch.setenv("JWT_SECRET", "p1a-test-secret-that-is-32-bytes-long")
    monkeypatch.delenv(control.EXECUTION_FLAG, raising=False)
    monkeypatch.setattr(control, "_paused_run", paused)
    monkeypatch.setattr(control, "_preflight", preflight)
    response = app_with(owner).post(
        "/simulator/community/burn-in/provision", json={"run_id": "simrun-1"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True and body["executed"] is False
    assert body["autonomous_execution"] is False and body["provider_calls"] is False
    assert body["execution_enabled"] is False
    assert body["run_state"] == "PAUSED" and body["plan"] == PLAN
    assert body["confirmation_token"] and body["confirmation_expires_at"]
    assert "No residents or receipts were written" in body["message"]
    assert calls == [(ADMIN["user_id"], "admin_override:owner")]


def test_running_run_and_unconfirmed_execute_are_refused(monkeypatch):
    async def running(run_id, store=None):
        raise HTTPException(status_code=409, detail="requires a PAUSED run")

    monkeypatch.setattr(control, "_paused_run", running)
    response = app_with(owner).post(
        "/simulator/community/burn-in/provision", json={"run_id": "simrun-1"}
    )
    assert response.status_code == 409

    async def paused(run_id, store=None):
        return {"run_id": run_id, "state": control.PAUSED,
                "simulation_scope": control.SIMULATION_SCOPE,
                "simulation_community_id": control.COMMUNITY_ID}

    async def preflight(operator, authority, store=None):
        return deepcopy(PLAN)

    monkeypatch.setattr(control, "_paused_run", paused)
    monkeypatch.setattr(control, "_preflight", preflight)
    response = app_with(owner).post(
        "/simulator/community/burn-in/provision",
        json={"run_id": "simrun-1", "execute": True},
    )
    assert response.status_code == 409
    assert "confirmation token" in response.json()["detail"]


def test_paused_run_must_be_bound_to_exact_living_community():
    base = {"run_id": "simrun-1", "state": control.PAUSED,
            "simulation_scope": control.SIMULATION_SCOPE,
            "simulation_community_id": control.COMMUNITY_ID}
    assert asyncio.run(control._paused_run("simrun-1", _Store(base))) == base
    for changed in (
        {**base, "simulation_scope": "demo_room"},
        {**base, "simulation_community_id": "other"},
        {"run_id": "simrun-1", "state": control.PAUSED},
    ):
        with pytest.raises(HTTPException, match="living-community"):
            asyncio.run(control._paused_run("simrun-1", _Store(changed)))


def test_confirmation_is_bound_to_operator_run_and_exact_plan(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "p1a-test-secret-that-is-32-bytes-long")
    token, _expires = control._issue_confirmation(ADMIN, "simrun-1", control._digest(PLAN))
    control._verify_confirmation(token, ADMIN, "simrun-1", control._digest(PLAN))
    with pytest.raises(HTTPException) as error:
        control._verify_confirmation(token, ADMIN, "simrun-2", control._digest(PLAN))
    assert error.value.status_code == 409
    changed = {**PLAN, "created_ids": ["sim:resident:009"]}
    with pytest.raises(HTTPException) as error:
        control._verify_confirmation(token, ADMIN, "simrun-1", control._digest(changed))
    assert error.value.status_code == 409


def test_confirmed_execution_still_requires_disabled_by_default_server_gate(monkeypatch):
    async def paused(run_id, store=None):
        return {"run_id": run_id, "state": control.PAUSED,
                "simulation_scope": control.SIMULATION_SCOPE,
                "simulation_community_id": control.COMMUNITY_ID}

    async def preflight(operator, authority, store=None):
        return deepcopy(PLAN)

    monkeypatch.setenv("JWT_SECRET", "p1a-test-secret-that-is-32-bytes-long")
    monkeypatch.delenv(control.EXECUTION_FLAG, raising=False)
    monkeypatch.setattr(control, "_paused_run", paused)
    monkeypatch.setattr(control, "_preflight", preflight)
    token, _expires = control._issue_confirmation(ADMIN, "simrun-1", control._digest(PLAN))
    response = app_with(owner).post(
        "/simulator/community/burn-in/provision",
        json={"run_id": "simrun-1", "execute": True, "confirmation_token": token},
    )
    assert response.status_code == 409
    assert control.EXECUTION_FLAG in response.json()["detail"]
