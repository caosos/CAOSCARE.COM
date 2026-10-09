import json, os, subprocess, sys, time
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / "heartbeat_probe.py"


def run(tmp, status, ledger=None, extra=None):
    sf = tmp / "status.json"
    sf.write_text(json.dumps(status))
    d = tmp / "intake"; d.mkdir(exist_ok=True)
    if ledger is not None:
        (d / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in ledger))
    env = dict(os.environ, CAOS_STATUS_FILE=str(sf), CAOS_INTAKE_DIR=str(d), **(extra or {}))
    out = subprocess.run([sys.executable, str(PROBE)], capture_output=True, text=True, env=env)
    return json.loads(out.stdout)


def test_idle_when_nothing_to_do(tmp_path):
    r = run(tmp_path, {"ready_unblocked": [], "workers": [], "questions": []})
    assert r == {"verdict": "IDLE", "reasons": []}


def test_wake_on_ready_work_and_questions(tmp_path):
    r = run(tmp_path, {"ready_unblocked": ["RQ-050"], "questions": ["which room?"]})
    assert r["verdict"] == "WAKE" and len(r["reasons"]) == 2


def test_wake_on_unacked_intake_item_but_not_acked(tmp_path):
    old = "2026-10-09T00:00:00+00:00"
    ledger = [{"kind": "received", "item_id": "da-1", "time": old}]
    assert run(tmp_path, {}, ledger)["verdict"] == "WAKE"
    ledger.append({"kind": "status", "item_id": "da-1", "status": "ACK", "at": old})
    assert run(tmp_path, {}, ledger)["verdict"] == "IDLE"


def test_wake_on_stalled_worker(tmp_path):
    wt = tmp_path / "wt"; wt.mkdir()
    subprocess.run(["git", "init", "-q", str(wt)], check=True)
    f = wt / "a.txt"; f.write_text("x")
    old = time.time() - 3 * 3600
    os.utime(f, (old, old))
    r = run(tmp_path, {"workers": [{"name": "w", "worktree": str(wt)}]})
    assert r["verdict"] == "WAKE" and "idle" in r["reasons"][0]


def test_unreadable_status_wakes(tmp_path):
    env = dict(os.environ, CAOS_STATUS_FILE=str(tmp_path / "missing.json"), CAOS_INTAKE_DIR=str(tmp_path))
    out = subprocess.run([sys.executable, str(PROBE)], capture_output=True, text=True, env=env)
    assert json.loads(out.stdout)["verdict"] == "WAKE"
