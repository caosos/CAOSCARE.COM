"""Coordination watch: classification, dedup, exceptions, gate and host verdicts - offline, no gh."""
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import coord_github as gh  # noqa: E402
import coord_host as host  # noqa: E402
import coord_queue as cq  # noqa: E402


def c(body, login="caosos", cid=1, at="2026-10-15T20:00:00Z"):
    return {"body": body, "user": {"login": login}, "id": cid, "html_url": f"https://x/{cid}", "created_at": at}


def test_classify_main_claude_states_and_boundary():
    r = gh.classify(c(gh.MAIN + "\n**CO-008 v11 CUTOVER RECEIPT** (owner decision)\n- run x"))
    assert r["kind"] == "coordinator_receipt" and r["state"] == "DONE" and r["boundary"] is False
    r = gh.classify(c(gh.MAIN + "\n**RELEASE DEPLOYED to Linode: COMPLETE** sha 1f60a58"))
    assert r["state"] == "DONE" and r["boundary"] is True and "1f60a58" in r["shas"]
    r = gh.classify(c(gh.MAIN + "\n**#153 slice 2 WORKING** careops-153-drilldown-truth-002"))
    assert r["state"] == "WORKING" and r["items"] == ["careops-153-drilldown-truth-002"]
    r = gh.classify(c(gh.MAIN + "\nNEED_OWNER: credentials missing"))
    assert r["state"] == "BLOCKED"


def test_classify_owner_watcher_and_others():
    assert gh.classify(c("QUEUE UPDATE - OWNER DIRECTION"))["kind"] == "owner_directive"
    assert gh.classify(c(gh.WATCH + gh.MAIN + "\n**anything**"))["kind"] == "watcher"
    assert gh.classify(c(gh.DA + "\nDELIVERED da-99f66f3163"))["kind"] == "da_delivery"
    assert gh.classify(c(gh.RECV + "\nACK da-99f66f3163"))["kind"] == "receiver_status"
    assert gh.classify(c("hello", login="someone"))["kind"] == "other"


def test_receipt_bodies_have_required_fields_and_wake_semantics():
    f = {"timestamp": "t", "task": "x", "coordinator": "caoscare-1-ec"}
    quiet = gh.receipt_body("T", f)
    assert gh.WATCH in quiet and gh.MAIN in quiet                       # routine: must NOT wake Main Claude
    wake = gh.receipt_body("T", f, wake=True)
    assert gh.WATCH in wake and gh.MAIN not in wake                     # delivery: must wake it
    mirror = gh.receipt_body("T", f, mirror=True)
    assert mirror.splitlines()[1].startswith("CAOSCARE RECEIPT:")      # ChatGPT supervisor wake line
    for k in ("timestamp", "task", "coordinator", "state", "branch", "head_sha", "tested_sha", "loaded_sha",
              "host_state", "last_host_evidence", "receipt/evidence", "eta", "next_check_at", "blocker", "next_action"):
        assert f"**{k}:**" in quiet
    assert "**eta:** UNKNOWN" in quiet                                  # no invented ETA


def test_queue_gate_and_next_ready(tmp_path):
    q = {"dispatch_gate": {"enabled": True, "require_boundary": "release"},
         "items": [{"id": "coord-test-001", "kind": "coordination_test", "status": "READY", "text": "t"},
                   {"id": "task-a", "kind": "task", "status": "READY", "text": "a"},
                   {"id": "task-b", "kind": "task", "status": "QUEUED", "text": "b"}]}
    assert cq.next_ready(q, set())["id"] == "task-a"                              # tests never count as the next task
    assert cq.next_ready(q, set(), kind="coordination_test")["id"] == "coord-test-001"
    assert cq.next_ready(q, {"task-a"}) is None
    assert cq.gate_open(q, False, {"verdict": "LIVE_IDLE"})[0] is False           # boundary required
    assert cq.gate_open(q, True, {"verdict": "LIVE_BUSY"})[0] is False            # busy: hold
    assert cq.gate_open(q, True, {"verdict": "LIVE_IDLE"})[0] is True
    q["dispatch_gate"]["enabled"] = False
    assert cq.gate_open(q, True, {"verdict": "LIVE_IDLE"})[0] is False
    txt = cq.delivery_text(q["items"][1], 166, "caoscare-1-ec")
    assert "ACK task-a" in txt and "#166" in txt and "caoscare-1-ec" in txt


