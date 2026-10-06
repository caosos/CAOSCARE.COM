"""Agent Control Plane, first vertical slice (docs/CAOSCARE_AGENT_CONTROL_PLANE.md §12):

  one registered test agent (mock) → one command → command receipt
  → delivery receipt → response/status receipt

In-process: the router is mounted on a test FastAPI app (it is not mounted in
server.py yet). Scratch database only; refuses the live `caoscare` DB.

    cd backend && MONGO_URL=mongodb://localhost:27017 DB_NAME=caoscare_agent_control_test \
      JWT_SECRET=x pytest tests/test_agent_control.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes agent-control records; point DB_NAME at a scratch database",
                allow_module_level=True)

from fastapi import FastAPI  # noqa: E402
from deps import db  # noqa: E402
from routes import agent_control as routes  # noqa: E402
from agent_control import registry  # noqa: E402

TAG = f"acp_{uuid.uuid4().hex[:8]}"
USERS = {r: {"user_id": f"{TAG}_{r}", "name": f"{TAG} {r}", "role": r, "email": f"{TAG}_{r}@x.dev"}
         for r in ("owner", "admin", "staff", "front_desk")}

app = FastAPI()
app.include_router(routes.router, prefix="/api")


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def token(role):
    return jwt.encode({"user_id": USERS[role]["user_id"],
                       "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                      os.environ["JWT_SECRET"], algorithm="HS256")


async def call(method, path, role=None, **kw):
    headers = {"Authorization": f"Bearer {token(role)}"} if role else {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.request(method, f"/api/agent-control{path}", headers=headers, **kw)


def cmd_body(**over):
    return {"client_command_id": uuid.uuid4().hex, "target_agent_id": "claude-test-mock",
            "instruction": "Report your branch and current task.", **over}


@pytest.fixture(autouse=True, scope="module")
def setup():
    os.environ["CAOSCARE_AGENT_CONTROL_ENABLED"] = "1"

    async def _up():
        for u in USERS.values():
            await db.users.update_one({"user_id": u["user_id"]}, {"$set": u}, upsert=True)

    async def _down():
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}"}})

    run(_up())
    yield
    run(_down())


def test_access_control():
    assert run(call("GET", "/agents")).status_code == 401
    for role in ("admin", "staff", "front_desk"):
        assert run(call("GET", "/agents", role)).status_code == 403, role
    r = run(call("GET", "/agents", "owner"))
    assert r.status_code == 200
    ids = {a["agent_id"] for a in r.json()["agents"]}
    assert {"claude-1-coordinator", "claude-6-security", "claude-test-mock"} <= ids
    assert run(call("POST", "/commands", "staff", json=cmd_body())).status_code == 403


def test_disabled_flag_hides_everything():
    os.environ["CAOSCARE_AGENT_CONTROL_ENABLED"] = ""
    try:
        assert run(call("GET", "/agents", "owner")).status_code == 404
        assert run(call("POST", "/commands", "owner", json=cmd_body())).status_code == 404
    finally:
        os.environ["CAOSCARE_AGENT_CONTROL_ENABLED"] = "1"


def test_unbound_agents_are_offline_not_invented():
    agents = {a["agent_id"]: a for a in run(call("GET", "/agents", "owner")).json()["agents"]}
    coord = agents["claude-1-coordinator"]
    assert coord["status"]["state"] == "offline"
    assert coord["session_ref"] is None and coord["current_task"] is None and coord["branch"] is None
    mock = agents["claude-test-mock"]
    assert mock["status"]["state"] == "online" and mock["status"]["simulated"] is True


def test_vertical_slice_receipt_chain():
    body = cmd_body(issued_by="someone-else", status="completed", target="/bin/sh")
    r = run(call("POST", "/commands", "owner", json=body))
    assert r.status_code == 200, r.text
    cmd = r.json()
    # Body claims ignored: issuer from auth, status from the lifecycle.
    assert cmd["issued_by"]["user_id"] == USERS["owner"]["user_id"]
    assert cmd["status"] == "acknowledged"
    assert [e["to_status"] for e in cmd["status_log"]] == ["queued", "delivered", "acknowledged"]

    detail = run(call("GET", f"/commands/{cmd['command_id']}", "owner")).json()
    recs = detail["receipts"]
    assert [x["action_type"] for x in recs] == [
        "agent_command_issued", "agent_command_delivered", "agent_command_acknowledged"]
    origin = recs[0]["receipt_id"]
    assert recs[0]["parent_receipt_id"] is None
    for prev, nxt in zip(recs, recs[1:]):
        assert nxt["parent_receipt_id"] == prev["receipt_id"]
    assert all(x["correlation_id"] == origin for x in recs)
    assert all(x["authority"] == "owner_only" for x in recs)
    # Issue: authenticated owner, verified. Delivery: system, simulated (mock).
    # Response: agent self-report, simulated, never verified.
    assert recs[0]["identity_basis"] == "authenticated" and recs[0]["result_label"] == "verified"
    assert recs[1]["actor_type"] == "system" and recs[1]["result_label"] == "simulated"
    assert recs[2]["actor_id"] == "agent:claude-test-mock" and recs[2]["result_label"] != "verified"
    for prev, nxt in zip(recs, recs[1:]):
        assert nxt["before_state"] == prev["after_state"]
    # History entries point at their receipts.
    assert [e["receipt_id"] for e in detail["command"]["status_log"]] == [x["receipt_id"] for x in recs]
    assert detail["command"]["origin_receipt_id"] == origin
    assert detail["command"]["delivery_receipt_id"] == recs[1]["receipt_id"]
    assert detail["command"]["response_receipt_id"] == recs[2]["receipt_id"]
    agent = run(call("GET", "/agents/claude-test-mock", "owner")).json()["agent"]
    assert agent["last_receipt_id"] == recs[2]["receipt_id"]


def test_replay_refused_and_recorded():
    body = cmd_body()
    assert run(call("POST", "/commands", "owner", json=body)).status_code == 200
    r = run(call("POST", "/commands", "owner", json=body))
    assert r.status_code == 409
    n = run(db.agent_commands.count_documents({"client_command_id": body["client_command_id"]}))
    assert n == 1
    assert run(db.receipts.count_documents({"action_type": "agent_command_refused",
                                            "failure_reason": {"$regex": "replay"}})) >= 1


def test_unbound_or_unknown_target_refused_and_recorded():
    before = run(db.receipts.count_documents({"action_type": "agent_command_refused"}))
    r = run(call("POST", "/commands", "owner", json=cmd_body(target_agent_id="claude-1-coordinator")))
    assert r.status_code == 409
    r = run(call("POST", "/commands", "owner", json=cmd_body(target_agent_id="pane:%1")))
    assert r.status_code == 404
    after = run(db.receipts.count_documents({"action_type": "agent_command_refused"}))
    assert after == before + 2


def test_instruction_validation():
    for bad in ("", "   ", "x" * 4001, "ls\x1b[2J", "a\x00b"):
        assert run(call("POST", "/commands", "owner", json=cmd_body(instruction=bad))).status_code == 422
    ok = run(call("POST", "/commands", "owner", json=cmd_body(instruction="line one\n\tline two")))
    assert ok.status_code == 200


def test_delivery_failure_is_recorded():
    registry.BINDINGS["mock-fail"] = {"adapter": "mock", "target": "mock-fail", "fail": True}
    run(db.agent_registry.update_one({"agent_id": "claude-test-mock"},
                                     {"$set": {"binding_id": "mock-fail"}}))
    try:
        cmd = run(call("POST", "/commands", "owner", json=cmd_body())).json()
        assert cmd["status"] == "failed"
        recs = run(call("GET", f"/commands/{cmd['command_id']}", "owner")).json()["receipts"]
        assert [x["action_type"] for x in recs] == ["agent_command_issued", "agent_command_delivery_failed"]
        assert recs[1]["status"] == "failed" and recs[1]["failure_reason"]
    finally:
        run(db.agent_registry.update_one({"agent_id": "claude-test-mock"},
                                         {"$set": {"binding_id": "mock-test"}}))
        registry.BINDINGS.pop("mock-fail", None)


def test_no_route_takes_a_target_path_or_shell():
    for route in routes.router.routes:
        for p in getattr(route, "param_convertors", {}):
            assert p in ("agent_id", "command_id"), p
    fields = set(routes.CommandInput.model_fields)
    assert fields == {"client_command_id", "target_agent_id", "instruction",
                      "parent_command_id", "based_on_integration_sha"}
