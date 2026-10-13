"""Observed community endpoint preserves read uncertainty and authorization."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import deps
from routes import simulation


def request(monkeypatch, role, result=None):
    async def current_user(_request):
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {"user_id": f"test-{role}", "name": "Test", "role": role}

    async def observed():
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(deps, "get_current_user", current_user)
    monkeypatch.setattr(simulation.community_observed_state, "observe_community_state", observed)
    app = FastAPI()
    app.include_router(simulation.router, prefix="/api")

    async def call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            return await client.get("/api/simulator/community/observed")

    return asyncio.run(call())


LOADED = {
    "status": "loaded",
    "community_id": "sim:community:living-80-v1",
    "counts": {"residents": 0, "tasks": 0, "notifications": 0, "runs": 0},
    "provisioning": {
        "state": "not_provisioned", "expected_residents": 10, "observed_residents": 0,
        "exact_blueprint_residents": 0, "missing_count": 10, "collision_count": 0,
    },
}


@pytest.mark.parametrize("role,status", ((None, 401), ("staff", 403)))
def test_observed_rejects_non_admins_without_read(monkeypatch, role, status):
    response = request(monkeypatch, role, AssertionError("must not read"))
    assert response.status_code == status


@pytest.mark.parametrize("role", ("owner", "admin"))
def test_observed_allows_admin_tiers_and_preserves_verified_zero(monkeypatch, role):
    response = request(monkeypatch, role, LOADED)
    assert response.status_code == 200
    assert response.json()["counts"]["residents"] == 0
    assert response.json()["provisioning"]["state"] == "not_provisioned"
    assert response.json()["observed_at"]


@pytest.mark.parametrize("state", ("unknown", "error"))
def test_observed_read_uncertainty_returns_503_without_counts(monkeypatch, state):
    response = request(monkeypatch, "owner", {"status": state, "counts": {"residents": None}})
    assert response.status_code == 503
    assert response.json() == {"detail": "Observed community state could not be verified"}