def test_host_verdicts(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "SESSIONS", tmp_path)
    pin = {"session_name": "caoscare-1-ec", "session_id": "sid", "cwd_prefix": "/home/caoscare-1"}
    assert host.coordinator_state(pin)["verdict"] == "UNVERIFIED"
    me = os.getpid()
    (tmp_path / f"{me}.json").write_text(json.dumps({"pid": me, "name": "caoscare-1-ec", "sessionId": "sid", "cwd": "/home/caoscare-1",
                                                     "kind": "interactive", "status": "busy", "statusUpdatedAt": 1e3 * (__import__("time").time() - 5)}))
    s = host.coordinator_state(pin)
    assert s["verdict"] == "LIVE_BUSY" and s["live"] and s["pid"] == me
    (tmp_path / f"{me}.json").write_text(json.dumps({"pid": me, "name": "caoscare-1-ec", "sessionId": "sid", "cwd": "/home/caoscare-1",
                                                     "kind": "interactive", "status": "idle", "statusUpdatedAt": 1e3 * (__import__("time").time() - 4000)}))
    assert host.coordinator_state(pin, stall_minutes=45)["verdict"] == "STALE"
    (tmp_path / "999999.json").write_text(json.dumps({"pid": 999999, "name": "caoscare-1-zz", "sessionId": "sid2", "kind": "interactive"}))
    assert host.coordinator_state({"session_name": "caoscare-1-zz", "session_id": "sid2"})["verdict"] == "STOPPED"
    assert host.duplicate_guard(pin)["interactive_sessions_in_cwd"] == ["caoscare-1-ec"]


def test_tick_dedups_and_dispatches_test_item_only_while_live(tmp_path, monkeypatch):
    import coordination_watch as cw
    monkeypatch.setattr(cw, "STATE_DIR", tmp_path); monkeypatch.setattr(cw, "STATE_FILE", tmp_path / "s.json"); monkeypatch.setattr(cw, "EVENTS", tmp_path / "e.jsonl")
    monkeypatch.setattr(cw, "DRY", True)
    posted = []
    monkeypatch.setattr(gh, "post_comment", lambda repo, n, body: posted.append((n, body)) or "https://x/p")
    comments = [c(gh.MAIN + "\n**release DEPLOYED to Linode COMPLETE**", cid=10, at="2026-10-15T21:00:00Z"),
                c("OWNER NOTE queued", cid=11, at="2026-10-15T21:01:00Z")]
    monkeypatch.setattr(gh, "comments_since", lambda repo, n, since: comments if n == 166 else [])
    monkeypatch.setattr(host, "coordinator_state", lambda pin, stall: {"verdict": "LIVE_BUSY", "live": True, "busy": True, "evidence": ["e"]})
    monkeypatch.setattr(host, "duplicate_guard", lambda pin: {"interactive_sessions_in_cwd": ["caoscare-1-ec"]})
    q = {"repo": "r", "authoritative_issue": 166, "watch_issues": [166], "mirror_pr": 131,
         "coordinator": {"session_name": "caoscare-1-ec", "session_id": "sid", "cwd_prefix": "/h"},
         "timers": {"poll_seconds": 60, "ack_minutes": 30, "stall_minutes": 45},
         "dispatch_gate": {"enabled": True, "require_boundary": "x"},
         "items": [{"id": "coord-test-001", "kind": "coordination_test", "status": "READY", "text": "t"},
                   {"id": "task-a", "kind": "task", "status": "READY", "text": "a"}]}
    st = cw.load_state(); st["cursor"] = "2026-10-15T20:00:00Z"
    s1 = cw.tick(st, q)
    assert st["boundary_seen"] is True and "coord-test-001" in st["dispatched"] and "task-a" not in st["dispatched"]   # busy: real item held
    n_pub = len(st["published"])
    s2 = cw.tick(st, q)                                                        # same comments again (cursor moved; none new)
    assert len(st["published"]) == n_pub and s2["events"] == []                # no duplicate receipts
    # ACK arrives for the test item
    comments.append(c(gh.MAIN + "\nACK coord-test-001 received", cid=12, at="2026-10-15T21:05:00Z"))
    cw.tick(st, q)
    assert st["dispatched"]["coord-test-001"]["ack_url"] == "https://x/12"
    # idle now and test ACKed -> real item dispatched through the open gate
    monkeypatch.setattr(host, "coordinator_state", lambda pin, stall: {"verdict": "LIVE_IDLE", "live": True, "busy": False, "evidence": ["e"]})
    cw.tick(st, q)
    assert "task-a" in st["dispatched"]
