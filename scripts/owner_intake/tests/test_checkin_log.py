import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checkin_log as cl  # noqa: E402

F = {"phase": "Pilot readiness", "completed": "x", "evidence": "y", "current": "task · caoscare-1-ee · WORKING",
     "remaining": "a;b", "upcoming": "m1;m2", "eta": "30 min", "next_check_at": "2026-10-12T01:30:00-05:00",
     "blocker": "NONE", "michael_action": "NOTHING"}
R1 = "https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-1"
R2 = "https://github.com/caosos/CAOSCARE.COM/issues/129#issuecomment-2"
NOW = datetime(2026, 10, 12, 0, 45, tzinfo=ZoneInfo("America/Chicago"))


def test_entry_has_all_fields_and_chicago_time(tmp_path):
    log = tmp_path / "log.md"
    added, entry = cl.add(R1, F, now=NOW, log=log)
    assert added and "Monday, October 12, 2026 — 12:45 AM America/Chicago" in entry
    for label in cl.LABELS.values():
        assert label in entry
    assert "  1. a\n  2. b" in entry


def test_append_only_dedup_and_correction(tmp_path):
    log = tmp_path / "log.md"
    cl.add(R1, F, now=NOW, log=log)
    first = log.read_text()
    assert cl.add(R1, F, now=NOW, log=log)[0] is False and log.read_text() == first     # same receipt: not logged twice
    cl.add(R2, {**F, "eta": "10 min"}, supersedes=R1, now=NOW, log=log)
    text = log.read_text()
    assert text.startswith(first) and f"- **Supersedes:** {R1}" in text                 # earlier entry unchanged


def test_refuses_missing_fields_and_bad_receipt(tmp_path):
    with pytest.raises(ValueError, match="michael_action"):
        cl.add(R1, {k: v for k, v in F.items() if k != "michael_action"}, log=tmp_path / "l.md")
    with pytest.raises(ValueError, match="receipt"):
        cl.add("not-a-url", F, log=tmp_path / "l.md")
