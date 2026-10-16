"""SIM-007A dashboard routes: owner/admin only, read-only, 404 for unknown items."""
import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import deps
from routes import community_dashboard
from simulation.community_dashboard_detail import DashboardNotFound


def call(monkeypatch, role, path):
    async def current_user(_request):
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {"user_id": f"test-{role}", "name": "Test", "role": role}

    async def summary():
        return {"status": "loaded"}

    async def missing(key):
        raise DashboardNotFound(f"unknown {key}")

    async def found(key):
        return {"status": "loaded", "key": key}

    monkeypatch.setattr(deps, "get_current_user", current_user)
    monkeypatch.setattr(community_dashboard, "dashboard_snapshot", summary)
    monkeypatch.setattr(community_dashboard, "department_detail", found)
    monkeypatch.setattr(community_dashboard, "worker_detail", missing)
    monkeypatch.setattr(community_dashboard, "resident_detail", found)
    monkeypatch.setattr(community_dashboard, "ticket_detail", found)
    app = FastAPI()
    app.include_router(community_dashboard.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(f"/api/simulator/community/dashboard{path}")
    return asyncio.run(go())


@pytest.mark.parametrize("role,status", ((None, 401), ("staff", 403)))
def test_non_admins_are_refused(monkeypatch, role, status):
    assert call(monkeypatch, role, "").status_code == status


@pytest.mark.parametrize("role", ("owner", "admin"))
def test_admin_tiers_read_every_view(monkeypatch, role):
    assert call(monkeypatch, role, "").json() == {"status": "loaded"}
    for path in ("/departments/nursing", "/residents/sim:resident:001", "/tickets/task_1"):
        assert call(monkeypatch, role, path).status_code == 200


def test_unknown_item_is_404(monkeypatch):
    response = call(monkeypatch, "owner", "/workers/sim:staff:ghost")
    assert response.status_code == 404 and "unknown" in response.json()["detail"]
