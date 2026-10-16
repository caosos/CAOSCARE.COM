"""HTTP reset requires exact confirmation and every existing safety gate."""

import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import deps
from routes import community_reset_controls
from simulation.community_index_contract import REQUIRED_INDEXES
from tests.community_runtime_fake import RuntimeStore


OWNER = {"user_id": "owner-1", "name": "Michael", "role": "owner"}
RUN_ID = "simrun:living:reset-api"
BODY = {
    "run_id": RUN_ID,
    "expected_state": "STOPPED",
    "confirmation": f"RESET {RUN_ID}",
    "operation_key": f"staff-ui:reset:{RUN_ID}",
}


def _install_required_indexes(store):
    grouped = {}
    for requirement in REQUIRED_INDEXES:
        grouped.setdefault(requirement["collection"], {})[requirement["name"]] = {
            "key": list(requirement["keys"]),
            **({"unique": True} if requirement["unique"] is True else {}),
            **({"partialFilterExpression": requirement["partial"]}
               if requirement.get("partial") else {}),
        }
    for collection_name, information in grouped.items():
        async def index_information(rows=deepcopy(information)):
            return deepcopy(rows)
        getattr(store, collection_name).index_information = index_information


def _app(monkeypatch, store, role="owner"):
    async def current_user(_request):
        if role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {**OWNER, "role": role}

    monkeypatch.setattr(deps, "get_current_user", current_user)
    monkeypatch.setattr(community_reset_controls, "db", store)
    app = FastAPI()
    app.include_router(community_reset_controls.router, prefix="/api")
    return app


async def _request(app, body=BODY):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        return await client.post(
            "/api/simulator/community/controls/reset", json=deepcopy(body),
        )


def test_default_gate_failure_never_calls_reset_service_or_writes(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", raising=False)
    store = RuntimeStore()
    _install_required_indexes(store)
    called = []

    async def resetter(*args, **kwargs):
        called.append((args, kwargs))

    monkeypatch.setattr(community_reset_controls, "reset_living_community", resetter)
    response = asyncio.run(_request(_app(monkeypatch, store)))
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "community_controls_unavailable"
    assert called == []
    assert store.sim_runs.docs == [] and store.receipts.docs == []


@pytest.mark.parametrize(
    "changes,status",
    (({"confirmation": "RESET the wrong run"}, 409),
     ({"expected_state": "PAUSED"}, 422)),
)
def test_wrong_confirmation_or_state_is_rejected_before_reset(monkeypatch, changes, status):
    called = []

    async def resetter(*args, **kwargs):
        called.append((args, kwargs))

    monkeypatch.setattr(community_reset_controls, "reset_living_community", resetter)
    response = asyncio.run(_request(
        _app(monkeypatch, RuntimeStore()), {**BODY, **changes},
    ))
    assert response.status_code == status
    assert called == []


def test_active_local_loop_is_rejected_before_reset_service(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)
    called = []
    monkeypatch.setattr(community_reset_controls, "is_active", lambda _run_id: True)
    monkeypatch.setattr(
        community_reset_controls, "reset_living_community",
        lambda *args, **kwargs: called.append((args, kwargs)),
    )
    response = asyncio.run(_request(_app(monkeypatch, store)))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "community_reset_loop_active"
    assert called == []


def test_success_and_retry_use_same_actor_bound_operation_key(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)
    calls = []

    async def resetter(actor, authority, operation_key, expected_run_id, *, store):
        calls.append((actor, authority, operation_key, expected_run_id, store))
        return {
            "reset_id": "simreset:one",
            "reset_generation": 1,
            "idempotent_replay": len(calls) > 1,
            "receipt_id": "receipt:reset",
            "deleted": {},
            "commit_reconciled": False,
        }

    monkeypatch.setattr(community_reset_controls, "reset_living_community", resetter)
    monkeypatch.setattr(community_reset_controls, "is_active", lambda _run_id: False)
    app = _app(monkeypatch, store)
    first = asyncio.run(_request(app))
    second = asyncio.run(_request(app))
    assert first.status_code == second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    assert len(calls) == 2 and calls[0][2] == calls[1][2]
    assert calls[0][2] == community_reset_controls._operation_key(
        OWNER, RUN_ID, BODY["operation_key"],
    )
    actor, authority, _, expected_run_id, selected = calls[0]
    assert actor.actor_id == "owner-1" and actor.actor_type == "real-human"
    assert authority == "admin_override:owner"
    assert expected_run_id == RUN_ID and selected is store


@pytest.mark.parametrize("role,status", ((None, 401), ("staff", 403)))
def test_reset_requires_real_admin_tier(monkeypatch, role, status):
    response = asyncio.run(_request(_app(monkeypatch, RuntimeStore(), role=role)))
    assert response.status_code == status


def test_registered_server_exposes_reset_path():
    from server import app

    assert "/api/simulator/community/controls/reset" in {
        route.path for route in app.routes
    }
