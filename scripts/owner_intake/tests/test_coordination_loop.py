"""Communication-loop regressions (owner order c6222937108, 2026-10-16): real receipt shapes, correlation, one recovery,
idempotent pickup, stale pin, pagination. Offline: gh, the registry and the inbox are stubbed / tmp."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import coord_github as gh  # noqa: E402
import coord_host as host  # noqa: E402
import intake_inbox as inbox  # noqa: E402
import receiver  # noqa: E402

KNOWN = {"caoscare-1-4e", "caoscare-1-e7"}
# first lines of the two real Claude receipts that were misread as owner directives (c6219240110, c6219463449)
REAL_ACK = ("ACK — aria-appointment-verification-001 (session caoscare-1-e7)\n\n- Task: canonical appointment truth model per #166 "
            "c6213933229 (REPORTED / VERIFIED / NEEDS_CONFIRMATION).\n- Note: this ACK is late")
REAL_DONE = ("DONE — aria-appointment-verification-001 → READY_FOR_MERGE (session caoscare-1-e7)\n\n**What changed**\n"
             "- PR #185 → `integration/2026-09-27`. Head `72953d03cac27fedb47e6186ef76aa970f62506c`")
URGENT = ("REPORT DATE: Friday, October 16, 2026 — 2:15 PM America/Chicago\n\nOWNER URGENT REGRESSION — aria-room-opening-context-regression-003\n"
          "Priority: immediate.\n\nStatus: repository-DELIVERED only. ACK/WORKING required within 300 seconds. Verified context: "
          "aria-appointment-verification-001 DONE earlier.")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ago(s):
    return iso(datetime.now(timezone.utc) - timedelta(seconds=s))


def c(body, cid, at, login="caosos"):
    return {"body": body, "user": {"login": login}, "id": cid, "html_url": f"https://github.com/caosos/CAOSCARE.COM/issues/166#issuecomment-{cid}", "created_at": at}


# ---------- classification
def test_real_unmarked_receipts_are_coordinator_receipts():
    a = gh.classify(c(REAL_ACK, 6219240110, "2026-10-16T15:50:15Z"), known_sessions=KNOWN)
    d = gh.classify(c(REAL_DONE, 6219463449, "2026-10-16T16:02:02Z"), known_sessions=KNOWN)
    assert (a["kind"], a["state"], a["session"], a["unmarked"]) == ("coordinator_receipt", "ACK", "caoscare-1-e7", True)
    assert (d["kind"], d["state"], d["items"]) == ("coordinator_receipt", "DONE", ["aria-appointment-verification-001"])


def test_receipt_shape_needs_a_registry_known_session():
    assert gh.classify(c(REAL_ACK.replace("caoscare-1-e7", "caoscare-1-zz"), 1, "t"), known_sessions=KNOWN)["kind"] == "owner_directive"
    assert gh.classify(c(REAL_ACK, 1, "t"))["kind"] == "owner_directive"          # no registry evidence -> not trusted


def test_owner_text_with_ack_done_words_or_quotes_is_not_execution():
    for body in (URGENT, "> " + REAL_ACK, "Please post ACK — and then DONE when finished (session caoscare-1-e7)",
                 "Michael: the ACK c6219240110 was wrong.\nDONE — nothing"):
        assert gh.classify(c(body, 2, "t"), known_sessions=KNOWN)["kind"] == "owner_directive", body
    u = gh.classify(c(URGENT, 6222902220, "t"), known_sessions=KNOWN)
    assert u["tasks"] == ["aria-room-opening-context-regression-003"]             # an example item later in the body is not its task


# ---------- watcher fixture
@pytest.fixture
def W(tmp_path, monkeypatch):
    import coordination_watch as w
    for name, val in (("STATE_DIR", tmp_path), ("STATE_FILE", tmp_path / "s.json"), ("EVENTS", tmp_path / "e.jsonl"), ("DRY", False)):
        monkeypatch.setattr(w, name, val)
    monkeypatch.setattr(inbox, "INBOX", tmp_path / "inbox.jsonl"); monkeypatch.setattr(inbox, "LISTENER", tmp_path / "listener.json")
    monkeypatch.setattr(inbox, "DIR", tmp_path)
    monkeypatch.setenv("CAOS_INTAKE_DIR", str(tmp_path / "intake"))
    posted = []
    monkeypatch.setattr(gh, "post_comment", lambda repo, n, body: posted.append((n, body)) or f"https://x/{len(posted)}")
    monkeypatch.setattr(host, "known_sessions", lambda: set(KNOWN))
    monkeypatch.setattr(host, "duplicate_guard", lambda pin: {"interactive_sessions_in_cwd": ["caoscare-1-4e"]})
    live = {"verdict": "LIVE_IDLE", "live": True, "busy": False, "pid": os.getpid(), "evidence": ["e"]}
    monkeypatch.setattr(host, "coordinator_state", lambda pin, stall: live)
    feed = []
    monkeypatch.setattr(gh, "comments_since", lambda repo, n, since: [x for x in feed if x["created_at"] > since] if n == 166 else [])
    q = {"repo": "r", "authoritative_issue": 166, "watch_issues": [166], "mirror_pr": None, "branch": "b",
         "coordinator": {"session_name": "caoscare-1-4e", "session_id": "sid", "cwd_prefix": "/h"},
         "timers": {"poll_seconds": 60, "ack_seconds": 300, "stall_minutes": 45},
         "dispatch_gate": {"enabled": False}, "items": []}
    st = w.load_state(); st["cursor"] = ago(3600); st["seen_ids"] = [0]
    return {"w": w, "q": q, "st": st, "feed": feed, "posted": posted, "live": live, "tmp": tmp_path}


def arm(W):
    """A real armed listener: this test process stands in for the session pid (the listener's ancestor)."""
    W["tmp"].joinpath("listener.json").write_text(json.dumps({"session": "caoscare-1-4e", "pid": os.getpid(), "consumed_seq": 0}))


def titles(W):
    return [b.splitlines()[1] for _, b in W["posted"]]


def test_unrelated_receipts_and_deliveries_do_not_clear_an_obligation(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    feed.append(c(URGENT, 6222902220, ago(60)))
    w.tick(st, q)
    assert "c6222902220" in st["owner_open"]
    feed += [c(gh.WATCH + "\nDELIVERED aria-room-opening-context-regression-003", 11, ago(50)),           # watcher post
             c(gh.DA + "\nDELIVERED aria-room-opening-context-regression-003", 12, ago(45)),              # automatic delivery
             c(REAL_DONE.replace("aria-appointment", "aria-other"), 13, ago(40)),                          # another task's DONE
             c(gh.MAIN + "\nWORKING careops-153-drilldown-truth-002", 14, ago(35))]                        # unrelated receipt
    w.tick(st, q)
    assert "c6222902220" in st["owner_open"] and not st["owner_acked"]


def test_correlated_ack_by_task_or_command_clears_only_its_command(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    feed += [c(URGENT, 6222902220, ago(120)), c("QUEUE NOTE: please confirm the dashboard copy", 6222999999, ago(110))]
    w.tick(st, q)
    feed.append(c("ACK — aria-room-opening-context-regression-003 (session caoscare-1-4e)\n- cites c6222902220", 20, ago(100)))
    w.tick(st, q)
    assert "c6222902220" in st["owner_acked"] and st["owner_acked"]["c6222902220"]["ack_session"] == "caoscare-1-4e"
    assert "c6222999999" in st["owner_open"]                                    # a different command stays open
    feed.append(c(gh.MAIN + "\nACK — coord-note-001 (session caoscare-1-4e) re c6222999999", 21, ago(90)))
    w.tick(st, q)
    assert "c6222999999" in st["owner_acked"]


def test_receipt_older_than_the_command_never_answers_it(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    feed += [c(REAL_ACK, 6219240110, ago(200)), c("REDO: aria-appointment-verification-001 again", 30, ago(100))]
    w.tick(st, q)
    assert "c30" in st["owner_open"]                                            # the earlier ACK does not satisfy the later command


def test_missed_ack_one_redelivery_to_armed_listener_then_one_need(W, monkeypatch):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    arm(W)
    feed.append(c(URGENT, 6222902220, ago(400)))
    w.tick(st, q)
    od = st["owner_open"]["c6222902220"]
    assert od["delivery"]["ok"] is True and od["recovery"]["ok"] is True       # immediate delivery + one redelivery (> 300 s)
    ent = inbox.entries()
    assert [e["reason"] for e in ent] == ["delivery", "redelivery"] and all(e["session"] == "caoscare-1-4e" for e in ent)
    assert "receiver.py pickup c6222902220 --task aria-room-opening-context-regression-003" in ent[1]["text"]
    for _ in range(3):
        w.tick(st, q)
    assert len(inbox.entries()) == 2                                            # never a second redelivery
    od["recovery"]["at"] = ago(400)
    w.tick(st, q); w.tick(st, q)
    assert sum("NEED_OWNER" in t for t in titles(W)) == 1


def test_missed_ack_without_armed_listener_is_reported_not_claimed(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    feed.append(c(URGENT, 6222902220, ago(400)))
    w.tick(st, q)
    rec = st["owner_open"]["c6222902220"]["recovery"]
    assert rec["ok"] is False and "NOT armed" in rec["note"]
    body = [b for _, b in W["posted"] if "COORDINATOR NOT REACHABLE" in b][0]
    assert "intake_inbox.py listen --session caoscare-1-4e" in body


def test_listener_must_belong_to_the_pinned_session(W):
    W["tmp"].joinpath("listener.json").write_text(json.dumps({"session": "caoscare-1-4e", "pid": os.getpid()}))
    assert inbox.armed("caoscare-1-4e", os.getpid())["armed"] is True
    assert inbox.armed("caoscare-1-4e", 999999)["armed"] is False             # running, but not under that session
    assert inbox.armed("caoscare-1-e7", os.getpid())["armed"] is False        # armed for someone else


def test_pickup_suppresses_recovery_and_is_published(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    arm(W)
    feed.append(c(URGENT, 6222902220, ago(30)))
    w.tick(st, q)
    receiver.main(["pickup", "c6222902220", "--task", "aria-room-opening-context-regression-003", "--session", "caoscare-1-4e"])
    st["owner_open"]["c6222902220"]["at"] = ago(400)
    w.tick(st, q)
    od = st["owner_open"]["c6222902220"]
    assert od["pickup_session"] == "caoscare-1-4e" and "recovery" not in od
    assert "pickup-c6222902220" in st["published"]


def test_duplicate_and_replayed_deliveries_are_idempotent(W, capsys):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    arm(W)
    cm = c(URGENT, 6222902220, ago(30))
    feed += [cm, dict(cm)]                                                      # same comment listed twice (page overlap)
    w.tick(st, q); w.tick(st, q)
    assert len(inbox.entries()) == 1 and len(st["owner_open"]) == 1
    assert inbox.deliver("caoscare-1-4e", "c6222902220", "t", "x", "delivery")["duplicate"] is True
    args = ["pickup", "c6222902220", "--task", "coord-x-001", "--session", "caoscare-1-4e"]
    receiver.main(args); receiver.main(args)
    receiver.main(["status", "coord-x-001", "DONE", "--issue", "166"])
    receiver.main(args)
    out = [json.loads(l)["verdict"] for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    assert out == ["NEW", "DUPLICATE", "COMPLETED"]                              # replay never restarts, completed never replays


def test_done_for_a_different_task_does_not_close_a_delivery(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    st["dispatched"] = {"coord-loop-proof-001": {"at": ago(100), "url": "u", "kind": "task", "ack_url": "a"}}
    feed.append(c(REAL_DONE, 40, ago(50)))
    w.tick(st, q)
    assert st["dispatched"]["coord-loop-proof-001"].get("done_url") is None


def test_stale_pin_blocks_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "SESSIONS", tmp_path)
    (tmp_path / f"{os.getpid()}.json").write_text(json.dumps({"pid": os.getpid(), "name": "caoscare-1-4e", "sessionId": "NEW-ID", "kind": "interactive"}))
    s = host.coordinator_state({"session_name": "caoscare-1-4e", "session_id": "OLD-ID"})
    assert s["verdict"] == "PIN_MISMATCH" and s["live"] is False
    assert host.known_sessions() == {"caoscare-1-4e"}


def test_stale_pin_publishes_need_and_queues_nothing_reachable(W, monkeypatch):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    arm(W)
    monkeypatch.setattr(host, "coordinator_state", lambda pin, stall: {"verdict": "PIN_MISMATCH", "live": False, "session_id": "x", "evidence": ["pin mismatch"]})
    feed.append(c(URGENT, 6222902220, ago(400)))
    w.tick(st, q)
    assert st["owner_open"]["c6222902220"]["recovery"]["ok"] is False
    assert any("pin is stale" in t for t in titles(W))


def test_pagination_reads_every_page(monkeypatch):
    pages = {1: [{"id": i} for i in range(100)], 2: [{"id": i} for i in range(100, 150)]}
    calls = []
    monkeypatch.setattr(gh, "gh_json", lambda args, timeout=60: calls.append(args[0]) or pages[int(args[0].rsplit("page=", 1)[1])])
    assert len(gh.comments_since("r", 166, "2026-10-16T00:00:00Z")) == 150 and len(calls) == 2


def test_cursor_overlap_reads_a_same_second_comment_once(W):
    w, st, q, feed = W["w"], W["st"], W["q"], W["feed"]
    t = ago(30)
    feed.append(c(URGENT, 50, t))
    w.tick(st, q)
    assert st["cursor"] == t
    feed.append(c("SECOND order in the same second: coord-same-001", 51, t))   # GitHub lists it only on the next poll
    w.tick(st, q); w.tick(st, q)
    assert {"c50", "c51"} <= set(st["owner_open"])
    assert sum(1 for k in st["published"] if k in ("c50", "c51")) == 2


def test_listener_wakes_on_its_entry_and_records_consumption(W):
    inbox.deliver("caoscare-1-4e", "c1", "coord-x-001", "hello", "delivery")
    p = subprocess.run([sys.executable, str(HERE / "intake_inbox.py"), "listen", "--session", "caoscare-1-4e", "--poll", "0.1"],
                       capture_output=True, text=True, timeout=20, env={**os.environ, "CAOS_COORD_STATE": str(W["tmp"])})
    assert p.returncode == 0 and json.loads(p.stdout.splitlines()[0])["command"] == "c1"
    assert json.loads(W["tmp"].joinpath("listener.json").read_text())["consumed_seq"] == 1
