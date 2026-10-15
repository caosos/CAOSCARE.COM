"""Room 214 self-code inspection through the real session paths (gate DB).

1. The resident session mint (`create_resident_session`, OpenAI faked) declares
   the tools + prompt line ONLY for the canonical Room 214 kiosk/resident; a
   Room 215 session and the demo room get neither.
2. Against the running gate backend (REACT_APP_BACKEND_URL): the verified
   Room 214 session can inspect/search/read with the exact HEAD SHA; a Room
   215 session - even when it sends room=214 / kiosk_id - an owner token, an
   admin token, the demo room and a bare caller are all refused; only POST
   exists; receipts are written for allowed and refused attempts.
"""
import asyncio
import os
import subprocess
import types
import uuid

import pytest
import requests

from deps import db
from routes import realtime_resident_session as rrs
from routes.realtime_room_lease import claim_or_reuse_room_lease
from routes.auth import _issue_jwt

TAG = f"sc{uuid.uuid4().hex[:8]}"
BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8070").rstrip("/")
API = f"{BASE}/api/aria/self-code"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HEAD = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()   # HEAD at collection; committing mid-run makes the backend's HEAD differ


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


class FakeClient:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *e): return False
    async def post(self, url, headers=None, json=None, **kw):
        class R:
            status_code = 200
            text = ""
            @staticmethod
            def json(): return {"value": "ek_fake", "expires_at": 0}
        return R()


@pytest.fixture(scope="module")
def world():
    """Canonical Room 214 record (stashing any pre-existing one), a Room 215
    neighbour, the demo kiosk, an owner and an admin user."""
    stashed = run(db.kiosks.find({"room": "214"}, {"_id": 0}).to_list(10))
    run(db.kiosks.delete_many({"room": "214"}))
    run(db.resident_aria_leases.delete_many({"room": {"$in": ["214", "215", "DEMO"]}}))
    k214, k215, kdemo = f"kio_{TAG}_214", f"kio_{TAG}_215", f"kio_{TAG}_demo"
    r214, r215, rdemo = f"res_{TAG}_214", f"res_{TAG}_215", f"res_{TAG}_demo"
    run(db.kiosks.insert_many([
        {"kiosk_id": k214, "room": "214", "resident_id": r214, "public_demo": False, "name": "214"},
        {"kiosk_id": k215, "room": "215", "resident_id": r215, "public_demo": False, "name": "215"},
        {"kiosk_id": kdemo, "room": "DEMO", "resident_id": rdemo, "public_demo": True, "name": "DEMO"}]))
    run(db.residents.insert_many([
        {"resident_id": r214, "name": f"{TAG} 214", "room": "214-HOME", "preferred_name": "M"},
        {"resident_id": r215, "name": f"{TAG} 215", "room": "215"},
        {"resident_id": rdemo, "name": f"{TAG} demo", "room": "DEMO", "synthetic": True}]))
    owner, admin = f"usr_{TAG}_owner", f"usr_{TAG}_admin"
    run(db.users.insert_many([
        {"user_id": owner, "email": f"{owner}@x.t", "name": "Owner", "role": "owner", "auth_provider": "jwt"},
        {"user_id": admin, "email": f"{admin}@x.t", "name": "Admin", "role": "admin", "auth_provider": "jwt"}]))
    w = types.SimpleNamespace(k214=k214, k215=k215, kdemo=kdemo, r214=r214, r215=r215, rdemo=rdemo,
                              owner=_issue_jwt(owner), admin=_issue_jwt(admin))
    yield w
    run(db.kiosks.delete_many({"kiosk_id": {"$in": [k214, k215, kdemo]}}))
    run(db.residents.delete_many({"resident_id": {"$in": [r214, r215, rdemo]}}))
    run(db.users.delete_many({"user_id": {"$in": [owner, admin]}}))
    run(db.resident_aria_leases.delete_many({"room": {"$in": ["214", "215", "DEMO"]}}))
    if stashed:
        run(db.kiosks.insert_many(stashed))


def mint(monkeypatch, payload):
    monkeypatch.setattr(rrs, "httpx", types.SimpleNamespace(AsyncClient=FakeClient))
    monkeypatch.setattr(rrs, "_require_openai_key", lambda: "sk-test-not-real")
    r = run(rrs.create_resident_session(payload))
    import json
    body = json.loads(r.body)
    run(db.resident_aria_leases.delete_many({"room": payload["room"]}))
    return body["_caos"]


def test_mint_declares_tools_only_for_room_214(world, monkeypatch):
    c = mint(monkeypatch, {"room": "214", "kiosk_id": world.k214, "resident_id": world.r214,
                           "session_id": f"rt_{TAG}_m214", "trigger_source": "wake_word"})
    names = [t["name"] for t in c["tools"]]
    assert names[-3:] == ["inspect_own_code", "search_own_code", "read_own_code"]
    assert "Your own source code (this verified Room 214 session only)" in c["instructions"]
    assert c["context"]["self_code_inspection"] is True
    for room, k, r in (("215", world.k215, world.r215), ("DEMO", world.kdemo, world.rdemo)):
        c = mint(monkeypatch, {"room": room, "kiosk_id": k, "resident_id": r, "session_id": f"rt_{TAG}_m{room}", "trigger_source": "wake_word"})
        assert not {"inspect_own_code", "search_own_code", "read_own_code"} & {t["name"] for t in c["tools"]}
        assert "Your own source code" not in c["instructions"] and c["context"]["self_code_inspection"] is False
    # a session claiming room 214 with another room's kiosk/resident gets nothing either
    c = mint(monkeypatch, {"room": "214", "kiosk_id": world.k215, "resident_id": world.r215, "session_id": f"rt_{TAG}_fake", "trigger_source": "manual_kiosk"})
    assert c["context"]["self_code_inspection"] is False and "inspect_own_code" not in str(c["tools"])


