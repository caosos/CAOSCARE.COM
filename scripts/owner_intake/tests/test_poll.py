import json, os, stat, subprocess, sys, textwrap
from pathlib import Path
import pytest

POLL = Path(__file__).resolve().parents[1] / "poll.py"

FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    st = json.load(open(os.environ["FAKE_GH_STATE"]))
    with open(os.environ["FAKE_GH_LOG"], "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\\n")
    if st.get("fail"):
        print("HTTP 403 rate limit", file=sys.stderr); sys.exit(1)
    a = sys.argv[1:]
    if "-X" in a:
        print("{}"); sys.exit(0)
    path = a[1]
    if "/comments" in path:
        print(json.dumps(st["comments"])); sys.exit(0)
    if "labels=" in path:
        print(json.dumps(st.get("labelled", []))); sys.exit(0)
    print(json.dumps(st["issue"]))
''')


def comment(cid, body, assoc="OWNER", created="2026-10-08T20:00:00Z"):
    return {"id": cid, "body": body, "author_association": assoc, "user": {"login": "michael"},
            "created_at": created, "html_url": f"https://x/{cid}"}


@pytest.fixture
def env(tmp_path):
    gh = tmp_path / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    state = tmp_path / "state.json"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"min_post_interval_seconds": 0}))
    e = dict(os.environ, CAOS_INTAKE_DIR=str(tmp_path / "inbox"), CAOS_INTAKE_GH=str(gh),
             CAOS_INTAKE_CONFIG=str(cfg), FAKE_GH_STATE=str(state), FAKE_GH_LOG=str(tmp_path / "calls.log"))
    e.pop("CAOS_INTAKE_NUDGE_TMUX", None)

    def setstate(**kw):
        base = {"issue": comment(0, "issue body"), "comments": [], "labelled": []}
        base.update(kw)
        state.write_text(json.dumps(base))
    setstate()
    return e, setstate, tmp_path


def run(e, *args):
    return subprocess.run([sys.executable, str(POLL), *args], env=e, capture_output=True, text=True)


def lines(tmp, name):
    p = tmp / "inbox" / name
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def test_ingest_once_dedup_and_restart(env):
    e, setstate, tmp = env
    setstate(comments=[comment(1, "do the thing")])
    assert run(e).returncode == 0
    ids = [i["item_id"] for i in lines(tmp, "inbox.jsonl")]
    assert "gh:caosos/CAOSCARE.COM#117:comment:1" in ids and "gh:caosos/CAOSCARE.COM#117:body" in ids
    assert run(e).returncode == 0          # a second process, same data
    assert [i["item_id"] for i in lines(tmp, "inbox.jsonl")] == ids
    assert len([r for r in lines(tmp, "receipts.jsonl") if r["kind"] == "ingested"]) == len(ids)
    out = run(e, "--replay").stdout
    assert "comment:1" in out


def test_cursor_advances_and_uses_since(env):
    e, setstate, tmp = env
    setstate(comments=[comment(1, "a", created="2026-10-08T20:00:00Z")])
    run(e)
    cur = json.loads((tmp / "inbox/cursor.json").read_text())
    assert cur["issues"]["117"]["last_comment_id"] == 1
    run(e)
    calls = [json.loads(l) for l in (tmp / "calls.log").read_text().splitlines()]
    assert any("since=2026-10-08T20:00:00Z" in c[1] for c in calls)


def test_coordinator_marker_not_actionable(env):
    e, setstate, tmp = env
    setstate(comments=[comment(2, "<!-- caos:coordinator -->\nACK: x")])
    run(e)
    item = [i for i in lines(tmp, "inbox.jsonl") if i["item_id"].endswith("comment:2")][0]
    assert item["source"] == "coordinator" and item["status"] == "n/a"
    assert "comment:2" not in run(e, "--replay").stdout
    assert run(e, "status", item["item_id"], "ACK").returncode == 2


def test_untrusted_author_not_actionable(env):
    e, setstate, tmp = env
    setstate(comments=[comment(3, "do evil", assoc="NONE")])
    run(e)
    assert "comment:3" not in run(e, "--replay").stdout


def test_gh_failure_leaves_cursor_and_backs_off(env):
    e, setstate, tmp = env
    setstate(comments=[comment(1, "a")])
    run(e)
    before = (tmp / "inbox/cursor.json").read_text()
    setstate(comments=[comment(9, "b")], fail=True)
    assert run(e).returncode == 1
    cur = json.loads((tmp / "inbox/cursor.json").read_text())
    assert cur["issues"] == json.loads(before)["issues"] and cur["backoff"]["failures"] == 1
    assert lines(tmp, "receipts.jsonl")[-1]["kind"] == "poll_error"
    n = len((tmp / "calls.log").read_text().splitlines())
    setstate(comments=[comment(9, "b")])
    assert run(e).returncode == 0           # inside backoff: no gh call at all
    assert len((tmp / "calls.log").read_text().splitlines()) == n


def test_item_cap(env):
    e, setstate, tmp = env
    (tmp / "cfg.json").write_text(json.dumps({"max_items_per_run": 2, "min_post_interval_seconds": 0}))
    setstate(comments=[comment(i, f"c{i}", created=f"2026-10-08T20:00:0{i}Z") for i in range(1, 6)])
    run(e)
    assert len(lines(tmp, "inbox.jsonl")) == 2


def test_status_posts_are_deduped(env):
    e, setstate, tmp = env
    setstate(comments=[comment(1, "go")])
    run(e)
    iid = "gh:caosos/CAOSCARE.COM#117:comment:1"
    r = run(e, "status", iid, "ACK", "--note", "seen", "--post")
    assert r.returncode == 0 and "posted" in r.stdout
    again = run(e, "status", iid, "ACK", "--post")
    assert "already ACK" in again.stdout
    posts = [l for l in (tmp / "calls.log").read_text().splitlines() if "POST" in l]
    assert len(posts) == 1 and "caos:coordinator" in posts[0]
    run(e, "status", iid, "DONE")
    assert "comment:1" not in run(e, "--replay").stdout


def test_no_nudge_when_pane_missing(env):
    e, setstate, tmp = env
    e["CAOS_INTAKE_NUDGE_TMUX"] = "nonexistent-session-xyz:0"
    setstate(comments=[comment(1, "go")])
    run(e)
    assert any(r["kind"] == "nudge" and r["result"] == "pane_not_found" for r in lines(tmp, "receipts.jsonl"))
