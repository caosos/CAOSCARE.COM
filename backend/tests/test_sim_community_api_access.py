"""Read-only authorization matrix for the community planning endpoints."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import deps
from routes import simulation


def _get(monkeypatch, path: str, role: str | None):
    async def current_user(_request):
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {
            "user_id": f"test-{role}",
            "name": f"Test {role}",
            "role": role,
            "department": "maintenance" if role == "staff" else None,
        }

    monkeypatch.setattr(deps, "get_current_user", current_user)
    app = FastAPI()
    app.include_router(simulation.router, prefix="/api")

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(f"/api{path}")

    return asyncio.run(request())


@pytest.mark.parametrize(
    "path", ("/simulator/community/overview", "/simulator/community/preview")
)
@pytest.mark.parametrize("role,status", ((None, 401), ("staff", 403)))
def test_community_planning_endpoints_reject_non_admins(monkeypatch, path, role, status):
    response = _get(monkeypatch, path, role)

    assert response.status_code == status


@pytest.mark.parametrize(
    "path", ("/simulator/community/overview", "/simulator/community/preview")
)
@pytest.mark.parametrize("role", ("owner", "admin"))
def test_community_planning_endpoints_allow_admin_tiers(monkeypatch, path, role):
    response = _get(monkeypatch, path, role)

    assert response.status_code == 200
    body = response.json()
    if path.endswith("overview"):
        assert body["execution_status"] == "planning_only"
    else:
        assert body["overview"]["execution_status"] == "planning_only"