@pytest.fixture
def live(world):
    """A live canonical Room 214 lease and a live Room 215 lease, written by
    the backend's own lease function (what the mint does)."""
    s214, s215 = f"rt_{TAG}_live214", f"rt_{TAG}_live215"
    run(db.resident_aria_leases.delete_many({"room": {"$in": ["214", "215"]}}))
    a = run(claim_or_reuse_room_lease("214", world.r214, world.k214, "wake_word", s214))
    b = run(claim_or_reuse_room_lease("215", world.r215, world.k215, "wake_word", s215))
    assert a["claimed"] and b["claimed"]
    yield types.SimpleNamespace(s214=s214, s215=s215)
    run(db.resident_aria_leases.delete_many({"room": {"$in": ["214", "215"]}}))


def post(path, body, token=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(f"{API}/{path}", json=body, headers=h, timeout=20)


def test_room_214_session_can_inspect_search_read(world, live):
    r = post("inspect", {"session_id": live.s214, "resident_id": world.r214, "frontend_build_sha": HEAD})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["allowed"] and j["room"] == "214" and j["inspected_sha"] == HEAD and j["frontend_match"] is True
    assert j["read_only"] is True and j["write_tools"] == [] and "backend/routes/aria_life_memory.py" in j["approved_files"]
    loaded = j["loaded_backend_sha"]
    assert j["backend_match"] == (None if not loaded else HEAD.startswith(loaded) or loaded.startswith(HEAD))
    r = post("search", {"session_id": live.s214, "resident_id": world.r214, "query": "summarize_pending_sessions"})
    assert r.status_code == 200 and any(m["path"].endswith("aria_life_memory.py") for m in r.json()["matches"])
    r = post("read", {"session_id": live.s214, "resident_id": world.r214, "path": "backend/routes/aria_life_memory.py", "start_line": 1, "end_line": 400})
    j = r.json()
    assert r.status_code == 200 and j["start"] == 1 and j["end"] <= 120 and j["lines"] and j["inspected_sha"] == HEAD
    rc = run(db.receipts.find({"action_type": "self_code_inspection", "conversation_session_id": live.s214}, {"_id": 0}).sort("created_at", 1).to_list(10))
    assert [x["result"] for x in rc] == ["inspect_own_code", "search_own_code", "read_own_code"]
    assert all(x["after_state"]["inspected_sha"] == HEAD and x["after_state"]["allowed"] for x in rc)
    assert j["lines"][0] not in str(rc)


@pytest.mark.parametrize("label", ["other_room", "other_room_claiming_214", "owner", "admin", "demo", "bare"])
def test_everyone_else_is_refused(world, live, label):
    body = {"session_id": live.s215, "resident_id": world.r215}
    token = None
    if label == "other_room_claiming_214":
        body = {"session_id": live.s215, "resident_id": world.r214, "room": "214", "kiosk_id": world.k214}
    if label == "owner":
        body, token = {"session_id": f"rt_{TAG}_owner", "resident_id": world.r214}, world.owner
    if label == "admin":
        body, token = {"session_id": f"rt_{TAG}_admin", "resident_id": world.r214}, world.admin
    if label == "demo":
        d = run(claim_or_reuse_room_lease("DEMO", world.rdemo, world.kdemo, "manual_kiosk", f"rt_{TAG}_demo"))
        assert d["claimed"]
        body = {"session_id": f"rt_{TAG}_demo", "resident_id": world.rdemo}
    if label == "bare":
        body = {"session_id": f"rt_{TAG}_nothing", "resident_id": world.r214, "room": "214"}
    for path, extra in (("inspect", {}), ("search", {"query": "memory"}), ("read", {"path": "backend/routes/aria_memory.py"})):
        r = post(path, {**body, **extra}, token)
        assert r.status_code == 403, (label, path, r.text)
        assert r.json()["detail"]["reason"] in ("not_room_214", "no_live_session", "resident_claim_mismatch")
    rc = run(db.receipts.find({"action_type": "self_code_inspection", "conversation_session_id": body["session_id"]}, {"_id": 0}).to_list(10))
    assert rc and all(x["status"] == "failed" and x["after_state"]["allowed"] is False for x in rc)
    run(db.resident_aria_leases.delete_many({"room": "DEMO"}))


def test_secrets_traversal_and_methods(world, live):
    for bad, reason in (("backend/.env", "path_not_approved"), ("../backend/.env", "path_traversal"),
                        ("/etc/passwd", "path_not_relative"), ("/proc/self/environ", "path_not_relative"),
                        ("backend/routes/auth.py", "path_not_approved"), ("backend/server.py", "path_not_approved")):
        r = post("read", {"session_id": live.s214, "resident_id": world.r214, "path": bad})
        assert r.status_code == 403 and r.json()["detail"]["reason"] == reason, (bad, r.text)
    for m in ("get", "put", "delete", "patch"):
        assert getattr(requests, m)(f"{API}/read", timeout=10).status_code == 405
