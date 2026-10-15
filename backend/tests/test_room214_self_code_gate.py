"""Room 214 read-only self-code inspection (owner feature 2026-10-15).

Proves the identity gate (only the live canonical Room 214 session, proven
from the backend's own lease/kiosk/resident records plus loopback origin),
the bounded source rules (allow-list, traversal, symlink, secrets, binary,
line caps), revision truth (inspected vs loaded SHA), receipts, and that no
write path exists. Pure unit tests: fake db, temp checkout, no server.
"""
import asyncio
import os
import re
import stat
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models import now_utc
from routes import self_code_identity as ident
from routes import self_code_source as src
from routes import self_code_inspection as insp
from routes import self_code_tools as tools


def run(c):
    return asyncio.run(c)


KIOSK = {"kiosk_id": "kio_214", "room": "214", "resident_id": "res_214", "public_demo": False}
RESIDENT = {"resident_id": "res_214", "synthetic": False}
LOOPBACK = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
LAN = SimpleNamespace(client=SimpleNamespace(host="192.168.1.77"))


def lease(**over):
    base = {"room": "214", "resident_id": "res_214", "kiosk_id": "kio_214", "session_id": "rt_214",
            "status": "active", "trigger_source": "wake_word", "last_seen_at": now_utc().isoformat()}
    return {**base, **over}


class FakeCursor:
    def __init__(self, docs): self.docs = docs
    async def to_list(self, n): return list(self.docs)[:n]


def fake_db(kiosks=(KIOSK,), residents=(RESIDENT,), leases=()):
    async def kiosk_find_one(q, proj=None):
        return next((k for k in kiosks if all(k.get(a) == b for a, b in q.items())), None)
    async def resident_find_one(q, proj=None):
        return next((r for r in residents if r.get("resident_id") == q.get("resident_id") or r.get("room") == q.get("room")), None)
    async def lease_find_one(q, proj=None):
        for l in leases:
            if l["session_id"] == q["session_id"] and l["status"] in q["status"]["$in"] and l["last_seen_at"] >= q["last_seen_at"]["$gte"]:
                return l
        return None
    return SimpleNamespace(
        kiosks=SimpleNamespace(find=lambda q, p=None: FakeCursor([k for k in kiosks if k.get("room") == q["room"] and not k.get("public_demo")]),
                               find_one=kiosk_find_one),
        residents=SimpleNamespace(find_one=resident_find_one),
        resident_aria_leases=SimpleNamespace(find_one=lease_find_one),
    )


@pytest.fixture
def wired(monkeypatch):
    def wire(**kw):
        d = fake_db(**kw)
        monkeypatch.setattr(ident, "db", d)
        import routes.kiosk_identity as ki
        monkeypatch.setattr(ki, "db", d)
        monkeypatch.delenv("CAOSCARE_SELF_INSPECT", raising=False)
        monkeypatch.delenv("CAOSCARE_SELF_INSPECT_ORIGINS", raising=False)
        return d
    return wire


# ---------------------------------------------------------------- identity gate

def test_verified_room_214_session_is_allowed(wired):
    wired(leases=[lease()])
    g = run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))
    assert g["allowed"] is True
    assert g["room"] == "214" and g["kiosk_id"] == "kio_214" and g["resident_id"] == "res_214"
    assert g["authority"] == "room214_lease_verified" and g["trigger_source"] == "wake_word"


@pytest.mark.parametrize("over,reason", [
    ({"room": "215"}, "not_room_214"),                 # another resident room
    ({"room": "DEMO", "kiosk_id": "kio_demo"}, "not_room_214"),   # demo / simulator room
    ({"kiosk_id": "kio_other"}, "kiosk_mismatch"),     # a different screen claiming the room
    ({"resident_id": "res_other"}, "resident_mismatch"),
    ({"status": "released"}, "no_live_session"),
    ({"last_seen_at": (now_utc() - timedelta(seconds=600)).isoformat()}, "no_live_session"),  # stale
])
def test_other_sessions_are_refused(wired, over, reason):
    wired(leases=[lease(**over)])
    g = run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))
    assert g == {**g, "allowed": False, "reason": reason}


def test_sessions_without_a_room_lease_are_refused(wired):
    """Owner /aria, Admin Aria, telephone Aria and plain API callers never
    hold a resident room lease - there is nothing to verify, so refused."""
    wired(leases=[])
    assert run(ident.verify_room214_session("owner_session", "res_214", LOOPBACK))["reason"] == "no_live_session"
    assert run(ident.verify_room214_session(None, None, LOOPBACK))["reason"] == "missing_session"


