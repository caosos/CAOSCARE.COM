"""Fail-closed HTTP and transaction-capability proofs."""

import asyncio
from copy import deepcopy

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import deps
from routes import community_controls
from simulation.community_control_capability import control_capability
from simulation.community_index_contract import REQUIRED_INDEXES
from tests.community_runtime_fake import RuntimeStore


OWNER = {"user_id": "owner-1", "name": "Michael", "role": "owner"}
POSITION = {
    "run_id": "simrun:living:api-test",
    "expected_state": "PAUSED",
    "expected_cursor": 7,
    "expected_sim_minute": 480,
    "operation_key": "browser-operation-1",
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
    monkeypatch.setattr(community_controls, "db", store)
    community_controls._service = None
    app = FastAPI()
    app.include_router(community_controls.router, prefix="/api")
    return app


async def _request(app, method, path, json=None):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        return await client.request(method, path, json=json)


def test_capability_executes_and_aborts_a_real_read_only_transaction(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)
    result = asyncio.run(control_capability(store))
    assert result["mutations_allowed"] is True
    assert "provision_residents" in result["available_actions"]
    assert "step" in result["available_actions"]
    assert result["step"] == {"enabled": True, "reason": None}
    assert result["transaction_probe"] == {
        "status": "passed", "supported": True, "blocker": None,
    }
    assert store.session.in_transaction is False
    assert store.sim_runs.docs == [] and store.receipts.docs == []


def test_default_disabled_get_explains_blocker_and_post_writes_nothing(monkeypatch):
    monkeypatch.delenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", raising=False)
    store = RuntimeStore()
    _install_required_indexes(store)
    app = _app(monkeypatch, store)
    capability = asyncio.run(_request(
        app, "GET", "/api/simulator/community/controls/capability",
    ))
    assert capability.status_code == 200
    assert capability.json()["mutations_allowed"] is False
    assert capability.json()["step"]["enabled"] is False
    assert capability.json()["transaction_probe"]["status"] == "passed"
    assert capability.json()["blockers"][0]["code"] == "controls_not_enabled"

    response = asyncio.run(_request(
        app, "POST", "/api/simulator/community/controls/create-paused",
        {"expected_state": "ABSENT", "expected_cursor": 0,
         "expected_sim_minute": 0, "operation_key": "create-1"},
    ))
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "community_controls_unavailable"
    provision = asyncio.run(_request(
        app, "POST", "/api/simulator/community/controls/provision-residents", POSITION,
    ))
    assert provision.status_code == 503
    assert store.sim_runs.docs == [] and store.receipts.docs == []
    assert community_controls._service is None


@pytest.mark.parametrize("role,status", ((None, 401), ("staff", 403)))
def test_controls_require_real_admin_tier(monkeypatch, role, status):
    app = _app(monkeypatch, RuntimeStore(), role=role)
    response = asyncio.run(_request(
        app, "GET", "/api/simulator/community/controls/capability",
    ))
    assert response.status_code == status


class RecordingControls:
    def __init__(self):
        self.calls = []

    async def create_paused(self, actor, authority, key):
        self.calls.append(("create", actor, authority, key))
        return {"run": {"state": "PAUSED", "cursor": 0, "sim_minute": 0}}

    async def provision_residents(self, actor, authority, run_id, cursor, minute, key):
        self.calls.append(("provision", actor, authority, run_id, cursor, minute, key))
        return {"run": {"state": "PAUSED", "cursor": cursor, "sim_minute": minute,
                        "residents_provisioned": True}}

    async def resume_and_start(self, actor, authority, run_id, cursor, minute, key, holder):
        self.calls.append(("resume", actor, authority, run_id, cursor, minute, key, holder))
        return {"run": {"state": "RUNNING", "cursor": cursor, "sim_minute": minute}}

    async def pause(self, actor, authority, run_id, cursor, minute, key):
        self.calls.append(("pause", actor, authority, run_id, cursor, minute, key))
        return {"run": {"state": "PAUSED", "cursor": cursor, "sim_minute": minute}}

    async def stop(self, actor, authority, run_id, state, cursor, minute, key):
        self.calls.append(("stop", actor, authority, run_id, state, cursor, minute, key))
        return {"run": {"state": "STOPPED", "cursor": cursor, "sim_minute": minute}}

    async def step_one(self, actor, authority, run_id, cursor, minute, key, holder):
        self.calls.append(("step", actor, authority, run_id, cursor, minute, key, holder))
        return {"run": {"state": "PAUSED", "cursor": cursor + 1, "sim_minute": minute}}


def test_enabled_actions_forward_exact_coordinates_key_and_authenticated_actor(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)
    app = _app(monkeypatch, store)
    controls = RecordingControls()
    community_controls._service = controls
    requests = [
        ("create-paused", {"expected_state": "ABSENT", "expected_cursor": 0,
                           "expected_sim_minute": 0, "operation_key": "create-1"}),
        ("provision-residents", POSITION),
        ("resume", POSITION),
        ("pause", {**POSITION, "expected_state": "RUNNING", "operation_key": "pause-1"}),
        ("step", POSITION),
        ("stop", {**POSITION, "operation_key": "stop-1"}),
    ]
    for action, body in requests:
        response = asyncio.run(_request(
            app, "POST", f"/api/simulator/community/controls/{action}", deepcopy(body),
        ))
        assert response.status_code == 200, response.text
    assert [call[0] for call in controls.calls] == [
        "create", "provision", "resume", "pause", "step", "stop",
    ]
    for call in controls.calls:
        actor, authority = call[1:3]
        assert actor.actor_id == "owner-1"
        assert actor.actor_type == "real-human"
        assert actor.identity_basis == "authenticated"
        assert authority == "admin_override:owner"
    assert controls.calls[1][3:7] == (
        POSITION["run_id"], 7, 480,
        community_controls._operation_key(
            OWNER, "provision_residents", "browser-operation-1",
        ),
    )
    assert controls.calls[1][6] != community_controls._operation_key(
        {**OWNER, "user_id": "owner-2"},
        "provision_residents", "browser-operation-1",
    )
    assert controls.calls[2][4:7] == (
        7, 480, community_controls._operation_key(OWNER, "resume", "browser-operation-1"),
    )


def test_stale_or_invalid_state_is_rejected_before_service_call(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)
    app = _app(monkeypatch, store)
    controls = RecordingControls()
    community_controls._service = controls
    invalid = asyncio.run(_request(
        app, "POST", "/api/simulator/community/controls/pause", POSITION,
    ))
    assert invalid.status_code == 409
    missing = asyncio.run(_request(
        app, "POST", "/api/simulator/community/controls/resume",
        {key: value for key, value in POSITION.items() if key != "expected_cursor"},
    ))
    assert missing.status_code == 422
    wrong_provision_state = asyncio.run(_request(
        app, "POST", "/api/simulator/community/controls/provision-residents",
        {**POSITION, "expected_state": "RUNNING"},
    ))
    assert wrong_provision_state.status_code == 422
    assert controls.calls == []


def test_step_is_enabled_and_forwards_authenticated_owner(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)
    app = _app(monkeypatch, store)
    controls = RecordingControls()
    community_controls._service = controls
    response = asyncio.run(_request(
        app, "POST", "/api/simulator/community/controls/step", POSITION,
    ))
    assert response.status_code == 200
    assert response.json()["action"] == "step"
    call = controls.calls[0]
    assert call[0] == "step"
    assert call[1].actor_id == "owner-1" and call[2] == "admin_override:owner"
    assert call[3:6] == (POSITION["run_id"], 7, 480)
    assert call[6] == community_controls._operation_key(
        OWNER, "step", "browser-operation-1",
    )
    assert call[7].startswith("community-process:")


def test_enabled_transactional_store_without_named_indexes_never_reaches_service(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    app = _app(monkeypatch, store)
    controls = RecordingControls()
    community_controls._service = controls
    attempts = (
        ("create-paused", {"expected_state": "ABSENT", "expected_cursor": 0,
                           "expected_sim_minute": 0, "operation_key": "missing-indexes"}),
        ("provision-residents", POSITION),
        ("resume", POSITION),
        ("pause", {**POSITION, "expected_state": "RUNNING"}),
        ("stop", POSITION),
    )
    for action, body in attempts:
        response = asyncio.run(_request(
            app, "POST", f"/api/simulator/community/controls/{action}", body,
        ))
        assert response.status_code == 503
        blockers = response.json()["detail"]["blockers"]
        assert blockers[0]["code"] == "required_indexes_unavailable"
        assert "living_receipts_run_cursor" in blockers[0]["message"]
    assert controls.calls == []
    assert store.sim_runs.docs == [] and store.receipts.docs == []


def test_session_api_without_successful_transactional_read_stays_blocked(monkeypatch):
    monkeypatch.setenv("CAOSCARE_LIVING_COMMUNITY_CONTROLS", "true")
    store = RuntimeStore()
    _install_required_indexes(store)

    async def rejected_read(*args, **kwargs):
        raise RuntimeError("transactions unsupported by server topology")

    store.sim_runs.find_one = rejected_read
    result = asyncio.run(control_capability(store))
    assert result["controls_enabled"] is True
    assert result["transaction_probe"]["status"] == "failed"
    assert result["transaction_probe"]["blocker"] == "RuntimeError"
    assert result["mutations_allowed"] is False
    assert store.session.in_transaction is False


def test_registered_server_exposes_the_guarded_paths():
    from server import app

    paths = {route.path for route in app.routes}
    assert "/api/simulator/community/controls/capability" in paths
    assert "/api/simulator/community/controls/create-paused" in paths
    assert "/api/simulator/community/controls/provision-residents" in paths
    assert "/api/simulator/community/controls/resume" in paths
    assert "/api/simulator/community/controls/pause" in paths
    assert "/api/simulator/community/controls/stop" in paths


def test_route_uses_the_process_registry_service(monkeypatch):
    expected = RecordingControls()
    runtime = type("Runtime", (), {"controls": expected})()
    monkeypatch.setattr(
        community_controls, "community_process_runtime",
        lambda store: runtime,
    )
    community_controls._service = None

    assert community_controls._controls() is expected
