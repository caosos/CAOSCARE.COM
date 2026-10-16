"""Authorization and stable payload tests for the runtime route."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import deps
from routes import community_runtime


FIXTURE = {
    "schema_version": 1, "status": "loaded", "read_only": True,
    "run": {"status": "loaded", "state": "RUNNING", "run_id": "living-run-1",
            "simulated_time": {"absolute_minute": 480},
            "next_event": {"day_index": 0, "minute": 470}},
    "tickets": {"status": "loaded", "counts": {"open": 0}},
    "staffing": {"status": "loaded", "workers": []},
}

ACTIVITY = {
    "schema_version": 1, "status": "loaded", "read_only": True,
    "run_id": "living-run-1", "tasks": {"status": "loaded", "items": []},
    "transitions": {"status": "loaded", "items": []},
}


QUEUE = {"schema_version": 1, "status": "loaded", "read_only": True, "run_id": "living-run-1"}


def request(monkeypatch, role):
    async def current_user(_request):
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {"user_id": f"test-{role}", "name": "Test", "role": role}

    async def snapshot():
        return dict(FIXTURE)

    async def activity_snapshot(*, run_id):
        assert run_id == "living-run-1"
        return ACTIVITY

    async def queue_snapshot(*, run_id, clock_minute, next_event_minute):
        assert (run_id, clock_minute, next_event_minute) == ("living-run-1", 480, 470)
        return QUEUE

    monkeypatch.setattr(deps, "get_current_user", current_user)
    monkeypatch.setattr(community_runtime.community_queue_view, "queue_snapshot", queue_snapshot)
    monkeypatch.setattr(community_runtime.community_runtime_view, "runtime_snapshot", snapshot)
    monkeypatch.setattr(community_runtime.community_activity_view, "activity_snapshot", activity_snapshot)
    app = FastAPI()
    app.include_router(community_runtime.router, prefix="/api")

    async def call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        ) as client:
            return await client.get("/api/simulator/community/runtime")

    return asyncio.run(call())


@pytest.mark.parametrize("role,status", ((None, 401), ("staff", 403)))
def test_runtime_rejects_non_admins(monkeypatch, role, status):
    assert request(monkeypatch, role).status_code == status


@pytest.mark.parametrize("role", ("owner", "admin"))
def test_runtime_allows_admin_tiers(monkeypatch, role):
    response = request(monkeypatch, role)
    assert response.status_code == 200
    assert response.json() == {**FIXTURE, "activity": ACTIVITY, "queue": QUEUE}