def test_supplying_room_214_from_another_session_does_not_bypass(wired):
    """A Room 215 session that says resident_id=res_214 (or passes room=214 in
    any argument) is still judged by ITS lease, which the backend wrote."""
    wired(leases=[lease(room="215", kiosk_id="kio_215", resident_id="res_215", session_id="rt_215")])
    g = run(ident.verify_room214_session("rt_215", "res_214", LOOPBACK))
    assert g["allowed"] is False and g["reason"] == "not_room_214"
    # and a Room 214 lease cannot be used by a caller claiming another resident
    wired(leases=[lease()])
    assert run(ident.verify_room214_session("rt_214", "res_other", LOOPBACK))["reason"] == "resident_claim_mismatch"


def test_origin_must_be_the_room_node(wired):
    wired(leases=[lease()])
    assert run(ident.verify_room214_session("rt_214", "res_214", LAN))["reason"] == "origin_not_room_node"
    assert run(ident.verify_room214_session("rt_214", "res_214", None))["reason"] == "origin_not_room_node"


def test_fails_closed_without_a_canonical_record(wired, monkeypatch):
    wired(kiosks=[], leases=[lease()])
    assert run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))["reason"] == "no_canonical_room_record"
    wired(kiosks=[KIOSK, {**KIOSK, "kiosk_id": "kio_dup"}], leases=[lease()])   # ambiguous
    assert run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))["reason"] == "no_canonical_room_record"
    wired(kiosks=[{**KIOSK, "public_demo": True}], leases=[lease()])            # the demo kiosk is never canonical
    assert run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))["reason"] == "no_canonical_room_record"
    wired(residents=[{**RESIDENT, "synthetic": True}], leases=[lease()])          # simulated resident
    assert run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))["reason"] == "no_canonical_room_record"
    wired(leases=[lease()])
    monkeypatch.setenv("CAOSCARE_SELF_INSPECT", "off")
    assert run(ident.verify_room214_session("rt_214", "res_214", LOOPBACK))["reason"] == "disabled"


def test_tools_declared_only_for_the_canonical_room_214_mint(wired):
    wired()
    claimed = {"claimed": True, "session_id": "rt_214"}
    ok = run(tools.self_code_session_extras({"room": "214", "kiosk_id": "kio_214", "resident_id": "res_214"}, claimed))
    assert [t["name"] for t in ok["tools"]] == list(tools.TOOL_NAMES) and "Your own source code" in ok["prompt"]
    for payload in ({"room": "215", "kiosk_id": "kio_215", "resident_id": "res_215"},
                    {"room": "214", "kiosk_id": "kio_other", "resident_id": "res_214"},
                    {"room": "DEMO", "kiosk_id": "kio_demo", "resident_id": "res_demo"}):
        assert run(tools.self_code_session_extras(payload, claimed)) == {"tools": [], "prompt": "", "enabled": False}
    assert run(tools.self_code_session_extras({"room": "214", "kiosk_id": "kio_214", "resident_id": "res_214"}, {"claimed": False}))["enabled"] is False


def test_no_other_aria_build_declares_the_tools():
    from routes.realtime_aria_tools import _build_aria_tools            # owner /aria
    from routes.phone_aria_tools import build_phone_tools                # telephone
    from routes.admin_assistant_tools import build_admin_tools           # Admin Aria
    from routes.realtime_tools import _build_tools                       # every resident room's base catalog
    names = {t["name"] for t in run(_build_aria_tools())}
    names |= {t["name"] for t in build_phone_tools([], ["nursing"])}
    names |= {t.get("function", t).get("name") for t in build_admin_tools()}
    names |= {t["name"] for t in run(_build_tools())}
    assert not names & set(tools.TOOL_NAMES)


# ---------------------------------------------------------------- source rules

