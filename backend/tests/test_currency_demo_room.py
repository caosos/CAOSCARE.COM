"""A demo-room request (simulated, no simulator run) is current while recent, not hidden as past SIM work."""
import os, sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routes.operations_currency import classify  # noqa: E402

NOW = datetime(2026, 10, 12, 6, 30, tzinfo=timezone.utc)
ago = lambda **kw: (NOW - timedelta(**kw)).isoformat()


def test_demo_room_request_is_current_while_recent():
    assert classify({"simulated": True, "created_at": ago(minutes=5)}, "task", None, NOW)["bucket"] == "sim_current"
    assert classify({"simulated": True, "created_at": ago(days=30)}, "task", None, NOW)["bucket"] == "sim_past"


def test_run_bound_records_keep_the_run_rule():
    rec = {"simulated": True, "simulation_run_id": "run1", "created_at": ago(minutes=5)}
    assert classify(rec, "task", "run1", NOW)["bucket"] == "sim_current"
    assert classify(rec, "task", None, NOW)["bucket"] == "sim_past"
    assert classify(rec, "task", "run2", NOW)["bucket"] == "sim_past"
