"""Call-quality receipts (aria-room-runtime-fixes-001): a degraded WebRTC
stats window is graded DEGRADED/BAD with the evidence that decided it, and
the final receipt for the call carries the worst grade and its causes.
Pure grading plus one round trip through the running gate backend."""
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.realtime_call_quality import grade_window, summarize  # noqa: E402

BASE_URL = (os.environ.get("TEST_API_BASE") or os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")

GOOD = {"loss_pct": 0.2, "jitter_ms": 6, "rtt_ms": 70, "concealed_pct": 0.4, "ui_lag_ms_max": 20,
        "connection_state": "connected"}
CELLULAR = {"loss_pct": 6.0, "jitter_ms": 45, "rtt_ms": 180, "concealed_pct": 7.0, "ui_lag_ms_max": 30,
            "connection_state": "connected"}


def test_grades_and_evidence():
    assert grade_window(GOOD) == {"grade": "GOOD", "evidence": [], "causes": []}
    g = grade_window(CELLULAR)
    assert g["grade"] == "DEGRADED" and g["causes"] == ["network"]
    assert {e["metric"] for e in g["evidence"]} == {"loss_pct", "jitter_ms", "concealed_pct"}
    assert grade_window({**GOOD, "loss_pct": 9})["grade"] == "BAD"
    assert grade_window({**GOOD, "connection_state": "disconnected"})["grade"] == "BAD"
    page = grade_window({**GOOD, "ui_lag_ms_max": 1400})
    assert page["grade"] == "BAD" and page["causes"] == ["local_page"]      # the room page stalled, not Wi-Fi
    slow = grade_window({**GOOD, "response_latency_ms_median": 3100})
    assert slow["grade"] == "DEGRADED" and slow["causes"] == ["provider_latency"]


def test_summary_keeps_the_worst_window():
    s = summarize([{**grade_window(GOOD), "metrics": GOOD}, {**grade_window(CELLULAR), "metrics": CELLULAR}])
    assert s["overall"] == "DEGRADED" and s["window_grades"] == {"GOOD": 1, "DEGRADED": 1, "BAD": 0}
    assert s["peaks"]["loss_pct"] == 6.0


def test_round_trip_receipt():
    if not BASE_URL:
        pytest.skip("no backend named")
    sid = f"rt_q_{uuid.uuid4().hex[:8]}"
    url = f"{BASE_URL}/api/realtime-diagnostics/call-quality"
    assert requests.post(url, json={"session_id": sid, "phase": "interval", "room": "T", "metrics": GOOD},
                         timeout=10).json()["grade"] == "GOOD"
    assert requests.post(url, json={"session_id": sid, "phase": "interval", "room": "T", "metrics": CELLULAR},
                         timeout=10).json()["grade"] == "DEGRADED"
    final = requests.post(url, json={"session_id": sid, "phase": "final", "room": "T", "reason": "end_call_tool",
                                     "metrics": {**GOOD, "transcript": ["no"], "blob": {"x": 1}}}, timeout=10).json()
    rec = final["receipt"]
    assert rec["overall"] == "DEGRADED" and rec["windows"] == 3 and rec["ended_reason"] == "end_call_tool"
    assert "transcript" not in rec["final_window"]["metrics"] and "blob" not in rec["final_window"]["metrics"]
    assert requests.get(f"{BASE_URL}/api/realtime-diagnostics/call-quality/{sid}", timeout=10).status_code in (401, 403)