@pytest.fixture
def checkout(tmp_path, monkeypatch):
    (tmp_path / "backend/routes").mkdir(parents=True)
    good = tmp_path / "backend/routes/realtime_fake.py"
    good.write_text("\n".join(f"line {i} token=sk-abcdefghijklmnopqrstuvwxyz" if i == 7 else f"line {i}" for i in range(1, 301)) + "\n")
    (tmp_path / "backend/routes/aria_secrets.py").write_text("x = 1\n")          # matches a glob, denied by name
    (tmp_path / "backend/routes/realtime_bin.py").write_bytes(b"\x00\x01binary")  # binary
    (tmp_path / "backend/.env").write_text("OPENAI_API_KEY=nope\n")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside/evil.py").write_text("print('escaped')\n")
    os.symlink(tmp_path / "outside/evil.py", tmp_path / "backend/routes/realtime_link.py")   # file symlink
    (tmp_path / "room-node").mkdir()
    os.symlink(tmp_path / "outside", tmp_path / "room-node/aria_wake")                       # directory symlink
    monkeypatch.setattr(src, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("CAOSCARE_RUNTIME_SHA", raising=False)
    return tmp_path


def test_allow_list_excludes_symlinks_secrets_and_binaries(checkout):
    assert src.approved_files() == ["backend/routes/realtime_fake.py"]


@pytest.mark.parametrize("bad,reason", [
    ("backend/.env", "path_not_approved"), (".env", "path_not_approved"),
    ("backend/routes/../.env", "path_traversal"), ("../../etc/passwd", "path_traversal"),
    ("/etc/passwd", "path_not_relative"), ("~/.ssh/id_rsa", "path_not_relative"),
    ("backend\\routes\\realtime_fake.py", "path_not_relative"), ("C:/x.py", "path_not_relative"),
    ("backend/routes/realtime_link.py", "path_not_approved"),          # symlink escape
    ("room-node/aria_wake/evil.py", "path_not_approved"),               # directory symlink escape
    ("backend/routes/aria_secrets.py", "path_not_approved"),
    ("backend/routes/realtime_bin.py", "path_not_approved"),
    ("/proc/self/environ", "path_not_relative"), ("", "path_required"), (None, "path_required"),
    ("backend/routes/realtime_fake.py\0", "path_not_relative"),
])
def test_paths_outside_the_allow_list_are_refused(checkout, bad, reason):
    with pytest.raises(src.SourceRefused) as e:
        src.resolve(bad)
    assert e.value.reason == reason


def test_reads_are_bounded_and_redacted(checkout):
    r = src.read_lines("backend/routes/realtime_fake.py", 1, None)
    assert (r["start"], r["end"], r["total_lines"], r["truncated"]) == (1, src.MAX_LINES, 300, True)
    r = src.read_lines("backend/routes/realtime_fake.py", 250, 99999)
    assert (r["start"], r["end"]) == (250, 300) and r["lines"][-1] == "300: line 300"
    r = src.read_lines("backend/routes/realtime_fake.py", 5, 9)
    assert len(r["lines"]) == 5 and "sk-" not in r["lines"][2] and "[redacted]" in r["lines"][2]


def test_search_is_literal_capped_and_redacted(checkout):
    with pytest.raises(src.SourceRefused):
        src.search("x")
    with pytest.raises(src.SourceRefused):
        src.search("y" * (src.MAX_QUERY + 1))
    r = src.search("LINE 2")
    assert r["matches"][0] == {"path": "backend/routes/realtime_fake.py", "line": 2, "text": "line 2"}
    assert len(r["matches"]) <= src.PER_FILE_RESULTS
    assert "sk-" not in src.search("token=")["matches"][0]["text"]


def test_revision_truth(checkout, monkeypatch):
    r = src.revision("backend/routes/realtime_fake.py")        # tmp dir is not a git checkout
    assert r["inspected_sha"] is None and r["backend_match"] is None
    monkeypatch.setenv("CAOSCARE_RUNTIME_SHA", "37cccd7")
    assert src.revision()["backend_match"] is None             # loaded known, inspected unknown -> unknown, not a claim
    assert src._same_commit("37cccd76f93bd7557b22cf26f1fcfb8415a09331", "37cccd7") is True
    assert src._same_commit("37cccd76f93bd7557b22cf26f1fcfb8415a09331", "bb657da") is False
    assert src._same_commit(None, "bb657da") is None


def test_real_checkout_reports_its_exact_head(monkeypatch):
    import subprocess
    head = subprocess.run(["git", "-C", str(src.REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    monkeypatch.setenv("CAOSCARE_RUNTIME_SHA", head[:7])
    r = src.revision("backend/routes/self_code_source.py")
    assert r["inspected_sha"] == head and len(head) == 40 and r["backend_match"] is True
    monkeypatch.setenv("CAOSCARE_RUNTIME_SHA", "0000000")
    assert src.revision()["backend_match"] is False           # loaded-vs-repository mismatch is reported, not hidden
    assert "backend/routes/aria_life_memory.py" in src.approved_files()
    assert not any(".env" in f or "/node_modules/" in f for f in src.approved_files())


# ---------------------------------------------------------------- router + receipts + no write path

@pytest.fixture
def api(wired, monkeypatch):
    wired(leases=[lease()])
    receipts = []
    async def fake_receipt(**kw):
        receipts.append(kw); return {"receipt_id": f"rcpt_{len(receipts)}"}
    monkeypatch.setattr(insp, "create_receipt", fake_receipt)
    monkeypatch.setenv("CAOSCARE_RUNTIME_SHA", "0000000")
    return receipts


def test_inspect_read_search_record_receipts_without_source_text(api):
    body = insp.InspectInput(session_id="rt_214", resident_id="res_214", frontend_build_sha=None)
    r = run(insp.inspect_own_code(body, LOOPBACK))
    assert r["allowed"] and r["read_only"] and r["write_tools"] == [] and r["backend_match"] is False
    assert r["inspected_sha"] and "NOT the backend currently serving" in r["message"]
    rd = run(insp.read_own_code(insp.ReadInput(session_id="rt_214", resident_id="res_214", path="backend/routes/self_code_identity.py", start_line=1, end_line=500), LOOPBACK))
    assert rd["end"] - rd["start"] + 1 <= src.MAX_LINES and rd["lines"]
    sr = run(insp.search_own_code(insp.SearchInput(session_id="rt_214", resident_id="res_214", query="verify_room214_session"), LOOPBACK))
    assert any(m["path"] == "backend/routes/self_code_identity.py" for m in sr["matches"])
    assert [x["result"] for x in api] == ["inspect_own_code", "read_own_code", "search_own_code"]
    for rc in api:
        after = rc["provenance"]["after_state"]
        assert rc["status"] == "completed" and rc["room"] == "214" and rc["conversation_session_id"] == "rt_214"
        assert after["allowed"] is True and after["inspected_sha"] == r["inspected_sha"]
        assert after["loaded_backend_sha"] == "0000000" and after["backend_match"] is False
        assert rc["provenance"]["identity_basis"] == "unverified_room_claim" and rc["provenance"]["authority"] == "room214_lease_verified"
        assert "lines" not in str(after) and rd["lines"][0] not in str(rc)
    assert api[1]["provenance"]["after_state"]["request"] == {"path": "backend/routes/self_code_identity.py", "start_line": 1, "end_line": 500, "start": 1, "end": rd["end"]}


def test_refusals_are_receipted_and_return_403(api):
    from fastapi import HTTPException
    other = insp.InspectInput(session_id="rt_215", resident_id="res_214", frontend_build_sha=None)
    with pytest.raises(HTTPException) as e:
        run(insp.inspect_own_code(other, LOOPBACK))
    assert e.value.status_code == 403 and e.value.detail["reason"] == "no_live_session"
    with pytest.raises(HTTPException) as e:
        run(insp.read_own_code(insp.ReadInput(session_id="rt_214", resident_id="res_214", path="backend/.env"), LOOPBACK))
    assert e.value.status_code == 403 and e.value.detail["reason"] == "path_not_approved"
    with pytest.raises(HTTPException) as e:
        run(insp.read_own_code(insp.ReadInput(session_id="rt_214", resident_id="res_214", path="../backend/.env"), LOOPBACK))
    assert e.value.detail["reason"] == "path_traversal"
    assert [(x["status"], x["failure_reason"], x["room"]) for x in api] == [
        ("failed", "no_live_session", None), ("failed", "path_not_approved", "214"), ("failed", "path_traversal", "214")]
    assert api[0]["provenance"]["after_state"]["allowed"] is False


def test_only_three_post_routes_and_no_write_path():
    import server
    mine = [r for r in server.app.routes if getattr(r, "path", "").startswith("/api/aria/self-code")]
    assert sorted(r.path for r in mine) == ["/api/aria/self-code/inspect", "/api/aria/self-code/read", "/api/aria/self-code/search"]
    assert all(r.methods == {"POST"} for r in mine)
    import inspect as pyinspect
    forbidden = re.compile(r"write_text|write_bytes|open\([^)]*['\"][wax]|os\.remove|os\.unlink|shutil|rmtree|\.rename\(|"
                           r"os\.system|shell\s*=\s*True|subprocess\.Popen|db\.\w+\.(insert|update|delete|replace|drop)")
    for mod in (ident, src, insp, tools):
        text = pyinspect.getsource(mod)
        assert not forbidden.search(text), mod.__name__
    assert set(re.findall(r'_git\("([a-z-]+)"', pyinspect.getsource(src))) == {"rev-parse", "status"}
