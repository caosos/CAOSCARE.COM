"""Owner operating addendum (2026-10-11): receipt schema, exact timer, three outcomes, early DONE,
missed-check exception, notification filtering, and the probe reading next_check_at from the ledger."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eta_receipts as er  # noqa: E402

TZ = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 11, 19, 0, tzinfo=TZ)
BASE = dict(project="CAOSCare", task_id="careops-x-001", owner="caoscare-1-ee", stage="building", evidence="tests green",
            eta="40 min", acceptance="gate + browser", blocker="NONE")


def test_ack_and_working_need_every_field_and_an_exact_timezone():
    r = er.build("ACK", next_check_at="2026-10-11T19:40:00-05:00", **BASE)
    assert r["next_check_at"] == "2026-10-11T19:40:00-05:00"
    with pytest.raises(er.ReceiptError, match="missing: eta, next_check_at"):
        er.build("WORKING", **{k: v for k, v in BASE.items() if k != "eta"})
    with pytest.raises(er.ReceiptError, match="no timezone"):
        er.build("ACK", next_check_at="2026-10-11T19:40:00", **BASE)
    with pytest.raises(er.ReceiptError, match="missing: blocker"):
        er.build("ACK", next_check_at="2026-10-11T19:40:00-05:00", **{**BASE, "blocker": ""})


def test_done_and_need_have_their_own_required_fields():
    with pytest.raises(er.ReceiptError, match="loaded_revision"):
        er.build("DONE", project="CAOSCare", task_id="t", owner="o", commit="abc", tests="ok", evidence="e",
                 host_observation="h", user_visible_result="u", timestamp="now", next_item="n")
    r = er.build("NEED", project="CAOSCare", task_id="t", owner="o", blocker="no driver", action="add one",
                 impact="live check blocked", compatible_work="routing audit", next_check_at="2026-10-11T20:00:00-05:00")
    assert "next_check_at: 2026-10-11T20:00:00-05:00" in er.render(r) and er.render(r).startswith("NEED")


def test_exact_timer_and_three_outcomes_with_early_done():
    r = er.build("WORKING", next_check_at="2026-10-11T19:40:00-05:00", **BASE)
    assert er.due(r, NOW) is False and er.due(r, NOW.replace(minute=40)) is True        # exact: not a minute early
    assert er.outcome(r, {}, NOW) is None                                               # healthy, not due: publish nothing
    assert er.outcome(r, {"done": True}, NOW) == "DONE"                                  # early DONE, immediately
    assert er.outcome(r, {"blocked": True}, NOW) == "NEED"
    assert er.outcome(r, {"blocked": True, "hard": True}, NOW) == "BLOCKED"
    assert er.outcome(r, {}, NOW.replace(minute=40)) == "WORKING"                        # at the check: revised receipt due
    assert {er.outcome(r, o, NOW.replace(minute=45)) for o in ({}, {"done": 1}, {"blocked": 1})} <= {"WORKING", "DONE", "NEED"}


def test_missed_check_is_an_exception_and_never_claims_the_worker_stopped():
    r = er.build("WORKING", next_check_at="2026-10-11T19:40:00-05:00", **BASE)
    assert er.missed(r, None, NOW.replace(minute=45)) is None                            # inside the grace window
    m = er.missed(r, None, NOW.replace(hour=20, minute=5))
    assert m["state"] == er.STALE and m["minutes_late"] == 25
    assert er.missed(r, "2026-10-11T19:50:00-05:00", NOW.replace(hour=20, minute=5)) is None   # a newer receipt clears it
    assert er.missed(r, None, NOW.replace(hour=20, minute=5), host_alive=False)["state"] == "HOST NOT RUNNING"


def test_notification_filter():
    assert er.should_notify("WORKING") is False                                         # routine healthy progress: silent
    assert er.should_notify("DONE") is False and er.should_notify("DONE", owner_acceptance=True) is True
    assert er.should_notify("NEED") and er.should_notify("BLOCKED") and er.should_notify("MISSED")
    assert er.should_notify("WORKING", failed_test=True) and er.should_notify("WORKING", material_cost=True)


def _probe(tmp, rows):
    sf = tmp / "status.json"; sf.write_text(json.dumps({"ready_unblocked": [], "workers": [], "questions": []}))
    d = tmp / "intake"; d.mkdir(exist_ok=True)
    (d / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    env = dict(os.environ, CAOS_STATUS_FILE=str(sf), CAOS_INTAKE_DIR=str(d))
    out = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "heartbeat_probe.py")], capture_output=True, text=True, env=env)
    return json.loads(out.stdout)


def test_probe_wakes_at_next_check_and_reports_a_missed_check(tmp_path):
    now = datetime.now(TZ)
    future = er.ledger_row(er.build("WORKING", next_check_at=(now + timedelta(minutes=30)).isoformat(), **BASE))
    p = _probe(tmp_path, [future])
    assert p["verdict"] == "IDLE" and p["next_check_at"] == future["next_check_at"]      # watchdog can schedule the exact time
    due = er.ledger_row(er.build("WORKING", next_check_at=(now - timedelta(minutes=2)).isoformat(), **BASE))
    assert _probe(tmp_path, [future, due])["reasons"] == ["next_check_at reached for careops-x-001"]
    late = er.ledger_row(er.build("WORKING", next_check_at=(now - timedelta(minutes=40)).isoformat(), **BASE))
    p = _probe(tmp_path, [late])
    assert p["verdict"] == "WAKE" and er.STALE in p["reasons"][0]


def test_cli_refuses_an_incomplete_receipt_and_records_a_valid_one(tmp_path):
    env = dict(os.environ, CAOS_INTAKE_DIR=str(tmp_path))
    cli = [sys.executable, str(Path(__file__).resolve().parents[1] / "eta_receipts.py")]
    bad = subprocess.run(cli + ["ACK", "-f", "project=CAOSCare"], capture_output=True, text=True, env=env)
    assert bad.returncode == 2 and "missing" in bad.stderr and not (tmp_path / "ledger.jsonl").exists()
    args = sum((["-f", f"{k}={v}"] for k, v in BASE.items()), [])
    ok = subprocess.run(cli + ["WORKING", "--in-minutes", "40"] + args, capture_output=True, text=True, env=env)
    assert ok.returncode == 0 and ok.stdout.startswith("WORKING")
    row = json.loads((tmp_path / "ledger.jsonl").read_text().splitlines()[-1])
    assert row["kind"] == "eta" and row["receipt"] == "WORKING" and row["task_id"] == "careops-x-001" and "-05:00" in row["next_check_at"]
